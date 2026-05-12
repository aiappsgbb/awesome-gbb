---
name: foundry-evals
description: >
  Evaluate Foundry hosted agents using the two-phase invoke+score pattern and Foundry
  built-in evaluators. Covers sequential invocation, cold-start handling, dataset
  creation, evaluator configuration, RBAC for eval judges, and result interpretation.
  USE FOR: evaluate agent, run evals, test agent, benchmark agent, Foundry evaluators,
  task adherence, intent resolution, eval scores, agent quality, create eval dataset,
  score agent responses, eval RBAC, judge model.
  DO NOT USE FOR: deploying agents (use threadlight-deploy), designing processes
  (use threadlight-design), unit testing code.
---

# Foundry Agent Evaluations

Evaluate Foundry hosted agents using the **two-phase invoke+score** pattern with
Foundry's built-in evaluators.

## When to Use

- After deploying a hosted agent, to measure quality
- Running batch evaluations against test scenarios
- Comparing agent performance across versions
- Validating that business rules (BR-XXX from SpecKit) are followed

## Why Two Phases?

The Foundry SDK's `azure_ai_agent` target type does **NOT** correctly route to hosted
agent endpoints — it sends requests to the project endpoint instead of the agent's
dedicated endpoint. You must invoke the agent yourself, then score the results separately.

```
Phase 1: Invoke agent → collect responses
Phase 2: Score responses → Foundry evaluators
```

---

## Phase 1: Invoke the Agent

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="<project_endpoint>",
    credential=DefaultAzureCredential(),
    allow_preview=True,
)
oai = project.get_openai_client(agent_name="my-agent")

# Warm up — single-shot ping is INSUFFICIENT for hosted agents that
# scale to zero (15min idle). Use the retry loop pattern below for any
# eval likely to hit a cold container — verified KYC PoC May 2026, where
# a single ping returned server_error in ~9s and made all 5 scenarios
# fail 0/5 before the agent had even spun up.
print("Warming up...")
oai.responses.create(input="Hello", stream=False)

# Invoke each query SEQUENTIALLY
# Concurrent requests overwhelm cold-start containers → empty responses
results = []
for query in test_queries:
    response = oai.responses.create(input=query, stream=False)
    results.append({
        "query": query,
        "response": response.output_text,
    })
    print(f"✓ {query[:50]}...")
```

### Critical Rules

- **Sequential, not concurrent** — concurrent eval requests overwhelm cold-start containers
  and produce empty responses
- **Warm up first** — send a throwaway "Hello" before the real queries
- **Use `stream=False`** — simpler for eval; streaming works but adds complexity
- **agent-bound client** — `get_openai_client(agent_name=...)` routes to the dedicated endpoint
- **Token refresh for long runs** — `DefaultAzureCredential` tokens expire after ~1h. For 30+ scenarios, refresh the token every 10 items or create a fresh client per batch
- **Pace invocations** — add a **5s** `time.sleep()` between calls (was 2s — bumped after KYC PoC May 2026 saw repeat empty responses at 2s). Rapid-fire requests produce empty responses even after warm-up
- **Warmup retry loop, not single-shot** — a single warmup ping is NOT enough for hosted agents that scale to zero. First call to a cold container returns `server_error` in 5-10s before the platform has even brought a replica up. **Pattern (verified KYC PoC May 2026, recovered eval from 0/5 → 4/5 substantive):**

```python
# Warmup with retry loop — handles scale-from-zero hosted agents
WARMUP_ATTEMPTS = 4
WARMUP_BACKOFF_S = 60
print(f"[warmup] coldstart loop (up to {WARMUP_ATTEMPTS} retries with {WARMUP_BACKOFF_S}s backoff)...")
for attempt in range(1, WARMUP_ATTEMPTS + 1):
    try:
        r = oai.responses.create(input="ping", stream=False)
        status = getattr(r, "status", "unknown")
        print(f"[warmup] attempt={attempt} status={status}")
        if status == "completed":
            print("[warmup] READY -- proceeding with eval")
            break
    except Exception as e:
        print(f"[warmup] attempt={attempt} EXC {type(e).__name__}: {str(e)[:120]}")
    if attempt < WARMUP_ATTEMPTS:
        time.sleep(WARMUP_BACKOFF_S)
else:
    raise RuntimeError("Hosted agent failed to warm up after 4 attempts (4 minutes). Check the deployment.")
```
- **ASCII-only logging on Windows** — see `Eval scripts on Windows: cp1252 trap` below. The default Windows console encoding is **cp1252**, not UTF-8. Any `print('→')`, `print('×')`, or `print('·')` in `run_evals.py` blows up with `UnicodeEncodeError` mid-run, killing partial results. Use `->`, `x`, `::` (or set `PYTHONUTF8=1` in the venv bootstrap; see fix below).
- **Tolerate gateway flake on Phase 1** — Foundry's gateway can enter 5-10 minute sticky `internal_server_error` windows under burst load (especially mid-cold-start). 30-60s exponential backoff is **not** enough on bad days. See `Gateway flakiness during Phase 1` below for the resume-after-cooldown pattern.
- **Retry on empty** — `output_text` can return empty when the agent does tool calls but the response structure varies. Retry once after a 3s pause. Also scan `response.output` items for message text as a fallback:

```python
text = response.output_text or ""
if not text and response.output:
    for item in response.output:
        if getattr(item, "type", "") == "message":
            for content in getattr(item, "content", []):
                text += getattr(content, "text", "")
```

### Alternative: Direct SSE Invocations (GHCP SDK agents)

If the agent uses the Invocations protocol (GHCP SDK), you can't use
`oai.responses.create()`. Use the raw SSE endpoint instead:

```python
import aiohttp

url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"

async with aiohttp.ClientSession() as session:
    async with session.post(url, json={"input": query}, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Foundry-Features": "HostedAgents=V1Preview",
    }) as resp:
        full_text = ""
        async for line in resp.content:
            line = line.decode().strip()
            if line.startswith("data: "):
                event = json.loads(line[6:])
                if event.get("type") == "assistant.message_delta":
                    full_text += event.get("data", {}).get("content", "")
```

> **Prefer the Responses API pattern** (agent-bound OpenAI client) unless the agent
> specifically only supports Invocations. It's simpler and handles conversation state.

### Eval scripts on Windows: cp1252 trap

The default Windows Python console uses **cp1252**, not UTF-8. Any
non-Latin1 character in a `print(...)` call mid-eval produces:

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
in position 14: character maps to <undefined>
```

…and kills the eval run. We've burned an hour on this twice. Two
defenses, in priority order:

**1. ASCII-only logging in `eval/run_evals.py`** (the right fix)

```python
# BAD — fails on Windows cp1252
print(f"  -> {ms}ms · {len(text)} chars · attempt {attempt}")

# GOOD — works on every platform
print(f"  -> {ms}ms :: {len(text)} chars :: attempt {attempt}")
```

Banned characters: `→ × · ✓ ✗ ❌ ✅ ▶ ▲ ▼ ←  ° €` and any em-dash /
en-dash. Replacements: `-> x :: PASS FAIL ! [done] etc.`

**2. The agent's response can ALSO contain non-ASCII** (the gap that bit
us twice on KYC even with #1 in place)

Banning Unicode in your own `print()` calls only solves half the
problem. The hosted agent is free to emit `→`, em-dashes, smart quotes,
and curly arrows in its tool-result tables — and the moment your eval
prints `output_first_400={out_text!r}`, the **agent's** `→` blows up
the same way. Two layers, both required:

```python
# AT THE TOP OF run_evals.py — wrap stdout/stderr to silently
# replace any byte that doesn't fit the cp1252 console
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

def safe(s, n=None):
    """Strip everything not ASCII before printing agent text."""
    if s is None:
        return ""
    if n:
        s = s[:n]
    return s.encode("ascii", errors="replace").decode("ascii")

# Then use safe() on every agent string you print:
print(f"  output_first_400: {safe(out_text, 400)!r}")
```

`io.TextIOWrapper(.., errors='replace')` is **the** fix for this — it
turns any otherwise-fatal `UnicodeEncodeError` into a `?` substitution
silently. Without it, even one `→` in one tool-result line aborts the
whole eval and you lose all results-so-far (see § Incremental result
writes below for the corollary mitigation).

**3. PYTHONUTF8=1 in the venv bootstrap** (defense in depth)

If you can't audit every `print` (e.g., a vendored library prints
arrows), force the interpreter into UTF-8 mode at process start. This
MUST be in the parent shell **before** Python launches:

```powershell
# scripts/setup_eval_env.ps1
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip sync requirements.txt
```

```bash
# scripts/setup_eval_env.sh
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
uv venv .venv
source .venv/bin/activate
uv pip sync requirements.txt
```

Setting these inside the script (`os.environ["PYTHONUTF8"] = "1"`)
**does not work** — by the time the assignment runs, Python's stdio
encoding is already locked. (Defense #2 above DOES work mid-script
because it rebuilds the wrapper from raw `sys.stdout.buffer`.)

The same trap kills `az acr build` log streaming on Windows; fix
there is `--no-logs` (separate skill: `foundry-mcp-aca`).

### Incremental result writes (mandatory default, not just for big batches)

The "Resume-after-cooldown" pattern in the next section is framed as
"recommended for batches > 5 scenarios." Treat that as a floor, not a
ceiling — **every** `run_evals.py` should write its results JSON
**after each scenario completes**, not at the end of the loop. Three
real things that have wiped a full eval batch this pilot cycle:

1. `UnicodeEncodeError` on the agent's response (the trap above) —
   killed v10/v12 mid-S-019 every cold-start run, lost 4 prior results.
2. Foundry gateway sticky 5xx window — kills attempt N, you lose 1..N-1.
3. Ctrl+C / shell window closed by accident — same outcome.

```python
from pathlib import Path
RESULTS_PATH = Path("eval/results.json")
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
results = []
for sc in selected:
    rec = run_one(sc)
    results.append(rec)
    # Write after EVERY scenario, not just at the end of the loop
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
```

The cost is one tiny disk write per scenario (~5ms). The benefit is
that a kill at scenario 4 of 5 still leaves you with 4 scored results
on disk, ready to rerun-the-tail on top.

### Gateway flakiness during Phase 1

Foundry's gateway occasionally enters 5-10+ minute sticky windows of
`internal_server_error` (or `503 model overloaded`) — typically right
after a cold-start burst, or when an upstream model deployment is
being reconfigured. The 30-60s exponential backoff most retry libraries
ship with is **not enough** on bad days.

Two patterns:

**Pattern A — Resume-after-cooldown (recommended for batches > 5
scenarios).** Persist results-so-far to disk after every successful
case, and add a `--resume` flag that skips already-completed `case_id`s.
Then a sticky-flake window just means "wait 10 min, re-run; it picks
up where it left off". `eval/run_evals.py` should look like:

```python
results_path = Path("eval/results.partial.json")
done_ids = set()
if results_path.exists() and "--resume" in sys.argv:
    done_ids = {r["case_id"] for r in json.loads(results_path.read_text())}

for case in cases:
    if case["case_id"] in done_ids:
        print(f"  [skip] {case['case_id']} already done")
        continue
    try:
        result = invoke_with_retry(case, max_retries=3, base_delay=60)
    except GatewayFlakeException:
        print(f"  [defer] {case['case_id']} -- gateway sticky, re-run with --resume")
        break  # don't burn budget
    append_result(results_path, result)
```

**Pattern B — Skip-and-mark.** If the SLA is "best 5 of 6" rather than
"all 6", record gateway failures as `status: GATEWAY_FLAKE` (NOT
`FAIL`), exclude them from scoring, and report the count in the run
summary. Don't let infrastructure noise pollute the agent-quality
signal.

> Both patterns are about **separating gateway flake from agent
> quality**. A failed retry on `internal_server_error` is not an
> eval-quality failure; it's a Foundry-side incident. Score them
> separately or you'll spend a day debugging a "regression" that
> turns out to be a 7-minute gateway window.

---

## Phase 2: Score with Foundry Evaluators

Foundry evals have two concepts:
- **Eval definition** — the evaluator configuration (metrics, data schema, judge model).
  Create this **once**, reuse across runs. Only recreate when changing metrics.
- **Eval run** — a single execution against a dataset. Create a new run for each
  test cycle, agent version, or dataset update.

### Step 2a: Create eval definition (once)

```python
# Use a NON-agent-bound client for evals
client = project.get_openai_client()  # NOT agent_name=...

# Judge model — MUST be gpt-5.4-mini (see quirks below)
JUDGE_MODEL = "gpt-5.4-mini"
EVAL_NAME = "my-agent-eval"

# Check if definition already exists
existing_evals = list(client.evals.list())
eval_def = next((e for e in existing_evals if e.name == EVAL_NAME), None)

if not eval_def:
    eval_def = client.evals.create(
        name=EVAL_NAME,
        data_source_config={
            "type": "custom",
            "item_schema": {
                "type": "object",
                "properties": {
                    "query": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "object"}}]},
                    "response": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "object"}}]},
                    "tool_definitions": {"anyOf": [{"type": "object"}, {"type": "array", "items": {"type": "object"}}]},
                },
                "required": ["query", "response"],
            },
            "include_sample_schema": True,
        },
        testing_criteria=[
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.intent_resolution",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                    "tool_definitions": "{{item.tool_definitions}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.task_adherence",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                    "tool_definitions": "{{item.tool_definitions}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.task_completion",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                    "tool_definitions": "{{item.tool_definitions}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.coherence",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.tool_selection",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                    "tool_definitions": "{{item.tool_definitions}}",
                },
            },
            {
                "type": "azure_ai_evaluator",
                "evaluator_name": "builtin.tool_output_utilization",
                "initialization_parameters": {"deployment_name": JUDGE_MODEL},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{item.response}}",
                    "tool_definitions": "{{item.tool_definitions}}",
                },
            },
        ],
    )
    print(f"Created eval definition: {eval_def.id}")
else:
    print(f"Reusing eval definition: {eval_def.id}")
```

### Step 2b: Create eval run (every time)

```python
# Create a new run against the existing definition.
# `name=` is REQUIRED as of the late-2026 Foundry preview ` omitting it returns
# `400 UserError: Evaluation display name is required is invalid`.
import time

run = client.evals.runs.create(
    eval_id=eval_def.id,
    name=f"{EVAL_NAME}-run-{int(time.time())}",   # required
    data_source={
        "type": "jsonl",
        "source": {
            "type": "file_content",
            "content": [{"item": r} for r in results],
        },
    },
)

print(f"Eval run: {run.id} ` status: {run.status}")
```

> **`name=` field is mandatory.** The skill's earlier examples didn't
> include it because the API used to accept `name=None`. Current preview
> rejects the run. Always pass a unique display name (timestamped is
> simplest) so the run appears in the Foundry portal eval list.

> **Do NOT call `client.evals.create()` every run.** The definition is reusable —
> only the dataset changes between runs. Creating a new definition per run clutters
> the eval dashboard and makes trending impossible.

### JSONL Data Format

Each item in the eval dataset MUST include `tool_definitions` for the tool evaluators
to work. Extract tool definitions from the agent's MCP tools or `@tool` functions:

```json
{
    "query": "Process loan application LA-1001",
    "response": "Based on the credit check...",
    "tool_definitions": [
        {
            "name": "get_customer_profile",
            "description": "Look up customer by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "Customer ID"}
                }
            }
        }
    ]
}
```

> **Without `tool_definitions`**, `tool_selection` and `tool_output_utilization`
> evaluators silently return 0% — they can't assess tool usage without knowing
> what tools were available.

### Enriched dataset shape (recommended for tool-using agents)

`tool_definitions` tells the judge which tools exist. It does NOT tell
the judge **what each tool returned for this query**. Without that
context, `tool_output_utilization` flags any tool-derived fact in the
response (mailing addresses pulled from `get_customer`, citations
emitted by `lookup_rule`, account numbers, dates) as **fabricated** ` and
the score craters.

Capture the agent's tool transcript during Phase 1 invoke and emit it
on every row:

```json
{
    "query": "Process dispute dc-001",
    "response": "Based on Reg E ` 1005.11(c)(1), provisional credit is required ` ",
    "tool_definitions": [
        { "name": "get_dispute_case", "type": "function", "parameters": {"} },
        { "name": "lookup_reg_rule",  "type": "function", "parameters": {"} }
    ],
    "tool_calls": [
        {
            "id": "call_001",
            "type": "tool_call",
            "name": "get_dispute_case",
            "arguments": {"case_id": "dc-001"}
        },
        {
            "id": "call_002",
            "type": "tool_call",
            "name": "lookup_reg_rule",
            "arguments": {"jurisdiction": "us", "rule_id": "12 CFR 1005.11(c)(1)"}
        }
    ],
    "tool_outputs": [
        {
            "tool_call_id": "call_001",
            "output": "{\"case_id\":\"dc-001\",\"customer_address\":\"248 Westbridge Road, Concord MA\",}"
        },
        {
            "tool_call_id": "call_002",
            "output": "{\"text\":\"The financial institution shall provisionally credit ` within 10 business days `\"}"
        }
    ]
}
```

The `data_source_config.item_schema` and per-evaluator `template`
mapping must thread `tool_calls` + `tool_outputs` through to each
evaluator that uses them ` add the same `{{item.tool_calls}}` /
`{{item.tool_outputs}}` tokens you already use for `{{item.tool_definitions}}`.

Capture pattern in `eval/run_evals.py`:

```python
# During Phase 1 invoke, scrape the tool transcript from the response
def extract_tool_transcript(response):
    calls, outputs = [], []
    for item in response.output:
        if getattr(item, "type", None) == "function_call":
            calls.append({
                "id": item.call_id,
                "type": "tool_call",
                "name": item.name,
                "arguments": json.loads(item.arguments),
            })
        elif getattr(item, "type", None) == "function_call_output":
            outputs.append({
                "tool_call_id": item.call_id,
                "output": item.output,
            })
    return calls, outputs

# Then emit them on the JSONL row:
calls, outputs = extract_tool_transcript(response)
results.append({
    "case_id": case["case_id"],
    "query":   case["query"],
    "response": response.output_text,
    "tool_definitions": case["tool_definitions"],
    "tool_calls":   calls,
    "tool_outputs": outputs,
})
```

> **Without `tool_outputs`**, `tool_output_utilization` will FLAG every
> grounded answer as fabricated ` even when the response is verbatim
> from a tool result. We hit this on the `card-dispute-investigation`
> reference PoC: 6/6 cases FLAGed despite the agent emitting real
> mailing addresses, real CFR citations, and real Reg E timer values
> straight from `get_dispute_case` + `lookup_reg_rule`. Adding the
> transcript flipped the same 6 cases to PASS.

---

## Built-in Evaluators

All evaluator names use the `builtin.` prefix.

| Evaluator | What It Measures | Requires `tool_definitions`? | When to Use |
|-----------|-----------------|:---:|-------------|
| `builtin.intent_resolution` | Did the agent understand user intent? | ✅ | Always |
| `builtin.task_adherence` | Did the agent follow system instructions? | ✅ | Always |
| `builtin.task_completion` | Did the agent complete the requested task? | ✅ | Always |
| `builtin.coherence` | Is the response logical and well-structured? | ❌ | Always |
| `builtin.tool_selection` | Did the agent pick the right tools? | ✅ | When agent has tools |
| `builtin.tool_output_utilization` | Did the agent use tool results effectively? | ✅ | When agent has tools |

### Recommended Minimum Set

For most agents, run at least:
- `builtin.task_adherence` — follows instructions?
- `builtin.task_completion` — completed the task?
- `builtin.intent_resolution` — understood user intent?
- `builtin.coherence` — logical response?

Add `tool_selection` and `tool_output_utilization` if the agent uses tools.

---

## Evaluator RBAC

The eval judge models need model access. Assign these roles:

| Principal | Role | Scope |
|-----------|------|-------|
| Your user identity | `Cognitive Services OpenAI User` | AI Services account |
| Account managed identity | `Cognitive Services OpenAI User` | AI Services account |
| Project managed identity | `Cognitive Services OpenAI User` | AI Services account |

Without these, evals fail with permission errors on the judge model.

### TPM Requirements

- **Minimum 300K TPM** recommended for eval runs
- Judge models consume significant tokens per evaluation item
- Lower TPM → 429 rate limits → incomplete eval results

---

## Creating Test Datasets

### From SpecKit Evaluation Scenarios

If you used `threadlight-design` with SpecKit, your `specs/SPEC.md` § 9 contains
evaluation scenarios (S-XXX) linked to business rules (BR-XXX):

```python
# Convert spec scenarios to eval queries
test_queries = [
    "Process a loan application: credit score 780, income $120K, amount $50K",  # S-001: happy path
    "Process a loan application: credit score 520",  # S-002: auto-decline
    "Process a loan: credit score 650, DTI 40%",  # S-003: human review
]
```

### From Production Traces

Create datasets from real agent interactions:

```python
# List recent traces
traces = project.telemetry.list_traces(
    agent_name="my-agent",
    start_time=start,
    end_time=end,
)

# Extract query/response pairs
dataset = [
    {"query": t.input, "response": t.output}
    for t in traces
    if t.status == "completed"
]
```

---

## Tool-Use Discipline

A common eval failure: agents over-call tools (e.g., `list_databases`, `get_schema`)
on every turn, causing `tool_selection` scores of 30-50% instead of 80%+.

### Tool Budget

Broad queries like "tell me everything about customer X" can trigger **>5 minute tool loops**
where the agent chains 10-20 tool calls. This is expensive (tokens + latency) and hurts
eval scores. Add a tool budget directive:

```
## Tool Budget

Limit yourself to a maximum of 5 tool calls per user message. If you need more data,
ask the user to narrow their question. Do NOT exhaustively scan all collections or
databases — target the specific data you need.
```

Adjust the budget (3-8 calls) based on the process complexity. Simpler processes
need fewer; complex multi-step workflows may need more.

### Task Adherence vs Tools Trade-off

> **Known trade-off:** `task_adherence` scores tend to **drop 5-15%** when the agent
> has many tools available. The evaluator penalizes the agent for spending tokens on
> tool calls instead of directly addressing the user's question.
>
> This is expected — don't chase 100% task_adherence if the agent needs tools to do
> its job. Focus on `tool_selection` + `tool_output_utilization` being high (80%+)
> alongside reasonable task_adherence (70%+).

**Fix:** Add a tool-use discipline directive to the agent's system instructions:

```
## Tool-Use Discipline

Only call tools when the user's request requires data you don't already have.
Do NOT call list_databases, get_schema, or exploratory tools on every turn.
If you already have the data from a previous tool call, use it directly.
```

This is critical for `builtin.tool_selection` and `builtin.tool_output_utilization` scores.

---

## Reading the run results

> **Trap.** `run.result_counts` and `output_items[*].results[*].passed`
> are unreliable in the current preview ` they consistently return
> `passed=0 / failed=0 / errored=0 / total=N` and `passed=None` even
> on runs that actually scored fine. The real verdicts live one level
> deeper.

The actual scores live in `output_items[*].results[*].sample.output[0]`
under the `content` field, as a JSON-encoded string (or `<S2>n</S2>`
markers for `coherence`). Extract them yourself:

```python
import json, re

def extract_score(result, evaluator_name: str):
    """Pull the real score from a Foundry eval result row."""
    out = (result.get("sample") or {}).get("output") or []
    if not out:
        return None
    content = out[0].get("content") or ""
    # Coherence emits `<S2>n</S2>` markers
    if "coherence" in evaluator_name:
        m = re.search(r"<S2>(\d)</S2>", content)
        return int(m.group(1)) if m else None
    # All other evaluators emit JSON
    try:
        verdict = json.loads(content)
        # Score field name varies: "score", "label", "verdict", "passed"
        return verdict.get("score") or verdict.get("label") or verdict.get("verdict")
    except json.JSONDecodeError:
        return None

# Aggregate per evaluator across all rows
run = client.evals.runs.retrieve(eval_id=eval_def.id, run_id=run.id)
items = client.evals.runs.output_items.list(
    eval_id=eval_def.id, run_id=run.id,
)

per_evaluator = {}
for item in items:
    for result in item.get("results", []):
        ev = result.get("name") or result.get("evaluator")
        score = extract_score(result, ev)
        per_evaluator.setdefault(ev, []).append(score)

for ev, scores in per_evaluator.items():
    ok = [s for s in scores if s is not None]
    print(f"{ev}: {len(ok)}/{len(scores)} scored ` values: {ok}")
```

> **Why both layers exist.** The `result_counts` API is for binary
> pass/fail evaluators that haven't been GA'd yet. The built-in judges
> (intent_resolution, task_adherence, etc.) are scoring evaluators ` they
> emit a 1-5 score, a label like `FLAG/FAIL`, or a `<S2>n</S2>` block
> in `content`. The pass/fail summary is therefore always 0/0/0/N.
> Use the extractor above for any production reporting.

A reusable `eval/compile_scores.py` helper that does this end-to-end
(per-case  per-evaluator matrix) is in the
`card-dispute-investigation` reference PoC.

## Interpreting Results

| Score Range | Quality | Action |
|-------------|---------|--------|
| 80-100% | Good | Monitor, iterate on edge cases |
| 60-79% | Needs work | Review failing scenarios, improve instructions |
| 40-59% | Poor | Major instruction rewrite, tool-use discipline, check data access |
| <40% | Broken | Check deployment, RBAC, tool connectivity |

### Common Failure Patterns

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Low `task_adherence` | Instructions too vague or too long | Tighten copilot-instructions.md |
| Low `tool_selection` | Agent calls tools unnecessarily | Add tool-use discipline directive |
| Low `tool_selection` (MAF) | Tool name prefix mismatch — MCP tools exposed without `mcp-tools-` prefix but JSONL tool_definitions use prefixed names | Include both prefixed and unprefixed names in tool_definitions, or normalize in JSONL |
| Low `tool_output_utilization` | Agent reads tool output but hallucinated data references | Check model precision — gpt-5.4-mini may hallucinate rule numbers; try gpt-5.4 |
| `tool_output_utilization` FAILs every case despite grounded answers | Dataset only ships `query` + `response` ` evaluator can't see the actual tool output, so it flags tool-derived facts as fabricated. Add `tool_calls` + `tool_outputs` arrays to each JSONL row (see "Enriched dataset shape" below) | Capture the agent's tool transcript during Phase 1 invoke and pass it through to Phase 2 |
| Low `intent_resolution` | Agent misunderstands domain terms | Add domain vocabulary to instructions |
| All scores 0 | Empty responses | Concurrent eval requests; switch to sequential |
| `task_adherence` 0% specifically | Using wrong judge model (gpt-5.4 instead of gpt-5.4-mini) | **Must use gpt-5.4-mini as judge** — gpt-5.4 penalizes tool claims it can't verify |
| `tool_selection` + `tool_output_utilization` both 0% | Missing `tool_definitions` in JSONL | Every JSONL item must include `tool_definitions` array |
| Eval run fails | RBAC missing on judge model | Assign `Cognitive Services OpenAI User` |
| Inconsistent scores | Low TPM causing rate limits | Increase to ≥300K TPM |
| Scenario fails but agent is correct | Eval scenario references data not in seed/mock data | Align scenario IDs with actual sample data (e.g., S-003 uses LA-1011 but only LA-1001..1003 exist) |
| Broad query causes >5min tool loop | No tool budget in instructions | Add tool budget directive: "max 5 tool calls per message" |
| `task_adherence` drops when tools added | Known trade-off — evaluator penalizes tool call overhead | Expected 5-15% drop; focus on tool_selection + tool_output_utilization being 80%+ |
| `task_adherence` recovers with conversation format | Using plain string query instead of conversation-format + tool_definitions | Use conversation-format query (messages array) and always include `tool_definitions` — evaluator scores improve significantly |
| BYOK token expires during long eval | Many sequential invocations exhaust the ~1h token | Refresh BYOK token per invocation: mint fresh `_get_provider()` every ~30 scenarios or create new session |
| `task_completion` = 0% but agent works | MCP tools not deployed — agent can't complete tasks that need tool calls | This is a deployment gap, not a quality failure. Deploy MCP server first, then re-run evals. |

---

## Tool Evaluator Quirks (Hard-Won Lessons)

These were discovered through dual-variant benchmarking (GHCP vs MAF, 11
scenarios, 6 evaluators each) during the threadlight pilot run. The
findings below are the durable, evaluator-side conclusions — there is no
public companion analysis to link to.

### 1. Judge Model: MUST be gpt-5.4-mini

**Always** set `initialization_parameters.deployment_name` to `gpt-5.4-mini`.

Using `gpt-5.4` as judge causes `task_adherence` to drop to 0% — it penalizes
responses that claim tool usage because it can't verify the tool calls from
response-only data. `gpt-5.4-mini` is more forgiving and produces accurate scores.

All other evaluators (coherence, intent, completion) are stable across both judge models.

### 2. Tool Name Prefix Mismatch (MAF vs GHCP)

GHCP SDK's declarative MCP config auto-prefixes tool names (e.g., `mcp-tools-find_document_by_id`).
MAF's `client.get_mcp_tool()` exposes raw names (e.g., `find_document_by_id`).

If your JSONL `tool_definitions` uses prefixed names but the agent response uses unprefixed
names, the evaluator sees them as "wrong" tools → `tool_selection` drops 20-30%.

**Fix:** Include BOTH prefixed and unprefixed names in `tool_definitions`, OR normalize
tool names in your JSONL generation to match what the agent actually uses.

### 3. `load_skill` Calls Are Penalized

If the agent calls `load_skill` to read business rules before acting (good practice!),
evaluators penalize the extra tool calls because `load_skill` isn't directly relevant
to the data task.

**Fix options:**
- Pre-load skills into the system prompt (reduces tool calls)
- Accept the score penalty (the agent behavior is actually correct)
- Exclude `load_skill` from `tool_definitions` in the JSONL

### 4. Coherence Evaluator Doesn't Need tool_definitions

`builtin.coherence` only needs `query` + `response`. Don't pass `tool_definitions`
to it — it may confuse the judge. All other 5 evaluators benefit from having
tool_definitions for context.

### 5. Seed Data Alignment is Critical

If an eval scenario references data IDs that don't exist in the mock/seed data
(e.g., scenario asks about `LA-1011` but only `LA-1001..1003` are seeded), both
agent variants will fail — but differently:
- GHCP: gracefully says "not found" (partial credit)
- MAF: may return empty response (zero credit)

**Fix:** Always align scenario inputs with actual sample data.

### 6. GHCP vs MAF Benchmark Summary

From a validated 11-scenario benchmark:

| Evaluator | GHCP | MAF | Notes |
|-----------|:----:|:---:|-------|
| Intent Resolution | 82% | 82% | Tied — both understand intent equally |
| Task Adherence | 82% | 82% | Tied with gpt-5.4-mini judge |
| Task Completion | 82% | 73% | GHCP slightly better |
| Coherence | 100% | 91% | Both excellent |
| Tool Selection | 82% | 55% | **GHCP +27%** — tool name prefix mismatch inflates MAF failures |
| Tool Output Utilization | 91% | 64% | **GHCP +27%** — MAF hallucinated rule references |

**Bottom line:** Both models understand intent equally. GHCP wins on tool precision.
MAF is chattier (6.0 tool calls/scenario vs 3.7) but less precise with tool output.

---

## Eval Trending

Track scores over time by creating new **runs** against the same **definition**:

```python
# List all runs for a definition — shows score progression
runs = client.evals.runs.list(eval_id=eval_def.id)
for run in runs:
    print(f"{run.created_at}: {run.metrics}")
```

This only works when reusing the same eval definition. If you create a new definition
per run, each has only one run and trending is impossible.

Re-run evals after each agent version update to ensure quality doesn't regress.

---

## Continuous Evaluation Loop (production telemetry → KPIs)

One-shot pre-deploy evaluation tells you "the agent shipped working".
**Continuous evaluation** tells you "the agent is *still* working in production
six weeks later". Wire this for every threadlight pilot — it's how the customer
proves the agent earned its budget at the next steering committee.

### Plan A (default): Foundry built-in continuous evaluation

**Use this first.** As of `azure-ai-projects>=2.0.0` (May 2026), Foundry has a
first-party `EvaluationRule` API that runs evaluators on **every response**
(or sampled) without you owning a cron job. It's wired through the Foundry
project itself, results land in the **Agent Monitoring Dashboard**, and works
for both Prompt Agents AND hosted agents.

**Setup (Python — also available in .NET):**

```bash
pip install "azure-ai-projects>=2.0.0" python-dotenv
```

```python
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    EvaluationRule,
    ContinuousEvaluationRuleAction,
    EvaluationRuleFilter,
    EvaluationRuleEventType,
)

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"], credential=credential) as project_client,
    project_client.get_openai_client() as openai_client,
):
    # 1. Define the evaluation (judges + criteria)
    eval_object = openai_client.evals.create(
        name="threadlight-continuous-eval",
        data_source_config={"type": "azure_ai_source", "scenario": "responses"},
        testing_criteria=[
            {"type": "azure_ai_evaluator", "name": "task_adherence", "evaluator_name": "builtin.task_adherence"},
            {"type": "azure_ai_evaluator", "name": "intent_resolution", "evaluator_name": "builtin.intent_resolution"},
            {"type": "azure_ai_evaluator", "name": "tool_call_accuracy", "evaluator_name": "builtin.tool_call_accuracy"},
        ],
    )

    # 2. Wire the rule that fires on every agent response
    rule = project_client.evaluation_rules.create_or_update(
        id="threadlight-continuous-rule",
        evaluation_rule=EvaluationRule(
            display_name="Threadlight continuous eval",
            description="Sample agent responses, score with built-in evaluators",
            action=ContinuousEvaluationRuleAction(
                eval_id=eval_object.id,
                max_hourly_runs=100,   # default cap; bump for high-volume processes
            ),
            event_type=EvaluationRuleEventType.RESPONSE_COMPLETED,
            filter=EvaluationRuleFilter(agent_name=os.environ["AZURE_AI_AGENT_NAME"]),
            enabled=True,
        ),
    )
```

**Required RBAC** (keyless throughout):
- The Foundry **project's own managed identity** needs **Azure AI User**
  (role ID `53ca6127-db72-4b80-b1b0-d745d6d5456d`) on the project itself.
  This is what runs the evaluators server-side. **Not your agent's UAMI;
  not your user account — the project's MI.**
- The project MI also needs `Cognitive Services OpenAI User` on whichever
  AOAI account hosts the **judge model** (typically `gpt-5.4` or `gpt-5.4-mini`),
  so the LLM-as-judge calls succeed.
- Verify with `az role assignment list --assignee <project-mi-principalId> --scope <project-resource-id>`
  before declaring the rule ready — silent failures here look like "no eval
  runs ever appear" with no error logged.

**Where results show up:**
- Foundry portal → agent → **Monitor** tab → evaluation charts
- Programmatically: `openai_client.evals.runs.list(eval_id=eval_object.id)`
- Each run has a `report_url` for the deep-dive HTML report

**What you also get for free**:
- **Scheduled Evaluations (preview)** — same rule shape but `event_type=SCHEDULED`,
  runs at a cadence against a pinned dataset (regression suite)
- **Red-team scans (preview)** — adversarial probes on the same agent
- **Alerts (preview)** — latency / token usage / eval-score / red-team thresholds wired to Action Groups

**Hosted-agent caveat (May 2026)**: continuous-eval works for hosted agents
on the **responses** protocol out of the box. Hosted agents using the
**invocations** protocol need `input_messages` shape in the `azure_ai_agent`
target — the rule still fires, but the data source must use the freeform
input format. Validate this with a small smoke test on day-1 of the pilot
(some hosted-agent preview features lag the protocol). If continuous-eval
silently emits no runs for an invocations-protocol hosted agent, fall back
to Plan B for that pilot until the gap closes.

**Reference samples**:
- [Continuous evaluation sample (Python)](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_continuous_evaluation_rule.py)
- [Scheduled evaluations sample (Python)](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py)
- [Agent Monitoring Dashboard docs](https://learn.microsoft.com/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard)

### Plan B (fallback): ACA Job continuous-eval pulling App Insights + Cosmos

Use this when **any** of the following is true:
- You need **custom KPIs** that aren't expressible as a built-in evaluator
  (e.g., `count(audit.decision == 'approved') / count(audit.decision != null)` —
  a business KPI computed from Cosmos audit records, not from agent traces)
- You need a **customer-facing App Insights workbook** branded for the COO
  (the Foundry Monitor tab is great for engineers, but COOs want a workbook)
- You need cross-source correlation (App Insights spans + Cosmos `case_audit` +
  external systems metrics) that the built-in `azure_ai_source` data source can't reach
- The hosted-agent invocations-protocol gap above (verify with day-1 smoke test)

**Architecture:**

```
┌──────────────┐  spans  ┌──────────────┐  pull   ┌──────────────────┐
│ Hosted Agent │ ──────► │ App Insights │ ◄────── │ continuous-eval  │
│   (production)         │   (telemetry) │         │   ACA Job (cron) │
└──────────────┘         └──────────────┘         └─────────┬────────┘
                                                            │
                                                  ┌─────────▼────────┐
                                                  │ score with       │
                                                  │ Foundry          │
                                                  │ evaluators       │
                                                  └─────────┬────────┘
                                                            │
                                              ┌─────────────┼──────────────┐
                                              ▼             ▼              ▼
                                       ┌──────────┐  ┌──────────┐  ┌──────────┐
                                       │ AppInsights │ Foundry │  │ Threshold│
                                       │  workbook   │ Eval Run │  │  alert   │
                                       │  (KPI dash) │ (history)│  │ (Action  │
                                       │             │          │  │  Group)  │
                                       └──────────┘  └──────────┘  └──────────┘
```

#### Step 1 — Read SPEC § 9 KPI table

Every threadlight SPEC's § 9 contains a **KPI table mapping business rules to
measurable outcomes**. Example:

```yaml
# specs/SPEC.md § 9 (excerpted)
kpis:
  - id: KPI-001
    business_rule: BR-001
    name: "Approval rate"
    metric: count(audit.decision == 'approved') / count(audit.decision != null)
    target: ">= 0.65"
    direction: higher-is-better
  - id: KPI-002
    business_rule: BR-007
    name: "SLA-met rate"
    metric: count(audit.sla.status == 'met') / count(audit.sla != null)
    target: ">= 0.95"
    direction: higher-is-better
  - id: KPI-003
    business_rule: BR-003
    name: "Tool-selection precision"
    metric: foundry_eval.tool_selection.f1
    target: ">= 0.85"
    direction: higher-is-better
```

The continuous-eval ACA Job translates each row into a query against App
Insights traces + Cosmos audit container, computes the metric, and writes to
both an App Insights workbook (for dashboarding) AND a Foundry eval run
(for trending).

#### Step 2 — Generate the ACA Job (delegates to threadlight-event-triggers)

Use the `aca-job-cron` scaffold from `threadlight-event-triggers`. The job
runs every N minutes (default: 15) and:

```python
# infra/jobs/continuous_eval/job.py
import asyncio
from datetime import datetime, timedelta, timezone
from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient
from azure.cosmos.aio import CosmosClient
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import metrics as otel_metrics

# These five helpers are co-located with this job in
# infra/jobs/continuous_eval/ — generated alongside job.py from the
# scaffolds documented in references/continuous-eval-job.md (this skill).
from .config import load_yaml
from .telemetry import emit_kpi_telemetry, raise_alert, record_foundry_eval_run
from .compute import compute_metric, breaches_threshold
from .sources import fetch_spans, fetch_audits

KPI_TABLE = load_yaml("specs/kpis.yaml")  # extracted from SPEC § 9

async def run():
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(minutes=15)

    spans = await fetch_spans(window_start, window_end)
    audits = await fetch_audits(window_start, window_end)

    metrics = {}
    for kpi in KPI_TABLE:
        value = await compute_metric(kpi, spans, audits)
        metrics[kpi["id"]] = value

        # Threshold check
        if breaches_threshold(value, kpi):
            await raise_alert(kpi, value, window_start, window_end)

    # Write to App Insights workbook table (custom telemetry)
    await emit_kpi_telemetry(metrics, window_end)

    # Write to Foundry eval run for trending
    await record_foundry_eval_run(metrics, window_end)

asyncio.run(run())
```

Idempotency: each window is keyed by `(window_start, window_end)` so re-running
the job for the same window doesn't double-count. Use the dedup pattern from
`threadlight-event-triggers/references/idempotency-patterns.md`.

#### Step 3 — Threshold alerts

For each KPI, the SPEC § 9 KPI table records the **direction** and **threshold
comparator** explicitly. The Bicep templater MUST split the threshold into a
KQL operator + numeric value — concatenating a string like `">= 0.65"` into a
KQL `where` clause yields `where avg_value < >= 0.65` and the rule fails to
deploy. KPI rows look like:

```yaml
# specs/SPEC.md § 9 (excerpt)
kpis:
  - id: alert_to_case_conversion_rate
    target_operator: ">="    # >= | <= | > | <
    target_value: 0.65       # numeric only
    direction: higher-is-better
    breach_operator: "<"     # KQL operator used in the alert query
```

Then the Bicep alert template uses `breach_operator` literally and
`target_value` as a number — never a glued string:

```yaml
# infra/modules/alerts.bicep (Phase 6 wires this if SPEC § 9 has KPIs)
resource alertRule 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = [for kpi in kpis: {
  name: 'kpi-${kpi.id}-breach'
  properties: {
    criteria: {
      allOf: [{
        query: 'customMetrics | where name == "${kpi.id}" | summarize avg_value=avg(value) by bin(timestamp, 30m) | where avg_value ${kpi.breach_operator} ${kpi.target_value}'
        threshold: 0
        operator: 'GreaterThan'
        timeAggregation: 'Count'
      }]
    }
    actions: { actionGroups: [actionGroup.id] }
    evaluationFrequency: 'PT15M'
    windowSize: 'PT1H'
  }
}]
```

Wire alerts via Azure Monitor Action Groups → Teams channel webhook or
PagerDuty.

#### Step 4 — App Insights workbook (the customer-facing KPI dashboard)

Generate a `infra/modules/kpi-workbook.bicep` that creates an App Insights
workbook with one tile per KPI:

- **Big number** with current value + target threshold
- **Trend line** over last 7 days
- **Color band** green / amber / red based on threshold proximity
- **Drill-down** to the underlying spans / audit records

This is the dashboard the customer's COO opens at the steering committee.
Make it look like the customer's brand (workbook themes are configurable).

#### Step 5 — Foundry eval trending (long-term quality drift)

Beyond the per-window KPI dashboard, also push each window's results to a
Foundry eval run so the long-term scoring history is preserved:

```python
async def record_foundry_eval_run(metrics, window_end):
    # Reuse the SAME eval definition for trending (per § Eval Trending above)
    run = await client.evals.runs.create(
        eval_id=PRODUCTION_EVAL_DEF_ID,
        name=f"continuous-{window_end.isoformat()}",
        data_source={
            "type": "telemetry",
            "appinsights_id": APPINSIGHTS_RESOURCE_ID,
            "window_start": (window_end - timedelta(minutes=15)).isoformat(),
            "window_end": window_end.isoformat(),
        },
    )
    return run
```

This gives the customer an "eval score over time" chart in Foundry portal
alongside per-window KPI tiles in App Insights.

#### Cost guardrails (Plan B)

A 15-minute cron job is ~96 runs/day = ~2900 runs/month. Each run pulls ~15
minutes of spans (typically <100 traces per process), scores them with
Foundry evaluators (~$0.05/run for `gpt-5.4-mini` judge), and emits ~15
custom metric data points. **Estimated cost: ~$5/month per process.**

If the customer wants to slow it down (e.g., hourly), change cron to `0 * * * *`
in the SPEC § 10b trigger declaration. The job re-reads SPEC at startup so no
code change.

### Troubleshooting (both plans)

| Issue | Cause | Fix |
|-------|-------|-----|
| Plan A: rule created but no eval runs appear | Project managed identity missing **Azure AI User** role on the project | Assign role per Setup section above, then generate fresh agent traffic |
| Plan A: `max_hourly_runs` exceeded | High-volume process | Bump cap (default 100) or set `event_type=SAMPLED` with sample rate |
| Plan A: hosted-agent invocations protocol — no runs fire | Service-side gap (preview) | Drop to Plan B for that pilot until protocol gap closes |
| Plan B: Continuous-eval job has no spans to score | App Insights connection on Foundry account missing | See `Eval Trending` section + threadlight-deploy gotchas |
| Plan B: Foundry evaluator 429 | Judge model TPM exhausted from concurrent windows | Use a dedicated judge deployment with 100K TPM |
| Plan B: KPI workbook shows blank | Custom metric not emitted | Check `emit_kpi_telemetry()` actually called `track_metric()` |
| Plan B: Alert never fires | Threshold off by ratio (forgot `* 100` for percentage) | Test with manual `customMetrics` query first |
| Plan B: Trending shows flat line | Same eval definition not reused | Hardcode `PRODUCTION_EVAL_DEF_ID` env var; never recreate the def |

---

## Input contract / Output artifacts

| Reads | From |
|-------|------|
| **SPEC.md § 9 KPI table** | `threadlight-design` (per-BR KPI mapping) |
| **SPEC.md § 10b Triggers** (cron schedule for continuous loop — Plan B only) | `threadlight-design` |
| App Insights spans (live — Plan B only) | The deployed agent |
| Cosmos `case_audit` container (live — Plan B only) | `threadlight-hitl-patterns` writes these |

| Produces | At | Plan |
|----------|-----|------|
| `tests/eval-dataset.json` | Pre-deploy eval dataset | Both |
| `infra/modules/continuous-eval-rule.bicep` *or* `scripts/setup_continuous_eval.py` | Foundry `EvaluationRule` provisioning | A |
| `infra/jobs/continuous_eval/job.py` | The cron job entry point | B |
| `infra/jobs/continuous_eval/Dockerfile` | Container for the ACA Job | B |
| `infra/modules/kpi-workbook.bicep` | App Insights workbook | B |
| `infra/modules/alerts.bicep` | Per-KPI scheduled query alert rules | B |
| `agent.yaml` env vars | `EVAL_DEFINITION_ID`, `KPI_WORKBOOK_ID` (B), `EVAL_RULE_ID` (A) | Both |
| `specs/kpis.yaml` | Extracted from SPEC § 9 — single source of truth at runtime | Both |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](../threadlight-design/) | Generates SPEC.md § 9 KPI table — the input contract for the continuous loop |
| [**threadlight-deploy**](../threadlight-deploy/) | Phase 6 wires the Plan-A `EvaluationRule` and (when needed) Plan-B `kpi-workbook.bicep` + `alerts.bicep` if SPEC § 9 has KPIs |
| [**threadlight-event-triggers**](../threadlight-event-triggers/) | Owns the `aca-job-cron` scaffold the **Plan B** loop runs on |
| [**threadlight-hitl-patterns**](../threadlight-hitl-patterns/) | Writes the `case_audit` records the **Plan B** loop reads for custom KPI computation |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | App Insights connection on Foundry account is prerequisite for both plans |

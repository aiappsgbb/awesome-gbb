---
name: foundry-evals
description: >
  Evaluate Foundry agents with agent-target runs or an explicit invoke+score fallback.
  Covers sequential invocation, cold-start handling, dataset
  creation, evaluator configuration, RBAC for eval judges, result interpretation,
  and native suite/data/evaluator lifecycle with official optimizer handoffs.
  USE FOR: evaluate agent
  post-deploy, score grounding quality, measure tool_selection, detect dataset drift,
  write custom grader, check URL citations, validate eval RBAC, day-1 smoke test,
  continuous eval loop, pre-merge eval gate, Foundry Evals SDK setup, evaluator
  framework, eval-driven optimization, ASSERT evaluators. DO NOT USE FOR: deploying
  agents (use threadlight-deploy), designing processes (use threadlight-design),
  unit testing code, reimplementing evaluator frameworks (foundry-assert is a
  historical name, not a shipped skill), writing your own optimizer loop
  (foundry-agent-optimizer is a historical name; use the official workflow).
metadata:
  version: "1.5.0"
---

# Foundry Agent Evaluations

Evaluate Foundry agents using the supported **agent-target** evaluation surface,
or an explicit **invoke+score** fallback with captured responses.

For the complete per-agent adoption and release-evidence workflow, see
[`foundry-agentops`](../foundry-agentops/SKILL.md). This skill remains
authoritative for deep evaluator configuration and dataset design; AgentOps
aggregates evidence and never replaces that evaluation contract.

## When to Use

- After deploying a hosted agent, to measure quality
- Running batch evaluations against test scenarios
- Comparing agent performance across versions
- Validating that business rules (BR-XXX from SpecKit) are followed

## Why Two Phases?

Two phases are a fallback, not a universal requirement. Current
[cloud evaluation guidance](https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation-targets)
supports `azure_ai_target_completions` with an `azure_ai_agent` target for prompt
and hosted agents. Select the path from the actual endpoint/protocol:

| Surface | Path |
|---|---|
| Supported prompt or hosted Responses agent | Agent-target run: query-only input, explicit agent name/version, `{{sample.output_text}}` for string evaluators or `{{sample.output_items}}` for interaction-aware evaluators. |
| Hosted Invocations agent | Use the documented freeform `input_messages` matching its real request contract; do not send a Responses template. The smoke helper below intentionally covers Responses only. |
| Existing captured responses, custom transport, or a confirmed unsupported target surface | Invoke explicitly, retain the real response/tool transcript, then score `{{item.response}}` as described in Phases 1 and 2 below. |

Start with one approved synthetic query. A created run is not success: poll to a
successful terminal state, download per-item `output_items`, and require actual
scores and usable responses. An auth, schema, model, or quota failure is **not**
permission to silently switch paths. Record the failure; use invoke+score only
when the surface requires it or the owner approves that fallback.

> **Canonical executable:** [references/python/eval_runner.py](references/python/eval_runner.py)
> implements a one-item agent-target or explicit invoke+score coherence smoke
> using `AIProjectClient.get_openai_client().evals`. See the
> [Day-1 recipe](#day-1-smoke-test-recipe-hosted-agent--mcp-tool-pilots).
> It does not replace full suites, custom graders or the local last-run adapter.

## Native suite, data and evaluator lifecycle

Use [the lifecycle checklist](references/native-lifecycle.md) for reviewed
suite generation, independent data/evaluator refresh, trace curation,
versioned comparisons and optimization. It adds the missing native workflow
without replacing the canonical captured-response `smoke_score`, citation
graders or existing output contracts. Use the official `microsoft-foundry`
workflow for native generation/optimizer orchestration; load only that
specific workflow, not a general deployment pipeline.

```
Phase 1: Invoke agent → collect responses
Phase 2: Score responses → Foundry evaluators
```

**When using the fallback:** complete both phases sequentially; never score an
invented response or treat a run ID as the agent's response.

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
# eval likely to hit a cold container. A single ping can return
# server_error in ~9s and make every scenario fail before the agent
# has even spun up.
print("Warming up...")
oai.responses.create(input="Hello", stream=False)

# MUST invoke each query SEQUENTIALLY (never concurrent)
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

- **DO NOT invoke concurrently** — concurrent eval requests overwhelm cold-start containers
  and produce empty responses. Sequential invocation is mandatory.
- **MUST warm up first** — send a throwaway "Hello" before the real queries using the retry
  loop pattern below (not a single ping). Cold containers return `server_error` in 5-10s
  before the platform has brought a replica up.
- **DO use `stream=False`** — simpler for eval and required for batch scoring.
- **MUST bind to agent endpoint** — use `get_openai_client(agent_name=...)` to route to
  the dedicated endpoint, not the project endpoint.
- **Token refresh for long runs** — `DefaultAzureCredential` tokens expire after ~1h. For 30+ scenarios, refresh the token every 10 items or create a fresh client per batch.
- **MUST pace invocations with 5s delay** — add `time.sleep(5)` between calls. Rapid-fire
  requests produce empty responses even after warm-up.
- **DO NOT poll container status API** — do NOT call `.../versions/{v}/containers/default`
  to check readiness on refreshed Foundry. This endpoint returns **HTTP 404** on modern hosted
  agents (the platform auto-provisions containers). Polling wastes 3+ minutes. Use the warmup
  chat loop below instead.

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

- **DO use ASCII-only logging on Windows** — see `Eval scripts on Windows: cp1252 trap` below.
  The default Windows console encoding is **cp1252**, not UTF-8. Any `print('→')`, `print('×')`,
  or `print('·')` in `run_evals.py` fails with `UnicodeEncodeError` mid-run, killing partial
  results. Use `->`, `x`, `::` instead (or set `PYTHONUTF8=1` in the venv bootstrap).
- **MUST tolerate gateway flake on Phase 1** — Foundry's gateway can enter 5-10 minute sticky
  `internal_server_error` windows under burst load (especially mid-cold-start). 30-60s exponential
  backoff is **not** enough. See `Gateway flakiness during Phase 1` below for the resume-after-cooldown pattern.
- **DO retry on empty response** — `output_text` can return empty when the agent does tool calls
  but the response structure varies. Retry once after a 3s pause. Also scan `response.output`
  items for message text as a fallback:

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
us twice in pilot runs even with #1 in place)

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
   killed agent versions mid-scenario every cold-start run, lost 4 prior results.
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

# Use an existing, approved chat-capable judge deployment.
import os
JUDGE_MODEL = os.environ["JUDGE_MODEL_DEPLOYMENT"]
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
# `name=` is REQUIRED as of Azure AI Projects SDK 2.0.x (May 2026).
# Omitting it returns: `400 UserError: Evaluation display name is required`.
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

print(f"Eval run: {run.id} · status: {run.status}")
```

> **`name=` field is mandatory (verified May 2026).** The API requires a unique display name
> to track runs in the Foundry portal. See
> [Foundry Agent Evaluations](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluations)
> for current documentation. **Note:** if running a later SDK version, check the
> [Foundry release notes](https://github.com/Azure/azure-sdk-for-python/releases)
> for any API changes.

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
emitted by `lookup_rule`, account numbers, dates) as **fabricated** and
the score craters.

Capture the agent's tool transcript during Phase 1 invoke and emit it
on every row:

> **Tip — bootstrap your eval set from local-test transcripts.**
> [`threadlight-local-test` **Pattern 0**](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-local-test/SKILL.md)
> can append every Quickstart chat turn to `tests/quickstart.jsonl` —
> exactly the schema this skill consumes. Run a few local demos, then
> promote the JSONL into your Foundry eval dataset without reshaping.

```json
{
    "query": "Process dispute CASE-<id>",
    "response": "The retrieved rule describes the conditions for provisional credit.",
    "tool_definitions": [
        { "name": "get_dispute_case", "type": "function", "parameters": {
            "type": "object", "properties": {"case_id": {"type": "string"}}
        } },
        { "name": "lookup_reg_rule", "type": "function", "parameters": {
            "type": "object", "properties": {
                "jurisdiction": {"type": "string"}, "rule_id": {"type": "string"}
            }
        } }
    ],
    "tool_calls": [
        {
            "id": "call_001",
            "type": "tool_call",
            "name": "get_dispute_case",
            "arguments": {"case_id": "CASE-<id>"}
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
            "output": "{\"case_id\":\"CASE-<id>\",\"customer_address\":\"<example-address>\"}"
        },
        {
            "tool_call_id": "call_002",
            "output": "{\"text\":\"Synthetic fixture: provisional credit depends on the applicable rule conditions.\"}"
        }
    ]
}
```

The `data_source_config.item_schema` and per-evaluator `template`
mapping must thread `tool_calls` + `tool_outputs` through to each
evaluator that uses them; add the same `{{item.tool_calls}}` /
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
> from a tool result. Recent investigation-style evals saw all cases
> flagged despite the agent emitting grounded addresses, citations,
> and timer values straight from MCP tools. Adding the
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

### Evaluator Troubleshooting

| Symptom | Root Cause | DO NOT Do | DO Instead | Check |
|---------|-----------|-----------|-----------|-------|
| Eval suite ran but no metric updated in the Foundry Evals UI | Eval write blocked by RBAC. Eval runner lacks `Foundry User` role on the project. | Do not assume the eval ran successfully just because the run completed. | Check runner service principal / user has `Foundry User` role on the project (required for both read and write). Re-run the eval suite after assigning the role. | Run logs: `az cli ai projects role assignment list` |
| Grader returns 0 or 1 randomly across identical inputs | Grader is stateful (e.g., fetches live data, uses non-seeded randomness, or depends on current time). Evals require pure, deterministic functions. | Do not use non-deterministic graders in pre-merge gates or continuous eval. | Make the grader pure: seed any random source, snapshot live data into the dataset, avoid `datetime.now()` or mock it. Mark stateful graders as smoke-test-only in the eval description. | Grader source code — check for `random.random()`, `requests.get()`, or time-based logic without mocking. |
| Dataset rotation drift — eval scores trend down silently over weeks | Dataset items now reference URLs / data that has changed since baseline. No version tracking or content validation. | Do not assume stable datasets over time. Do not run evals without monitoring for drift. | Snapshot dataset version + content hash (SHA256 of JSONL) on every baseline run. Alert ops if drift > 5% week-over-week. Store hashes in run metadata. | Dataset file: `sha256sum dataset.jsonl` · Store in eval run description. |

---

## Evaluator RBAC

The eval judge models need model access. Assign these roles:

| Principal | Role | Scope |
|-----------|------|-------|
| Your user identity | `Cognitive Services OpenAI User` | AI Services account |
| Account managed identity | `Cognitive Services OpenAI User` | AI Services account |
| Project managed identity | `Cognitive Services OpenAI User` | AI Services account |
| Project managed identity | `Cognitive Services User` | AI Services account |

Without these, evals fail with permission errors on the judge model.

> **Pattern 23 (server-side worker RBAC).** Eval graders run **inside the
> Foundry project as the project's system-assigned managed identity
> (SAMI)**, NOT as the caller's UAMI. The project SAMI is a distinct
> principal from your user and from any agent-instance MI. It MUST hold
> **both** `Cognitive Services OpenAI User` AND `Cognitive Services User`
> at the AI Services account scope — the first lets it call OpenAI
> deployments, the second lets it enumerate them. Missing either role
> manifests as a silent 401 from the grader (no error in your client
> code, eval run just never completes). Grant order: project MI
> first; user/account MIs second. AAD propagation: wait ≥ 5 min after
> the role assignment lands before re-triggering the eval. See
> `AGENTS.md` § 9.7 Pattern 23 for the catalog-side post-mortem.

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

## Custom grader recipe: URL-citation quality (for grounded-answer pilots)

For agents whose value-add is "grounded answers backed by citations" (e.g. a
Microsoft Learn assistant, an internal docs Q&A, a code-grounded coding
assistant), an `agent-output-only` grader misses the most important quality
signal: **did the agent actually cite real, reachable sources?**

> **MUST:** Use the canonical reference graders. Do NOT redefine inline — the validator enforces single-source-of-truth.
>
> - [`references/python/url_citation_grader.py`](references/python/url_citation_grader.py) — both graders (`grade_citation_present` + `grade_citation_resolves`) plus the `LEARN_URL_PATTERN` regex (swap the domain for your corpus).
> - [`references/python/eval_runner.py`](references/python/eval_runner.py) — Day-1 coherence smoke runner (1–5 scale, caller-selected threshold); see § Day-1 Smoke Test Recipe.
> - [`references/data/sample_eval_dataset.jsonl`](references/data/sample_eval_dataset.jsonl) — 8 representative items from grounded-Q&A + hosted-agent pilots showing the standard simple item shape (`{"item": {"prompt", "expected_tool", ...}}`).

Wire two complementary graders into your eval suite:

### Grader A — citation_present (cheap, runs on every answer)

Import from `references/python/url_citation_grader.py`:

```python
from references.python.url_citation_grader import grade_citation_present
```

Use as a `FunctionEvaluator` in Foundry Evals. Latency: negligible
(string regex). Run on EVERY eval item.

### Grader B — citation_resolves (sampled, runs against live deploy)

Import from `references/python/url_citation_grader.py`:

```python
from references.python.url_citation_grader import grade_citation_resolves
```

Latency: 1-5 s per item (depends on network + number of URLs). Run in a
post-deploy smoke gate or scheduled nightly drift run, not on every PR.

### Wire-up

In your eval config, declare both:

```yaml
evaluators:
  citation_present:
    type: function
    function: graders.citation_present.grade_citation_present
  citation_resolves:
    type: function
    function: graders.citation_resolves.grade_citation_resolves
gates:
  pre_merge:
    - citation_present (>= 0.8)
  post_deploy:
    - citation_present (>= 0.8)
    - citation_resolves (>= 0.95)
```

If your domain isn't `learn.microsoft.com`, swap the regex (and put the
domain in a config rather than hardcoded). Verified pattern from a
grounded-Q&A pilot — 4/4 in-scope demo scenarios returned ≥2 citations,
every URL resolved.

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

Poll `client.evals.runs.retrieve(...)` to a successful terminal state, then
download **all pages** from `client.evals.runs.output_items.list(...)`.
Convert SDK objects with `model_dump()` before dictionary access. Current
built-in coherence results expose `score`, `passed`, `reason`, and `status`
directly in each item's `results[]`; these fields were present in both live
paths verified for the 1.4.0 helper. Do not assume all previews always return
zero counts or null verdicts.

For agent-target runs the captured answer is in
`datasource_item["sample.output_text"]`; for pre-captured JSONL it is in
`datasource_item["response"]`. A run-level completed status alone is
insufficient: inspect item/sample errors and require real output plus the
expected finite numeric metric. Preserve **zero** scores — never use
`score or label or verdict`, which discards a valid zero.

> **MUST:** Use the canonical score/poll/output checks in
> [`references/python/eval_runner.py`](references/python/eval_runner.py) for the
> Day-1 coherence smoke. For full suites, follow the current
> [results contract](https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation-results)
> for each evaluator. Custom evaluator multi-entry results and legacy
> judge-text payloads need explicit interpretation; do not silently coerce
> missing metrics to pass or apply a 0–1 threshold to a 1–5 score.

## Programmatic last-run introspection

> **MUST:** Copy verbatim from [`references/python/last_run.py`](references/python/last_run.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
> That file preserves the local last-run summary contract. It is not an
> implementation of Threadlight's separate evaluation manifest.

Extract the most-recent eval run summary with the stable 11-key dict:

```python
from foundry_evals.last_run import last_run_summary

summary = last_run_summary(evals_dir="evals/")
if summary is None:
    print("No eval run found yet")
else:
    if summary["confidence"] < 0.8:
        print(f"Run is stale (> 7 days): {summary['stale']}")
    print(f"Passed: {summary['scenarios_passed']}/{summary['scenarios_total']}")
```

| Key | Type | Notes |
|---|---|---|
| `ran_at` | str (ISO-8601 UTC) | Timestamp of the eval run |
| `run_id` | str | Unique run identifier |
| `scenarios_total` | int | Total scenario count |
| `scenarios_passed` | int | Passed scenario count |
| `scenarios_failed` | int | Failed scenario count |
| `threshold_breaches` | list[str] | Per-scenario failure + latency-budget overage entries |
| `p50_latency_ms` | float \| None | Median latency across scenarios |
| `p95_latency_ms` | float \| None | 95th-percentile latency |
| `confidence` | float | 1.0 if fresh (≤ 7 days); 0.5 if stale (> 7 days); 0.0 if no scenarios |
| `stale` | bool | True if run age > 7 days (controlled by `STALE_AFTER_DAYS`) |
| `source` | str | File path to the run's manifest.json |

The helper returns `None` if no `evals/runs/*/manifest.json` exists (no eval has run yet).
The historical EVAL-201 integration claim is not demonstrated by current
Threadlight source. Preserve the helper's 11-key shape for existing callers,
but do not invent a `foundry_evals` import dependency in another project.
Threadlight retains its own `threadlight-evals-manifest/v1` evidence contract;
adapt only at an explicitly implemented and tested boundary.

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
| `task_adherence` 0% specifically | Judge lacks the actual interaction/tool context or rubric | Inspect mappings and full tool transcript; compare approved compatible judges without choosing one merely to inflate scores |
| `tool_selection` + `tool_output_utilization` both 0% | Missing `tool_definitions` in JSONL | Every JSONL item must include `tool_definitions` array |
| Eval run fails | RBAC missing on judge model | Assign `Cognitive Services OpenAI User` AND `Cognitive Services User` to the project MI (Pattern 23 — graders run as the project SAMI, not the caller) |
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

<a id="1-judge-model-must-be-gpt-54-mini"></a>

### 1. Judge Model: select an approved deployment

The earlier
benchmark used `gpt-5.4-mini`, but that deployment name is not required by the
API. Select an existing chat-capable judge supported by the evaluator and
record its deployment/version. Response-only data can hide tool evidence from
any judge. Correct mappings/rubrics first; a more forgiving model is not proof
of a more accurate evaluation.

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

## Day-1 Smoke Test Recipe (hosted-agent + MCP-tool pilots)

Before broader evaluation, prove that the selected invocation/evaluation path
returns a real score. This one-item **coherence** smoke is not a tool-selection
gate, business acceptance test, or production certification.

1. Confirm the project endpoint, agent name/version, protocol, existing chat
   judge deployment, and approval to store synthetic input/output in Foundry.
   Use `azure-tenant-isolation` before Azure calls; do not log in, change
   subscriptions, or grant roles to make a failed test pass.
2. Use the bounded SDK versions in the [pin](references/upstream-pin.md).
   Set `FOUNDRY_PROJECT_ENDPOINT` and `JUDGE_MODEL_DEPLOYMENT`. The legacy
   `AZURE_AI_PROJECT_ENDPOINT` alias remains accepted by the helper.
3. Run the canonical helper, not a locally rewritten evaluator:

   ```bash
   python skills/foundry-evals/references/python/eval_runner.py \
     "<representative-synthetic-query>" \
     --agent-name "<agent-name>" --agent-version "<version>" \
     --mode agent-target --threshold 3 \
     --artifact "./evals/private-smoke.json"
   ```

4. The helper uses the project's **OpenAI sub-client**, sends query-only
   agent-target input, and shares a default **300-second acceptance budget**
   across eval/run creation, polling and every result page. Each request uses
   the remaining budget as its HTTP per-I/O timeout, with SDK retries disabled.
   It checks the deadline after blocking calls and before accepting scores.
   Cleanup gets a separate 30-second request/acceptance budget, without retries;
   late/failed cleanup is reported as unverified. These are **not hard wall-clock
   cancellation guarantees**: HTTP timeouts apply per I/O phase, and token
   acquisition or a transport may overrun before returning. An outer process
   supervisor is needed for a strict wall-clock kill. Explicit invocation in
   invoke-score mode occurs before this scoring budget.
   The helper preserves zero scores. A missing/non-finite score or failed/unfinished run
   is an execution failure. Coherence uses a **1–5 scale**; `3` is an illustrative
   threshold, not universal policy. Exit 0/1 reflects that chosen threshold.
5. When the target surface requires explicit invocation, use
   `--mode invoke-score` instead (without `--agent-version`): the agent-bound
   Responses endpoint selects its active version. The helper scores the actual
   captured non-empty response. For custom SSE/Invocations transports, capture
   using the agent's documented transport, then call `smoke_score(query,
   captured_response, project_client=project, judge_model=...)` directly.
   Do not invent a `function_eval` API or report a pinned version on this path.

> **MUST:** [`references/python/eval_runner.py`](references/python/eval_runner.py)
> is the single source of truth. Its smoke creates a UUID-named disposable eval,
> attempts deletion of **only that eval**, and reports cleanup failures separately.
> It never deletes the existing target agent. The optional artifact retains the
> run IDs and raw per-item evidence: keep it private. Normal long-lived evaluation
> definitions/runs in Phase 2 remain reusable; this cleanup is smoke-only.

Follow a successful execution smoke with the full tool-aware suite and reviewed
thresholds. Keep `tool_definitions`, actual tool calls/outputs and SPEC-derived
cases where required. `last_run_summary()` and its local manifest contract are
unchanged; the helper's private artifact is **not** a Threadlight evaluation manifest.

---

## Continuous Evaluation Loop (production telemetry → KPIs)

One-shot pre-deploy evaluation tells you "the agent shipped working".
**Continuous evaluation** tells you "the agent is *still* working in production
six weeks later". Wire this for every threadlight pilot — it's how the customer
proves the agent earned its budget at the next steering committee.

> **Cross-skill ownership note:** This section owns **scoring patterns, dataset schema,
> and evaluator wiring**. Related concerns are owned by peer skills:
> - **Identity & RBAC for eval runners** → see `foundry-hosted-agents` § Identity & RBAC
> - **Hosted-agent lifecycle & deployment** → see `foundry-hosted-agents` § Troubleshooting
> - **Knowledge base / VectorDB orchestration & continuous indexing** → see `foundry-iq` § Continuous indexing
>
> If your eval runner has permission errors or your agent fails to start during continuous eval,
> check those upstream SKILLs first. This SKILL focuses on the eval definition and score extraction.

### Plan A (default): Foundry built-in continuous evaluation

**Use this first.** Follow the official
[continuous evaluation workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/observe/references/continuous-eval.md).
It distinguishes response-triggered **Prompt** evaluation from scheduled
**Hosted** trace evaluation. Do not assume every hosted transport emits the
same response-completed event.

Discover the current Foundry MCP command schema before use; these are
operation names, not Python methods in the pinned SDK:

| Operation | Required lifecycle check |
|---|---|
| `continuous_eval_get` | Resolve project/agent and inspect existing configuration before any write |
| `continuous_eval_create` | Supply the complete desired configuration; replacement can drop omitted evaluators |
| `evaluation_get` | Resolve the linked evaluation group to recover evaluator definitions before changing/disabling |
| Disable via `enabled=false` | Preserve evaluators, judge deployment, sampling/caps and selected configuration |
| `continuous_eval_delete` | Use the exact configuration ID from readback, with owner approval; verify absence |

For Prompt, explicitly approve `samplingRate` and `maxHourlyRuns`. For Hosted,
approve `intervalHours`, `maxTraces` and the connected telemetry source. Do not
enable an uncapped recurring evaluator as a side effect of running a smoke.
Persist configuration/eval IDs and the owner/retention decision. Read back
the configuration and require actual scored output from the intended agent;
successful creation is not monitoring acceptance.

**Required RBAC** (keyless throughout — three grants on **two distinct identities**):

| # | Principal | Role | Scope |
|---|-----------|------|-------|
| 1 | **Caller** (your user / deploy UAMI / CI UAMI) | `Azure AI User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) | Foundry **project** |
| 2 | **Project SAMI** (the project's own managed identity — NOT the caller) | `Cognitive Services OpenAI User` | AOAI account hosting the judge model |
| 3 | **Project SAMI** (same identity as row 2) | `Cognitive Services User` | AOAI account hosting the judge model |

The project SAMI is a **different principal** from anything you've already
granted — it's auto-created when the Foundry project is provisioned, and
the LLM-as-judge calls execute server-side as that principal (Pattern 23).
Granting your caller `Cognitive Services OpenAI User` does NOT cover the
grader path — the grader never sees your token. `Cognitive Services OpenAI
User` alone is also not sufficient on the SAMI: list-deployments
enumeration during judge dispatch requires `Cognitive Services User` too.

Look up the project SAMI's principalId from the project resource's
`identity.principalId`, then verify (replace `<AOAI_ACCOUNT_RESOURCE_ID>`
with the full ARM ID of the AI Services account):

```bash
az role assignment list \
  --assignee <project-sami-principalId> \
  --scope <AOAI_ACCOUNT_RESOURCE_ID> \
  --query "[].roleDefinitionName"
```

Both `Cognitive Services OpenAI User` and `Cognitive Services User` must
appear. Silent failures here look like "no eval runs ever appear" with
no error surfaced to the caller.

**Where results show up:**
- Foundry portal → agent → **Monitor** tab → evaluation charts
- Programmatically: list runs through the project's OpenAI client using the
  `evalId` returned by the selected continuous configuration
- Each run has a `report_url` for the deep-dive HTML report

Scheduled regression suites, red teaming and alerts are separate capabilities,
not free side effects of creating a continuous configuration. Validate the
actual telemetry/transport path. Missing runs require diagnosis of the source,
identity and schedule; do not silently replace monitoring with a custom job.

**Reference samples**:
- [Continuous evaluation sample (Python)](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_continuous_evaluation_rule.py)
- [Scheduled evaluations sample (Python)](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/samples/evaluations/sample_scheduled_evaluations.py)
- [Agent Monitoring Dashboard docs](https://learn.microsoft.com/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard)

### Plan B (fallback): ACA Job continuous-eval pulling App Insights + Cosmos

**Bounded implementation handoff, not a shipped job scaffold.** Use this when
native monitoring cannot meet the approved requirements, for example:
- You need **custom KPIs** that aren't expressible as a built-in evaluator
  (e.g., `count(audit.decision == 'approved') / count(audit.decision != null)` —
  a business KPI computed from Cosmos audit records, not from agent traces)
- You need a **customer-facing App Insights workbook** branded for the COO
  (the Foundry Monitor tab is great for engineers, but COOs want a workbook)
- You need cross-source correlation (App Insights spans + Cosmos `case_audit` +
  external systems metrics) that the built-in `azure_ai_source` data source can't reach
- The selected hosted transport does not supply the required native trace data
  (verify this rather than assuming a platform gap)

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

The application owner must implement the source queries and KPI computation.
Business aggregates go to telemetry/workbooks; they are not automatically
valid Foundry evaluation items.

#### Step 2 — Generate the ACA Job (delegates to threadlight-event-triggers)

For a Threadlight project, hand the approved schedule and source contract to
[threadlight-event-triggers](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-event-triggers/).
For other applications, use the existing
[azd-patterns](../azd-patterns/SKILL.md) ACA Job primitives. Neither supplies
this application's KPI queries or scoring glue automatically.

Before deploying, implement and test in the consuming application:

1. A bounded time-window query against the approved telemetry/audit sources,
   with pagination, late-arrival policy, redaction and explicit failures.
2. A durable checkpoint/dedup key containing source, window and scorer version.
   Retry must not double-count a completed window.
3. Conversion of actual captured responses/tool transcripts to the Phase 2
   item schema. Keep non-LLM business aggregates separate.
4. Scoring through the project's OpenAI evaluation client, retaining eval/run
   IDs, terminal status and every per-item score/error. The canonical
   `smoke_score` proves one captured-response case, not a batch implementation.
5. Telemetry emission, alert tests and exact resource cleanup/retention custody.

No `continuous-eval-job.md` scaffold or generated `fetch_spans`,
`compute_metric`, or `record_foundry_eval_run` helper ships in this skill.
Do not report Plan B complete until the application code exists, a synthetic
window is scored end-to-end, replay is idempotent, and lifecycle cleanup is verified.

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

Use the approved Azure Monitor alert primitives in
[`azure-monitor-alert-baseline`](../azure-monitor-alert-baseline/SKILL.md),
not an incomplete inline Bicep resource. Validate operator/value input against
an allowlist, then test a synthetic threshold breach. Action Group destinations
and recurring evaluation spend require owner approval.

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

Retain real evaluation run IDs and the curated dataset version for each scored
window. Use the supported captured-response or agent-target data source from
this skill, not an invented `type: telemetry` payload. Reuse an eval definition
only while its evaluator configuration remains unchanged; label dataset changes
so a changing test population is not mistaken for agent drift.

#### Cost guardrails (Plan B)

A 15-minute schedule means 96 runs/day before retries. Estimate using measured
rows, evaluator calls/tokens, job duration and current first-party pricing;
there is no universal monthly estimate. Agree on cadence, row/token caps,
retention and a disable path before enabling the job. A schedule or SPEC edit
does not update deployed infrastructure until the consuming implementation
explicitly applies it.

### Troubleshooting (both plans)

| Issue | Cause | Fix |
|-------|-------|-----|
| Plan A: rule created but no eval runs appear | Source, sampling, schedule or judge identity/access mismatch | Inspect the selected config and actual failing identity; obtain approval for any access change |
| Plan A: hourly cap reached | Traffic exceeds approved sampling | Review sampling/cap with owner; do not silently increase spend |
| Plan A: hosted agent has no scores | Missing trace source, identity or schedule configuration | Diagnose the scheduled Hosted path before choosing Plan B |
| Plan B: Continuous-eval job has no spans to score | App Insights connection on Foundry account missing | See `Eval Trending` section + threadlight-deploy gotchas |
| Plan B: Foundry evaluator 429 | Judge model capacity exhausted from concurrent windows | Measure actual request/capacity limits, reduce approved concurrency; capacity changes require approval |
| Plan B: KPI workbook shows blank | Application's telemetry emission or query is incomplete | Verify a synthetic metric through the real producer and workbook query |
| Plan B: Alert never fires | Threshold off by ratio (forgot `* 100` for percentage) | Test with manual `customMetrics` query first |
| Plan B: Trending shows flat line | Wrong run group, unchanged data or missing new results | Verify real per-item outputs and dataset lineage; reuse the group only while evaluator criteria are unchanged |

---

## Input contract / Output artifacts

The paths below are **application implementation targets**, not files
shipped or automatically generated by this skill. Native workflow artifacts
remain in their selected agent root; do not overwrite a Threadlight manifest
with the private smoke artifact or local 11-key summary.

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
| User env in the [selected hosted profile](../foundry-hosted-agents/references/hosted-contract.json) | `EVAL_DEFINITION_ID`, `KPI_WORKBOOK_ID` (B), `EVAL_RULE_ID` (A) | Both |
| `specs/kpis.yaml` | Extracted from SPEC § 9 — single source of truth at runtime | Both |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Generates SPEC.md § 9 KPI table — the input contract for the continuous loop |
| [**threadlight-deploy**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy/) | Coordinate the consuming project's deployment and preserve its actual evaluation evidence contract |
| [**threadlight-event-triggers**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-event-triggers/) | Owns the `aca-job-cron` scaffold the **Plan B** loop runs on |
| [**threadlight-hitl-patterns**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-hitl-patterns/) | Writes the `case_audit` records the **Plan B** loop reads for custom KPI computation |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | App Insights connection on Foundry account is prerequisite for both plans |
| [Official evaluator lifecycle](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/observe/observe.md) | Generate/review custom evaluators and native suites; no `foundry-assert` sibling ships here |
| [Official Agent Optimizer](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/agent-optimizer/agent-optimizer.md) | Optimize a candidate and re-evaluate before owner-approved deployment; no `foundry-agent-optimizer` sibling ships here |

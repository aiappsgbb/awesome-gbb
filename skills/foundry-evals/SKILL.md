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

# Warm up (cold start takes 15-30s on first request)
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

---

## Phase 2: Score with Foundry Evaluators

```python
# Use a NON-agent-bound client for evals
client = project.get_openai_client()  # NOT agent_name=...

# Judge model — MUST be gpt-5.4-mini (see quirks below)
JUDGE_MODEL = "gpt-5.4-mini"

evaluation = client.evals.create(
    name="my-agent-eval",
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
        # Non-tool evaluators (query + response only)
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
        # Tool evaluators (require tool_definitions)
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

run = client.evals.runs.create(
    eval_id=evaluation.id,
    data_source={
        "type": "jsonl",
        "source": {
            "type": "file_content",
            "content": [{"item": r} for r in results],
        },
    },
)

print(f"Eval run: {run.id} — status: {run.status}")
```

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

---

## Tool Evaluator Quirks (Hard-Won Lessons)

These were discovered through dual-variant benchmarking (GHCP vs MAF, 11 scenarios,
6 evaluators each). See the full analysis at `threadlight-vnext/docs/dual-variant-eval-analysis.md`.

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

Track scores over time to catch regressions:

```python
# Compare runs
runs = client.evals.runs.list(eval_id=evaluation.id)
for run in runs:
    print(f"{run.created_at}: {run.metrics}")
```

Re-run evals after each agent version update to ensure quality doesn't regress.

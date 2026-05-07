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

evaluation = client.evals.create(
    name="my-agent-eval",
    data_source_config={
        "type": "custom",
        "item_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
            },
            "required": ["query", "response"],
        },
    },
    testing_criteria=[
        {
            "type": "azure_ai_evaluator",
            "evaluator_name": "builtin.task_adherence",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
            },
        },
        {
            "type": "azure_ai_evaluator",
            "evaluator_name": "builtin.task_completion",
            "data_mapping": {
                "query": "{{item.query}}",
                "response": "{{item.response}}",
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

---

## Built-in Evaluators

All evaluator names use the `builtin.` prefix.

| Evaluator | What It Measures | When to Use |
|-----------|-----------------|-------------|
| `builtin.intent_resolution` | Did the agent understand user intent? | Always — baseline quality |
| `builtin.task_adherence` | Did the agent follow system instructions? | Always — tests instruction compliance |
| `builtin.task_completion` | Did the agent complete the requested task? | Always — end-to-end success |
| `builtin.coherence` | Is the response logical and well-structured? | Always — readability |
| `builtin.tool_selection` | Did the agent pick the right tools? | When agent has multiple tools |
| `builtin.tool_output_utilization` | Did the agent use tool results effectively? | When agent uses tools |

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
| Low `intent_resolution` | Agent misunderstands domain terms | Add domain vocabulary to instructions |
| All scores 0 | Empty responses | Concurrent eval requests; switch to sequential |
| Eval run fails | RBAC missing on judge model | Assign `Cognitive Services OpenAI User` |
| Inconsistent scores | Low TPM causing rate limits | Increase to ≥300K TPM |

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

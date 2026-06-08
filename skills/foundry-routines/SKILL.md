---
name: foundry-routines
description: >
  Schedule and dispatch Foundry agent invocations via Routines —
  declarative automation rules that fire on cron (schedule trigger)
  or at a specific time (timer trigger). Wraps azure-ai-projects
  2.2.0+ `client.beta.routines` (create_or_update, dispatch,
  enable/disable, list/get/list_runs, delete), both action types
  (`invoke_agent_responses_api`, `invoke_agent_invocations_api`),
  YAML routine manifests, the `Foundry-Features: Routines=V1Preview`
  REST header, and regional preview availability.
  USE FOR: routines, scheduled agent, timer trigger, recurring
  trigger, cron schedule, agent automation, run history,
  dispatch_async, Foundry-Features header, RoutineDispatchPayload,
  azd ai routine. DO NOT USE FOR: multi-step orchestration or
  multi-agent coordination (use workflows), branching/approval logic
  (use workflows), in-cluster cron outside Foundry (use Azure
  Functions / Logic Apps), agent runtime (use foundry-prompt-agents
  or foundry-hosted-agents).
metadata:
  version: "1.0.0"
---

# Microsoft Foundry Routines — Reference Guide

A **routine** is a named automation rule that fires an existing
Foundry agent on a schedule (cron) or at a specific moment (timer).
The Foundry service queues the invocation, runs the agent, and
stores a run record you can inspect later. Routines remove the need
to host your own scheduler (Functions, Logic Apps, cron jobs)
around an agent that already lives in Foundry.

> **Status: preview (regional).** Send the
> `Foundry-Features: Routines=V1Preview` header on every REST call
> (the SDK adds it automatically). Available in a subset of regions
> — see § 2.

---

## 1 · What & when

A routine has exactly one **trigger** and one **action**.

| Concept | Values |
|---|---|
| **Trigger** | `schedule` (cron, ≥ 5 min interval) or `timer` (one-shot at a future timestamp / duration) |
| **Action** | `invoke_agent_responses_api` (call agent via Responses API) or `invoke_agent_invocations_api` (call via Invocations API) |
| **Lifecycle** | Created enabled or disabled, then `enable` / `disable` / `delete` |
| **Run history** | Every fire is recorded — query via SDK, REST, or portal |

### When to reach for routines

| Scenario | Use routines? |
|---|---|
| Run a Foundry agent every weekday at 07:00 UTC | ✅ Yes — schedule trigger |
| Run a Foundry agent once at a fixed future timestamp | ✅ Yes — timer trigger |
| Test an agent on-demand without waiting for its schedule | ✅ Yes — `dispatch()` manual dispatch |
| Multi-step workflow (call agent A, branch on result, call agent B) | ❌ No — use Foundry workflows |
| Event-driven trigger (HTTP webhook, queue message, file upload) | ❌ No — use Azure Functions / Event Grid / Logic Apps and call the agent from there |
| Sub-minute precision schedule | ❌ No — 5-minute minimum interval |

**Routines complement, not replace,** `foundry-prompt-agents` and
`foundry-hosted-agents` — those skills create the agent; this
skill schedules its invocation.

---

## 2 · Prerequisites

1. **Microsoft Foundry project** in one of the routines-preview
   regions (verified against the routines concept doc — see § 10):

   - East US
   - East US 2
   - West US
   - West US 2
   - West Central US
   - North Central US
   - Sweden Central
   - Japan East

2. **Existing agent with a configured agent identity.** A prompt
   agent created via `project.agents.create_version(...)` (see
   `foundry-prompt-agents`) or a hosted agent (see
   `foundry-hosted-agents`) both qualify. Pure prompt-only agents
   without an agent identity are rejected by the service when
   bound to a routine action.

3. **Foundry User role** (or higher) on the project scope. (The
   Foundry RBAC roles were recently renamed — Foundry User /
   Foundry Owner / Foundry Account Owner / Foundry Project Manager
   were previously Azure AI User / Owner / etc. The role IDs and
   permissions are unchanged.)

4. **Python 3.9+** with the routines-capable SDK:

   ```bash
   pip install "azure-ai-projects~=2.2.0" "azure-identity~=1.25"
   ```

   Routines surface under `client.beta.routines` requires
   `azure-ai-projects` 2.2.0 or later (preview). Earlier versions
   raise `AttributeError` on `client.beta.routines`.

5. **Authentication** via `DefaultAzureCredential` for SDK calls
   or `az account get-access-token --resource https://ai.azure.com`
   for raw REST. Routines are data-plane operations under the
   project endpoint.

---

## 3 · Author a routine

```python
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
# Format: https://<account>.services.ai.azure.com/api/projects/<project>

client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)
```

### Schedule trigger (recurring cron)

Minimum interval is **5 minutes**. The cron expression follows the
standard 5-field form (`minute hour day-of-month month day-of-week`).
`time_zone` accepts any IANA zone (e.g. `America/Los_Angeles`); set
to `UTC` for a UTC-anchored schedule.

```python
routine = client.beta.routines.create_or_update(
    routine_name="daily-summary",
    description="Runs a daily summary agent on weekday mornings.",
    enabled=True,
    triggers={
        "weekday-morning": {
            "type": "schedule",
            "cron_expression": "0 7 * * 1-5",  # required
            "time_zone": "UTC",                # required
        }
    },
    action={
        "type": "invoke_agent_responses_api",
        "agent_name": "my-summary-agent",  # required, ≤ 256 chars
        # "conversation_id": "...",        # optional
    },
)
print(f"Routine: {routine.name}, enabled={routine.enabled}")
```

### Timer trigger (one-shot)

Fires exactly once. The `at` field accepts three shapes:

- ISO 8601 timestamp with explicit UTC offset: `"2026-09-01T09:00:00Z"`
- Local timestamp paired with `time_zone`:
  `"at": "2026-09-01T09:00:00", "time_zone": "America/Los_Angeles"`
- A positive duration from now: `"30m"`, `"2h"` (introduced in
  `azure-ai-projects` 2.2.0)

```python
routine = client.beta.routines.create_or_update(
    routine_name="once-on-release-day",
    description="Runs the agent once on release day.",
    enabled=True,
    triggers={
        "release-day": {
            "type": "timer",
            "at": "2026-09-01T09:00:00Z",  # required
        }
    },
    action={
        "type": "invoke_agent_responses_api",
        "agent_name": "release-bot",
    },
)
```

### Action types

Exactly one action per routine. Choose based on how the agent is
exposed:

| Action type | Required field | Optional | Use when |
|---|---|---|---|
| `invoke_agent_responses_api` | `agent_name` (≤ 256) | `conversation_id` | Calling a prompt agent or hosted agent via the Responses API (default for new prompt agents) |
| `invoke_agent_invocations_api` | `agent_name` (≤ 256) | `session_id` | Calling a hosted agent via the Invocations API (long-running session pattern) |

### YAML manifest equivalent

For consumers who prefer YAML / `azd ai routine` (preview-CLI
unstable — see § 8):

```yaml
# routine.yaml
name: daily-summary
description: Runs a daily summary agent on weekday mornings.
enabled: true
triggers:
  weekday-morning:
    type: schedule
    cron: "0 7 * * 1-5"
    time_zone: UTC
action:
  type: invoke_agent_responses_api
  agent_name: my-summary-agent
```

---

## 4 · Trigger a run

### Wait for the schedule

The schedule fires automatically once enabled — no further code.
The routine's `enabled=True` field gates whether the schedule is
honoured.

### Manually dispatch a run

`dispatch()` queues a one-off run without waiting for the next
scheduled fire. Useful for smoke tests, on-demand reruns, or
end-to-end verification right after creation. The payload type
**must match** the routine's action type.

```python
result = client.beta.routines.dispatch(
    routine_name="daily-summary",
    payload={
        "type": "invoke_agent_responses_api",
        "input": "Run the daily summary for testing.",  # optional, ≤ 32768 chars
    },
)
print(f"dispatch_id: {result.dispatch_id}")
print(f"task_id:     {result.task_id}")
```

The `dispatch_id` is the handle you use to find this specific run
in run history (§ 6). `action_correlation_id` is the
downstream-service correlation handle (e.g. the Responses API
response ID).

> **REST equivalent:** `POST {endpoint}/routines/{name}:dispatch_async`
> with the same payload, plus the `Foundry-Features: Routines=V1Preview`
> header. The endpoint suffix is `:dispatch_async` (note the colon),
> not `/dispatch`.

---

## 5 · Lifecycle

```python
# Pause a routine without deleting it
client.beta.routines.disable("daily-summary")

# Re-enable a paused routine
client.beta.routines.enable("daily-summary")

# Fetch the current definition
routine = client.beta.routines.get("daily-summary")
print(f"{routine.name}  enabled={routine.enabled}")

# Iterate all routines in the project
for r in client.beta.routines.list():
    print(f"{r.name}  enabled={r.enabled}  triggers={list(r.triggers.keys())}")

# Remove a routine permanently
client.beta.routines.delete("daily-summary")
```

To **update** a routine's trigger or action, reissue
`create_or_update` with the same name — the operation replaces the
stored definition. Omitted fields reset to defaults.

---

## 6 · Run history

Every routine fire (scheduled or dispatched) is recorded. Query
with `list_runs(routine_name)`:

```python
runs = client.beta.routines.list_runs("daily-summary", limit=20)

for run in runs:
    print(
        f"{run.id}  phase={run.phase}  source={run.attempt_source}  "
        f"started={run.started_at}  ended={run.ended_at}"
    )
    if run.phase == "failed":
        print(f"  error: {run.error_type} — {run.error_message}")
```

Useful `RoutineRun` fields:

| Field | Meaning |
|---|---|
| `id` | Run record ID |
| `phase` | `queued` / `running` / `completed` / `failed` |
| `attempt_source` | `schedule_delivery` or `manual_dispatch` |
| `trigger_type` | `schedule` or `timer` |
| `started_at` / `ended_at` | UTC timestamps |
| `dispatch_id` | Matches the `dispatch_id` from a manual `dispatch()` call |
| `response_id` | Downstream Responses API response ID — open in the portal to see the full agent response |
| `error_type` / `error_message` | Populated when `phase == "failed"` |

### Portal & REST alternatives

- The Foundry portal exposes a run table on each routine's detail
  page with the same fields, plus links to the full agent response.
- REST: `GET {endpoint}/routines/{name}/runs` with the
  `Foundry-Features: Routines=V1Preview` header.

---

## 7 · RBAC & governance

| Identity | Role required | Why |
|---|---|---|
| **Caller** authoring the routine | Foundry User (or higher) on the project scope | Authors `routines/*` operations |
| **Project managed identity** (server-side) | `Cognitive Services OpenAI User` on the AI Services account scope | The agent invocation runs server-side as the project MI; if the agent calls a model deployment it needs this role |

> **Pattern 23 (catalog convention).** When a routine fires, the
> downstream agent invocation is executed by Foundry's server-side
> worker, which authenticates as the **project managed identity**
> — not as the caller who created the routine. If your agent calls
> a chat / embedding deployment, the project MI must have
> `Cognitive Services OpenAI User` (and `Cognitive Services User`
> for embedding paths) on the AI Services **account** scope. The
> CI infrastructure for this catalog has these grants pre-applied;
> in customer engagements add them explicitly.

### Governance notes

- Routine input strings are persisted in the run record; treat
  them as visible to anyone with project read access.
- Routine names are project-scoped — collisions across teams in
  the same project will silently replace the prior definition on
  `create_or_update`. Use a naming convention (`<team>-<purpose>`).
- A routine has no built-in approval / four-eyes step. If you
  need that, wrap the dispatch behind a Logic App or Functions
  endpoint and call `dispatch()` only after approval.

---

## 8 · Preview limitations (as of `azure-ai-projects` 2.2.0)

1. **One trigger and one action per routine.** Multi-trigger or
   multi-action shapes are rejected by the service.
2. **Only `schedule` and `timer` triggers** are supported. No event,
   webhook, or queue triggers — those belong upstream of routines.
3. **Only `invoke_agent_responses_api` and `invoke_agent_invocations_api`
   actions** are supported. No HTTP-call or "run-a-function" actions.
4. **Regional preview** — provision your project in one of the
   regions listed in § 2.
5. **5-minute minimum interval** between schedule fires. Cron
   expressions tighter than that are rejected.
6. **Agent identity required.** Prompt-only agents without a
   configured agent identity are rejected when bound to a routine
   action. The agent must be a project-scoped agent (prompt-agent
   version published, or hosted agent deployed).
7. **`azd ai routine create --trigger schedule` inline form is NOT
   supported in preview.** Create schedule routines from a YAML
   manifest:

   ```bash
   azd extension install azure.ai.routines
   azd ai routine create --file routine.yaml
   ```

   The inline `--trigger schedule --cron …` form is timer-only in
   the preview extension. Per Pattern 16 (catalog convention),
   prefer the Python SDK for scheduled routines — the preview-CLI
   flag surface drifts between releases.
8. **`azd ai routine` cannot list run history** in preview. Use the
   portal, the REST API, or the SDK (`list_runs`).
9. **Input override is bounded.** The `payload.input` field in
   `dispatch()` caps at 32,768 characters.
10. **`agent_name` is bounded.** ≤ 256 characters on both action
    types.
11. **`Foundry-Features: Routines=V1Preview` header is required on
    every REST call.** The Python SDK injects it automatically; raw
    REST clients must set it explicitly.

---

## 9 · Anti-patterns

| Anti-pattern | Why it's wrong | What to do instead |
|---|---|---|
| Using a routine for multi-agent orchestration ("agent A then agent B based on A's output") | Routines have exactly one action — no branching, no chaining | Use Foundry workflows (preview), or invoke agent B from inside agent A as a sub-tool call |
| Putting secrets / PII in routine `input` overrides | The input is persisted in the run record and visible to anyone with project read | Pass references (e.g., a Key Vault secret name) and resolve them inside the agent |
| Sub-minute schedules (e.g. `* * * * *` expecting every-minute) | Service enforces a 5-minute minimum; tighter cron is rejected | For tighter intervals, use Logic Apps / Functions and call `dispatch()` from there |
| Treating the schedule as exact-second-precise | The service queues fires with some slack — don't build pipelines that assume sub-second alignment with the cron boundary | Build idempotency into the agent (deduplicate by an external key) |
| Re-creating a routine on every deploy with a different name | Each fresh name is a fresh routine — you accumulate orphans with old definitions still scheduled | Use a stable name and rely on `create_or_update` replacing the prior definition |
| Calling `dispatch()` repeatedly to simulate high-frequency scheduling | Each dispatch is a separately-recorded run; you'll spam the run history | If you genuinely need high-frequency invocation, the agent should be called directly via the Responses API, not via a routine |
| Mismatching `payload.type` with the routine's action type on `dispatch()` | The service rejects the call | Always set `payload.type` to the same string as the routine's `action.type` |

---

## 10 · References

- [Routines concept doc — Microsoft Learn](https://learn.microsoft.com/azure/foundry/agents/concepts/routines)
- [Automate agents with routines (how-to)](https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines)
- [`azure-ai-projects` on PyPI](https://pypi.org/project/azure-ai-projects/)
- Sibling skills:
  - `foundry-prompt-agents` — author the agent a routine will invoke
  - `foundry-hosted-agents` — same, for container-hosted agents
  - `foundry-observability` — observe routine runs via Foundry traces

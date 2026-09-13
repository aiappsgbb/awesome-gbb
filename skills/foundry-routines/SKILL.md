---
name: foundry-routines
description: >
  Schedule and dispatch Foundry agent invocations via Routines: cron,
  timer, GitHub issue and supported custom events. Covers the
  azure-ai-projects 2.4.x `client.beta.routines` lifecycle, azd run
  history and declarative azure.yaml, Responses/Invocations actions,
  preview headers and dispatch identity boundaries.
  USE FOR: routines, scheduled agent, timer trigger, recurring
  trigger, cron schedule, agent automation, run history,
  dispatch_async, Foundry-Features header, RoutineDispatchPayload,
  azd ai routine, GitHub issue trigger, Teams message trigger.
  DO NOT USE FOR: multi-step orchestration or
  multi-agent coordination (use workflows), branching/approval logic
  (use workflows), in-cluster cron outside Foundry (use Azure
  Functions / Logic Apps), agent runtime (use foundry-prompt-agents
  or foundry-hosted-agents).
metadata:
  version: "1.1.0"
---

# Microsoft Foundry Routines — Reference Guide

A **routine** is a named automation rule that fires an existing
Foundry agent on a schedule (cron), at a specific moment (timer), or
when a supported external event arrives.
The Foundry service queues the invocation, runs the agent, and
stores a run record you can inspect later. Routines remove the need
to host your own scheduler (Functions, Logic Apps, cron jobs)
around an agent that already lives in Foundry.

> **Status: preview.** Send the
> `Foundry-Features: Routines=V1Preview` header on every REST call
> (the SDK adds it automatically). Availability and identity constraints
> are service-version dependent — see § 2 and § 7.

The SDK examples remain the existing consumer path. For imperative CLI
and source-controlled deployment, use the
[azd routines workflow](references/azd-routines.md). It distinguishes CLI
aliases from API fields and preserves the existing SDK/REST alternatives.

---

## 1 · What & when

A routine has exactly one **trigger** and one **action**.

| Concept | Values |
|---|---|
| **Trigger** | `schedule` (cron, ≥ 5 min interval), `timer` (one-shot), `github_issue`, or `custom` with a supported provider |
| **Action** | `invoke_agent_responses_api` (call agent via Responses API) or `invoke_agent_invocations_api` (call via Invocations API) |
| **Lifecycle** | Created enabled or disabled, then `enable` / `disable` / `delete` |
| **Run history** | Query via SDK, REST, portal, or `azd ai routine run list` |

### When to reach for routines

| Scenario | Use routines? |
|---|---|
| Run a Foundry agent every weekday at 07:00 UTC | ✅ Yes — schedule trigger |
| Run a Foundry agent once at a fixed future timestamp | ✅ Yes — timer trigger |
| Test an agent on-demand without waiting for its schedule | ✅ Yes — `dispatch()` manual dispatch |
| Multi-step workflow (call agent A, branch on result, call agent B) | ❌ No — use Foundry workflows |
| React to an opened/closed GitHub issue | ✅ Yes — `github_issue` with an authorized connector connection |
| React to a Teams channel message | ✅ Yes — `custom` with the supported `teams` provider |
| Arbitrary HTTP webhook, queue message, or file upload | ❌ Not a generic event receiver — use Functions / Event Grid / Logic Apps unless a supported routine provider covers that event |
| Sub-minute precision schedule | ❌ No — 5-minute minimum interval |

**Routines complement, not replace,** `foundry-prompt-agents` and
`foundry-hosted-agents` — those skills create the agent; this
skill automates its invocation.

---

## 2 · Prerequisites

1. **Microsoft Foundry project with routines enabled.** Check the
   [current availability](https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines#prerequisites)
   for the target project; the historical eight-region preview list is
   not a current allowlist. The September 2026 documentation excludes
   UK West, Switzerland West, Japan West, UAE North and Norway East.
   Routines inherit the project's private networking configuration but
   do not support customer-managed key encryption.

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
   pip install "azure-ai-projects~=2.4.0" "azure-identity~=1.25.3" "httpx~=0.28.1"
   ```

   Routines surface under `client.beta.routines` requires
   `azure-ai-projects` 2.2.0 or later (preview). Earlier versions
   raise `AttributeError` on `client.beta.routines`. The explicit
   `httpx` pin works around an `azure-ai-projects` 2.4.0 packaging gap:
   the SDK imports `httpx` directly but does not declare it.

5. **Authentication** via `DefaultAzureCredential` for SDK calls
   or `az account get-access-token --resource https://ai.azure.com`
   for raw REST. Routines are data-plane operations under the
   project endpoint.

6. **Isolated CLI context** per `azure-tenant-isolation` before SDK,
   `az`, or `azd` work. Set both tenant-specific config directories and
   verify the intended tenant/subscription before mutations. An explicit
   project endpoint does not replace the tenant guard.

7. **Event connections** require separate authorization and connector
   consent. A manual dispatch does not prove that an external event
   source can deliver a trigger; see the [event prerequisites](references/azd-routines.md#event-triggers).

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
        "input": "Summarize the activity since the previous run.",
        # "conversation_id": "...",        # optional
    },
)
print(f"Routine: {routine.name}, enabled={routine.enabled}")
```

### Timer trigger (one-shot)

Fires exactly once. The `at` field accepts three shapes:

- ISO 8601 timestamp with explicit UTC offset: `"2030-09-01T09:00:00Z"`
- Local timestamp paired with `time_zone`:
  `"at": "2030-09-01T09:00:00", "time_zone": "America/Los_Angeles"`
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
            "at": "2030-09-01T09:00:00Z",  # replace with a future timestamp
        }
    },
    action={
        "type": "invoke_agent_responses_api",
        "agent_name": "release-bot",
        "input": "Produce the release summary.",
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

For consumers who prefer YAML / `azd ai routine`, manifest fields use
the API wire names, not CLI aliases or flags:

```yaml
# routine.yaml
name: daily-summary
description: Runs a daily summary agent on weekday mornings.
enabled: true
triggers:
  weekday-morning:
    type: schedule
    cron_expression: "0 7 * * 1-5"
    time_zone: UTC
action:
  type: invoke_agent_responses_api
  agent_name: my-summary-agent
  input: Summarize the activity since the previous run.
```

Create it with a positional routine name and an explicit project endpoint;
see [CLI setup and creation](references/azd-routines.md#imperative-lifecycle).
The manifest's `action.input` is persisted. A manual dispatch override
does not update that stored input.

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

An enqueue acknowledgment is not agent completion. Inspect the correlated
run before reporting that the agent succeeded.

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

To update supported fields, read the current definition and preserve fields
you are not changing. Do not assume `create_or_update` permits replacing a
trigger: the live service can reject changes to the **trigger definition**
even when its type is unchanged. Use a description-only update for a harmless
round-trip check. A schedule change needs an explicitly coordinated replacement
when the service rejects in-place updates; see the
[azd update boundary](references/azd-routines.md#imperative-lifecycle).

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
| `response_id` | Correlation handle for the downstream response; it does not guarantee that the current caller can retrieve its body |
| `error_type` / `error_message` | Populated when `phase == "failed"` |

### CLI, portal & REST alternatives

- CLI: `azd ai routine run list <name>` supports `--top`, `--filter`
  and `--output json`; use the explicit endpoint form in the
  [azd reference](references/azd-routines.md#imperative-lifecycle).
- The Foundry portal exposes a run table on each routine's detail
  page with the same fields, plus links to the full agent response.
- REST: `GET {endpoint}/routines/{name}/runs` with the
  `Foundry-Features: Routines=V1Preview` header.

**Completion and response readback are different checks.** In manual
acceptance, the run reached `phase=completed`, `status=Finished`, with no
error fields, but retrieving its `response_id` returned 404 through both
project and agent OpenAI clients. Do not report model-output assertions as
passed from the run record alone. The cause of that readback boundary was
not established; preserve the run/dispatch correlation for investigation
rather than inferring a permission fix or silently changing identities.

---

## 7 · RBAC & governance

| Identity | Role required | Why |
|---|---|---|
| **Caller** authoring the routine | Foundry User (or higher) on the project scope | Authors `routines/*` operations |
| **Agent identity** (default dispatch) | Permissions required by the agent's model and tools | Current routines default to the agent identity, not the authoring caller |
| **Connector connection identity** | Access and consent for the watched repository or Teams channel | Authenticates event delivery independently of agent dispatch |

Do not infer the executing principal from the identity that authored the
routine. Identify the actual agent runtime principal before diagnosing or
granting downstream RBAC. The project MI grants used by the existing CI
fixture are fixture preconditions, not a universal identity model.

The current service also documents **creator identity** as an explicit
REST create-time opt-in for delegated tools. It means the routine creator,
not the agent creator, a later editor or an arbitrary dispatch user.
Changing that setting requires recreation; an update does not change it.
The current SDK/azd models use the default agent identity. See
[dispatch identity](https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines#choose-a-dispatch-identity)
before adopting the REST opt-in; it is not covered by this skill's SDK
lifecycle fixture.

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

## 8 · Preview limitations (source alignment: September 2026)

1. **One trigger and one action per routine.** Multi-trigger or
   multi-action shapes are rejected by the service.
2. **Supported event providers only.** `github_issue` and the
   `custom` Teams provider add event-driven automation; they do not
   make routines a generic webhook or queue receiver.
3. **Only `invoke_agent_responses_api` and `invoke_agent_invocations_api`
   actions** are supported. No HTTP-call or "run-a-function" actions.
4. **Check availability and encryption requirements** per § 2.
5. **5-minute minimum interval** between schedule fires. Cron
   expressions tighter than that are rejected.
6. **Agent identity required.** Prompt-only agents without a
   configured agent identity are rejected when bound to a routine
   action. The agent must be a project-scoped agent (prompt-agent
   version published, or hosted agent deployed).
7. **CLI aliases differ from wire types.** Inline scheduled creation
   uses `--trigger recurring`; manifests use `type: schedule` and
   `cron_expression`. `create` has no `--input` flag; stored input
   belongs in a manifest. Check the installed extension's help rather
   than inventing an unsupported flag.
8. **Run history is available in azd** through `azd ai routine run list`,
   as well as SDK `list_runs`, REST and the portal.
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
- [azd lifecycle, event prerequisites and declarative deployment](references/azd-routines.md)
- [`azure-ai-projects` on PyPI](https://pypi.org/project/azure-ai-projects/)
- Sibling skills:
  - `foundry-prompt-agents` — author the agent a routine will invoke
  - `foundry-hosted-agents` — same, for container-hosted agents
  - `foundry-observability` — observe routine runs via Foundry traces

---
name: threadlight-event-triggers
description: >
  Scaffold non-interactive trigger receivers for a threadlight process —
  ACA jobs (cron / manual), Azure Functions (HTTP / Event Grid / Service
  Bus / Timer / Blob), Event Grid subscriptions, Service Bus consumers,
  webhook receivers. Reads spec § 10b Triggers (Receiver contract) and
  produces the receiver scaffold + idempotency / dead-letter wiring.
  USE FOR: scheduled trigger, event-driven trigger, ACA job scaffold,
  webhook receiver, Service Bus consumer, Event Grid subscription, cron
  trigger, idempotency key, dead-letter queue, threadlight triggers.
  DO NOT USE FOR: chat / on-demand triggers (those go through the agent
  directly), bot infrastructure (use foundry-teams-bot), MCP server
  deployment (use foundry-mcp-aca).
---

# Threadlight Event Triggers

Generate non-interactive trigger receivers (ACA jobs, Functions, Event Grid
subs, Service Bus consumers, webhook receivers) for a threadlight process,
based on `specs/SPEC.md` § 10b.

> **Why a separate skill from `azd-patterns`?** `azd-patterns` documents
> the ACA-job *deployment* pattern (Bicep, postdeploy hook, image update).
> This skill is one level up: given a spec, it picks the right
> receiver shape, generates the receiver code, wires idempotency and
> dead-letter rules, and emits the right Bicep that `azd-patterns`
> teaches how to deploy. They're complementary.

## When to Use

- Process spec § 10 declares `Trigger: scheduled` or `event-driven`
- Process needs a webhook receiver from an external system
- Process needs a periodic job (e.g. nightly batch, hourly KPI rollup)
- Process needs to consume from Service Bus / Event Grid

## When NOT to Use

- Process is `on-demand` only (chat-triggered through the agent itself)
- Process is `continuous` streaming (different scaffold — needs Stream Analytics
  or Event Hubs consumer; not yet covered in this skill)
- The trigger logic is part of the agent's reasoning (e.g. agent decides
  to schedule a follow-up) — that lives in the agent skill, not here

---

## Input contract / Output artifacts

**Input contract**:

- `specs/SPEC.md` § 10b **Triggers (Receiver contract)** — required:
  - `Trigger source` (cron expression, event topic, queue name, webhook URL)
  - `Receiver type` (ACA Job / Function / ACA consumer)
  - `Idempotency key` (field name or `none`)
  - `Dedup window`
  - `Dead-letter rule`
- `specs/SPEC.md` § 10 — for SLA/concurrency context
- `specs/SPEC.md` § 6 — for the agent invocation contract (the receiver
  ultimately calls the agent)
- `specs/SPEC.md` § 11c (Tech Stack) — confirms `event-grid`, `service-bus`,
  or `aca-job` is selected

**Output**:

```
src/triggers/
├── {trigger-name}/
│   ├── receiver.py            # The receiver entry point
│   ├── pyproject.toml         # uv-managed deps
│   ├── Dockerfile             # for ACA Job receivers
│   ├── host.json              # for Function receivers
│   ├── function.json          # for Function receivers
│   └── README.md              # how to test locally + idempotency notes
infra/triggers/
├── {trigger-name}.bicep       # ACA Job / Function / Event Grid sub / Service Bus consumer
└── dead-letter.bicep          # Storage Queue / SB DLQ / etc.
```

Plus updates to:
- `azure.yaml` — register the new service
- `infra/main.bicep` — wire the trigger module
- `scripts/postdeploy.py` — for ACA Job image updates (per `azd-patterns`)

---

## The five receiver shapes

| Shape | When | Where it runs |
|-------|------|---------------|
| **ACA Job (cron)** | Periodic batch; latency tolerance >1 min | Container Apps Job, scheduled trigger |
| **ACA Job (manual)** | Webhook receiver invokes via REST; or part of a workflow | Container Apps Job, manual trigger via REST |
| **Azure Function (HTTP)** | Lightweight webhook; consumption billing | Function App (Flex Consumption) |
| **Azure Function (Service Bus / Event Grid)** | Bound to a message queue or event topic | Function App with binding |
| **ACA consumer** | High-throughput SB / Event Hubs consumer; long-running stateful | Container App with KEDA scaler |

Default for most threadlight processes: **ACA Job (cron)** for scheduled,
**Azure Function (HTTP)** for webhook, **ACA consumer** for high-volume
event streams.

---

## Generation procedure

### Step 1: Read § 10b

```python
trigger_source = spec["triggers"]["source"]            # "cron 0 6 * * *", "Event Grid topic orders/created", etc.
receiver_type = spec["triggers"]["receiver"]            # one of the five shapes above
idempotency_key = spec["triggers"]["idempotency_key"]   # field name or "none"
dedup_window = spec["triggers"]["dedup_window"]         # "5m", "24h", "none"
dlq_rule = spec["triggers"]["dead_letter"]              # "retry 3x then DLQ", "DLQ immediately on parse error", etc.
```

### Step 2: Pick the scaffold

Copy from `references/scaffolds/{receiver-type}/` into `src/triggers/{trigger-name}/`.

### Step 3: Wire idempotency

Every receiver needs an idempotency check before invoking the agent:

```python
# Pattern: Cosmos-backed idempotency table
from datetime import timedelta

async def is_already_processed(key: str, window: timedelta) -> bool:
    """Check if we've seen this key within the dedup window."""
    entry = await cosmos.read_item(container="trigger_idempotency", id=key, partition_key=key)
    if not entry:
        return False
    seen_at = datetime.fromisoformat(entry["seen_at"])
    return (datetime.utcnow() - seen_at) < window

async def mark_processed(key: str):
    await cosmos.upsert_item(container="trigger_idempotency", body={
        "id": key,
        "seen_at": datetime.utcnow().isoformat(),
        "ttl": int(window.total_seconds() * 2),  # auto-expire after 2x window
    })
```

The Cosmos `trigger_idempotency` container has `partitionKey: /id` and a TTL
matched to 2× the dedup window so the table self-cleans.

### Step 4: Wire dead-letter

For Service Bus / Event Grid: configure DLQ in Bicep. For HTTP webhooks:
return 5xx on failure to trigger the sender's retry; persist the payload to
a Storage Queue if all retries exhausted.

```bicep
// Service Bus subscription with DLQ
resource subscription 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2024-01-01' = {
  name: '${prefix}-sub'
  parent: topic
  properties: {
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    deadLetteringOnFilterEvaluationExceptions: true
  }
}
```

### Step 5: Invoke the agent

The receiver's actual work is to construct an agent invocation and call it.
Pick by **who owns the agent definition**:

**Pattern A — invoke a Foundry-hosted agent** (recommended; the agent lives in Foundry):

```python
from agent_framework.foundry import FoundryAgent
from azure.identity.aio import AzureCliCredential

async def invoke_agent(payload):
    async with AzureCliCredential() as cred:
        agent = FoundryAgent(
            project_endpoint=PROJECT_ENDPOINT,
            agent_name=AGENT_NAME,
            credential=cred,
            allow_preview=True,   # opt into the preview Responses surface for hosted agents
            version="v2",
        )
        return await agent.run(format_input(payload))
```

**Pattern B — call the Foundry Responses endpoint directly** (when you don't
want the agent_framework dependency, e.g., a tiny Function receiver):

```python
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

async def invoke_agent(payload):
    async with DefaultAzureCredential() as cred:
        # allow_preview=True opens the Responses-on-hosted-agents surface
        async with AIProjectClient(
            endpoint=PROJECT_ENDPOINT,
            credential=cred,
            allow_preview=True,
        ) as project:
            # agent_name binds the OpenAI client to a specific hosted agent
            openai_client = project.get_openai_client(agent_name=AGENT_NAME)
            return await openai_client.responses.create(
                input=format_input(payload),
                stream=False,
            )
```

> **SDK version pins (May 2026)**: `azure-ai-projects>=2.0.0`,
> `agent-framework-foundry` (only Pattern A). The legacy
> `agent_framework.azure.AzureAIAgentClient` was removed — do NOT use it.

For long-running receivers (e.g. nightly batch over thousands of cases):
batch invocations with controlled concurrency (default `max_concurrent=4`).

### Step 6: Bicep + azure.yaml registration

Generate `infra/triggers/{trigger-name}.bicep`:

```bicep
// ACA Job (cron)
resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-${triggerName}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${uami}': {} } }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      replicaTimeout: 1800
      triggerType: 'Schedule'
      scheduleTriggerConfig: { cronExpression: triggerSource }
      registries: [{ server: '${acr}.azurecr.io', identity: uami }]
    }
    template: {
      containers: [{
        name: 'receiver'
        image: jobExists ? fetchLatestImage.outputs.containers[0].image : emptyContainerImage
        resources: { cpu: 1, memory: '2Gi' }
        env: [
          { name: 'AZURE_CLIENT_ID', value: uamiClientId }
          { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
          { name: 'AGENT_NAME', value: agentName }
          { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
        ]
      }]
    }
  }
  tags: { 'azd-service-name': triggerName }
}
```

Add to `azure.yaml`:

```yaml
services:
  trigger-{trigger-name}:
    project: ./src/triggers/{trigger-name}
    host: containerapp   # or 'function'
    language: python
    docker:
      remoteBuild: true
```

And to `infra/main.bicep`:

```bicep
module trigger './triggers/{trigger-name}.bicep' = {
  name: '{trigger-name}'
  params: { /* ... */ }
}
```

For ACA Jobs, also extend `scripts/postdeploy.py` to update the job image
(per the `azd-patterns` ACA Job pattern).

### Step 7: Validate

```
✅ Receiver scaffold compiles
✅ Idempotency check fires on duplicate input (test with same key twice)
✅ Dead-letter rule fires on simulated failure
✅ Agent invocation succeeds with a synthetic payload
✅ Bicep deploys cleanly (azd up dry-run)
✅ Cosmos `trigger_idempotency` container exists and has correct TTL
✅ For HTTP webhooks: idempotency header documented in README
```

---

## Idempotency strategies (decision tree)

```
Does the trigger source provide a unique message ID?
├── Yes → use it (Service Bus MessageId, Event Grid event.id)
│         dedup_window = "24h" (default, override if SLA differs)
└── No  → derive from payload content (hash of canonical fields)
          dedup_window = match the natural deduplication window of the source
```

Always document the idempotency key choice in the receiver's README — the
customer's SREs need to know it for replay scenarios.

---

## Dead-letter strategies (decision tree)

```
What's the failure mode?
├── Parse error (bad payload)              → DLQ immediately, alert ops
├── Transient (network, timeout)            → retry 3-5x with exponential backoff
├── Agent-side rejection (not retryable)    → record outcome + audit, don't DLQ
└── Downstream system unavailable           → retry until budget exhausted, then DLQ
```

The DLQ destination should be queryable (Storage Queue with management UI,
or Service Bus DLQ) — not a fire-and-forget log entry.

---

## Reference files

| File | Purpose |
|------|---------|
| `references/scaffolds/aca-job-cron/` | Cron-triggered ACA Job receiver scaffold |
| `references/scaffolds/aca-job-manual/` | Manual-triggered ACA Job (REST entry) |
| `references/scaffolds/function-http/` | Azure Function HTTP webhook receiver |
| `references/scaffolds/function-servicebus/` | Azure Function Service Bus binding |
| `references/scaffolds/function-eventgrid/` | Azure Function Event Grid binding |
| `references/scaffolds/aca-consumer/` | ACA consumer with KEDA scaler |
| `references/idempotency-patterns.md` | Cosmos / Redis / Storage Table backed dedup |
| `references/dead-letter-patterns.md` | DLQ destinations and replay tooling |

---

## Anti-patterns

- ❌ **Skip idempotency.** Every receiver MUST be idempotent. The customer
  WILL replay events; the source WILL retry; without idempotency you'll
  ship a demo that double-charges, double-approves, double-emails.
- ❌ **Use Function HTTP for high-throughput streams.** Use ACA consumer or
  Function with Event Hubs binding — HTTP doesn't backpressure.
- ❌ **Hide the DLQ.** A DLQ that nobody can see is worse than no DLQ. Wire
  alerts on DLQ depth >0.
- ❌ **Inline business logic in the receiver.** The receiver's job is
  idempotency check + agent invocation + audit. Business logic lives in
  the agent's skills.
- ❌ **Use a single receiver for multiple unrelated triggers.** One trigger
  = one receiver = one Bicep module = one deployable.
- ❌ **Forget to register the trigger in azure.yaml.** The Bicep alone
  won't deploy; azd needs the service registration.

---

## See Also

| Skill | Use When |
|-------|----------|
| [`threadlight-design`](../threadlight-design/) | Produces spec § 10b that this skill consumes |
| [`azd-patterns`](../azd-patterns/) | The ACA Job deployment pattern (Bicep + postdeploy hook) |
| [`threadlight-deploy`](../threadlight-deploy/) | The orchestrator that calls this skill when § 10b is non-empty |
| [`threadlight-hitl-patterns`](../threadlight-hitl-patterns/) | The SLA watcher receiver type (cron job that escalates stale approvals) |
| [`foundry-mcp-aca`](../foundry-mcp-aca/) | If the receiver also exposes a webhook *into* the system (mock receiver) |

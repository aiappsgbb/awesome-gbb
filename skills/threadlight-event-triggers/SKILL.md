---
name: threadlight-event-triggers
description: >
  Scaffold non-interactive trigger receivers for a threadlight process —
  ACA-first (jobs, app HTTP receivers, KEDA-scaled consumers) with Azure
  Functions only when narrow constraints demand it. Reads spec § 10b
  Triggers (Receiver contract) and produces the receiver scaffold +
  idempotency / dead-letter wiring.
  USE FOR: scheduled trigger, event-driven trigger, ACA job scaffold,
  ACA app webhook, ACA consumer, KEDA scaler, Service Bus consumer, Event
  Grid subscription, cron trigger, idempotency key, dead-letter queue,
  threadlight triggers.
  DO NOT USE FOR: chat / on-demand triggers (those go through the agent
  directly), bot infrastructure (use foundry-teams-bot), MCP server
  deployment (use foundry-mcp-aca).
metadata:
  version: "1.0.0"
---

# Threadlight Event Triggers

Generate non-interactive trigger receivers (ACA jobs, ACA HTTP apps, ACA
consumers with KEDA, optionally Functions) for a threadlight process,
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

## ACA-first stance

Every receiver in this skill defaults to **Azure Container Apps**. We chose
this for production-grade threadlight pilots over Azure Functions for
boring-but-real reasons:

| Functions pain in production | ACA equivalent / mitigation |
|------------------------------|-----------------------------|
| Cold starts (5-10s on Consumption; better-but-not-zero on Flex) | ACA `minReplicas: 1` keeps a warm replica; Jobs are launched on demand without an idle tax |
| Programming-model split (v1 vs v2 Python decorators, in-proc vs isolated .NET) | One model: a regular container running your framework of choice |
| `host.json` / `local.settings.json` / `function.json` politics | One `Dockerfile`, one `azure.yaml`, one Bicep |
| Bindings hide failures behind generic 500s; `func` runtime lags Azure | Direct SDK calls in the container; same code runs locally with `docker run` |
| Identity / UAMI sometimes silently ignored by the binding extension | UAMI is a first-class `identity:` block on the container; predictable |
| Time-bound (10 min default, 60 min Premium) — kills long agent loops | Jobs `replicaTimeout` up to 24h; apps run indefinitely |
| Scaling rules less expressive than KEDA | ACA *is* KEDA — full scaler catalog (SB, Event Grid, Cosmos, Kafka, Cron, custom) |
| App Insights auto-instrumentation conflicts with manual OTel | Bring your own OTel SDK, exports cleanly to App Insights / Foundry traces |

**This is not "Functions are bad"** — they're great for hobby-scale or
narrowly-scoped HTTP webhooks where a customer is already deeply invested
in the Functions ecosystem. But the threadlight value prop ("we deliver
this reliably") is undermined when day-3 of the pilot turns into a
debug-the-binding session.

ACA is the default. Functions appear in this skill only as **escape-hatch
shapes** — call them out explicitly if you reach for one (see § "When to
choose Functions anyway" below).

---

## Input contract / Output artifacts

**Input contract**:

- `specs/SPEC.md` § 10b **Triggers (Receiver contract)** — required:
  - `Trigger source` (cron expression, event topic, queue name, webhook URL)
  - `Receiver type` (ACA Job / ACA App / ACA Consumer / Function — last only when justified)
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
│   ├── Dockerfile             # for ALL ACA receivers (Job / App / Consumer)
│   └── README.md              # how to test locally + idempotency notes
infra/triggers/
├── {trigger-name}.bicep       # ACA Job / App / Consumer / (Function escape hatch)
└── dead-letter.bicep          # Storage Queue / SB DLQ / etc.
```

Plus updates to:
- `azure.yaml` — register the new service
- `infra/main.bicep` — wire the trigger module
- `scripts/postdeploy.py` — for ACA Job image updates (per `azd-patterns`)

---

## The receiver shapes (ACA-first)

| # | Shape | When | Where it runs |
|---|-------|------|---------------|
| 1 | **ACA Job (cron)** | Periodic batch; latency tolerance >1 min | Container Apps Job, scheduled trigger |
| 2 | **ACA Job (manual)** | Webhook receiver invokes via REST; or part of a workflow | Container Apps Job, manual trigger via REST `start` |
| 3 | **ACA App (HTTP)** | Webhook receiver; low-medium throughput; needs sub-second response | Container App with HTTP ingress, `minReplicas: 1` |
| 4 | **ACA Consumer (KEDA)** | Service Bus / Event Grid / Event Hubs / Cosmos change feed / Kafka | Container App with KEDA scaler; scales to zero between events |
| 5 | **Function (escape hatch)** | See § "When to choose Functions anyway" — narrow cases only | Function App (Flex Consumption preferred) |

**Default for most threadlight processes**:
- Scheduled → **#1 ACA Job (cron)**
- Webhook → **#3 ACA App (HTTP)**
- High-volume event stream → **#4 ACA Consumer (KEDA)**

### When to choose Functions anyway

Pick Function (#5) only if at least one of these is true. Document the reason
in the spec § 11d (Open Questions) and the receiver's README:

- **Customer already operates a Function App** for related workloads and the
  ops team has refused another runtime
- **Sub-second cold-start NOT required** AND request volume is so low (e.g.,
  <10/day) that the consumption-plan free-tier dominates cost rationale
- **Native binding required** to a service ACA can't reach as cleanly (very
  rare in 2026; Cosmos change feed, Service Bus, Event Grid, Event Hubs all
  have first-class KEDA scalers)
- **Customer policy forbids container ingress** but allows Function endpoints
  (sometimes seen in heavily-regulated tenants)

If you DO scaffold a Function, prefer **Flex Consumption** (Linux, Python 3.11+,
managed identity, VNet integration, no cold-start penalty in steady state).
Avoid Premium plan and avoid the legacy v1 programming model.

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

Every receiver needs an idempotency check before invoking the agent.
**Use the verified `IdempotencyStore` class from
[references/idempotency-patterns.md](references/idempotency-patterns.md)
verbatim** — copy-paste it into `src/triggers/_shared/idempotency.py`
and import.

Why a reference instead of inlining: the store has subtle correctness
properties (correct Cosmos data-plane API, `CosmosResourceNotFoundError`
catch on the read, `datetime.now(timezone.utc)` not deprecated `utcnow`,
TTL math from the *passed* window not a closure variable) that prior
versions of this skill got wrong inline. The reference file is the
single source of truth.

The Cosmos `trigger_idempotency` container has `partitionKey: /id` and a
TTL set to ≥ 2× the dedup window so the table self-cleans without the
receiver having to delete rows.

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

The receiver's actual work is to construct an agent invocation and call
the hosted agent. Use the `AIProjectClient` + `get_openai_client(agent_name=...)`
pattern — this is the **only** runtime-supported path for invoking a
Foundry-hosted agent from a containerized receiver as of May 2026.

> ⚠️ **Do NOT use `agent_framework.foundry.FoundryAgent` or the legacy
> `agent_framework.azure.AzureAIAgentClient`.** Both have been removed
> from agent-framework as of the April 2026 hosted-agents preview
> refresh. The canonical pattern lives in `foundry-hosted-agents` SKILL —
> copy from there.

```python
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

async def invoke_agent(payload):
    # Container's UAMI is picked up via AZURE_CLIENT_ID env var.
    # AzureCliCredential is for local dev only — never inside a container.
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

> **SDK version pins (May 2026)**: `azure-ai-projects>=2.0.0`. The legacy
> `agent_framework.azure.AzureAIAgentClient` was removed in agent-framework
> 1.0 — do NOT use it. Likewise, `agent_framework.foundry.FoundryAgent`
> was removed in the April 2026 hosted-agents preview refresh.
>
> ### ⚠️ Keyless RBAC for the receiver UAMI
>
> The receiver (ACA Job or ACA App) authenticates to Foundry via its UAMI.
> `DefaultAzureCredential` inside the container will pick up the UAMI
> from `AZURE_CLIENT_ID` automatically. **`AzureCliCredential` is for
> local dev only** — it requires `~/.azure/` state from `az login` which
> a container does not have, and it does **not** read `AZURE_CLIENT_ID`.
> Use `DefaultAzureCredential` everywhere; the credential chain will pick
> ManagedIdentityCredential in-container and `AzureCliCredential` locally.
>
> Required role assignments (assign at Bicep provisioning time):
>
> | Resource | Role | Role ID |
> |----------|------|---------|
> | **Foundry project** | `Azure AI User` | `53ca6127-db72-4b80-b1b0-d745d6d5456d` |
> | Service Bus namespace (Shape #2) | `Azure Service Bus Data Receiver` | `4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0` |
> | Event Grid topic (Shape #3, push delivery) | `EventGrid Data Sender` (on the source) | n/a — see Event Grid CloudEvents docs |
> | Storage Blob (if processing blobs) | `Storage Blob Data Reader` | `2a2b9908-6ea1-4ae2-8e65-a410df84e7d1` |
> | Cosmos DB (audit writes — paired with `threadlight-hitl-patterns`) | `Cosmos DB Built-in Data Contributor` | `00000000-0000-0000-0000-000000000002` |
>
> **Do NOT** use `Azure AI Developer` for the project — it's scoped to the
> legacy AML/Foundry-hub world. **Do NOT** use connection strings or shared
> access keys for Service Bus / Storage / Cosmos — managed identity only.
> Verify with `az role assignment list --assignee <uami-principal-id>` before
> declaring the trigger ready.

For long-running receivers (e.g. nightly batch over thousands of cases):
batch invocations with controlled concurrency (default `max_concurrent=4`).

### Step 6: Bicep + azure.yaml registration

Generate `infra/triggers/{trigger-name}.bicep`. Pick the template by shape:

**Shape #1 — ACA Job (cron)**:

> **Bicep helper symbols** (`jobExists`, `appExists`, `fetchLatestImage`,
> `emptyContainerImage`) are **expected to be passed in as params or
> defined in your `infra/main.bicep`**. They come from the canonical
> azd-Bicep helper pattern documented in `azd-patterns/SKILL.md`
> § "Helper symbols for image-aware deployment". Don't redefine them
> ad-hoc in this module; reuse the parent's.

```bicep
resource job 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-${triggerName}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${uami}': {} } }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      // 1800s = 30 min default. For long agent loops, bump to 7200 (2h) or up to 86400 (24h).
      // The right value is the p99 of one full agent invocation, with headroom.
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

**Shape #3 — ACA App (HTTP webhook)**:

```bicep
resource webhookApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-${triggerName}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${uami}': {} } }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true   // false if behind APIM / Front Door
        targetPort: 8080
        // 'http' = HTTP/1.1 + HTTP/2 (default; works for FastAPI, aiohttp).
        // Use 'http2' if you need explicit HTTP/2-only (rare), 'tcp' for non-HTTP.
        // 'auto' is deprecated — prefer explicit 'http'.
        transport: 'http'
        allowInsecure: false
      }
      registries: [{ server: '${acr}.azurecr.io', identity: uami }]
    }
    template: {
      containers: [{
        name: 'receiver'
        image: appExists ? fetchLatestImage.outputs.containers[0].image : emptyContainerImage
        resources: { cpu: '0.5', memory: '1Gi' }
        env: [
          { name: 'AZURE_CLIENT_ID', value: uamiClientId }
          { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
          { name: 'AGENT_NAME', value: agentName }
          { name: 'COSMOS_ENDPOINT', value: cosmosEndpoint }
        ]
      }]
      scale: {
        minReplicas: 1   // KEY: keep one warm — this is the cold-start cure
        maxReplicas: 10
        rules: [{
          name: 'http-scale'
          http: { metadata: { concurrentRequests: '50' } }
        }]
      }
    }
  }
  tags: { 'azd-service-name': triggerName }
}
```

**Shape #4 — ACA Consumer (KEDA — Service Bus example)**:

```bicep
resource consumerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-${triggerName}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${uami}': {} } }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      registries: [{ server: '${acr}.azurecr.io', identity: uami }]
      // No ingress block — this app pulls from Service Bus, not via HTTP
    }
    template: {
      containers: [{
        name: 'receiver'
        image: appExists ? fetchLatestImage.outputs.containers[0].image : emptyContainerImage
        resources: { cpu: 1, memory: '2Gi' }
        env: [
          { name: 'AZURE_CLIENT_ID', value: uamiClientId }
          { name: 'SERVICEBUS_NAMESPACE', value: serviceBusNamespace }
          { name: 'SERVICEBUS_QUEUE', value: queueName }
          { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
          { name: 'AGENT_NAME', value: agentName }
        ]
      }]
      scale: {
        minReplicas: 0   // Scale to zero between events
        maxReplicas: 30
        rules: [{
          name: 'sb-keda'
          custom: {
            type: 'azure-servicebus'
            // KEDA workload identity binding. The `identity` value MUST be
            // the UAMI's full resource ID, not its client ID — KEDA looks up
            // the principal at scale time. The TriggerAuthentication is
            // wired by the Container Apps environment automatically when
            // this `identity:` field is populated.
            identity: uami   // UAMI resource ID, e.g. /subscriptions/.../userAssignedIdentities/{name}
            metadata: {
              // namespace MUST be the FQDN host without https:// prefix and
              // without a trailing slash, e.g. 'mybus.servicebus.windows.net'
              // — bare 'mybus' will silently fail to scale.
              namespace: serviceBusNamespace
              queueName: queueName
              messageCount: '5'   // scale up when ≥5 unprocessed msgs per replica
            }
          }
        }]
      }
    }
  }
  tags: { 'azd-service-name': triggerName }
}
```

Add to `azure.yaml` — pick `host:` by shape:

```yaml
services:
  trigger-{trigger-name}:
    project: ./src/triggers/{trigger-name}
    # ACA App (#3) and ACA Consumer (#4) → containerapp
    # ACA Job (#1, #2)                  → containerapp  (azd treats jobs the same; the bicep distinguishes)
    # Function escape hatch (#5)         → function
    host: containerapp
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

| File | Purpose | Status |
|------|---------|--------|
| `references/scaffolds/aca-job-cron/` | Cron-triggered ACA Job receiver scaffold (default for scheduled) | shipped |
| `references/scaffolds/aca-job-manual/` | Manual-triggered ACA Job (REST `start` entry) | shipped |
| `references/scaffolds/aca-consumer/` | ACA Consumer Job with KEDA scaler (Service Bus / Event Grid / Event Hubs / Cosmos / Kafka). Use as the base for `aca-app-http` and `aca-consumer-keda` variants below — clone and edit `containerApp.bicep`'s `scale.rules` block. | shipped |
| `references/scaffolds/function-http/` | Azure Function HTTP webhook (escape hatch — see § "When to choose Functions anyway") | shipped |
| `references/scaffolds/function-servicebus/` | Azure Function Service Bus binding (escape hatch) | shipped |
| `references/scaffolds/function-eventgrid/` | Azure Function Event Grid binding (escape hatch) | shipped |
| `references/idempotency-patterns.md` | Cosmos / Redis / Storage Table backed dedup (single source of truth — copied verbatim into `src/triggers/_shared/idempotency.py`) | shipped |

> **DLQ wiring** lives inline in the relevant scaffold's `containerApp.bicep`
> + `consumer.py` files (Service Bus dead-letter; Event Grid retry +
> dead-letter to a Storage Queue; HTTP receiver returning 5xx to trigger
> sender retry then persisting to a Storage Queue). There is no separate
> `dead-letter-patterns.md` reference — the patterns are scaffold-bound
> because the right shape depends on the upstream binding.
>
> **ACA vs Functions** — see § "When to choose Functions anyway" earlier
> in this SKILL for the rationale. There is no separate `aca-vs-functions.md`
> reference.

---

## Anti-patterns

- ❌ **Skip idempotency.** Every receiver MUST be idempotent. The customer
  WILL replay events; the source WILL retry; without idempotency you'll
  ship a demo that double-charges, double-approves, double-emails.
- ❌ **Reach for an Azure Function by default.** Functions are the escape
  hatch (#5), not the default. Pick ACA App / Job / Consumer first; only
  fall back to Functions when one of the documented justifications applies.
- ❌ **Use a Function HTTP webhook for anything that matters.** Cold starts
  + binding quirks + ops-team-needs-to-learn-Functions cost more than the
  perceived "simplicity" savings. Use ACA App (HTTP) with `minReplicas: 1`.
- ❌ **Use Function HTTP for high-throughput streams.** Use ACA Consumer
  with KEDA — Function HTTP doesn't backpressure.
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
| [`threadlight-safe-check`](../threadlight-safe-check/) | Probes the receivers generated here (last 5 ACA Job executions must not all be Failed) in the post-deploy phase |
| [`threadlight-hitl-patterns`](../threadlight-hitl-patterns/) | The SLA watcher receiver type (cron job that escalates stale approvals) |
| [`foundry-mcp-aca`](../foundry-mcp-aca/) | If the receiver also exposes a webhook *into* the system (mock receiver) |

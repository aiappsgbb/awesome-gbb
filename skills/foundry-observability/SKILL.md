---
name: foundry-observability
description: >
  End-to-end observability for Threadlight pilots — App Insights +
  Log Analytics + OpenTelemetry across hosted agents, ACA MCP servers,
  ACA jobs, bot service, workspace UIs. Closes the silent gap where
  `azd up` returns 0 but **zero traces ever reach App Insights**.
  Three layers: Bicep `app-insights.bicep` + `log-analytics.bicep`
  always included; Foundry account-level connection (`category:
  AppInsights`) so hosted agents auto-inject
  `APPLICATIONINSIGHTS_CONNECTION_STRING`; ACA-side
  `configure_azure_monitor()` for MCP / bot / workspace / cron.
  Includes `Application Insights Data Ingestor` RBAC and KQL queries.
  USE FOR: app insights, application insights, OpenTelemetry, OTel,
  configure_azure_monitor, agent traces missing, no telemetry, blank
  appin, log analytics, KQL, observability, trace MCP, silent cron,
  Application Insights Data Ingestor, AppInsights connection foundry,
  account-level appin.
  DO NOT USE FOR: continuous eval (foundry-evals), pre-deploy gates
  (threadlight-safe-check), Foundry IQ monitoring (foundry-iq).
metadata:
  version: "1.0.1"
---

# Foundry Observability

End-to-end telemetry across every component of a Threadlight pilot:
Foundry hosted agent, MCP servers on ACA, ACA jobs (cron triggers),
bot service, workspace UI. **Default discipline**, not optional.

> **Why this skill exists.** Recent pilots deployed cleanly
> (`azd up` returned 0, all resources provisioned) but App Insights
> stayed **completely empty** — no agent traces, no MCP tool calls,
> no cron logs. Root cause: no one wired the connection at any layer.
> The intel for *each layer* lives scattered across `threadlight-deploy`,
> `foundry-hosted-agents`, `foundry-mcp-aca`, `threadlight-event-triggers` —
> but no single skill walks an operator through the full chain. That's
> what this skill does. Pair with `threadlight-safe-check` Step 5.6
> (App Insights existence + first-trace probe) to gate it shut.

---

## Mental model — three layers, one signal

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 3: ACA workloads (MCP / bot / workspace / cron jobs)          │
│   • configure_azure_monitor() reads APPLICATIONINSIGHTS_CONNECTION_STRING │
│   • Env var set by Bicep from app-insights.outputs.connectionString  │
│   • OTel exporter ships spans + logs + metrics over HTTPS           │
└─────────────────────────────────────────────────────────────────────┘
                                  ▲
                                  │ direct push from container code
                                  │
┌─────────────────────────────────┼───────────────────────────────────┐
│ Layer 2: Foundry hosted agent (the runtime)                         │
│   • Account-level AppInsights connection (category: AppInsights)    │
│   • Platform AUTO-INJECTS APPLICATIONINSIGHTS_CONNECTION_STRING     │
│   • RBAC: Application Insights Data Ingestor on agent identities     │
│   • Tracing emitted by the runtime — no app code change             │
└─────────────────────────────────┼───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 1: Bicep substrate                                            │
│   • app-insights.bicep — workspace-based (LAW-bound)                │
│   • log-analytics.bicep — single LAW for ALL workloads in the RG    │
│   • ACA env wiring: dapr.appInsightsConnectionString OR direct env  │
│   • Output `connectionString` consumed by every workload            │
└─────────────────────────────────────────────────────────────────────┘
```

**Single connection string, three fan-outs.** All telemetry lands in
the same App Insights resource. No per-workload AppIn — that fragments
the trace graph and makes correlation impossible.

---

## What ships from this skill

```
foundry-observability/
├── SKILL.md
└── references/
    ├── bicep/
    │   ├── log-analytics.bicep          # LAW (workspace) — required by both AppIn and ACA env
    │   ├── app-insights.bicep           # AppIn workspace-based + UAMI Application Insights Data Ingestor
    │   └── aca-env-monitoring.bicep     # ACA env wired to LAW + AppIn
    ├── python/
    │   └── otel_init.py                 # configure_azure_monitor() for ACA workloads
    ├── postprovision/
    │   └── connect_foundry_appinsights.py  # creates the account-level AppInsights connection
    └── queries/
        ├── agent-traces.kql             # hosted-agent traces, last 1h
        ├── mcp-tool-calls.kql           # MCP tool invocation breakdown
        ├── silent-cron-debug.kql        # ACA Job exec failures with no console logs
        └── first-trace-probe.kql        # smoke query — "did ANY trace land in last 5 min?"
```

Drop these into a PoC's `infra/modules/`, `infra/scripts/`, `src/<svc>/`,
and `docs/queries/` respectively. The patterns work as-shipped — replace
parameter values, re-deploy, traces flow.

---

## Layer 1 — Bicep substrate

### Step 1.1 — Single LAW for the whole pilot

```bicep
// infra/modules/log-analytics.bicep — drop-in
@description('Log Analytics workspace. ONE per pilot. AppIn binds to it; ACA env binds to it; cron jobs ship console+system logs to it.')
param location string = resourceGroup().location
param name string

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    features: { enableLogAccessUsingOnlyResourcePermissions: true }
  }
}

output workspaceId string = law.id           // ARM ID — used by AppIn + ACA env
output customerId string = law.properties.customerId  // GUID — for KQL queries
output workspaceName string = law.name
```

### Step 1.2 — App Insights bound to that LAW

```bicep
// infra/modules/app-insights.bicep — drop-in
@description('App Insights component. workspace-based (legacy classic mode is deprecated). Auto-grants Application Insights Data Ingestor to the workload UAMI so OTel traces, logs, and metrics can be ingested keylessly.')
param location string = resourceGroup().location
param name string
param workspaceId string
param uamiPrincipalId string  // Foundry agent UAMI principal — for RBAC

resource appin 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
    DisableLocalAuth: true        // RBAC-only ingestion — keyless mandate
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Application Insights Data Ingestor — required for OTel trace/log/metric ingestion
// when DisableLocalAuth is true. "Monitoring Metrics Publisher" covers only custom
// metrics API — it does NOT cover OTel exporter ingestion and will cause HTTP 400
// "Bad Request" from the azure-monitor-opentelemetry-exporter.
// Role GUID: f526a384-b230-433a-b45c-95f59c4a2dec (well-known)
resource dataIngestor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: appin
  name: guid(appin.id, uamiPrincipalId, 'f526a384-b230-433a-b45c-95f59c4a2dec')
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'f526a384-b230-433a-b45c-95f59c4a2dec'
    )
  }
}

output id string = appin.id
output name string = appin.name
output connectionString string = appin.properties.ConnectionString
output instrumentationKey string = appin.properties.InstrumentationKey
```

> **Why `DisableLocalAuth: true`.** Threadlight pilots are keyless by
> mandate (see `azure-tenant-isolation` and `citadel-spoke-onboarding`).
> AppIn ingestion keys are a back-door around RBAC — disable them and
> rely on `Application Insights Data Ingestor` to gate writes.
> **⚠️ `Monitoring Metrics Publisher` is NOT sufficient** — it covers
> only the custom metrics API, not the OTel trace/log ingestion endpoint.
> Using the wrong role with `DisableLocalAuth: true` causes HTTP 400
> "Bad Request" from the `azure-monitor-opentelemetry-exporter`.

### Step 1.3 — main.bicep wiring

```bicep
// infra/main.bicep — observability is ALWAYS-ON
module law 'modules/log-analytics.bicep' = {
  name: 'law-${envName}'
  params: { name: 'log-${envName}' }
}

module appInsights 'modules/app-insights.bicep' = {
  name: 'appin-${envName}'
  params: {
    name: 'appin-${envName}'
    workspaceId: law.outputs.workspaceId
    uamiPrincipalId: uami.outputs.principalId
  }
}

// ACA env binds to the same LAW so console+system logs land alongside traces
module acaEnv 'modules/aca-env-monitoring.bicep' = {
  name: 'env-${envName}'
  params: {
    name: 'env-${envName}'
    workspaceCustomerId: law.outputs.customerId
    workspaceSharedKey: listKeys(law.outputs.workspaceId, '2023-09-01').primarySharedKey  // ACA env still requires shared-key today
    appInsightsConnectionString: appInsights.outputs.connectionString
  }
}

// Every ACA app + ACA job container reads APPLICATIONINSIGHTS_CONNECTION_STRING
// from env. Pass it through `containers[].env`:
//   - { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.outputs.connectionString }
//
// MCP server, bot, workspace, deadline-watcher cron — all four get the same env var.
// The Foundry hosted agent does NOT — Foundry auto-injects it (Layer 2).
```

> **The shared-key gotcha.** Azure Container Apps environment binding
> to LAW still uses `customerId + sharedKey` (not RBAC) as of late 2025.
> This is the one remaining keyed surface in an otherwise-keyless stack.
> Document the exception in your README; don't fight it.

---

## Layer 2 — Foundry hosted agent (the runtime)

The hosted agent runtime emits traces automatically — but ONLY if the
account has an AppInsights connection registered. **Without that
connection, the runtime silently drops every span.**

> **Architecture (MAF 1.6.0+).** The platform (`azure.ai.agentserver`)
> manages its OWN OTel pipeline via `_tracing.py:_setup_log_export()`.
> This pipeline captures platform log records (HTTP requests, agent
> lifecycle, message routing) but does NOT export dependency spans.
> With 1.6.0, the hosting package bundles `microsoft-opentelemetry`
> which adds the SpanExporter + all instrumentors (openai-v2, httpx,
> etc.) — gen_ai dependency spans flow automatically.
>
> **Do NOT call standalone `configure_azure_monitor()` in
> `container.py`** — it conflicts with the platform's TracerProvider
> setup, causing duplicate log records and/or lost spans. The only
> telemetry code you need is the env var passthrough (for O-012
> workaround) and optionally `client.configure_azure_monitor()`.
> See `foundry-hosted-agents` § MAF 1.6.0 update.

### Step 2.1 — Create the account-level connection (postprovision)

```bash
# infra/scripts/connect_foundry_appinsights.py — see references/postprovision/
uv run infra/scripts/connect_foundry_appinsights.py
```

The script:
1. Reads `${AZURE_FOUNDRY_ACCOUNT_NAME}` and `${AZURE_APPINSIGHTS_RESOURCE_ID}` from azd env
2. PUTs to `https://management.azure.com/subscriptions/.../accounts/{name}/connections/AppInsights?api-version=2025-04-01-preview`
3. Body: `{ "properties": { "category": "AppInsights", "target": "<armResourceId>", "metadata": { "ApiType": "Azure" } } }`
4. The connection is on the **account**, not the project — this is the
   trap that bites everyone

After this runs, the platform begins injecting
`APPLICATIONINSIGHTS_CONNECTION_STRING` into every hosted-agent
container revision automatically.

### Step 2.2 — RBAC for the agent identities

The hosted-agent platform creates **two** managed identities per agent
(`AgentService-<agent-name>` + `Foundry-<workspace>`). Both need
`Application Insights Data Ingestor` (role GUID `f526a384-...`) on the
AppInsights resource, OR they fail to ingest telemetry with HTTP 400
"Bad Request". The Bicep in Step 1.2 grants it to your workload UAMI; the
postprovision script extends the same grant to the platform-managed
identities.

### Step 2.3 — agent.yaml — what NOT to set

```yaml
# agent.yaml
environment_variables:
  - name: COSMOS_ENDPOINT
    value: ${AZURE_COSMOS_ENDPOINT}
  - name: SEARCH_ENDPOINT
    value: ${AZURE_SEARCH_ENDPOINT}
  # ❌ DO NOT add APPLICATIONINSIGHTS_CONNECTION_STRING here
  # The platform injects it from the account-level connection.
  # Setting it manually causes telemetry collisions.
```

Add it to `agent.yaml` and the agent runtime errors with
`APPLICATIONINSIGHTS_CONNECTION_STRING is reserved`.

> **⚠️ Layer 2 caveat — hosted-agent containers MUST guard the init too.**
> The "platform auto-injects `APPLICATIONINSIGHTS_CONNECTION_STRING`"
> promise is **best-effort, not contractual** — we have field evidence
> that it can silently fail. In some regions, the AppInsights
> account-level connection can persist as
> `credentials: null` (silent-drop on AAD-rejected → ApiKey-fallback PUT
> — see "Auth-type platform forensic" below). The platform did NOT
> inject the env var. The hosted-agent container called raw
> `configure_azure_monitor()` as the first line of `main()`. The SDK
> raised `ValueError`. The container crashed before `ResponsesHostServer`
> bound. Foundry returned `server_error`/`model:""` on every smoke —
> with ZERO telemetry to debug it (telemetry init was what crashed).
> **The agent itself was fine.**
>
> **Discipline.** Hosted-agent `container.py` MUST use the same
> guarded-init pattern as ACA workloads (Layer 3 helper below), NOT
> raw `configure_azure_monitor()`. Treat the platform's auto-injection
> guarantee as best-effort — guard it like Layer 3 does. See gap rows
> O-011 / O-012 for the full forensic and the canonical inline helper
> shape.

---

## Layer 3 — ACA workloads + hosted-agent containers (MCP / bot / workspace / cron / agent)

The Foundry runtime auto-instruments hosted agents, but **everything
else** (your MCP server, your bot, your workspace, your cron jobs) is
plain Python or Node — you wire OTel yourself. **And per the Layer 2
caveat above, hosted-agent `container.py` belongs in this bucket too**
when the platform's auto-injection of `APPLICATIONINSIGHTS_CONNECTION_STRING`
fails — they MUST use the same `init_telemetry()` helper as every other
workload, just defensively guarded so a missing env var doesn't crash
startup.

### Step 3.1 — Python init (one line of init code per workload)

```python
# src/mcp/server.py (or src/bot/app.py, or src/jobs/deadline-watcher/main.py)
from azure.monitor.opentelemetry import configure_azure_monitor

# Reads APPLICATIONINSIGHTS_CONNECTION_STRING from env automatically.
# Call ONCE at module import / before any FastMCP / FastAPI / app code.
# Wraps OTel SDK + Azure Monitor exporter + standard library instrumentations
# (logging, urllib3, requests, fastapi, httpx, redis, postgres, ...) in one shot.
configure_azure_monitor(
    logger_name="<process>-mcp",          # show up as cloudRoleName in AppIn
    instrumentation_options={
        "azure_sdk": { "enabled": True },   # capture Cosmos / AOAI / Search SDK calls
        "fastapi":   { "enabled": True },   # MCP server is FastAPI under the hood
        "django":    { "enabled": False },
        "flask":     { "enabled": False },
        "psycopg2":  { "enabled": False },
        "requests":  { "enabled": True },
        "urllib3":   { "enabled": True },
        "urllib":    { "enabled": True },
    },
)
```

See `references/python/otel_init.py` for the full version (handles
missing env var gracefully — important for local-test pattern).

### Step 3.2 — requirements.txt addition

```
azure-monitor-opentelemetry>=1.6.0
```

That's the only dep. It transitively pulls in opentelemetry-api,
opentelemetry-sdk, the AzureMonitor exporter, and the auto-instrumentors.
Don't pin individual `opentelemetry-*` packages — they drift fast and
the Azure-Monitor wrapper version-locks the compatible set for you.

### Step 3.3 — ACA env wiring

```bicep
// infra/modules/<svc>-aca.bicep — for MCP, bot, workspace
containers: [
  {
    name: 'mcp'
    image: image
    env: [
      // ... cosmos, search, etc ...
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: appInsightsConnectionString  // passed from main.bicep
      }
    ]
  }
]
```

For ACA Jobs (cron `deadline-watcher`):

```bicep
// infra/modules/aca-job.bicep
configuration: {
  triggerType: 'Schedule'
  scheduleTriggerConfig: {
    cronExpression: '*/15 * * * *'
  }
}
template: {
  containers: [
    {
      name: 'deadline-watcher'
      image: image
      env: [
        // ... cosmos endpoint, etc ...
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
      ]
    }
  ]
}
```

> **The silent-cron lesson** (from recent pilot retrospectives — see
> `azd-patterns` § ACA Job silent-failure playbook). When the cron
> exits with non-zero before any `print()` reaches stdout, ACA's
> default LAW logging routes nothing — but if `configure_azure_monitor()`
> ran successfully *before* the crash, the exception trace lands in
> AppIn `exceptions` table even though `ContainerAppConsoleLogs_CL` is
> empty. **Initialize OTel as the very first thing in `__main__`** —
> before any I/O, any imports of Cosmos SDK, any environment lookups.

---

## Diagnostic queries (KQL)

Drop these in your repo's `docs/queries/` and reference from the
runbook. See `references/queries/` for the full set.

### "Did ANY trace land in the last 5 minutes?" — the smoke probe

```kql
union traces, requests, dependencies, exceptions
| where timestamp > ago(5m)
| summarize count() by table=$table, cloud_RoleName
| order by count_ desc
```

If `count_ == 0` for everything, the AppInsights connection is broken
at one of the three layers above. Most common causes:

| Symptom | Layer | Fix |
|---|---|---|
| `count_ == 0` everywhere, never recovered | Layer 1 — connection string never reached the workload | `az containerapp show -g <rg> -n <app> --query 'properties.template.containers[0].env'` — confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` is present |
| Hosted agent absent (`AgentService-*` cloudRoleName), ACA workloads fine | Layer 2 — Foundry account-level connection missing or RBAC missing | Re-run `connect_foundry_appinsights.py`; verify `Application Insights Data Ingestor` on agent identities |
| MCP traces present, agent traces absent | Layer 2 only — agent runtime not emitting | Check the agent's `agent.yaml` — make sure `APPLICATIONINSIGHTS_CONNECTION_STRING` is NOT in `environment_variables` (manual override breaks platform injection) |
| Some workloads fine, one missing | Layer 3 — that workload didn't call `configure_azure_monitor()` | Grep that service's entry-point file for the call; add it as the first line of `__main__` |
| Traces present but no `customDimensions` from your code | Logging not bridged into OTel | `import logging; logging.getLogger(__name__).info("...")` should auto-flow once `configure_azure_monitor()` ran. If it doesn't, check `logging` is in the `instrumentation_options` |

### Hosted-agent traces, last hour

```kql
// Platform log traces (HTTP, messages, agent lifecycle)
traces
| where timestamp > ago(1h)
| where cloud_RoleName startswith "AgentService-" or cloud_RoleName startswith "agent-"
| project timestamp, severityLevel, message, cloud_RoleName
| order by timestamp desc
```

### Hosted-agent gen_ai spans (model, tokens, latency)

> **Note (MAF 1.6.0+):** gen_ai dependency spans use
> `cloud_RoleName == "agent_framework"` — NOT the agent name prefix.
> Queries filtering `startswith "agent-"` will miss these spans.

```kql
dependencies
| where timestamp > ago(1h)
| where cloud_RoleName == "agent_framework"
| project timestamp, name,
    model=tostring(customDimensions['gen_ai.response.model']),
    op=tostring(customDimensions['gen_ai.operation.name']),
    input_tokens=tostring(customDimensions['gen_ai.usage.input_tokens']),
    output_tokens=tostring(customDimensions['gen_ai.usage.output_tokens']),
    duration
| order by timestamp desc
```

### MCP tool-call breakdown

```kql
dependencies
| where timestamp > ago(1h)
| where cloud_RoleName has "mcp"
| where name has "tools/call"
| extend tool = tostring(customDimensions.['mcp.tool.name'])
| summarize count(), avg_ms=avg(duration), p95_ms=percentile(duration, 95) by tool
| order by count_ desc
```

### Silent-cron debug — exec failures with no console output

```kql
let job_name = "ca-job-deadline-watcher";
let window = 1h;
union
  (exceptions
    | where timestamp > ago(window)
    | where cloud_RoleName has job_name
    | project timestamp, table="exceptions", problem=type, outerMessage),
  (ContainerAppConsoleLogs_CL
    | where TimeGenerated > ago(window)
    | where ContainerAppName_s has job_name
    | project timestamp=TimeGenerated, table="console", problem=Log_s, outerMessage="")
| order by timestamp desc
```

If `exceptions` returns rows but `console` is empty, the cron initialized
OTel before crashing — you have a stack trace in AppIn even though logs
are silent. This is the single most useful query when an ACA Job is
"failing without telemetry."

---

## Threadlight integration

| Skill | What it gets from this skill |
|-------|-----------------------------|
| `threadlight-design` | SPEC § 11c selectors must include `app-insights: yes` and `log-analytics: yes` (always — never opt-out). manifest.json `deployment_manifest.expected_resource_types` must list `Microsoft.Insights/components` and `Microsoft.OperationalInsights/workspaces` |
| `threadlight-deploy` | Phase 6 always-include modules: `app-insights.bicep` + `log-analytics.bicep`. Postprovision hook must call `connect_foundry_appinsights.py`. Every ACA service module passes `APPLICATIONINSIGHTS_CONNECTION_STRING` env. Every Python entry-point starts with `configure_azure_monitor()` |
| `threadlight-safe-check` | NEW Step 5.6 (App Insights existence) — see that skill's post-deploy phase. Gate FAILS if `Microsoft.Insights/components` not in deployed RG when SPEC declared `app-insights: yes`. Optional smoke query (`first-trace-probe.kql`) can be invoked manually after PoC smoke to confirm traces actually flow |
| `foundry-hosted-agents` | RBAC pin (`Application Insights Data Ingestor`) on agent identities; `APPLICATIONINSIGHTS_CONNECTION_STRING is reserved` rule for `agent.yaml` |
| `foundry-mcp-aca` | Layer 3 init (`configure_azure_monitor()` in `server.py`); ACA env wiring (env var passthrough) |
| `foundry-teams-bot` | Layer 3 init (`configure_azure_monitor()` in `app.py`); same env wiring |
| `threadlight-event-triggers` | ACA Job init pattern (OTel as first line of `__main__` so cron crashes leave a trace) |
| `threadlight-workspace-ui` | If workspace ships an API gateway (FastAPI), Layer 3 init applies. Pure-static workspace doesn't need OTel — but the nginx access logs still flow to LAW via ACA env binding |
| `threadlight-local-test` | OTel init must be **conditional** on `APPLICATIONINSIGHTS_CONNECTION_STRING` being set — don't spam local dev with telemetry-init errors when running against the local stack |
| `azd-patterns` | The cron silent-failure playbook in `azd-patterns` references the `silent-cron-debug.kql` query in this skill |
| `foundry-evals` | Eval Phase 1 invoke writes traces too (same connection). Eval scores live in Foundry; agent telemetry lives in AppIn — different signals, both required |

---

## Common silent-failure modes (the gap catalog)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| O-001 | AppIn empty after `azd up` returned 0 | `app-insights.bicep` not in `infra/main.bicep` (Phase 6 module composer skipped it) | Always include — never opt-out |
| O-002 | AppIn provisioned but zero traces | Foundry account-level connection never created | Run postprovision hook `connect_foundry_appinsights.py` |
| O-003 | Hosted agent OK, MCP / bot / cron silent | `configure_azure_monitor()` not called in those services | Add as first line of `__main__` (or module-level) |
| O-004 | Agent emits `APPLICATIONINSIGHTS_CONNECTION_STRING is reserved` | Connection string set in `agent.yaml` `environment_variables` | Remove it — platform auto-injects |
| O-005 | OTel exporter returns HTTP 400 "Bad Request" when `DisableLocalAuth: true` | Wrong RBAC role: `Monitoring Metrics Publisher` covers only custom metrics API, NOT OTel trace/log ingestion | Grant `Application Insights Data Ingestor` (GUID `f526a384-b230-433a-b45c-95f59c4a2dec`) instead. Verify both `AgentService-*` and `Foundry-*` UAMI principals have it. If `DisableLocalAuth: false`, this is not the issue |
| O-006 | Cron logs empty in `ContainerAppConsoleLogs_CL` despite failure | Container exits before stdout flushed; OTel ran first → `exceptions` table has the trace | Use the `silent-cron-debug.kql` union query — don't trust console logs alone |
| O-007 | Local-test runs spam errors at startup | OTel init unguarded against missing env var | Wrap `configure_azure_monitor()` in `if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):` |
| O-008 | Telemetry from two pilots collides in same AppIn | One AppIn shared across pilots without `cloud_RoleName` discipline | Pass distinct `logger_name` per service, OR provision one AppIn per pilot |
| O-009 | Traces appear briefly then stop after redeploy | New ACA revision didn't get the env var (drift in revision template) | Check the most recent revision's container env explicitly: `az containerapp revision show -g <rg> -n <app> --revision <rev> --query 'properties.template.containers[0].env'` |
| O-010 | Telemetry shows but with key-based auth (despite `disableLocalAuth=true`) | A previous deploy left the ingestion key path active | Force-set `DisableLocalAuth: true`; redeploy; old keys stop working immediately |
| O-011 | **Hosted agent returns `server_error` / `model: ""` on every smoke; AppIn 0 rows; container looks healthy in `azd ai agent show`** | `container.py` calls raw `configure_azure_monitor()` as the first line of `main()` with no try/except. When the platform's `APPLICATIONINSIGHTS_CONNECTION_STRING` auto-injection fails (e.g. account-level AppIn connection persisted with `credentials: null` — see O-012), the SDK raises `ValueError`. Container exits before `ResponsesHostServer` binds; Foundry runtime sees no agent. **The agent itself is fine — only telemetry init crashed it.** | **Hosted-agent `container.py` MUST use guarded init** — `init_telemetry()` from `references/python/otel_init.py` OR inline an 8-line equivalent that no-ops on (a) missing env var, (b) SDK ImportError, (c) any SDK exception. Never call `configure_azure_monitor()` raw at module/main scope. The agent works fine without telemetry — don't let telemetry init kill it |
| O-012 | AppInsights connection PUT returns HTTP 400 ValidationError on `authType: AAD`; ApiKey fallback returns 200 but `credentials: null` on subsequent GET (silent server-side drop) | Platform gap on account-RP scope — confirmed on `2025-04-01-preview`, `2025-06-01`, `2025-10-01-preview`, `2026-03-01`, `2026-03-15-preview` across `northcentralus` and `eastus2`. The data-plane `getConnectionWithCredentials` API also returns `credentials: {}`. `FoundryChatClient.configure_azure_monitor()` (SDK path) calls `telemetry.get_application_insights_connection_string()` → `_get_with_credentials` → empty credentials → `ValueError`. **Neither the platform env var injection NOR the SDK telemetry path work on O-012 affected accounts.** | **WORKAROUND FOUND (May 2026).** Pass `APPLICATION_INSIGHTS_CONNECTION_STRING` (note: underscore between APPLICATION and INSIGHTS) directly in `HostedAgentDefinition.environment_variables` via `create_version()`. The platform reserves `APPLICATIONINSIGHTS_CONNECTION_STRING` (no underscore) but accepts the underscored variant. In `container.py`, read both names with priority to the underscored variant, validate with `startswith("InstrumentationKey=")`, and call `configure_azure_monitor(connection_string=...)` explicitly. Verified: 88 traces + gen\_ai dependency spans landed in App Insights from a hosted agent on `northcentralus`. See `threadlight-deploy` § deploy.py env var passthrough for the exact wiring. |
| O-013 | `FoundryChatClient.configure_azure_monitor()` fails with `ValueError("Application Insights connection does not have a connection string.")` even after account-level connection created | SDK calls `telemetry.get_application_insights_connection_string()` → lists connections → `_get_with_credentials(name)` → data-plane returns `credentials: {}` (empty dict, not the key stored via management API PUT). Same root cause as O-012 — management and data plane don't share the credential. | Use the O-012 workaround (env var passthrough). The SDK path (`FoundryChatClient.configure_azure_monitor()`) is a clean fallback for accounts where O-012 is NOT present — keep it as Path 2 after the env var Path 1. |

### Auth-type platform forensic (some regions)

The Layer 2 caveat callout above and gap rows O-011 / O-012 are
anchored on this forensic. Three remediation paths attempted, **all
failed with documented evidence**:

| Path | Outcome | Evidence anchor |
|---|---|---|
| 1. Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in `agent.yaml` (escape hatch) | HTTP 400 `invalid_request_error`: "Environment variable 'APPLICATIONINSIGHTS_CONNECTION_STRING' is reserved for platform use" | Request IDs available in platform logs |
| 2. AAD `authType` on PUT to AppInsights connection (skill-recommended) | HTTP 400 ValidationError: "AuthType for AppInsights Connection can only be ApiKey" | Correlation IDs available in platform logs (`2025-10-01-preview`) |
| 3. ApiKey `authType` with `credentials.key` in body (workaround) | HTTP 200 on PUT, GET returns `credentials: null` (silent-drop on a brand-new clean account-level resource at canonical scope) | `isDefault: true, isSharedToAll: true` records on the connection; platform still does NOT inject the env var |

> **Re-confirmation guidance.** If the same three failure paths reproduce
> on a separate Foundry account with a clean install + upgraded agent
> dependencies (`agent-framework-foundry-hosting` >= `1.0.0a260421`),
> treat the behavior as platform-region, not project- or dependency-
> specific. For affected regions, ship Layer 3 telemetry and skip the
> AppIn account connection until the platform fix lands.

**Lesson.** The Layer 2 promise ("platform auto-injects when you have
an account-level `AppInsights` connection") cannot be relied upon as a
runtime contract. Layer 2 is best-effort observability; **Layer 3
(`init_telemetry()` everywhere — including in the hosted-agent
container) is the contract that holds.** Build for Layer 3; treat
Layer 2 as a bonus.

> **O-012 workaround found (May 2026).** Pass `APPLICATION_INSIGHTS_CONNECTION_STRING`
> (underscored variant) directly in `HostedAgentDefinition.environment_variables`
> via `create_version()`. The platform reserves `APPLICATIONINSIGHTS_CONNECTION_STRING`
> (no underscore) but accepts the underscored name. In the container entrypoint:
>
> ```python
> def _valid_cs(cs: str | None) -> str:
>     cs = (cs or "").strip()
>     return cs if cs.startswith("InstrumentationKey=") else ""
>
> _CS = _valid_cs(os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING")) \
>     or _valid_cs(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
> if _CS:
>     os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = _CS
>     configure_azure_monitor(connection_string=_CS, logger_name="hosted-agent-maf")
> ```
>
> This bypasses both the broken platform auto-injection AND the broken
> SDK `FoundryChatClient.configure_azure_monitor()` path (which also
> hits O-012 via `_get_with_credentials` → empty credentials).
> Verified: 88+ traces from a hosted agent on `northcentralus`.
>
> **Also requires**: `no_cache=True` on `DockerBuildRequest` + a used
> `ARG BUILD_TS` (`RUN echo $BUILD_TS > /dev/null`) in the per-job
> Dockerfile, otherwise ACR layer caching produces identical digests
> and Foundry deduplicates `create_version` — the new code never
> reaches the container. See `foundry-hosted-agents` § Image-tag
> staleness trap.

---

## Validation checklist

Before declaring a pilot "deploy-complete":

- [ ] `infra/modules/log-analytics.bicep` exists and is referenced from `main.bicep`
- [ ] `infra/modules/app-insights.bicep` exists and is referenced from `main.bicep`
- [ ] `infra/scripts/connect_foundry_appinsights.py` exists and is called from `azure.yaml` `postprovision` hook
- [ ] Every ACA service in `azure.yaml` (MCP, bot, workspace, cron) passes `APPLICATIONINSIGHTS_CONNECTION_STRING` env from bicep outputs
- [ ] Every Python entry-point under `src/` calls `configure_azure_monitor()` before any other init
- [ ] `agent.yaml` does NOT include `APPLICATIONINSIGHTS_CONNECTION_STRING` in `environment_variables`
- [ ] `Application Insights Data Ingestor` granted to workload UAMI in `app-insights.bicep`
- [ ] Postprovision hook also grants Application Insights Data Ingestor to `AgentService-*` and `Foundry-*` platform identities
- [ ] After `azd up` smoke + first agent invocation, the smoke probe `first-trace-probe.kql` returns ≥ 1 row from each of: hosted-agent (`AgentService-*` cloudRoleName), MCP (`mcp` cloudRoleName), bot (`bot` cloudRoleName)
- [ ] `threadlight-safe-check` Step 5.6 (App Insights existence) PASSES

If any box is unchecked, **the pilot is not deploy-complete**. The
visible "agent works in the portal" smoke does not catch this gap —
the agent works exactly the same with or without telemetry. Only the
KQL probe catches it.

---

## References

- App Insights workspace-based components: <https://learn.microsoft.com/azure/azure-monitor/app/create-workspace-resource>
- `azure-monitor-opentelemetry` Python SDK: <https://learn.microsoft.com/python/api/overview/azure/monitor-opentelemetry-readme>
- Foundry account-level connections (AppInsights category): <https://learn.microsoft.com/azure/ai-foundry/concepts/connections>
- Application Insights Data Ingestor role: <https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/monitor#application-insights-data-ingestor>
- ACA env LAW + AppIn binding: <https://learn.microsoft.com/azure/container-apps/observability>
- KQL reference: <https://learn.microsoft.com/azure/data-explorer/kusto/query/>

Related skills: `threadlight-deploy`, `threadlight-safe-check`,
`foundry-hosted-agents`, `foundry-mcp-aca`, `foundry-teams-bot`,
`threadlight-event-triggers`, `azd-patterns`, `foundry-evals`.

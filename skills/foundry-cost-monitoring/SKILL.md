---
name: foundry-cost-monitoring
description: >
  Continuous Foundry token-cost monitoring, chargeback, budget alerts,
  and FinOps automation. Joins gen_ai.usage spans emitted by
  foundry-observability with the Azure Retail Prices API to compute
  per-agent / per-project / per-tenant cost projection. Wires Cost
  Management budgets + Action Groups, and uses Foundry's project-tag
  attribution (preview) for chargeback. USE FOR: foundry cost
  monitoring, token cost dashboard, FinOps Foundry, project-level
  chargeback, project tag cost attribution, Azure retail prices API,
  gen_ai.usage cost KQL, budget alert Foundry, Action Group cost
  webhook, token cost anomaly detection, OTel vs Cost Management
  reconciliation, per-agent / per-tenant token spend.
  DO NOT USE FOR: one-shot PTU vs PAYGO sizing (use
  paygo-ptu-cost-analyzer); emitting cost telemetry from agent code
  (use foundry-observability); gateway-only chargeback via x-app-id
  (use citadel-spoke-onboarding); fine-tuning cost estimates.
metadata:
  version: "1.0.4"
---

# Foundry Cost Monitoring

Continuous, FinOps-grade cost monitoring for Microsoft Foundry. Where
[`foundry-observability`](../foundry-observability/SKILL.md) emits the
`gen_ai.usage.*` spans, this skill **consumes** them — joining them with
the Azure Retail Prices API to project per-agent, per-project, and
per-tenant cost in near-real time, then wiring Cost Management budgets
and Action Groups so the FinOps team sees overruns within minutes
instead of next-month's invoice.

> **Sibling skills.** Pair with `foundry-observability` for the telemetry
> emit path, [`paygo-ptu-cost-analyzer`](../paygo-ptu-cost-analyzer/SKILL.md)
> for one-shot PTU sizing decisions, and
> [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) when
> chargeback is gateway-mediated via APIM `x-app-id` headers.

---

## §1 — Three layers of cost truth

Foundry cost lands in three places, with three different latencies and
three different fidelities:

| Layer | Source | Latency | Fidelity | Use for |
|-------|--------|---------|----------|---------|
| **1. Foundry portal estimate** | `ai.azure.com` → Operate → Overview / Build → Agent / Model Monitor | ≈ 2–5 min | **Estimate** — not invoiceable | Near-real-time engineering insight (per-agent rollup) |
| **2. OTel real-time projection** | App Insights `customDimensions['gen_ai.usage.*']` × Retail Prices rate card | ≈ 2–5 min ingest + your KQL window | **Engineering projection** — not invoiceable | Per-tenant / per-agent / per-conversation projection, anomaly detection, dashboards |
| **3. Cost Mgmt actuals** | `Microsoft.CostManagement/query` REST + invoice CSV exports | ≈ 8–24 h | **Source of truth** for billing | Finance reconciliation, chargeback, budgets |

**Reconciliation rule** (and this is the rule that prevents the awkward
quarterly call with finance): treat **layer 3** as authoritative for
anything that ends up on the bill. Layers 1 and 2 are engineering tools
to **see overruns before** layer 3 catches up. Per the MS Learn cost
guidance: *"treat your invoice and meter records as the source of
truth."*

---

## §2 — Pricing source: Azure Retail Prices REST API

The [Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
is anonymous, public, and rate-card complete:

```
GET https://prices.azure.com/api/retail/prices
    ?$filter=<OData filter>
    [&$top=N]
    [&$skip=N]
```

No auth header. No subscription. Just `curl` (or `urllib.request`). The
filter shape that matters for Foundry models in Sweden Central:

```bash
# Foundry models (post-rename — current GA service classification)
curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName eq 'Foundry Models' and armRegionName eq 'swedencentral' and contains(meterName, 'Tokens')" | jq '.Items[0:3]'

# Embeddings — Sweden Central requires GlobalStandard SKU; filter accordingly
curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName eq 'Foundry Models' and armRegionName eq 'swedencentral' and contains(productName, 'embedding')"
```

Each `Items[]` row carries the fields you need to price a token row:

| Field | Example | What it means |
|-------|---------|---------------|
| `serviceName` | `Foundry Models` | Top-level service classification |
| `productName` | `Azure OpenAI`, `Azure Llama Models`, `Azure OpenAI GPT5` | Model family bucket |
| `skuName` | `gpt 4.1 Inp regnl` | Deployment-shape SKU |
| `meterName` | `gpt 4.1 Inp regnl Tokens` | Billing meter |
| `retailPrice` | `0.00242` | Per `unitOfMeasure` |
| `unitOfMeasure` | `1K`, `1M` | Token unit (mix of `1K` and `1M` — **normalize before multiplying**) |
| `currencyCode` | `USD` | Pricing currency |
| `armRegionName` | `swedencentral` | Region |
| `type` | `Consumption` | `Consumption` for PAYGO, `Reservation` for PTU |

**Pagination**: response includes `NextPageLink`; iterate until null when
caching the full catalog (~thousands of rows for `AI + Machine Learning`).

> **Service-name drift.** The Retail Prices API used to surface OpenAI
> meters under `serviceName eq 'Cognitive Services'`. Current GA
> classification is **`Foundry Models`**. The drift detector for this
> skill polls the Retail Prices endpoint weekly — if a new classification
> appears, refresh § 11 of this skill and bump PATCH.

**Cache TTL recommendation**: 24 h. Rates change weekly at most; daily
refresh comfortably beats invoice cadence.

---

## §3 — Foundry `project` tag chargeback (Preview)

Foundry automatically tags Models-sold-by-Azure usage records with a
`project` tag whose value is the Foundry project name. The chargeback
flow is then:

1. In Cost Management → Cost Analysis, scope to your Foundry resource.
2. **Add filter** → **Tag** → `project`.
3. Pick one or more projects → cost split by project, time-series.

CLI equivalent:

```bash
az consumption usage list \
  --subscription "$SUB" \
  --start-date "$(date -u -v-30d +%Y-%m-%d)" \
  --end-date "$(date -u +%Y-%m-%d)" \
  --query "[?tags.project=='proj-fsi-claims'].{date:usageStart, meter:meterDetails.meterName, qty:quantity, cost:pretaxCost}" \
  -o table
```

> **Verbatim preview limit (MS Learn, [manage-costs#chargeback-with-project-level-cost-attribution-preview](https://learn.microsoft.com/azure/foundry/concepts/manage-costs#chargeback-with-project-level-cost-attribution-preview)):**
>
> *"Project-level cost attribution is currently supported for Models
> sold by Azure (Azure Direct models, including Azure OpenAI). It isn't
> yet supported for models served through Azure Marketplace."*

Concretely: Azure OpenAI / Foundry-native models → tagged automatically.
Llama / Mistral / DeepSeek / Cohere via Azure Marketplace → **no project
tag**; fall back to layer-2 OTel projection (§ 4) or per-resource
grouping (one project ↔ one resource group).

The tag is **not manually applied** — do not try to add it via
`az tag create-or-update`; Foundry control plane writes it on the
underlying meter records.

---

## §4 — In-flight cost projection: KQL on `gen_ai.usage.*`

This is the engineering-insight layer. Requires `foundry-observability`
already wired (account-level App Insights connection + ACA-side
`configure_azure_monitor()`). The MAF 1.6.0+ schema emits OTel spans
with the following `customDimensions`:

| Key | Type | Example |
|-----|------|---------|
| `gen_ai.system` | string | `azure_openai` |
| `gen_ai.request.model` | string | `gpt-5.4-mini` |
| `gen_ai.response.model` | string | `gpt-5.4-mini-2026-01-15` |
| `gen_ai.usage.input_tokens` | int | `1284` |
| `gen_ai.usage.output_tokens` | int | `342` |
| `gen_ai.operation.name` | string | `chat`, `embeddings` |

Spans land in `traces` / `dependencies` depending on instrumentation. The
canonical filter for MAF-emitted spans is `cloud_RoleName == "agent_framework"`
(verified at MAF 1.6.0+ — see [`foundry-observability`](../foundry-observability/SKILL.md)
§ "OTel cloud_RoleName" for the rationale).

### 4.1 Per-agent cost rollup (last 24 h)

```kql
// Per-agent token cost (last 24h) — projection-only, not invoiceable
let rateCard = externaldata(model:string, in_rate_usd_per_1k:real, out_rate_usd_per_1k:real)
  [@"https://raw.githubusercontent.com/<your-org>/<your-repo>/main/rate-card.csv"]
  with (format="csv", ignoreFirstRecord=true);
dependencies
| where timestamp > ago(24h)
| where cloud_RoleName == "agent_framework"
| where isnotempty(customDimensions["gen_ai.usage.input_tokens"])
| extend
    agent      = tostring(customDimensions["gen_ai.agent.name"]),
    model      = tostring(customDimensions["gen_ai.request.model"]),
    in_tokens  = toint(customDimensions["gen_ai.usage.input_tokens"]),
    out_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| join kind=leftouter rateCard on model
| extend
    in_cost  = (in_tokens  / 1000.0) * in_rate_usd_per_1k,
    out_cost = (out_tokens / 1000.0) * out_rate_usd_per_1k
| summarize
    calls            = count(),
    input_tokens     = sum(in_tokens),
    output_tokens    = sum(out_tokens),
    projected_cost_usd = sum(in_cost + out_cost)
    by agent, model
| order by projected_cost_usd desc
```

### 4.2 Per-project cost rollup

`gen_ai.agent.name` carries the agent name. To get per-project rollup
without the preview tag, instrument the project name as a resource
attribute on the OTel exporter (e.g. `OTEL_RESOURCE_ATTRIBUTES="foundry.project=proj-fsi-claims"`)
and group on `customDimensions["foundry.project"]` instead of `agent`.
Where the `project` tag (§ 3) IS available, prefer Cost Management for
authoritative reconciliation and reserve KQL for in-flight projection.

### 4.3 Per-tenant cost rollup (Citadel APIM gateway path)

If traffic goes through the AI Citadel gateway (see § 5), the APIM
fragment-policy stamps the tenant identifier into the OTel span as
`enduser.id` (gateway maps `x-app-id` header → `enduser.id`). The
per-tenant rollup is identical to § 4.1 but groups on
`tostring(customDimensions["enduser.id"])`.

---

## §5 — Citadel APIM `x-app-id` chargeback path

When Foundry traffic is fronted by an APIM AI Gateway (the AI Citadel
Hub topology), tenant identity arrives on the `x-app-id` request header
and the gateway logs it into App Insights. This is the cleanest
chargeback path for multi-tenant SaaS deployments because it does not
depend on Foundry's project-tag preview.

Wiring path (full detail in
[`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md)):

```
Tenant request → APIM (validates JWT, stamps x-app-id) → Foundry
                                                            ↓
                                                    OTel span tagged with
                                                    enduser.id = x-app-id
```

KQL aggregates over `enduser.id` then rejoin to the customer-ID-to-name
table (kept outside this skill — usually a Cosmos/Kusto reference
table).

---

## §6 — Budget alerts via Azure Cost Management

Set bottom-up: subscription budget + per-RG budgets for spike isolation.

### 6.1 Bicep (recommended)

```bicep
// budget.bicep — per-RG budget with notifications at 80% / 100% / 120%
@description('Budget amount in USD per month')
param budgetAmount int = 5000

@description('FinOps distribution list')
param finopsEmails array = [
  'finops@<example-bank>.com'
]

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'budget-foundry-${resourceGroup().name}'
  properties: {
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-06-01'
    }
    category: 'Cost'
    notifications: {
      Warning_80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: finopsEmails
        thresholdType: 'Actual'
      }
      Critical_100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: finopsEmails
        contactGroups: [
          actionGroup.id
        ]
        thresholdType: 'Actual'
      }
      Forecast_120: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 120
        contactEmails: finopsEmails
        thresholdType: 'Forecasted'
      }
    }
    filter: {
      tags: {
        name: 'project'
        operator: 'In'
        values: [
          'proj-fsi-claims'
          'proj-fsi-onboarding'
        ]
      }
    }
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2024-10-01-preview' = {
  name: 'ag-finops-${resourceGroup().name}'
  location: 'global'
  properties: {
    groupShortName: 'finops'
    enabled: true
    webhookReceivers: [
      {
        name: 'finops-teams'
        serviceUri: '<teams-incoming-webhook-url>'
        useCommonAlertSchema: true
      }
    ]
  }
}
```

### 6.2 CLI equivalent

```bash
# Resource-group scoped budget — fires Action Group on actual cost > $5000
az consumption budget create-with-rg \
  --resource-group "$RG" \
  --budget-name "budget-foundry-$RG" \
  --amount 5000 \
  --time-grain Monthly \
  --start-date "$(date -u +%Y-%m-01)" \
  --category Cost \
  --notifications-properties \
      "[{operator:'GreaterThan',threshold:80,contactEmails:['finops@<example-bank>.com'],thresholdType:'Actual'}]"
```

> **Hard-limit caveat (MS Learn manage-costs § Create budgets):**
> *"Azure OpenAI doesn't currently provide [hard-limit] functionality.
> You can start automation from action groups as part of your budget
> notifications to take more advanced actions, but this functionality
> requires additional custom development."*
>
> Budgets are **alerts**, not throttles. For hard ceilings, wire the
> Action Group → Logic App / Function that disables the offending
> deployment (e.g. `az cognitiveservices account deployment update
> --properties.callRateLimit=0`).

---

## §7 — Action Group → Webhook / Logic App / Teams

Standard Azure pattern. The Action Group from § 6.1 wires three
common downstream channels:

| Channel | Use case |
|---------|----------|
| **Teams incoming webhook** | FinOps channel notification (`useCommonAlertSchema: true` so payload is parseable) |
| **Logic App** | Disable / scale-down offending deployments automatically |
| **Azure Function** | Custom remediation (e.g. notify owner, file ticket, page on-call) |

The Action Group is fire-and-forget — Cost Management posts the budget
breach event payload to every receiver in parallel.

---

## §8 — Anomaly detection on token cost

The KQL queries in § 4 are point-in-time. To catch *unexpected* spend
spikes (a leaked API key, a runaway agent loop, a prompt that exploded
context-window utilisation), wrap the time-series in
`series_decompose_anomalies`:

```kql
// 7-day token-cost anomaly detection per agent
let bin_size = 1h;
dependencies
| where timestamp > ago(7d)
| where cloud_RoleName == "agent_framework"
| where isnotempty(customDimensions["gen_ai.usage.input_tokens"])
| extend
    agent      = tostring(customDimensions["gen_ai.agent.name"]),
    model      = tostring(customDimensions["gen_ai.request.model"]),
    in_tokens  = toint(customDimensions["gen_ai.usage.input_tokens"]),
    out_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
| summarize total_tokens = sum(in_tokens + out_tokens) by agent, bin(timestamp, bin_size)
| make-series series=sum(total_tokens) default=0 on timestamp from ago(7d) to now() step bin_size by agent
| extend (anomalies, score, baseline) = series_decompose_anomalies(series, 2.5)
| mv-expand timestamp, series, anomalies, score, baseline
| where toint(anomalies) != 0
| project agent, timestamp=todatetime(timestamp), tokens=toint(series), anomaly=toint(anomalies), score=todouble(score)
| order by score desc
```

Wire this query to an Azure Monitor scheduled query alert (15-min
frequency, threshold `count() > 0`) → same Action Group from § 6.

---

## §9 — Reconciliation drift: OTel projection vs Cost Mgmt actuals

The two layers will **never** match exactly. Expected drift:

| Source | Latency | Causes of drift vs invoice |
|--------|---------|----------------------------|
| **OTel projection** | 2–5 min ingest | Stale rate card; dropped spans; OTel sampling; cached input pricing not modeled; reservation discounts not applied |
| **Cost Mgmt actuals** | 8–24 h | Authoritative — the bill |

Acceptable drift: **±5%** day-over-day, **±2%** month-over-month. If your
projection consistently overshoots, the rate card is stale (refresh from
Retail Prices API). If it consistently undershoots, you're missing a
meter — usually the cached-input meter (some models split cached input
into a separate, cheaper meter) or the fine-tuned-hosting hourly meter.

Reconciliation cadence:

1. **Daily**: run § 4.1 KQL for previous day, compare to `query.usage`
   result for the same scope + day. Log delta.
2. **Weekly**: refresh the rate-card CSV from Retail Prices.
3. **Monthly**: full reconciliation against invoice CSV export. Adjust
   `series_decompose_anomalies` baseline if drift bias exceeds ±2%.

---

## §10 — Common pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| **Model-name normalization** | KQL `model` join misses (`gpt-5.4-mini` vs `gpt-5.4-mini-2026-01-15`) | Strip the date suffix before joining: `extend model_base = extract(@"^([a-z0-9\-\.]+?)(?:-\d{4}-\d{2}-\d{2})?$", 1, model)` |
| **Missing meter for new SKU** | Recently-released model returns no rate | Refresh rate card (Retail Prices is updated within hours); fall back to a same-family proxy SKU temporarily |
| **Project-tag preview limit** | Marketplace models (Llama, Mistral, DeepSeek) return zero rows when filtered by `tags.project` | § 3 verbatim — fall back to OTel `customDimensions["foundry.project"]` |
| **OTel ingestion lag** | Cost dashboard shows zero for the last 5 min | Expected. Use `ago(15m)` minimum window. Pattern 13 (LAW soft-PASS) for any alert |
| **Marketplace-vs-direct boundary** | Reconciliation drift > 10% on a Marketplace-heavy tenant | Marketplace meters bill under different scopes (`Global resources` resource group); scope KQL accordingly |
| **Unit-of-measure mix** | Cost projection 1000× too high | Rate card has both `1K` and `1M` units — normalize to `1K` in your rate-card cache |
| **Cached input pricing** | Projection consistently overshoots actuals | Some models emit `gen_ai.usage.input_tokens.cached` separately; price that with the cheaper cached-input meter |
| **Currency mix** | Multi-region tenant has both USD and EUR rows | Filter `currencyCode eq 'USD'` (or normalize FX) in your rate-card cache |
| **Cost Mgmt 429** | `query.usage` throttled under load | Cache to a per-day Kusto table; never query Cost Mgmt from a per-request hot path |

---

## §11 — Permissions matrix

Per [MS Learn `manage-costs#configure-permissions-to-view-costs`](https://learn.microsoft.com/azure/foundry/concepts/manage-costs#configure-permissions-to-view-costs):

| Role | Scope | What it grants | Required for |
|------|-------|----------------|--------------|
| **Cost Management Reader** *(built-in)* | Subscription or RG | View costs and usage data via Cost Mgmt | § 1 layer 3, § 3, § 6, § 9 |
| **Foundry User** *(built-in, formerly Azure AI User)* | Foundry account / project | View Foundry resource data and usage context | § 1 layer 1 (portal estimates), per-agent Monitor tab |
| **Monitoring Reader** *(built-in)* | Subscription or RG containing App Insights | Read App Insights metrics + alerts metadata | § 7 Action Group inspection |
| **Log Analytics Reader** *(built-in)* | LAW workspace | Run KQL via `query_workspace` | § 4, § 8 |
| **Application Insights Component Contributor** *(built-in)* | App Insights resource | Manage alerts (create scheduled-query rules) | § 8 alert wiring |
| **Foundry Cost Reader** *(custom — example below)* | Foundry resource | Least-privilege read for cost-only dashboards | Optional — when you don't want to grant full Cost Management Reader |

> **MS Learn role rename notice (current as of 2026-06).** *"The Foundry
> RBAC roles were recently renamed. Foundry User, Foundry Owner, Foundry
> Account Owner, and Foundry Project Manager were previously named
> Azure AI User, Azure AI Owner, Azure AI Account Owner, and Azure AI
> Project Manager. … The role IDs and core permissions are unchanged."*

### Example custom role: **Foundry Cost Reader**

MS Learn ships an example JSON for a least-privilege custom role
covering cost-only views. Use this when full **Cost Management Reader**
is too broad:

```json
{
  "Name": "Foundry Cost Reader",
  "IsCustom": true,
  "Description": "Can see cost metrics in Foundry",
  "Actions": [
    "Microsoft.Consumption/*/read",
    "Microsoft.CostManagement/*/read",
    "Microsoft.Resources/subscriptions/read",
    "Microsoft.CognitiveServices/accounts/AIServices/usage/read"
  ],
  "NotActions": [],
  "DataActions": [],
  "NotDataActions": [],
  "AssignableScopes": [
    "/subscriptions/<subscriptionId>/resourceGroups/<resourceGroupName>/providers/Microsoft.CognitiveServices/accounts/<foundryResourceName>"
  ]
}
```

Create with:

```bash
az role definition create --role-definition foundry-cost-reader.json
```

> **Important** — the custom role on its own does NOT grant Foundry
> resource visibility. Pair it with **Foundry User** when the role
> recipient also needs to inspect Foundry agents / models / projects.

### CI-side grants used by `awesome-gbb`'s own fixture

The CI UAMI currently has Contributor + AcrPush + Cognitive Services
OpenAI User + Foundry User on the CI resource group (see
AGENTS.md § 9.7 and `.github/ci-shared-preamble.md` for the canonical
identifiers). The fixture for this skill exercises the **Cost
Management read** path; the role needed is **Cost Management Reader**
at subscription scope:

```bash
az role assignment create \
  --assignee-object-id "$AZURE_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Cost Management Reader" \
  --scope "/subscriptions/$AZURE_SUBSCRIPTION_ID"
```

The fixture **soft-passes** on 403 from the Cost Management REST call
per AGENTS.md § 9.7 Pattern 25, so the CI run still emits PASS when this
grant is pending — the role grant is tracked separately and does not
block the catalog from shipping.

---

## §12 — Inference cost optimization levers (FinOps)

§ 1–§ 9 tell you *what* you spend; these levers cut it. Inference cost
turns on three knobs distinct from generic compute right-sizing: **token
volume**, **deployment type** (Standard pay-per-token vs Provisioned/PTU),
and **deployment SKU/region**. Apply in priority order:

| Priority | Lever | Detection | Action | Savings |
|----------|-------|-----------|--------|---------|
| 🔴 Crit | Idle PTU deployment | `sku.name` Provisioned + sustained util below breakeven | PTU bills 24/7 — cut count or move to GlobalStandard | 30–70% |
| 🔴 Crit | Flagship on simple tasks | `gpt-5.4` for classify/extract/route at scale | move to `-mini`/`-nano` | 50–95% |
| 🟠 High | Sync endpoint for batchable work | offline evals/backfills on real-time endpoint | Batch API (24h window) | ~50% |
| 🟠 High | Uncached repeated context | large static system prompt resent every call | enable prompt caching | 10–40% |
| 🟠 High | Regional SKU where Global fits | `Standard`/`DataZoneStandard`, no residency need | switch to GlobalStandard | 5–30% |
| 🟡 Med | Unbounded output | no `max_completion_tokens` cap | cap output (priced > input) | 10–30% |
| 🟡 Med | Oversized embedding | `text-embedding-3-large` where small fits | `text-embedding-3-small` | 60–80% |

**Deployment-type breakeven:** PTU only beats Standard once sustained
throughput clears the per-token breakeven — model it from real volume
(`paygo-ptu-cost-analyzer`) before reserving. Below breakeven, idle PTU
is the single largest inference waste. **Per-app showback** needs
token-level attribution Cost Management lacks — emit `gen_ai.usage.*`
tagged by consumer (§ 4) and reconcile against deployment cost (§ 9).

---

## See also

- [`foundry-observability`](../foundry-observability/SKILL.md) — emits the OTel `gen_ai.usage.*` spans this skill consumes.
- [`paygo-ptu-cost-analyzer`](../paygo-ptu-cost-analyzer/SKILL.md) — one-shot PTU vs PAYGO sizing report (different question, different cadence).
- [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/SKILL.md) — gateway-layer `x-app-id` chargeback path.
- MS Learn — [Manage Foundry costs](https://learn.microsoft.com/azure/foundry/concepts/manage-costs).
- MS Learn — [Cost Management automation overview](https://learn.microsoft.com/azure/cost-management-billing/automate/automation-overview).
- MS Learn — [Retail Prices REST API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).
- MS Learn — [Cost Management Query Usage REST](https://learn.microsoft.com/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01).

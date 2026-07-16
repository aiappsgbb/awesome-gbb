---
name: citadel-hub-deploy
description: >
  Deploy the **AI Citadel Governance Hub** (Layer 1) — APIM AI Gateway,
  Microsoft Foundry control plane, telemetry, 4 LLM APIs (Azure OpenAI,
  OpenAI Realtime, Universal LLM, Unified AI), private endpoints, access
  contracts. Wraps `Azure-Samples/ai-hub-gateway-solution-accelerator`
  branch `citadel-v1` (azd template) at a pinned commit. Ships 3 profiles
  (pilot-quickstart, enterprise-baseline, vnet-isolated-spoke-aware) plus
  tenant-isolated workflow.
  USE FOR: deploy citadel hub, citadel governance hub, apim ai gateway,
  ai-hub-gateway-solution-accelerator, citadel-v1, llm backend pool, unified
  ai api, universal llm api, openai realtime api, citadel access contract,
  multi-region foundry hub, BYO vnet hub, BYO log analytics, foundry
  network injection, managed redis semantic cache.
  DO NOT USE FOR: connecting a spoke to a hub (use citadel-spoke-
  onboarding), in-process governance (use foundry-agt), single-resource
  Foundry (use foundry-vnet-deploy or microsoft-foundry), tenant isolation
  (use azure-tenant-isolation).
metadata:
  version: "1.1.1"
---

# Citadel Hub Deploy — Layer 1 Governance Hub

> **Status:** Public Preview wrapper around the
> [Azure-Samples / ai-hub-gateway-solution-accelerator] branch
> `citadel-v1` (MIT). The accelerator is the canonical source; this skill
> never forks or vendors its Bicep — it pins to a known-good commit, ships
> 3 curated AZD env profiles, and wires the deployment into the
> awesome-gbb conventions (tenant isolation, MCAPS pilot tagging,
> spoke-aware networking).
>
> **Pinned upstream:** see [`references/upstream-pin.md`](references/upstream-pin.md).
> **Live-validated:** ✅ Resource & shape audit + APIM smoke calls against
> a real `rg-citadel-hub-01` in Sweden Central (May 2026, see
> [`references/live-audit-notes.md`](references/live-audit-notes.md)).

[Azure-Samples / ai-hub-gateway-solution-accelerator]: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1

---

## 1. Why this matters

Most "Foundry pilot" decks stop at "deploy a Foundry account, run an
agent". That works for **one** team and **one** use case. The moment a
second team needs the same model, you hit five hard problems:

1. **Cost attribution.** Whose subscription pays for which call?
2. **Quota fairness.** One team's batch run starves another's chat.
3. **Policy uniformity.** PII redaction, content safety, model
   allow-lists — defined once, enforced everywhere.
4. **Auditability.** Who called what model, when, with which prompt?
5. **Backend abstraction.** Switching a model from PTU → PayAsYouGo
   shouldn't require every spoke to re-deploy.

The Citadel Governance Hub is the AI Apps GBB reference design that
solves all five at the platform level. APIM in front of every model
backend, Cosmos for usage telemetry, Logic App for billing aggregation,
Event Hub for streaming events, and a **per-team Access Contract**
(APIM Product) that gives each spoke its own subscription key, scope,
and policy bundle.

Without this you end up with N spoke projects each negotiating their
own Foundry quota and their own PII policy — and your CISO finds out
on day 91.

```
   ┌──────────────────────────────────────────────────────────┐
   │   Layer 1 — Governance Hub (this skill deploys it)        │
   │                                                           │
   │  ┌────────────┐    ┌──────────┐    ┌──────────────────┐  │
   │  │ APIM v2    │ ←→ │ Cosmos   │ ←→ │ Foundry (×N)     │  │
   │  │ AI Gateway │    │ Usage DB │    │ Multi-region     │  │
   │  └────────────┘    └──────────┘    └──────────────────┘  │
   │       ↑                  ↑                                │
   │       │                  │                                │
   │  ┌────┴───┐   ┌──────────┴────┐                          │
   │  │ Event  │   │ Logic App     │                          │
   │  │ Hub    │   │ Usage         │                          │
   │  └────────┘   │ Aggregation   │                          │
   │               └───────────────┘                          │
   └──────────────────────────────────────────────────────────┘
            ↑                          ↑                ↑
            │ per-team access contract │                │
            │ (APIM Product + sub key) │                │
   ┌────────┴──────┐         ┌─────────┴─────┐  ┌──────┴────┐
   │ Spoke project │         │ Spoke project │  │ Foundry   │
   │  team A       │         │   team B      │  │ Workspace │
   │ (use citadel- │         │ (use citadel- │  │ (use      │
   │  spoke-onbrd) │         │  spoke-onbrd) │  │  spoke…)  │
   └───────────────┘         └───────────────┘  └───────────┘
```

---

## 2. What `citadel-hub-deploy` does (and what it doesn't)

### Does

- Captures the upstream `azd` template at a **pinned SHA** (see
  `references/upstream-pin.md`); never silently rolls forward.
- Wraps the deployment in a **tenant-isolated, assertion-gated** workflow
  (see `azure-tenant-isolation`).
- Ships **3 curated AZD environment profiles** in `references/profiles/`:
  - `pilot-quickstart.env` — Developer SKU, cheapest demo
  - `enterprise-baseline.env` — Standard v2, production-grade, BYO Log Analytics
  - `vnet-isolated-spoke-aware.env` — BYO VNet + DNS, pre-wired for
    `foundry-vnet-deploy` spokes
- Documents the **8 upstream validation notebooks** and the
  recommended execution order.
- Documents the **post-deploy hand-off** to `citadel-spoke-onboarding`
  (per-team access contracts) and `foundry-agt` (in-process governance).

### Doesn't

- **Doesn't fork or vendor** the upstream Bicep. The 55 KB `main.bicep`
  + 3-tier module tree lives at the source repo and is fetched fresh by
  `azd init --template ... --branch citadel-v1` at the pinned SHA.
- **Doesn't onboard spokes.** That's `citadel-spoke-onboarding` — a
  single `az deployment sub create` against
  `bicep/infra/citadel-access-contracts/main.bicep`.
- **Doesn't add in-process governance.** That's `foundry-agt` — runs
  inside the agent process, before/after every tool call.
- **Doesn't manage post-deploy upgrades.** The
  `bicep/infra/apim-gateway-upgrade/` flow (StandardV2 → newer SKUs,
  policy fragment refresh) is upstream-owned.
- **Doesn't onboard LLM backends.** That's the
  `validation/llm-backend-onboarding-runner.ipynb` notebook upstream.

| Want to do this | Use this skill instead |
|---|---|
| Wire your agent project into a deployed hub | `citadel-spoke-onboarding` |
| Add per-tool-call governance inside MAF/Foundry agents | `foundry-agt` |
| Deploy a single-resource Foundry inside a private VNet (no APIM) | `foundry-vnet-deploy` |
| Switch tenants, isolate az/azd config dirs | `azure-tenant-isolation` |
| Apply MCAPS pilot tagging conventions (`SecurityControl: Ignore`, `AZURE_TAGS`) | `azd-patterns` |
| Get App Insights traces from the deployed hub into your spoke | `foundry-observability` |

---

## 3. When NOT to deploy a Citadel Hub

The hub is opinionated: APIM Standard v2 + Foundry control plane + Cosmos
+ Event Hub + Logic App + Redis + 13 Private DNS Zones + 4 NSGs + private
endpoints. That's **~$800-2,500/month baseline cost** in pilot config
(see `guides/citadel-sizing-guide.md` upstream) and 30-45 minutes of
APIM provisioning before the first request can flow.

Don't deploy a hub when:

- **Single-team pilot, single-use-case PoC.** You don't need APIM
  arbitration if there's only one consumer. Use `microsoft-foundry`
  + a direct AOAI/AI Services connection.
- **Dev-time Foundry exploration.** Engineers spinning up sandbox
  Foundry workspaces shouldn't pay for a shared APIM. Use
  `foundry-vnet-deploy` for private networking instead.
- **Budget below $1k/mo.** Even the `pilot-quickstart` profile (Developer
  SKU APIM, no SLA) lands around $200-400/mo with realistic usage, before
  Foundry model burn. If you can't justify that for governance, you
  probably shouldn't be running production agents on any platform.
- **Pure offline / batch workloads.** No runtime to govern → no gateway
  needed. `foundry-evals` + direct backend calls suffice.
- **You're inside a Landing Zone with a pre-existing hub.** Reuse it via
  `citadel-spoke-onboarding`. Don't deploy a parallel hub.

---

## 4. Stakeholder TL;DR

- **Engineer:** "It's `azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator -e <env> --branch citadel-v1` then `azd up`. Profile picks the SKU/network shape. 30-45 min wall clock. Don't forget tenant isolation."
- **Architect:** "Layer 1 of the 4-layer Citadel platform. APIM is the gateway plane; spokes connect via per-team access contracts (Bicep-driven). Pairs with `foundry-agt` for in-process defence in depth. Telemetry sinks: 3 App Insights workspaces + 1 Log Analytics + Cosmos `usage-db`."
- **Compliance:** "PII redaction (Azure AI Language) + Content Safety + JWT-enforceable RBAC + per-team subscription keys with audit trail in Cosmos + private endpoints on every backend service. Documented in `guides/pii-masking-apim.md` and `guides/jwt-client-identity-permissions.md` upstream."
- **Seller:** "One repeatable Bicep deployment that checks the platform-team's first 5 boxes (cost attribution, quota fairness, policy uniformity, audit, backend abstraction) plus the unified-ai-api wildcard route lets you onboard AOAI, Foundry, and Gemini behind one developer-friendly endpoint. Demo runs against the deployed hub via `validation/citadel-universal-llm-api-all-models-tests.ipynb`."

---

## 5. Quickstart

<!-- <HARD-GATE>
  STOP. Before running ANY azd or az command in this section:
  1. You MUST have selected a profile (pilot-quickstart, enterprise-baseline,
     or vnet-isolated-spoke-aware). Do NOT deploy without a profile.
  2. You MUST have set AZURE_CONFIG_DIR and AZD_CONFIG_DIR per
     azure-tenant-isolation. A Citadel hub costs $200-1000+/mo — deploying
     to the wrong subscription is expensive.
  3. You MUST run the tenant assertion (az account show) and verify output.
  If any of these are not done, STOP and complete them first.
</HARD-GATE> -->

> **TENANT ISOLATION FIRST.** Per `azure-tenant-isolation`, set both
> `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` to per-tenant directories
> **before** any `az` / `azd` command. Then run the two-layer assertion
> (`az account show --query tenantId / name`) before `azd up`. Without
> these, you risk deploying a $1k+/mo hub into the wrong subscription.

### Path A — Pilot Quickstart (cheapest demo)

Goal: smallest hub that exercises every API surface. Developer SKU APIM,
public access, all feature flags on, greenfield VNet + Log Analytics.

```bash
# 0. Set the path to your awesome-gbb checkout (or `~/.copilot/skills`
#    user-scope mirror) so the .env profiles below resolve.
SKILL_DIR="$HOME/.copilot/skills/citadel-hub-deploy"  # or your repo path

# 1. Tenant isolation (per azure-tenant-isolation skill)
export AZURE_CONFIG_DIR="$HOME/.azure-tenants/<alias>"
export AZD_CONFIG_DIR="$HOME/.azd-tenants/<alias>"
az login --tenant "$TENANT_ID"
azd auth login --tenant-id "$TENANT_ID"
az account set --subscription "$DEFAULT_SUB"
[ "$(az account show --query name -o tsv)" = "$DEFAULT_SUB" ] || exit 1

# 2. Init template at pinned branch
mkdir my-citadel-hub && cd my-citadel-hub
azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator \
         -e citadel-pilot-01 \
         --branch citadel-v1

# 3. Apply the pilot-quickstart profile (env-var bundle from the skill)
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" == \#* ]] && continue
  azd env set "$k" "$v"
done < "$SKILL_DIR/references/profiles/pilot-quickstart.env"

# 4. Deploy
azd up
```

Expected wall clock: **30-45 min** (APIM provisioning dominates).
Expected baseline cost: ~$200-400/mo with light usage.

### Path B — Enterprise Baseline (production-grade, public APIM)

Goal: Standard v2 APIM, all backend services on private endpoints,
BYO Log Analytics for the central observability landing zone.

```bash
# (Tenant isolation + SKILL_DIR setup as Path A)
mkdir my-citadel-hub && cd my-citadel-hub
azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator \
         -e citadel-prod-01 \
         --branch citadel-v1

# Set BYO Log Analytics first
azd env set USE_EXISTING_LOG_ANALYTICS true
azd env set EXISTING_LOG_ANALYTICS_NAME "log-central-prod"
azd env set EXISTING_LOG_ANALYTICS_RG "rg-observability-prod"
azd env set EXISTING_LOG_ANALYTICS_SUBSCRIPTION_ID "<central-sub-id>"

# Apply the enterprise-baseline profile
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" == \#* ]] && continue
  azd env set "$k" "$v"
done < "$SKILL_DIR/references/profiles/enterprise-baseline.env"

azd up
```

To go fully private (no public APIM access): set
`APIM_V2_PUBLIC_NETWORK_ACCESS=false` after applying the profile.

### Path C — VNet-Isolated, Spoke-Aware (peers to your landing zone)

Goal: Deploy the hub into an existing hub-spoke topology, BYO VNet,
BYO Private DNS Zones (typical landing zone with central DNS), pre-wired
for spokes deployed via `foundry-vnet-deploy`.

```bash
# (Tenant isolation + SKILL_DIR setup as Path A)
# Pre-requisites:
#   - VNet vnet-citadel-hub already exists in rg-network-prod
#     with subnets snet-apim, snet-private-endpoint, snet-functionapp, snet-agents
#   - Private DNS zones already exist in rg-dns-prod (one zone per privatelink.* type)

mkdir my-citadel-hub && cd my-citadel-hub
azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator \
         -e citadel-prod-01 \
         --branch citadel-v1

# Set BYO networking first
azd env set USE_EXISTING_VNET true
azd env set VNET_NAME "vnet-citadel-hub"
azd env set EXISTING_VNET_RG "rg-network-prod"
azd env set EXISTING_DNS_ZONE_OPENAI "/subscriptions/<dns-sub-id>/resourceGroups/rg-dns-prod/providers/Microsoft.Network/privateDnsZones/privatelink.openai.azure.com"
# … repeat EXISTING_DNS_ZONE_* for the other 12 zones — see
# `$SKILL_DIR/references/profiles/vnet-isolated-spoke-aware.env` for the
# full list of EXISTING_DNS_ZONE_* env vars.

# Apply the vnet-isolated-spoke-aware profile
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" == \#* ]] && continue
  azd env set "$k" "$v"
done < "$SKILL_DIR/references/profiles/vnet-isolated-spoke-aware.env"

azd up
```

Then deploy your spoke separately with `foundry-vnet-deploy`, peer the
spoke VNet to the hub VNet, and link the
`privatelink.azure-api.net` zone to the spoke VNet so spoke agents
resolve the hub APIM private FQDN.

### PowerShell equivalent (Windows)

```powershell
# Path to the skill (repo or user-scope mirror)
$skillDir = "$env:USERPROFILE\.copilot\skills\citadel-hub-deploy"

# Tenant isolation (per azure-tenant-isolation skill)
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\<alias>"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\<alias>"
az login --tenant $tenantId
azd auth login --tenant-id $tenantId
az account set --subscription $defaultSub
if ((az account show --query name -o tsv) -ne $defaultSub) { exit 1 }

# Init + apply profile
mkdir my-citadel-hub; cd my-citadel-hub
azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator `
         -e citadel-pilot-01 --branch citadel-v1
Get-Content "$skillDir\references\profiles\pilot-quickstart.env" |
  Where-Object { $_ -and -not $_.StartsWith('#') } |
  ForEach-Object { $k,$v = $_.Split('=',2); azd env set $k $v }
azd up
```

---

## 6. Pre-flight checklist

See [`references/customer-checklist.md`](references/customer-checklist.md)
for the full pre-flight (tenant verified, providers registered, quota
requested, RBAC, networking decision, DNS ownership). The TL;DR:

- [ ] Tenant + subscription confirmed via two-layer assertion
- [ ] Resource providers registered: `Microsoft.ApiManagement`,
      `Microsoft.CognitiveServices`, `Microsoft.DocumentDB`,
      `Microsoft.EventHub`, `Microsoft.Insights`, `Microsoft.Logic`
- [ ] Quota: APIM Standard v2 (1+ unit), Foundry GlobalStandard tokens
      for each model in your `aiFoundryModelsConfig`, Cosmos RU/s
- [ ] RBAC: deployer is **Owner** or has **Contributor** + **User Access
      Administrator** on the target sub (role assignments are part of
      the deploy)
- [ ] Networking decision made (greenfield vs BYO VNet vs BYO DNS)
- [ ] If BYO Log Analytics: workspace ID + cross-sub RBAC granted
- [ ] If `entraAuth=true` later: app registration ready (use
      `bicep/infra/entra-id-setup/setup.ps1` upstream — outside v1.0.0
      of this skill)

---

## 7. Post-deploy verification

The upstream ships **8 validation notebooks** under `validation/`. The
recommended baseline (run all 4 on every new deployment):

| # | Notebook | What it validates | ⭐ Baseline? |
|---|----------|-------------------|------------|
| 1 | `llm-backend-onboarding-runner.ipynb` | Register AI backends + deploy routing logic into APIM | ⭐ |
| 2 | `citadel-universal-llm-api-all-models-tests.ipynb` | Validate every gateway-configured model through `/models` | ⭐ |
| 3 | `citadel-access-contracts-tests.ipynb` | Per-team access contracts with KV + Foundry connection | ⭐ |
| 4 | `citadel-agent-frameworks-tests.ipynb` | MAF + Foundry SDK + LangChain consumption | ⭐ |
| 5 | `citadel-model-aliases-tests.ipynb` | `resolve-model-alias` policy fragment (priority + weighted) | scenario |
| 6 | `citadel-pii-processing-tests.ipynb` | PII anonymize/deanonymize/block | scenario |
| 7 | `citadel-unified-ai-api-tests.ipynb` | Multi-provider routing through unified-ai wildcard API | scenario |
| 8 | `citadel-jwt-authentication-tests.ipynb` | JWT enforcement + RBAC across endpoints | scenario |

Each notebook auto-loads from your `azd` env via the
`init_from_azd = True` toggle in cell 0:

```python
init_from_azd = True   # auto-pulls AZURE_RESOURCE_GROUP, AZURE_LOCATION, …
                       # from `azd env get-values` of the active env
```

Manually-set values (anything not equal to the `"REPLACE"` sentinel) win
over azd values. See `validation/README.md` upstream for the per-notebook
azd env-var map.

### Quick smoke (no Jupyter)

If you don't have a Python venv handy, this curl (or `Invoke-RestMethod`)
proves the gateway works:

```bash
# Get APIM gateway URL
GW=$(az apim show -g <rg> -n <apim> --query gatewayUrl -o tsv)

# Get the master subscription key (DEMO ONLY — don't use master in prod;
# create a per-team Access Contract via citadel-spoke-onboarding instead)
KEY=$(az rest --method post \
  --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/<rg>/providers/Microsoft.ApiManagement/service/<apim>/subscriptions/master/listSecrets?api-version=2022-08-01" \
  --query primaryKey -o tsv)

# Discover models
curl -s "$GW/models/models" -H "api-key: $KEY" | jq '.value[].name'

# Send one chat completion (NOTE: api-key header, NOT Ocp-Apim-Subscription-Key)
curl -s -X POST "$GW/openai/deployments/gpt-5.4-mini/chat/completions?api-version=2024-12-01-preview" \
  -H "api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"ping"}],"max_completion_tokens":10}'
```

Live-tested round-trip latency from this skill's audit run (Sweden
Central, gpt-5.4-mini, warm): **~1 sec end-to-end** through APIM.
Discovery `/models` call: **~250 ms warm**. See
`references/live-audit-notes.md` for the full numbers + gotchas.

---

## 8. Hand-off to `citadel-spoke-onboarding`

After the hub is deployed, every spoke project needs:

1. An **APIM Product** (the access contract, e.g.,
   `LLM-Healthcare-PatientAssistant-DEV`) — created via
   `bicep/infra/citadel-access-contracts/main.bicep`.
2. An **APIM Subscription** scoped to that product (auto-created by the
   contract Bicep, named `<product>-SUB-01`).
3. **Optional Key Vault secrets** (endpoint + API key stored in central
   KV — recommended for managed-identity-only spokes).
4. **Optional Foundry connection** (the contract Bicep can create an
   APIM connection in a target Foundry project, so agents can
   `client.connections.get(...)` their gateway).

Naming: `{serviceCode}-{businessUnit}-{useCase}-{environment}`
(e.g., `LLM-Healthcare-PatientAssistant-DEV`). One product per spoke,
one subscription per product, optional KV secret per subscription.

**Use the `citadel-spoke-onboarding` skill** for the per-spoke wiring;
it documents the contract `.bicepparam`, the optional policy XML, and
the Foundry-side connection fetch. The hub deploy intentionally
provisions ZERO access contracts at install time (the upstream sample
in our audit hub deployed `LLM-RnD-BATScraper-DEV` post-install via
exactly this mechanism).

---

## 9. The 4-layer Citadel Platform

The Governance Hub is **Layer 1**. The full platform is documented in
the [Citadel Platform overview](https://aka.ms/foundry-citadel) but
the relevant mapping for this catalog is:

| Layer | Concern | Skill in this catalog |
|-------|---------|-----------------------|
| **L1** Governance Hub (infra) | Gateway, APIs, policies, telemetry | **`citadel-hub-deploy`** ← *you are here* |
| **L1** Governance Hub (wiring) | Per-team access contracts, JWT, KV secrets | `citadel-spoke-onboarding` |
| **L1.5** In-process governance | OWASP ASI 2026 deterministic safety inside agent runtime | `foundry-agt` |
| **L2** AI Control Plane | Foundry control plane + project lifecycle | (no skill yet — Foundry portal + APIs) |
| **L3** Agent Identity | Entra agent identities + delegated permissions | (no skill yet — Entra Agent ID GA path) |
| **L4** Security Fabric | Defender for Cloud, Purview, Entra Conditional Access | (no skill yet — Microsoft security stack) |

Defence in depth is the principle: gateway-side governance (L1) plus
in-process governance (L1.5) catches a class of attacks neither alone
can stop. See `foundry-agt`'s "Why this matters" for the
26.67% (prompt-only) vs 0.00% (deterministic) red-team stat.

---

## 10. Cross-skill composition

| Skill | Compose how |
|-------|-------------|
| `azure-tenant-isolation` | **Mandatory.** Per-tenant `AZURE_CONFIG_DIR` + `AZD_CONFIG_DIR` + two-layer assertion before `azd up`. The hub is too expensive to deploy to the wrong sub. |
| `azd-patterns` | Apply MCAPS pilot tagging (`SecurityControl: Ignore` is already in upstream `bicepparam`; layer `AZURE_TAGS` env-var per `azd-patterns` for cost-allocation tags). |
| `foundry-vnet-deploy` | Pair for spoke-side VNet bring-up. Path C above is pre-wired for this. The spoke VNet peers to the hub VNet; `apim-dns-zone-link.bicep` from `foundry-vnet-deploy` links `privatelink.azure-api.net` into the spoke. |
| `citadel-spoke-onboarding` | The **post-deploy** sibling. Hub deploys infra; spoke-onboarding creates per-team Access Contracts on top. |
| `foundry-agt` | The **in-process** sibling. Hub governs at the gateway; AGT governs inside the agent process. **Use both.** |
| `foundry-observability` | The hub deploys its own 3× Application Insights (apim, foundry, func). For spoke agent traces to flow into the hub's central observability story, follow `foundry-observability`'s 3-layer pattern (Bicep + AppIn account-level connection + `configure_azure_monitor()`). |
| `foundry-cross-resource` | If a spoke needs to call models in a Foundry project that lives in a *different* Foundry account from the hub's Foundry pool, the cross-resource pattern (connectionName/deploymentName) routes through APIM transparently. |

---

## 11. Known issues (from live audit)

Captured during the audit pass on `rg-citadel-hub-01` (Sweden Central,
first observed at upstream pin `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`;
still applicable at the current pin `08294f09a70833e282776a07fe7f97a6aead55b1`):

1. **Newer GPT-5.4 models reject `max_tokens`.** A vanilla
   `chat/completions` POST with `max_tokens` returns HTTP 400 with
   `"Use 'max_completion_tokens' instead"`. The APIM passes the request
   straight through; the rejection is from the model. Update any client
   code accordingly. *Tested 2026-05.*
2. **APIM subscription header is `api-key`, not
   `Ocp-Apim-Subscription-Key`.** The 4 LLM APIs override the default
   subscription-key header to match Azure OpenAI conventions. Look at
   `properties.subscriptionKeyParameterNames.header` on each API to
   confirm.
3. **Bicep build emits BCP318 warnings** ("module | null may be null at
   start of deployment"). These are linter advisories, not deployment
   blockers — the conditional module pattern is intentional in
   `main.bicep` (`useExistingLogAnalytics`, `useExistingVnet`,
   `enableManagedRedis`, etc.).
4. **Sub-level deploy can fail twice before succeeding** on first run
   (RBAC propagation, Cognitive Services capacity warm-up, APIM
   provisioning timing). Re-run `azd up` — `azd` is idempotent. The
   audit hub showed 2 failed sub-level deploys before 2 successful ones.
5. **`azd env list` outside an azd project dir errors with `no project
   exists`.** Sync sessions in agent shells lose `cd <project>`; always
   re-establish working directory. The notebook `init_from_azd = True`
   path needs the active `azd` env to be discoverable from cwd.
6. **APIM default region for the audit hub was `swedencentral`** —
   Standard v2 has [limited region availability]; check
   `az apim list-skus` for your target region before locking the profile.
7. **`SecurityControl: Ignore` tag is already in the upstream
   `bicepparam`** — no need to override unless you're targeting a
   non-MCAPS sub where Defender for Cloud auto-remediation isn't an
   issue.
8. **First-time bicep build is slow on Windows.** A 6 MB ARM JSON
   compile from `main.bicep` (55 KB) takes ~2-5 min cold. Use
   `--outfile` not `--stdout` (large stdout buffers stall PowerShell).

[limited region availability]: https://learn.microsoft.com/azure/api-management/v2-service-tiers-overview#region-availability

---

## 12. References

- [`references/upstream-pin.md`](references/upstream-pin.md) — pinned
  commit SHA, branch, version, verified API surface, full known issues.
- [`references/customer-checklist.md`](references/customer-checklist.md)
  — pre-flight (providers, quota, RBAC, networking, DNS ownership).
- [`references/live-audit-notes.md`](references/live-audit-notes.md) —
  live audit data captured against `rg-citadel-hub-01` in Sweden Central.
- [`references/profiles/pilot-quickstart.env`](references/profiles/pilot-quickstart.env)
  — Developer SKU, public, all features on (cheapest demo).
- [`references/profiles/enterprise-baseline.env`](references/profiles/enterprise-baseline.env)
  — Standard v2, private endpoints, BYO Log Analytics.
- [`references/profiles/vnet-isolated-spoke-aware.env`](references/profiles/vnet-isolated-spoke-aware.env)
  — BYO VNet + DNS, pre-wired for `foundry-vnet-deploy` spokes.

### Upstream

- [Repo (citadel-v1 branch)](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1)
- [aka.ms shortlink](https://aka.ms/ai-hub-gateway)
- [Citadel Platform overview](https://aka.ms/foundry-citadel)
- [Architecture diagram](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/assets/citadel-governance-hub-v1.png)
- [Quick Deployment Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/quick-deployment-guide.md)
- [Full Deployment Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/full-deployment-guide.md)
- [Citadel Sizing Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/citadel-sizing-guide.md)
- [PTU Estimation Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/put-estimation-guide.md)
- [Network Approach Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/network-approach.md)
- [LLM Routing Architecture](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/llm-routing-architecture.md)
- [PII Masking via APIM](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/pii-masking-apim.md)
- [JWT Client Identity & Permissions](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/jwt-client-identity-permissions.md)
- [Agent Governance Toolkit Integration](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/agent-governance-toolkit-integration.md)
  — pairs the hub with `foundry-agt` (this catalog)
- [Validation Notebooks Index](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/README.md)
- [Citadel Access Contracts Bicep README](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/README.md)

---

## 13. Changelog

- **1.1.1** (2026-07) — Re-pin upstream `f2702b49` (PR #117) →
  `08294f09a70833e282776a07fe7f97a6aead55b1` (PR #133), 48 commits. Offline
  `az bicep build` at the new SHA passes (exit 0, ~4.6 MB ARM JSON,
  warnings-only). Env-var surface diff shows exactly one change:
  `FOUNDRY_NETWORK_INJECTION_ENABLED` removed upstream — now dropped from all
  3 profiles. Audit notes updated: API Center is now live on
  `rg-citadel-hub-01` (`apic-codfa4k4hph2q`, Free). Full `azd up` re-audit at
  the new pin is still pending (skill is `issue_only` / not-CI-runnable) —
  see `references/upstream-pin.md`.
- **1.1.0** (2026-05) — Adopt superpowers patterns: description audit,
  verification gates, escalation rules (multi-skill rewrite, #78).
- **1.0.1** (2026-05) — Fix: profile `.env` path in Quickstart paths now
  references `$SKILL_DIR` (the awesome-gbb skill dir) rather than the
  azd project dir (which doesn't have it). Add `az login` before
  `az account set` in Quickstart (per `azure-tenant-isolation` rule 4).
  Audit notes correct an env-var naming mix-up
  (`enableAIGatewayPiiRedaction` is the bicep param; the env var is
  `ENABLE_PII_REDACTION` — profiles were already correct, only the
  audit notes had the wrong name). Customer-checklist clarifies the
  upstream default model list (gpt-5.4 is NOT in default config).
- **1.0.0** (2026-05) — Initial release. Pinned upstream
  `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`. 3 curated profiles
  (pilot-quickstart, enterprise-baseline, vnet-isolated-spoke-aware).
  Live-validated against `rg-citadel-hub-01` in Sweden Central:
  resource & shape audit + APIM smoke calls (`/models` discovery 250 ms
  warm, `gpt-5.4-mini` chat ~1 sec warm round-trip). Cross-skill
  composition wired to azure-tenant-isolation, azd-patterns,
  foundry-vnet-deploy, citadel-spoke-onboarding, foundry-agt,
  foundry-observability.

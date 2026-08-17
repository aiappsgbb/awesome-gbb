---
name: citadel-hub-deploy
description: >
  Deploy the **AI Citadel Governance Hub** (Layer 1) — APIM AI Gateway,
  Microsoft Foundry control plane, telemetry, 4 LLM APIs (Azure OpenAI,
  OpenAI Realtime, Universal LLM, Unified AI), private endpoints, access
  contracts. Wraps `Azure-Samples/ai-hub-gateway-solution-accelerator`
  branch `citadel-v1` (azd template) at a pinned commit. Ships 3 profiles
  (pilot-quickstart, enterprise-baseline, vnet-isolated-spoke-aware) plus
  tenant isolation.
  USE FOR: deploy citadel hub, citadel governance hub, apim ai gateway,
  ai-hub-gateway-solution-accelerator, citadel-v1, llm backend pool, unified
  ai api, universal llm api, openai realtime api, citadel access contract,
  multi-region foundry hub, BYO vnet hub, BYO log analytics, foundry
  private Foundry networking, managed redis semantic cache.
  DO NOT USE FOR: connecting a spoke to a hub (use citadel-spoke-
  onboarding), in-process governance (use foundry-agt), single-resource
  Foundry (use foundry-vnet-deploy or microsoft-foundry), tenant isolation
  (use azure-tenant-isolation).
metadata:
  version: "1.1.2"
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
> **Pinned upstream:** `63f0f812474e713916dc909494d655246783a1d9`;
> see [`references/upstream-pin.md`](references/upstream-pin.md).
> **Validation boundary:** the current pin is build-validated only (exact
> checkout + `main.bicep` + `main.bicepparam`). The resource audit and APIM
> smoke calls in [`references/live-audit-notes.md`](references/live-audit-notes.md)
> are historical evidence from the prior pin
> `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`, not live evidence for the
> current pin.

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
  - `pilot-quickstart.env` — Developer SKU, lean optional-service overlay
  - `enterprise-baseline.env` — Standard v2, production-grade, BYO Log Analytics
  - `vnet-isolated-spoke-aware.env` — BYO VNet + DNS, pre-wired for
    `foundry-vnet-deploy` spokes
- Documents the current **12-scenario upstream validation sequence** and
  the four-notebook strongly recommended baseline.
- Documents the **post-deploy hand-off** to `citadel-spoke-onboarding`
  (per-team access contracts) and `foundry-agt` (in-process governance).

### Doesn't

- **Doesn't fork or vendor** the upstream Bicep. The deployment uses a
  detached Git checkout at the exact pinned SHA. `azd init` cannot pin a
  commit when given `--branch`, so branch-based initialization is forbidden.
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

The hub is opinionated: APIM + Foundry control plane + Cosmos + Event Hub +
Logic App + private networking, with Redis and API Center optional by profile.
That's **~$800-2,500/month baseline cost** in enterprise config
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

- **Engineer:** "Clone upstream, detach and verify the pinned SHA, select a
  profile, then run `azd up` from that checkout. Profile picks the SKU/network
  shape. 30-45 min wall clock. Don't forget tenant isolation."
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
  3. You MUST assert the exact tenant GUID and subscription GUID immediately
     before every deploy or mutating post-deploy command.
  If any of these are not done, STOP and complete them first.
</HARD-GATE> -->

> **TENANT ISOLATION FIRST.** Per `azure-tenant-isolation`, set both
> `AZURE_CONFIG_DIR` and `AZD_CONFIG_DIR` to per-tenant directories
> **before** any `az` / `azd` command. Then run the two-layer assertion
> (`az account show --query tenantId / id`, plus the selected azd environment)
> immediately before every `azd up`, `setup.ps1`, rollback, or destructive
> Azure operation. Display names are not identity checks. Without
> these, you risk deploying a $1k+/mo hub into the wrong subscription.

### Path A — Pilot Quickstart (lean non-production overlay)

Goal: lean non-production hub. Developer SKU APIM is public; data-plane
backends stay private. Redis, API Center, Search, Document Intelligence,
dashboards, and Foundry network injection are disabled. Keep the upstream
default `foundryNetworkInjectionEnabled=false`; enabling it without the full
BYO Standard Agent dependency set fails.

```bash
set -euo pipefail

# 0. Set the path to your awesome-gbb checkout (or `~/.copilot/skills`
#    user-scope mirror) so the .env profiles below resolve.
SKILL_DIR="$HOME/.copilot/skills/citadel-hub-deploy"  # or your repo path

# 1. Tenant isolation with immutable GUID expectations
export AZURE_CONFIG_DIR="$HOME/.azure-tenants/<alias>"
export AZD_CONFIG_DIR="$HOME/.azd-tenants/<alias>"
EXPECTED_TENANT_ID="<tenant-guid>"
EXPECTED_SUBSCRIPTION_ID="<subscription-guid>"

assert_azure_target() {
  local actual_tenant actual_subscription azd_tenant azd_subscription
  actual_tenant="$(az account show --query tenantId -o tsv)"
  actual_subscription="$(az account show --query id -o tsv)"
  azd_tenant="$(azd env get-value AZURE_TENANT_ID)"
  azd_subscription="$(azd env get-value AZURE_SUBSCRIPTION_ID)"
  [[ "$actual_tenant" == "$EXPECTED_TENANT_ID" ]] ||
    { echo "Azure CLI tenant mismatch" >&2; return 1; }
  [[ "$actual_subscription" == "$EXPECTED_SUBSCRIPTION_ID" ]] ||
    { echo "Azure CLI subscription mismatch" >&2; return 1; }
  [[ "$azd_tenant" == "$EXPECTED_TENANT_ID" ]] ||
    { echo "azd tenant mismatch" >&2; return 1; }
  [[ "$azd_subscription" == "$EXPECTED_SUBSCRIPTION_ID" ]] ||
    { echo "azd subscription mismatch" >&2; return 1; }
}

az login --tenant "$EXPECTED_TENANT_ID"
azd auth login --tenant-id "$EXPECTED_TENANT_ID"
az account set --subscription "$EXPECTED_SUBSCRIPTION_ID"

# 2. Materialize and verify the exact pin. Do not replace this with
#    branch-based azd init: citadel-v1 is mutable.
PINNED_SHA="63f0f812474e713916dc909494d655246783a1d9"
git clone --filter=blob:none --no-checkout \
  https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator \
  my-citadel-hub
git -C my-citadel-hub fetch --depth 1 origin "$PINNED_SHA"
(cd my-citadel-hub && git checkout --detach "$PINNED_SHA")
test "$(git -C my-citadel-hub rev-parse HEAD)" = "$PINNED_SHA" || exit 1
cd my-citadel-hub
azd env new citadel-pilot-01
azd env set AZURE_TENANT_ID "$EXPECTED_TENANT_ID"
azd env set AZURE_SUBSCRIPTION_ID "$EXPECTED_SUBSCRIPTION_ID"

# 3. Apply the pilot-quickstart profile (env-var bundle from the skill)
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" == \#* ]] && continue
  azd env set "$k" "$v"
done < "$SKILL_DIR/references/profiles/pilot-quickstart.env"

# 4. Review the structured aiFoundryInstances and aiFoundryModelsConfig
#    arrays in bicep/infra/main.bicepparam. ENV profiles cannot safely
#    override arrays. Reduce them directly if quota or model scope requires.

# 5. Deploy
assert_azure_target
azd up
```

Expected wall clock: **30-45 min** (APIM provisioning dominates).
Expected baseline cost: ~$200-400/mo with light usage.
Complete the common Entra step below after the deployment.

### Path B — Enterprise Baseline (production-grade, public APIM)

Goal: Standard v2 APIM, all backend services on private endpoints,
BYO Log Analytics for the central observability landing zone.

```bash
# Repeat Path A steps 0-2 with env name citadel-prod-01. You must be inside
# the verified detached checkout before continuing.

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

assert_azure_target
azd up
```

To make APIM ingress private-only: set
`APIM_V2_PUBLIC_NETWORK_ACCESS=false` after applying the profile.
Event Hub public access must still remain `Enabled` for APIM v2 provisioning.

### Path C — VNet-Isolated, Spoke-Aware (peers to your landing zone)

Goal: Deploy the hub into an existing hub-spoke topology, BYO VNet,
BYO Private DNS Zones (typical landing zone with central DNS), pre-wired
for spokes deployed via `foundry-vnet-deploy`.

```bash
# Repeat Path A steps 0-2 with env name citadel-prod-01.
# Pre-requisites:
#   - VNet vnet-citadel-hub already exists in rg-network-prod
#     with subnets snet-apim, snet-private-endpoint, snet-functionapp
#   - Private DNS zones already exist in rg-dns-prod (one zone per privatelink.* type)

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

assert_azure_target
azd up
```

Then deploy your spoke separately with `foundry-vnet-deploy`, peer the
spoke VNet to the hub VNet, and link the
`privatelink.azure-api.net` zone to the spoke VNet so spoke agents
resolve the hub APIM private FQDN.

### Required Entra setup for all profiles

All profiles enable Entra JWT policy, but all also keep Key Vault public
network access disabled. Run the pinned
`bicep/infra/entra-id-setup/setup.ps1` only after `azd up`, from an
administrative host that uses the same isolated az/azd environment and has
private DNS plus network reachability to the Key Vault private endpoint
(for example, a workstation connected by the approved VPN or a peered
management host). Do not weaken the profile automatically just to run the
script.

The signed-in operator needs:

- Microsoft Graph `Application.ReadWrite.All` permission or the Entra
  **Application Developer** role to create/update the app registration,
  service principal, and two-year client secret.
- **Key Vault Secrets Officer** on the deployed vault data plane.
- **API Management Service Contributor** on the deployed APIM service (or
  its resource group) to read/create/update JWT named values.

The script then creates or reuses the app registration, creates the service
principal, resets the client secret, writes it as
`ENTRA-APP-CLIENT-SECRET`, updates four APIM named values, and stores values
in the selected azd environment. It configures APIM directly; a second
`azd up` is not required. The pinned `setup.ps1` continues on a Key Vault
secret-write failure, so its final success banner is not sufficient: treat
a missing Key Vault secret as a failed setup and verify both data planes.

```bash
# Run from the exact detached checkout and selected azd environment on the
# network-connected administrative host described above. First repeat Path A
# step 1 on that host so EXPECTED_* and assert_azure_target are defined.
set -euo pipefail
cd bicep/infra/entra-id-setup
assert_azure_target || exit 1
pwsh ./setup.ps1

KEY_VAULT_NAME="$(azd env get-value KEY_VAULT_NAME)"
APIM_RESOURCE_GROUP="$(azd env get-value AZURE_RESOURCE_GROUP)"
APIM_NAME="$(azd env get-value APIM_NAME)"
EXPECTED_CLIENT_ID="$(azd env get-value AZURE_CLIENT_ID)"
EXPECTED_CLIENT_SECRET="$(azd env get-value ENTRA_CLIENT_SECRET)"
ACTUAL_CLIENT_SECRET="$(az keyvault secret show \
  --vault-name "$KEY_VAULT_NAME" \
  --name ENTRA-APP-CLIENT-SECRET \
  --query value -o tsv)"
[[ -n "$EXPECTED_CLIENT_SECRET" &&
   "$ACTUAL_CLIENT_SECRET" == "$EXPECTED_CLIENT_SECRET" ]] ||
  { echo "Key Vault ENTRA_CLIENT_SECRET mismatch" >&2; exit 1; }
unset EXPECTED_CLIENT_SECRET ACTUAL_CLIENT_SECRET

verify_apim_named_value() {
  local named_value="$1"
  local expected_value="$2"
  local actual_value
  actual_value="$(az apim nv show \
    --resource-group "$APIM_RESOURCE_GROUP" \
    --service-name "$APIM_NAME" \
    --named-value-id "$named_value" \
    --query value -o tsv)"
  [[ "$actual_value" == "$expected_value" ]] ||
    { echo "APIM named value mismatch: $named_value" >&2; exit 1; }
}
verify_apim_named_value JWT-TenantId "$EXPECTED_TENANT_ID"
verify_apim_named_value JWT-AppRegistrationId "$EXPECTED_CLIENT_ID"
verify_apim_named_value JWT-Issuer \
  "https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0"
verify_apim_named_value JWT-OpenIdConfigUrl \
  "https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0/.well-known/openid-configuration"
```

### PowerShell equivalent (Windows)

```powershell
$ErrorActionPreference = "Stop"

# Path to the skill (repo or user-scope mirror)
$skillDir = "$env:USERPROFILE\.copilot\skills\citadel-hub-deploy"

# Tenant isolation (per azure-tenant-isolation skill)
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\<alias>"
$env:AZD_CONFIG_DIR   = "$env:USERPROFILE\.azd-tenants\<alias>"
$expectedTenantId = "<tenant-guid>"
$expectedSubscriptionId = "<subscription-guid>"

function Assert-NativeSuccess {
  param([string]$Operation)
  if ($LASTEXITCODE -ne 0) {
    throw "$Operation failed with native exit code $LASTEXITCODE"
  }
}

function Assert-AzureTarget {
  $accountJson = az account show --output json
  Assert-NativeSuccess "az account show"
  $account = $accountJson | ConvertFrom-Json
  $azdTenantId = azd env get-value AZURE_TENANT_ID
  Assert-NativeSuccess "azd tenant lookup"
  $azdTenantId = $azdTenantId.Trim()
  $azdSubscriptionId = azd env get-value AZURE_SUBSCRIPTION_ID
  Assert-NativeSuccess "azd subscription lookup"
  $azdSubscriptionId = $azdSubscriptionId.Trim()
  if ($account.tenantId -ne $expectedTenantId) {
    throw "Azure CLI tenant mismatch"
  }
  if ($account.id -ne $expectedSubscriptionId) {
    throw "Azure CLI subscription mismatch"
  }
  if ($azdTenantId -ne $expectedTenantId) {
    throw "azd tenant mismatch"
  }
  if ($azdSubscriptionId -ne $expectedSubscriptionId) {
    throw "azd subscription mismatch"
  }
}

az login --tenant $expectedTenantId
Assert-NativeSuccess "az login"
azd auth login --tenant-id $expectedTenantId
Assert-NativeSuccess "azd auth login"
az account set --subscription $expectedSubscriptionId
Assert-NativeSuccess "az account set"

# Exact detached checkout + profile
$pinnedSha = "63f0f812474e713916dc909494d655246783a1d9"
git clone --filter=blob:none --no-checkout `
  https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator `
  my-citadel-hub
Assert-NativeSuccess "git clone"
git -C my-citadel-hub fetch --depth 1 origin $pinnedSha
Assert-NativeSuccess "git fetch"
git -C my-citadel-hub checkout --detach $pinnedSha
Assert-NativeSuccess "git checkout"
$currentSha = git -C my-citadel-hub rev-parse HEAD
Assert-NativeSuccess "git rev-parse"
if ($currentSha -ne $pinnedSha) { throw "Detached checkout SHA mismatch" }
Set-Location my-citadel-hub
azd env new citadel-pilot-01
Assert-NativeSuccess "azd env new"
azd env set AZURE_TENANT_ID $expectedTenantId
Assert-NativeSuccess "azd tenant assignment"
azd env set AZURE_SUBSCRIPTION_ID $expectedSubscriptionId
Assert-NativeSuccess "azd subscription assignment"
$profilePath = Join-Path $skillDir "references\profiles\pilot-quickstart.env"
if (-not (Test-Path -LiteralPath $profilePath -PathType Leaf)) {
  throw "Citadel profile not found: $profilePath"
}
Get-Content -LiteralPath $profilePath -ErrorAction Stop |
  Where-Object { $_ -and -not $_.StartsWith('#') } |
  ForEach-Object {
    $k,$v = $_.Split('=',2)
    azd env set $k $v
    Assert-NativeSuccess "profile value $k"
  }
Assert-AzureTarget
azd up
Assert-NativeSuccess "azd up"

# Run only from a host with private DNS/network reachability to the deployed
# Key Vault and the Graph, Key Vault, and APIM permissions listed above.
Set-Location bicep\infra\entra-id-setup
Assert-AzureTarget
pwsh .\setup.ps1
Assert-NativeSuccess "Entra setup"

$keyVaultName = azd env get-value KEY_VAULT_NAME
Assert-NativeSuccess "Key Vault name lookup"
$apimResourceGroup = azd env get-value AZURE_RESOURCE_GROUP
Assert-NativeSuccess "APIM resource group lookup"
$apimName = azd env get-value APIM_NAME
Assert-NativeSuccess "APIM name lookup"
$expectedClientId = azd env get-value AZURE_CLIENT_ID
Assert-NativeSuccess "Entra client ID lookup"
$expectedClientSecret = azd env get-value ENTRA_CLIENT_SECRET
Assert-NativeSuccess "Entra client secret lookup"
$actualClientSecret = az keyvault secret show `
  --vault-name $keyVaultName `
  --name ENTRA-APP-CLIENT-SECRET `
  --query value -o tsv
Assert-NativeSuccess "Key Vault client secret lookup"
if (-not $expectedClientSecret -or
    $actualClientSecret -ne $expectedClientSecret) {
  throw "Key Vault ENTRA_CLIENT_SECRET mismatch"
}
Remove-Variable expectedClientSecret, actualClientSecret

$expectedNamedValues = @{
  "JWT-TenantId" = $expectedTenantId
  "JWT-AppRegistrationId" = $expectedClientId
  "JWT-Issuer" = "https://login.microsoftonline.com/$expectedTenantId/v2.0"
  "JWT-OpenIdConfigUrl" = "https://login.microsoftonline.com/$expectedTenantId/v2.0/.well-known/openid-configuration"
}
foreach ($namedValue in $expectedNamedValues.Keys) {
  $actualValue = az apim nv show `
    --resource-group $apimResourceGroup `
    --service-name $apimName `
    --named-value-id $namedValue `
    --query value -o tsv
  Assert-NativeSuccess "APIM named value lookup: $namedValue"
  if ($actualValue -ne $expectedNamedValues[$namedValue]) {
    throw "APIM named value mismatch: $namedValue"
  }
}
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
- [ ] APIM v2 profiles keep `EVENTHUB_NETWORK_ACCESS=Enabled` during
      provisioning: Event Hub remains `Enabled` during APIM v2 provisioning,
      as required by the pinned `main.bicep`
- [ ] Networking decision made (greenfield vs BYO VNet vs BYO DNS)
- [ ] If BYO Log Analytics: workspace ID + cross-sub RBAC granted
- [ ] Foundry network injection remains disabled unless the full BYO Standard
      Agent dependency set is supplied outside this accelerator
- [ ] Entra operator has Graph `Application.ReadWrite.All` or Application
      Developer, Key Vault Secrets Officer, API Management Service
      Contributor, and private network reachability to the vault
- [ ] Post-deploy `bicep/infra/entra-id-setup/setup.ps1` execution and
      explicit Key Vault/APIM verification agreed

---

## 7. Post-deploy verification

The upstream ships **13 notebooks** under `validation/` and documents a
**12-scenario recommended sequence**. Run the first four as the strongly
recommended baseline on every new deployment:

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
| 9 | `llm-backend-onboarding-extended-providers-runner.ipynb` | AWS, Gemini, and Anthropic backend onboarding | scenario |
| 10 | `citadel-session-affinity-tests.ipynb` | Sticky routing for stateful Responses API sessions | scenario |
| 11 | `citadel-alerting-tests.ipynb` | Throttling/quota metrics and Azure Monitor alerts | scenario |
| 12 | `citadel-publish-contract-tests.ipynb` | API-to-MCP, remote MCP, and A2A publication contracts | scenario |

`citadel-image-models-tests.ipynb` is an additional image-model notebook not
listed in the numbered 12-scenario sequence. Run it when image deployments are
kept in `aiFoundryModelsConfig`.

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

Historical old-pin round-trip latency from this skill's May 2026 audit
(Sweden Central, gpt-5.4-mini, warm): **~1 sec end-to-end** through APIM.
Discovery `/models` call: **~250 ms warm**. See
`references/live-audit-notes.md` for the evidence boundary and full numbers.

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

Defence in depth is the principle: APIM governs edge authentication,
rate limiting, and product policy (L1), while
[`foundry-agt`](../foundry-agt/SKILL.md#why-action-governance-matters)
provides in-process action governance (L1.5). As documented in
**Why action governance matters**, AGT makes deterministic allow/deny
decisions by tool name before the tool body (`call_next()`) executes;
argument validation remains the caller's or tool body's responsibility.

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

## 11. Known issues and current-pin contract notes

Current-pin source/build findings:

- **The upstream branch is mutable.** `azd init` with a branch cannot
  materialize an immutable commit. Use the detached checkout flow in § 5 and
  verify `git rev-parse HEAD` before any Azure operation.
- **Foundry network injection defaults to false.** Enabling it without the
  complete BYO Standard Agent dependency set is an upstream-documented
  deployment failure. The removed env setting is not consumed by the current
  `main.bicepparam`; all profiles leave it disabled.
- **Redis HA is explicit.** Profiles that enable Redis set
  `REDIS_HIGH_AVAILABILITY=Enabled`; the Redis-disabled pilot sets `Disabled`.

The following observations were captured during the historical audit pass on
`rg-citadel-hub-01` (Sweden Central), at old pin
`f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`:

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
  — Developer SKU; public APIM, private backends, fixed-cost optional services
  off.
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

- **1.1.1** (2026-08) — Re-pin upstream to
  `63f0f812474e713916dc909494d655246783a1d9`; replace mutable branch-based
  initialization with an exact detached checkout; update all profiles for the
  current env contract, safe network-injection default, Redis HA, and Entra
  setup; refresh model/notebook guidance; clearly separate current build-only
  validation from historical live evidence at the old pin.
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

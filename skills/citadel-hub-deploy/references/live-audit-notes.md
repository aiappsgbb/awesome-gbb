# Live audit notes — current-pin core validation + historical evidence

Captured during the v1.0.0 authoring pass against a real deployed hub in
`rg-citadel-hub-01` (Sweden Central, May 2026). Subscription: a sandbox
MCAPS sub (name redacted). The live evidence in this file belongs to commit
`f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`.

This file is **shipped with the skill as record** so future contributors
can re-validate the same checks against a different deployed hub
(or re-pin upstream).

> **Evidence boundary:** the skill now pins
> `63f0f812474e713916dc909494d655246783a1d9`. The section immediately below
> records its 2026-08-19 lean deployment and core gateway smoke. Later
> resource counts, latency numbers, and notebook observations remain
> historical evidence from the old live commit.

## Current pin — build + live core validation (2026-08-19)

The target commit was materialized as an exact detached checkout and both
deployment entry points compiled without errors:

```text
git rev-parse HEAD
63f0f812474e713916dc909494d655246783a1d9

az bicep build --file bicep/infra/main.bicep --outfile <tmp>/main.json
exit 0; 4,867,085-byte ARM JSON with Bicep CLI 0.43.8; warnings only

az bicep build-params --file bicep/infra/main.bicepparam \
  --outfile <tmp>/main.parameters.json
exit 0; 10,971-byte parameters JSON; warnings only
```

The coordinator's reference build produced a 4,867,124-byte `main.json`.
Generated ARM JSON byte size can vary by Bicep compiler; both runs exited zero
with warnings only.

The exact pin was also deployed to a non-production subscription with the
lean pilot overlay in East US 2. The structured arrays were deliberately
reduced to one Foundry account plus `gpt-5.4-mini` and
`text-embedding-3-large`, both at 30K TPM. Redis, API Center, AI Search,
Document Intelligence, dashboards, and Foundry network injection remained
disabled.

`azd provision --preview` succeeded. The first deployment exposed a missing
`Microsoft.ManagedIdentity` provider preflight during APIM activation. After
registering the provider and recreating the failed APIM service, `azd up`
succeeded using the canonical `azure-tenant-isolation` bootstrap and an
explicit subscription argument.

One LLM Access Contract was deployed with direct output rather than Key Vault
secret storage. Live calls then returned:

```text
GET /models/models
HTTP 200
gpt-5.4-mini

POST /openai/deployments/gpt-5.4-mini/chat/completions
HTTP 200
citadel-ok
```

A product policy setting `jwtRequired=true` rejected a missing bearer token
with HTTP 401. Positive client-credentials validation did not complete: the tenant rejected the
pinned two-year secret lifetime, a 30-day append-only credential succeeded,
and the private Key Vault rejected the local host with
`ForbiddenByConnection`. A temporary in-VNet workload then wrote the same
secret through the private endpoint and read it back byte-for-byte
(`KV_SECRET_MATCH`); its container, role assignment, and subnet were removed.
No Key Vault firewall exception was introduced. Conditional Access still
rejected workload token issuance with `AADSTS53003`. The current pin is
therefore live-validated for deployment, core gateway traffic, missing-token
JWT enforcement, and private Key Vault persistence, but not for a positive
client-credentials dual-auth call.

### Current-pin static contract review

Static review of the pinned sources established two constraints that are now
enforced by the shipped profile validator:

- `bicep/infra/main.bicep` documents `eventHubNetworkAccess=Enabled` as
  required while an APIM v2 SKU provisions. The enterprise and VNet profiles
  therefore keep Event Hub public access enabled; this is source inspection,
  not post-deploy hardening evidence.
- `bicep/infra/entra-id-setup/setup.ps1` mutates Microsoft Graph, writes
  `ENTRA-APP-CLIENT-SECRET` through the Key Vault data plane, and creates or
  updates APIM named values. It also continues after a Key Vault write failure.
  The skill consequently requires Graph app-registration permission, Key
  Vault Secrets Officer, API Management Service Contributor, private vault
  reachability, and explicit post-script data-plane verification.

The provider, credential-lifetime, private-network, and Conditional Access
findings above were observed live at the current pin. The APIM v2 Event Hub
constraint remains source-reviewed rather than live-tested because the lean
validation used Developer APIM.

---

## Historical live audit — old pin

### Phase 1 — Pin upstream + bicep build

```
$ git ls-remote https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-v1
f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4    refs/heads/citadel-v1

$ git clone --depth 1 --branch citadel-v1 https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator
$ az bicep build --file bicep/infra/main.bicep --outfile out.json
# Bicep CLI 0.43.8 — exit 0 — ARM JSON 6 MB
# Warnings: no-unused-params (1), no-hardcoded-env-urls (4), BCP318 (~20),
#           prefer-unquoted-property-names (1)
# All warnings are linter advisories on intentional patterns; no errors.
```

**Gotcha #1**: `az bicep build --stdout` stalls PowerShell on a 6 MB ARM
JSON output. Always use `--outfile` for hubs of this size.

---

### Phase 2 — Resource & shape audit

After tenant isolation per `azure-tenant-isolation`:

```
$ az group list -o table | grep citadel
rg-citadel-hub-01        swedencentral    Succeeded
$ az group show -n rg-citadel-hub-01 --query tags
{"SecurityControl": "Ignore", "azd-env-name": "citadel-hub-01"}
```

### Resource inventory (~75 resources)

| Resource type | Count | Names (sample) |
|---|---|---|
| APIM | 1 | `apim-codfa4k4hph2q` |
| APIM Identity (UAMI) | 1 | `id-apim-codfa4k4hph2q` |
| AI Foundry (AIServices) | 2 | `aif-codfa4k4hph2q-0` (sweden) + `aif-codfa4k4hph2q-1` (east-us-2) |
| Foundry Project (per Foundry) | 2 | `citadel-governance-project` |
| Cosmos DB | 1 | `cosmos-codfa4k4hph2q` |
| Event Hub Namespace | 1 | `evhns-codfa4k4hph2q` |
| Key Vault | 1 | `kv-codfa4k4hph2q` |
| Log Analytics | 1 | `log-codfa4k4hph2q` |
| Application Insights | 3 | `appi-apim`, `appi-aif`, `appi-func` |
| Redis (Managed) | 1 | `redis-codfa4k4hph2q` |
| Logic App | 1 | `logic-usage-codfa4k4hph2q` |
| Logic App Identity (UAMI) | 1 | `id-logicapp-codfa4k4hph2q` |
| Function App | 1 | `funcusagecodfa4k4hph2q` |
| Storage Account | 1 | (st* — referenced via blob/file/queue/table PEs) |
| VNet | 1 | `vnet-codfa4k4hph2q` (10.170.0.0/24) |
| Subnets | 4 | `snet-apim`, `snet-private-endpoint`, `snet-functionapp`, `snet-agents` |
| NSGs | 4 | `nsg-apim`, `nsg-pe`, `nsg-functionapp`, `nsg-agents` |
| Route Table | 1 | `rt-apim` |
| Private Endpoints | 13 | apim-pe, kv-pe, evhns-pe, cosmos-pe, foundry-pe ×2, redis-pe, storage-pe ×4 |
| Private DNS Zones | 13 | One per privatelink.* type (openai, documents, table, servicebus, blob, cognitiveservices, services.ai, azure-api, vaultcore, redis, file, queue) |
| Private DNS Zone Links | 13 | All linked to `vnet-codfa4k4hph2q` |

### APIM details

```
sku                       : StandardV2 (capacity 1)
location                  : Sweden Central
virtualNetworkType        : External
publicNetworkAccess       : Enabled
gatewayUrl                : https://apim-codfa4k4hph2q.azure-api.net
```

### APIs imported

| name | path | notes |
|---|---|---|
| azure-openai-api | `openai` | classic Azure OpenAI surface |
| openai-realtime-ws-api | `openai/realtime` | WebSocket realtime |
| unified-ai-api | `unified-ai` | wildcard multi-provider routing |
| universal-llm-api | `models` | OpenAI-style provider-agnostic surface |
| weather-api | `weather` | sample/test |

All 4 LLM APIs use `subscriptionKeyParameterNames.header = "api-key"`
(Azure OpenAI convention), NOT the APIM default
`Ocp-Apim-Subscription-Key`.

### Products + Subscriptions

| Product | State | Subscription |
|---|---|---|
| `unified-ai-product` | published | (no per-product sub at audit time) |
| `LLM-RnD-BATScraper-DEV` | published | `LLM-RnD-BATScraper-DEV-SUB-01` |
| (built-in) | — | `master` (all-access) |

Confirms that real access contracts get deployed POST-install via
`citadel-spoke-onboarding` — the hub itself ships zero contracts.

### Foundry deployments

`aif-codfa4k4hph2q-0` (Sweden Central):

| Model | Version | SKU | Capacity |
|---|---|---|---|
| gpt-4.1 | 2025-04-14 | GlobalStandard | 100 |
| gpt-5.4 | 2026-03-05 | GlobalStandard | 100 |
| gpt-5.4-mini | 2026-03-17 | GlobalStandard | 100 |
| Mistral-Large-3 | 1 | GlobalStandard | 100 |
| text-embedding-3-large | 1 | GlobalStandard | 100 |
| DeepSeek-R1 | 1 | GlobalStandard | 1 |
| Phi-4 | 7 | GlobalStandard | 1 |

`aif-codfa4k4hph2q-1` (East US 2):

| Model | Version | SKU | Capacity |
|---|---|---|---|
| gpt-5.4 | 2026-03-05 | GlobalStandard | 100 |
| gpt-5.4-mini | 2026-03-17 | GlobalStandard | 100 |
| gpt-5.2 | 2025-12-11 | GlobalStandard | 100 |
| text-embedding-3-large | 1 | GlobalStandard | 100 |
| DeepSeek-R1 | 1 | GlobalStandard | 1 |
| Phi-4 | 7 | GlobalStandard | 1 |

### Sub-level deploy attempts (`citadel-hub-01-*`)

```
citadel-hub-01-1778506070  Failed     2026-05-11 13:46
citadel-hub-01-1778507356  Failed     2026-05-11 13:56
citadel-hub-01-1778508022  Succeeded  2026-05-11 14:06
citadel-hub-01-1778512463  Succeeded  2026-05-11 15:20
```

**Gotcha #2**: First-run `azd up` failed twice before succeeding. Likely
RBAC propagation + Cognitive Services regional warm-up + APIM
provisioning timing. `azd up` is idempotent; re-run.

### Actual deployment parameters used (from successful sub-deploy)

Notable env-var overrides from upstream defaults:

```
APIM_SKU                              = StandardV2
APIM_NETWORK_TYPE                     = External
APIM_V2_USE_PRIVATE_ENDPOINT          = true
APIM_V2_PUBLIC_NETWORK_ACCESS         = true
COSMOS_DB_PUBLIC_ACCESS               = Disabled
AI_FOUNDRY_EXTERNAL_NETWORK_ACCESS    = Disabled
KEY_VAULT_EXTERNAL_NETWORK_ACCESS     = Disabled
REDIS_PUBLIC_NETWORK_ACCESS           = Disabled
EVENTHUB_NETWORK_ACCESS               = Enabled  (default — public)
ENABLE_PII_REDACTION                  = true       # bicep param: enableAIGatewayPiiRedaction
ENABLE_AI_MODEL_INFERENCE             = true
ENABLE_MANAGED_REDIS                  = true
ENABLE_OPENAI_REALTIME                = true
ENABLE_UNIFIED_AI_API                 = true
FOUNDRY_NETWORK_INJECTION_ENABLED     = true
ENABLE_API_CENTER                     = false
ENABLE_AZURE_AI_SEARCH                = false
ENABLE_DOCUMENT_INTELLIGENCE          = false
AZURE_ENTRA_AUTH                      = false
USE_EXISTING_LOG_ANALYTICS            = false
USE_EXISTING_VNET                     = false
VNET_ADDRESS_PREFIX                   = 10.170.0.0/24
APIM_SKU_UNITS                        = 1
COSMOS_DB_RUS                         = 400
EVENTHUB_CAPACITY                     = 1
APIC_SKU                              = Free
KEY_VAULT_SKU_NAME                    = standard
REDIS_SKU_NAME                        = Balanced_B1
```

This shape is essentially **enterprise-baseline minus disabled-public-APIM**:
production-grade APIM SKU + private endpoints on backend services + public
APIM access (so notebooks can reach it from the internet without VPN).

---

## Phase 3 — APIM smoke-call

### Discover models — `GET /models/models`

```
call 1 (cold): 663 ms — 8 models returned
call 2:        266 ms
call 3:        256 ms
```

### Chat completion — `POST /openai/deployments/gpt-5.4-mini/chat/completions`

First attempt with `max_tokens=5`:

```
HTTP 400 Bad Request
{"error":{"message":"Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.","type":"invalid_request_error","param":"max_tokens","code":"unsupported_parameter"}}
```

**Gotcha #3**: Newer GPT-5.4 family models migrated from `max_tokens`
to `max_completion_tokens`. APIM passes the request through; the
rejection comes from the model.

After fixing to `max_completion_tokens=10`:

```
call 1 (cold-ish): 1682 ms — resp="pong"   prompt=13 completion=5
call 2:             998 ms — resp="pong"   prompt=13 completion=5
call 3:            1104 ms — resp="pong"   prompt=13 completion=5
```

### PII redaction probe — `POST /openai/.../chat/completions`

Prompt: `Echo this exact text back: My SSN is 123-45-6789 and my email is jane.doe@example.com`

```
latency=1124 ms
PII echo: "Sorry, I can't repeat or echo sensitive personal data like SSNs
or email addresses. If you want, I can help redact it or format it safely."
```

**Observation**: model refused, so we can't conclusively distinguish
model-side safety from APIM PII fragment redaction in this single
call. Either way, a sensitive PII echo did NOT round-trip — defence in
depth is working. For more discriminating tests, see upstream
`validation/citadel-pii-processing-tests.ipynb` (uses targeted
prompts that bypass model alignment to test the policy fragment
explicitly).

### Auth gotcha (root cause of initial failures)

First call attempts used `Ocp-Apim-Subscription-Key: ...` header — got
401. Fix: use `api-key: ...` header on all 4 LLM APIs (matches Azure
OpenAI conventions; configured via APIM API
`subscriptionKeyParameterNames.header`).

```
$ az rest --method get --url ".../apis/universal-llm-api?api-version=2022-08-01" \
    --query "{path:properties.path, subKeyHeader:properties.subscriptionKeyParameterNames.header}"
{
  "path": "models",
  "subKeyHeader": "api-key"
}
```

---

## Phase 4 — Notebook structure (recommended baseline)

Did NOT execute the notebook against the shared hub (would have
created an extra access contract = invasive). Instead captured the
notebook structure for documentation purposes:

`citadel-universal-llm-api-all-models-tests.ipynb` — 23 cells:

| Cell | Type | Purpose |
|------|------|---------|
| 0 | md | Title + overview |
| 1 | md | Init mode toggle docs |
| 2 | code | **Init**: `init_from_azd = True`, REPLACE fallbacks, `utils.load_azd_env()` |
| 3-4 | md+code | Verify `az account show` |
| 5-6 | md+code | Init `APIMClientTool` from `shared/apimtools.py` |
| 7-8 | md+code | Provision Access Contract via `bicep/infra/citadel-access-contracts/main.bicep` |
| 9-10 | md+code | Retrieve API key from access contract subscription |
| 11-12 | md+code | Discover models via `GET /models/models` |
| 13-14 | md+code | Classify models (chat vs embedding vs realtime) |
| 15-16 | md+code | Execute per-model operations |
| 17-18 | md+code | Sanity check `allowedModels=""` |
| 19-22 | md+code | Tabulate results, cleanup |

**Init pattern is universal across all 8 notebooks**: a `init_from_azd`
boolean cell + REPLACE sentinels + `utils.load_azd_env({...})` from
`validation/shared/utils.py`. Per-notebook env-var maps documented in
`validation/README.md` upstream.

**Dependencies (`validation/shared/requirements.txt`)** — substantial:
azure-cli, azure-identity, openai, openai[realtime], azure-ai-projects,
azure-ai-agents, azure-ai-inference[prompts], azure-search-documents,
azure-functions, azure-mgmt-apimanagement, mcp, autogen-core,
autogen-ext[openai,azure,mcp], autogen-agentchat, semantic-kernel[mcp],
agent-framework, opentelemetry-api/sdk, azure-monitor-opentelemetry +
~15 more. Plan for ~5-10 min `pip install` on a fresh venv.

**Recommended baseline run order** (per upstream `validation/README.md`):

1. `llm-backend-onboarding-runner.ipynb` ⭐
2. `citadel-universal-llm-api-all-models-tests.ipynb` ⭐
3. `citadel-access-contracts-tests.ipynb` ⭐
4. `citadel-agent-frameworks-tests.ipynb` ⭐
5. `citadel-model-aliases-tests.ipynb` (optional)
6. `citadel-pii-processing-tests.ipynb` (optional)
7. `citadel-unified-ai-api-tests.ipynb` (optional)
8. `citadel-jwt-authentication-tests.ipynb` (optional)

---

## Audit conclusions

1. **Wrapper shape works.** The `azd init --template ... --branch citadel-v1`
   + `azd env set` overlay flow is the right wrapping pattern. No need
   to fork or vendor.
2. **Live hub is reachable, gateway routes correctly, latency is
   reasonable.** ~1 sec warm chat through APIM is acceptable for
   gateway-mediated workloads.
3. **`api-key` header is non-obvious.** This is the #1 first-time-user
   gotcha — captured in SKILL.md § 11 and on every smoke-call example.
4. **`max_completion_tokens` migration bites.** GPT-5.4 family clients
   need to update — captured in SKILL.md § 11.
5. **3-profile design covers the realistic deploy shapes.** The audit
   hub matches a hybrid of `enterprise-baseline` (Standard v2,
   Foundry/Cosmos/KV/Redis private) and `pilot-quickstart` (public
   APIM access for notebook-friendly testing). The 3 profiles in
   `references/profiles/` cover this surface.
6. **PII filter is active**, though the smoke test alone can't fully
   discriminate model-side refusal vs APIM-side redaction.
   `citadel-pii-processing-tests.ipynb` is the right tool.

End of audit notes.

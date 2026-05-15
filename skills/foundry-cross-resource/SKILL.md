---
name: foundry-cross-resource
description: >
  Cross-resource model invocation in Microsoft Foundry via an Azure APIM AI
  Gateway, using the `connectionName/deploymentName` model string. Documents
  the verified ApiKey and ProjectManagedIdentity (PMI) auth paths, three
  invocation patterns (Responses API, PromptAgentDefinition, refreshed-preview
  hosted-agent client), the APIM inbound policy XML, and the connection
  ARM/REST schema with the metadata-stringification quirk that catches users
  out. USE FOR: connectionName/deploymentName, cross-resource model access,
  AI Gateway, APIM connection, ApiManagement connection, remote model
  invocation, Foundry gateway, use models from another Foundry project, APIM AI
  gateway setup, Foundry Agent Service gateway, model gateway connection,
  remote deployment, ProjectManagedIdentity APIM, AI Foundry APIM ApiKey.
  DO NOT USE FOR: single-resource model calls (use the project's own
  AzureOpenAI/AIServices connection), Azure tenant isolation
  (use azure-tenant-isolation), Foundry project creation, APIM creation
  from scratch.
metadata:
  version: "1.0.1"
---

# Cross-Resource Model Invocation via Foundry AI Gateway

> **Status — verified live on 2026-04-23** with Foundry account
> `xtest-foundry-mr5kfi` / project `xtest-proj-mr5kfi` (Sweden Central) calling
> deployment `gpt-4o-mini v2024-07-18` hosted on a different Azure OpenAI
> account (`acme-aoai-shared`) through APIM `acme-ai-apim`. Both **ApiKey**
> and **ProjectManagedIdentity** auth paths returned `PONG` on all three
> invocation patterns. See "Verified working configuration" at the end.
>
> **Default in worked examples below: `gpt-5.4-mini`** (current
> Foundry-routable chat-mini family, May 2026). The original verification
> was on `gpt-4o-mini`; the gateway routes by `deployment-name-in-path`
> regardless of model family, so the recipe is mechanically identical for
> any deployment your APIM backend actually carries. The exact API
> `version` string in the connection metadata below is illustrative —
> use whatever your backend deployment is registered with (check
> `az cognitiveservices account deployment show`).

---

## 1. What this skill solves

You have a Foundry project ("**consumer**") that needs to invoke models
deployed on a **different** Azure OpenAI / AI Services account ("**backend**"),
fronted by an Azure API Management instance acting as the AI Gateway. You want
to address those models via the Foundry-native string
`connectionName/deploymentName` so the application code is identical to a
local-deployment call.

```
┌────────────────────────┐                ┌──────────────────────────┐                ┌─────────────────────────────┐
│  Consumer Foundry      │                │  APIM AI Gateway         │                │  Backend AI/OpenAI account  │
│  project               │  Foundry MI    │  acme-ai-apim        │   APIM MI →    │  acme-aoai-shared       │
│  xtest-proj-mr5kfi     ├───or────────► │   /xtest-aoai            ├──Bearer───────►│  gpt-5.4-mini deployment    │
│  (Sweden Central)      │  ApiKey        │   /xtest-aoai-pmi        │  (msi token)   │  (East US 2)                │
│                        │                │                          │                │                             │
│  ApiManagement         │                │  validate token /        │                │  Cognitive Services User RBAC│
│  connection            │                │  enforce subscription    │                │  granted to APIM MI         │
│  category=ApiManagement│                │  set-backend-service     │                │                             │
│  target=APIM API URL   │                │  authentication-managed- │                │                             │
│  authType=ApiKey | PMI │                │   identity → backend     │                │                             │
└────────────────────────┘                └──────────────────────────┘                └─────────────────────────────┘
```

The consumer project never holds the backend's API key or RBAC. APIM is the
trust boundary.

---

## 2. The 100% reliable checklist

Before any agent call, ALL of these must be true. Cross them off in order;
the official validator script
[`test_apim_connection.py`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/test_apim_connection.py)
plus the field-tested probes in §8 below verify each step end-to-end.

| # | Item | How to verify |
|---|------|---------------|
| 1 | Backend AI Services / Azure OpenAI account exists with the model deployed | `az cognitiveservices account deployment list -g <rg> -n <backend>` |
| 2 | APIM exists (any SKU; Developer is fine for testing, Standard v2/Premium for prod) and has system-assigned managed identity enabled | `az apim show -g <rg> -n <apim> --query identity` |
| 3 | APIM MI has `Cognitive Services User` (or `Cognitive Services OpenAI User`) on the backend account | `az role assignment list --assignee <apim-mi-objectId> --scope <backend-id>` |
| 4 | APIM has an API whose path you'll target (e.g., `/xtest-aoai`) with **inbound policy that calls `set-backend-service` + `authentication-managed-identity` + Bearer header injection** (see §6) | `Invoke-RestMethod -Uri https://<apim>.azure-api.net/<api>/deployments/<dep>/chat/completions?api-version=2024-10-21 -Headers @{api-key='<sub-key>';...}` returns 200 |
| 5 | (ApiKey only) An APIM subscription scoped to that API (or to a product the API is in) exists; you have the primary key | `az apim subscription show ...` |
| 6 | (PMI only) APIM API has `subscriptionRequired: false` AND inbound policy includes `<validate-azure-ad-token>` with `<client-application-ids>` containing the **consumer project MI's client/app ID** | API GET shows `subscriptionRequired:false`; policy GET shows the GUID |
| 7 | Consumer Foundry project exists, has Azure AI User RBAC for the caller, and (PMI) has system-assigned managed identity enabled | `az cognitiveservices account project show ... --query identity` |
| 8 | An `ApiManagement` connection exists on the consumer project (NOT `AzureOpenAI`, NOT `AIServices`) | See §5 for the verified PUT body |
| 9 | The connection's `metadata.models` is a **JSON-stringified** array (NOT a real array) and `metadata.deploymentInPath` matches the backend style | See §5 — this is the most common silent error |
| 10 | Caller code uses `model="<connectionName>/<deploymentName>"` and calls `responses.create(...)` (NOT `chat.completions.create`) | See §7 |

If step 4 doesn't return 200 outside Foundry, no Foundry call will work. Always
smoke-test the gateway directly first.

---

## 3. Decision tree

```
                          ┌──────────────────────────────────────┐
                          │ What backend does APIM forward to?   │
                          └─────────────┬────────────────────────┘
                                        │
              ┌─────────────────────────┴────────────────────────┐
              │                                                  │
   AOAI / AI Services on /openai                       OpenAI v1 (/v1/...)  
   (most common — Azure OpenAI)                        or Anthropic etc.    
              │                                                  │
              ▼                                                  ▼
   metadata.deploymentInPath = "true"           metadata.deploymentInPath = "false"
   metadata.inferenceAPIVersion = "2024-10-21"  metadata.inferenceAPIVersion = ""  (or omit)
   models[].properties.model.format = "OpenAI"  models[].properties.model.format = "OpenAI"|"Anthropic"|"NonOpenAI"
                                                modelDiscovery.listModelsEndpoint = "/models"
                                                modelDiscovery.deploymentProvider = "AzureOpenAI"|"OpenAI"|"Anthropic"|"NonOpenAI"

                          ┌──────────────────────────────────────┐
                          │ How do callers prove identity to APIM?│
                          └─────────────┬────────────────────────┘
                                        │
              ┌─────────────────────────┼────────────────────────┐
              │                         │                        │
        APIM subscription key   Project Managed Identity    Both (dual-auth)
              │                  (no static secrets)               │
              ▼                         ▼                        ▼
   authType: "ApiKey"           authType: "ProjectManagedIdentity"  Two connections OR
   credentials.key: <key>       credentials: {}                     APIM <choose><when>
   APIM api: subscription req   audience:                           policy that branches
   APIM policy: pass-through      "https://cognitiveservices.azure.com"
                                APIM policy: validate-azure-ad-token
                                  with <client-application-ids>
                                  containing project MI clientId
                                APIM api: subscriptionRequired=false
```

---

## 4. APIM-side configuration

### 4.1 Service URL on the API

The Foundry connection target is `https://<apim>.azure-api.net/<apiPath>`.
Inside the API's inbound policy you `set-backend-service` to the backend
account. Foundry then appends `/deployments/{dep}/chat/completions?api-version=...`
(or `/v1/responses` etc.) to the gateway URL.

Operations on the API (i.e., the routes Foundry will call) must therefore
match the AOAI / OpenAI surface. The simplest setup is **catch-all** with one
operation per HTTP verb on the wildcard path `/{*path}`. For Azure OpenAI
backends, all of the following must reach the inbound policy and 200:

```
POST /deployments/{deployment-id}/chat/completions?api-version=2024-10-21
POST /deployments/{deployment-id}/embeddings?api-version=2024-10-21
POST /v1/responses?api-version=preview          (Responses API)
GET  /models?api-version=2024-10-21             (model catalogue, used for dynamic discovery)
```

### 4.2 ApiKey-only inbound policy (verified working — `xtest-aoai`)

```xml
<policies>
    <inbound>
        <base />
        <set-backend-service base-url="https://acme-aoai-shared.openai.azure.com/openai" />
        <authentication-managed-identity
            resource="https://cognitiveservices.azure.com"
            output-token-variable-name="msi-access-token"
            ignore-error="false" />
        <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["msi-access-token"])</value>
        </set-header>
    </inbound>
    <backend><base /></backend>
    <outbound><base /></outbound>
    <on-error><base /></on-error>
</policies>
```

Subscription enforcement is at the API/product level (set
`subscriptionRequired: true` and configure `subscriptionKeyParameterNames.header`
to `api-key` so the caller sends `api-key: <key>`, not
`Ocp-Apim-Subscription-Key`). Foundry sends the `api-key` header.

### 4.3 PMI-only inbound policy (verified working — `xtest-aoai-pmi`)

```xml
<policies>
    <inbound>
        <base />
        <validate-azure-ad-token
            tenant-id="<your-tenant-id>"
            header-name="Authorization"
            failed-validation-httpcode="401"
            failed-validation-error-message="Unauthorized: token did not match expected audience or application">
            <client-application-ids>
                <application-id><consumer-project-MI-clientId></application-id>
            </client-application-ids>
            <audiences>
                <audience>https://cognitiveservices.azure.com</audience>
                <audience>https://cognitiveservices.azure.com/</audience>
            </audiences>
        </validate-azure-ad-token>
        <set-backend-service base-url="https://acme-aoai-shared.openai.azure.com/openai" />
        <authentication-managed-identity
            resource="https://cognitiveservices.azure.com"
            output-token-variable-name="msi-access-token"
            ignore-error="false" />
        <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["msi-access-token"])</value>
        </set-header>
    </inbound>
    <backend><base /></backend>
    <outbound><base /></outbound>
    <on-error><base /></on-error>
</policies>
```

PMI API also needs `subscriptionRequired: false` on the API resource
(otherwise APIM rejects with 401 before the policy runs).

> **Why `<client-application-ids>` and not `<required-claims>` with `xms_mirid`?**
> Both mechanisms work in principle, but the `xms_mirid` value Foundry's
> project MI puts in its token is **not** the project ARM ID — it varies by
> resource provider and current APIs.  The MI's `appid` claim is universally
> present and stable, so `<client-application-ids>` is the documented and
> most reliable check. (Verified 2026-04-23: a policy requiring
> `xms_mirid = <project ARM ID>` returned 401; switching to `<client-application-ids>` returned 200.)

### 4.4 Dual-auth inbound policy (ApiKey OR PMI)

```xml
<policies>
    <inbound>
        <base />
        <choose>
            <when condition="@(context.Subscription == null)">
                <validate-azure-ad-token
                    tenant-id="<your-tenant-id>"
                    header-name="Authorization"
                    failed-validation-httpcode="401">
                    <client-application-ids>
                        <application-id><consumer-project-MI-clientId></application-id>
                    </client-application-ids>
                    <audiences>
                        <audience>https://cognitiveservices.azure.com</audience>
                        <audience>https://cognitiveservices.azure.com/</audience>
                    </audiences>
                </validate-azure-ad-token>
            </when>
        </choose>
        <set-backend-service base-url="https://<backend>.openai.azure.com/openai" />
        <authentication-managed-identity
            resource="https://cognitiveservices.azure.com"
            output-token-variable-name="msi-access-token" />
        <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["msi-access-token"])</value>
        </set-header>
    </inbound>
</policies>
```

API must have `subscriptionRequired: false` (so PMI calls aren't rejected up
front); the `<choose>` branch enforces token validation only when no
subscription was used.

---

## 5. Connection schema (verified live)

ARM type:
`Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview`.
Reachable also via the Foundry data-plane endpoint
`https://<account>.services.ai.azure.com/api/projects/<project>/connections/<name>?api-version=v1`.

> ⚠ **The `metadata.models` and `metadata.modelDiscovery` fields are
> JSON-encoded strings, not real JSON objects.** This is because Azure
> connection metadata is a flat string→string dictionary. Pass the JSON as a
> `string` value or your PUT will be silently ignored / rejected.

### 5.1 ApiKey connection — verified working PUT body

```json
{
  "properties": {
    "category": "ApiManagement",
    "target": "https://acme-ai-apim.azure-api.net/xtest-aoai",
    "authType": "ApiKey",
    "credentials": { "key": "<APIM subscription primary key>" },
    "isSharedToAll": true,
    "metadata": {
      "deploymentInPath": "true",
      "inferenceAPIVersion": "2024-10-21",
      "models": "[{\"name\":\"gpt-5.4-mini\",\"properties\":{\"model\":{\"name\":\"gpt-5.4-mini\",\"format\":\"OpenAI\",\"version\":\"2026-04-30\",\"publisher\":\"Microsoft\"}}}]"
    }
  }
}
```

PUT URL:

```
https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/
Microsoft.CognitiveServices/accounts/<consumer-acct>/projects/<consumer-proj>/
connections/<connectionName>?api-version=2025-04-01-preview
```

Or via the data plane:

```
PUT https://<consumer-acct>.services.ai.azure.com/api/projects/<consumer-proj>/connections/<name>?api-version=v1
```

### 5.2 PMI connection — verified working PUT body

```json
{
  "properties": {
    "category": "ApiManagement",
    "target": "https://acme-ai-apim.azure-api.net/xtest-aoai-pmi",
    "authType": "ProjectManagedIdentity",
    "credentials": {},
    "audience": "https://cognitiveservices.azure.com",
    "isSharedToAll": true,
    "metadata": {
      "deploymentInPath": "true",
      "inferenceAPIVersion": "2024-10-21",
      "models": "[{\"name\":\"gpt-5.4-mini\",\"properties\":{\"model\":{\"name\":\"gpt-5.4-mini\",\"format\":\"OpenAI\",\"version\":\"2026-04-30\",\"publisher\":\"Microsoft\"}}}]"
    }
  }
}
```

`audience` lives at `properties.audience`, NOT in metadata. The data-plane
GET strips it from the response, but it is required on PUT and is what Foundry
uses when requesting the MI token.

### 5.3 Metadata reference (full)

| Field | Type | Required | Default | Purpose |
|-------|------|----------|---------|---------|
| `deploymentInPath` | string `"true"`/`"false"` | Yes (in practice — without it: `Upstream gateway returned NotFound`) | none | `"true"` → AOAI shape `/deployments/{dep}/chat/completions`. `"false"` → OpenAI v1 shape with model in body. |
| `inferenceAPIVersion` | string | Recommended for AOAI | none | Appended as `?api-version=...`. Use `2024-10-21` (or newer GA) for AOAI; leave empty for `/v1/responses` style backends. |
| `deploymentAPIVersion` | string | Optional | `inferenceAPIVersion` | Used for `modelDiscovery` list calls. |
| `models` | **string** (JSON array, escaped) | Required if no `modelDiscovery` | none | Static catalogue. Must be JSON-stringified. |
| `modelDiscovery` | **string** (JSON object, escaped) | Required if no `models` | none | Dynamic discovery. Must be JSON-stringified. Defaults: `listModelsEndpoint=/deployments`, `getModelEndpoint=/deployments/{deploymentName}`, `deploymentProvider=AzureOpenAI`. Override to `/models` and `OpenAI` for OpenAI-v1 style backends. |
| `customHeaders` | string (JSON object) | Optional | none | Adds extra HTTP headers on every Foundry-to-APIM call. |
| `authConfig` | string (JSON object) | Optional | none | For non-`Authorization`-header auth (e.g., gateway expects `x-api-key: Bearer <key>`). |

`models[].properties.model.format` accepts `OpenAI`, `Anthropic`, `NonOpenAI`.
For Azure OpenAI deployments use `OpenAI`.

### 5.4 What does NOT work (verified failures)

| Connection variant | Result |
|--------------------|--------|
| Connection with **no** `metadata` at all | `400 Model gateway error: Upstream gateway returned NotFound` |
| Connection with `metadata.modelDiscovery` (stringified) but **no** `models` | `400 Model gateway error: Upstream gateway returned NotFound` (against AOAI backends — AOAI's `/deployments` data-plane endpoint isn't a list) |
| `models` passed as a real JSON array (not stringified) | Foundry stores it but inference returns `Upstream gateway returned NotFound`; this is a silent footgun |
| `authType: "AAD"` (legacy alias) | Inconsistent — sometimes accepted, sometimes rejected. Always use `ProjectManagedIdentity`. |

---

## 6. Setup paths

### 6.1 Bicep (recommended for production)

Use the official module from
[`microsoft-foundry/foundry-samples/infrastructure/infrastructure-setup-bicep/01-connections/apim/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/apim).
Files of interest:

- `connection-apim.bicep` — top-level module
- `modules/apim-connection-common.bicep` — actual `connections` resource declaration
- `samples/parameters-static-models.json` — ApiKey + static models
- `samples/parameters-dynamic-discovery.json` — dynamic via `/models`
- `samples/parameters-custom-headers.json`
- `samples/parameters-custom-auth-config.json`

When using Bicep, you write `models` as a real Bicep array; the module
JSON-stringifies it before assigning to `metadata.models`. Check
`apim-connection-common.bicep` to confirm — do NOT hand-stringify if you go
through Bicep, only if you call ARM/REST directly.

### 6.2 PowerShell REST (operational scripts)

```powershell
$tenant = '<tenant-id>'
$proj   = 'https://<consumer-acct>.services.ai.azure.com/api/projects/<consumer-proj>'
$apim   = 'https://acme-ai-apim.azure-api.net/xtest-aoai'

# Token for Foundry data plane (use the AI resource audience)
$tok = az account get-access-token --resource 'https://ai.azure.com' --query accessToken -o tsv

$models = @(@{
    name = 'gpt-5.4-mini'
    properties = @{
      model = @{ name='gpt-5.4-mini'; format='OpenAI'; version='2026-04-30'; publisher='Microsoft' }
    }
}) | ConvertTo-Json -Depth 6 -Compress

$body = @{
  properties = @{
    category      = 'ApiManagement'
    target        = $apim
    authType      = 'ApiKey'
    credentials   = @{ key = '<APIM subscription primary key>' }
    isSharedToAll = $true
    metadata      = @{
      deploymentInPath    = 'true'
      inferenceAPIVersion = '2024-10-21'
      models              = $models    # already a JSON string thanks to ConvertTo-Json
    }
  }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Put `
  -Uri "$proj/connections/aigw-strmeta?api-version=v1" `
  -Headers @{ Authorization = "Bearer $tok"; 'Content-Type' = 'application/json' } `
  -Body $body
```

For PMI: replace `authType` with `'ProjectManagedIdentity'`, set
`credentials = @{}`, and add `audience = 'https://cognitiveservices.azure.com'`
inside `properties`.

### 6.3 Foundry Portal (manual / quick check)

Operate → **Admin console** → All projects → click parent AI Services
account → **Admin-connected models** tab → **Add** → choose **API Management**
→ wizard fills:

- Display name (becomes connection name)
- Source = APIM service (drop-down lists APIMs in the same tenant)
- API = drop-down of APIs on that APIM
- Auth = ApiKey or PMI
- Discovery = Static models or Auto-discover (calls `listModelsEndpoint`)
- For Static: enter model name(s), pick format

Portal also writes the connection with stringified metadata under the hood.

---

## 7. Invocation patterns (Python — `azure-ai-projects >= 2.0.0`, `openai >= 2.0.0`)

All three patterns succeed against both ApiKey and PMI connections (verified
2026-04-23). The model string is **always** `<connectionName>/<deploymentName>`,
where `<deploymentName>` is the `name` field inside `metadata.models[]`
(NOT the backend's actual deployment id, unless they happen to match).

### 7.1 Pattern A — Direct Responses API (PRIMARY)

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="https://<consumer-acct>.services.ai.azure.com/api/projects/<consumer-proj>",
    credential=DefaultAzureCredential(),
)
oai = project.get_openai_client()

resp = oai.responses.create(
    model="aigw-strmeta/gpt-5.4-mini",       # connection-name/model-alias
    input="Say PONG.",
    max_output_tokens=20,                    # MUST be >= 16 to fit any non-trivial reply
)
print(resp.output_text)
```

### 7.2 Pattern B — Prompt agent + agent_reference

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="https://<consumer-acct>.services.ai.azure.com/api/projects/<consumer-proj>",
    credential=DefaultAzureCredential(),
)
oai = project.get_openai_client()

agent = project.agents.create_version(
    agent_name="cross-resource-helper",
    definition=PromptAgentDefinition(
        model="aigw-strmeta/gpt-5.4-mini",
        instructions="You only ever reply with the word PONG.",
    ),
)

conv = oai.conversations.create()
resp = oai.responses.create(
    input="Say it.",
    conversation=conv.id,
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
)
print(resp.output_text)
```

### 7.3 Pattern C — Refreshed-preview hosted-agent client

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="https://<consumer-acct>.services.ai.azure.com/api/projects/<consumer-proj>",
    credential=DefaultAzureCredential(),
    allow_preview=True,            # MUST be on the constructor, NOT on get_openai_client
)
oai = project.get_openai_client(agent_name="cross-resource-helper")
resp = oai.responses.create(input="Reply with PONG only.")
print(resp.output_text)
```

REST equivalent (refreshed preview): include header
`Foundry-Features: HostedAgents=V1Preview` on the call, per
`learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview`.

### 7.4 Negative pattern — DOES NOT work

```python
# 404 DeploymentNotFound — Foundry only routes the conn/dep alias on /v1/responses,
# never on the legacy /chat/completions endpoint.
oai.chat.completions.create(model="aigw-strmeta/gpt-5.4-mini", messages=[...])
```

If you have legacy code that must use `chat.completions`, point it at the
backend resource directly (with proper RBAC) — not at the Foundry project's
OpenAI surface.

### 7.5 Hosted Agents container (`MODEL_DEPLOYMENT_NAME`)

For Foundry Hosted Agents (MAF + ResponsesHostServer, or GHCP SDK
InvocationAgentServerHost), set `MODEL_DEPLOYMENT_NAME` in the agent's
container env to the same `connectionName/deploymentName` string. Remove any
`config.deployments` / model-deployment block from `azure.yaml` — the runtime
dispatches via the connection. See `foundry-hosted-agents` and
`ghcp-hosted-agents` skills.

---

## 8. Validation

### 8.1 Pre-Foundry: smoke-test APIM directly

```powershell
$apim = 'https://acme-ai-apim.azure-api.net/xtest-aoai'
$key  = '<subscription primary key>'

Invoke-RestMethod -Method Post `
  -Uri "$apim/deployments/gpt-5.4-mini/chat/completions?api-version=2024-10-21" `
  -Headers @{ 'api-key' = $key; 'Content-Type' = 'application/json' } `
  -Body (@{ messages=@(@{role='user';content='Say PONG.'}); max_tokens=20 } | ConvertTo-Json -Depth 5)
```

Expected: HTTP 200 with `choices[0].message.content`. If this fails, fix APIM
before touching Foundry.

### 8.2 Foundry probe: `test_apim_connection.py`

[`microsoft-foundry/foundry-samples/.../apim/test_apim_connection.py`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/test_apim_connection.py)
is the official validator — it issues a probe `/models` (or `/deployments`)
request and surfaces auth / discovery / target reachability problems before
agent calls.

### 8.3 Field-tested probes

Stand up two minimal probe scripts under `tests/` in your consumer project
— one per auth mode — that exercise all three invocation patterns plus
the negative `chat.completions` case for `ApiKey`. Pattern shape:

```python
# tests/probe_apim_apikey.py  (and probe_apim_pmi.py — same shape, different connection)
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

CONNECTION = os.environ["APIM_CONNECTION_NAME"]   # aigw-strmeta or aigw-pmi
DEPLOYMENT = os.environ["APIM_DEPLOYMENT_NAME"]   # e.g. gpt-5.4-mini

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
    allow_preview=True,
)
oai = project.inference.get_openai_client(api_version="v1")

# Pattern A — Responses
r = oai.responses.create(model=f"{CONNECTION}/{DEPLOYMENT}",
                         input="Say PONG", max_output_tokens=16)
assert r.output_text, "Pattern A returned empty output"

# Pattern B/C — see §6 for full hosted-agent invocation shapes
```

Run them as a regression gate when you provision new APIM/Foundry combinations.

---

## 9. Troubleshooting matrix (reproduced root causes)

| Symptom | Root cause | Fix |
|---------|-----------|-----|
| `400 Model gateway error: Upstream gateway returned NotFound` on EVERY call | Connection `metadata` is missing or `models`/`modelDiscovery` not stringified | PUT a connection that matches §5.1 verbatim. Stringify `models`. |
| `404 DeploymentNotFound` from `chat.completions.create()` with `model="conn/dep"` | Foundry routes `conn/dep` only on the Responses API | Use `responses.create()` (Pattern A) or one of the agent patterns. |
| `401 Access denied due to missing subscription key` (ApiKey path) | `api-key` header missing OR API/product `subscriptionRequired=false` is set | Either ensure connection holds the key (`credentials.key`) and APIM API requires sub; or switch to PMI and clear `subscriptionRequired`. |
| `401 Invalid token (audience or xms_mirid claim mismatch)` (PMI path) | Either audience mismatch or `xms_mirid` required-claim doesn't match Foundry's actual MI token | Validate using `<client-application-ids>` with the project MI clientId. (See §4.3 — `xms_mirid` value from Foundry is unreliable.) |
| Connection PUT with KV reference fails: "Azure Key Vault connections can only be created or updated at the workspace hub level" | Trying to store API key in a project-level KV connection on a Foundry V2 project | Don't. The 2025-04-01-preview ARM API stores ApiKey credentials inline. KV is not required. |
| Connection accepts `metadata.models` as real JSON array but inference still 404s | `models` stored as native dict, not stringified — silent footgun | JSON-stringify (`json.dumps(...)` then assign as the metadata value). |
| `BadRequest: API version not supported` calling `/connections` data plane | Wrong api-version. Foundry data plane uses `?api-version=v1`, not the ARM `2025-04-01-preview` | Use `?api-version=v1` for `/api/projects/<p>/connections/...`. ARM `2025-04-01-preview` works only at `https://management.azure.com/...`. |
| `ValueError: get_openai_client(...agent_name) requires allow_preview=True` | Set `allow_preview` on `get_openai_client()` instead of on the constructor | Move `allow_preview=True` to `AIProjectClient(...)`. |
| Pattern A returns `r.output_text == ""` | `max_output_tokens` too small; reasoning tokens consumed budget | Set `max_output_tokens >= 16` for "PONG"-style smoke tests; higher for real traffic. |
| Foundry call returns `500 server_error: Model gateway error: backend returned a non-200 response` | Custom APIM policy returned anything other than HTTP 200 | Foundry only accepts 200 from upstream. Don't try to short-circuit with `<return-response>`. |

---

## 10. Network isolation

For private VNet deployments (private endpoint on AI Services + private
endpoint on APIM + DNS), see template
[`16-private-network-standard-agent-apim-setup-preview`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/16-private-network-standard-agent-apim-setup-preview).
Conceptually identical to the public path — the connection target becomes
`https://<apim-private-host>/<api-path>`; Foundry resolves it through the
project's outbound private DNS zone.

---

## 11. Verified working configuration shape

This section captures the resource shape used in live verification of
this skill (subscriptions, principal IDs, and resource names redacted —
the recipe is reproducible from the placeholders).

| Component | Value |
|-----------|-------|
| Subscription | `<your-subscription-guid>` |
| Tenant | `<your-tenant-guid>` |
| Backend account | `<backend>-oai` (Azure OpenAI, `<rg-infra>`, East US 2) |
| Backend deployment | `gpt-5.4-mini` (or `gpt-4o-mini` v `2024-07-18` — both verified; gpt-4o-mini is legacy and reaches end-of-support per Azure OpenAI lifecycle calendar) |
| APIM | `<apim>` (`<rg-infra>`, Developer SKU is fine for testing; Standard v2 / Premium for prod, system-assigned MI) |
| APIM MI principal | `<apim-mi-objectId>` |
| APIM MI RBAC | `Cognitive Services OpenAI User` on backend account |
| APIM API (ApiKey) | `xtest-aoai`, `subscriptionRequired=true`, header `api-key` |
| APIM API (PMI) | `xtest-aoai-pmi`, `subscriptionRequired=false`, AAD-token-validated |
| Consumer account | `<consumer-foundry>` (`<rg-foundry>`, Sweden Central) |
| Consumer project | `<consumer-project>` |
| Consumer project MI clientId | `<consumer-project-mi-clientId>` |
| Consumer project endpoint | `https://<consumer-foundry>.services.ai.azure.com/api/projects/<consumer-project>` |
| Connection (ApiKey) | `aigw-strmeta`, `target=https://<apim>.azure-api.net/xtest-aoai` |
| Connection (PMI) | `aigw-pmi`, `target=https://<apim>.azure-api.net/xtest-aoai-pmi`, `audience=https://cognitiveservices.azure.com` |
| Test result (ApiKey) | Pattern A ✅ Pattern B ✅ Pattern C ✅ Negative chat.completions → 404 ✅ |
| Test result (PMI) | Pattern A ✅ Pattern B ✅ Pattern C ✅ |

> **Model currency note.** Verification ran on `gpt-4o-mini` (April
> 2026). Worked examples in this document **default to `gpt-5.4-mini`**
> (current Foundry-routable chat-mini family, May 2026) for currency,
> NOT because gpt-5.4-mini was independently re-verified end-to-end
> against this APIM topology — only that the gateway routes by
> `deployment-name-in-path` so the recipe is mechanically identical
> across model families. When you adopt this skill for a new pilot,
> verify with the actual deployment name + version in your APIM
> backend (`az cognitiveservices account deployment show`); the
> `version` field shown in the connection-metadata JSON is
> illustrative. `gpt-4o` family is **legacy** and reaches
> end-of-support per the Azure OpenAI lifecycle calendar — see
> `foundry-doc-vision-speech` § "GPT-4o is LEGACY".

SDK versions used: `azure-ai-projects 2.1.0`, `openai 2.36.0`,
`azure-identity 1.x`. Compatible with `azure-ai-projects >= 2.0.0`.

---

## 12. References

Authoritative sources backing every claim in this skill:

- **MS Learn** — [`AI Gateway connection (Foundry agents)`](https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway)
- **MS Learn** — [`Refreshed hosted agent preview`](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview)
- **GitHub `microsoft-foundry/foundry-samples`** —
  - [`connection-apim.bicep`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/connection-apim.bicep)
  - [`apim-connection-common.bicep`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/modules/apim-connection-common.bicep)
  - [`APIM-Connection-Objects.md`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/APIM-Connection-Objects.md)
  - [`apim-setup-guide-for-agents.md`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/apim-setup-guide-for-agents.md)
  - [`troubleshooting-guide.md`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/troubleshooting-guide.md)
  - [`test_apim_connection.py`](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/test_apim_connection.py)
  - [`16-private-network-standard-agent-apim-setup-preview/`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/16-private-network-standard-agent-apim-setup-preview)
- **ARM** — `Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview`
- **APIM** — [`validate-azure-ad-token` policy reference](https://learn.microsoft.com/azure/api-management/validate-azure-ad-token-policy)
- **APIM** — [`authentication-managed-identity` policy reference](https://learn.microsoft.com/azure/api-management/authentication-managed-identity-policy)
- **Related skills** — `foundry-hosted-agents`, `ghcp-hosted-agents`,
  `azure-tenant-isolation`, `azd-patterns`, `foundry-mcp-aca`

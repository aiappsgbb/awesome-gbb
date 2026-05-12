---
name: citadel-spoke-onboarding
description: >
  Onboard a GenAI app or Microsoft Foundry project as a spoke into an existing
  AI Citadel Governance Hub. Covers Access Contracts, Foundry APIM connections,
  Key Vault secret wiring, product policies, JWT auth, and networking.
  USE FOR: citadel spoke, citadel spoke onboarding, onboard agent to citadel,
  onboard foundry project to citadel, onboard genai app to citadel, access contract,
  ai hub gateway access contract, connect foundry to citadel, APIM connection,
  foundry apim connection citadel, bring your own ai gateway foundry,
  citadel onboarding, govern agent, AI gateway spoke, citadel compliant agent,
  citadel access contract, connect to governance hub, citadel JWT auth,
  citadel product policy, citadel key vault secrets, citadel validation notebook,
  unified ai api, openai compatible gateway, agent governance toolkit, citadel AGT.
  DO NOT USE FOR: deploying the Citadel hub itself, APIM infrastructure,
  hub networking, hub provisioning, hub sizing, llm backend onboarding,
  deploying model backends, apim backend pools, hub policy fragment deployment.
---

# Citadel Spoke Onboarding — Reference Guide

How to connect a GenAI application or Microsoft Foundry project to an
**existing** AI Citadel Governance Hub so that all AI traffic is governed,
observable, and compliant.

> **Threadlight integration**: This skill is the **opt-in Phase 7** of
> `threadlight-deploy`. It runs ONLY when SPEC § 11b sets
> `governance_hub.required: yes` (the SPEC field is generic; the AI
> Citadel hub is one reference implementation). The base agent deploy
> (Phase 5 + 6) lands in the customer's tenant first; this skill
> onboards it as a hub spoke afterwards as an additive step. Read
> SPEC § 11b for the per-process governance posture (hub endpoint,
> access contracts, JWT requirements, secret wiring).
>
> **Threadlight pilots MUST use Option B (Foundry Connection)** — see
> `Consuming the Gateway from Your App` below. Option A (Key Vault
> secret pull) violates the keyless-by-mandate posture: it requires
> the agent to hold an APIM subscription key and read it from KV at
> runtime. Option B threads the call through a Foundry APIM connection
> so the agent's UAMI is the only credential, and APIM enforces JWT
> validation on the project's MI token. If a customer insists on
> Option A for a non-threadlight reason, document the deviation in
> SPEC § 11b explicitly.

> **Source repo:** [Azure-Samples/ai-hub-gateway-solution-accelerator](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1) (branch `citadel-v1`)
> **Quick link:** <https://aka.ms/ai-hub-gateway>

---

## Key Concepts

| Term | Meaning |
|------|---------|
| **Citadel Governance Hub** | Central control plane with Azure API Management (APIM) acting as the unified AI gateway. Already deployed — not your concern here. |
| **Spoke** | An isolated workload environment (Foundry project, Container App, Function, etc.) that consumes AI services **through** the hub gateway. |
| **Access Contract** | A Bicep parameter file (`.bicepparam`) + optional policy XML declaring what AI services a spoke needs, with what policies. Deployed as IaC. |
| **Foundry Connection** | An APIM-type connection inside an Azure AI Foundry project that routes model calls through the Citadel gateway. |
| **Service Code** | Short acronym mapping a category of AI services to APIM API IDs (e.g. `LLM`, `DOC`, `SRCH`, `OAIRT`). |

---

## What Gets Created Per Access Contract

| Resource | Naming Pattern | Description |
|----------|----------------|-------------|
| **APIM Product** | `{code}-{BU}-{UseCase}-{ENV}` | One per service code, with attached APIs and policies |
| **APIM Subscription** | `{product}-SUB-01` | Subscription with API key |
| **Key Vault Secrets** (optional) | `{secretName}` | Endpoint URL + API key stored in KV |
| **Foundry Connection** (optional) | `{prefix}-{code}` | APIM connection for Foundry agents |

---

## Prerequisites (Spoke Side)

| Requirement | Details |
|-------------|---------|
| Running Citadel Hub | APIM deployed with published APIs matching your `apiNameMapping` |
| Azure CLI + Bicep | Latest version with `az deployment sub create` support |
| Permissions | `API Management Service Contributor` on APIM RG, `Key Vault Secrets Officer` on target KV (if used), `Contributor` on Foundry RG (if using Foundry connections) |
| Foundry Project | Must exist if you want APIM connections inside Foundry |

---

## Step-by-Step: Create an Access Contract

### 1. Scaffold the Contract Folder

Clone or init the accelerator, then follow the pattern `contracts/<businessunit-usecasename>/<environment>/`:

```powershell
# Option A: clone the accelerator
git clone -b citadel-v1 https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator.git
cd ai-hub-gateway-solution-accelerator/bicep/infra/citadel-access-contracts

# Option B: if using azd
azd init --template Azure-Samples/ai-hub-gateway-solution-accelerator -e my-citadel --branch citadel-v1

# Create contract folder
mkdir -p contracts/myteam-myagent/dev
cd contracts/myteam-myagent/dev

# Copy templates
cp ../../../main.bicepparam main.bicepparam
cp ../../../policies/default-ai-product-policy.xml ai-product-policy.xml
```

> 📂 Full contract folder structure and module reference:
> [citadel-access-contracts/](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/bicep/infra/citadel-access-contracts)
>
> ⚠️ Sample contracts were removed from the repo. Use `main.bicepparam` as your template base.

### 2. Configure the Parameter File

Edit `main.bicepparam`:

```bicep
using '../../../main.bicep'

// ── Hub coordinates (get these from your platform team) ──
param apim = {
  subscriptionId: '<HUB-SUBSCRIPTION-ID>'
  resourceGroupName: '<HUB-APIM-RG>'
  name: '<HUB-APIM-NAME>'
}

// ── Secret storage ──
param useTargetAzureKeyVault = true        // false → credentials in deployment output
param keyVault = {
  subscriptionId: '<SPOKE-SUBSCRIPTION-ID>'
  resourceGroupName: '<SPOKE-KV-RG>'
  name: '<SPOKE-KV-NAME>'
}

// ── Use-case identity ──
param useCase = {
  businessUnit: 'MyTeam'
  useCaseName: 'MyAgent'
  environment: 'DEV'                       // DEV | TEST | PROD
}

// ── Map service codes → APIM API IDs ──
// ⚠️ Order matters: endpoint secret stores the gateway URL for the FIRST API.
//    Put the API matching your SDK first (e.g. azure-openai-api for AzureOpenAI SDK).
param apiNameMapping = {
  LLM: ['azure-openai-api', 'universal-llm-api', 'unified-ai-api']
}

// ── Services to onboard ──
param services = [
  {
    code: 'LLM'
    endpointSecretName: 'MYAGENT-LLM-ENDPOINT'
    apiKeySecretName: 'MYAGENT-LLM-KEY'
    policyXml: loadTextContent('ai-product-policy.xml')   // '' → use default
  }
]

// ── Foundry integration (optional) ──
param useTargetFoundry = true              // false if not using Foundry agents
param foundry = {
  subscriptionId: '<FOUNDRY-SUBSCRIPTION-ID>'
  resourceGroupName: '<FOUNDRY-RG>'
  accountName: '<FOUNDRY-ACCOUNT>'
  projectName: '<FOUNDRY-PROJECT>'
}
param foundryConfig = {
  connectionNamePrefix: ''                 // empty → auto from useCase naming
  deploymentInPath: 'false'                // model name in request body
  isSharedToAll: false
  inferenceAPIVersion: ''                  // empty → APIM defaults
  deploymentAPIVersion: ''
  staticModels: []
  listModelsEndpoint: ''
  getModelEndpoint: ''
  deploymentProvider: ''
  customHeaders: {}
  authConfig: {}
}
```

### 3. Customise the Product Policy (Optional)

The [default policy](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/policies/default-ai-product-policy.xml) includes model restrictions, token limits, and content safety.
For custom policies, edit `ai-product-policy.xml`. Full policy reference:
[citadel-access-contracts-policy.md](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/citadel-access-contracts-policy.md)

**Recommended policy ordering in `<inbound>`:**

```xml
<inbound>
    <base />

    <!-- 1. JWT Authentication (optional) -->
    <set-variable name="jwtRequired" value="true" />

    <!-- 2. App Role Authorization (optional, requires JWT) -->
    <set-variable name="requiredRoles" value="Models.Read" />

    <!-- 3. Model extraction and access control -->
    <include-fragment fragment-id="set-llm-requested-model" />
    <set-variable name="allowedModels" value="gpt-5.4-mini,gpt-5.4-nano" />
    <include-fragment fragment-id="validate-model-access" />

    <!-- 4. Capacity management (subscription level) -->
    <llm-token-limit counter-key="@(context.Subscription.Id)"
        tokens-per-minute="5000"
        estimate-prompt-tokens="false"
        tokens-consumed-header-name="consumed-tokens"
        remaining-tokens-header-name="remaining-tokens"
        token-quota="100000"
        token-quota-period="Monthly"
        retry-after-header-name="retry-after" />

    <!-- 5. Usage attribution (optional) -->
    <set-variable name="appId" value="@(context.Request.Headers.GetValueOrDefault("x-app-id", context.Subscription?.Id ?? "Portal-Admin"))" />
    <set-variable name="customDimension1" value="@(context.Request.Headers.GetValueOrDefault("x-sub-agent-id", "general-agent"))" />
    <set-variable name="customDimension2" value="@(context.Request.Headers.GetValueOrDefault("x-enduser-id", "anonymous-enduser"))" />

    <!-- 6. PII Anonymization (optional) -->
    <set-variable name="piiAnonymizationEnabled" value="true" />

    <!-- 7. Content Safety (optional) -->
    <llm-content-safety backend-id="content-safety-backend" shield-prompt="true">
        <categories output-type="EightSeverityLevels">
            <category name="Hate" threshold="3" />
            <category name="Violence" threshold="3" />
        </categories>
    </llm-content-safety>

    <!-- 8. Response debug headers (dev/test only) -->
    <set-variable name="enableResponseHeaders" value="@(true)" />
</inbound>
```

**Per-model capacity limits** (instead of flat subscription-level):

```xml
<include-fragment fragment-id="set-llm-requested-model" />
<choose>
    <when condition="@((string)context.Variables["requestedModel"] == "gpt-5.4-mini")">
        <llm-token-limit counter-key="@(context.Subscription.Id + "-gpt-5.4-mini")"
            tokens-per-minute="10000" token-quota="100000" token-quota-period="Monthly"
            estimate-prompt-tokens="false" />
    </when>
    <when condition="@((string)context.Variables["requestedModel"] == "DeepSeek-R1")">
        <llm-token-limit counter-key="@(context.Subscription.Id + "-DeepSeek-R1")"
            tokens-per-minute="2000" token-quota="10000" token-quota-period="Weekly"
            estimate-prompt-tokens="false" />
    </when>
    <otherwise>
        <llm-token-limit counter-key="@(context.Subscription.Id + "-default")"
            tokens-per-minute="1000" token-quota="5000" token-quota-period="Monthly"
            estimate-prompt-tokens="false" />
    </otherwise>
</choose>
```

**Throttling alerts** (in `<on-error>` section):

```xml
<on-error>
    <base />
    <set-variable name="productName" value="@(context.Product?.Name?.ToString() ?? "Portal-Admin")" />
    <set-variable name="deploymentName" value="@((string)context.Variables.GetValueOrDefault<string>("requestedModel", "DefaultModel"))" />
    <set-variable name="appId" value="@((string)context.Variables.GetValueOrDefault<string>("appId", context.Subscription?.Id ?? "Portal-Admin-Sub"))" />
    <include-fragment fragment-id="raise-throttling-events" />
</on-error>
```

### 4. Validate and Deploy

```powershell
# Preview (what-if)
az deployment sub what-if `
  --location <REGION> `
  --template-file ../../../main.bicep `
  --parameters main.bicepparam

# Deploy
az deployment sub create `
  --name myteam-myagent-dev `
  --location <REGION> `
  --template-file ../../../main.bicep `
  --parameters main.bicepparam
```

### 5. Verify

```powershell
# Check APIM product
az apim product list `
  --resource-group <HUB-APIM-RG> `
  --service-name <HUB-APIM-NAME> `
  --query "[?contains(name, 'MyTeam')].{Name:name, State:state}"

# Check Key Vault secrets (if using KV)
az keyvault secret list `
  --vault-name <SPOKE-KV-NAME> `
  --query "[?contains(name, 'MYAGENT')].name"
```

---

## Consuming the Gateway from Your App

### Option A: Key Vault (Traditional Apps — NOT for threadlight pilots)

> **Threadlight pilots: do NOT use Option A.** Pulling an APIM subscription
> key from Key Vault means the agent holds a long-lived secret at
> runtime, which violates the keyless-by-mandate posture. Use Option B
> (Foundry Connection) below — APIM still authorizes via the project
> MI token, and the agent never sees a key. Option A remains documented
> for traditional non-Foundry apps that don't have a project-level
> connection surface.

> **Secret name normalization:** The Bicep module lowercases names and replaces
> underscores with hyphens. E.g. `MYAGENT-LLM-ENDPOINT` → `myagent-llm-endpoint`.
> Use the normalized name when retrieving secrets.

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
kv = SecretClient(vault_url="https://<kv-name>.vault.azure.net/", credential=credential)

endpoint = kv.get_secret("myagent-llm-endpoint").value   # normalized name
api_key  = kv.get_secret("myagent-llm-key").value

# Use with Azure OpenAI SDK (requires azure-openai-api FIRST in apiNameMapping)
from openai import AzureOpenAI
client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version="2024-12-01-preview")
response = client.chat.completions.create(model="gpt-5.4-mini", messages=[{"role":"user","content":"Hello"}])
```

### Option B: Foundry Connection (Foundry Agents)

The `connectionName/modelName` pattern routes LLM calls through the APIM gateway.
This works at the **agent level** — not via raw `oai.chat.completions.create()`.

**Hosted Agents (FoundryChatClient):**

Set `MODEL_DEPLOYMENT_NAME` in `agent.yaml` to `connectionName/modelName`:

```yaml
# agent.yaml
environment_variables:
  - name: MODEL_DEPLOYMENT_NAME
    value: Hub-MyTeam-MyAgent-DEV-LLM/gpt-5.4
```

The `FoundryChatClient` in `container.py` resolves the connection automatically:

```python
client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],  # "connectionName/gpt-5.4"
    credential=DefaultAzureCredential(),
)
```

**Prompt Agents (PromptAgentDefinition):**

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

client = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://<foundry-account>.services.ai.azure.com/api/projects/<project>",
    allow_preview=True,
)

# Connection name from access contract output
model_deployment = "Hub-MyTeam-MyAgent-DEV-LLM/gpt-5.4"

agent = client.agents.create_version(
    agent_name="my-agent",
    definition=PromptAgentDefinition(
        model=model_deployment,
        instructions="You are a helpful assistant.",
    ),
)

# Chat via get_openai_client(agent_name=...) + responses.create()
oai = client.get_openai_client(agent_name="my-agent")
response = oai.responses.create(input="Hello", stream=False)
```

> **⚠️ CRITICAL: `connectionName/model` does NOT work with raw OpenAI API calls.**
> Calling `oai.chat.completions.create(model="connName/gpt-5.4")` returns
> `404 DeploymentNotFound`. The routing only works through:
> - `FoundryChatClient(model="connName/model")` (hosted agents)
> - `PromptAgentDefinition(model="connName/model")` (prompt agents)
> - NOT via `oai.chat.completions.create()` or `oai.responses.create()` directly

> **`isSharedToAll` quirk:** The REST API ignores `isSharedToAll=true` on PUT/PATCH
> — it always stays `false`. This does NOT block hosted agent routing (the agent
> identity resolves the connection via `FoundryChatClient`). It may affect prompt
> agents depending on how the caller authenticates.

### Option C: Direct Output (CI/CD Pipelines)

When not using Key Vault, set `useTargetAzureKeyVault = false` but still provide
a placeholder `keyVault` object (Bicep validation requires it):

```bicep
param useTargetAzureKeyVault = false
param keyVault = {
  subscriptionId: '00000000-0000-0000-0000-000000000000'
  resourceGroupName: 'placeholder'
  name: 'placeholder'
}
```

Retrieve credentials from deployment output:

```powershell
$output = az deployment sub show `
  --name myteam-myagent-dev `
  --query properties.outputs.endpoints.value -o json | ConvertFrom-Json

$creds = $output | Where-Object { $_.code -eq 'LLM' }
# $creds.endpoint and $creds.apiKey are available (handle as secrets!)
```

---

## JWT Authentication (Optional Layer)

When the hub is deployed with `entraAuth=true`, you can require JWT on top of the API key.

### Enable in Product Policy

Add to your `ai-product-policy.xml`:

```xml
<inbound>
    <base />
    <set-variable name="jwtRequired" value="true" />
</inbound>
```

### Authentication Matrix

| Scenario | Headers Required | Result |
|----------|-----------------|--------|
| API Key only (JWT disabled) | `api-key: {key}` | ✅ |
| API Key + JWT (JWT enabled) | `api-key: {key}` + `Authorization: Bearer {token}` | ✅ |
| API Key only (JWT enabled) | `api-key: {key}` | ❌ 401 |
| JWT only (no API Key) | `Authorization: Bearer {token}` | ❌ 401 |

### Acquiring the JWT

Two distinct identities are involved:
- **Gateway audience** (`<GATEWAY-APP-ID>`): The Entra app registration configured in the hub's APIM. The hub team provides this.
- **Spoke client identity**: Your app's own service principal or managed identity, which must be granted access to the gateway app role.

**Service principal client:**

```python
from azure.identity import ClientSecretCredential

credential = ClientSecretCredential(
    tenant_id="<TENANT-ID>",
    client_id="<SPOKE-CLIENT-APP-ID>",           # your app's identity
    client_secret="<SPOKE-CLIENT-SECRET>"         # your app's secret
)
token = credential.get_token("api://<GATEWAY-APP-ID>/.default").token
# Pass as: Authorization: Bearer {token}
```

**Managed identity client (recommended on Azure):**

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("api://<GATEWAY-APP-ID>/.default").token
```

> ⚠️ Your spoke identity must be granted the required app role (e.g. `Models.Read`)
> on the gateway app registration. Ask the platform team to assign this via Entra ID.
>
> **Guides:**
> - [JWT Authentication Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/entraid-auth-validation.md)
> - [JWT Client Identity & Permissions](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/jwt-client-identity-permissions.md)

### Custom Identity Provider Override

Access contracts can override gateway JWT defaults per product:

```xml
<inbound>
    <base />
    <set-variable name="jwtRequired" value="true" />
    <!-- Override for Auth0, Okta, or separate Entra tenant -->
    <set-variable name="jwtAudience" value="https://my-custom-api-audience" />
    <set-variable name="jwtIssuer" value="https://my-idp.example.com/" />
    <set-variable name="jwtOpenIdConfigUrl" value="https://my-idp.example.com/.well-known/openid-configuration" />
</inbound>
```

| Variable | Falls Back To (APIM Named Value) |
|----------|----------------------------------|
| `jwtAudience` | `JWT-AppRegistrationId` |
| `jwtIssuer` | `JWT-Issuer` |
| `jwtOpenIdConfigUrl` | `JWT-OpenIdConfigUrl` |

### App Role Authorization

Require specific Entra app roles (enforced after JWT validation, OR logic):

```xml
<set-variable name="jwtRequired" value="true" />
<set-variable name="requiredRoles" value="Models.Read,Agent.Read" />
```

Available gateway app roles: `Task.ReadWrite`, `Models.Read`, `MCP.Read`, `Agent.Read`.

---

## Foundry APIM Connection (Standalone)

If you only need to wire a Foundry project to the APIM gateway **without** a full
Access Contract (e.g. the product/subscription already exists), use the
[`foundry-integration/main.bicep`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/bicep/infra/foundry-integration) template:

```bash
cd bicep/infra/foundry-integration
cp main.bicepparam my-connection.bicepparam
# Edit my-connection.bicepparam with your values

az account set --subscription <foundry-subscription-id>
az deployment group create \
  --name foundry-apim-conn \
  --resource-group <foundry-rg> \
  --template-file main.bicep \
  --parameters my-connection.bicepparam
```

Key parameters (`foundry-integration/main.bicepparam`):

| Parameter | Description |
|-----------|-------------|
| `aiFoundryAccountName` | Name of the AI Foundry account |
| `aiFoundryProjectName` | Name of the AI Foundry project |
| `connectionName` | Name for the connection (e.g. `citadel-hub-connection`) |
| `apimGatewayUrl` | APIM gateway URL (e.g. `https://<apim>.azure-api.net`) |
| `apiPath` | APIM API path (e.g. `models`, `openai`) |
| `apimSubscriptionKey` | Valid APIM subscription key for API access |
| `deploymentInPath` | `'true'` = model in URL path, `'false'` = model in body |
| `inferenceAPIVersion` | API version for inference calls (e.g. `2024-02-01`) |
| `staticModels` | Array of model objects (alternative to dynamic discovery) |
| `customHeaders` | Additional headers for requests |

Verify in Foundry portal: **Project → Operate → Admin → Connected resources**.

---

## Model Discovery Options

| Method | When to Use | Config |
|--------|-------------|--------|
| **APIM Defaults** (recommended) | Standard Citadel hub | Leave `staticModels` empty, no custom discovery params |
| **Static Models** | Fixed known model set | `staticModels = [{ name: 'gpt-5.4-mini', properties: { model: { name: 'gpt-5.4-mini', version: '...', format: 'OpenAI' }}}]` |
| **Custom Discovery** | Non-standard endpoints | Set `listModelsEndpoint`, `getModelEndpoint`, `deploymentProvider` |

> ⚠️ Cannot use both static models and dynamic discovery simultaneously.

---

## Networking Considerations (Spoke Side)

The spoke connects to the Citadel hub gateway over the network. Two patterns:

| Pattern | How It Works | Spoke Requirement |
|---------|-------------|-------------------|
| **Hub-based** | Citadel runs inside the hub VNet | Spoke has direct peering or routes through hub firewall |
| **Spoke-based** | Citadel runs in a dedicated spoke VNet | Spoke routes via hub firewall → Citadel spoke VNet |

As a spoke owner, verify DNS, routing, and firewall/NSG access to the APIM
gateway. The platform team owns the hub-side VNet/APIM/private endpoint config.

- ✅ DNS resolution for `<apim-name>.azure-api.net` resolves to private IP
- ✅ NSG rules allow HTTPS (443) to the APIM subnet
- ✅ If using private endpoints, the relevant Private DNS Zones are linked to your spoke VNet

> **Foundry Network Injection:** The hub now supports `foundryNetworkInjectionEnabled`,
> which injects Foundry instances into the hub VNet with private endpoints. If your
> platform team has enabled this, Foundry-to-APIM traffic stays fully private.

---

## Multi-Service Bundles

A single access contract can onboard multiple AI services. Each service entry
creates a **separate** APIM product, subscription key, endpoint secret, and API key secret.

```bicep
param apiNameMapping = {
  LLM: ['azure-openai-api', 'universal-llm-api']
  DOC: ['document-intelligence-api', 'document-intelligence-api-legacy']
  SRCH: ['azure-ai-search-index-api']
}

param services = [
  {
    code: 'LLM'
    endpointSecretName: 'MYAPP-LLM-ENDPOINT'
    apiKeySecretName: 'MYAPP-LLM-KEY'
    policyXml: loadTextContent('llm-policy.xml')
  }
  {
    code: 'DOC'
    endpointSecretName: 'MYAPP-DOC-ENDPOINT'
    apiKeySecretName: 'MYAPP-DOC-KEY'
    policyXml: loadTextContent('doc-policy.xml')
  }
  {
    code: 'SRCH'
    endpointSecretName: 'MYAPP-SEARCH-ENDPOINT'
    apiKeySecretName: 'MYAPP-SEARCH-KEY'
    policyXml: ''   // use default
  }
]
```

> ⚠️ Mixed bundles require policy awareness — LLM uses token-per-minute limits,
> non-LLM services use request-per-minute limits. Use separate policy XMLs per code.

---

## Advanced Policy Capabilities

Full policy reference with XML snippets:
[citadel-access-contracts-policy.md](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/citadel-access-contracts-policy.md)

| Capability | Key Variable / Snippet | When to Use |
|------------|----------------------|-------------|
| Model access control | `allowedModels` via `validate-model-access` fragment | Restrict which models a spoke can call |
| Token limits (subscription) | `llm-token-limit` (TPM + monthly quota) | Budget control per subscription |
| Token limits (per model) | `llm-token-limit` with `choose` on `requestedModel` | Different budgets per model |
| Content Safety | `llm-content-safety` with category thresholds | Prompt Shield, content filtering (10K char limit) |
| JWT per-product | `jwtRequired=true` | Layered auth on top of API key |
| JWT custom IdP | `jwtAudience`, `jwtIssuer`, `jwtOpenIdConfigUrl` | Auth0, Okta, or separate Entra tenant |
| App role authorization | `requiredRoles` (comma-separated, OR logic) | Require `Models.Read`, `Agent.Read`, etc. |
| Usage attribution | `appId`, `customDimension1`, `customDimension2` | Chargeback via `x-app-id`, `x-sub-agent-id`, `x-enduser-id` headers |
| Response debug headers | `enableResponseHeaders = @(true)` | Exposes `UAIG-*` headers (auth type, model, backend, cache, region) |
| PII anonymization | `piiAnonymizationEnabled`, confidence, exclusions, regex | Replace PII with placeholders before LLM, restore in response |
| PII audit logging | `piiStateSavingEnabled` via `pii-state-saving` fragment | Log PII processing to Event Hub for compliance |
| Throttling alerts | `raise-throttling-events` in `<on-error>` | Feed 429 events to App Insights for alerting |

### PII Anonymization Setup

PII works in two phases: inbound anonymization → outbound deanonymization.

```xml
<!-- Inbound: detect and replace PII -->
<set-variable name="piiAnonymizationEnabled" value="true" />
<set-variable name="piiConfidenceThreshold" value="0.8" />
<set-variable name="piiEntityCategoryExclusions" value="PersonType" />
<set-variable name="piiDetectionLanguage" value="en" />     <!-- "auto" for multilingual -->
<set-variable name="piiInputContent" value="@(context.Request.Body.As<string>(preserveContent: true))" />
<include-fragment fragment-id="pii-anonymization" />
<set-body>@(context.Variables.GetValueOrDefault<string>("piiAnonymizedContent"))</set-body>
```

```xml
<!-- Outbound: restore original PII -->
<set-variable name="piiDeanonymizeContentInput" value="@(context.Response.Body.As<string>(preserveContent: true))" />
<include-fragment fragment-id="pii-deanonymization" />
<set-variable name="piiStateSavingEnabled" value="true" />  <!-- optional: audit log -->
<include-fragment fragment-id="pii-state-saving" />
<set-body>@(context.Variables.GetValueOrDefault<string>("piiDeanonymizedContentOutput"))</set-body>
```

Custom regex patterns can extend NLP detection for domain-specific PII (credit cards, passport numbers, etc.).
See [PII Masking Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/pii-masking-apim.md) for full details.

### Response Debug Headers (`UAIG-*`)

When `enableResponseHeaders` is `true`, these headers are injected in the response:

| Header | Description |
|--------|-------------|
| `UAIG-Auth-Type` | `api-key`, `jwt`, `api-key-jwt`, or `none` |
| `UAIG-Model-Id` | Requested model name |
| `UAIG-Backend` | Selected backend pool |
| `UAIG-Cache-Operation` | Cache hit/miss/skip |
| `UAIG-Is-Streaming` | Whether streaming was used |
| `UAIG-Request-Id` | APIM correlation ID |
| `UAIG-Gateway-Region` | Gateway Azure region |

> ⚠️ Disable in production — these headers expose internal gateway state.

---

## Validation Notebooks

After deploying an access contract, use the repo's
[validation notebooks](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/validation)
to verify end-to-end connectivity:

| Need to Validate | Notebook |
|-----------------|----------|
| Access contract deployment + keys | [`citadel-access-contracts-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-access-contracts-tests.ipynb) |
| Foundry / LangChain / MAF consumption | [`citadel-agent-frameworks-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-agent-frameworks-tests.ipynb) |
| JWT + role enforcement | [`citadel-jwt-authentication-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-jwt-authentication-tests.ipynb) |
| PII masking/blocking policies | [`citadel-pii-processing-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-pii-processing-tests.ipynb) |
| Unified AI API routing across providers | [`citadel-unified-ai-api-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-unified-ai-api-tests.ipynb) |
| Universal LLM API all-models validation | [`citadel-universal-llm-api-all-models-tests.ipynb`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/citadel-universal-llm-api-all-models-tests.ipynb) |

> Requires Python with packages from [`validation/requirements.txt`](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/requirements.txt).

---

## Platform Team Handoff

When onboarding a new spoke, request the following from the Citadel platform team:

- APIM subscription ID, resource group, and APIM instance name
- Available APIM API IDs and paths (to populate `apiNameMapping`)
- Supported model names and deployment formats
- Whether `/deployments` discovery is enabled on the gateway
- Whether JWT, PII, Content Safety, or custom IdP support is configured
- Gateway app registration ID (if using JWT auth)
- Network routing: private endpoint DNS, firewall rules, VNet peering status

Reference the [LLM Backend Onboarding module](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1/bicep/infra/llm-backend-onboarding) for platform-team context
on how backends are onboarded to the hub (not a spoke deployment step).

> **Additional guides:**
> - [Full Deployment Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/full-deployment-guide.md)
> - [Network Approach Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/network-approach.md)
> - [Citadel Sizing Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/citadel-sizing-guide.md)
> - [Parameters Usage Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/parameters-usage-guide.md)
> - [OpenAI Compatible API Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/openai-compatible-api-guide.md) *(NEW)*
> - [Unified AI API Type Onboarding](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/unified-ai-api-type-onboarding.md) *(NEW)*
> - [Agent Governance Toolkit Integration](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/agent-governance-toolkit-integration.md) *(NEW)*

---

## Service Code Reference

Default APIM API mappings provisioned by the Citadel hub:

| Code | APIs | Description |
|------|------|-------------|
| `LLM` | `azure-openai-api`, `universal-llm-api`, `unified-ai-api` | Large language model inference (OpenAI V1 compatible) |
| `OAIRT` | `openai-realtime-ws-api` | OpenAI realtime WebSocket API |
| `DOC` | `document-intelligence-api`, `document-intelligence-api-legacy` | Document Intelligence |
| `SRCH` | `azure-ai-search-index-api` | Azure AI Search |

The **Unified AI API** (`unified-ai-api`) now supports multi-provider routing including
Azure OpenAI, Foundry Models, and Amazon Bedrock — all through a single OpenAI-compatible
endpoint at `https://<apim-gateway>/unified-ai/v1/*`. See the
[OpenAI Compatible API Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/openai-compatible-api-guide.md).

Custom APIs can be added to `apiNameMapping` as long as they exist in APIM.

---

## Unified AI API (OpenAI-Compatible Endpoint)

The Unified AI API provides a single OpenAI-compatible surface that routes across
multiple backend providers. Spoke apps can use standard OpenAI SDKs without code changes.

**Base URL:** `https://<apim-gateway>/unified-ai/v1`

```python
from openai import OpenAI

# Works with any backend behind the gateway (Azure OpenAI, Foundry, Bedrock)
client = OpenAI(
    base_url="https://<apim-gateway>/unified-ai/v1",
    api_key="<your-apim-subscription-key>"
)
response = client.chat.completions.create(
    model="gpt-4o",          # model alias or deployment name
    messages=[{"role": "user", "content": "Hello"}]
)
```

Key features:
- **Multi-provider routing** — Azure OpenAI, Foundry Models, Amazon Bedrock behind one endpoint
- **Model aliases** — `priority` (failover) and `weighted` (load distribution) routing
- **Cross-model fallback** — automatic retry across backends
- **Responses API** — supported via stateful `responses_id` caching

> See [OpenAI Compatible API Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/openai-compatible-api-guide.md) for full details.

---

## Agent Governance Toolkit (AGT) Integration

For advanced agent-level governance beyond API gateway controls, spoke agents can
integrate the [Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
with Citadel.

| Capability | What It Adds |
|------------|-------------|
| **Agent identity** | Ed25519 / SPIFFE-based cryptographic identity per agent |
| **Runtime policy enforcement** | Agent-level policies beyond APIM (tool restrictions, data access) |
| **Trust scoring** | Dynamic trust assessment for agent actions |
| **Tamper-evident audit** | Immutable audit logs with correlation via `x-ms-request-id` |
| **Citadel correlation** | `CitadelAuditExporter` links AGT traces to Citadel gateway telemetry |

> See [AGT Integration Guide](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/agent-governance-toolkit-integration.md) for setup.

---

## Checklist: Spoke Onboarding

- [ ] Obtain hub coordinates from platform team (APIM subscription ID, RG, name)
- [ ] Decide credential strategy: Key Vault, Foundry Connection, or Direct Output
- [ ] Create contract folder: `contracts/<bu>-<usecase>/<env>/`
- [ ] Configure `main.bicepparam` with hub + spoke coordinates
- [ ] Customize product policy XML (or use default)
- [ ] Run `what-if` to preview changes
- [ ] Deploy with `az deployment sub create`
- [ ] Verify APIM product and subscription created
- [ ] Verify secrets in Key Vault (if applicable)
- [ ] Verify Foundry connection (if applicable)
- [ ] Test end-to-end: agent → gateway → AI backend
- [ ] Commit contract files to source control for audit trail

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| **404 DeploymentNotFound via `oai.chat.completions.create()`** | `connectionName/model` only works at agent level, not raw OpenAI API | Use `FoundryChatClient(model="conn/model")` for hosted agents, or `PromptAgentDefinition(model="conn/model")` for prompt agents |
| **`isSharedToAll` stuck at `false`** | REST API (all versions) ignores the flag on PUT/PATCH | Does NOT block hosted agent routing. For prompt agents, add caller OID to `sharedUserList` |
| **Hub KV `Forbidden: ForbiddenByConnection`** | Hub Key Vault has public network access disabled | Use Option C (direct output) or deploy from inside the hub VNet |
| **Tool calls fail with `server_error`** | APIM policy `allowedModels` doesn't include your model, or TPM too low for tool-heavy queries | Update `allowedModels` in policy XML. Bump TPM to ≥10K for agents with MCP tools |
| **`apiPath` wrong → model discovery fails** | `openai` path has no `/models` endpoint, `models` path does | For APIM defaults discovery use `apiPath='models'`. For static models use `apiPath='openai'` with `deploymentInPath='true'` |
| **Static models not appearing in connection metadata** | Bicep module may use dynamic discovery defaults even when staticModels passed | Set `models` directly in metadata as stringified JSON via REST PUT |
| **Connection category `ApiKey` vs `ApiManagement`** | Portal "API Key" creates `ApiKey` category, Bicep creates `ApiManagement` | Both work for routing. `ApiManagement` is preferred (has model discovery) |
| **Cross-region (spoke ≠ hub region)** | Foundry in northcentralus, APIM in swedencentral | Works — connection routes over public internet. VNet peering needed only for private endpoints |

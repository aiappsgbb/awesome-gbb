---
name: citadel-spoke-onboarding
description: >
  Onboard a Foundry project as a spoke into an AI Citadel Governance Hub.
  Covers Access Contracts, APIM connections, product policies, JWT auth.
  USE FOR: citadel spoke onboarding, access contract, connect foundry to citadel,
  APIM connection, bring your own ai gateway, govern agent, citadel JWT auth,
  citadel product policy, unified ai api, citadel AGT, vnet-isolated citadel
  spoke, foundry-vnet-deploy spoke onboarding.
  DO NOT USE FOR: deploying the Citadel hub itself, APIM infrastructure,
  hub networking, hub provisioning, hub sizing, llm backend onboarding,
  deploying model backends, apim backend pools, hub policy fragment deployment,
  spoke-side VNet/peering creation (use foundry-vnet-deploy).
metadata:
  version: "2.0.0"
---

# Citadel Spoke Onboarding — Reference Guide

How to connect a GenAI application or Microsoft Foundry project to an
**existing** AI Citadel Governance Hub. Controls cover the traffic actually routed
through the gateway, not every agent action or a compliance certification.

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
> so the agent does not retrieve the subscription key. The pinned connection
> uses `authType: ApiKey`; this is **not end-to-end keyless**. Caller-to-Foundry
> Entra authentication, connection-managed secret custody and downstream APIM
> authentication are separate boundaries. JWT requires its own approved setup
> and positive/negative runtime evidence; no MI-to-APIM JWT flow is implied.
> If a customer insists on
> Option A for a non-threadlight reason, document the deviation in
> SPEC § 11b explicitly.

> **Source:** [exact hub/spoke revision](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/63f0f812474e713916dc909494d655246783a1d9).
> The [pin record](references/upstream-pin.md) separates source comparison from
> live compatibility. `citadel-v1` is a freshness signal, not a deployment input.
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

Before any operator Azure call, apply
[`azure-tenant-isolation`](../azure-tenant-isolation/SKILL.md): paired isolated
CLI/AZD context and the approved exact tenant/subscription. Assert the target
immediately before writes. Read-only inventory grants no repair authority.

---

## Step-by-Step: Create an Access Contract

### 1. Scaffold the Contract Folder

Materialize the exact reviewed hub revision, then follow
`contracts/<businessunit-usecasename>/<environment>/`. Do not overwrite an existing
checkout, deployed contract or policy to align a pin.

```bash
PINNED_SHA="63f0f812474e713916dc909494d655246783a1d9"
git clone --filter=blob:none --no-checkout https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator.git
cd ai-hub-gateway-solution-accelerator
git fetch --depth 1 origin "$PINNED_SHA"
git checkout --detach "$PINNED_SHA"
test "$(git rev-parse HEAD)" = "$PINNED_SHA"
cd bicep/infra/citadel-access-contracts

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
> Review `allowedModels` explicitly: this revision's default LLM policy allows
> `gpt-4.1,gpt-5.4-mini`, unlike the older policy's broader list. Existing
> approved policies are not replaced automatically. Leave optional key rotation
> and additional-gateway settings disabled unless separately approved.

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
    <!-- ⚠️ For Foundry agents with MCP tools, use ≥100K TPM.
         A single CI query with 10-20 tool calls consumes 50-80K tokens.
         10K TPM causes server_error after the first tool call completes. -->
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
> (Foundry Connection) below — the platform connection retains the APIM key,
> and the agent does not retrieve it. This does not establish downstream JWT.
> Option A remains documented
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

Use the current [canonical unified azure.yaml](../foundry-hosted-agents/references/yaml/azure.yaml)
and [runtime main.py](../foundry-hosted-agents/references/python/main.py) unchanged.
Set the azd environment's `AZURE_AI_MODEL_DEPLOYMENT_NAME` to the selected
`connectionName/modelName`, for example `Hub-MyTeam-MyAgent-DEV-LLM/gpt-5.4-mini`.
This structural excerpt shows the existing hosted service key, not a full
deployment template:

```yaml
services:
  my-agent:
    environmentVariables:
      - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
        value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}
```

The canonical runtime passes that value to `FoundryChatClient(model=...)`.
Keep its [dependency cohort](../foundry-hosted-agents/references/python/pyproject.toml)
and deployment preflight; do not substitute the Toolbox or management SDK pins.
`FOUNDRY_PROJECT_ENDPOINT` is platform-injected, never a declared service variable.
This wiring correction is not live proof for the selected gateway/model.

The [pinned connection module](https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/63f0f812474e713916dc909494d655246783a1d9/bicep/infra/citadel-access-contracts/modules/foundryConnection.bicep)
stores the APIM key in the managed connection. An Entra-authenticated caller to
Foundry does not make that downstream credential a JWT. Observe the actual
connection category, target and auth type through credential-free GET; never
retrieve its secret as a probe. If end-to-end keylessness is required, stop for
an independently supported and authorized design; no auth migration is supplied here.

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

The spoke connects to the Citadel hub gateway over the network. Three patterns:

| Pattern | How It Works | Spoke Requirement |
|---------|-------------|-------------------|
| **Hub-based** | Citadel runs inside the hub VNet | Spoke has direct peering or routes through hub firewall |
| **Spoke-based** | Citadel runs in a dedicated spoke VNet | Spoke routes via hub firewall → Citadel spoke VNet |
| **VNet-isolated spoke** (e.g., Foundry-in-VNet from [`foundry-vnet-deploy`](../foundry-vnet-deploy/)) | Spoke Foundry account + project sit inside the customer's own private VNet (private endpoints, no public access) | Bidirectional peering spoke ↔ hub VNet **plus** a VNet link from `privatelink.azure-api.net` to the spoke VNet. `foundry-vnet-deploy` Step 8d / 12D auto-creates the spoke side; the hub team runs the emitted reverse-peering command. |

As a spoke owner, verify DNS, routing, and firewall/NSG access to the APIM
gateway. The platform team owns the hub-side VNet/APIM/private endpoint config.

- ✅ DNS resolution for `<apim-name>.azure-api.net` resolves to private IP
- ✅ NSG rules allow HTTPS (443) to the APIM subnet
- ✅ If using private endpoints, the relevant Private DNS Zones are linked to your spoke VNet

> **Foundry Network Injection:** The hub now supports `foundryNetworkInjectionEnabled`,
> which injects Foundry instances into the hub VNet with private endpoints. If your
> platform team has enabled this, Foundry-to-APIM traffic stays fully private.

### Combining with `foundry-vnet-deploy`

When the Foundry project to be onboarded was deployed by
[`foundry-vnet-deploy`](../foundry-vnet-deploy/) (i.e., it lives inside a
customer-private VNet with public access disabled), the order of operations
and auth posture are constrained:

**Recommended ordering**

1. Run [`azure-tenant-isolation`](../azure-tenant-isolation/) so all
   subsequent `az` commands land in the intended subscription.
2. Run [`foundry-vnet-deploy`](../foundry-vnet-deploy/). When prompted in
   **Step 8d (Citadel hub integration)**, supply `hubVnetResourceId` and
   `apimDnsZoneResourceId`; the deployment creates the spoke-side peering
   and the `privatelink.azure-api.net` VNet link in the same pass.
3. Run the one-line `hubReversePeeringCommand` emitted by the deployment
   (or hand it to the hub team to run with their RBAC).
4. Run **Step 12D** verification — both peerings `Connected`,
   `{apim}.azure-api.net` resolves to a private IP, `Test-NetConnection
   ... 443` succeeds.
5. Run this skill (`citadel-spoke-onboarding`) against the Foundry project.
6. **Use Option B (Foundry Connection)**, not Option A (KV secret pull) —
   see the next section for why this is non-negotiable for VNet-isolated
   spokes.

**Auth posture (mandatory for VNet-isolated spokes)**

Option A retrieves the APIM subscription key from Key Vault at runtime. In
a VNet-isolated spoke this means the agent must:
- Reach KV over the network (extra private endpoint + DNS link).
- Hold a static subscription key (defeats keyless-by-mandate posture).

**Option B** keeps the static key in the Foundry connection, not in agent code.
Private networking does not alter `authType: ApiKey` into JWT. Keep caller-to-Foundry
identity, connection custody and downstream APIM authentication distinct.
The hub pin's positive dual-auth JWT acceptance remains separate and unproven;
an APIM inventory match or private DNS lookup cannot close it.

**Pre-flight checklist before running this skill**

```powershell
# Run these from inside the spoke VNet (peered VM, Bastion, or VPN client)
az network vnet peering show --resource-group <spoke-rg> --vnet-name <spoke-vnet> `
  --name peering-to-hub --query peeringState -o tsv         # → "Connected"
Resolve-DnsName "<apim>.azure-api.net"                      # → private IP
Test-NetConnection -ComputerName "<apim>.azure-api.net" -Port 443

```

Read the selected **project** identity separately through its credential-free ARM
GET. Account identity is not project identity, and neither proves which credential
the connection uses downstream. Do not create or grant an identity to satisfy
this read-only check.

If any check fails, **stop** and fix the network plumbing in
`foundry-vnet-deploy` Step 12D before proceeding — onboarding the spoke
against a misconfigured network will silently inject an APIM connection
whose first call times out.

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

## Hub-side Access Contract probe

Use the canonical helper for **hub ARM inventory only**, after tenant isolation
and approval of the exact read scope. It does not observe a Foundry connection,
perform inference, verify private routing or enforce policy.
Use `azure-mgmt-apimanagement~=5.0.0`, `azure-mgmt-resource~=23.1.0` and
`azure-identity~=1.25.3` in the operator's isolated environment. Add this skill's
`references/python` directory to `PYTHONPATH`; import the actual module:

```python
from access_contract_probe import probe_hub_contract

result = probe_hub_contract(
    hub_rg="<hub-resource-group>",
    spoke_id="my-spoke",
    subscription="<hub-subscription-id>",
    apim_name="<hub-apim>",
    api_id="azure-openai-api",
    product_id="LLM-MyTeam-MyAgent-DEV",
    credential=credential,  # already-approved credential for this isolated context
)
```

Returns a never-raising `dict`. **Version 2 migration:** consumers must not use
the former `foundry_connection_status="ok"` as hub acceptance. It is now always
`unverified`; use `hub_contract_status` for this narrower inventory result and
collect Foundry/runtime evidence independently. This intentional contract change
requires downstream handling before adopting skill 2.0.0.

| Key                          | Type                            | Meaning                                                                                   |
|------------------------------|---------------------------------|-------------------------------------------------------------------------------------------|
| `api_present`                | `bool`                          | Exact API GET returned the selected resource ID. |
| `product_assigned`           | `bool`                          | Exact product GET matched scope AND native `product_api.check_entity_exists` confirmed this API association. |
| `foundry_connection_status`  | `"unverified"` | No Foundry observation is made, even if every hub check passes. |
| `hub_contract_status`        | `"ok"` \| `"missing"` \| `"errored"` | All three hub signals present / at least one absent / any unreadable or invalid observation. |
| `evidence_scope`             | `"hub-arm-inventory"` | Not runtime, transport, credentials or enforcement proof. |
| `subscription_key_present`   | `bool`                          | Legacy name: active subscription metadata with exact product scope in this APIM. No key is retrieved or tested. |
| `rate_limit_policy`          | `dict` \| `None`                 | Optional `{"raw_xml": ...}` API-level policy snapshot. Not parsed limits or effective product/global policy enforcement; keep XML private. |
| `last_probe_at`              | `str`                           | ISO-8601 UTC timestamp                                                                    |
| `confidence`                 | `float` 0.0–1.0                 | Legacy hub inventory coverage only: `1.0` for all three signals. Never readiness confidence; `hub_contract_status` and errors remain authoritative. |
| `missing_perms`              | `list[str]`                     | Human-readable explanations when the probe can't make conclusions (perms, ambiguity, SDK absent) |

**Behavioral guarantees** (offline regressions in
`scripts/tests/test_citadel_access_contract_probe.py` and
`scripts/tests/test_citadel_spoke_contract.py`, including native SDK HTTP transport):

- **Never raises.** SDK exceptions become an operation/type/status diagnostic in
  `missing_perms`, without raw exception bodies. Already verified observations
  are preserved; the failed observation never becomes a pass.
  `KeyboardInterrupt` / `SystemExit` propagate.
- **Missing vs unreadable.** Resource/binding 404 is absence; 403, malformed
  resource IDs or failed inventory pages are errors, not permission to onboard
  or repair. Subscription pagination completes before any positive result.
  Exact absolute product scope or documented `/products/<id>` within the selected
  APIM is accepted; display-name substrings, all-API and other-product scopes are not.
- **Policy readback.** Optional API policy 404 leaves no snapshot; other errors
  are explicit. Product/global policies and live behavior require separate evidence.
- **APIM auto-discovery.** Pass `apim_name=None` and the helper queries the hub RG for `Microsoft.ApiManagement/service` resources. Exactly one match → use it. Zero or more than one → error path with explanation in `missing_perms`.
- **Env-var fallback for hub RG.** If `hub_rg` is empty, the helper reads `TL_CITADEL_HUB_RG` from the environment (backwards-compat with threadlight v0.5.x runtime).
- **Env-var fallback for subscription.** If `subscription` is empty, the helper reads `AZURE_SUBSCRIPTION_ID`. If still empty, returns the error-path dict.
- **Guarded azure imports.** The module's azure SDK imports are wrapped in `try/except ImportError` so unit tests run under CI without `azure-mgmt-apimanagement` / `azure-mgmt-resource` / `azure-identity` installed. When called without the SDK, the helper returns an error dict with `"azure SDK not available: pip install azure-mgmt-apimanagement azure-mgmt-resource azure-identity"` in `missing_perms`.

> **MUST:** Use the canonical reference verbatim — do NOT redefine inline.
> The single source of truth is
> [`references/python/access_contract_probe.py`](references/python/access_contract_probe.py).
> Repo invariant: AGENTS.md §7 (SSOT).

Use the [opt-in manual acceptance protocol](test-fixture/manual_consumer_prompt.md)
for the separately authorized live owner. It requires no hub deployment and
keeps hub inventory, Hosted gateway routing, JWT and cleanup outcomes separate.

### Naming convention

The probe assumes:
- API ID: `f"{spoke_id}-api"`
- Product ID: `f"{spoke_id}-product"`

These defaults are retained only for legacy callers. The native contract uses
shared APIs from `apiNameMapping` and products `{code}-{BU}-{UseCase}-{ENV}`.
Pass `api_id` / `product_id` explicitly for those deployments and verify every
required API, rather than guessing IDs from a display name.

### Cross-skill: threadlight self-verify integration

[`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy)
NET-501 / NET-502 self-verify steps flip from `kind: manual` to
`kind: sibling-skill` against this helper in threadlight v0.5.2 (tracker:
[issue #246](https://github.com/aiappsgbb/awesome-gbb/issues/246)).
Consumers gain machine-readable partial hub inventory without forcing
the threadlight runtime to take an `azure-mgmt-*` dependency — the helper
gracefully degrades to the "SDK not installed" error path when run inside
threadlight's stdlib-only worker shell.
Any downstream readiness gate must adopt the version-2 output semantics and
retain separate credential-free Foundry connection, private-route, actual
downstream authentication and correlated runtime evidence.

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

**If the spoke itself sits in a private VNet** (e.g., deployed by
[`foundry-vnet-deploy`](../foundry-vnet-deploy/)), the operator must also
hand the hub team the spoke's network identity so the hub side of the
peering can be created with their RBAC:

- Spoke VNet ARM resource ID (full `/subscriptions/.../virtualNetworks/<vnet>`)
- Spoke VNet address space (e.g., `10.50.0.0/16`)
- Agent subnet name (default `agent-subnet`) and any custom NSG attached
- The one-line `hubReversePeeringCommand` emitted by `foundry-vnet-deploy`
  (it's pre-formatted for the hub team to paste into `az`)

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
| **Tool calls fail with `server_error`** | APIM policy TPM too low — agent exhausts token budget on 2nd+ turn of tool loop | **Bump TPM to ≥100K** for agents with MCP tools. CI-style agents with 10-20 tool calls consume 50-80K tokens per query. 10K TPM causes `server_error` after the first tool call completes. Also check `allowedModels` includes your model. |
| **`apiPath` wrong → model discovery fails** | `openai` path has no `/models` endpoint, `models` path does | For APIM defaults discovery use `apiPath='models'`. For static models use `apiPath='openai'` with `deploymentInPath='true'` |
| **Static models not appearing in connection metadata** | Bicep module may use dynamic discovery defaults even when staticModels passed | Set `models` directly in metadata as stringified JSON via REST PUT |
| **Connection category `ApiKey` vs `ApiManagement`** | Portal "API Key" creates `ApiKey` category, Bicep creates `ApiManagement` | Both work for routing. `ApiManagement` is preferred (has model discovery) |
| **Cross-region (spoke ≠ hub region)** | Foundry in northcentralus, APIM in swedencentral | Works — connection routes over public internet. VNet peering needed only for private endpoints |

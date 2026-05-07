---
name: citadel-spoke-onboarding
description: >
  Onboard a GenAI app or Microsoft Foundry project as a spoke into an existing
  AI Citadel Governance Hub. Covers Access Contracts, Foundry APIM connections,
  Key Vault secret wiring, product policies, JWT auth, and networking.
  USE FOR: citadel spoke, onboard agent to citadel, access contract, connect
  foundry to citadel, APIM connection, citadel onboarding, govern agent,
  AI gateway spoke, citadel compliant agent, citadel access contract,
  connect to governance hub, citadel JWT auth, citadel product policy.
  DO NOT USE FOR: deploying the Citadel hub itself, APIM infrastructure,
  hub networking, hub provisioning, hub sizing.
---

# Citadel Spoke Onboarding — Reference Guide

How to connect a GenAI application or Microsoft Foundry project to an
**existing** AI Citadel Governance Hub so that all AI traffic is governed,
observable, and compliant.

> Source accelerator: <https://aka.ms/ai-hub-gateway> (branch `citadel-v1`)

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

Follow the pattern `contracts/<businessunit-usecasename>/<environment>/`:

```powershell
# From the citadel-access-contracts root
mkdir -p contracts/myteam-myagent/dev
cd contracts/myteam-myagent/dev

# Copy templates
cp ../../../main.bicepparam main.bicepparam
cp ../../../policies/default-ai-product-policy.xml ai-product-policy.xml
```

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
param apiNameMapping = {
  LLM: ['universal-llm-api', 'azure-openai-api', 'unified-ai-api']
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

The default policy includes model restrictions, token limits, and content safety.
For custom policies, edit `ai-product-policy.xml`. Available policy snippets:

| Snippet | Purpose | Key Variables |
|---------|---------|---------------|
| `set-llm-requested-model` + `validate-model-access` | Restrict allowed models | `allowedModels` (comma-separated, no spaces) |
| `llm-token-limit` | Token-per-minute and monthly quota | `tokens-per-minute`, `token-quota`, `token-quota-period` |
| Content Safety fragments | Prompt Shield, content filtering | Configured at hub level |
| `jwt-auth.xml` snippet | Require JWT Bearer on top of API key | Sets `jwtRequired=true` |

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

### Option A: Key Vault (Traditional Apps)

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
kv = SecretClient(vault_url="https://<kv-name>.vault.azure.net/", credential=credential)

endpoint = kv.get_secret("MYAGENT-LLM-ENDPOINT").value
api_key  = kv.get_secret("MYAGENT-LLM-KEY").value

# Use with OpenAI SDK
from openai import AzureOpenAI
client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version="2024-12-01-preview")
response = client.chat.completions.create(model="gpt-4o", messages=[{"role":"user","content":"Hello"}])
```

### Option B: Foundry Connection (Foundry Agents)

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

# Connection name pattern: <BU>-<UseCase>-<ENV>-<ServiceCode>
connection_name = "MyTeam-MyAgent-DEV-LLM"
model_deployment = f"{connection_name}/gpt-4o"

client = AIProjectClient(
    credential=DefaultAzureCredential(),
    endpoint="https://<foundry-account>.cognitiveservices.azure.com/"
)
agent = client.agents.create_agent(
    model=model_deployment,
    name="my-agent",
    instructions="You are a helpful assistant."
)
```

### Option C: Direct Output (CI/CD Pipelines)

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

```python
from azure.identity import ClientSecretCredential

credential = ClientSecretCredential(
    tenant_id="<TENANT-ID>",
    client_id="<APP-REGISTRATION-CLIENT-ID>",
    client_secret="<CLIENT-SECRET>"            # from Key Vault: ENTRA-APP-CLIENT-SECRET
)
token = credential.get_token("api://<APP-REGISTRATION-CLIENT-ID>/.default").token
# Pass as: Authorization: Bearer {token}
```

---

## Foundry APIM Connection (Standalone)

If you only need to wire a Foundry project to the APIM gateway **without** a full
Access Contract (e.g. the product/subscription already exists):

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

Key parameters:

| Parameter | Description |
|-----------|-------------|
| `projectResourceId` | Full resource ID of the AI Foundry project |
| `apimResourceId` | Full resource ID of the APIM service |
| `apiName` | APIM API name to connect to |
| `apimSubscriptionName` | Subscription name for API key (default: `master`) |
| `deploymentInPath` | `'true'` = model in URL path, `'false'` = model in body |
| `inferenceAPIVersion` | API version for inference calls |
| `staticModels` | Array of model objects (alternative to dynamic discovery) |

Verify in Foundry portal: **Project → Operate → Admin → Connected resources**.

---

## Model Discovery Options

| Method | When to Use | Config |
|--------|-------------|--------|
| **APIM Defaults** (recommended) | Standard Citadel hub | Leave `staticModels` empty, no custom discovery params |
| **Static Models** | Fixed known model set | `staticModels = [{ name: 'gpt-4o', properties: { model: { name: 'gpt-4o', version: '...', format: 'OpenAI' }}}]` |
| **Custom Discovery** | Non-standard endpoints | Set `listModelsEndpoint`, `getModelEndpoint`, `deploymentProvider` |

> ⚠️ Cannot use both static models and dynamic discovery simultaneously.

---

## Networking Considerations (Spoke Side)

The spoke connects to the Citadel hub gateway over the network. Two patterns:

| Pattern | How It Works | Spoke Requirement |
|---------|-------------|-------------------|
| **Hub-based** | Citadel runs inside the hub VNet | Spoke has direct peering or routes through hub firewall |
| **Spoke-based** | Citadel runs in a dedicated spoke VNet | Spoke routes via hub firewall → Citadel spoke VNet |

In both cases, spoke agents reach the APIM gateway via private endpoint or
VNet-integrated DNS. Ensure:

- ✅ DNS resolution for `<apim-name>.azure-api.net` resolves to private IP
- ✅ NSG rules allow HTTPS (443) to the APIM subnet
- ✅ If using private endpoints, the relevant Private DNS Zones are linked to your spoke VNet

---

## Service Code Reference

Default APIM API mappings provisioned by the Citadel hub:

| Code | APIs | Description |
|------|------|-------------|
| `LLM` | `azure-openai-api`, `universal-llm-api`, `unified-ai-api` | Large language model inference |
| `OAIRT` | `openai-realtime-ws-api` | OpenAI realtime WebSocket API |
| `DOC` | `document-intelligence-api`, `document-intelligence-api-legacy` | Document Intelligence |
| `SRCH` | `azure-ai-search-index-api` | Azure AI Search |

Custom APIs can be added to `apiNameMapping` as long as they exist in APIM.

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

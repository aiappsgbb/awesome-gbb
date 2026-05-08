---
name: foundry-cross-resource
description: >
  Cross-resource model invocation in Microsoft Foundry via AI Gateway (APIM).
  USE FOR: connectionName/deploymentName, cross-resource model access, AI Gateway,
  APIM connection, ApiManagement connection, remote model invocation, Foundry gateway,
  use models from another resource, cross-project model access, APIM AI gateway setup,
  Foundry Agent Service gateway, model gateway connection, remote deployment.
  DO NOT USE FOR: single-resource model calls, Azure tenant isolation (use azure-tenant-isolation),
  Foundry project creation, APIM creation from scratch.
---

# Cross-Resource Model Invocation via Foundry AI Gateway

## Overview

This skill documents how to invoke AI models deployed on a **different** Microsoft Foundry resource/project using the `connectionName/deploymentName` pattern routed through an **Azure API Management (APIM) AI Gateway**.

### Architecture

```
Source Project (your project)
  → ApiManagement connection (category: "ApiManagement")
    → APIM Gateway (azure-api.net)
      → Backend AI Services resource (remote resource with models)
```

### Key Pattern

```python
model = "connection-name/deployment-name"  # e.g. "remote-gw/gpt-5.4-mini"
resp = oai.responses.create(model=model, input="...", max_output_tokens=50)
```

---

> [!IMPORTANT]
> **Before using AI Gateway, ALL of the following must be in place.** If any is missing,
> you'll get 404/401/500 errors. Check each one:
>
> 1. ✅ **Remote resource exists** with the model deployed (e.g., `gpt-5.4-mini` on a Sweden Central AI Services account). Not all models are available in all regions — verify with `az cognitiveservices account list-models`.
> 2. ✅ **APIM instance** exists (BasicV2+ or StandardV2) with **system-assigned managed identity enabled**
> 3. ✅ **APIM MI has RBAC** — `Cognitive Services User` on the remote AI Services resource
> 4. ✅ **APIM has an API** with `serviceUrl` pointing to `https://<remote-resource>.services.ai.azure.com`
> 5. ✅ **APIM API policy** has MI auth + api-version stripping (see Step 1c below)
> 6. ✅ **Foundry project has an `ApiManagement` connection** (NOT `AIServices`, NOT `AzureOpenAI`) pointing to `https://<apim>.azure-api.net/<api-path>/openai/v1` with APIM subscription key
> 7. ✅ **Connection has `modelDiscovery` metadata** configured (dynamic or static — see Step 2)
> 8. ✅ **`MODEL_DEPLOYMENT_NAME`** in agent.yaml is `connectionName/deploymentName` (e.g., `remote-gw/gpt-5.4-mini`)
>
> **Most common failure:** step 6 — the connection doesn't exist on the Foundry project. Check in Portal → Project Settings → Connections, or `az resource show` on the project's connections.

## Prerequisites

| Component | Requirement |
|-----------|-------------|
| **Remote resource** | Azure AI Services account with model deployments (check region availability!) |
| **APIM instance** | Azure API Management (StandardV2 or BasicV2+) with system-assigned managed identity |
| **APIM MI RBAC** | `Cognitive Services User` role on the remote AI Services resource |
| **Source project** | Foundry project where you want to USE the remote models |
| **SDK** | `azure-ai-projects >= 2.0.0` and `openai` |

---

## Setup Guide

### Step 1: Configure the APIM Gateway

The APIM instance needs three things:

#### 1a. API with serviceUrl pointing to the remote backend

```powershell
# The API should have:
# - path: e.g. "my-api-prefix"
# - serviceUrl: "https://<remote-resource>.services.ai.azure.com"
# - subscriptionRequired: true
# - subscriptionKeyParameterNames.header: "api-key"
```

#### 1b. System-assigned Managed Identity with RBAC

```powershell
# APIM MI needs "Cognitive Services User" on the remote AI Services resource
az role assignment create \
  --assignee <APIM-MI-principal-id> \
  --role "Cognitive Services User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<remote-resource>
```

#### 1c. API Policy with MI authentication and api-version stripping

This is **critical**. The APIM must:
1. Authenticate to the backend using its managed identity
2. Strip the `api-version` query parameter (the `/openai/v1/` endpoints reject it)

```xml
<policies>
    <inbound>
        <base />
        <!-- Authenticate to backend with APIM's managed identity -->
        <authentication-managed-identity
            resource="https://cognitiveservices.azure.com"
            output-token-variable-name="msi-access-token"
            ignore-error="false" />
        <set-header name="Authorization" exists-action="override">
            <value>@("Bearer " + (string)context.Variables["msi-access-token"])</value>
        </set-header>
        <!-- Strip api-version: /openai/v1/ endpoints don't accept it -->
        <set-query-parameter name="api-version" exists-action="delete" />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>
```

**Common mistakes:**
- Missing `serviceUrl` on the API → APIM doesn't know where to forward
- Missing MI auth policy → backend returns 401/500
- NOT stripping `api-version` → backend returns "API version not supported"
- Wrong MI resource scope (must be `https://cognitiveservices.azure.com`, NOT `https://ai.azure.com/`)

### Step 2: Create the ApiManagement Connection on Source Project

**CRITICAL: The connection category MUST be `ApiManagement`** — NOT `AIServices` or `AzureOpenAI`. Those categories do NOT support the `connectionName/deploymentName` pattern.

#### Option A: AAD Auth (Recommended — no Key Vault needed)

Uses the project's managed identity to authenticate to APIM. **No credentials to store →
no Key Vault required.** This is the keyless approach and should be your default.

**Prerequisite:** APIM must accept the project MI. Assign `API Management Service Reader`
or a custom role on the APIM instance to the project's managed identity.

```powershell
$connBody = @{
    properties = @{
        category = "ApiManagement"
        target = "https://<apim-name>.azure-api.net/<api-path>/openai/v1"
        authType = "AAD"
        metadata = @{
            deploymentInPath = "false"
            modelDiscovery = '{"listModelsEndpoint":"/models","getModelEndpoint":"/models/{deploymentName}","deploymentProvider":"OpenAI"}'
        }
        isSharedToAll = $true
    }
} | ConvertTo-Json -Depth 5

$connUri = "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<resource>/connections/<conn-name>?api-version=2025-10-01-preview"

Invoke-RestMethod -Uri $connUri -Method Put -Headers $headers -Body $connBody
```

#### Option B: API Key Auth (needs Key Vault on the project)

Uses an APIM subscription key. The platform stores the key in the project's credential
store (Key Vault). **If the project was created via Bicep without a Key Vault, this
will fail with 500 Internal Server Error** (credential store → Key Vault → token failure).

> **Known issue:** Projects created via our minimal Bicep scaffold do NOT have a Key Vault.
> The platform auto-provisions one when creating via Portal, but not via raw Bicep.
> If you need ApiKey auth, either create the project via Portal first, or provision
> a Key Vault separately and link it manually.

```powershell
$connBody = @{
    properties = @{
        category = "ApiManagement"
        target = "https://<apim-name>.azure-api.net/<api-path>/openai/v1"
        authType = "ApiKey"
        credentials = @{
            key = "<APIM-subscription-key>"
        }
        metadata = @{
            deploymentInPath = "false"
            modelDiscovery = '{"listModelsEndpoint":"/models","getModelEndpoint":"/models/{deploymentName}","deploymentProvider":"OpenAI"}'
        }
        isSharedToAll = $true
    }
} | ConvertTo-Json -Depth 5

# Deploy via ARM API on the Foundry v2 project
$connUri = "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<resource>/projects/<project>/connections/<conn-name>?api-version=2025-04-01-preview"

Invoke-RestMethod -Uri $connUri -Method Put -Headers $headers -Body $connBody
```

#### Connection Configuration Details

| Field | Value | Why |
|-------|-------|-----|
| `category` | `"ApiManagement"` | Only this category enables `connectionName/deploymentName` routing |
| `target` | `https://<apim>.azure-api.net/<api-path>/openai/v1` | Must include `/openai/v1` suffix for OpenAI-compatible endpoints |
| `authType` | `"ApiKey"` | APIM subscription key authentication |
| `deploymentInPath` | `"false"` | Model name goes in request body, NOT URL path |
| `modelDiscovery` | OpenAI provider with `/models` endpoints | Agent Service validates models via discovery before inference |

#### Model Discovery Configuration (IMPORTANT)

The Agent Service **always** validates the model before making inference calls. Without correct model discovery config, you get `"Connection not found"` or `"Failed to parse deployment response"` errors.

**Two options:**

**Option A: Dynamic discovery (recommended)** — Agent Service calls `/models` endpoint:
```json
{
  "modelDiscovery": {
    "listModelsEndpoint": "/models",
    "getModelEndpoint": "/models/{deploymentName}",
    "deploymentProvider": "OpenAI"
  }
}
```

**Option B: Static discovery** — pre-define the model list:
```json
{
  "models": [
    {
      "name": "gpt-5.4-mini",
      "properties": {
        "model": {
          "name": "gpt-5.4-mini",
          "version": "",
          "format": "OpenAI"
        }
      }
    }
  ]
}
```

**CRITICAL: `deploymentProvider` must be `"OpenAI"`, NOT `"AzureOpenAI"`.**
The `/openai/v1/` endpoints return OpenAI-format responses. Using `AzureOpenAI` causes `"Failed to parse deployment response"` errors because it expects a different JSON structure.

### Step 3: Use in Code

```python
import os
os.environ["AZURE_CONFIG_DIR"] = r"C:\Users\ricchi\.azure-tenants\<alias>"

from azure.identity import AzureCliCredential
from azure.ai.projects import AIProjectClient

endpoint = "https://<resource>.services.ai.azure.com/api/projects/<project>"
credential = AzureCliCredential(process_timeout=30)
client = AIProjectClient(endpoint=endpoint, credential=credential)
oai = client.get_openai_client()

# The magic: connectionName/deploymentName
model = "<connection-name>/<deployment-name>"

# Responses API (works!)
resp = oai.responses.create(
    model=model,
    input="What is 2+2?",
    max_output_tokens=50,
)
print(resp.output_text)
```

> **Note:** The `connectionName/deploymentName` pattern works with the **Responses API** and **Agent Service**. It does NOT work with `chat.completions.create()` (the OpenAI chat completions endpoint treats it as a literal deployment name and returns `DeploymentNotFound`).

---

## Using AI Gateway with Hosted Agents

The `connectionName/deploymentName` pattern works inside hosted agent containers —
both GHCP SDK and MAF variants. The Foundry project routes through APIM transparently.

### In `agent.yaml`

```yaml
environment_variables:
  - name: MODEL_DEPLOYMENT_NAME
    value: aigw-fruocco-2/gpt-5.4-mini    # connectionName/deploymentName
```

### GHCP SDK (BYOK)

The BYOK provider's `base_url` points to the project endpoint. The model name
is passed to the session and APIM routing happens transparently:

```python
# In container.py — _get_provider() stays the same
# Model is set from env var: connectionName/deploymentName
_model = os.getenv("MODEL_DEPLOYMENT_NAME", "aigw-fruocco-2/gpt-5.4-mini")

# CopilotClient session uses the gateway-routed model
kwargs = {"model": _model, "provider": provider, ...}
```

### MAF (FoundryChatClient)

```python
client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ.get("MODEL_DEPLOYMENT_NAME", "aigw-fruocco-2/gpt-5.4-mini"),
    credential=DefaultAzureCredential(),
)
```

### azure.yaml — No `config.deployments` needed

When using AI Gateway, the model is already deployed on the remote resource.
**Remove** the `config.deployments` section from `azure.yaml` — otherwise azd
tries to create a duplicate deployment locally:

```yaml
services:
  my-agent:
    project: ./src/agent
    host: azure.ai.agent
    language: docker
    docker:
      remoteBuild: true
    config:
      container:
        resources:
          cpu: "1"
          memory: 2Gi
      # NO deployments section — model comes from AI Gateway
```

### Requirements

- Foundry project must have an `ApiManagement` connection (see Setup Guide above)
- The connection's target URL must point to the APIM gateway with the correct API path
- APIM MI must have `Cognitive Services User` on the remote AI Services resource

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection 'X' not found` | Connection category is `AIServices` or `AzureOpenAI` | Recreate as `ApiManagement` category |
| `Model gateway error: Upstream gateway returned InternalServerError` | APIM can't authenticate to backend | Add MI auth policy, verify RBAC |
| `Model gateway error: Upstream gateway returned NotFound` | Model discovery fails or wrong path | Set `modelDiscovery` with `"deploymentProvider": "OpenAI"` and `/models` endpoints |
| `Failed to parse deployment response for 'X' from provider 'AzureOpenAI'` | Discovery uses wrong provider format | Set `deploymentProvider: "OpenAI"` (not `AzureOpenAI`) |
| `API version not supported` | `api-version` query param sent to `/openai/v1/` endpoints | Add APIM policy: `<set-query-parameter name="api-version" exists-action="delete" />` |
| `DeploymentNotFound` | Using `chat.completions.create()` | Use `responses.create()` instead — chat completions doesn't support `connectionName/deploymentName` |
| APIM returns 500 | `serviceUrl` is null on the API | Set `serviceUrl` to the remote backend URL |
| **PUT connection 500: credential store → Key Vault token failure** | Project created via Bicep without a Key Vault. `authType: "ApiKey"` needs KV to store the subscription key. | **Use `authType: "AAD"` instead (recommended)** — no Key Vault needed. Or create project via Portal (auto-provisions KV). See Step 2 Options A/B. |

---

## Reference: Verified Working Configuration

This was validated on 2026-03-29 with:

| Component | Details |
|-----------|---------|
| **Source project** | `tlnext-agents-proj` on `tlnext-agents-tlnext` (North Central US) |
| **Remote resource** | `global-aiapps-gbb-sw` (Sweden Central) |
| **APIM gateway** | `global-aiapps-gbb-aigw` (BasicV2, Sweden Central) |
| **Connection name** | `remote-gw` |
| **Connection category** | `ApiManagement` |
| **Target** | `https://global-aiapps-gbb-aigw.azure-api.net/global-aiapps-gbb-sw/openai/v1` |
| **Model used** | `remote-gw/gpt-5.4-mini` |
| **SDK** | `azure-ai-projects 2.0.1`, `openai` (latest) |
| **API** | Responses API (`oai.responses.create()`) |

### ThreadLight tl2-prd Configuration (validated 2026-04-14)

| Component | Details |
|-----------|---------|
| **Source project** | `aiprj-4f31f390` on `tl2-hub-ah3f7giaicvzu` (North Central US) |
| **Remote resource** | `emea-aigbb-demos-oai-fruocco-2` (Sweden Central, has `gpt-5.4-mini`) |
| **APIM gateway** | `aigw-fruocco-2` (BasicV2, Sweden Central) in RG `rg-infra-fruocco-2`, sub `2c745a8f-9d37-45e3-8506-80797e89735e` |
| **Connection name** | `aigw-fruocco-2` |
| **Connection category** | `ApiManagement` |
| **Target** | `https://aigw-fruocco-2.azure-api.net/emea-aigbb-demos-oai-fruocco-2/openai/v1` |
| **APIM subscription** | `tl2-prd-agents` (scoped to API) |
| **Model used** | `aigw-fruocco-2/gpt-5.4-mini` |
| **Env var** | `AZURE_OPENAI_AGENT_MODEL=aigw-fruocco-2/gpt-5.4-mini` |
| **Code** | `_ensure_aigw_connection()` in `azure_loader.py`, `upsert_agent()` uses `config.AZURE_OPENAI_AGENT_MODEL` |

---

## Official Documentation

### Foundry Samples (authoritative reference for connection setup)

- [**APIM and ModelGateway Integration Guide**](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim-and-modelgateway-integration-guide.md) — choose between APIM and ModelGateway connection types
- [**APIM Connection Objects**](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/apim/APIM-Connection-Objects.md) — full schema: deploymentInPath, modelDiscovery, authConfig, customHeaders
- [**ModelGateway Connection Objects**](https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/01-connections/model-gateway/ModelGateway-Connection-Objects.md) — for non-APIM gateways (Kong, MuleSoft, custom, direct OpenAI)
- [**APIM Setup Bicep templates**](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/apim) — Bicep for creating APIM connections
- [**ModelGateway Bicep templates**](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/01-connections/model-gateway) — Bicep for creating ModelGateway connections

### Azure Docs

- [Connect an AI gateway to Foundry Agent Service (preview)](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/ai-gateway)
- [Red Teaming docs (connectionName/deploymentName format)](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/run-ai-red-teaming-cloud#configure-your-target-model)

### Connection Types Quick Reference

| Gateway Type | Connection Category | When to Use |
|-------------|-------------------|-------------|
| **Azure API Management** | `ApiManagement` | APIM as gateway — supports AAD + ApiKey auth |
| **Any other gateway** (Kong, MuleSoft, custom, direct OpenAI) | `ModelGateway` | Non-APIM gateways — ApiKey auth only (for now) |

> **ModelGateway** is useful when you don't have APIM but want to route through
> another gateway, or connect directly to OpenAI/third-party endpoints. Currently
> only supports ApiKey auth — AAD auth is APIM-only for now.

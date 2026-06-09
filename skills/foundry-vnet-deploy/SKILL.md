---
name: foundry-vnet-deploy
description: >
  Deploy Azure AI Foundry with **Agent Setup inside a private VNet** —
  the `15-private-network-standard-agent-setup` Bicep reference
  architecture. Supports new/existing VNets, resource reuse (CosmosDB /
  Storage / AI Search / private DNS zones), hosted-agent RBAC,
  App Insights, and spoke-side peering + APIM-DNS-zone link to a
  Citadel hub VNet. Read the full skill body for the guided interview,
  retry logic, and subnet sizing — do not deploy from this summary.
  USE FOR: foundry private vnet, network-secured foundry, agent
  injection, capability host, citadel hub peering, vnet-isolated
  citadel spoke, apim private dns zone link, central dns at scale,
  hub-spoke private dns, InvalidPrivateDnsZoneIds.
  DO NOT USE FOR: azd-based deploys (use threadlight-deploy or
  foundry-hosted-agents), public-network Foundry, APIM cross-resource
  (use foundry-cross-resource), tenant isolation
  (use azure-tenant-isolation), Citadel app-layer onboarding (use
  citadel-spoke-onboarding for APIM products + Foundry connection).
metadata:
  version: "1.1.4"
---

# Foundry VNet Deploy — Agent Setup inside a Private VNet

## 1. Goal

Guide the user step by step to deploy **Azure AI Foundry with Agent in a private VNet** using the Bicep files from the `15-private-network-standard-agent-setup` reference project. The skill collects all required parameters, generates the `.bicepparam` file, and runs the deployment.

> **Optional scenario hint.** When the user invokes the skill, they may pass a one-line scenario hint such as `"new VNet in swedencentral"` or `"existing VNet with existing DNS zones"`. Use it to pre-fill defaults during the interview wherever it applies.

> **Day-2 lifecycle companion.** This skill covers greenfield create only. For **Day-2 capability host lifecycle** (idempotent re-create, delete, soft-delete + purge of the parent account, `Subnet already in use` redeploy guard, soft-delete recovery) see [`foundry-caphost-lifecycle`](../foundry-caphost-lifecycle/SKILL.md). You will need it any time you tear down and redeploy a Foundry caphost into the same VNet/subnet.

## 2. Architecture being deployed

The deployment creates the following secure network architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    Resource Group                        │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Virtual Network (VNet)                  │ │
│  │                                                      │ │
│  │  ┌──────────────────┐  ┌──────────────────────────┐ │ │
│  │  │  Agent Subnet     │  │  Private Endpoint Subnet │ │ │
│  │  │  (delegated to    │  │                          │ │ │
│  │  │  Container Apps)  │  │  ● AI Services PE        │ │ │
│  │  │                   │  │  ● AI Search PE          │ │ │
│  │  │  Network          │  │  ● Storage PE (blob)     │ │ │
│  │  │  Injection for    │  │  ● CosmosDB PE (SQL)     │ │ │
│  │  │  AI Agents        │  │                          │ │ │
│  │  └──────────────────┘  └──────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────┐ ┌────────────┐ ┌───────────────────┐  │
│  │ AI Services  │ │ AI Search  │ │ Storage Account   │  │
│  │ (Foundry)    │ │ (standard) │ │ (StorageV2, ZRS)  │  │
│  │ ● SKU S0     │ │ ● disabled │ │ ● public access   │  │
│  │ ● public     │ │   public   │ │   disabled        │  │
│  │   disabled   │ │   access   │ │ ● shared key      │  │
│  │ ● network    │ │            │ │   disabled        │  │
│  │   injection  │ │            │ │                   │  │
│  └──────────────┘ └────────────┘ └───────────────────┘  │
│                                                          │
│  ┌──────────────┐ ┌────────────────────────────────────┐ │
│  │ CosmosDB     │ │ Private DNS Zones (6 zones)       │ │
│  │ (SQL API)    │ │ ● privatelink.services.ai.azure.. │ │
│  │ ● public     │ │ ● privatelink.openai.azure.com    │ │
│  │   disabled   │ │ ● privatelink.cognitiveservices.. │ │
│  │ ● local auth │ │ ● privatelink.search.windows.net  │ │
│  │   disabled   │ │ ● privatelink.blob.core.windows.. │ │
│  │              │ │ ● privatelink.documents.azure.com │ │
│  └──────────────┘ └────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ AI Foundry Account Capability Host                   │ │
│  │ ● capabilityHostKind: Agents                         │ │
│  │ ● customerSubnet → Agent Subnet (VNet injection)     │ │
│  │ ● Replaces manual createCapHost.sh                   │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ AI Foundry Project                                   │ │
│  │ ● System-Assigned Managed Identity                   │ │
│  │ ● Connections: CosmosDB, Storage, AI Search          │ │
│  │ ● Project Capability Host (Agents) with:             │ │
│  │   - vectorStoreConnections → AI Search               │ │
│  │   - storageConnections → Blob Storage                │ │
│  │   - threadStorageConnections → CosmosDB               │ │
│  │ ● Depends on Account Capability Host                 │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                          │
│  Role Assignments (Project SMI):                         │
│  ● Storage Blob Data Contributor (account level)         │
│  ● Storage Blob Data Owner (container level, scoped)     │
│  ● Cosmos DB Operator (account level)                    │
│  ● Cosmos DB Built-in Data Contributor (enterprise_memory)│
│  ● AI Search Index Data Contributor                      │
│  ● AI Search Service Contributor                         │
│  └───────────────────────────────────────────────────────┘
└──────────────────────────────────────────────────────────┘
```

## 3. Workflow

Follow these steps IN ORDER. Use the `ask_user` tool for every question.

### Step 1: Verify prerequisites

Before starting, verify:

1. Run `az account show` to confirm the user is logged in to Azure CLI.
2. If NOT logged in, indicate that they must run `az login` first.
3. Show the current subscription and ask whether it is correct.

### Step 2: Subscription and Resource Group

Ask the user:

1. **Subscription**: Do they want to use the current subscription or change it? If they want to change, ask for the subscription ID.
2. **Resource Group**: Does the resource group already exist or does it need to be created?
   - If it needs to be created, ask for the name and location.
   - If it already exists, ask for the name.

### Step 3: Location

Ask for the deployment region. The allowed regions are:

- westus, eastus, eastus2, japaneast, francecentral, spaincentral, uaenorth
- southcentralus, italynorth, germanywestcentral, brazilsouth, southafricanorth
- australiaeast, swedencentral, canadaeast, westeurope, westus3, uksouth, southindia
- koreacentral, polandcentral, switzerlandnorth, norwayeast (Class B and C only)

Present the options as a list and offer `swedencentral` as the recommended one.

### Step 4: AI service and project name

Ask:

1. **aiServices**: Prefix for the AI Services resource (default: `foundry`). A unique suffix will be appended automatically.
2. **firstProjectName**: Project name (default: `project`).
3. **displayName**: Visible project name (default: same as the project name).
4. **projectDescription**: Project description (default: `A project for the AI Foundry account with network secured deployed Agent`).
5. **accountCapHost**: Name of the account-level capability host (default: `caphostacct`). This resource sets `customerSubnet` for the agent runtime network injection.

### Step 5: Model configuration

Ask:

1. **modelName**: Name of the model to deploy (default: `gpt-4.1`). Common options: gpt-4.1, gpt-4o, gpt-4o-mini, gpt-4.1-mini, gpt-4.1-nano.
2. **modelFormat**: Model provider (default: `OpenAI`).
3. **modelVersion**: Model version. Depends on the chosen model.
4. **modelSkuName**: Deployment SKU (default: `GlobalStandard`). Options: GlobalStandard, Standard, ProvisionedManaged.
5. **modelCapacity**: TPM (tokens per minute) in thousands (default: `30` = 30K TPM).

### Step 6: Network configuration (VNet)

Ask the user:

**Are you going to use an existing VNet or create a new one?**

### Option A: New VNet
Ask:
1. **vnetName**: VNet name (default: `agent-vnet`).
2. **vnetAddressPrefix**: Address space (default: `192.168.0.0/16`). Also supports `10.x.x.x/16` or `172.16.x.x/16`.
3. **agentSubnetPrefix**: CIDR of the agent subnet (default: automatically calculated as the first /24 of the address space).
4. **peSubnetPrefix**: CIDR of the private endpoint subnet (default: automatically calculated as the second /24).
5. **agentSubnetName**: Name of the agent subnet (default: `agent-subnet`).
6. **peSubnetName**: Name of the PE subnet (default: `pe-subnet`).

### Option B: Existing VNet
Ask:
1. **existingVnetResourceId**: Full resource ID of the VNet. Format: `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}`.
2. **agentSubnetName**: Name of the agent subnet (will be created if it does not exist). IMPORTANT: This subnet needs delegation to `Microsoft.App/environments`.
3. **peSubnetName**: Name of the private endpoint subnet (will be created if it does not exist).
4. **agentSubnetPrefix**: CIDR of the agent subnet (mandatory if the subnet does not exist). WARNING: Must not overlap with existing subnets.
5. **peSubnetPrefix**: CIDR of the PE subnet (mandatory if the subnet does not exist).

### Step 7: Existing resources (optional)

Ask whether the user has existing resources they want to reuse:

1. **Do you have an existing AI Search?** If yes → ask for `aiSearchResourceId` (full ARM format).
2. **Do you have an existing Storage Account?** If yes → ask for `azureStorageAccountResourceId`.
3. **Do you have an existing CosmosDB?** If yes → ask for `azureCosmosDBAccountResourceId`.

If none are provided, all of them will be created automatically. The new resources are created with:
- **AI Search**: Standard SKU, public access disabled, local auth enabled with AAD.
- **Storage**: StorageV2, ZRS (or GRS in southindia/westus), public access disabled, shared key disabled.
- **CosmosDB**: Global Document DB, Session consistency, public access disabled, local auth disabled.

### Step 8: Private DNS zones (optional)

Ask:

**Do you have existing private DNS zones that you want to reuse?**

If NO → all zones will be created automatically (6 zones). Continue to step 9.

If YES → ask:

1. **dnsZonesSubscriptionId**: Subscription where the DNS zones are located (leave empty if it is the same as the deployment).
2. For each zone, ask whether it exists and which resource group it is in:
   - `privatelink.services.ai.azure.com`
   - `privatelink.openai.azure.com`
   - `privatelink.cognitiveservices.azure.com`
   - `privatelink.search.windows.net`
   - `privatelink.blob.core.windows.net`
   - `privatelink.documents.azure.com`

The format is an object where each key is the zone name and the value is the resource group (empty = create a new one).

> **Central DNS at scale (hub-and-spoke).** When the spoke is deployed into an enterprise hub-and-spoke topology, the 6 zones above are typically owned by the **platform team in a separate subscription** (often the connectivity hub). The `dnsZonesSubscriptionId` parameter combined with the per-zone resource-group map in `existingDnsZones` is exactly the pattern described in Microsoft's Cloud Adoption Framework — see [Private Link and DNS integration at scale](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale#private-link-and-dns-integration-in-hub-and-spoke-network-architectures) for the canonical reference architecture. The deployment principal needs `Private DNS Zone Contributor` on each zone in the hub subscription to create the VNet links; without this you will hit `InvalidPrivateDnsZoneIds` at deploy time.
>
> - For deploy-time DNS troubleshooting (including the `InvalidPrivateDnsZoneIds` symptom → cause → fix table), see the upcoming `foundry-network-runbook` skill.

### Step 8b: Hosted agent developers (optional but recommended)

Users / service principals that are going to **create hosted agents** in this Foundry need:
- `Managed Identity Operator` on the Foundry account
- `Network Contributor` on the agent injection subnet

Without these permissions, hosted agent creation will fail with 403 errors when provisioning the MIs or NICs. The template can assign them automatically.

Ask:

1. **Which users / groups / SPs are going to create hosted agents in this Foundry?**
   - Ask for a list of **AAD objectIds** (you can get them with `az ad signed-in-user show --query id -o tsv` or `az ad user show --id <upn> --query id -o tsv`).
   - If the user does not want to use it now, leave the list empty and it can be added manually later.
2. **Principal type** (User / Group / ServicePrincipal). Default `User`. All IDs must be of the same type (run the module twice if you need to mix types).

### Step 8c: Application Insights + Log Analytics (recommended)

The official [hosted agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions) doc lists App Insights + Log Analytics Workspace as **required resources**:
- They enable agent traces, logs and metrics
- Required for the **evaluations** feature
- The template creates them + creates an `appinsights` connection in the project + assigns to the project MI:
  - `Log Analytics Reader` on the workspace
  - `Azure AI User` on the account (recommended by the doc so the MI can infer via the project endpoint)

They usually do not need user input; names are auto-generated unless the user wants to customize them.

Optional question:

1. **Do you want custom names for the Log Analytics workspace and App Insights?** If not, they are auto-generated with a unique suffix.

### Step 8d: Citadel hub integration (optional)

If the spoke project will be onboarded into an **AI Citadel Governance Hub** as a spoke (see `citadel-spoke-onboarding`), this template can create the spoke-side network plumbing in the same deployment. Otherwise skip to Step 9.

Ask:

1. **Will this Foundry be a Citadel hub spoke?** (yes/no — default no).
   - If **no**, leave the four `hub*` / `apimDnsZone*` parameters empty in Step 9 and continue. Citadel onboarding can also be added later via a re-deploy with the same `deploymentTimestamp`.
   - If **yes**, ask the next questions.
2. **`hubVnetResourceId`** — full ARM ID of the Citadel hub VNet. Format: `/subscriptions/{hubSub}/resourceGroups/{hubRg}/providers/Microsoft.Network/virtualNetworks/{hubVnet}`.
   - The deployment will create **only the spoke→hub peering** (your RBAC). The hub→spoke reverse peering is hub-team RBAC; the deployment will emit a one-line `az network vnet peering create` in the `hubReversePeeringCommand` output for them to run.
   - ⚠️ **Address-space requirement**: spoke and hub VNets must NOT overlap. Re-validate the values from Step 6 against the hub VNet's address space before continuing.
3. **`apimDnsZoneResourceId`** (optional) — full ARM ID of the existing `privatelink.azure-api.net` private DNS zone (typically owned by the hub team). Format: `/subscriptions/{hubSub}/resourceGroups/{hubDnsRg}/providers/Microsoft.Network/privateDnsZones/privatelink.azure-api.net`.
   - Required when the Citadel hub APIM uses a private endpoint (most common). Skip when APIM is reachable on a public endpoint.
   - The deployment will link the zone to the spoke VNet so the agent resolves `{apim}.azure-api.net` to its private IP.
4. **`hubPeeringName`** (optional, default `peering-to-hub`) — friendly name for the spoke-side peering.
5. **`apimDnsZoneLinkName`** (optional, default `foundry-spoke-link`) — VNet-link name on the DNS zone (must be unique within the zone).

Pre-flight (run **after** Step 11 verification, before invoking `citadel-spoke-onboarding`):

```powershell
# 1. Both peerings must be Connected
az network vnet peering show --resource-group {rg} --vnet-name {vnetName} `
  --name {hubPeeringName} --query peeringState -o tsv     # → "Connected"

# 2. DNS resolution from inside the spoke VNet (run from a peered VM/Bastion):
Resolve-DnsName "{apim}.azure-api.net"                    # must resolve to a 10.x / 192.168.x / 172.16.x private IP

# 3. End-to-end TCP reachability:
Test-NetConnection -ComputerName "{apim}.azure-api.net" -Port 443
```

If all three pass, the Foundry account in this VNet can now reach the Citadel hub APIM gateway, and you can run `citadel-spoke-onboarding` against the project to inject the APIM products + Foundry connection.

### Step 9: Generate the .bicepparam file

With all the data collected, generate the `main.bicepparam` file with the following format:

```bicep
using './main.bicep'

param location = '{location}'
param aiServices = '{aiServices}'
param modelName = '{modelName}'
param modelFormat = '{modelFormat}'
param modelVersion = '{modelVersion}'
param modelSkuName = '{modelSkuName}'
param modelCapacity = {modelCapacity}
param firstProjectName = '{firstProjectName}'
param projectDescription = '{projectDescription}'
param displayName = '{displayName}'
param peSubnetName = '{peSubnetName}'
param accountCapHost = '{accountCapHost}'

// Existing resources
param existingVnetResourceId = '{existingVnetResourceId}'
param vnetName = '{vnetName}'
param agentSubnetName = '{agentSubnetName}'
param aiSearchResourceId = '{aiSearchResourceId}'
param azureStorageAccountResourceId = '{azureStorageAccountResourceId}'
param azureCosmosDBAccountResourceId = '{azureCosmosDBAccountResourceId}'

// DNS configuration
param dnsZonesSubscriptionId = '{dnsZonesSubscriptionId}'
param existingDnsZones = {
  'privatelink.services.ai.azure.com': '{rg_or_empty}'
  'privatelink.openai.azure.com': '{rg_or_empty}'
  'privatelink.cognitiveservices.azure.com': '{rg_or_empty}'
  'privatelink.search.windows.net': '{rg_or_empty}'
  'privatelink.blob.core.windows.net': '{rg_or_empty}'
  'privatelink.documents.azure.com': '{rg_or_empty}'
}

param dnsZoneNames = [
  'privatelink.services.ai.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.search.windows.net'
  'privatelink.blob.core.windows.net'
  'privatelink.documents.azure.com'
]

// Network configuration
param vnetAddressPrefix = '{vnetAddressPrefix}'
param agentSubnetPrefix = '{agentSubnetPrefix}'
param peSubnetPrefix = '{peSubnetPrefix}'

// Hosted-agent developer RBAC (optional). Object IDs that will get
// 'Managed Identity Operator' on the account and 'Network Contributor'
// on the agent subnet. Leave empty to skip.
param agentDeveloperPrincipalIds = [
  // '00000000-0000-0000-0000-000000000000'
]
param agentDeveloperPrincipalType = 'User'

// Application Insights + Log Analytics workspace (REQUIRED by hosted agent permissions doc).
// Leave empty to auto-name; project gets an `appinsights` connection and the
// project MI receives Log Analytics Reader + Azure AI User on the account.
param logAnalyticsWorkspaceName = ''
param appInsightsName = ''

// Citadel hub integration (optional). Set to non-empty values when the spoke
// will be onboarded as a Citadel hub spoke (Step 8d above + citadel-spoke-onboarding).
// Leave empty to skip — existing flows are unchanged.
param hubVnetResourceId = '{hubVnetResourceId}'
param hubPeeringName = '{hubPeeringName}'           // default: 'peering-to-hub'
param apimDnsZoneResourceId = '{apimDnsZoneResourceId}'
param apimDnsZoneLinkName = '{apimDnsZoneLinkName}' // default: 'foundry-spoke-link'
```

**IMPORTANT**: 
- If a value is empty (not provided by the user), use the empty string `''`.
- The `dnsZoneNames` parameter must always include the 6 zones.
- If using a new VNet without prefixes, leave the subnet prefixes empty (they will be calculated automatically).
- **DO NOT include `deploymentTimestamp`** in the `.bicepparam` file. This parameter is always passed via CLI (`--parameters deploymentTimestamp=...`) so it can be reused on retries without modifying the file.
- Use a descriptive name for the `.bicepparam` file (e.g. `deploy-{resourceGroup}.bicepparam`) so as not to overwrite the project's original `main.bicepparam`.

### Step 10: Confirm and deploy

1. Show a **complete summary** of the configuration to the user, including:
   - Subscription and Resource Group
   - Region
   - AI service and project name
   - Model and capacity
   - VNet type (new/existing) and subnets
   - Reused existing resources
   - DNS zones (new/existing)
   - **Citadel hub integration** (if Step 8d was completed): hub VNet ARM ID, APIM DNS zone ARM ID, peering name. Otherwise: "(none — local Foundry only)".

2. Ask the user whether to proceed with the deployment.

3. If they confirm, generate a **fixed timestamp** for the deployment and store it:
   ```powershell
   $deployTimestamp = Get-Date -Format 'yyyyMMddHHmmss'
   ```
   This timestamp will be reused if the deployment has to be retried.

4. Run the deployment passing the timestamp as an explicit parameter:
   ```
   az deployment group create \
     --resource-group {resourceGroup} \
     --template-file main.bicep \
     --parameters {bicepparam_file} \
     --parameters deploymentTimestamp={deployTimestamp} \
     --name "foundry-vnet-{deployTimestamp}"
   ```

   > **⚠️ CRITICAL — Timestamp idempotency**
   > The Bicep uses `uniqueString(resourceGroup().id + deploymentTimestamp)` to generate
   > a unique suffix (`uniqueSuffix`) that is appended to ALL resource names
   > (AI Services, CosmosDB, Storage, AI Search, Project). If the timestamp changes between
   > attempts, a different suffix will be generated and DUPLICATE resources will be created
   > instead of retrying the existing ones. That is why it is **mandatory** to fix the timestamp
   > and reuse it on any retry.

5. The deployment can take **45-90 minutes**. The slowest step is the Account
   Capability Host (network injection / Container Apps Environment) which can take
   30-60+ minutes. Monitor the progress with:
   ```
   az deployment operation group list --resource-group {resourceGroup} \
     --name "foundry-vnet-{deployTimestamp}" \
     --query "[].{name:properties.targetResource.resourceName, state:properties.provisioningState}" -o table
   ```

6. **If the deployment fails**, follow the retry procedure in Step 10b.

### Step 10b: Safe retry (anti-duplication)

If the deployment fails (frequently due to a timeout of the Account Capability Host),
follow these steps to retry without duplicating resources:

1. **Reuse the SAME timestamp** (`$deployTimestamp`) as the original attempt. This is
   the most important thing to avoid duplication.

2. **Check whether the Account Capability Host was created internally** despite the timeout.
   Azure sometimes completes the operation after ARM reports a timeout:
   ```powershell
   # Try to create again — if it returns "Conflict" with provisioningState: Succeeded,
   # it means it already exists and works correctly
   az rest --method PUT \
     --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/capabilityHosts/{capHostName}?api-version=2025-04-01-preview" \
     --body "@caphost-body.json" \
     --headers "Content-Type=application/json"
   ```
   
   If the error is `Conflict` with `provisioning state: Succeeded` → the caphost **already exists**.
   In that case, create the **Project Capability Host** directly via the REST API:
   ```powershell
   # Get the project's connection names
   az rest --method GET \
     --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}/connections?api-version=2025-04-01-preview" \
     --query "value[].{name:name, category:properties.category}" -o table

   # Create the project caphost with the connections
   # Body: {"properties":{"capabilityHostKind":"Agents","vectorStoreConnections":["searchConn"],"storageConnections":["storageConn"],"threadStorageConnections":["cosmosConn"]}}
   az rest --method PUT \
     --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}/capabilityHosts/caphost?api-version=2025-04-01-preview" \
     --body "@project-caphost-body.json" \
     --headers "Content-Type=application/json"
   ```

3. **If duplicate resources were created** (because of retrying without fixing the timestamp),
   identify and delete them:
   ```powershell
   # List resources — look for names with a suffix different from the original
   az resource list --resource-group {rg} --query "[].name" -o tsv
   
   # Delete duplicates (those that do NOT have the original suffix)
   az resource delete --ids {duplicate_resource_id}
   ```

4. **Re-run the full deployment** with the original timestamp:
   ```
   az deployment group create \
     --resource-group {resourceGroup} \
     --template-file main.bicep \
     --parameters {bicepparam_file} \
     --parameters deploymentTimestamp={deployTimestamp} \
     --name "foundry-vnet-retry-{deployTimestamp}"
   ```

5. If the Account Capability Host keeps failing with a timeout after 2 attempts,
   use the direct REST API path (step 2 of this block) to create the capability
   hosts manually and then run the remaining role assignments via Bicep or CLI.

### Step 11: Post-deployment verification

After the deployment (successful or after completing the retry steps), run ALL these
checks and present the results to the user as a status table.

### 11.1 — AI Services Account

```powershell
az rest --method GET \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}?api-version=2025-04-01-preview" \
  --query "{name:name, state:properties.provisioningState, publicAccess:properties.publicNetworkAccess, sku:sku.name, networkInjections:properties.networkInjections}" -o json
```

Verify:
- `provisioningState` = `Succeeded`
- `publicNetworkAccess` = `Disabled`
- `networkInjections[0].scenario` = `agent` and points to the correct subnet

### 11.2 — Model deployment

```powershell
az rest --method GET \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/deployments?api-version=2025-04-01-preview" \
  --query "value[].{name:name, model:properties.model.name, version:properties.model.version, sku:sku.name, capacity:sku.capacity, state:properties.provisioningState}" -o table
```

Verify: `provisioningState` = `Succeeded`, model and capacity match what was requested.

### 11.3 — Project + Identity

```powershell
az rest --method GET \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}?api-version=2025-04-01-preview" \
  --query "{name:name, state:properties.provisioningState, identityType:identity.type, principalId:identity.principalId}" -o json
```

Verify: `provisioningState` = `Succeeded`, `identity.type` = `SystemAssigned`, `principalId` is not null.

### 11.4 — Capability Hosts

**Account Capability Host** — use PUT to verify (GET does not always work with this resource):
```powershell
# If it returns "Conflict" with "provisioning state: Succeeded" → OK
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/capabilityHosts/{capHostName}?api-version=2025-04-01-preview" \
  --body "@caphost-body.json" --headers "Content-Type=application/json"
```

**Project Capability Host**:
```powershell
az rest --method GET \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}/capabilityHosts/caphost?api-version=2025-04-01-preview" \
  --query "{name:name, state:properties.provisioningState, kind:properties.capabilityHostKind, vectorStore:properties.vectorStoreConnections, storage:properties.storageConnections, threadStorage:properties.threadStorageConnections}" -o json
```

Verify:
- `provisioningState` = `Succeeded`
- `capabilityHostKind` = `Agents`
- The 3 connections (vectorStore, storage, threadStorage) point to the correct resources

### 11.5 — Project Connections

```powershell
az rest --method GET \
  --url "https://management.azure.com/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{accountName}/projects/{projectName}/connections?api-version=2025-04-01-preview" \
  --query "value[].{name:name, category:properties.category, target:properties.target}" -o table
```

Verify: 3 connections exist (CosmosDb, CognitiveSearch, AzureStorageAccount) with correct targets.

### 11.6 — VNet and Subnets

```powershell
az network vnet show --resource-group {rg} --name {vnetName} \
  --query "{name:name, addressSpace:addressSpace.addressPrefixes[0], subnets:subnets[].{name:name, prefix:addressPrefix, delegation:delegations[0].serviceName}}" -o json
```

Verify:
- Address space is correct
- `agent-subnet` delegated to `Microsoft.App/environments`
- `pe-subnet` without delegation

### 11.7 — Private Endpoints

```powershell
az network private-endpoint list --resource-group {rg} \
  --query "[].{name:name, status:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status}" -o table
```

Verify: 4 Private Endpoints, all with status `Approved`.

### 11.8 — DNS Zone VNet Links

For each of the 6 DNS zones, verify that the deployment's VNet has an active link.
If reusing existing zones from another resource group:
```powershell
# For each zone, list links and look for the one pointing to our VNet
$zones = @("privatelink.services.ai.azure.com","privatelink.openai.azure.com",
  "privatelink.cognitiveservices.azure.com","privatelink.search.windows.net",
  "privatelink.blob.core.windows.net","privatelink.documents.azure.com")
foreach ($z in $zones) {
    $all = az network private-dns link vnet list --resource-group {dnsZonesRg} --zone-name $z -o json | ConvertFrom-Json
    $mine = $all | Where-Object { $_.virtualNetwork.id -match '{rg}' }
    if ($mine -and $mine.provisioningState -eq "Succeeded") {
        Write-Host "✅ $z"
    } else {
        Write-Host "❌ $z → MISSING VNet link"
    }
}
```

**⚠️ IMPORTANT**: If VNet links are missing, private DNS resolution will not work from the
deployment's VNet. Create them manually:
```powershell
az network private-dns link vnet create \
  --resource-group {dnsZonesRg} \
  --zone-name {zoneName} \
  --name "{vnetName}-link-{zoneSuffix}" \
  --virtual-network {vnetResourceId} \
  --registration-enabled false
```

### 11.9 — Private resources (public access disabled)

```powershell
# CosmosDB
az cosmosdb show --name {cosmosName} --resource-group {rg} \
  --query "{name:name, publicAccess:publicNetworkAccess}" -o json

# AI Search
az search service show --name {searchName} --resource-group {rg} \
  --query "{name:name, publicAccess:publicNetworkAccess}" -o json

# Storage
az storage account show --name {storageName} --resource-group {rg} \
  --query "{name:name, publicAccess:publicNetworkAccess, allowSharedKey:allowSharedKeyAccess}" -o json
```

Verify: `publicNetworkAccess` = `Disabled` on the 3 resources. Storage additionally: `allowSharedKeyAccess` = `false`.

### 11.10 — Role Assignments (6 total)

**ARM RBAC (5 assignments)**:
```powershell
az role assignment list --assignee {principalId} --all \
  --query "[].{role:roleDefinitionName, scope:scope}" -o table
```

Verify the following exist:
1. `Storage Blob Data Contributor` (scope: storage account)
2. `Storage Blob Data Owner` (scope: storage account, with ABAC condition)
3. `Cosmos DB Operator` (scope: cosmos account)
4. `Search Index Data Contributor` (scope: search service)
5. `Search Service Contributor` (scope: search service)

**CosmosDB SQL Role (1 assignment)**:
```powershell
az cosmosdb sql role assignment list --account-name {cosmosName} --resource-group {rg} \
  --query "[?principalId=='{principalId}'].{scope:scope}" -o table
```

Verify: Built-in Data Contributor scoped to `dbs/enterprise_memory`.

### 11.11 — Summary and result

Present a summary table to the user with the status of each check:

| Component | Status | Detail |
|---|---|---|
| AI Services | ✅/❌ | name, SKU, network injection |
| Model | ✅/❌ | name, version, SKU, capacity |
| Project | ✅/❌ | name, identity |
| Account CapHost | ✅/❌ | kind, subnet |
| Project CapHost | ✅/❌ | kind, connections |
| VNet + Subnets | ✅/❌ | address space, delegation |
| Private Endpoints (4) | ✅/❌ | status Approved |
| DNS VNet Links (6) | ✅/❌ | all linked |
| Private resources (3) | ✅/❌ | publicAccess Disabled |
| Role Assignments (6) | ✅/❌ | all present |

If everything is ✅, inform that the deployment is **100% operational**.

If there are ❌, indicate what is missing and offer to fix it automatically.

### Step 12: VNet access configuration (optional)

Ask the user how they will access the private resources of the VNet. The options are:

1. **Existing VPN Gateway** (P2S) in another VNet → Step 12A
2. **VM / Bastion / ExpressRoute** already available in the same VNet or with peering → Step 12C
3. **No access configured** → needs to create one → Step 12B
4. **AI Citadel hub integration** (peering + DNS link were created in Step 8d / 9 / 10) → Step 12D **post-deploy verification**
5. **I will configure it later** → skip to Step 13

> Step 12 options are not mutually exclusive — a Citadel-spoke deployment commonly also needs operator access (Step 12A/B/C) for `az`-side validation.

### Step 12A — Access via existing VPN Gateway (with peering)

If the user has a VPN Gateway with Point-to-Site configured in **another VNet**,
bidirectional peering with gateway transit is required so VPN clients can reach
the new VNet.

#### 12A.1 — Identify the VPN Gateway

```powershell
# Locate the gateway and its VNet
az network vnet-gateway list --resource-group {gatewayRg} \
  --query "[].{name:name, vnet:ipConfigurations[0].subnet.id}" -o json

# Get P2S address pool
az network vnet-gateway show --resource-group {gatewayRg} --name {gatewayName} \
  --query "{p2sPool:vpnClientConfiguration.vpnClientAddressPool.addressPrefixes}" -o json
```
  --query "{p2sPool:vpnClientConfiguration.vpnClientAddressPool.addressPrefixes}" -o json
```

#### 12A.2 — Create bidirectional VNet Peering with gateway transit

TWO peerings are required: one from each side. The peering from the gateway's VNet
must enable `allowGatewayTransit`, and the peering from the new VNet must enable
`useRemoteGateways`. This allows P2S clients to reach the new VNet through the
existing gateway.

```powershell
$gatewayVnetId = "/subscriptions/{subId}/resourceGroups/{gatewayRg}/providers/Microsoft.Network/virtualNetworks/{gatewayVnet}"
$newVnetId = "/subscriptions/{subId}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnetName}"

# Peering 1: Gateway VNet → New VNet (allows gateway transit)
az network vnet peering create \
  --resource-group {gatewayRg} \
  --vnet-name {gatewayVnet} \
  --name "peering-to-{vnetName}" \
  --remote-vnet $newVnetId \
  --allow-vnet-access \
  --allow-forwarded-traffic \
  --allow-gateway-transit

# Peering 2: New VNet → Gateway VNet (uses the remote gateway)
az network vnet peering create \
  --resource-group {rg} \
  --vnet-name {vnetName} \
  --name "peering-to-{gatewayVnet}" \
  --remote-vnet $gatewayVnetId \
  --allow-vnet-access \
  --allow-forwarded-traffic \
  --use-remote-gateways
```

Verify both peerings are in `Connected` state:
```powershell
az network vnet peering show --resource-group {gatewayRg} --vnet-name {gatewayVnet} \
  --name "peering-to-{vnetName}" --query "{state:peeringState}" -o tsv
az network vnet peering show --resource-group {rg} --vnet-name {vnetName} \
  --name "peering-to-{gatewayVnet}" --query "{state:peeringState}" -o tsv
```

> **⚠️ REQUIREMENT**: The address spaces of both VNets MUST NOT overlap.
> If the gateway's VNet uses 10.0.0.0/16, the new VNet should use 10.1.0.0/16 or another
> non-overlapping range (this is already validated in Step 6).

#### 12A.3 — Get private IPs of the endpoints

```powershell
$pes = az network private-endpoint list --resource-group {rg} --query "[].name" -o tsv
foreach ($pe in $pes) {
    $nicId = az network private-endpoint show --name $pe --resource-group {rg} \
      --query "networkInterfaces[0].id" -o tsv
    az network nic show --ids $nicId \
      --query "ipConfigurations[].{ip:privateIPAddress, fqdn:privateLinkConnectionProperties.fqdns[0]}" -o table
}
```

#### 12A.4 — Generate hosts file entries

Generate the lines for `C:\Windows\System32\drivers\etc\hosts` (or `/etc/hosts` on Linux/Mac):
```
# Foundry VNet - {rg} ({vnetName})
{ip}  {fqdn}
...
```

Present the lines to the user and remind them to:
1. Edit the hosts file with **administrator permissions**
2. **Reconnect the VPN client** (disconnect and reconnect) so it loads the routes
   for the new IP range through the peering with gateway transit
3. Verify connectivity: `Test-NetConnection -ComputerName {fqdn} -Port 443`

> **Note**: The hosts file entries are necessary because private DNS resolution
> (Private DNS Zones) only works inside the VNet. P2S VPN clients resolve DNS
> externally, so they need the hosts entries to point to the private IPs of
> the endpoints.

### Step 12B — No access configured (create a new VPN Gateway)

If the user has no means of accessing the VNet, they need to create one.
The most common option for development/testing is a VPN Gateway with Point-to-Site.

Inform the user of what they need and offer help to create it:

1. **VPN Gateway** in the deployment's VNet (or in another VNet with peering):
   - Requires a `GatewaySubnet` (minimum /27) in the VNet.
   - Recommended SKU: `VpnGw1` (sufficient for development, ~30 min to deploy).
   - Configure P2S with self-signed certificates or Azure AD auth.
   
   ```powershell
   # Create GatewaySubnet in the deployment's VNet
   az network vnet subnet create \
     --resource-group {rg} \
     --vnet-name {vnetName} \
     --name GatewaySubnet \
     --address-prefixes {gatewaySubnetPrefix}  # e.g. 10.1.2.0/27
   
   # Create public IP for the gateway
   az network public-ip create \
     --resource-group {rg} \
     --name "{vnetName}-gateway-pip" \
     --allocation-method Static \
     --sku Standard
   
   # Create VPN Gateway (takes ~30 minutes)
   az network vnet-gateway create \
     --resource-group {rg} \
     --name "{vnetName}-vpn-gateway" \
     --vnet {vnetName} \
     --public-ip-addresses "{vnetName}-gateway-pip" \
     --gateway-type Vpn \
     --vpn-type RouteBased \
     --sku VpnGw1 \
     --vpn-gateway-generation Generation1 \
     --no-wait
   ```

2. **Faster alternative — Azure Bastion + VM**:
   - Create a VM in the same VNet (in `pe-subnet` or a new subnet).
   - Configure Azure Bastion for web access to the VM desktop.
   - From the VM, private resources are resolved directly via Private DNS Zones.
   - No hosts file needed.

Ask the user which option they prefer and inform that both take ~30 min to deploy.

### Step 12C — Already has access (VM, Bastion, ExpressRoute)

If the user already has access to the VNet (or to a peered VNet) via VM, Bastion,
ExpressRoute or other means:

1. If they access **from inside the VNet** (VM/Bastion): private DNS resolution
   works automatically via Private DNS Zones → **no hosts file needed**.

2. If they access **from a different VNet with peering**: verify that:
   - Bidirectional peering exists with `Connected` state
   - The DNS zones have VNet links to that VNet too
   - If not, create the VNet links (see step 11.8)

3. If they access **via ExpressRoute**: verify that the ExpressRoute circuit is
   connected to the deployment's VNet (directly or via peering) and that the
   DNS zones have VNet links configured.

### Step 12D — AI Citadel hub spoke (post-deploy verification)

If Step 8d enabled Citadel hub integration, the deployment has already created
the **spoke-side** peering and (optionally) linked the APIM private DNS zone to
the spoke VNet. Two things still need to happen before `citadel-spoke-onboarding`
can run successfully against the project:

#### 12D.1 — Hub team creates the reverse peering

Retrieve the one-line `az` command from the deployment output and hand it to
the Citadel hub team (separate RBAC; they own the hub VNet):

```powershell
$deploymentName = "foundry-vnet-{deployTimestamp}"
az deployment group show --resource-group {rg} --name $deploymentName `
  --query "properties.outputs.hubReversePeeringCommand.value" -o tsv
```

The output looks like:

```
az network vnet peering create --resource-group {hubRg} --vnet-name {hubVnet} \
  --name peering-from-{spokeVnet} \
  --remote-vnet /subscriptions/{spokeSub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{spokeVnet} \
  --allow-vnet-access --allow-forwarded-traffic --subscription {hubSub}
```

Paste it into a Teams/Slack handoff to the hub team.

#### 12D.2 — Pre-flight checklist

Once the hub team confirms the reverse peering is in place, verify end-to-end
from inside the spoke VNet (a peered VM, Bastion, or VPN-connected client):

```powershell
# 1. Both peerings must be in "Connected" state
az network vnet peering show --resource-group {rg} --vnet-name {vnetName} `
  --name {hubPeeringName} --query peeringState -o tsv      # → "Connected"

# 2. APIM hostname must resolve to a private IP (10.x / 192.168.x / 172.16.x)
#    — this requires the privatelink.azure-api.net VNet link from Step 8d.
Resolve-DnsName "{apim}.azure-api.net"

# 3. End-to-end TCP reachability on 443
Test-NetConnection -ComputerName "{apim}.azure-api.net" -Port 443
```

> **NSG egress (manual)** — if the customer attached a custom NSG to the agent
> subnet (foundry-vnet-deploy never does this, since attaching an NSG to a
> delegated subnet is destructive), ensure its outbound rules allow HTTPS (443)
> to the hub VNet address space or to the `AzureCloud` service tag. The default
> subnet NSG is permissive and needs no change.

#### 12D.3 — Hand off to citadel-spoke-onboarding

Once 12D.1 + 12D.2 pass, the project is ready to be onboarded as a Citadel
spoke. Inform the operator:

1. The Foundry account + project ARM IDs needed by `citadel-spoke-onboarding`
   are visible in the deployment outputs (`spokeVnetId`, `agentSubnetName`).
2. Use **Option B (Foundry Connection)** in `citadel-spoke-onboarding` —
   Option A (Key Vault secret pull) violates the keyless-by-mandate posture
   that VNet-isolated spokes require.
3. The hub team-owned APIM gateway URL is what the Foundry connection routes
   to; the agent's UAMI is the only credential threaded through the call.

### Step 13: Final notes

After successful verification, remind the user:

1. To use the Agents they need **VNet access** (VPN, ExpressRoute, Bastion, or a VM in the VNet).
2. They can verify the private IPs of the endpoints with `get_ips_services.ps1`.
3. The account capability host (with `customerSubnet`) and the project one are already created — **there is NO need to run `createCapHost.sh`** manually.
4. If they have a VPN Gateway with peering configured, they must **reconnect the VPN client** after creating the peering to load the new routes.

## 4. Important rules

1. **Always** use `ask_user` for each question. DO NOT put multiple questions in a single one.
2. **Offer default values** whenever possible to minimize user input.
3. **Validate** Resource ID formats before continuing (they must start with `/subscriptions/`).
4. **Do not** generate the .bicepparam until you have ALL parameters.
5. **Save** the .bicepparam file with a descriptive name (e.g. `deploy-{rg}.bicepparam`) in the same directory as `main.bicep`, **never** overwrite `main.bicepparam`.
6. The Bicep files (`main.bicep`, `main.bicepparam` and the `modules-network-secured/` folder) live in the **`templates/` subfolder of this skill**. Locate that path and use it as the working directory for the deployments — copy them out to a workspace folder first if you want to keep the originals pristine.
7. If the user passed a one-line scenario hint when invoking the skill (see the **Goal** section), use it to pre-fill values whenever possible.
8. **Always generate and store a fixed `deploymentTimestamp`** before the first deployment. Pass it as `--parameters deploymentTimestamp={timestamp}` on every attempt (including retries). This guarantees that `uniqueSuffix` is identical and resources are not duplicated.
9. **On retries**, first verify whether the Account Capability Host completed internally (via REST API PUT → look for "Conflict" error with "Succeeded"). If it already exists, create the Project Capability Host directly via the REST API and then re-run the full deployment with the same timestamp to complete the role assignments.
10. **Citadel hub integration is opt-in via Step 8d.** When the spoke will be onboarded as a Citadel hub spoke, complete Step 12D (hub team creates the reverse peering, all three pre-flight checks pass) **before** running `citadel-spoke-onboarding`. Otherwise the injected APIM Foundry connection's first call will time out — either no route to the hub, or no DNS resolution for `{apim}.azure-api.net`.

---

## 5. References

- **Foundry Samples** — [`15-private-network-standard-agent-setup`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup) — Bicep template set under `templates/` derives from this Foundry samples reference.
- **Original interview/automation logic** — Angel Sevillano (Microsoft), [`asevillano/foundry-vnet-deploy`](https://github.com/asevillano/foundry-vnet-deploy).
- **Related skills** — `azure-tenant-isolation` (set up first), `foundry-hosted-agents` (deploy agents into the host this skill creates), `threadlight-deploy` (`azd`-based public-network alternative), `foundry-cross-resource` (APIM cross-resource model wiring on top), **`citadel-spoke-onboarding` — see Step 8d + Step 12D for the network plumbing this skill creates so the deployed Foundry can be onboarded as a Citadel hub spoke**, `foundry-observability` (App Insights wiring if Step 8c was opted in).
- **Template fork notice** — the `templates/` set started as a clone of [`15-private-network-standard-agent-setup`](https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup); awesome-gbb adds three optional integration paths on top: (1) `modules-network-secured/spoke-hub-peering.bicep` and (2) `modules-network-secured/apim-dns-zone-link.bicep` are awesome-gbb-only modules wired into `main.bicep` behind the new `hubVnetResourceId` / `apimDnsZoneResourceId` parameters; (3) `main.bicep` emits a `hubReversePeeringCommand` deployment output. Future upstream syncs must diff against the original 23 modules and re-apply these additions.

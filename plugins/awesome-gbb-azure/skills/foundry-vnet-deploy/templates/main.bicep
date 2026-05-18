/*
Standard Setup Network Secured Steps for main.bicep
-----------------------------------
*/
@description('Location for all resources.')
@allowed([
  'westus'
  'eastus'
  'eastus2'
  'japaneast'
  'francecentral'
  'spaincentral'
  'uaenorth'
  'southcentralus'
  'italynorth'
  'germanywestcentral'
  'brazilsouth'
  'southafricanorth'
  'australiaeast'
  'swedencentral'
  'canadaeast'
  'westeurope'
  'westus3'
  'uksouth'
  'southindia'

  //only class B and C
  'koreacentral'
  'polandcentral'
  'switzerlandnorth'
  'norwayeast'
])
param location string = 'eastus'

@description('Name for your AI Services resource.')
param aiServices string = 'aiservices'

// Model deployment parameters
@description('The name of the model you want to deploy')
param modelName string = 'gpt-4.1'
@description('The provider of your model')
param modelFormat string = 'OpenAI'
@description('The version of your model')
param modelVersion string = '2025-04-14'
@description('The sku of your model deployment')
param modelSkuName string = 'GlobalStandard'
@description('The tokens per minute (TPM) of your model deployment')
param modelCapacity int = 30

// Create a short, unique suffix, that will be unique to each resource group
param deploymentTimestamp string = utcNow('yyyyMMddHHmmss')
var uniqueSuffix = substring(uniqueString('${resourceGroup().id}-${deploymentTimestamp}'), 0, 4)
var accountName = toLower('${aiServices}${uniqueSuffix}')

@description('Name for your project resource.')
param firstProjectName string = 'project'

@description('This project will be a sub-resource of your account')
param projectDescription string = 'A project for the AI Foundry account with network secured deployed Agent'

@description('The display name of the project')
param displayName string = 'network secured agent project'

// Existing Virtual Network parameters
@description('Virtual Network name for the Agent to create new or existing virtual network')
param vnetName string = 'agent-vnet-test'

@description('The name of Agents Subnet to create new or existing subnet for agents')
param agentSubnetName string = 'agent-subnet'

@description('The name of Private Endpoint subnet to create new or existing subnet for private endpoints')
param peSubnetName string = 'pe-subnet'

//Existing standard Agent required resources
@description('Existing Virtual Network name Resource ID')
param existingVnetResourceId string = ''

@description('Address space for the VNet (only used for new VNet)')
param vnetAddressPrefix string = ''

@description('Address prefix for the agent subnet. The default value is 192.168.0.0/24 but you can choose any size /26 or any class like 10.0.0.0 or 172.168.0.0')
param agentSubnetPrefix string = ''

@description('Address prefix for the private endpoint subnet')
param peSubnetPrefix string = ''

@description('The AI Search Service full ARM Resource ID. This is an optional field, and if not provided, the resource will be created.')
param aiSearchResourceId string = ''
@description('The AI Storage Account full ARM Resource ID. This is an optional field, and if not provided, the resource will be created.')
param azureStorageAccountResourceId string = ''
@description('The Cosmos DB Account full ARM Resource ID. This is an optional field, and if not provided, the resource will be created.')
param azureCosmosDBAccountResourceId string = ''

//New Param for resource group of Private DNS zones
//@description('Optional: Resource group containing existing private DNS zones. If specified, DNS zones will not be created.')
//param existingDnsZonesResourceGroup string = ''

@description('Subscription ID where existing private DNS zones are located. Leave empty to use current subscription.')
param dnsZonesSubscriptionId string = ''

@description('Object mapping DNS zone names to their resource group, or empty string to indicate creation')
param existingDnsZones object = {
  'privatelink.services.ai.azure.com': ''
  'privatelink.openai.azure.com': ''
  'privatelink.cognitiveservices.azure.com': ''               
  'privatelink.search.windows.net': ''           
  'privatelink.blob.core.windows.net': ''                            
  'privatelink.documents.azure.com': ''                       
}

@description('Zone Names for Validation of existing Private Dns Zones')
param dnsZoneNames array = [
  'privatelink.services.ai.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.search.windows.net'
  'privatelink.blob.core.windows.net'
  'privatelink.documents.azure.com'
]

@description('AAD object IDs of users / groups / service principals that will create or update hosted agents in this Foundry account. They will be granted Managed Identity Operator on the account and Network Contributor on the agent injection subnet (both required for hosted-agent provisioning in a VNet). Leave empty to skip.')
param agentDeveloperPrincipalIds array = []

@description('Principal type for agentDeveloperPrincipalIds.')
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param agentDeveloperPrincipalType string = 'User'

@description('Name for the Log Analytics workspace that backs Application Insights. Required by hosted agent permissions doc; used by the project for evaluations and trace ingestion.')
param logAnalyticsWorkspaceName string = ''

@description('Name for the Application Insights component used by the Foundry project. Required by hosted agent permissions doc; the project will get a connection to it.')
param appInsightsName string = ''


// ── Citadel hub integration (optional) ──────────────────────────────────────
// All four parameters default to empty/no-op. Existing flows are unchanged.
// Set them in tandem when the spoke will be onboarded as a Citadel hub spoke
// (see SKILL.md Step 12D).

@description('Optional: full ARM ID of the Citadel hub VNet to peer to. Empty = no peering created. When set, this deployment creates the SPOKE-side peering only; the reverse peering must be created by the hub team (see deployment output `hubReversePeeringCommand`).')
param hubVnetResourceId string = ''

@description('Friendly name for the spoke-side peering (used only when `hubVnetResourceId` is non-empty).')
param hubPeeringName string = 'peering-to-hub'

@description('Optional: full ARM ID of an existing `privatelink.azure-api.net` private DNS zone (typically owned by the Citadel hub team). Empty = no link created. When set, this deployment links the zone to the spoke VNet so the agent can resolve the APIM gateway hostname to its private IP.')
param apimDnsZoneResourceId string = ''

@description('Friendly name for the VNet-link record on the APIM DNS zone (used only when `apimDnsZoneResourceId` is non-empty). Must be unique within the zone.')
param apimDnsZoneLinkName string = 'foundry-spoke-link'


var projectName = toLower('${firstProjectName}${uniqueSuffix}')
var cosmosDBName = toLower('${aiServices}${uniqueSuffix}cosmosdb')
var aiSearchName = toLower('${aiServices}${uniqueSuffix}search')
var azureStorageName = toLower('${aiServices}${uniqueSuffix}storage')
var logAnalyticsName = empty(logAnalyticsWorkspaceName) ? toLower('${aiServices}${uniqueSuffix}-law') : logAnalyticsWorkspaceName
var appInsightsResolvedName = empty(appInsightsName) ? toLower('${aiServices}${uniqueSuffix}-ai') : appInsightsName

// Check if existing resources have been passed in
var storagePassedIn = azureStorageAccountResourceId != ''
var searchPassedIn = aiSearchResourceId != ''
var cosmosPassedIn = azureCosmosDBAccountResourceId != ''
var existingVnetPassedIn = existingVnetResourceId != ''


var acsParts = split(aiSearchResourceId, '/')
var aiSearchServiceSubscriptionId = searchPassedIn ? acsParts[2] : subscription().subscriptionId
var aiSearchServiceResourceGroupName = searchPassedIn ? acsParts[4] : resourceGroup().name

var cosmosParts = split(azureCosmosDBAccountResourceId, '/')
var cosmosDBSubscriptionId = cosmosPassedIn ? cosmosParts[2] : subscription().subscriptionId
var cosmosDBResourceGroupName = cosmosPassedIn ? cosmosParts[4] : resourceGroup().name

var storageParts = split(azureStorageAccountResourceId, '/')
var azureStorageSubscriptionId = storagePassedIn ? storageParts[2] : subscription().subscriptionId
var azureStorageResourceGroupName = storagePassedIn ? storageParts[4] : resourceGroup().name

var vnetParts = split(existingVnetResourceId, '/')
var vnetSubscriptionId = existingVnetPassedIn ? vnetParts[2] : subscription().subscriptionId
var vnetResourceGroupName = existingVnetPassedIn ? vnetParts[4] : resourceGroup().name
var existingVnetName = existingVnetPassedIn ? last(vnetParts) : vnetName
var trimVnetName = trim(existingVnetName)

// Resolve DNS zones subscription ID - use current subscription if not specified
var resolvedDnsZonesSubscriptionId = empty(dnsZonesSubscriptionId) ? subscription().subscriptionId : dnsZonesSubscriptionId

// ── Citadel hub integration: resolve targets ───────────────────────────────
var hubPeeringEnabled = !empty(hubVnetResourceId)
var apimDnsLinkEnabled = !empty(apimDnsZoneResourceId)

var apimDnsZoneParts = split(apimDnsZoneResourceId, '/')
var apimDnsZoneSubscriptionId = apimDnsLinkEnabled ? apimDnsZoneParts[2] : subscription().subscriptionId
var apimDnsZoneResourceGroupName = apimDnsLinkEnabled ? apimDnsZoneParts[4] : resourceGroup().name
var apimDnsZoneName = apimDnsLinkEnabled ? last(apimDnsZoneParts) : 'privatelink.azure-api.net'

@description('The name of the project capability host to be created')
param projectCapHost string = 'caphostproj'

@description('The name of the account-level capability host to be created (network-injected setup)')
param accountCapHost string = 'caphostacct'

// Create Virtual Network and Subnets
module vnet 'modules-network-secured/network-agent-vnet.bicep' = {
  name: 'vnet-${trimVnetName}-${uniqueSuffix}-deployment'
  params: {
    location: location
    vnetName: trimVnetName
    useExistingVnet: existingVnetPassedIn
    existingVnetResourceGroupName: vnetResourceGroupName
    agentSubnetName: agentSubnetName
    peSubnetName: peSubnetName
    vnetAddressPrefix: vnetAddressPrefix
    agentSubnetPrefix: agentSubnetPrefix
    peSubnetPrefix: peSubnetPrefix
    existingVnetSubscriptionId: vnetSubscriptionId
  }
}

/*
  Create the AI Services account and gpt-4o model deployment
*/
module aiAccount 'modules-network-secured/ai-account-identity.bicep' = {
  name: '${accountName}-${uniqueSuffix}-deployment'
  params: {
    // workspace organization
    accountName: accountName
    location: location
    modelName: modelName
    modelFormat: modelFormat
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
    agentSubnetId: vnet.outputs.agentSubnetId
  }
}
/*
  Validate existing resources
  This module will check if the AI Search Service, Storage Account, and Cosmos DB Account already exist.
  If they do, it will set the corresponding output to true. If they do not exist, it will set the output to false.
*/
module validateExistingResources 'modules-network-secured/validate-existing-resources.bicep' = {
  name: 'validate-existing-resources-${uniqueSuffix}-deployment'
  params: {
    aiSearchResourceId: aiSearchResourceId
    azureStorageAccountResourceId: azureStorageAccountResourceId
    azureCosmosDBAccountResourceId: azureCosmosDBAccountResourceId
    existingDnsZones: existingDnsZones
    dnsZoneNames: dnsZoneNames
    dnsZonesSubscriptionId: resolvedDnsZonesSubscriptionId
  }
}

// This module will create new agent dependent resources
// A Cosmos DB account, an AI Search Service, and a Storage Account are created if they do not already exist
module aiDependencies 'modules-network-secured/standard-dependent-resources.bicep' = {
  name: 'dependencies-${uniqueSuffix}-deployment'
  params: {
    location: location
    azureStorageName: azureStorageName
    aiSearchName: aiSearchName
    cosmosDBName: cosmosDBName

    // AI Search Service parameters
    aiSearchResourceId: aiSearchResourceId
    aiSearchExists: validateExistingResources.outputs.aiSearchExists

    // Storage Account
    azureStorageAccountResourceId: azureStorageAccountResourceId
    azureStorageExists: validateExistingResources.outputs.azureStorageExists

    // Cosmos DB Account
    cosmosDBResourceId: azureCosmosDBAccountResourceId
    cosmosDBExists: validateExistingResources.outputs.cosmosDBExists
    }
}

resource storage 'Microsoft.Storage/storageAccounts@2022-05-01' existing = {
  name: aiDependencies.outputs.azureStorageName
  scope: resourceGroup(azureStorageSubscriptionId, azureStorageResourceGroupName)
}


resource aiSearch 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: aiDependencies.outputs.aiSearchName
  scope: resourceGroup(aiDependencies.outputs.aiSearchServiceSubscriptionId, aiDependencies.outputs.aiSearchServiceResourceGroupName)
}

resource cosmosDB 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: aiDependencies.outputs.cosmosDBName
  scope: resourceGroup(cosmosDBSubscriptionId, cosmosDBResourceGroupName)
}

// Private Endpoint and DNS Configuration
// This module sets up private network access for all Azure services:
// 1. Creates private endpoints in the specified subnet
// 2. Sets up private DNS zones for each service
// 3. Links private DNS zones to the VNet for name resolution
// 4. Configures network policies to restrict access to private endpoints only
module privateEndpointAndDNS 'modules-network-secured/private-endpoint-and-dns.bicep' = {
    name: '${uniqueSuffix}-private-endpoint'
    params: {
      aiAccountName: aiAccount.outputs.accountName    // AI Services to secure
      aiSearchName: aiDependencies.outputs.aiSearchName       // AI Search to secure
      storageName: aiDependencies.outputs.azureStorageName        // Storage to secure
      cosmosDBName:aiDependencies.outputs.cosmosDBName
      vnetName: vnet.outputs.virtualNetworkName    // VNet containing subnets
      peSubnetName: vnet.outputs.peSubnetName        // Subnet for private endpoints
      suffix: uniqueSuffix                                    // Unique identifier
      vnetResourceGroupName: vnet.outputs.virtualNetworkResourceGroup
      vnetSubscriptionId: vnet.outputs.virtualNetworkSubscriptionId // Subscription ID for the VNet
      cosmosDBSubscriptionId: cosmosDBSubscriptionId // Subscription ID for Cosmos DB
      cosmosDBResourceGroupName: cosmosDBResourceGroupName // Resource Group for Cosmos DB
      aiSearchSubscriptionId: aiSearchServiceSubscriptionId // Subscription ID for AI Search Service
      aiSearchResourceGroupName: aiSearchServiceResourceGroupName // Resource Group for AI Search Service
      storageAccountResourceGroupName: azureStorageResourceGroupName // Resource Group for Storage Account
      storageAccountSubscriptionId: azureStorageSubscriptionId // Subscription ID for Storage Account
      existingDnsZones: existingDnsZones
      dnsZonesSubscriptionId: resolvedDnsZonesSubscriptionId
    }
    dependsOn: [
    aiSearch      // Ensure AI Search exists
    storage       // Ensure Storage exists
    cosmosDB      // Ensure Cosmos DB exists
  ]
  }

/*
  Creates a new project (sub-resource of the AI Services account)
*/
module aiProject 'modules-network-secured/ai-project-identity.bicep' = {
  name: '${projectName}-${uniqueSuffix}-deployment'
  params: {
    // workspace organization
    projectName: projectName
    projectDescription: projectDescription
    displayName: displayName
    location: location

    aiSearchName: aiDependencies.outputs.aiSearchName
    aiSearchServiceResourceGroupName: aiDependencies.outputs.aiSearchServiceResourceGroupName
    aiSearchServiceSubscriptionId: aiDependencies.outputs.aiSearchServiceSubscriptionId

    cosmosDBName: aiDependencies.outputs.cosmosDBName
    cosmosDBSubscriptionId: aiDependencies.outputs.cosmosDBSubscriptionId
    cosmosDBResourceGroupName: aiDependencies.outputs.cosmosDBResourceGroupName

    azureStorageName: aiDependencies.outputs.azureStorageName
    azureStorageSubscriptionId: aiDependencies.outputs.azureStorageSubscriptionId
    azureStorageResourceGroupName: aiDependencies.outputs.azureStorageResourceGroupName
    // dependent resources
    accountName: aiAccount.outputs.accountName
  }
  dependsOn: [
     privateEndpointAndDNS
     cosmosDB
     aiSearch
     storage
  ]
}

module formatProjectWorkspaceId 'modules-network-secured/format-project-workspace-id.bicep' = {
  name: 'format-project-workspace-id-${uniqueSuffix}-deployment'
  params: {
    projectWorkspaceId: aiProject.outputs.projectWorkspaceId
  }
}

/*
  Assigns the project SMI the storage blob data contributor role on the storage account
*/
module storageAccountRoleAssignment 'modules-network-secured/azure-storage-account-role-assignment.bicep' = {
  name: 'storage-${azureStorageName}-${uniqueSuffix}-deployment'
  scope: resourceGroup(azureStorageSubscriptionId, azureStorageResourceGroupName)
  params: {
    azureStorageName: aiDependencies.outputs.azureStorageName
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
  dependsOn: [
   storage
   privateEndpointAndDNS
  ]
}

// The Comos DB Operator role must be assigned before the caphost is created
module cosmosAccountRoleAssignments 'modules-network-secured/cosmosdb-account-role-assignment.bicep' = {
  name: 'cosmos-account-ra-${uniqueSuffix}-deployment'
  scope: resourceGroup(cosmosDBSubscriptionId, cosmosDBResourceGroupName)
  params: {
    cosmosDBName: aiDependencies.outputs.cosmosDBName
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
  dependsOn: [
    cosmosDB
    privateEndpointAndDNS
  ]
}

// This role can be assigned before or after the caphost is created
module aiSearchRoleAssignments 'modules-network-secured/ai-search-role-assignments.bicep' = {
  name: 'ai-search-ra-${uniqueSuffix}-deployment'
  scope: resourceGroup(aiSearchServiceSubscriptionId, aiSearchServiceResourceGroupName)
  params: {
    aiSearchName: aiDependencies.outputs.aiSearchName
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
  dependsOn: [
    aiSearch
    privateEndpointAndDNS
  ]
}

// Creates the ACCOUNT-level capability host (sets customerSubnet on the account).
// Required for network-injected Standard Agent setup; replaces the manual createCapHost.sh.
module addAccountCapabilityHost 'modules-network-secured/add-account-capability-host.bicep' = {
  name: 'account-capabilityHost-${uniqueSuffix}-deployment'
  params: {
    accountName: aiAccount.outputs.accountName
    accountCapHost: accountCapHost
    agentSubnetId: vnet.outputs.agentSubnetId
  }
  dependsOn: [
    privateEndpointAndDNS
  ]
}

// This module creates the capability host for the project and account
module addProjectCapabilityHost 'modules-network-secured/add-project-capability-host.bicep' = {
  name: 'capabilityHost-configuration-${uniqueSuffix}-deployment'
  params: {
    accountName: aiAccount.outputs.accountName
    projectName: aiProject.outputs.projectName
    cosmosDBConnection: aiProject.outputs.cosmosDBConnection
    azureStorageConnection: aiProject.outputs.azureStorageConnection
    aiSearchConnection: aiProject.outputs.aiSearchConnection
    projectCapHost: projectCapHost
  }
  dependsOn: [
     aiSearch      // Ensure AI Search exists
     storage       // Ensure Storage exists
     cosmosDB
     privateEndpointAndDNS
     cosmosAccountRoleAssignments
     storageAccountRoleAssignment
     aiSearchRoleAssignments
     addAccountCapabilityHost  // Account caphost must exist before project caphost
  ]
}

// The Storage Blob Data Owner role must be assigned after the caphost is created
module storageContainersRoleAssignment 'modules-network-secured/blob-storage-container-role-assignments.bicep' = {
  name: 'storage-containers-ra-${uniqueSuffix}-deployment'
  scope: resourceGroup(azureStorageSubscriptionId, azureStorageResourceGroupName)
  params: {
    aiProjectPrincipalId: aiProject.outputs.projectPrincipalId
    storageName: aiDependencies.outputs.azureStorageName
    workspaceId: formatProjectWorkspaceId.outputs.projectWorkspaceIdGuid
  }
  dependsOn: [
    addProjectCapabilityHost
  ]
}

// The Cosmos Built-In Data Contributor role must be assigned after the caphost is created
module cosmosContainerRoleAssignments 'modules-network-secured/cosmos-container-role-assignments.bicep' = {
  name: 'cosmos-containers-ra-${uniqueSuffix}-deployment'
  scope: resourceGroup(cosmosDBSubscriptionId, cosmosDBResourceGroupName)
  params: {
    cosmosAccountName: aiDependencies.outputs.cosmosDBName
    projectWorkspaceId: formatProjectWorkspaceId.outputs.projectWorkspaceIdGuid
    projectPrincipalId: aiProject.outputs.projectPrincipalId

  }
dependsOn: [
  addProjectCapabilityHost
  storageContainersRoleAssignment
  ]
}

// Grant the listed agent-developer principals the prerequisite roles needed to
// create hosted agents in this network-injected Foundry account:
//   - Managed Identity Operator on the Foundry account
//   - Network Contributor on the agent injection subnet
module agentDeveloperRoleAssignments 'modules-network-secured/agent-developer-role-assignments.bicep' = if (!empty(agentDeveloperPrincipalIds)) {
  name: 'agent-dev-ra-${uniqueSuffix}-deployment'
  params: {
    principalIds: agentDeveloperPrincipalIds
    principalType: agentDeveloperPrincipalType
    accountName: aiAccount.outputs.accountName
    vnetName: vnet.outputs.virtualNetworkName
    agentSubnetName: vnet.outputs.agentSubnetName
    vnetResourceGroupName: vnet.outputs.virtualNetworkResourceGroup
    vnetSubscriptionId: vnet.outputs.virtualNetworkSubscriptionId
  }
}

// ---------------------------------------------------------------------------
// Application Insights + Log Analytics Workspace
// Required by hosted agent permissions doc as part of the standard setup.
// They enable agent telemetry, trace viewing and evaluations.
// ---------------------------------------------------------------------------
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsResolvedName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
  }
}

// AppInsights connection in the project (uses ApiKey auth with the AI connection string).
// Uses the locally computed accountName/projectName (deterministic at start of deployment).
resource accountForAiConn 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}
resource projectForAiConn 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: accountForAiConn
  name: projectName
}
resource projectAppInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: projectForAiConn
  name: 'appinsights'
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    authType: 'ApiKey'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
    }
    credentials: {
      key: appInsights.properties.ConnectionString
    }
  }
  dependsOn: [
    aiProject
  ]
}

// Grant the project MI: Log Analytics Reader on the LAW + Azure AI User on the account
module appInsightsRoleAssignments 'modules-network-secured/app-insights-role-assignments.bicep' = {
  name: 'appinsights-ra-${uniqueSuffix}-deployment'
  params: {
    accountName: aiAccount.outputs.accountName
    logAnalyticsWorkspaceName: logAnalyticsWorkspace.name
    projectPrincipalId: aiProject.outputs.projectPrincipalId
  }
}

// ── Citadel hub integration (optional) ─────────────────────────────────────
// Spoke-side peering to the Citadel hub VNet. The hub-side reverse peering
// is hub-team RBAC; this deployment emits `hubReversePeeringCommand` for them.
module spokeHubPeering 'modules-network-secured/spoke-hub-peering.bicep' = if (hubPeeringEnabled) {
  name: 'spoke-hub-peering-${uniqueSuffix}-deployment'
  scope: resourceGroup(vnetSubscriptionId, vnetResourceGroupName)
  params: {
    spokeVnetName: vnet.outputs.virtualNetworkName
    hubVnetResourceId: hubVnetResourceId
    peeringName: hubPeeringName
  }
}

// Link the hub's privatelink.azure-api.net DNS zone to the spoke VNet so
// the agent resolves the APIM gateway hostname to its private IP.
module apimDnsZoneLink 'modules-network-secured/apim-dns-zone-link.bicep' = if (apimDnsLinkEnabled) {
  name: 'apim-dns-zone-link-${uniqueSuffix}-deployment'
  scope: resourceGroup(apimDnsZoneSubscriptionId, apimDnsZoneResourceGroupName)
  params: {
    zoneName: apimDnsZoneName
    spokeVnetResourceId: vnet.outputs.virtualNetworkId
    linkName: apimDnsZoneLinkName
  }
}

// Outputs the hub team needs to complete the bidirectional peering. Empty
// when Citadel hub integration is not enabled.
var hubVnetParts = split(hubVnetResourceId, '/')
output hubReversePeeringCommand string = hubPeeringEnabled ? 'az network vnet peering create --resource-group ${hubVnetParts[4]} --vnet-name ${last(hubVnetParts)} --name peering-from-${trimVnetName} --remote-vnet ${vnet.outputs.virtualNetworkId} --allow-vnet-access --allow-forwarded-traffic --subscription ${hubVnetParts[2]}' : ''
output spokeVnetId string = vnet.outputs.virtualNetworkId
output spokeVnetAddressSpace string = vnetAddressPrefix
output agentSubnetName string = vnet.outputs.agentSubnetName

param name string
param location string
param tags object
param ciPrincipalId string
param provisionerPrincipalId string

@description('Managed-identity principal IDs of Foundry projects whose KB MCP connections call this service.')
param projectPrincipalIds array = []

var searchServiceContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
)
var searchIndexDataContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
)
var searchIndexDataReaderRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '1407120a-92aa-4202-b7e9-c0e197c71c8f'
)
var readerRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'acdd72a7-3385-48ef-bd42-f606fba81ae7'
)

// The preview management API is required only to set knowledgeRetrieval
// billing. The live fixture itself uses the stable 2026-04-01 data plane.
resource searchService 'Microsoft.Search/searchServices@2026-03-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  // The system-assigned identity calls the knowledge base planning model.
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    disableLocalAuth: true
    knowledgeRetrieval: 'standard'
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    replicaCount: 1
    semanticSearch: 'free'
  }
}

// Search Service Contributor is required to create indexes and knowledge sources.
resource ciSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, ciPrincipalId, searchServiceContributorRoleId)
  properties: {
    principalId: ciPrincipalId
    roleDefinitionId: searchServiceContributorRoleId
  }
}

// Search Index Data Contributor lets the smoke upload its known-answer
// documents and call retrieve. It is a data-plane role; Contributor alone
// cannot read or write documents.
resource ciSearchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, ciPrincipalId, searchIndexDataContributorRoleId)
  properties: {
    principalId: ciPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: searchIndexDataContributorRoleId
  }
}

// Foundry Agent Service calls the KB MCP endpoint as the project managed
// identity (RemoteTool connection, ProjectManagedIdentity auth).
resource projectSearchIndexDataReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for projectPrincipalId in projectPrincipalIds: {
  scope: searchService
  name: guid(searchService.id, projectPrincipalId, searchIndexDataReaderRoleId)
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: searchIndexDataReaderRoleId
  }
}]

// Reader permits tag-based Resource Graph discovery without exposing the endpoint.
resource ciReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, ciPrincipalId, readerRoleId)
  properties: {
    principalId: ciPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: readerRoleId
  }
}

resource provisionerSearchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (provisionerPrincipalId != ciPrincipalId) {
  scope: searchService
  name: guid(searchService.id, provisionerPrincipalId, searchServiceContributorRoleId)
  properties: {
    principalId: provisionerPrincipalId
    roleDefinitionId: searchServiceContributorRoleId
  }
}

output endpoint string = 'https://${searchService.name}.search.windows.net'
output name string = searchService.name
output principalId string = searchService.identity.principalId

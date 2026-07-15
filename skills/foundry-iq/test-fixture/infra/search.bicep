param name string
param location string
param tags object
param ciPrincipalId string
param provisionerPrincipalId string

var searchServiceContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
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

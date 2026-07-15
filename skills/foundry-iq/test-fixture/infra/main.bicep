targetScope = 'subscription'

@description('Dedicated resource group for the standing Foundry IQ CI Search service.')
param resourceGroupName string

@description('Tenant ID expected by the isolated deployment environment.')
param expectedTenantId string

@description('Subscription ID expected by the isolated deployment environment.')
param expectedSubscriptionId string

@description('Azure region that supports agentic retrieval.')
param location string

@description('Object ID of the GitHub Actions UAMI that executes the live smoke.')
param ciPrincipalId string

@description('Object ID of the operator provisioning the standing CI service.')
param provisionerPrincipalId string

var deploymentContextIsSafe = resourceGroupName != 'rg-awesome-gbb-ci' && startsWith(resourceGroupName, 'rg-foundry-iq-') && length(resourceGroupName) > length('rg-foundry-iq-') && tenant().tenantId == expectedTenantId && subscription().subscriptionId == expectedSubscriptionId

var tags = {
  SecurityControl: 'Ignore'
  lifecycle: 'persistent-ci'
  'created-by': 'azd'
  workload: 'foundry-iq'
}

// ARM rejects an empty module deployment name during template validation.
// Keeping every mutable resource behind this dependency makes an unsafe
// context fail before the resource group can be created or updated.
module deploymentSafetyGuard './deployment-safety.bicep' = {
  name: deploymentContextIsSafe ? 'foundry-iq-deployment-safety' : ''
}

resource smokeResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
  dependsOn: [
    deploymentSafetyGuard
  ]
}

module searchService './search.bicep' = {
  scope: smokeResourceGroup
  name: 'search'
  params: {
    name: 'srch${uniqueString(subscription().id, resourceGroupName)}'
    location: location
    tags: tags
    ciPrincipalId: ciPrincipalId
    provisionerPrincipalId: provisionerPrincipalId
  }
}

output AZURE_RESOURCE_GROUP string = smokeResourceGroup.name
output AZURE_SEARCH_ENDPOINT string = searchService.outputs.endpoint
output AZURE_SEARCH_SERVICE_NAME string = searchService.outputs.name

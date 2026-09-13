targetScope = 'subscription'

@maxLength(20)
param environmentName string
param resourceGroupName string
param acaEnvironmentName string
param acrName string
param identityName string
param mcpTenantId string
param mcpApiClientId string

// Brownfield only. Gate B preflight must prove this environment is internal,
// VNet-connected, and reachable from the actual Foundry runtimes.
resource group 'Microsoft.Resources/resourceGroups@2024-03-01' existing = {
  name: resourceGroupName
}
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  scope: group
  name: acaEnvironmentName
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  scope: group
  name: acrName
}
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  scope: group
  name: identityName
}

var name = '${environmentName}-mcp'
var baseUrl = 'https://${name}.${environment.properties.defaultDomain}'

// Reuse the catalog module, including its app-level external ingress. In an
// INTERNAL ACA environment this permits VNet callers, not public internet access.
module mcp '../../../azd-patterns/references/bicep/aca-app.bicep' = {
  scope: group
  name: '${environmentName}-mcp'
  params: {
    name: name
    location: environment.location
    tags: {
      'azd-env-name': environmentName
      'azd-service-name': 'mcp'
    }
    acaEnvironmentId: environment.id
    uamiResourceId: identity.id
    acrLoginServer: registry.properties.loginServer
    containerImage: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
    targetPort: 8080
    cpu: '0.5'
    memory: '1Gi'
    minReplicas: 1
    maxReplicas: 1
    envVars: [
      { name: 'MCP_TENANT_ID', value: mcpTenantId }
      { name: 'MCP_API_CLIENT_ID', value: mcpApiClientId }
      { name: 'MCP_BASE_URL', value: baseUrl }
    ]
  }
}

output AZURE_RESOURCE_GROUP string = group.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = registry.properties.loginServer
output MCP_ENDPOINT string = 'https://${mcp.outputs.fqdn}/mcp'

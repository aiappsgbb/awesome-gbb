// Canonical narrow pull grant for a legacy-permissions ACR.
// Source of truth for `../../SKILL.md § Private network composition`.

param registryName string
param principalIds array
param description string

var acrPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource assignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principalId in principalIds: {
  scope: registry
  name: guid(registry.id, principalId, acrPullRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRole)
    principalId: principalId
    principalType: 'ServicePrincipal'
    description: description
  }
}]
output ids array = [for index in range(0, length(principalIds)): assignments[index].id]

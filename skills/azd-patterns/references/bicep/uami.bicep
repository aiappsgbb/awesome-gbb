// Canonical workload pull identity without bundled permissions.
// Source of truth for `../../SKILL.md § Private network composition`.

param name string
param location string
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}
output id string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId

// Canonical template contract for foundry-mcp-aca-jobs.
// Source of truth for the prose example in ../../../SKILL.md § Security and least-privilege RBAC.

targetScope = 'resourceGroup'

@description('Name of the user-assigned managed identity.')
param name string

@description('Deployment location.')
param location string

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
}

output resourceId string = identity.id
output principalId string = identity.properties.principalId
output clientId string = identity.properties.clientId

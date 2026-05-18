@description('Name of the User-Assigned Managed Identity')
param name string

@description('Location for the identity')
param location string = resourceGroup().location

@description('Tags for the resource')
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = identity.id
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
output name string = identity.name

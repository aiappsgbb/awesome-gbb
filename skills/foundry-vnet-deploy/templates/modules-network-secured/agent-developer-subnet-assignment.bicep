/*
  Inner module: assigns a single role on the agent subnet. Required because
  role assignments must be deployed at the resource scope, and the subnet
  may live in a different subscription/resource group than the Foundry account.
*/

param principalId string
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param principalType string
param vnetName string
param agentSubnetName string
param roleDefinitionId string

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  name: '${vnetName}/${agentSubnetName}'
}

resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subnet.id, principalId, roleDefinitionId)
  scope: subnet
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
    principalId: principalId
    principalType: principalType
  }
}

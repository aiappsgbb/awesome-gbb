/*
  Grants the principals (typically the developers / CI service principals that
  will create or update hosted agents in the Foundry account) the minimum RBAC
  needed for hosted-agent provisioning in a network-injected (VNet) Foundry:

    - Managed Identity Operator on the Foundry (Cognitive Services) account
        Required to attach / operate the system-assigned MIs that Foundry
        creates for each hosted agent (instance_identity, blueprint).
    - Network Contributor on the agent injection subnet
        Required so Foundry can create and bind NICs in the customer subnet
        used for network injection.

  Both assignments are idempotent thanks to the deterministic guid() naming.
  The module is a no-op when the input array is empty.
*/

@description('AAD object IDs of users / groups / service principals that will deploy hosted agents.')
param principalIds array

@description('Type of the principals (User, Group, ServicePrincipal). Applied to all entries in principalIds.')
@allowed([ 'User', 'Group', 'ServicePrincipal' ])
param principalType string = 'User'

@description('Name of the Foundry (Cognitive Services) account.')
param accountName string

@description('Name of the VNet hosting the agent injection subnet.')
param vnetName string

@description('Name of the subnet used for hosted-agent network injection.')
param agentSubnetName string

@description('Resource group of the VNet (defaults to the deployment RG).')
param vnetResourceGroupName string = resourceGroup().name

@description('Subscription of the VNet (defaults to current subscription).')
param vnetSubscriptionId string = subscription().subscriptionId

// Built-in role definitions
var managedIdentityOperatorRoleId = 'f1a07417-d97a-45cb-824c-7a7467783830'
var networkContributorRoleId      = '4d97b98b-1d4f-4787-a291-c67834d212e7'

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  name: '${vnetName}/${agentSubnetName}'
  scope: resourceGroup(vnetSubscriptionId, vnetResourceGroupName)
}

// Managed Identity Operator on the Foundry account
resource miOperatorAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for pid in principalIds: {
  name: guid(account.id, pid, managedIdentityOperatorRoleId)
  scope: account
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', managedIdentityOperatorRoleId)
    principalId: pid
    principalType: principalType
  }
}]

// Network Contributor on the agent injection subnet
module subnetAssignments 'agent-developer-subnet-assignment.bicep' = [for pid in principalIds: {
  name: 'agent-dev-net-${uniqueString(pid, vnetName, agentSubnetName)}'
  scope: resourceGroup(vnetSubscriptionId, vnetResourceGroupName)
  params: {
    principalId: pid
    principalType: principalType
    vnetName: vnetName
    agentSubnetName: agentSubnetName
    roleDefinitionId: networkContributorRoleId
  }
}]

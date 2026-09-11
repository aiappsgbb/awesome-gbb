// Canonical ACA subnet in an existing VNet; no parent-VNet replacement.
// Source of truth for `../../SKILL.md § Private network composition`.

param virtualNetworkName string
param subnetName string
param addressPrefix string
param natGatewayId string

resource network 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: virtualNetworkName
}
resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: network
  name: subnetName
  properties: {
    addressPrefix: addressPrefix
    defaultOutboundAccess: false
    // Preserve the infrastructure policy selected by ACA instead of flipping it on redeploy.
    privateEndpointNetworkPolicies: 'Disabled'
    natGateway: {
      id: natGatewayId
    }
    delegations: [
      {
        name: 'container-app-environments'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}
output id string = subnet.id

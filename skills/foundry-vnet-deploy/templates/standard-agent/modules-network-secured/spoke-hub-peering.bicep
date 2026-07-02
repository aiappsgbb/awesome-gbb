/*
  Spoke-side VNet peering to a Citadel hub VNet.

  Creates ONLY the spoke→hub peering (this RG / spoke-deployer's RBAC).
  The hub→spoke reverse peering must be created by the hub team — main.bicep
  emits an `hubReversePeeringCommand` deployment output for that purpose.

  Properties chosen for a Citadel-spoke posture:
  - allowVirtualNetworkAccess: true   (spoke must reach APIM private IPs)
  - allowForwardedTraffic:    true   (in case hub fronts via firewall/NVA)
  - allowGatewayTransit:      false  (spoke is not a transit hub)
  - useRemoteGateways:        false  (do NOT bind spoke to a hub-side gateway;
                                       this would conflict with Step 12B P2S
                                       VPN setups in the same spoke)
*/

@description('Name of the spoke VNet (the one this deployment created or referenced).')
param spokeVnetName string

@description('Full ARM ID of the Citadel hub VNet to peer to.')
param hubVnetResourceId string

@description('Friendly name for the spoke-side peering.')
param peeringName string = 'peering-to-hub'

resource spokeVnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: spokeVnetName
}

resource peering 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = {
  parent: spokeVnet
  name: peeringName
  properties: {
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: false
    useRemoteGateways: false
    remoteVirtualNetwork: {
      id: hubVnetResourceId
    }
  }
}

output peeringId string = peering.id
output peeringName string = peering.name
output peeringState string = peering.properties.peeringState

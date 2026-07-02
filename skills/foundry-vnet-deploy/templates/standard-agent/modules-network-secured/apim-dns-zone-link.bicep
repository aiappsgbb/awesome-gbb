/*
  Link an existing private DNS zone (typically `privatelink.azure-api.net`,
  governing the Citadel hub APIM private endpoint) to the spoke VNet so
  agents inside the spoke resolve the APIM hostname to its private IP.

  The DNS zone may live in a different subscription / resource group than
  the spoke deployment (typical: hub team owns the zone). The caller (main.bicep)
  is responsible for setting `scope: resourceGroup(zoneSubId, zoneRgName)`
  on this module's invocation so the link lands in the zone's RG.
*/

@description('Name of the private DNS zone to link (e.g. `privatelink.azure-api.net`).')
param zoneName string

@description('Full ARM ID of the spoke VNet to link.')
param spokeVnetResourceId string

@description('Friendly name for the VNet link (must be unique within the DNS zone).')
param linkName string = 'foundry-spoke-link'

@description('Whether this link should auto-register VNet records in the zone. False for privatelink zones.')
param registrationEnabled bool = false

resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: zoneName
}

resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: zone
  name: linkName
  location: 'global'
  properties: {
    registrationEnabled: registrationEnabled
    virtualNetwork: {
      id: spokeVnetResourceId
    }
  }
}

output linkId string = link.id
output linkName string = link.name

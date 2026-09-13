// Canonical DNS for an internal ACA ILB, not an ACA Private Endpoint.
// Source of truth for `../../SKILL.md § Private network composition`.

param defaultDomain string
param staticIp string
param virtualNetworkIds array
param linkNamePrefix string
param tags object = {}

resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: defaultDomain
  location: 'global'
  tags: tags
}
resource records 'Microsoft.Network/privateDnsZones/A@2020-06-01' = [for name in ['@', '*']: {
  parent: zone
  name: name
  properties: {
    ttl: 60
    aRecords: [
      { ipv4Address: staticIp }
    ]
  }
}]
resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (virtualNetworkId, index) in virtualNetworkIds: {
  parent: zone
  name: '${linkNamePrefix}-${index}'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: virtualNetworkId
    }
  }
}]
output id string = zone.id
output recordIds array = [for index in range(0, 2): records[index].id]
output linkIds array = [for index in range(0, length(virtualNetworkIds)): links[index].id]

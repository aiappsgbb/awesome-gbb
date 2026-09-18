// Canonical owner-only perimeter for two dedicated standing Jobs data accounts.
// Source of truth for ../../SKILL.md § Composable Bicep Module Library.
param name string
param location string
param storageId string
param cosmosId string
param tags object = {}

resource perimeter 'Microsoft.Network/networkSecurityPerimeters@2024-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {}
}
resource profile 'Microsoft.Network/networkSecurityPerimeters/profiles@2024-07-01' = {
  parent: perimeter
  name: 'jobs-data'
  properties: {}
}
resource inbound 'Microsoft.Network/networkSecurityPerimeters/profiles/accessRules@2024-07-01' = {
  parent: profile
  name: 'ci-subscription'
  properties: {
    direction: 'Inbound'
    subscriptions: [{ id: subscription().id }]
  }
}
resource associations 'Microsoft.Network/networkSecurityPerimeters/resourceAssociations@2024-07-01' = [for target in [
  { name: 'storage', id: storageId }
  { name: 'cosmos', id: cosmosId }
]: {
  parent: perimeter
  name: target.name
  properties: {
    accessMode: 'Enforced'
    privateLinkResource: { id: target.id }
    profile: { id: profile.id }
  }
  dependsOn: [inbound]
}]
output perimeterId string = perimeter.id
output profileId string = profile.id
output ruleId string = inbound.id
output associationIds array = [for i in range(0, 2): associations[i].id]

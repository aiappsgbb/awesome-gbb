// Canonical internal Consumption environment using Azure Monitor, not shared keys.
// Source of truth for `../../SKILL.md § Private network composition`.

param name string
param location string
param subnetId string
param logAnalyticsWorkspaceId string
param infrastructureResourceGroup string
param tags object = {}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    infrastructureResourceGroup: infrastructureResourceGroup
    vnetConfiguration: {
      infrastructureSubnetId: subnetId
      internal: true
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
}
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: environment
  name: 'to-law'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'ContainerAppConsoleLogs', enabled: true }
      { category: 'ContainerAppSystemLogs', enabled: true }
    ]
  }
}
output id string = environment.id
output defaultDomain string = environment.properties.defaultDomain
output staticIp string = environment.properties.staticIp
output diagnosticsId string = diagnostics.id
output managedResourceGroupName string = environment.properties.infrastructureResourceGroup

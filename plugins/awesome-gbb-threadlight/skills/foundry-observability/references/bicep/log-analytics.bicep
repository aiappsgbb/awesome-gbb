// log-analytics.bicep
// ONE Log Analytics workspace per pilot — drop-in.
// AppIn binds to it (Layer 1); ACA env binds to it (console + system logs);
// cron jobs ship console logs to ContainerAppConsoleLogs_CL via the env binding.
// Drop into infra/modules/, reference from main.bicep, call once per pilot.

@description('Region. Defaults to RG location.')
param location string = resourceGroup().location

@description('Workspace name. Convention: log-{envName}.')
param name string

@description('Retention in days. PerGB2018 minimum is 30. For long-running pilots, bump to 90.')
@minValue(30)
@maxValue(730)
param retentionInDays int = 30

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionInDays
    features: {
      // RBAC-only access. Combined with disableLocalAuth on AppIn this
      // closes the keyless loop for ingestion AND query.
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

@description('ARM resource ID — used by AppIn (workspaceResourceId).')
output workspaceId string = law.id

@description('LAW customer GUID — used in KQL workspace() references and ACA env binding.')
output customerId string = law.properties.customerId

@description('Workspace name — used in az monitor log-analytics CLI calls.')
output workspaceName string = law.name

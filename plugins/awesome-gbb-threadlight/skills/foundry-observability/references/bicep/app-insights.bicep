// app-insights.bicep
// Workspace-based App Insights component (classic mode is deprecated).
// Drop-in. Always-on for every Threadlight pilot — never opt out.
//
// Wiring contract:
//   - workspaceId (input)        : LAW ARM ID from log-analytics.bicep output
//   - uamiPrincipalId (input)    : Workload UAMI principal ID (the one your
//                                  ACA services run as). Granted Application
//                                  Insights Data Ingestor so containers can
//                                  write traces/logs/metrics keylessly.
//   - connectionString (output)  : Consumed by ACA service modules and
//                                  agent.yaml-via-platform-injection.

@description('Region. Defaults to RG location.')
param location string = resourceGroup().location

@description('App Insights component name. Convention: appin-{envName}.')
param name string

@description('Log Analytics workspace ARM ID (from log-analytics.bicep output).')
param workspaceId string

@description('Workload UAMI principal ID — receives Application Insights Data Ingestor on this AppIn.')
param uamiPrincipalId string

@description('Disable local (key-based) ingestion. Threadlight default: true (keyless mandate).')
param disableLocalAuth bool = true

resource appin 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
    DisableLocalAuth: disableLocalAuth
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: 90
  }
}

// Application Insights Data Ingestor (well-known role GUID — DO NOT change)
// Required for the workload UAMI to ingest OTel traces/logs/metrics into
// AppIn under disableLocalAuth=true. "Monitoring Metrics Publisher"
// (3913510d-...) covers only the custom metrics API — it does NOT cover
// OTel exporter ingestion and will cause HTTP 400 "Bad Request".
// The same role must also be granted to the Foundry platform-managed
// identities (AgentService-* and Foundry-*) by the postprovision script
// connect_foundry_appinsights.py — that part can't be done at provision
// time because those identities don't exist until the agent is created.
var dataIngestorRoleId = 'f526a384-b230-433a-b45c-95f59c4a2dec'

resource dataIngestor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: appin
  name: guid(appin.id, uamiPrincipalId, dataIngestorRoleId)
  properties: {
    principalId: uamiPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      dataIngestorRoleId
    )
  }
}

@description('AppIn component ARM ID — used by Foundry account-level connection (postprovision).')
output id string = appin.id

@description('AppIn component name — used in CLI queries.')
output name string = appin.name

@description('Connection string — set as APPLICATIONINSIGHTS_CONNECTION_STRING env on every ACA workload.')
output connectionString string = appin.properties.ConnectionString

@description('Instrumentation key — legacy clients only; prefer connection string.')
output instrumentationKey string = appin.properties.InstrumentationKey

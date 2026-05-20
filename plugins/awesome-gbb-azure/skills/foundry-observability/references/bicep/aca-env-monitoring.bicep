// aca-env-monitoring.bicep
// Azure Container Apps environment with LAW + AppIn binding.
//
// Two distinct integrations — DO NOT confuse them:
//
//   1. LAW shared-key binding (envBinding):
//      ACA writes ContainerAppConsoleLogs_CL + ContainerAppSystemLogs_CL
//      to LAW using customerId + sharedKey. This is the ONE remaining
//      keyed surface in an otherwise-keyless stack — Microsoft has not
//      shipped RBAC-based ACA->LAW binding yet (as of late 2025).
//
//   2. AppIn connection string (passed through to each container as
//      APPLICATIONINSIGHTS_CONNECTION_STRING env var). This is what
//      `configure_azure_monitor()` reads at runtime.
//
// The env doesn't store the AppIn string itself — that's per-container
// env, set in <svc>-aca.bicep. This module only owns the env resource +
// the LAW binding.

@description('Region. Defaults to RG location.')
param location string = resourceGroup().location

@description('ACA environment name. Convention: env-{envName}.')
param name string

@description('LAW customer GUID (from log-analytics.bicep customerId output).')
param workspaceCustomerId string

@description('LAW primary shared key. Look up via listKeys() in main.bicep.')
@secure()
param workspaceSharedKey string

@description('Workload-profile config. Default: Consumption only.')
param workloadProfiles array = [
  {
    name: 'Consumption'
    workloadProfileType: 'Consumption'
  }
]

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspaceCustomerId
        sharedKey: workspaceSharedKey
      }
    }
    workloadProfiles: workloadProfiles
    zoneRedundant: false
  }
}

@description('ACA env ARM ID — referenced by every <svc>-aca.bicep module.')
output id string = env.id

@description('ACA env name.')
output name string = env.name

@description('Default domain (e.g., bluepeak-abcd1234.swedencentral.azurecontainerapps.io). Use to build app FQDNs.')
output defaultDomain string = env.properties.defaultDomain

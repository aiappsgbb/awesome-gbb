// Canonical standing data resources for an isolated Jobs CI workload.
// Source of truth for ../../SKILL.md § Composable Bicep Module Library.
targetScope = 'resourceGroup'

param location string
param storageName string
param cosmosName string
param databaseName string
param appPrincipalId string
param workerPrincipalId string
param runnerPrincipalId string
param tags object = {}
@allowed(['Enabled', 'Disabled', 'SecuredByPerimeter'])
param publicNetworkAccess string = 'Enabled'
param perimeterIdentity bool = false
@description('Preserve the observed account value on brownfield deployment; false for a new single-region serverless account.')
param automaticFailover bool = false

assert separateWorkloadIdentities = appPrincipalId != workerPrincipalId
resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    publicNetworkAccess: publicNetworkAccess
  }
}
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2025-04-15' = {
  name: cosmosName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  identity: perimeterIdentity ? { type: 'SystemAssigned' } : null
  properties: {
    databaseAccountOfferType: 'Standard'
    disableLocalAuth: true
    minimalTlsVersion: 'Tls12'
    enableAutomaticFailover: automaticFailover
    publicNetworkAccess: publicNetworkAccess
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0, isZoneRedundant: false }]
  }
}
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmos
  name: databaseName
  properties: { resource: { id: databaseName } }
}
resource blobGrants 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for principal in [appPrincipalId, workerPrincipalId, runnerPrincipalId]: {
  name: guid(storage.id, principal, 'blob-data-contributor')
  scope: storage
  properties: {
    principalId: principal
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}]
resource cosmosGrants 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = [for principal in [appPrincipalId, workerPrincipalId, runnerPrincipalId]: {
  parent: cosmos
  name: guid(cosmos.id, databaseName, principal, 'jobs-data')
  properties: {
    principalId: principal
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${principal == runnerPrincipalId ? '00000000-0000-0000-0000-000000000001' : '00000000-0000-0000-0000-000000000002'}'
    scope: '${cosmos.id}/dbs/${databaseName}'
  }
  dependsOn: [database]
}]
output storageId string = storage.id
output storageUrl string = 'https://${storage.name}.blob.${environment().suffixes.storage}'
output cosmosId string = cosmos.id
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output databaseName string = database.name

targetScope = 'resourceGroup'

@description('Existing ACR resource name.')
param acrName string

@description('Existing Cosmos DB account name.')
param cosmosAccountName string

@description('Existing Cosmos DB database name.')
param cosmosDatabaseName string

@description('Existing Cosmos DB control container name.')
param cosmosContainerName string

@description('Existing storage account name.')
param storageAccountName string

@description('Existing storage container name.')
param storageContainerName string

@description('Existing Key Vault name (optional).')
param keyVaultName string

@description('Existing ACA Job name.')
param jobName string

@description('Principal ID of the app UAMI.')
param appPrincipalId string

@description('Principal ID of the job UAMI.')
param jobPrincipalId string

@description('Built-in ACR Pull role definition ID.')
param acrPullRoleDefinitionId string

@description('Built-in Cosmos SQL data contributor role definition ID.')
param cosmosDataContributorRoleDefinitionId string

@description('Built-in storage blob data contributor role definition ID.')
param blobDataContributorRoleDefinitionId string

@description('Built-in Key Vault secrets user role definition ID.')
param keyVaultUserRoleDefinitionId string

@description('Subscription-scoped custom role definition ID for ACA job operations.')
param customRoleDefinitionId string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosAccountName
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' existing = {
  parent: cosmos
  name: cosmosDatabaseName
}

resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' existing = {
  parent: cosmosDatabase
  name: cosmosContainerName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = {
  parent: storageAccount
  name: 'default'
}

resource storageContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' existing = {
  parent: blobService
  name: storageContainerName
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (!empty(keyVaultName)) {
  name: keyVaultName
}

resource job 'Microsoft.App/jobs@2026-01-01' existing = {
  name: jobName
}

resource appAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, appPrincipalId, acrPullRoleDefinitionId)
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource jobAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, jobPrincipalId, acrPullRoleDefinitionId)
  properties: {
    principalId: jobPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

resource appCosmosData 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmos
  name: guid(cosmos.id, appPrincipalId, cosmosDataContributorRoleDefinitionId)
  properties: {
    principalId: appPrincipalId
    roleDefinitionId: cosmosDataContributorRoleDefinitionId
    scope: cosmosContainer.id
  }
}

resource jobCosmosData 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmos
  name: guid(cosmos.id, jobPrincipalId, cosmosDataContributorRoleDefinitionId)
  properties: {
    principalId: jobPrincipalId
    roleDefinitionId: cosmosDataContributorRoleDefinitionId
    scope: cosmosContainer.id
  }
}

resource appBlobData 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageContainer
  name: guid(storageContainer.id, appPrincipalId, blobDataContributorRoleDefinitionId)
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobDataContributorRoleDefinitionId
  }
}

resource jobBlobData 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageContainer
  name: guid(storageContainer.id, jobPrincipalId, blobDataContributorRoleDefinitionId)
  properties: {
    principalId: jobPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: blobDataContributorRoleDefinitionId
  }
}

resource jobKeyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(keyVaultName)) {
  scope: keyVault
  name: guid(keyVault.id, jobPrincipalId, keyVaultUserRoleDefinitionId)
  properties: {
    principalId: jobPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultUserRoleDefinitionId
  }
}

resource appJobOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: job
  name: guid(job.id, appPrincipalId, customRoleDefinitionId)
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: customRoleDefinitionId
  }
}

targetScope = 'subscription'

@description('Resource group containing the existing ACR, ACA environment, storage account, and deployed runtime modules.')
param resourceGroupName string

@description('Deployment location for the runtime resources.')
param location string

@description('Existing Azure Container Registry name.')
param acrName string

@description('Existing Container Apps managed environment name.')
param environmentName string

@description('Existing storage account name used for job output and callback capture.')
param storageAccountName string

@description('Existing blob container name used for job output and callback capture.')
param storageContainerName string

@description('Cosmos DB account name for the control store.')
param cosmosAccountName string

@description('Cosmos DB database name for the control store.')
param cosmosDatabaseName string = 'jobs'

@description('Cosmos DB container name for the control store.')
param cosmosContainerName string = 'tasks'

@description('Container App name for the MCP server.')
param appName string

@description('ACA Job name for the worker.')
param jobName string

@description('App UAMI resource name.')
param appIdentityName string = '${appName}-uami'

@description('Job UAMI resource name.')
param jobIdentityName string = '${jobName}-uami'

@description('Entra app client ID used to validate inbound app tokens.')
param authClientId string

@description('Immutable OCI digest used by both the app and the job.')
param imageDigest string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48'

@description('Optional Key Vault name for the job callback secret path.')
param keyVaultName string = ''

var outputStorageUrl = 'https://${storageAccountName}.blob.core.windows.net/${storageContainerName}'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  scope: resourceGroup(resourceGroupName)
  name: acrName
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  scope: resourceGroup(resourceGroupName)
  name: environmentName
}

module identities 'identity-rbac.bicep' = {
  name: 'create-identities'
  scope: subscription()
  params: {
    resourceGroupName: resourceGroupName
    location: location
    appUamiName: appIdentityName
    jobUamiName: jobIdentityName
    createIdentities: true
    createAssignments: false
    roleDefinitionName: 'foundry-mcp-aca-jobs-job-operator'
  }
}

module cosmos 'cosmos.bicep' = {
  name: 'create-cosmos'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: cosmosAccountName
    location: location
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
  }
}

module app 'app.bicep' = {
  name: 'create-app'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: appName
    location: location
    environmentId: environment.id
    imageDigest: imageDigest
    uamiResourceId: identities.outputs.appUamiResourceId
    acrServer: acr.properties.loginServer
    authClientId: authClientId
    allowedCallerClientIds: [
      identities.outputs.jobUamiClientId
    ]
    environmentVariables: []
  }
}

module job '../../../azd-patterns/references/bicep/aca-job.bicep' = {
  name: 'create-job'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: jobName
    location: location
    environmentId: environment.id
    imageDigest: imageDigest
    containerName: 'job'
    command: [
      'python'
      '-m'
      'app.job_worker'
    ]
    args: []
    environmentVariables: []
    uamiResourceId: identities.outputs.jobUamiResourceId
    acrServer: acr.properties.loginServer
  }
}

module rbac 'identity-rbac.bicep' = {
  name: 'assign-rbac'
  scope: subscription()
  params: {
    resourceGroupName: resourceGroupName
    location: location
    appUamiName: appIdentityName
    jobUamiName: jobIdentityName
    createIdentities: false
    createAssignments: true
    acrName: acrName
    cosmosAccountName: cosmos.outputs.accountName
    cosmosDatabaseName: cosmos.outputs.databaseName
    cosmosContainerName: cosmos.outputs.containerName
    storageAccountName: storageAccountName
    storageContainerName: storageContainerName
    keyVaultName: keyVaultName
    jobName: job.outputs.name
    appPrincipalId: identities.outputs.appUamiPrincipalId
    jobPrincipalId: identities.outputs.jobUamiPrincipalId
    roleDefinitionName: 'foundry-mcp-aca-jobs-job-operator'
  }
}

output appName string = app.outputs.name
output jobName string = job.outputs.name
output fqdn string = app.outputs.fqdn
output appIdentityResourceId string = identities.outputs.appUamiResourceId
output jobIdentityResourceId string = identities.outputs.jobUamiResourceId
output appIdentityPrincipalId string = identities.outputs.appUamiPrincipalId
output jobIdentityPrincipalId string = identities.outputs.jobUamiPrincipalId
output appIdentityClientId string = identities.outputs.appUamiClientId
output jobIdentityClientId string = identities.outputs.jobUamiClientId
output cosmosEndpoint string = cosmos.outputs.endpoint
output storageUrl string = outputStorageUrl
output authAudience string = app.outputs.authAudience
output imageDigest string = imageDigest

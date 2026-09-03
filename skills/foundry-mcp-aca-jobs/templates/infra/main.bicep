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

@description('Existing blob container name used for job outputs. Must differ from the callback container name.')
param outputStorageContainerName string

@description('Existing blob container name used for callback capture. Must differ from the output container name.')
param callbackStorageContainerName string

@description('Allowed app-only caller client IDs for the MCP app.')
param allowedMcpCallerClientIds array

@description('Explicit allowlisted input hosts for the MCP policy and job worker.')
param inputHosts array

@description('Explicit allowlisted result hosts for the MCP policy and job worker.')
param resultHosts array

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

type CallbackAuthMode = 'managed_identity' | 'key_vault'

@description('Immutable OCI digest used by both the app and the job.')
param imageDigest string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48'

@description('Callback delivery mode. key_vault requires externalCallbackUrl, callbackSecretName, and keyVaultName.')
param callbackAuthMode CallbackAuthMode = 'managed_identity'

@description('External callback URL used when callbackAuthMode is key_vault. Required together with callbackSecretName and keyVaultName in that mode.')
param externalCallbackUrl string = ''

@description('Managed-identity callback audience used when callbackAuthMode is managed_identity.')
param callbackAudience string = 'api://${authClientId}'

@description('Key Vault secret name used when callbackAuthMode is key_vault. Required together with externalCallbackUrl and keyVaultName in that mode.')
param callbackSecretName string = ''

@description('Existing Key Vault name used when callbackAuthMode is key_vault. Required together with externalCallbackUrl and callbackSecretName in that mode.')
param keyVaultName string = ''

var callbackRouteUrl = callbackAuthMode == 'managed_identity'
  ? 'https://${appName}.${managedEnvironment.properties.defaultDomain}/callbacks/jobs'
  : externalCallbackUrl
var outputStorageUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}/${outputStorageContainerName}'
var callbackStorageUrl = 'https://${storageAccountName}.blob.${environment().suffixes.storage}/${callbackStorageContainerName}'
var callbackPolicy = callbackAuthMode == 'managed_identity'
  ? {
      url: callbackRouteUrl
      auth_mode: callbackAuthMode
      audience: callbackAudience
    }
  : {
      url: callbackRouteUrl
      auth_mode: callbackAuthMode
      secret_name: callbackSecretName
    }
var appPolicyJson = string({
  jobs: {
    'short-job': {
      resource_group: resourceGroupName
      job_name: jobName
      container_name: 'job'
      image_digest: imageDigest
      command: [
        'python'
        '-m'
        'app.job_worker'
      ]
    }
  }
  callbacks: {
    ops: callbackPolicy
  }
  input_hosts: inputHosts
  result_hosts: resultHosts
})
var jobCallbackEnvironmentVariables = callbackAuthMode == 'managed_identity' ? [
  {
    name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE'
    value: callbackAudience
  }
] : [
  {
    name: 'MCP_ACA_JOBS_CALLBACK_VAULT_URL'
    value: 'https://${keyVaultName}${environment().suffixes.keyvaultDns}'
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_SECRET_NAME'
    value: callbackSecretName
  }
]
var appEnvironmentVariables = [
  {
    name: 'AZURE_CLIENT_ID'
    value: identities.outputs.appUamiClientId
  }
  {
    name: 'AZURE_SUBSCRIPTION_ID'
    value: subscription().subscriptionId
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT'
    value: cosmos.outputs.endpoint
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_DATABASE'
    value: cosmos.outputs.databaseName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_CONTAINER'
    value: cosmos.outputs.containerName
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_CONTAINER_URL'
    value: callbackStorageUrl
  }
  {
    name: 'MCP_ACA_JOBS_POLICY_JSON'
    value: appPolicyJson
  }
]
var jobEnvironmentVariables = concat([
  {
    name: 'AZURE_CLIENT_ID'
    value: identities.outputs.jobUamiClientId
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT'
    value: cosmos.outputs.endpoint
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_DATABASE'
    value: cosmos.outputs.databaseName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_CONTAINER'
    value: cosmos.outputs.containerName
  }
  {
    name: 'MCP_ACA_JOBS_JOB_TYPE'
    value: 'short-job'
  }
  {
    name: 'MCP_ACA_JOBS_JOB_RESOURCE_GROUP'
    value: resourceGroupName
  }
  {
    name: 'MCP_ACA_JOBS_JOB_NAME'
    value: jobName
  }
  {
    name: 'MCP_ACA_JOBS_JOB_CONTAINER_NAME'
    value: 'job'
  }
  {
    name: 'MCP_ACA_JOBS_JOB_IMAGE_DIGEST'
    value: imageDigest
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_URL'
    value: callbackRouteUrl
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_AUTH_MODE'
    value: callbackAuthMode
  }
], jobCallbackEnvironmentVariables, [
  {
    name: 'MCP_ACA_JOBS_OUTPUT_CONTAINER_URL'
    value: outputStorageUrl
  }
  {
    name: 'MCP_ACA_JOBS_INPUT_HOSTS'
    value: join(inputHosts, ',')
  }
  {
    name: 'MCP_ACA_JOBS_RESULT_HOSTS'
    value: join(resultHosts, ',')
  }
])

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  scope: resourceGroup(resourceGroupName)
  name: acrName
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
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

module preRuntimeRbac 'identity-rbac/assignments.bicep' = {
  name: 'assign-pre-runtime-rbac'
  scope: resourceGroup(resourceGroupName)
  params: {
    acrName: acrName
    cosmosAccountName: cosmos.outputs.accountName
    cosmosDatabaseName: cosmos.outputs.databaseName
    cosmosContainerName: cosmos.outputs.containerName
    storageAccountName: storageAccountName
    outputStorageContainerName: outputStorageContainerName
    callbackStorageContainerName: callbackStorageContainerName
    keyVaultName: callbackAuthMode == 'key_vault' ? keyVaultName : ''
    appPrincipalId: identities.outputs.appUamiPrincipalId
    jobPrincipalId: identities.outputs.jobUamiPrincipalId
    acrPullRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    blobDataContributorRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    keyVaultUserRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

module app 'app.bicep' = {
  name: 'create-app'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: appName
    location: location
    environmentId: managedEnvironment.id
    imageDigest: imageDigest
    uamiResourceId: identities.outputs.appUamiResourceId
    acrServer: acr.properties.loginServer
    authClientId: authClientId
    allowedMcpCallerClientIds: union(allowedMcpCallerClientIds, [
      identities.outputs.jobUamiClientId
    ])
    environmentVariables: appEnvironmentVariables
  }
  dependsOn: [
    preRuntimeRbac
  ]
}

module job '../../../azd-patterns/references/bicep/aca-job.bicep' = {
  name: 'create-job'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: jobName
    location: location
    environmentId: managedEnvironment.id
    imageDigest: imageDigest
    containerName: 'job'
    command: [
      'python'
      '-m'
      'app.job_worker'
    ]
    args: []
    environmentVariables: jobEnvironmentVariables
    uamiResourceId: identities.outputs.jobUamiResourceId
    acrServer: acr.properties.loginServer
  }
  dependsOn: [
    app
    preRuntimeRbac
  ]
}

module jobOperator 'identity-rbac/job-operator.bicep' = {
  name: 'assign-job-operator'
  scope: resourceGroup(resourceGroupName)
  params: {
    jobName: job.outputs.name
    appPrincipalId: identities.outputs.appUamiPrincipalId
    customRoleDefinitionId: identities.outputs.customRoleDefinitionId
  }
}

output appResourceName string = app.outputs.name
output jobResourceName string = job.outputs.name
output appFqdn string = app.outputs.fqdn
output appIdentityResourceId string = identities.outputs.appUamiResourceId
output jobIdentityResourceId string = identities.outputs.jobUamiResourceId
output appIdentityPrincipalId string = identities.outputs.appUamiPrincipalId
output jobIdentityPrincipalId string = identities.outputs.jobUamiPrincipalId
output appIdentityClientId string = identities.outputs.appUamiClientId
output jobIdentityClientId string = identities.outputs.jobUamiClientId
output cosmosEndpoint string = cosmos.outputs.endpoint
output outputStorageContainerUrl string = outputStorageUrl
output callbackStorageContainerUrl string = callbackStorageUrl
output authAudience string = app.outputs.authAudience
output appImageDigest string = imageDigest

// Canonical template contract for foundry-mcp-aca-jobs.
// Source of truth for the prose example in ../../SKILL.md § Deploy with azd.

targetScope = 'subscription'

@description('Resource group receiving the MCP app, ACA Job, and their managed identities.')
param resourceGroupName string

@description('Optional tags applied to the deployment resource group.')
param resourceGroupTags object = {}

@description('Resource group containing existing brownfield ACR, ACA environment, storage, and optionally Cosmos resources. Defaults to the deployment resource group for greenfield use.')
param platformResourceGroupName string = resourceGroupName

@description('Deployment location for the runtime resources.')
param location string

@description('Existing Azure Container Registry name.')
param acrName string

@description('Existing Container Apps managed environment name.')
param environmentName string

@description('Existing storage account name used for job output and callback capture.')
param storageAccountName string

@description('Existing blob storage account URL used for job output and callback capture.')
param storageAccountUrl string

@description('Blob container name to create for job outputs. Azure blob container names are 3-63 lowercase letters, numbers, and hyphens. This value is capped at 53 chars so the derived -callbacks container stays within 63 chars.')
@maxLength(53)
param outputStorageContainerName string

@description('Allowed app-only caller client IDs for the MCP app.')
param allowedMcpCallerClientIds array = []

@description('Allowed caller principal object IDs for the MCP app.')
param allowedMcpCallerPrincipalIds array = []

@description('Explicit allowlisted input hosts for the MCP policy and job worker.')
param inputHosts array

@description('Explicit allowlisted result hosts for the MCP policy and job worker.')
param resultHosts array

@description('Cosmos DB account name for the control store.')
param cosmosAccountName string

@description('Existing Cosmos DB account endpoint for brownfield CI mode.')
param cosmosAccountEndpoint string = ''

@description('Use the existing Cosmos DB account rather than creating a new one.')
param cosmosUseExistingAccount bool = false

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

type CallbackManagedIdentityConfig = {
  authMode: 'managed_identity'
}

type CallbackKeyVaultConfig = {
  authMode: 'key_vault'
  externalCallbackUrl: string
  callbackSecretName: string
  keyVaultName: string
}

@discriminator('authMode')
type CallbackConfig = CallbackManagedIdentityConfig | CallbackKeyVaultConfig

@description('Immutable OCI digest used by both the app and the job.')
param imageDigest string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48'

@description('Callback delivery configuration. managed_identity uses the app Easy Auth audience only; key_vault requires an external callback URL, secret name, and Key Vault name.')
param callbackConfig CallbackConfig

var authAudience = 'api://${authClientId}'
assert exactlyOneMcpCallerAllowlistMode = (empty(allowedMcpCallerClientIds) && !empty(allowedMcpCallerPrincipalIds)) || (!empty(allowedMcpCallerClientIds) && empty(allowedMcpCallerPrincipalIds))
assert nonemptyMcpCallerClientIds = empty(filter(allowedMcpCallerClientIds, id => empty(trim(id))))
assert nonemptyMcpCallerPrincipalIds = empty(filter(allowedMcpCallerPrincipalIds, id => empty(trim(id))))
var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'
var storageAccountUrlHost = replace(replace(storageAccountUrl, 'https://', ''), 'http://', '')
var storageAccountNameFromUrl = split(storageAccountUrlHost, '.')[0]
var cosmosAccountNameFromEndpoint = split(replace(replace(cosmosAccountEndpoint, 'https://', ''), 'http://', ''), '.')[0]
var storageAccountContractMatches = storageAccountNameFromUrl == storageAccountName
var cosmosAccountContractMatches = !cosmosUseExistingAccount || cosmosAccountNameFromEndpoint == cosmosAccountName
assert storageAccountUrlMatchesName = storageAccountContractMatches
assert cosmosEndpointMatchesName = cosmosAccountContractMatches
var storageHost = storageAccountUrlHost
var effectiveResultHosts = union(resultHosts, [storageHost])
var callbackRouteUrl = callbackConfig.authMode == 'managed_identity'
  ? 'https://${appName}.${managedEnvironment.properties.defaultDomain}/callbacks/jobs'
  : callbackConfig.externalCallbackUrl
var outputStorageUrl = '${storageAccountUrl}/${outputStorageContainerName}'
var callbackStorageUrl = '${storageAccountUrl}/${callbackStorageContainerName}'
var callbackPolicy = callbackConfig.authMode == 'managed_identity'
  ? {
      url: callbackRouteUrl
      auth_mode: callbackConfig.authMode
      audience: authAudience
    }
  : {
      url: callbackRouteUrl
      auth_mode: callbackConfig.authMode
      secret_name: callbackConfig.callbackSecretName
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
  result_hosts: effectiveResultHosts
})
var jobCallbackEnvironmentVariables = callbackConfig.authMode == 'managed_identity' ? [
  {
    name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE'
    value: authAudience
  }
] : [
  {
    name: 'MCP_ACA_JOBS_CALLBACK_VAULT_URL'
    value: 'https://${callbackConfig.keyVaultName}${environment().suffixes.keyvaultDns}'
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_SECRET_NAME'
    value: callbackConfig.callbackSecretName
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
    name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'
    value: storageAccountUrl
  }
  {
    name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME'
    value: storageAccountName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT'
    value: effectiveCosmosEndpoint
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME'
    value: effectiveCosmosAccountName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_DATABASE'
    value: effectiveCosmosDatabaseName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_CONTAINER'
    value: effectiveCosmosContainerName
  }
  {
    name: 'MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID'
    value: identities.outputs.jobUamiPrincipalId
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
    name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_URL'
    value: storageAccountUrl
  }
  {
    name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME'
    value: storageAccountName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT'
    value: effectiveCosmosEndpoint
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME'
    value: effectiveCosmosAccountName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_DATABASE'
    value: effectiveCosmosDatabaseName
  }
  {
    name: 'MCP_ACA_JOBS_COSMOS_CONTAINER'
    value: effectiveCosmosContainerName
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
    value: callbackConfig.authMode
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
    value: join(effectiveResultHosts, ',')
  }
])

resource workloadResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: resourceGroupName
  location: location
  tags: resourceGroupTags
}

resource platformResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' existing = {
  name: platformResourceGroupName
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  scope: platformResourceGroup
  name: acrName
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  scope: platformResourceGroup
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
  dependsOn: [
    workloadResourceGroup
  ]
}

module cosmos 'cosmos.bicep' = if (!cosmosUseExistingAccount) {
  name: 'create-cosmos'
  scope: workloadResourceGroup
  params: {
    name: cosmosAccountName
    location: location
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
    useExistingAccount: cosmosUseExistingAccount
    existingAccountEndpoint: cosmosAccountEndpoint
  }
}

module existingCosmos 'cosmos.bicep' = if (cosmosUseExistingAccount) {
  name: 'use-existing-cosmos'
  scope: platformResourceGroup
  params: {
    name: cosmosAccountName
    location: location
    databaseName: cosmosDatabaseName
    containerName: cosmosContainerName
    useExistingAccount: cosmosUseExistingAccount
    existingAccountEndpoint: cosmosAccountEndpoint
  }
}

var effectiveCosmosEndpoint = cosmosUseExistingAccount ? existingCosmos!.outputs.endpoint : cosmos!.outputs.endpoint
var effectiveCosmosAccountName = cosmosUseExistingAccount ? existingCosmos!.outputs.accountName : cosmos!.outputs.accountName
var effectiveCosmosDatabaseName = cosmosUseExistingAccount ? existingCosmos!.outputs.databaseName : cosmos!.outputs.databaseName
var effectiveCosmosContainerName = cosmosUseExistingAccount ? existingCosmos!.outputs.containerName : cosmos!.outputs.containerName

module preRuntimeRbac 'identity-rbac/assignments.bicep' = {
  name: 'assign-pre-runtime-rbac'
  scope: platformResourceGroup
  params: {
    acrName: acrName
    cosmosAccountName: effectiveCosmosAccountName
    cosmosDatabaseName: effectiveCosmosDatabaseName
    cosmosContainerName: effectiveCosmosContainerName
    storageAccountName: storageAccountName
    outputStorageContainerName: outputStorageContainerName
    keyVaultName: callbackConfig.authMode == 'key_vault' ? callbackConfig.keyVaultName : ''
    appPrincipalId: identities.outputs.appUamiPrincipalId
    jobPrincipalId: identities.outputs.jobUamiPrincipalId
    acrPullRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    blobDataContributorRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    keyVaultUserRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    createPlatformAssignments: true
    createCosmosAssignments: cosmosUseExistingAccount
  }
}

module preRuntimeCosmosRbac 'identity-rbac/assignments.bicep' = if (!cosmosUseExistingAccount) {
  name: 'assign-cosmos-rbac'
  scope: workloadResourceGroup
  params: {
    acrName: acrName
    cosmosAccountName: effectiveCosmosAccountName
    cosmosDatabaseName: effectiveCosmosDatabaseName
    cosmosContainerName: effectiveCosmosContainerName
    storageAccountName: storageAccountName
    outputStorageContainerName: outputStorageContainerName
    keyVaultName: ''
    appPrincipalId: identities.outputs.appUamiPrincipalId
    jobPrincipalId: identities.outputs.jobUamiPrincipalId
    acrPullRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    blobDataContributorRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    keyVaultUserRoleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    createPlatformAssignments: false
    createCosmosAssignments: true
  }
}

module app 'app.bicep' = {
  name: 'create-app'
  scope: workloadResourceGroup
  params: {
    name: appName
    location: location
    environmentId: managedEnvironment.id
    imageDigest: imageDigest
    uamiResourceId: identities.outputs.appUamiResourceId
    acrServer: acr.properties.loginServer
    authClientId: authClientId
    allowedMcpCallerClientIds: !empty(allowedMcpCallerClientIds)
      ? union(allowedMcpCallerClientIds, [
          identities.outputs.jobUamiClientId
        ])
      : []
    allowedMcpCallerPrincipalIds: !empty(allowedMcpCallerPrincipalIds)
      ? union(allowedMcpCallerPrincipalIds, [
          identities.outputs.jobUamiPrincipalId
        ])
      : []
    environmentVariables: appEnvironmentVariables
  }
  dependsOn: [
    preRuntimeRbac
    preRuntimeCosmosRbac
  ]
}

module job '../../../azd-patterns/references/bicep/aca-job.bicep' = {
  name: 'create-job'
  scope: workloadResourceGroup
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
    preRuntimeCosmosRbac
  ]
}

module jobOperator 'identity-rbac/job-operator.bicep' = {
  name: 'assign-job-operator'
  scope: workloadResourceGroup
  params: {
    jobName: job.outputs.name
    appPrincipalId: identities.outputs.appUamiPrincipalId
    customRoleDefinitionId: identities.outputs.customRoleDefinitionId
  }
}

output appResourceName string = app.outputs.name
output jobResourceName string = job.outputs.name
output appFqdn string = app.outputs.fqdn
output MCP_APP_NAME string = app.outputs.name
output ACA_JOB_NAME string = job.outputs.name
output AZURE_RESOURCE_GROUP string = workloadResourceGroup.name
output ACR_NAME string = acr.name
output ACR_LOGIN_SERVER string = acr.properties.loginServer
output MCP_ACA_JOBS_STORAGE_ACCOUNT_URL string = storageAccountUrl
output MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME string = storageAccountName
output MCP_ACA_JOBS_COSMOS_ENDPOINT string = effectiveCosmosEndpoint
output MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME string = effectiveCosmosAccountName
output MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT string = cosmosUseExistingAccount ? 'true' : 'false'
output appIdentityResourceId string = identities.outputs.appUamiResourceId
output jobIdentityResourceId string = identities.outputs.jobUamiResourceId
output appIdentityPrincipalId string = identities.outputs.appUamiPrincipalId
output jobIdentityPrincipalId string = identities.outputs.jobUamiPrincipalId
output appIdentityClientId string = identities.outputs.appUamiClientId
output jobIdentityClientId string = identities.outputs.jobUamiClientId
output cosmosEndpoint string = effectiveCosmosEndpoint
output outputStorageContainerUrl string = outputStorageUrl
output callbackStorageContainerUrl string = callbackStorageUrl
output authAudience string = app.outputs.authAudience
output appImageDigest string = imageDigest
output storageAccountNameFromUrl string = storageAccountNameFromUrl
output storageAccountContractMatches bool = storageAccountContractMatches
output cosmosAccountNameFromEndpoint string = cosmosAccountNameFromEndpoint
output cosmosAccountContractMatches bool = cosmosAccountContractMatches

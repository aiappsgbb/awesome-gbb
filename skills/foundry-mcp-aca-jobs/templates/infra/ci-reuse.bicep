// Canonical explicit CI reuse entrypoint; no identity, role, database or RG creation.
// Source of truth for ../../SKILL.md § Deploy with azd.
targetScope = 'resourceGroup'

param location string
param runId string
param environmentId string
param acrServer string
param appIdentityId string
param workerIdentityId string
param appClientId string
param workerClientId string
param workerPrincipalId string
param callerPrincipalId string
param authClientId string
param cosmosAccountName string
param cosmosEndpoint string
param cosmosDatabaseName string
param storageAccountName string
param storageAccountUrl string
param imageDigest string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48'

var appName = 'ci-smoke-mcp-jobs-${runId}'
var jobName = 'ci-smoke-mcp-jobs-worker-${runId}'
var controlContainer = 'ci-smoke-mcp-jobs-task-${runId}'
var outputContainer = 'mcpjobs-${runId}'
var callbackContainer = '${outputContainer}-callbacks'
var storageHost = '${storageAccountName}.blob.${environment().suffixes.storage}'
var authAudience = 'api://${authClientId}'

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: last(split(environmentId, '/'))
}
var callbackUrl = 'https://${appName}.${managedEnvironment.properties.defaultDomain}/callbacks/jobs'
var outputUrl = '${storageAccountUrl}/${outputContainer}'
var callbackStorageUrl = '${storageAccountUrl}/${callbackContainer}'

module control 'cosmos.bicep' = {
  name: 'ci-control-${runId}'
  params: {
    name: cosmosAccountName
    useExistingAccount: true
    useExistingDatabase: true
    existingAccountEndpoint: cosmosEndpoint
    databaseName: cosmosDatabaseName
    containerName: controlContainer
  }
}
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = {
  parent: storage
  name: 'default'
}
resource outputs 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobs
  name: outputContainer
  properties: { publicAccess: 'None' }
}
resource callbacks 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobs
  name: callbackContainer
  properties: { publicAccess: 'None' }
}
var policy = {
  jobs: {
    'short-job': {
      resource_group: resourceGroup().name
      job_name: jobName
      container_name: 'job'
      image_digest: imageDigest
      command: ['python', '-m', 'app.job_worker']
    }
  }
  callbacks: {
    ops: {
      url: callbackUrl
      auth_mode: 'managed_identity'
      audience: authAudience
    }
  }
  input_hosts: [storageHost]
  result_hosts: [storageHost]
}
var commonEnv = [
  { name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
  { name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME', value: storageAccountName }
  { name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT', value: cosmosEndpoint }
  { name: 'MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME', value: cosmosAccountName }
  { name: 'MCP_ACA_JOBS_COSMOS_DATABASE', value: cosmosDatabaseName }
  { name: 'MCP_ACA_JOBS_COSMOS_CONTAINER', value: controlContainer }
]
module app 'app.bicep' = {
  name: 'ci-app-${runId}'
  params: {
    name: appName
    location: location
    environmentId: environmentId
    imageDigest: imageDigest
    uamiResourceId: appIdentityId
    acrServer: acrServer
    authClientId: authClientId
    allowedMcpCallerPrincipalIds: [callerPrincipalId, workerPrincipalId]
    tags: { 'ci-run-id': runId }
    environmentVariables: concat(commonEnv, [
      { name: 'AZURE_CLIENT_ID', value: appClientId }
      { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
      { name: 'MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID', value: workerPrincipalId }
      { name: 'MCP_ACA_JOBS_CALLBACK_CONTAINER_URL', value: callbackStorageUrl }
      { name: 'MCP_ACA_JOBS_POLICY_JSON', value: string(policy) }
    ])
  }
  dependsOn: [control, outputs, callbacks]
}
module job '../../../azd-patterns/references/bicep/aca-job.bicep' = {
  name: 'ci-job-${runId}'
  params: {
    name: jobName
    location: location
    environmentId: environmentId
    imageDigest: imageDigest
    containerName: 'job'
    command: ['python', '-m', 'app.job_worker']
    uamiResourceId: workerIdentityId
    acrServer: acrServer
    replicaRetryLimit: 0
    environmentVariables: concat(commonEnv, [
      { name: 'AZURE_CLIENT_ID', value: workerClientId }
      { name: 'MCP_ACA_JOBS_JOB_TYPE', value: 'short-job' }
      { name: 'MCP_ACA_JOBS_JOB_RESOURCE_GROUP', value: resourceGroup().name }
      { name: 'MCP_ACA_JOBS_JOB_NAME', value: jobName }
      { name: 'MCP_ACA_JOBS_JOB_CONTAINER_NAME', value: 'job' }
      { name: 'MCP_ACA_JOBS_JOB_IMAGE_DIGEST', value: imageDigest }
      { name: 'MCP_ACA_JOBS_CALLBACK_URL', value: callbackUrl }
      { name: 'MCP_ACA_JOBS_CALLBACK_AUTH_MODE', value: 'managed_identity' }
      { name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE', value: authAudience }
      { name: 'MCP_ACA_JOBS_OUTPUT_CONTAINER_URL', value: outputUrl }
      { name: 'MCP_ACA_JOBS_INPUT_HOSTS', value: storageHost }
      { name: 'MCP_ACA_JOBS_RESULT_HOSTS', value: storageHost }
    ])
  }
  dependsOn: [app]
}

output MCP_APP_NAME string = app.outputs.name
output ACA_JOB_NAME string = job.outputs.name
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output ACR_NAME string = first(split(acrServer, '.'))
output ACR_LOGIN_SERVER string = acrServer
output MCP_ACA_JOBS_STORAGE_ACCOUNT_URL string = storageAccountUrl
output MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME string = storageAccountName
output MCP_ACA_JOBS_COSMOS_ENDPOINT string = cosmosEndpoint
output MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME string = cosmosAccountName
output MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT string = 'true'
output appIdentityResourceId string = appIdentityId
output jobIdentityResourceId string = workerIdentityId
output appIdentityClientId string = appClientId
output jobIdentityClientId string = workerClientId
output jobIdentityPrincipalId string = workerPrincipalId
output outputStorageContainerUrl string = outputUrl
output callbackStorageContainerUrl string = callbackStorageUrl
output authAudience string = authAudience

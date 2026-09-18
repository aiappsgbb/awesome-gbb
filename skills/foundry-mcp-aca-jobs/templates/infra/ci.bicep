// Opt-in standing-infrastructure composition. No RG, account, identity or grant creation.
targetScope = 'resourceGroup'

param location string
param appName string
param jobName string
param environmentId string
param environmentDomain string
param acrServer string
param appIdentityId string
param appClientId string
param workerIdentityId string
param workerClientId string
param workerPrincipalId string
param callerPrincipalId string
param authClientId string
param storageAccountUrl string
param storageAccountName string
param cosmosAccountEndpoint string
param cosmosAccountName string
param cosmosDatabaseName string
param cosmosContainerName string
param outputStorageContainerName string
param imageDigest string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld@sha256:e9b3e7c34664c7cffd7144864b0e4eec369bfde80068f9095dc63b37058bec48'

assert separateIdentities = toLower(appIdentityId) != toLower(workerIdentityId) && appClientId != workerClientId
var storageHost = '${storageAccountName}.blob.core.windows.net'
var callbackUrl = 'https://${appName}.${environmentDomain}/callbacks/jobs'
var audience = 'api://${authClientId}'
var commonEnv = [
  { name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_URL', value: storageAccountUrl }
  { name: 'MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME', value: storageAccountName }
  { name: 'MCP_ACA_JOBS_COSMOS_ENDPOINT', value: cosmosAccountEndpoint }
  { name: 'MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME', value: cosmosAccountName }
  { name: 'MCP_ACA_JOBS_COSMOS_DATABASE', value: cosmosDatabaseName }
  { name: 'MCP_ACA_JOBS_COSMOS_CONTAINER', value: cosmosContainerName }
]
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
    ops: { url: callbackUrl, auth_mode: 'managed_identity', audience: audience }
  }
  input_hosts: [storageHost]
  result_hosts: [storageHost]
}

module data '../../../azd-patterns/references/bicep/jobs-run-data.bicep' = {
  name: '${appName}-data'
  params: {
    storageAccountName: storageAccountName
    cosmosAccountName: cosmosAccountName
    databaseName: cosmosDatabaseName
    controlContainerName: cosmosContainerName
    outputContainerName: outputStorageContainerName
  }
}
module app 'app.bicep' = {
  name: '${appName}-app'
  params: {
    name: appName
    location: location
    environmentId: environmentId
    imageDigest: imageDigest
    uamiResourceId: appIdentityId
    acrServer: acrServer
    authClientId: authClientId
    allowedMcpCallerPrincipalIds: [callerPrincipalId, workerPrincipalId]
    environmentVariables: concat(commonEnv, [
      { name: 'AZURE_CLIENT_ID', value: appClientId }
      { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
      { name: 'MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID', value: workerPrincipalId }
      { name: 'MCP_ACA_JOBS_CALLBACK_CONTAINER_URL', value: '${storageAccountUrl}/${outputStorageContainerName}-callbacks' }
      { name: 'MCP_ACA_JOBS_POLICY_JSON', value: string(policy) }
    ])
  }
  dependsOn: [data]
}
module job '../../../azd-patterns/references/bicep/aca-job.bicep' = {
  name: '${appName}-job'
  params: {
    name: jobName
    location: location
    environmentId: environmentId
    imageDigest: imageDigest
    containerName: 'job'
    command: ['python', '-m', 'app.job_worker']
    uamiResourceId: workerIdentityId
    acrServer: acrServer
    environmentVariables: concat(commonEnv, [
      { name: 'AZURE_CLIENT_ID', value: workerClientId }
      { name: 'MCP_ACA_JOBS_JOB_TYPE', value: 'short-job' }
      { name: 'MCP_ACA_JOBS_JOB_RESOURCE_GROUP', value: resourceGroup().name }
      { name: 'MCP_ACA_JOBS_JOB_NAME', value: jobName }
      { name: 'MCP_ACA_JOBS_JOB_CONTAINER_NAME', value: 'job' }
      { name: 'MCP_ACA_JOBS_JOB_IMAGE_DIGEST', value: imageDigest }
      { name: 'MCP_ACA_JOBS_CALLBACK_URL', value: callbackUrl }
      { name: 'MCP_ACA_JOBS_CALLBACK_AUTH_MODE', value: 'managed_identity' }
      { name: 'MCP_ACA_JOBS_CALLBACK_AUDIENCE', value: audience }
      { name: 'MCP_ACA_JOBS_OUTPUT_CONTAINER_URL', value: '${storageAccountUrl}/${outputStorageContainerName}' }
      { name: 'MCP_ACA_JOBS_INPUT_HOSTS', value: storageHost }
      { name: 'MCP_ACA_JOBS_RESULT_HOSTS', value: storageHost }
    ])
  }
  dependsOn: [app]
}
output MCP_APP_NAME string = app.outputs.name
output ACA_JOB_NAME string = job.outputs.name
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output ACR_NAME string = split(acrServer, '.')[0]
output ACR_LOGIN_SERVER string = acrServer
output MCP_ACA_JOBS_STORAGE_ACCOUNT_URL string = storageAccountUrl
output MCP_ACA_JOBS_STORAGE_ACCOUNT_NAME string = storageAccountName
output MCP_ACA_JOBS_COSMOS_ENDPOINT string = cosmosAccountEndpoint
output MCP_ACA_JOBS_COSMOS_ACCOUNT_NAME string = cosmosAccountName
output MCP_ACA_JOBS_COSMOS_USE_EXISTING_ACCOUNT string = 'true'

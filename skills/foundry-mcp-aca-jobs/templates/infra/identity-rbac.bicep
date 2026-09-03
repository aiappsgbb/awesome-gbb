targetScope = 'subscription'

@description('Deployment resource group that owns the runtime resources.')
param resourceGroupName string

@description('Deployment location for user-assigned managed identities.')
param location string

@description('Name of the MCP app UAMI.')
param appUamiName string

@description('Name of the ACA Job UAMI.')
param jobUamiName string

@description('When true, create the two user-assigned managed identities and custom role definition.')
param createIdentities bool = true

@description('When true, create the RBAC assignments against existing resources.')
param createAssignments bool = false

@description('Existing ACR resource name.')
param acrName string = ''

@description('Existing Cosmos DB account name.')
param cosmosAccountName string = ''

@description('Existing Cosmos DB database name.')
param cosmosDatabaseName string = ''

@description('Existing Cosmos DB control container name.')
param cosmosContainerName string = ''

@description('Existing storage account name.')
param storageAccountName string = ''

@description('Existing blob container name for job outputs. Azure blob container names are 3-63 lowercase letters, numbers, and hyphens. This value is capped at 53 chars so the derived -callbacks container stays within 63 chars.')
@maxLength(53)
param outputStorageContainerName string = ''

@description('Existing Key Vault name (optional).')
param keyVaultName string = ''

@description('Principal ID of the app UAMI when creating RBAC assignments.')
param appPrincipalId string = ''

@description('Principal ID of the job UAMI when creating RBAC assignments.')
param jobPrincipalId string = ''

@description('Job-scope role definition name.')
param roleDefinitionName string = 'foundry-mcp-aca-jobs-job-operator'

var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var blobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var keyVaultUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var customRoleDefinitionGuid = guid(subscription().id, roleDefinitionName)
var customRoleDefinitionResourceId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', customRoleDefinitionGuid)
var callbackStorageContainerName = '${outputStorageContainerName}-callbacks'

module appUami './identity-rbac/uami.bicep' = if (createIdentities) {
  name: 'appUami'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: appUamiName
    location: location
  }
}

module jobUami './identity-rbac/uami.bicep' = if (createIdentities) {
  name: 'jobUami'
  scope: resourceGroup(resourceGroupName)
  params: {
    name: jobUamiName
    location: location
  }
}

resource jobRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' = if (createIdentities) {
  scope: subscription()
  name: customRoleDefinitionGuid
  properties: {
    roleName: roleDefinitionName
    description: 'Least-privilege role for the MCP app to manage one allowlisted ACA Job resource.'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.App/jobs/read'
          'Microsoft.App/jobs/start/action'
          'Microsoft.App/jobs/execution/read'
          'Microsoft.App/jobs/executions/read'
          'Microsoft.App/jobs/stop/execution/action'
        ]
        notActions: []
      }
    ]
    assignableScopes: [
      subscription().id
    ]
  }
}

module assignments './identity-rbac/assignments.bicep' = if (createAssignments) {
  name: 'assignments'
  scope: resourceGroup(resourceGroupName)
  params: {
    acrName: acrName
    cosmosAccountName: cosmosAccountName
    cosmosDatabaseName: cosmosDatabaseName
    cosmosContainerName: cosmosContainerName
    storageAccountName: storageAccountName
    outputStorageContainerName: outputStorageContainerName
    keyVaultName: keyVaultName
    appPrincipalId: appPrincipalId
    jobPrincipalId: jobPrincipalId
    acrPullRoleDefinitionId: acrPullRoleDefinitionId
    blobDataContributorRoleDefinitionId: blobDataContributorRoleDefinitionId
    keyVaultUserRoleDefinitionId: keyVaultUserRoleDefinitionId
  }
}

output appUamiResourceId string = createIdentities ? appUami!.outputs.resourceId : ''
output appUamiPrincipalId string = createIdentities ? appUami!.outputs.principalId : ''
output appUamiClientId string = createIdentities ? appUami!.outputs.clientId : ''
output jobUamiResourceId string = createIdentities ? jobUami!.outputs.resourceId : ''
output jobUamiPrincipalId string = createIdentities ? jobUami!.outputs.principalId : ''
output jobUamiClientId string = createIdentities ? jobUami!.outputs.clientId : ''
output customRoleDefinitionId string = customRoleDefinitionResourceId

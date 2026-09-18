// Owner-only bootstrap; NEVER part of the unattended per-run CI entrypoint.
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param storageName string
param cosmosName string
param databaseName string = 'ci-jobs'
param appIdentityName string
param workerIdentityName string
param runnerPrincipalId string
param acrName string
param tags object = {}
@description('Owner-only two-phase NSP opt-in: associate while Disabled, then enforce after verified associations. public preserves the original default.')
@allowed(['public', 'associate', 'enforce'])
param networkStage string = 'public'
param perimeterName string = 'jobs-data-perimeter'
@description('On brownfield deployment, explicitly pass the existing account value; do not reset it during a network-mode change.')
param cosmosAutomaticFailover bool = false

module app '../../../azd-patterns/references/bicep/uami.bicep' = {
  name: 'jobs-standing-app-identity'
  params: { name: appIdentityName, location: location, tags: tags }
}
module worker '../../../azd-patterns/references/bicep/uami.bicep' = {
  name: 'jobs-standing-worker-identity'
  params: { name: workerIdentityName, location: location, tags: tags }
}
module data '../../../azd-patterns/references/bicep/jobs-standing-data.bicep' = {
  name: 'jobs-standing-data'
  params: {
    location: location
    storageName: storageName
    cosmosName: cosmosName
    databaseName: databaseName
    appPrincipalId: app.outputs.principalId
    workerPrincipalId: worker.outputs.principalId
    runnerPrincipalId: runnerPrincipalId
    tags: tags
    publicNetworkAccess: networkStage == 'public' ? 'Enabled' : (networkStage == 'associate' ? 'Disabled' : 'SecuredByPerimeter')
    perimeterIdentity: networkStage != 'public'
    automaticFailover: cosmosAutomaticFailover
  }
}
module perimeter '../../../azd-patterns/references/bicep/jobs-data-perimeter.bicep' = if (networkStage != 'public') {
  name: 'jobs-standing-perimeter'
  params: {
    name: perimeterName
    location: location
    storageId: data.outputs.storageId
    cosmosId: data.outputs.cosmosId
    tags: tags
  }
}
module pull '../../../azd-patterns/references/bicep/acr-pull.bicep' = {
  name: 'jobs-standing-acr-pull'
  params: {
    registryName: acrName
    principalIds: [app.outputs.principalId, worker.outputs.principalId]
    description: 'Standing isolated Jobs CI app and worker image pulls.'
  }
}
resource operatorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'standing-jobs-operator')
  properties: {
    roleName: 'Jobs CI operator ${uniqueString(resourceGroup().id)}'
    description: 'Start, read and stop Jobs in this CI workload group; no resource or RBAC writes.'
    type: 'CustomRole'
    assignableScopes: [resourceGroup().id]
    permissions: [{
      actions: [
        'Microsoft.App/jobs/read'
        'Microsoft.App/jobs/start/action'
        'Microsoft.App/jobs/execution/read'
        'Microsoft.App/jobs/executions/read'
        'Microsoft.App/jobs/stop/execution/action'
      ]
      notActions: []
      dataActions: []
      notDataActions: []
    }]
  }
}
resource operatorGrant 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, appIdentityName, operatorRole.id)
  properties: {
    principalId: app.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: operatorRole.id
  }
}
output appIdentityId string = app.outputs.id
output workerIdentityId string = worker.outputs.id
output storageId string = data.outputs.storageId
output storageUrl string = data.outputs.storageUrl
output cosmosId string = data.outputs.cosmosId
output cosmosEndpoint string = data.outputs.cosmosEndpoint
output databaseName string = data.outputs.databaseName
output perimeterId string = networkStage == 'public' ? '' : perimeter!.outputs.perimeterId
output profileId string = networkStage == 'public' ? '' : perimeter!.outputs.profileId
output perimeterRuleId string = networkStage == 'public' ? '' : perimeter!.outputs.ruleId
output associationIds array = networkStage == 'public' ? [] : perimeter!.outputs.associationIds

targetScope = 'resourceGroup'

@description('Existing ACA Job name.')
param jobName string

@description('Principal ID of the app UAMI.')
param appPrincipalId string

@description('Subscription-scoped custom role definition ID for ACA job operations.')
param customRoleDefinitionId string

resource job 'Microsoft.App/jobs@2026-01-01' existing = {
  name: jobName
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

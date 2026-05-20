// Grants the Foundry project's managed identity:
//   - Log Analytics Reader on the Log Analytics workspace
//     (lets the project read telemetry for evaluations)
//   - Azure AI User on the Foundry account
//     (recommended by the hosted-agent permissions doc; auto-assigned when the
//      project creator has roleAssignments/write on the account, but added here
//      explicitly for IaC determinism)

param accountName string
param logAnalyticsWorkspaceName string
param projectPrincipalId string

// Built-in role definition IDs
var logAnalyticsReaderRoleId = '73c42c96-874c-492b-b04d-ab87d138a893'
var azureAiUserRoleId        = '53ca6127-db72-4b80-b1b0-d745d6d5456d'

resource law 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource projectLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(law.id, projectPrincipalId, logAnalyticsReaderRoleId)
  scope: law
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', logAnalyticsReaderRoleId)
  }
}

resource projectAzureAiUserOnAccount 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(account.id, projectPrincipalId, azureAiUserRoleId)
  scope: account
  properties: {
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', azureAiUserRoleId)
  }
}

// Cross-resource role grants for the Teams bot's User-Assigned Managed
// Identity. Three grants are needed for an end-to-end working bot:
//
//   1. AcrPull on the Container Registry   → so the ACA can pull the bot image
//   2. Foundry User on the Foundry account → data-plane access for model
//                                            inference via the project endpoint
//   3. Foundry User on the Foundry project → storage, history, project-scoped
//                                            APIs (Responses API endpoint)
//
// `Foundry User` is the post-rename name (May 2026) of the role previously
// known as `Azure AI User`. The GUID `53ca6127-db72-4b80-b1b0-d745d6d5456d`
// is unchanged across the rename, so pin by GUID to survive future renames.
//
// Why this module exists: keeping cross-resource RBAC in a single file (instead
// of inline in main.bicep) makes it easier to extend (add Cosmos / Key Vault /
// Storage grants) without touching the main wiring, and avoids accidental
// drift between the bot's UAMI and other workloads.

@description('Principal ID of the bot UAMI (output `principalId` from uami.bicep)')
param botPrincipalId string

@description('Name of the existing Azure Container Registry')
param acrName string

@description('Name of the existing Foundry (Cognitive Services) account')
param foundryAccountName string

@description('Name of the existing Foundry project (child of the account)')
param foundryProjectName string

// --- Role definition IDs ----------------------------------------------------
// Pinned by GUID so display-name rotations (e.g. "Azure AI User" → "Foundry
// User" in May 2026) don't break the deploy.

var acrPullRoleId    = '7f951dda-4ed3-4680-a7ca-43fe172d538d' // AcrPull
var foundryUserRoleId = '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Foundry User (was Azure AI User)

// --- Existing resources (lookups) -------------------------------------------

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' existing = {
  parent: foundryAccount
  name: foundryProjectName
}

// --- Role assignments -------------------------------------------------------

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, botPrincipalId, acrPullRoleId)
  properties: {
    principalId: botPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

resource foundryUserOnAccount 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryAccount
  name: guid(foundryAccount.id, botPrincipalId, foundryUserRoleId)
  properties: {
    principalId: botPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

resource foundryUserOnProject 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryProject
  name: guid(foundryProject.id, botPrincipalId, foundryUserRoleId)
  properties: {
    principalId: botPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', foundryUserRoleId)
  }
}

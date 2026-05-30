// =============================================================================
// CANONICAL REFERENCE — vendored from smb-credit-memo pilot infra
//
// Source: ~/Repos/smb-credit-memo-pilot/infra/modules/rbac.bicep
// Live-deployed: 2026-05-29 (agentic-loop SKILL Validation history row 8)
// Subscription: <internal-pilot-sub> (swedencentral)
//
// Source of truth for the prose example in ../../SKILL.md § RBAC — assign
// once, applies to all resources + § Prefer Bicep dependsOn:[rbac] over
// the retry loop.
//
// All role assignments pinned by GUID per AGENTS.md § 2.4 (display names
// rotate — "Azure AI User" became "Foundry User" mid-2026 with no GUID
// change). Granted at the appropriate scope; ACA-app modules dependsOn:
// [rbac] to dodge the 30-60s propagation race (A3 from PR #180, MID-4
// + MID-5 from PR #181, agentic-loop SKILL § Implement crib rows 7 + 8).
// =============================================================================

param acrName string
param foundryAccountName string
param backendUamiPrincipalId string
param frontendUamiPrincipalId string
param projectSystemMiPrincipalId string
param deployingUserObjectId string

// Role GUIDs (pinned; display names may drift)
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var roleAcrRepoReader = 'b93aa761-3e63-49ed-ac28-beffa264f7ac' // Container Registry Repository Reader (new token-based pulls)
var roleCogSvcOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
var roleCogSvcUser = 'a97b65f3-24c7-4388-baec-2e87135dc908' // Cognitive Services User
var roleCogSvcContributor = '25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68' // Cognitive Services Contributor
var roleAzureAIUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d' // Azure AI User (aka Foundry User)

resource acr 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: acrName
}

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryAccountName
}

// ── Backend UAMI → ACR AcrPull (Crib row 7) ────────────────────────────────
resource backendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, backendUamiPrincipalId, roleAcrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
    principalId: backendUamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Backend UAMI → Foundry account Cognitive Services User ─────────────────
resource backendCogSvcUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, backendUamiPrincipalId, roleCogSvcUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcUser)
    principalId: backendUamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Frontend UAMI → ACR AcrPull (Crib row 7) ───────────────────────────────
resource frontendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, frontendUamiPrincipalId, roleAcrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
    principalId: frontendUamiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Foundry project system MI → ACR AcrPull (Crib row 3) ──────────────────
resource projectMiAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, projectSystemMiPrincipalId, roleAcrPull)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
    principalId: projectSystemMiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Foundry project system MI → ACR Container Registry Repository Reader (Crib row 3) ──
resource projectMiAcrRepoReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, projectSystemMiPrincipalId, roleAcrRepoReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrRepoReader)
    principalId: projectSystemMiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Foundry project system MI → Foundry account Cognitive Services OpenAI User (MID-4) ──
resource projectMiOpenAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, projectSystemMiPrincipalId, roleCogSvcOpenAIUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcOpenAIUser)
    principalId: projectSystemMiPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Deploying user → Foundry account Cognitive Services Contributor (azd deploy <agent>) ──
resource userCogSvcContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployingUserObjectId)) {
  scope: foundry
  name: guid(foundry.id, deployingUserObjectId, roleCogSvcContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCogSvcContributor)
    principalId: deployingUserObjectId
    principalType: 'User'
  }
}

// ── Deploying user → Foundry account Azure AI User (browse in portal) ──
resource userAzureAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployingUserObjectId)) {
  scope: foundry
  name: guid(foundry.id, deployingUserObjectId, roleAzureAIUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAIUser)
    principalId: deployingUserObjectId
    principalType: 'User'
  }
}

// (MID-4 reactive part — agent INSTANCE MI gets OpenAI User on the account in the
// postdeploy-agent.sh hook, since the agent doesn't exist before deploy.)

// =============================================================================
// CANONICAL REFERENCE — vendored from smb-credit-memo pilot infra
//
// Source workspace: ~/Repos/smb-credit-memo-pilot/infra/modules/foundry-account.bicep
// Live-deployed: 2026-05-29 (agentic-loop SKILL Validation history row 8)
// Subscription: <internal-pilot-sub> (swedencentral)
// Outcome: all 4 demo scenarios passed live; deploy attempt 3 (after MID-9
//          quota fix + MID-10 capabilityHost fix) Succeeded in 3m02s.
//
// Source of truth for the prose example in ../../SKILL.md § Composable
// Bicep Module Library. When this file changes, also update the prose
// (per AGENTS.md § 4 mass-edit playbook).
//
// Embedded MID anchors (per agentic-loop SKILL § Validation history rows 7+8):
//   MID-2  → output endpoints[`AI Foundry API`] (line at bottom)
//   MID-4  → project SystemAssigned identity (separately needs Cognitive
//            Services OpenAI User role; granted via postdeploy hook — see
//            foundry-hosted-agents/references/bash/postdeploy-agent.sh)
//   MID-8  → appin connection metadata.ConnectionString explicit
//   MID-10 → account-level capabilityHost BEFORE project-level (the
//            single-biggest provision-time bug from the smb run)
// =============================================================================

param accountName string
param projectName string
param location string
param tags object
param aiProjectDeployments array
param appInsightsConnectionString string
@secure()
param appInsightsInstrumentationKey string

// ── Foundry account ────────────────────────────────────────────────────────
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    allowProjectManagement: true
  }
}

// ── Foundry project (system MI is critical — see Crib row 3 + MID-4) ──────
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: account
  name: projectName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'SMB Credit Memo pilot — multi-business-SKILL agent'
    displayName: 'SMB Credit Memo'
  }
}

// ── capabilityHost (account-level — required FIRST, then project-level)
// (MID-10 — preemptive next-time) The Foundry account must have its own
// capabilityHost before any project-level capabilityHost can be created.
// Without it, project-level capabilityHost provisioning fails with
// "Foundry Account capabilityHost Not Found". The BCP037 Bicep warning
// about `capabilityHostKind` is a stale-type false positive — the API
// accepts it and sets capabilityHostKind: 'Agents' by default.
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  parent: account
  name: 'default'
  properties: {
    capabilityHostKind: 'Agents'
  }
}

// ── capabilityHost (project-level) — required to host `host: azure.ai.agent` services
resource capabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  parent: project
  name: 'default'
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [
    accountCapabilityHost
  ]
}

// ── Model deployments (loop over LITERAL array — Crib row 4) ──────────────
@batchSize(1)
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [for d in aiProjectDeployments: {
  parent: account
  name: d.name
  sku: {
    name: d.sku.name
    capacity: d.sku.capacity
  }
  properties: {
    model: {
      name: d.model.name
      format: d.model.format
      version: d.model.version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
}]

// ── AppIn connection on the project (Crib row 9 + MID-8) ─────────────────
// authType: 'ApiKey' (NOT 'AAD' — Foundry hosted-agent runtime AAD path for AppIn
// is not supported in May 2026 preview). PLUS metadata.ConnectionString (MID-8)
// — without it, agent runtime can't reach AppIn even with the key.
resource appinConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'appin-connection'
  properties: {
    category: 'AppInsights'
    target: appInsightsConnectionString
    authType: 'ApiKey'
    credentials: {
      key: appInsightsInstrumentationKey
    }
    metadata: {
      // (MID-8) — the agent runtime reads this metadata field to bootstrap OTel
      ConnectionString: appInsightsConnectionString
      ApiType: 'Azure'
    }
    isSharedToAll: true
  }
  dependsOn: [
    capabilityHost
  ]
}

// =============================================================================
// Outputs
// =============================================================================
output accountName string = account.name
output accountId string = account.id
output projectName string = project.name
output projectResourceId string = project.id
output projectSystemMiPrincipalId string = project.identity.principalId

// (MID-2) — explicitly the 'AI Foundry API' endpoint, NOT the legacy
// account.properties.endpoint (which returns *.cognitiveservices.azure.com).
// The 'AI Foundry API' value is what `azd ai agent show` expects.
output projectEndpoint string = account.properties.endpoints['AI Foundry API']

// First deployment is the chat model for the agent.
output modelDeploymentName string = aiProjectDeployments[0].name

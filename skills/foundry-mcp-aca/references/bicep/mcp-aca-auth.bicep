// =============================================================================
// CANONICAL REFERENCE — ACA built-in auth (Easy Auth) for an MCP server
//
// Source of truth for the prose example in `../../SKILL.md § Layer 1 —
// Identity perimeter`.
//
// Add-on to mcp-aca.bicep: fronts the container app with Entra-validated auth
// so unauthenticated callers get 401 (Return401) and never reach your tools.
// Validation-only posture — NO client secret, because we only VALIDATE inbound
// bearer tokens (we do not run the interactive login/redirect flow). Add a
// clientSecretSettingName + an ACA secret only if you also need interactive
// browser sign-in.
//
// Key Vault Secrets User matches the reference's get_secret API, which can
// read values even though the tool returns properties. Metadata-only policy
// requires a separately reviewed API/role; this is not a fallback grant.
// =============================================================================

@description('Name of the existing MCP container app (from mcp-aca.bicep)')
param containerAppName string

@description('Entra app (client) ID whose api://<clientId> audience callers request')
param authClientId string

@description('Explicit client IDs of the allowed app-only callers; never substitute the API audience client ID.')
@minLength(1)
param allowedCallerClientIds array

@description('Entra tenant ID that issues the tokens')
param tenantId string = subscription().tenantId

@description('Existing Key Vault the MI may read secret metadata from')
param keyVaultName string

@description('Principal (object) ID of the container app user-assigned MI')
param mcpIdentityPrincipalId string

resource app 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: containerAppName
}

// Easy Auth: validate Entra tokens at the platform edge; reject anonymous
// callers with 401 before the request reaches the container.
resource authConfig 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: app
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      // API-server posture: reject unauthenticated calls outright.
      unauthenticatedClientAction: 'Return401'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: authClientId
          openIdIssuer: 'https://login.microsoftonline.com/${tenantId}/v2.0'
          // No clientSecretSettingName: validation-only (bearer JWT check).
        }
        validation: {
          // v2 aud is the API client GUID; v1 can use its resource URI.
          // Neither spelling authorizes a caller: the explicit ACL below does.
          allowedAudiences: [
            'api://${authClientId}'
            authClientId
          ]
          // App-only tokens (server-to-server / MI bearer — this skill's PRIMARY
          // consumer model) are REJECTED with 403 unless the caller's client id is
          // listed here, EVEN WHEN the audience matches. Empty [] = deny all
          // app-only callers. Verify the loaded policy after an edit; do not
          // infer success from PATCH or automatically restart shared resources.
          defaultAuthorizationPolicy: {
            allowedApplications: allowedCallerClientIds
          }
        }
      }
    }
  }
}

// Layer 2 — least privilege: the MI may read secret METADATA, nothing broader.
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Key Vault Secrets User (built-in role).
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, mcpIdentityPrincipalId, keyVaultSecretsUserRoleId)
  scope: kv
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: mcpIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

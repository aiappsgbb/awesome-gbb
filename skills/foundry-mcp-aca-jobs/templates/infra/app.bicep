// Canonical template contract for foundry-mcp-aca-jobs.
// Source of truth for the prose example in ../../SKILL.md § Architecture and shared-image contract.

@description('Name of the MCP Container App.')
param name string

@description('Deployment location.')
param location string = resourceGroup().location

@description('Container Apps environment resource ID.')
param environmentId string

@description('Immutable image digest used by the MCP app.')
param imageDigest string

@description('User-assigned managed identity resource ID used for ACR pull.')
param uamiResourceId string

@description('ACR login server, for example myregistry.azurecr.io.')
param acrServer string

@description('Entra app client ID used to validate bearer tokens at the edge.')
param authClientId string

@description('Allowed app-only caller client IDs for default authorization.')
param allowedMcpCallerClientIds array = []

@description('azure.yaml service key used by azd to discover this Container App.')
param azdServiceName string = 'mcp'

@description('Additional environment variables to append to the MCP app.')
param environmentVariables array = []

@description('Optional tags.')
param tags object = {}

var authAudience = 'api://${authClientId}'

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': azdServiceName
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: imageDigest
          command: [
            'python'
            '-m'
            'app.mcp_server'
          ]
          env: concat([
            {
              name: 'MCP_ACA_JOBS_AUTH_MODE'
              value: 'aca-easy-auth'
            }
          ], environmentVariables)
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          // livenessProbe
          // startupProbe
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8080
              }
              initialDelaySeconds: 5
              periodSeconds: 10
              timeoutSeconds: 5
              failureThreshold: 3
            }
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8080
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              timeoutSeconds: 5
              failureThreshold: 12
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

resource authConfig 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: app
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'Return401'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: authClientId
          openIdIssuer: '${environment().authentication.loginEndpoint}${subscription().tenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            authAudience
            authClientId
          ]
          defaultAuthorizationPolicy: {
            allowedApplications: allowedMcpCallerClientIds
          }
        }
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn
output authAudience string = authAudience

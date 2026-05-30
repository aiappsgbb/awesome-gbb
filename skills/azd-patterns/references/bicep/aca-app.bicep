// =============================================================================
// CANONICAL REFERENCE — vendored from smb-credit-memo pilot infra
//
// Source: ~/Repos/smb-credit-memo-pilot/infra/modules/aca-app.bicep
// Live-deployed: 2026-05-29 (agentic-loop SKILL Validation history row 8)
// Subscription: <internal-pilot-sub> (swedencentral)
//
// Canonical 3-service-shape ACA container app module used across all
// agentic-loop pilots (weather-agent, learn-assistant, smb-credit-memo,
// hybrid-mcp-agent). The user-assigned identity + ACR registry binding
// pattern below is what closes A2 (every ACA UAMI needs AcrPull) — see
// rbac.bicep for the matching role assignment.
//
// Source of truth for the prose example in ../../SKILL.md § ACR + ACA
// Registry Binding.
// =============================================================================


param name string
param location string
param tags object
param acaEnvironmentId string
param uamiResourceId string
param acrLoginServer string
param containerImage string
param targetPort int
param cpu string
param memory string
param minReplicas int = 0
param maxReplicas int = 2
param envVars array = []

resource app 'Microsoft.App/containerApps@2025-02-02-preview' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    managedEnvironmentId: acaEnvironmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
        corsPolicy: {
          allowedOrigins: [
            '*'
          ]
          allowedMethods: [
            'GET'
            'POST'
            'OPTIONS'
          ]
          allowedHeaders: [
            '*'
          ]
          allowCredentials: false
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'app'
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: concat([
            {
              name: 'PORT'
              value: string(targetPort)
            }
          ], envVars)
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output id string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn

// =============================================================================
// CANONICAL REFERENCE — MCP server on Azure Container Apps
//
// Source of truth for the prose example in ../../SKILL.md § Bicep: ACA
// for MCP Server.
//
// What this Bicep module does:
//   - Creates an ACA container app with external ingress on :8080 (M2 — the
//     transport="streamable-http" + host="0.0.0.0" + port=8080 trio that
//     references/python/server.py expects)
//   - Wires user-assigned identity for ACR pull (A2 from the audit — every
//     ACA UAMI needs AcrPull on the ACR)
//   - Liveness + startup probes on /health — without these, cold-start tool
//     calls return 502 until the first health scrape
//   - minReplicas: 1 — avoid the cold-start hit on every demo
//
// NOT in this module: VNet injection. If your agent runs in a private
// topology, see foundry-vnet-deploy SKILL for the network shape. External
// ingress is required when the Foundry hosted agent (which runs in
// Foundry's infrastructure, not your VNET) calls the MCP.
// =============================================================================

@description('Name of the MCP ACA')
param name string

@description('Location')
param location string = resourceGroup().location

@description('Container app environment ID')
param containerAppEnvironmentId string

@description('Container image (in the ACR; pulled with the UAMI below)')
param image string

@description('Environment variables')
param env array = []

@description('User-assigned managed identity resource ID (for ACR pull + downstream RBAC)')
param userAssignedIdentityId string

@description('Container Registry name (no FQDN — just the resource name)')
param acrName string

resource mcpAca 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        // Use 'http' (HTTP/1.1 + Streamable HTTP) explicitly. 'auto' was
        // deprecated for new container apps in early 2026 — leaving it
        // here makes new revisions fail at deploy time with
        // `InvalidParameterValueInContainerTemplate`.
        transport: 'http'
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: userAssignedIdentityId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: image
          env: env
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          // Liveness + startup probes — Foundry's MCP client only flips
          // the server "healthy" if /health returns 200; missing probes
          // mean cold-start tool calls 502 until the first scrape.
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 2
              periodSeconds: 3
              failureThreshold: 30
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

output fqdn string = mcpAca.properties.configuration.ingress.fqdn

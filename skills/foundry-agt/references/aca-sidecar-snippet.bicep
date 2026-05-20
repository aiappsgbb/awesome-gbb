// ----------------------------------------------------------------------
// AGT sidecar pattern for Azure Container Apps (Path B in foundry-agt).
//
// Scenario: your agent code is NOT a MAF agent (different framework,
// or shell-out to a model server), so in-process middleware isn't an
// option. The AGT enforcer runs as a sidecar container in the same
// ACA pod, listening on localhost; your agent posts every action to
// it via HTTP and respects the deny verdict.
//
// Status: 📖 documented upstream — NOT yet GBB-tested. Verify before
// rolling out for a customer.
//
// References:
//   - upstream: docs/deployment/azure-container-apps.md
//   - composes with: azd-patterns (resource group, Log Analytics, ACA env)
//   - composes with: foundry-observability (App Insights wiring)
// ----------------------------------------------------------------------

@description('Container App name (your agent app)')
param agentAppName string

@description('Region')
param location string = resourceGroup().location

@description('ACA managed environment id')
param acaEnvironmentId string

@description('User-assigned managed identity for ACR pulls + key vault')
param uamiResourceId string

@description('Container image: your agent (provides /chat or whatever)')
param agentImage string

@description('Container image: AGT enforcer sidecar')
param agtSidecarImage string = 'mcr.microsoft.com/agentmesh/enforcer:3.6.0'

@description('Storage account share with the YAML policies')
param policiesStorageAccountName string
@description('Storage account file share name')
param policiesShareName string = 'agt-policies'

@description('App Insights connection string for OTel export')
@secure()
param appInsightsConnectionString string

resource agentApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: agentAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uamiResourceId}': {} }
  }
  properties: {
    managedEnvironmentId: acaEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
      }
      registries: [
        {
          server: split(agentImage, '/')[0]
          identity: uamiResourceId
        }
      ]
      secrets: [
        {
          name: 'appin-connection'
          value: appInsightsConnectionString
        }
      ]
    }
    template: {
      // ---- Volume from Azure Files holding the YAML policies ----
      volumes: [
        {
          name: 'agt-policies'
          storageType: 'AzureFile'
          storageName: policiesStorageAccountName
          mountOptions: 'dir_mode=0755,file_mode=0644'
        }
      ]
      containers: [
        // ---- Your agent container ----
        {
          name: 'agent'
          image: agentImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            // Tell the agent to call the sidecar at localhost
            { name: 'AGT_ENFORCER_URL', value: 'http://localhost:8081' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appin-connection' }
          ]
        }
        // ---- AGT enforcer sidecar ----
        {
          name: 'agt-enforcer'
          image: agtSidecarImage
          resources: {
            cpu: json('0.25')
            memory: '512Mi'
          }
          env: [
            { name: 'AGT_POLICY_DIR', value: '/policies' }
            { name: 'AGT_LISTEN_ADDR', value: '0.0.0.0:8081' }
            { name: 'AGT_AGENT_ID',    value: agentAppName }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appin-connection' }
          ]
          volumeMounts: [
            { volumeName: 'agt-policies', mountPath: '/policies', readOnly: true }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8081 }
              initialDelaySeconds: 5
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/ready', port: 8081 }
              initialDelaySeconds: 2
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

output agentAppFqdn string = agentApp.properties.configuration.ingress.fqdn

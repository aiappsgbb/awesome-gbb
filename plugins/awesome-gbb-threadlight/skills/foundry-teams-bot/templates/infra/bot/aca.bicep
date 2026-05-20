@description('Name of the container app')
param name string

@description('Location')
param location string = resourceGroup().location

@description('Container app environment resource ID')
param containerAppEnvironmentId string

@description('Container image (fully-qualified: <acrLoginServer>/<repo>:<tag>)')
param image string

@description('Target port')
param targetPort int = 80

@description('User-Assigned Managed Identity resource ID — used for ACR pull AND outbound calls')
param userAssignedIdentityId string

@description('ACR login server (e.g. myacr.azurecr.io). Required so the UAMI can pull from a private ACR.')
param acrLoginServer string

@description('Environment variables')
param env array = []

@description('Tags')
param tags object = {}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${userAssignedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      // Private-ACR pull via the bot's UAMI. The UAMI must have AcrPull on
      // the registry (granted in bot-rbac.bicep). Without this block the
      // first revision pulls anonymously and fails with "UNAUTHORIZED",
      // ACA then falls back to the previous (often placeholder) image.
      registries: [
        {
          server: acrLoginServer
          identity: userAssignedIdentityId
        }
      ]
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'bot'
          image: image
          env: env
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output id string = containerApp.id
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output name string = containerApp.name

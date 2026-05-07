@description('Name of the container app')
param name string

@description('Location')
param location string = resourceGroup().location

@description('Container app environment resource ID')
param containerAppEnvironmentId string

@description('Container image')
param image string

@description('Target port')
param targetPort int = 80

@description('User-Assigned Managed Identity resource ID')
param userAssignedIdentityId string

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
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'copilot'
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

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output name string = containerApp.name

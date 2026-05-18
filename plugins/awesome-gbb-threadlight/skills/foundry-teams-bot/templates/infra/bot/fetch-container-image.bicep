@description('Check if bot ACA already exists to preserve current image on re-provision')
param exists bool
param name string

resource existingApp 'Microsoft.App/containerApps@2024-03-01' existing = if (exists) {
  name: name
}

output image string = exists ? existingApp.properties.template.containers[0].image : ''

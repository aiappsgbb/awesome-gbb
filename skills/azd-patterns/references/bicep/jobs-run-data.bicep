// Canonical per-run Jobs containers in existing standing data accounts.
// Source of truth for ../../SKILL.md § Composable Bicep Module Library.
param storageAccountName string
param cosmosAccountName string
param databaseName string
param controlContainerName string
param outputContainerName string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}
resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' existing = {
  parent: storage
  name: 'default'
}
resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for name in [outputContainerName, '${outputContainerName}-callbacks']: {
  parent: blobs
  name: name
  properties: { publicAccess: 'None' }
}]
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosAccountName
}
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' existing = {
  parent: cosmos
  name: databaseName
}
resource control 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: controlContainerName
  properties: {
    resource: {
      id: controlContainerName
      partitionKey: { paths: ['/ownerScope'], kind: 'Hash', version: 2 }
      uniqueKeyPolicy: { uniqueKeys: [{ paths: ['/idempotencyKeyHash'] }] }
    }
    options: {}
  }
}
output controlId string = control.id
output blobContainerIds array = [for i in range(0, 2): containers[i].id]

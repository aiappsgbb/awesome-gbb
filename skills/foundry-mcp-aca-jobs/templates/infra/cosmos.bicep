// Canonical template contract for foundry-mcp-aca-jobs.
// Source of truth for the prose example in ../../SKILL.md § Control record and lifecycle.

@description('Cosmos DB account name.')
param name string

@description('Deployment location.')
param location string = resourceGroup().location

@description('Database name.')
param databaseName string

@description('Control container name.')
param containerName string = 'tasks'

@description('Optional tags.')
param tags object = {}

resource account 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: account
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource tasks 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          '/ownerScope'
        ]
        kind: 'Hash'
        version: 2
      }
      uniqueKeyPolicy: {
        uniqueKeys: [
          {
            paths: [
              '/idempotencyKeyHash'
            ]
          }
        ]
      }
    }
  }
}

output accountName string = account.name
output accountId string = account.id
output endpoint string = account.properties.documentEndpoint
output databaseId string = database.id
output containerId string = tasks.id
output databaseName string = database.name
output containerName string = tasks.name

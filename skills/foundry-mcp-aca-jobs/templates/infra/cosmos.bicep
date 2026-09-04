// Canonical template contract for foundry-mcp-aca-jobs.
// Source of truth for the prose example in ../../SKILL.md § Control record and lifecycle.

@description('Cosmos DB account name.')
param name string

@description('Use an existing Cosmos DB account instead of creating a new one.')
param useExistingAccount bool = false

@description('Existing Cosmos DB account endpoint for brownfield CI mode.')
param existingAccountEndpoint string = ''

@description('Deployment location.')
param location string = resourceGroup().location

@description('Database name.')
param databaseName string

@description('Control container name.')
param containerName string = 'tasks'

@description('Optional tags.')
param tags object = {}

resource account 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = if (!useExistingAccount) {
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

resource existingAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = if (useExistingAccount) {
  name: name
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = if (!useExistingAccount) {
  parent: account
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource brownfieldDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = if (useExistingAccount) {
  parent: existingAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource tasks 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = if (!useExistingAccount) {
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

resource brownfieldTasks 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = if (useExistingAccount) {
  parent: brownfieldDatabase
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

var effectiveEndpoint = useExistingAccount ? existingAccountEndpoint : account!.properties.documentEndpoint

output accountName string = name
output accountId string = resourceId('Microsoft.DocumentDB/databaseAccounts', name)
output endpoint string = effectiveEndpoint
output databaseId string = resourceId('Microsoft.DocumentDB/databaseAccounts/sqlDatabases', name, databaseName)
output containerId string = resourceId('Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers', name, databaseName, containerName)
output databaseName string = databaseName
output containerName string = containerName

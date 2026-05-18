@description('Name of the Azure Bot resource')
param name string

@description('Location for the Bot Service (use "global" for most scenarios)')
param location string = 'global'

@description('Bot display name in Teams')
param displayName string

@description('UAMI Client ID — used as msaAppId')
param msaAppId string

@description('UAMI Tenant ID')
param msaAppTenantId string

@description('UAMI Resource ID')
param msaAppMSIResourceId string

@description('Bot messages endpoint (e.g., https://<aca-fqdn>/api/messages)')
param messagesEndpoint string

@description('Tags for the resource')
param tags object = {}

resource bot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'F0'
  }
  kind: 'azurebot'
  properties: {
    displayName: displayName
    endpoint: messagesEndpoint
    msaAppId: msaAppId
    msaAppType: 'UserAssignedMSI'
    msaAppTenantId: msaAppTenantId
    msaAppMSIResourceId: msaAppMSIResourceId
    schemaTransformationVersion: '1.3'
  }
}

resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: bot
  name: 'MsTeamsChannel'
  location: location
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      isEnabled: true
    }
  }
}

output botId string = bot.properties.msaAppId
output botName string = bot.name

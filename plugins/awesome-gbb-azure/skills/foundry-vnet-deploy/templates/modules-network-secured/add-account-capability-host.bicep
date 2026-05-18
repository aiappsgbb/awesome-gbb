/*
  Creates the ACCOUNT-level capability host for the AI Services (Foundry) account
  in the network-injected (private network) Standard Agent setup.

  This is the equivalent of the manual `createCapHost.sh` script: it sets the
  `customerSubnet` property on the account capability host so that the agent
  runtime is delegated into the customer VNet/subnet.

  This account-level capability host MUST exist BEFORE the project-level
  capability host is created.
*/

@description('Name of the existing AI Services (Foundry) account')
param accountName string

@description('Name for the account-level capability host')
param accountCapHost string = 'caphostacct'

@description('Full ARM Resource ID of the agent subnet (delegated to Microsoft.App/environments)')
param agentSubnetId string

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

#disable-next-line BCP081
resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  name: accountCapHost
  parent: account
  properties: {
    capabilityHostKind: 'Agents'
    customerSubnet: agentSubnetId
  }
}

output accountCapHost string = accountCapabilityHost.name

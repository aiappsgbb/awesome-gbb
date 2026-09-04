// =============================================================================
// CANONICAL REFERENCE — ACA Job module
//
// Source of truth for the prose example in ../../SKILL.md § Bicep: ACA Job Pattern.
//
// Manual-trigger ACA Job module with UAMI + registry identity, immutable
// digest contract, explicit command/args/env wiring, and id/name outputs.
// Runtime/deployment precondition enforcement lives in Task13 converge_image.py;
// this module stays portable and copy-verbatim compiles without repo bicepconfig.
// =============================================================================

param name string
param location string
param environmentId string
@description('registry/repo@sha256:<64 lowercase hex>.')
param imageDigest string
param containerName string
param command array
param args array = []
param environmentVariables array = []
param uamiResourceId string
param acrServer string
param replicaTimeout int = 300
param replicaRetryLimit int = 1

resource job 'Microsoft.App/jobs@2026-01-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: replicaTimeout
      replicaRetryLimit: replicaRetryLimit
      registries: [
        {
          server: acrServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: containerName
          image: imageDigest
          command: command
          args: args
          env: environmentVariables
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
    }
  }
}

output id string = job.id
output name string = job.name

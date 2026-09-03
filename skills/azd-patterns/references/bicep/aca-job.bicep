// =============================================================================
// CANONICAL REFERENCE — ACA Job module
//
// Source of truth for the prose example in ../../SKILL.md § Bicep: ACA Job Pattern.
//
// Manual-trigger ACA Job module with UAMI + registry identity, immutable
// digest enforcement, explicit command/args/env wiring, and id/name outputs.
// =============================================================================

param name string
param location string
param environmentId string
param imageDigest string
param containerName string
param command array
param args array = []
param environmentVariables array = []
param uamiResourceId string
param acrServer string
param replicaTimeout int = 300
param replicaRetryLimit int = 1

assert digestFormat = contains(imageDigest, '@sha256:') && length(split(imageDigest, '@sha256:')[1]) == 64

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
            cpu: 1
            memory: '2Gi'
          }
        }
      ]
    }
  }
}

output id string = job.id
output name string = job.name

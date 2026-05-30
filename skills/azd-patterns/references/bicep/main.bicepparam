// =============================================================================
// CANONICAL REFERENCE — vendored from smb-credit-memo pilot infra
//
// Source: ~/Repos/smb-credit-memo-pilot/infra/main.bicepparam
// Live-deployed: 2026-05-29 (agentic-loop SKILL Validation history row 8)
// Subscription: <internal-pilot-sub> (swedencentral)
//
// Source of truth for the prose example in ../../SKILL.md § azd env set
// + JSON arrays/objects: use .bicepparam, not JSON parameters.
//
// ⚠️  This file references `./main.bicep` via the `using` directive.
//     When copied into a real pilot workspace, ensure `infra/main.bicep`
//     exists alongside it. The `az bicep build` step in awesome-gbb CI
//     skips this file because it can't resolve the using target in
//     isolation — that's expected for a parameter-file snippet.
//
// Two anti-patterns this file prevents:
//   1. (A1) Setting `aiProjectDeployments` via `azd env set` of a JSON
//      string — gets triple-escaped through shell → azd → Bicep → ARM,
//      fails with BCP186 `Unable to parse literal JSON value`.
//   2. (MID-9) Default `capacity: 100` on a shared subscription often
//      fails with `InsufficientQuota` (shared subs run at 900+/1000 K
//      TPM aggregate). Default to capacity: 30; preflight via
//      `az cognitiveservices usage list` before raising.
//
// The `readEnvironmentVariable` calls at the top are fine for SCALAR
// values (string + bool). Only ARRAYS / OBJECTS need the literal
// treatment here.
// =============================================================================

using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'dev')
param location = readEnvironmentVariable('AZURE_LOCATION', 'swedencentral')
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', '')

// LITERAL — see A1 + MID-9. The azd ai agent extension WILL rewrite an
// env-driven version with triple-escaped JSON on every `azd provision`
// and break BCP186 — hardcode here.
param aiProjectDeployments = [
  {
    name: 'gpt-5.4-mini'
    model: {
      name: 'gpt-5.4-mini'
      format: 'OpenAI'
      version: '2026-03-17'
    }
    sku: {
      name: 'GlobalStandard'
      capacity: 30  // MID-9 — default for shared-sub pilots; preflight before raising
    }
  }
]

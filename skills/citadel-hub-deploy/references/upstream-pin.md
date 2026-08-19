---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: Azure-Samples/ai-hub-gateway-solution-accelerator
  ref: citadel-v1
  pinned_sha: 63f0f812474e713916dc909494d655246783a1d9
  pinned_commit_message: |
    Merge pull request #152 from mohamedsaif/citadel-v1
  license: MIT
  notes: |
    The Citadel Governance Hub — Layer 1 of the AI Citadel Platform.
    The pinned SHA and Bicep entry points are build-validated. A lean Azure
    deployment and core APIM gateway smoke passed on 2026-08-19. Positive
    client-credentials JWT validation remains blocked by the validation
    tenant's Conditional Access policy. This remains issue_only.

docs_to_revalidate:
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/tree/citadel-v1
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/validation/README.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/bicep/infra/citadel-access-contracts/README.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/llm-routing-architecture.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/pii-masking-apim.md
  - https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/blob/citadel-v1/guides/network-approach.md

known_issues:
  - id: KI-001
    description: GPT-5.4 family models reject max_tokens — use max_completion_tokens
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/1
    status: open
    workaround_location: SKILL.md § 11 "Known issues" item 1
  - id: KI-002
    description: APIM subscription header is api-key (not Ocp-Apim-Subscription-Key)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/2
    status: open
    workaround_location: SKILL.md § 11 item 2
  - id: KI-003
    description: Bicep BCP318 module-nullable warnings (intentional pattern)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/3
    status: open
    workaround_location: SKILL.md § 11 item 3
  - id: KI-004
    description: Sub-level azd up can fail twice on first run (RBAC/APIM warm-up)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/4
    status: open
    workaround_location: SKILL.md § 11 item 4

validation:
  requires:
    - github_only
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # Manual build-only validator. issue_only + runnable:false is intentional:
    # the complete skill contract still requires a human live Azure deployment.
    set -euo pipefail
    PINNED_SHA="${PINNED_SHA:-63f0f812474e713916dc909494d655246783a1d9}"
    WORKDIR="$(mktemp -d)"
    trap 'rm -rf "$WORKDIR"' EXIT
    git clone --filter=blob:none --no-checkout \
      https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator \
      "$WORKDIR/source"
    git -C "$WORKDIR/source" fetch --depth 1 origin "$PINNED_SHA"
    (cd "$WORKDIR/source" && git checkout --detach "$PINNED_SHA")
    ACTUAL_SHA="$(git -C "$WORKDIR/source" rev-parse HEAD)"
    test "$ACTUAL_SHA" = "$PINNED_SHA"
    az bicep build \
      --file "$WORKDIR/source/bicep/infra/main.bicep" \
      --outfile "$WORKDIR/main.json"
    az bicep build-params \
      --file "$WORKDIR/source/bicep/infra/main.bicepparam" \
      --outfile "$WORKDIR/main.parameters.json"
    echo "PINNED_SHA_OK=$ACTUAL_SHA"
    echo "BICEP_BUILD_OK=$(wc -c < "$WORKDIR/main.json" | tr -d ' ')"
    echo "BICEPPARAM_BUILD_OK=$(wc -c < "$WORKDIR/main.parameters.json" | tr -d ' ')"
  expected_output:
    - "PINNED_SHA_OK=63f0f812474e713916dc909494d655246783a1d9"
    - "BICEP_BUILD_OK="
    - "BICEPPARAM_BUILD_OK="

last_validated: 2026-08-19
validated_by: copilot-bot
known_issues_count: 4
---

# Upstream Pin

| Field | Value |
|-------|-------|
| **Repo** | `Azure-Samples/ai-hub-gateway-solution-accelerator` |
| **Branch** | `citadel-v1` |
| **Pinned commit SHA** | `63f0f812474e713916dc909494d655246783a1d9` |
| **Pinned commit message** | `Merge pull request #152 from mohamedsaif/citadel-v1` |
| **License** | MIT (Microsoft) |
| **azd template name** | `ai-citadel-governance-hub` |
| **Bicep entry** | `bicep/infra/main.bicep` (~59 KB) |
| **Bicep param entry** | `bicep/infra/main.bicepparam` (~17 KB, ~80 envs) |
| **Single azd service** | `usageProcessingLogicApp` (Logic App / Function, JS) |

## Deterministic materialization

The branch is the freshness signal, not the deployment input. `azd init
--branch citadel-v1` accepts only a mutable branch name and can silently move
between runs. Materialize the exact SHA and run `azd` from that checkout:

```bash
PINNED_SHA="63f0f812474e713916dc909494d655246783a1d9"
git clone --filter=blob:none --no-checkout \
  https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator \
  citadel-hub
git -C citadel-hub fetch --depth 1 origin "$PINNED_SHA"
(cd citadel-hub && git checkout --detach "$PINNED_SHA")
test "$(git -C citadel-hub rev-parse HEAD)" = "$PINNED_SHA"
cd citadel-hub
```

## Validation boundary

- **Current pin:** exact checkout, both Bicep entry points, lean Azure
  deployment, APIM model discovery, and chat inference succeeded.
- **JWT boundary:** a JWT-required Access Contract rejected a missing bearer
  token with HTTP 401. Positive client-credentials token acquisition was
  blocked by the validation tenant's Conditional Access policy, so the
  positive dual-auth call remains unverified.
- **Private Key Vault:** the local host was correctly blocked. A temporary
  in-VNet workload wrote and read-matched the secret through the private
  endpoint, then its container, role, and subnet were removed. Public access
  remained disabled.
- **Historical live evidence:** the May 2026 deployment and API observations
  below were collected at commit
  `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4`, not the current pin.

## Build and live core validation as of 2026-08 against current pinned SHA

### Bicep build (offline)

```
az bicep build --file bicep/infra/main.bicep --outfile <tmp>/citadel-main.json
# exit code 0 (PASS)
# ARM JSON output: 4,867,085 bytes with Bicep CLI 0.43.8

az bicep build-params \
  --file bicep/infra/main.bicepparam \
  --outfile <tmp>/citadel-main.parameters.json
# exit code 0 (PASS)
# parameters JSON output: 10,971 bytes
# Both commands emit warnings only; no build errors.
# The coordinator's reference build produced 4,867,124 bytes for main.json;
# generated JSON byte size can vary with the Bicep compiler. Exit status and
# semantic compilation are the contract, not an exact main.json byte count.
```

### Lean live deployment (non-production, East US 2)

The exact detached pin was deployed with the pilot overlay and these
structured-array reductions:

- one Foundry account and one project;
- `gpt-5.4-mini` at 30K TPM;
- `text-embedding-3-large` at 30K TPM;
- Developer APIM;
- Redis, API Center, AI Search, Document Intelligence, dashboards, and
  Foundry network injection disabled.

`azd provision --preview` succeeded before provisioning. The first APIM
activation exposed a missing `Microsoft.ManagedIdentity` provider preflight;
after registering it and recreating the failed APIM service, `azd up`
succeeded. The successful run used the canonical `azure-tenant-isolation`
bootstrap plus an explicit subscription argument.

### Current-pin live gateway evidence

After deploying one personal LLM Access Contract:

```text
GET /models/models
HTTP 200
models: gpt-5.4-mini

POST /openai/deployments/gpt-5.4-mini/chat/completions
HTTP 200
response: citadel-ok
```

A product policy setting `jwtRequired=true` rejected the API key without a
bearer token with HTTP 401. Entra setup then exposed two tenant constraints:

- the pinned two-year credential reset violated the tenant credential
  lifetime policy; append-only rotation with a 30-day end date succeeded;
- the private Key Vault correctly rejected the local host with
  `ForbiddenByConnection`; a temporary in-VNet workload produced
  `KV_SECRET_MATCH`, then its temporary resources were removed without a
  firewall exception;
- Conditional Access rejected the client-credentials token request with
  `AADSTS53003`.

Therefore the current pin has live deployment and core gateway evidence, but
not a positive client-credentials dual-auth call. Do not present the missing
positive JWT evidence as passed.

### Historical live deployment audit (old pin, Sweden Central, May 2026)

- **APIM**: StandardV2, External VNet, public access enabled
  (Sweden Central, capacity 1)
- **AI Foundry**: 2 instances (sweden + east-us-2), each with
  `citadel-governance-project` and 6-7 model deployments
  (gpt-4.1, gpt-5.4, gpt-5.4-mini, gpt-5.2, DeepSeek-R1, Mistral-Large-3,
  text-embedding-3-large, Phi-4)
- **VNet**: greenfield 10.170.0.0/24 with 4 /26 subnets (apim, pe, functionapp, agents)
- **Private endpoints**: 13 (Cosmos, Event Hub, Foundry ×2, KV, Redis, APIM v2,
  Storage ×4, Foundry ×2)
- **Private DNS Zones**: 13 (one per privatelink.* type, all linked to vnet)
- **Cosmos / Foundry / KV / Redis**: public network access **Disabled**
- **Event Hub**: public network access **Enabled** (default)
- **Logic App**: Workflow Standard plan + Function App (usage ingestion)
- **App Insights**: 3 workspaces (apim, foundry, func) sharing 1 Log Analytics
- **Tags**: `SecurityControl: Ignore`, `azd-env-name: citadel-hub-01`

### Verified API surface (live, against pinned hub)

```
APIs imported into APIM:
- azure-openai-api          path: openai
- openai-realtime-ws-api    path: openai/realtime
- unified-ai-api            path: unified-ai
- universal-llm-api         path: models
- weather-api               path: weather       (sample only)

Subscription key header (all 4 LLM APIs):  api-key
                                           ^^^^^^^
                          NOT Ocp-Apim-Subscription-Key
```

### Latency baselines (live, Sweden Central, May 2026)

| Call | Cold | Warm |
|------|------|------|
| `GET /models/models` (universal-llm-api discovery) | 663 ms | 256 ms |
| `POST /openai/.../chat/completions` (gpt-5.4-mini) | 1682 ms | ~1 sec |
| PII probe (model refused echo of fake SSN/email) | 1124 ms | n/a |

## Historical known issues from the live-validated old pin

See `SKILL.md § 11` for the full list. Quick reference:

1. Newer GPT-5.4 family models reject `max_tokens` — use
   `max_completion_tokens`.
2. APIM subscription header is `api-key` (Azure OpenAI convention),
   not the APIM default `Ocp-Apim-Subscription-Key`.
3. Bicep build emits BCP318 module-nullable warnings (intentional
   conditional pattern; not a deployment blocker).
4. Sub-level `azd up` can fail twice on first run before succeeding
   (RBAC propagation, Cognitive Services warm-up, APIM provisioning
   timing). Re-run `azd up` — it's idempotent.
5. `azd env list` errors with `no project exists` outside the project
   dir — sync sessions lose cwd, re-`cd`.
6. Bicep CLI on Windows: large `--stdout` buffers stall PowerShell —
   use `--outfile` instead.

## Re-pin procedure

When upstream advances:

1. `git ls-remote https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-v1`
   → capture new SHA.
2. Shallow clone at new SHA into a scratch dir.
3. `az bicep build --file bicep/infra/main.bicep --outfile out.json` → must exit 0.
4. Diff the new `bicep/infra/main.bicepparam` against the prior SHA's:
   any added/renamed env vars need to be reflected in
   `references/profiles/*.env`.
5. Run the live audit checks above against a fresh `azd up` if any
   profile-relevant env vars changed.
6. Update SHA in this file + bump skill `metadata.version`
   (PATCH for SHA-only, MINOR for new profiles, MAJOR for breaking
   changes per AGENTS.md § 5).

## Cross-references in upstream worth bookmarking

- `validation/README.md` — recommended notebook execution order, init pattern
- `bicep/infra/citadel-access-contracts/README.md` — per-team contract Bicep
- `guides/agent-governance-toolkit-integration.md` — hub + AGT pairing
- `guides/llm-routing-architecture.md` — deep-dive on backend pool routing
- `guides/pii-masking-apim.md` — PII anonymize/deanonymize/block policy
- `guides/citadel-sizing-guide.md` — capacity & cost estimation
- `guides/put-estimation-guide.md` — PTU sizing for OpenAI workloads
- `guides/network-approach.md` — hub vs spoke networking decision

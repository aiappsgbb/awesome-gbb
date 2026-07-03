---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: Azure-Samples/ai-hub-gateway-solution-accelerator
  ref: citadel-v1
  pinned_sha: 08294f09a70833e282776a07fe7f97a6aead55b1
  pinned_commit_message: |
    Merge pull request #133 from mohamedsaif/citadel-v1
  license: MIT
  notes: |
    The Citadel Governance Hub — Layer 1 of the AI Citadel Platform.
    Validation requires `azd up` against a real Azure subscription,
    so this is issue_only.

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
    workaround_location: SKILL.md § 15 "Known issues" item 1
  - id: KI-002
    description: APIM subscription header is api-key (not Ocp-Apim-Subscription-Key)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/2
    status: open
    workaround_location: SKILL.md § 15 item 2
  - id: KI-003
    description: Bicep BCP318 module-nullable warnings (intentional pattern)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/3
    status: open
    workaround_location: SKILL.md § 15 item 3
  - id: KI-004
    description: Sub-level azd up can fail twice on first run (RBAC/APIM warm-up)
    upstream_url: https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator/issues/4
    status: open
    workaround_location: SKILL.md § 15 item 4

validation:
  requires:
    - github_only
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — requires Azure subscription + tenant isolation
    # Run from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill.
    set -euo pipefail

    # 1. Capture current upstream SHA
    git ls-remote https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-v1

    # 2. Shallow clone at the pinned SHA
    git clone --depth 1 --branch citadel-v1 \
      https://github.com/Azure-Samples/ai-hub-gateway-solution-accelerator citadel-upstream
    cd citadel-upstream
    git fetch origin "${PINNED_SHA}"
    git checkout "${PINNED_SHA}"

    # 3. Bicep build (offline; no Azure call needed for this step)
    az bicep build --file bicep/infra/main.bicep --outfile /tmp/citadel-main.json
    echo "Bicep build OK: $(wc -c < /tmp/citadel-main.json) bytes"

    # 4. (Optional) azd up against a test subscription — costs apply
    # azd env new citadel-hub-test
    # azd up
  expected_output:
    - "Bicep build OK"

last_validated: 2026-07-03
validated_by: ricchi
known_issues_count: 4
---

# Upstream Pin

| Field | Value |
|-------|-------|
| **Repo** | `Azure-Samples/ai-hub-gateway-solution-accelerator` |
| **Branch** | `citadel-v1` |
| **Pinned commit SHA** | `08294f09a70833e282776a07fe7f97a6aead55b1` |
| **Pinned commit message** | `Merge pull request #133 from mohamedsaif/citadel-v1` |
| **License** | MIT (Microsoft) |
| **azd template name** | `ai-citadel-governance-hub` |
| **Bicep entry** | `bicep/infra/main.bicep` (~55 KB) |
| **Bicep param entry** | `bicep/infra/main.bicepparam` (~17 KB, ~80 envs) |
| **Single azd service** | `usageProcessingLogicApp` (Logic App / Function, JS) |

## Re-pin validation — 2026-07-03 → `08294f09` (PR #133) [PARTIAL: `azd up` pending]

Re-pin from `f2702b49` (PR #117) → `08294f09` (PR #133) — **48 commits**.

- **Offline bicep build** (`az bicep build --file bicep/infra/main.bicep`,
  Bicep CLI 0.43.8) at `08294f09`: **exit 0**, ARM JSON ~4.6 MB, **0 errors**,
  100 warnings — BCP318 ×56 (nullable-module conditional pattern), BCP037 ×25
  (preview-RP type advisories), no-unused-params ×5, no-unnecessary-dependson
  ×5, no-hardcoded-env-urls ×4, +BCP187/BCP081/BCP036/prefer-unquoted-property-names/no-unused-vars
  ×1 each. Warnings-only; the multi-cloud routing revamp added the extra
  BCP037/BCP318 advisories — no deployment blockers.
- **Env-var surface diff** (`bicep/infra/main.bicepparam`, `f2702b49..08294f09`):
  exactly one change — `FOUNDRY_NETWORK_INJECTION_ENABLED` **removed** upstream
  (no additions). Dropped from all 3 `references/profiles/*.env`.
  `ENABLE_API_CENTER` still defaults `false`.
- **Partial live evidence**: API Center enabled out-of-band on the audit hub
  `rg-citadel-hub-01` — service `apic-codfa4k4hph2q` (Free, Sweden Central),
  8 APIs + 4 environments registered — via the upstream `apic.bicep` +
  `api-center-onboarding-all.bicep` modules. `what-if` was clean (13 create,
  72 ignore, 0 modify/delete); both deployments Succeeded.
- **Pending for full sign-off**: `azd up` re-audit at `08294f09`. The upstream
  Foundry default model list changed (DeepSeek-R1 removed; gpt-5.2 + image
  models added), so a full provision would reconcile model deployments. This
  is why the skill stays `automation_tier: issue_only` / `runnable: false` —
  a human must run the live validation before this pin is considered fully
  validated.

---

## Validated as of 2026-05 against pinned SHA

### Bicep build (offline)

```
az bicep build --file bicep/infra/main.bicep --outfile <tmp>/citadel-main.json
# Bicep CLI 0.43.8
# exit code 0 (PASS)
# ARM JSON output: 6 MB
# Warnings only (no errors):
#   - WARNING no-unused-params (1)
#   - WARNING prefer-unquoted-property-names (1)
#   - WARNING no-hardcoded-env-urls (4× core.windows.net)
#   - WARNING BCP318 nullable module access (~20×) — intentional for
#     conditional deployment modules (useExistingLogAnalytics,
#     useExistingVnet, enableManagedRedis, etc.)
```

### Live deployment audit (rg-citadel-hub-01, Sweden Central, May 2026)

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

## Known issues at this pin

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

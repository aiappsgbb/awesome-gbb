# Upstream Pin

| Field | Value |
|-------|-------|
| **Repo** | `Azure-Samples/ai-hub-gateway-solution-accelerator` |
| **Branch** | `citadel-v1` |
| **Pinned commit SHA** | `f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4` |
| **Pinned commit message** | `Merge pull request #117 from mohamedsaif/citadel-v1` |
| **License** | MIT (Microsoft) |
| **azd template name** | `ai-citadel-governance-hub` |
| **Bicep entry** | `bicep/infra/main.bicep` (~55 KB) |
| **Bicep param entry** | `bicep/infra/main.bicepparam` (~17 KB, ~80 envs) |
| **Single azd service** | `usageProcessingLogicApp` (Logic App / Function, JS) |

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

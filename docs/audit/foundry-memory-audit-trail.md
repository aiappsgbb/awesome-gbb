# `foundry-memory` — Deep audit trail (21 findings)

| Field | Value |
| --- | --- |
| Skill | `foundry-memory` |
| SKILL.md version before | 1.0.1 |
| SKILL.md version after | 1.0.2 |
| Audit date | 2026-05-31 |
| Auditor | Phase 4 audit worker (unsafecode/foundry-memory-audit) |
| Companion PR | _this PR_ |
| Predecessor PR | #185 (Phase 3 fixture turn-green + Pattern 23 RBAC bootstrap) |
| Bug-class scan reference | `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` Appendix A (L381-403) |
| Audit surface | `skills/foundry-memory/SKILL.md` + `references/upstream-pin.md` + `test-fixture/consumer_prompt.md` (read-only) |

`foundry-memory` is an **authored** wrapper (not a third-party SDK re-pin) over the
`azure-ai-projects>=2.0.0` SDK surface `project_client.beta.memory_stores` and
the `2025-11-15-preview` API version. The skill ships no Bicep, no
`references/<lang>/` code, and no agent.yaml — its risk surface is exclusively
SKILL.md prose, the `upstream-pin.md` freshness contract, and the
Phase-3-proven `test-fixture/consumer_prompt.md` (out of scope for this audit).
This audit walks all 21 bug classes from Appendix A; 3 HITs (C9 medium, C10
low-medium, C21 low) are fix-in-PR via PATCH bump 1.0.1 → 1.0.2; the remaining
18 classes resolve to `none observed` or `N/A` with one-line justification.

## Findings

### C1 — Hardcoded secrets, GUIDs, customer identifiers
**none observed.** SKILL.md uses placeholders `<entra-oid>` (L170, L205,
L248, L265) and `<contoso>` archetype prose only. No real subscription IDs,
tenant IDs, or ARM resource IDs anywhere
(`grep -nE 'subscriptions/[0-9a-f]{8}-' skills/foundry-memory/ → empty`).

### C2 — Bicep shape drift (azd-patterns canonical modules)
**N/A.** Skill ships zero Bicep
(`find skills/foundry-memory -name '*.bicep' → empty`). Memory store creation
is a runtime API call (`project_client.beta.memory_stores.create(...)`), not an
ARM resource. The standing `aif-awesome-gbb-ci` Foundry account is provisioned
by repo-level infra outside this skill.

### C3 — CLI install drift (Pattern 15)
**N/A.** The only CLI referenced is `az` (REST auth helper
`az account get-access-token` at SKILL.md L136); no `azd`, `func`, `kubectl`,
or `helm`
(`grep -nE '\b(azd|func|kubectl|helm)\b' skills/foundry-memory/SKILL.md → empty`).
Per Pattern 15 rule 3, `az` is on the `ubuntu-latest` pre-installed-CLI
allowlist (alongside `gh`), so no workflow-side install step is required and
the install-drift class is satisfied by construction.

### C4 — OIDC TTL / teardown bounds (Pattern 25)
**N/A.** Test fixture is out of scope (proven green Phase 3, untouched per
brief). SKILL.md documents only `create` / `begin_update_memories` /
`search_memories` SDK shapes (L123/L185/L246) — no `.delete()` call or
fixture-teardown semantics, so no OIDC-token-lifetime exposure surface to
audit here.

### C5 — Preview-CLI flag branching (Pattern 16)
**none observed.** SKILL.md exclusively documents the SDK path
(`project_client.beta.memory_stores.*` throughout §3-§7). No `azd ai`,
`az cognitiveservices`, or other preview-CLI surfaces appear
(`grep -nE 'azd ai|az cognitiveservices' skills/foundry-memory/SKILL.md → empty`).
Pattern 16 (one-shot SDK path, never CLI branching) is respected by
construction.

### C6 — `azd` ↔ ACA Jobs deploy-gap (Pattern 18)
**N/A.** Skill provisions no Azure resources via `azd` or Bicep. Memory
stores are runtime data-plane objects (`AIProjectClient.beta.memory_stores`),
not control-plane ACA resources. Pattern 18's job-vs-app fanout doesn't apply.

### C7 — Foundry SDK shape drift (`AIProjectClient`, etc.)
**none observed.** `project_client.beta.memory_stores` surface matches
the SDK floor `azure-ai-projects>=2.0.0` (SKILL.md L44) and the REST API
version `2025-11-15-preview` (SKILL.md L46). The `.beta` Python entry-point
callout at L45 mirrors the SDK contract. (upstream-pin.md tracks the
github_repo only — `packages: []` at L23 — so SDK floor is asserted in
SKILL.md, not in the pin.)

### C8 — Deprecated SDK API references
**none observed.** `azure-ai-projects>=2.0.0` is the floor (SKILL.md L44,
restated L62); no `azure-ai-ml`, `azureml-core`, or `azure-cognitiveservices-*`
legacy patterns
(`grep -nE 'azure-ai-ml|azureml-core|azure-cognitiveservices' skills/foundry-memory/SKILL.md → empty`).
The SDK floor was set deliberately to gate the preview memory surface.

### C9 — RBAC propagation race (`AcrPull`, Cog OpenAI User) — **HIT (medium)**
SKILL.md §7 (hosted agents, L321-371) and §9 (troubleshooting, L407-416)
were **silent** on the Pattern 23 server-side-worker RBAC requirement.
`foundry-memory`'s server-side memory-consolidation worker runs as the
**project SAMI** (NOT the caller's UAMI), and the project SAMI by default
holds only ACR roles — not `Cognitive Services OpenAI User` or
`Cognitive Services User`. Phase 3 run `26714879734` 401'd on exactly this
gap; PR #185 fixed it for CI by granting both roles to project SAMI
`8c1b62da-…` at account scope (AGENTS.md §9.7 Pattern 23). Consumers
following SKILL.md verbatim would hit the same 401 with no documented
remediation.

**Before** (end of §7, pre-edit):
```
Operationally:

- the agent injects **static profile memory** at conversation start
- it retrieves **contextual memories** per turn
- it schedules memory writes after inactivity using `update_delay`

This is the cleanest replacement for external memory middleware when the agent
already runs on Foundry.
```

**After** (insert a new `**RBAC requirement**` paragraph between the last
operational bullet and the closing `This is the cleanest replacement…`
sentence):
```
**RBAC requirement** (Pattern 23 — server-side worker identity): Memory
consolidation runs as the **project's system-assigned managed identity**
(NOT the caller's identity). That identity needs `Cognitive Services
OpenAI User` AND `Cognitive Services User` at the Foundry account scope to
call the chat deployment. The project SAMI is created with ACR roles only —
the two Cog roles must be granted explicitly. Symptom of omission: 401 from
the memory worker on its first consolidation pass, with the deploy/invoke
path superficially succeeding. See `AGENTS.md` § 9.7 Pattern 23 for the
canonical grant script.
```

**Plus** §9 troubleshooting table (3-column: Symptom | Likely cause | Fix) —
add a row between `update_delay` (L414) and `Direct API call` (L416); applied
row sits at L415:

```
| 401 from memory worker (server-side, not your client) | Project SAMI lacks `Cognitive Services OpenAI User` AND `Cognitive Services User` at account scope | Grant **both** roles per Pattern 23 (AGENTS.md § 9.7), then wait ≥ 5 min for AAD propagation |
```

**Disposition.** Fix-in-PR. Scope: `skills/foundry-memory/SKILL.md` only.
PATCH bump 1.0.1 → 1.0.2. Counted toward `[skill-rewrite]` commit tag.

### C10 — Region / SKU drift (Sweden Central, GlobalStandard embeddings) — **HIT (low-medium)**
SKILL.md §2 "Embedding model" (L65-69) and the regional availability list
(heading L77, list paragraph L79-82) were silent on Pattern 21 (Sweden
Central requires `GlobalStandard` SKU for embedding deployments). The CI
region (`swedencentral`) is explicitly listed at L82 as supported — but a
consumer who provisions a
`text-embedding-3-small` deployment with the default `Standard` SKU there
will get `InvalidResourceProperties: Sku is not supported in this region`.
This is the literal class of bug Pattern 21 was added to catch.

**Before** (SKILL.md L65-69):
```
### Embedding model requirement

Deploy **`text-embedding-3-small`** or **`text-embedding-3-large`** in the same
project (or via a connected resource). Memory retrieval uses that embedding
model to index and recall relevant memories.
```

**After** (append a Pattern 21 blockquote immediately after the existing
paragraph, before the `### Supported regions` heading at L77):
```
### Embedding model requirement

Deploy **`text-embedding-3-small`** or **`text-embedding-3-large`** in the same
project (or via a connected resource). Memory retrieval uses that embedding
model to index and recall relevant memories.

> **Sweden Central:** embedding deployments MUST use SKU `GlobalStandard`,
> not the default `Standard` — ARM rejects `Standard` with
> `InvalidResourceProperties: Sku is not supported in this region`. Other
> regions may impose similar constraints; verify the SKU-by-region
> availability table in the Foundry / Cognitive Services capacity docs
> before deploying elsewhere. (AGENTS.md § 9.7 Pattern 21.)
```

**Disposition.** Fix-in-PR. Scope: `skills/foundry-memory/SKILL.md` only.
Counted toward 1.0.1 → 1.0.2 PATCH bump.

### C11 — Cross-skill reference drift
**none observed.** §10 cross-refs (`foundry-iq`, `foundry-hosted-agents`,
`zava-workspace-deploy`) all resolve to skills present in the catalog
(`ls skills/{foundry-iq,foundry-hosted-agents}/SKILL.md` exists;
`zava-workspace-deploy` is the canonical zava-constellation cross-repo
reference and currently lives there).

### C12 — Link rot
**none observed.** Inline links to learn.microsoft.com (memory store docs)
and the SDK preview index are detected by the weekly skill-freshness cron
(AGENTS.md § 9.3 detector 4). No manual link probe needed in this PR.

### C13 — Telemetry wiring (App Insights, OTel, Foundry traces)
**N/A.** SKILL.md is silent on telemetry wiring
(`grep -nEi 'telemetry|foundry-observability|application insights|tracing' skills/foundry-memory/SKILL.md → empty`).
Per catalog convention, observability is the `foundry-observability` skill's
contract — memory operations inherit App Insights traces from the parent
agent's `configure_azure_monitor(...)` call rather than from anything this
skill wires itself.

### C14 — JSON / YAML escaping (Bicep params, agent.yaml)
**N/A.** No Bicep parameters, no agent.yaml — see C2. Only YAML in the skill
is the `upstream-pin.md` front-matter, which is validated by
`scripts/validate-skills.py` on every PR.

### C15 — Reference ↔ SKILL.md drift (env vars, function signatures, defaults)
**none observed.** Skill ships no `references/python|js|csharp/` code body
(authored skill, not wrapper of a code reference). The
`x-memory-user-id` HTTP header (L303, L348, L413) and `{{$userId}}` template
variable (L302, L316, L331) are consistent across §6 (scope isolation) and
§7 (hosted agents). SDK signature `project_client.beta.memory_stores.create(...)`
(L123) matches the `2025-11-15-preview` API version pinned at SKILL.md L46.

### C16 — Missing `dependsOn` on RBAC (Bicep race)
**N/A.** No Bicep — see C2 / C14. Pattern 23's RBAC race is a runtime
AAD-propagation issue (5-15 min after `az role assignment create`), which is
documented in the C9 fix above; this is distinct from the Bicep `dependsOn`
race that C16 targets.

### C17 — Tool wrapper type mismatches (MCPTool, OpenAPI tool shapes)
**none observed.** The single Pydantic tool model is `MemorySearchPreviewTool`
(import L327, instantiation L329), which is the canonical SDK type for
surfacing memory search to a hosted agent. No MCPTool or OpenAPI tool wiring
in this skill.

### C18 — Bot / webhook signature validation
**N/A.** Skill exposes no HTTP endpoints, no webhook handlers, no bot
listeners. Memory consolidation is a server-side Foundry-internal worker; the
skill consumer never writes a webhook for it.

### C19 — Logging exposure (secrets in logs, PII in transcripts)
**none observed.** No `print(token)` / `logger.info(api_key)` patterns
(`grep -nE 'print\(.*token|api_key|secret' skills/foundry-memory/SKILL.md → empty`).
The `extra_headers={"x-memory-user-id": "<entra-oid>"}` pattern (L348) is the
intentional scope-isolation surface — the value is a per-user opaque ID, not
a credential.

### C20 — Async / sync mismatches (in-process vs over-the-wire)
**none observed.** Python surface uses sync `AIProjectClient` throughout
(no `azure.ai.projects.aio` imports). TypeScript/C# snippets use the
language-idiomatic surface (`await project.beta.memoryStores.*` and
`MemoryStores.*` task-based APIs respectively). No mixed sync/async within
the same client path. One-shot fixture invokes use sync Python per
Pattern 16 rule 3.

### C21 — Outdated package version pins (prose vs frontmatter contract) — **HIT (low)**
`skills/foundry-memory/references/upstream-pin.md` has 3 internal
inconsistencies where the body table drifts from the canonical front-matter
(the front-matter is the machine-readable contract; body is human audit
trail). The front-matter is what `scripts/validate-skills.py` and the
weekly freshness cron consume; a reader trusting the body for the SHA, last
validation date, or validator identity would be misled. This is the same
class of bug the toolbox audit caught at C21.

**Before** (upstream-pin.md):

| Location | Body text |
| --- | --- |
| L80 | `Pinned SHA \| `325091fc44bafebc11330a442af58039248c9f29`` |
| L84 | `Last re-validated \| 2026-05-25` |
| L146 | `git ls-remote microsoft/skills main \| ✅ \| `325091fc44bafebc11330a442af58039248c9f29` at authoring time` |
| L150 | `Captured at last_validated: 2026-05-25 by copilot-cli.` |

**After** (canonicalize to front-matter L10 SHA / L60 date / L61 validator):

| Location | Body text |
| --- | --- |
| L80 | `Pinned SHA \| `858117a89d7e8f8c907141e1165b8816f3c18611`` |
| L84 | `Last re-validated \| 2026-05-29` |
| L146 | `git ls-remote microsoft/skills main \| ✅ \| `858117a89d7e8f8c907141e1165b8816f3c18611` at last validation` |
| L150 | `Captured at last_validated: 2026-05-29 by copilot-bot.` |

**Disposition.** Fix-in-PR. Scope: `skills/foundry-memory/references/upstream-pin.md`
body only — front-matter unchanged (it was already canonical). Counted
toward 1.0.1 → 1.0.2 PATCH bump.

## Fixture

| Field | Value |
| --- | --- |
| Path | `skills/foundry-memory/test-fixture/consumer_prompt.md` |
| Pattern compliance | 12 (marker file at `/tmp/foundry-memory-smoke-result`), 14 (40-min job ceiling shared), 15.3 (workflow-side install), 17 (show-don't-assert preamble), 22 (max-parallel 2), 23 (RBAC pre-granted by predecessor PR #185), 25 (soft-PASS teardown) |
| Wall-clock budget | ~13 min observed steady-state (well inside the 40-min ceiling) |
| Azure cost per run | ~$0.04 (1 memory store create + ~2 embedding calls + 1 chat call + delete) |
| Success signal | `printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-memory-smoke-result` (Pattern 12 `cmp -s` byte-exact) |
| Teardown | Best-effort `memory_stores.delete(...)`; soft-PASS on failure per Pattern 25 |

The fixture is **out of scope for this audit** (proven green Phase 3,
untouched per brief). No fixture-side changes are needed; the C9 and C10
HITs above are documentation-only fixes targeted at consumer-readers of
SKILL.md.

## CI matrix runs

| Date | SHA | Run | Outcome | Notes |
| --- | --- | --- | --- | --- |
| 2026-05-30 | pre-#185 | [`26714879734`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26714879734) | RED (401) | Project SAMI lacked Cog OpenAI User → motivated Pattern 23 + this audit's C9 finding |
| 2026-05-30 | #185 merge | [`26716984572`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26716984572) | GREEN | Post-RBAC grant + ≥5 min AAD propagation |
| 2026-05-31 | post-#185 | [`26717346015`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26717346015) | GREEN | Stability re-run; ~13 min wall-clock |
| 2026-05-31 | _this PR_ | _pending change-gated matrix (Pattern 24)_ | _pending_ | Audit-only diff under `docs/audit/` + SKILL.md PATCH bump + pin canon — memory leg should be the only matrix leg that fans out |

## Open items

**Deferred** (none): all 3 HITs are fix-in-PR. No cross-skill HITs were
discovered during the scan.

**Future evergreen.** Pattern 23's RBAC requirement is now documented for
consumers (C9 fix); however, a follow-up could add a copy-paste `az role
assignment create` snippet to the SKILL.md body — currently the C9 fix
points readers to `AGENTS.md § 9.7 Pattern 23` for the script. Deferred
because (a) the script involves discovering the project SAMI object ID,
which adds 4-6 lines to the SKILL and risks describing a flow that drifts
from `az cognitiveservices account project show`'s output schema; and (b)
the Pattern 23 grant is a one-time bootstrap, not a per-deploy concern.
Add to weekly-cron re-audit instead.

## Audit closure

`foundry-memory` passes Phase 4 deep audit with three fix-in-PR HITs
(C9 medium, C10 low-medium, C21 low), all bundled in a single PATCH bump
1.0.1 → 1.0.2. The remaining 18 classes resolve cleanly: skill is
authored (not wrapped), ships no Bicep / agent.yaml / reference-code
bodies, uses SDK-only paths (Pattern 16-compliant by construction), and
defers telemetry to `foundry-observability`. The audit-side fix
canonicalizes the upstream-pin body table to its already-correct
front-matter, and the two SKILL.md-side fixes document Pattern 21 (SKU
constraint) and Pattern 23 (project SAMI RBAC) for downstream consumers
who would otherwise hit the same 401 that run `26714879734` did. The
Phase-3-green test fixture is untouched.

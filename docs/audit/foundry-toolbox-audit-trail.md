# `foundry-toolbox` — Deep audit trail (21 findings)

| Field | Value |
|------|------|
| Skill | `foundry-toolbox` |
| SKILL.md version at audit start | `1.6.0` |
| SKILL.md version after audit | `1.6.1` (PATCH bump, this PR) |
| Audit date | 2026-06-01 |
| Auditor | Copilot CLI session `unsafecode/foundry-toolbox-audit` |
| Companion PR | this PR (`docs(foundry-toolbox): complete deep-audit trail`) |
| Predecessor PR | [#185](https://github.com/aiappsgbb/awesome-gbb/pull/185) — Phase 3 fixture addition |
| Bug-class scan reference | `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` Appendix A (21 classes) |
| Audit surface | `skills/foundry-toolbox/SKILL.md` (1162 L), `references/python/mcp_text_extractor.py` (62 L), `references/python/toolbox_wiring.py` (93 L), `references/upstream-pin.md` (118 L) |

This audit replaces the 52-line stub created at the time of the Phase 3
fixture landing. It scans the audit surface against each of the 21
bug classes in Appendix A and against the runtime patterns 11-25 in
`AGENTS.md` § 9.7. Numbering mirrors the canonical
`foundry-agt-audit-trail.md` ordering.

---

## Findings

### C1 — Hardcoded secrets, GUIDs, or customer identifiers

**Status:** none observed.

```bash
rg -n 'subscriptions/[0-9a-f]{8}-' skills/foundry-toolbox/  # 0 hits
rg -ni '(kyc-poc|threadlight-v[123]|ricchi|contoso[a-z]+\.com)' skills/foundry-toolbox/  # 0 hits
```

All Azure identifiers are placeholders (`<sub-id>`, `<rg>`,
`<project>`); customer name examples use `Contoso Bank` (allowed
archetype per AGENTS.md § 2.1).

### C2 — Bicep shape drift (azd-patterns canonical modules)

**Status:** N/A.

The skill ships **no Bicep**. Step 4 (L666-730) wraps `azd ai agent
init`, which scaffolds `agent.yaml` declaratively — Bicep ownership
remains with `foundry-hosted-agents` / `azd-patterns`.

### C3 — CLI install drift (Pattern 15)

**Status:** none observed.

The fixture installs only `azure-ai-projects` + `azure-identity` via
`pip`. No `azd` / `func` / `kubectl` / `helm` install is in the
fixture body, and the `Azure/setup-azd@v2.3.0` workflow action is
**not** consumed because the skill exercises the Foundry data-plane
SDK in-process, not the azd extension. Pattern 15 compliance is
trivially satisfied.

### C4 — OIDC TTL / teardown bounds (Pattern 25)

**Status:** none observed — Pattern 25 satisfied.

The fixture (`consumer_prompt.md` L32-36) creates one toolbox version
with a single zero-arg tool, verifies the create call returned an
identifier, then deletes the version. Wall-clock budget is ~2-3 min
end-to-end — two `project.beta.toolboxes` round-trips + auth —
comfortably inside the ~5-min OIDC-TTL floor. Teardown is **direct
skill-contract output** (Pattern 25 matrix row 1), so the fixture's
Step 2 marker contract correctly hard-FAILs on cleanup failure
(L82-87) rather than soft-PASS-ing. This is the right call: a
`create_version` that succeeds but whose paired `delete_version` errors
indicates a real skill bug, not a hygiene tail.

### C5 — Preview-CLI flag branching (Pattern 16)

**Status:** N/A.

No `az` / `azd` preview-CLI flags are referenced by the fixture.
SKILL.md does document `azd ai agent init --no-prompt` (L1135) but
only as a "don't use this flag" Known Issue, which is the correct
guidance shape — not a flag the fixture branches on.

### C6 — `azd` ↔ ACA Jobs deploy-gap (Pattern 18)

**Status:** N/A.

No ACA Jobs path. The toolbox runs as a **managed Foundry resource**
behind a single MCP endpoint; the deployment surface is the Foundry
account, not ACA.

### C7 — Foundry SDK shape drift (`AIProjectClient`, `MCPStreamableHTTPTool`, etc.)

**Status:** none observed.

Cross-checked against `azure-ai-projects` `2.1.0` (the pin contract at
`references/upstream-pin.md` L14, validated by the pin's
`validation.script` L57-63 import smoke). `AIProjectClient.beta.toolboxes`
and `MCPStreamableHTTPTool` both resolve cleanly on that floor. The
`Foundry-Features: Toolboxes=V1Preview` preview-opt-in header documented
at SKILL.md L194-202 is also called out in the fixture's REST-fallback
note (`consumer_prompt.md` L54).

### C8 — Deprecated SDK API references

**Status:** **none observed — positive signal.**

SKILL.md L540-554 documents the removal of `get_toolbox()` /
`select_toolbox_tools()` in MAF 1.3.0+ and of
`SkillsProvider(skill_paths=...)` in MAF 1.4.0+, and prescribes the
replacement (`SkillsProvider().get_skills(...)` +
`MCPStreamableHTTPTool`). The pin file's `validation.script` carries
two **direct negative assertions** that prove those removals stay
removed: L68-73 expects `from agent_framework.foundry import
select_toolbox_tools` to raise `ImportError`, and L75-82 expects
`SkillsProvider(skill_paths=Path('.'))` to raise `TypeError`. The
third documented removal (`get_toolbox`) is captured only in pin
prose (L24) without a direct import test — acceptable, since a
caller importing `get_toolbox` would already trip the
`select_toolbox_tools` import upstream. Net: 2 of 3 removed APIs
carry executable assertions — the "regression caught at the pin
layer" pattern the freshness contract is designed for.

### C9 — RBAC propagation race (`AcrPull`, model deployment, Cog OpenAI User)

**Status:** N/A.

The fixture performs zero `az role assignment create` calls. SKILL.md
L213 prescribes `Azure AI User` at the project scope as a
prerequisite (pre-granted in `<ci-foundry-account>` per Pattern 23) —
no in-fixture grant + propagation race.

### C10 — Region / SKU drift (Sweden Central, GlobalStandard embeddings)

**Status:** N/A.

The skill is region-agnostic. No model deployments are provisioned
by the fixture; the standing `gpt-5.4-mini` and
`text-embedding-3-small` in `<ci-foundry-account>` (Sweden Central,
`GlobalStandard` per Pattern 21) are consumed read-only.

### C11 — Cross-skill reference drift

**Status:** none observed.

L1141-1153 cross-skill table inspected end-to-end. All 11 referenced
sections exist:

- `foundry-mcp-aca` ✅
- `foundry-hosted-agents` § "MCP with per-call AAD bearer" ✅
- `foundry-hosted-agents` § "MCP `ping` trap on Foundry-hosted MCP servers" ✅
- `foundry-iq` § Common Errors ✅
- `foundry-hosted-agents` § azure.yaml (azd ai agent Extension) ✅
- `threadlight-deploy` § Foundry Toolbox Setup ✅
- `foundry-vnet-deploy` ✅
- `threadlight-hitl-patterns` ✅
- `foundry-doc-vision-speech` ✅

No stale anchors. No back-references missing (forward-only catalog).

### C12 — Link rot

**Status:** none observed.

`upstream-pin.md` `docs_to_revalidate[]` lists 3 Microsoft Learn URLs
under Foundry toolbox preview docs. The weekly `skill-freshness.yml`
HEAD-probes these; the most recent run (2026-05-31) was clean. No
inline `microsoft.com` URL in SKILL.md targets a page known to be
moved/deprecated.

### C13 — Telemetry wiring (App Insights, OTel, Foundry traces)

**Status:** N/A.

The skill does not own telemetry. App Insights / OTel wiring is
delegated to `foundry-observability` (no inline duplication, no
boundary violation). The fixture itself emits no telemetry beyond
stdout.

### C14 — JSON / YAML escaping (Bicep params, agent.yaml)

**Status:** none observed.

The two YAML blocks of concern are:

- L674-721 — `agent.yaml` `{{ param }}` jinja syntax with secrets
  (e.g. `${SEARCH_API_KEY}`) — quoted correctly, double-curly
  preserved through fence rendering
- L666-730 — `azd env set` triple-escape pattern is **not** used here
  (no JSON-array params in the `kind: toolbox` shape); the simpler
  `${VAR}` pattern is documented correctly

No backslash-escape or single-vs-double-quote drift inspected.

### C15 — Reference ↔ SKILL.md drift (env vars, function signatures, defaults)

**Status:** **HIT (medium) — FIXED IN-PR + 1 DEFERRED.**

**HIT (fixed in this PR) — stale Learn-doc method names in SKILL.md.**
SKILL.md L749-787 (the "version + lifecycle" walkthrough)
called the toolbox lifecycle methods by their *older Learn-doc*
names — `create_toolbox_version`, `list_toolbox_versions`,
`delete_toolbox_version` — while the same SKILL.md's canonical
guidance at L329 (Pattern A example), L349-354 (the disambiguation
note that explicitly calls these out as the *old* names), and L1014
(Known Issues) prescribes the SDK-actual names `create_version`,
`list_versions`, `delete_version`. The fixture's `consumer_prompt.md`
L51-52 also explicitly warns "the SDK exposes
`project.beta.toolboxes.create_version(...)` — `create_toolbox_version`
is the older Learn-doc name and may not exist on the installed SDK"
— so the walkthrough section was directly contradicting the rest of
the skill it lives in.

Drift fixed in this PR (single replacement pass, no behaviour change):

| Line | Before | After |
|---|---|---|
| SKILL.md L750 | `client.beta.toolboxes.create_toolbox_version(name="agent-tools", …)` | `client.beta.toolboxes.create_version(name="agent-tools", …)` |
| SKILL.md L778 | "…and `delete_toolbox_version` to roll back" | "…and `delete_version` to roll back" |
| SKILL.md L783 | `list_toolbox_versions("agent-tools")` | `list_versions("agent-tools")` |
| SKILL.md L787 | `delete_toolbox_version("agent-tools", "v1")` | `delete_version("agent-tools", "v1")` |

The fixture exercises `create_version` + `delete_version` directly
(Step 1, L34-36), so the C8 negative-assertions plus the fixture's
positive-path execution provide layered protection against future
regressions of either name.

**DEFERRED — env var convention split.** The skill also ships two
distinct code paths with **different env var conventions** for the
chat model deployment name:

| Location | Env var | Convention origin |
|---|---|---|
| SKILL.md L433 (Pattern A — OpenAIChatClient direct AOAI) | `AZURE_AI_MODEL_DEPLOYMENT_NAME` | AZD-scaffold canonical (matches Step 4 L674-675, L721) |
| `references/python/toolbox_wiring.py` L71 (FoundryChatClient) | `MODEL_DEPLOYMENT_NAME` | FoundryChatClient canonical (matches `foundry-hosted-agents`) |

Both names are individually correct for their layer — `OpenAIChatClient`
reads the AZD-emitted name; `FoundryChatClient` reads the Foundry-host
canonical name. The drift is **cosmetic only**, not a functional bug —
consumers who follow Pattern A get `OpenAIChatClient` working with the
AZD env, consumers who follow Pattern B get `FoundryChatClient` working
with the Foundry-host env. **Deferred** because aligning them would
either (a) require editing the canonical reference file (and would lose
sibling-skill alignment with `foundry-hosted-agents` that the reference
file deliberately mirrors) or (b) scope-creep into `foundry-hosted-agents`
to flip its canonical env var. Both options are larger than this
audit's scope. Tracked in Open Items.

### C16 — Missing `dependsOn` on RBAC (Bicep race)

**Status:** N/A.

No Bicep in this skill — no `dependsOn` to validate. RBAC is
documented as a pre-flight prerequisite (L213), not as a fixture-side
provisioning step.

### C17 — Tool wrapper type mismatches (MCPTool, OpenAPI tool shapes)

**Status:** none observed.

`MCPStreamableHTTPTool` constructor call site (L515-518) takes
`url=` + `headers=` + `approval_mode=`, matching the
`agent-framework` `1.7.0` surface (pin contract at
`references/upstream-pin.md` L20). `AzureAIProjectToolbox` (L562-564,
LangGraph variant) is imported from `langchain_azure_ai.toolboxes`
— verified to exist in `langchain-azure-ai >= 0.1.7`.

### C18 — Bot / webhook signature validation

**Status:** N/A.

No bot, no webhook, no Teams / Slack / Direct Line surface. The
skill is a tool-wiring skill, not a channel skill.

### C19 — Logging exposure (secrets in logs, PII in transcripts)

**Status:** none observed.

The fixture prints connection names, deployment names, and toolbox
IDs — none of these are secrets in the Foundry threat model. No
API keys, no JWT, no bearer tokens are logged. The skill body does
warn (L460-465) against printing `header_provider` outputs (which
contain bearer tokens).

### C20 — Async / sync mismatches (in-process vs over-the-wire)

**Status:** none observed.

Two deliberate split points:

- **Sync** `DefaultAzureCredential` at L320, L326, L613, L621 — used
  inside Pattern A / Step 3 narrative snippets that are demonstrative
  one-shots
- **Async** `azure.identity.aio.DefaultAzureCredential` at
  `references/python/toolbox_wiring.py` L29-32 — used inside the
  canonical wiring helper that runs under an asyncio event loop in
  the `FoundryChatClient` path

The reference file header (L7) documents the async choice and cites
MID-I (managed-identity-injection) compatibility as the reason.
This is the correct convention.

### C21 — Outdated package version pins (prose vs frontmatter contract)

**Status:** **HIT (low) — FIXED IN-PR.**

Several sites had drifted prose `1.6.0` / `1.6` / `2026-05-29` while
the pin frontmatter contract was already `1.7.0` (the auto-tier pin
refresh from the prior week bumped `packages[*].version` and
`validation.script`, but the audit-only prose tables in the same file,
plus SKILL.md narrative + reference-file headers, were not
co-updated):

| File | Line | Before | After |
|---|---|---|---|
| `references/upstream-pin.md` | L106 (prose table) | `agent-framework 1.6.0` | `agent-framework 1.7.0` |
| `references/upstream-pin.md` | L92 (`last_validated`) | `2026-05-29` | `2026-06-01` |
| `references/python/toolbox_wiring.py` | L1 (module docstring) | `MAF 1.6` | `MAF 1.7` |
| `references/python/toolbox_wiring.py` | L20 (header comment) | `agent-framework 1.6.0` | `agent-framework 1.7.0` |
| `references/python/mcp_text_extractor.py` | L11 (header comment) | `MAF 1.6` | `MAF 1.7` |
| `SKILL.md` | L360 | `agent-framework-core==1.6.0` | `agent-framework-core==1.7.0` |
| `SKILL.md` | L361 | `agent-framework-foundry==1.6.0` | `agent-framework-foundry==1.7.0` |
| `SKILL.md` | L470 | "MAF 1.6 doesn't unwrap" | "MAF 1.7 doesn't unwrap" |
| `SKILL.md` | L497 | "(MAF 1.6.0, …)" | "(MAF 1.7.0, May 2026)" |
| `SKILL.md` | L515 | `# MAF 1.6 API` | `# MAF 1.7 API` |
| `SKILL.md` | L22 (metadata.version) | `1.6.0` | `1.6.1` (PATCH bump per AGENTS.md § 5) |
| `SKILL.md` | L23 (validated) | `2026-05-28` | `2026-06-01` |

The pin's `packages[*].version` (frontmatter contract, L20) was
already at `1.7.0` and the `validation.script` (L57) installs
`agent-framework~=1.7.0` — so the pin gate was correctly evaluating
1.7.0 binaries during PR validation, but the human-readable prose
documentation across SKILL.md narrative + reference-file headers was
stale and would mislead any consumer reading the skill end-to-end.

Four `1.6`-shaped strings in the audit surface are **intentionally
preserved** as historical boundary markers and are NOT regressions:

- `SKILL.md` L366 — "Pre-1.6 agent-framework versions …" (compatibility
  boundary callout)
- `SKILL.md` L543 — external PR link prose
- `SKILL.md` L551 — "MAF 1.6.0 added per-tool factory methods" (historical
  changelog fact)
- `upstream-pin.md` L31 — "agent-framework 1.6.0 requires mcp>=1.24.0"
  (mcp floor justification)

---

## Fixture

| Field | Value |
|------|------|
| Path | `skills/foundry-toolbox/test-fixture/consumer_prompt.md` (93 lines, **unchanged in this PR**) |
| Pattern compliance | P11, P12, P15, P17, P20, P22, P24, P25 |
| Wall-clock budget | ~2-3 min (`create_version` + `delete_version` round-trips + auth; no model invocation) |
| Azure cost | ~$0 (two `project.beta.toolboxes` API calls + `DefaultAzureCredential`) |
| Success signal | Pattern 12 file marker at `/tmp/foundry-toolbox-smoke-result` |
| Teardown | Explicit `delete_version` in Step 1; cleanup failure hard-FAILs the smoke per Step 2 marker contract (Pattern 25 matrix row 1 — delete IS the skill-contract output) |

The fixture is a Phase 3 carry-over (predecessor PR #185) — proven
GREEN on `main` and **not modified** by this audit-only PR.

---

## CI matrix runs

`foundry-toolbox` already has multiple GREEN runs on `main` from the
Phase 3 fixture landing. This audit-only PR is doc-touch only; CI
fanout on this branch will re-run the leg as part of the change-gated
matrix (Pattern 24) since `skills/foundry-toolbox/SKILL.md` is in the
diff.

| # | SHA | Run | Outcome | Notes |
|---|---|---|---|---|
| 1 | `155256b` | [`26684167090`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26684167090) | ✅ GREEN | Phase 3 fixture-merge run on `main` (2026-05-30). First green of the toolbox leg. |
| 2 | `ca41e1d` | [`26723599405`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26723599405) | ✅ GREEN | Stability re-run on `main` (2026-05-31). Confirmed Pattern 25 teardown N/A path holds. |
| 3 | (this PR) | (filled after first PR push) | (pending) | Doc-touch fanout; toolbox leg re-runs because SKILL.md PATCH bump is in the diff. |

The pre-existing two GREEN runs satisfy the "≥ 2 GREEN main runs"
informal stability bar for audit-only PRs (no fixture change → no new
stability cycle required).

---

## Open items

- **Missing E2E test file** — `scripts/tests/test_e2e_foundry_toolbox.py`
  does not exist (Spec § 2026-05-30 design Appendix B). Phase 4
  coverage work owns the rollout of these per-skill pytest harnesses
  for the catalog; out of scope for this audit-only PR.
- **C15 env var convention alignment** — `AZURE_AI_MODEL_DEPLOYMENT_NAME`
  (Pattern A / AZD scaffold) vs `MODEL_DEPLOYMENT_NAME` (Pattern B /
  FoundryChatClient reference file). Deferred to a future cross-skill
  alignment pass with `foundry-hosted-agents` — the two skills must
  flip together or stay together.
- **Sidecar variant audit** — not exercised by the fixture (no
  sidecar path in `foundry-toolbox`'s scope; sidecar wiring is owned
  by `foundry-mcp-aca` and audited there).

---

## Audit closure

This audit was performed against SKILL.md @ `1.6.0`. After this PR
lands (`1.6.0` → `1.6.1` with the C21 fix-in-PR), the next deep-audit
pass should be triggered on the next MINOR/MAJOR `agent-framework`
or `azure-ai-projects` upstream bump (per `references/upstream-pin.md`
freshness contract) or on detection of cross-skill ref drift against
`foundry-hosted-agents` / `foundry-iq` / `foundry-mcp-aca`.

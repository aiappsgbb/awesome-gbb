# Changelog

## Unreleased — #518 deployment and recovery contract candidate

Candidate live results remain source-bound; full acceptance, adoption and release
remain pending. See the deployment-contract acceptance record for actual coverage.

- [`foundry-hosted-agents`](skills/foundry-hosted-agents/SKILL.md) MAJOR **3.0.0**:
  versioned consumer profile, early capabilities, pre-parse response custody,
  adoption hashes and bounded recovery; existing MAF dependency cohort retained.
- [`foundry-mcp-aca`](skills/foundry-mcp-aca/SKILL.md) MAJOR **2.0.0**,
  [`foundry-mcp-aca-jobs`](skills/foundry-mcp-aca-jobs/SKILL.md) MAJOR **2.0.0**,
  [`foundry-teams-bot`](skills/foundry-teams-bot/SKILL.md) MAJOR **2.0.0**,
  [`foundry-mcp-auth`](skills/foundry-mcp-auth/SKILL.md) MAJOR **2.0.0**, and
  [`ghcp-hosted-agents`](skills/ghcp-hosted-agents/SKILL.md) MAJOR **3.0.0**:
  explicit operation custody and no replay based on an uncertain client result.
  Candidate delegated-auth release gates remain unchanged.
- [`foundry-iq`](skills/foundry-iq/SKILL.md) MAJOR **2.0.0**: replace custom
  reserved `FOUNDRY_IQ_*` environment names with `APP_IQ_*`.
- Contract-reference PATCH updates: `azd-patterns` **1.6.1**,
  `foundry-network-runbook` **1.1.1**, `foundry-caphost-lifecycle` **2.0.2**,
  `foundry-vnet-deploy` **1.3.2**, `foundry-rbac-audit` **1.0.2**,
  [`foundry-evals`](skills/foundry-evals/SKILL.md) **1.4.2**,
  `foundry-doc-vision-speech` **1.2.10**, `foundry-observability` **1.2.5**,
  and `azure-sre-agent` **1.0.2**.
- The #509 tenant bootstrap and manual fixture remain byte-identical.
  Downstream installation/adoption is not performed by this change.
- The Jobs candidate adds an explicit resource-group-scoped CI reuse entrypoint
  and authenticated standing-input gate. Existing identities/database/RG and
  grants are never provisioned or cleaned up by that path; exact temporary
  objects and image receipts drive verified cleanup. Ordinary consumer
  provisioning remains the default. Live execution is still separately gated.

## Unreleased — progress-guard scale-out contract

- `progress-guard` MINOR **1.2.1 → 1.3.0**: end-to-end assignment ownership,
  ordinary authorized operations versus new-effect escalation, scoped blockers,
  evidence reuse/invalidation and one actionable dependency/release notice.
- Optional declared limits and coordination fields preserve the existing SQLite
  schema and bounded terminal output. No scheduler, notification sender, automatic
  write lock, runtime installation or behavioral certification.
- Ten synthetic regression cases; catalog and runtime behavior remain distinct.

## Unreleased — progress-guard recovery clarifications

- [`progress-guard`](skills/progress-guard/SKILL.md) PATCH **1.2.0 → 1.2.1**:
  remember permitted file fallback after failed native discovery; do not retry
  discovery solely because context was compacted.
- Clarify no-progress review thresholds are not task expiry or invented phase
  quotas. Ordinary within-scope corrections may use the existing one bounded
  recovery only with known effects, without overriding explicit limits or approvals.
- No schema/helper changes or claims of runtime compaction/discovery repair.

## Unreleased — progress-guard child coordination

- [`progress-guard`](skills/progress-guard/SKILL.md) MINOR **1.1.0 → 1.2.0**:
  explicit child skill loading and assignment boundaries, quiet intermediate
  execution, terminal-only returns with safety/approval exceptions, and parent
  receipt deduplication/verification before dependent work or compaction.
- Optional read-only `handoff` emits at most 4 KiB of UTF-8 JSON from terminal
  state; working/waiting states, inconsistent completion and oversize packets
  fail explicitly. Existing ledger schema and default reads are unchanged.
- Local synthetic tests are not evidence of App notification suppression,
  automatic instruction inheritance or runtime compaction effectiveness.
  Plugin stays at 4.35.0; installed behavior needs explicit loading in each child.

## 4.36.0 — Proposed / Unreleased

Adds [`copilot-doctor`](skills/copilot-doctor/SKILL.md) **1.1.1 local source
candidate** for maintenance of existing Copilot App/CLI setups, separate from
bootstrap guidance. Includes read-only inventory, secret-value suppression,
source-attributed findings, opt-in private scan history, bounded CLI help probes
and an approval/backup/verification/rollback repair runbook.

The 1.1.0 feedback iteration adds opt-in bounded MCP initialization and useful-tool
checks, independent auth evidence, and explicit accepted structural preferences
in the same private history store. Browser extension mode can be intentional;
neither extension nor isolated mode is imposed as a universal requirement.

The 1.1.1 review fixes isolate MCP 1.27.x protocol tests from the shared MCP 2.x
cohort, enforce malformed-policy/expectation rejection, restrict schema metadata,
and terminate owned probe descendants even after their group leader exits.

- Proposed plugin/marketplace MINOR **4.35.0 → 4.36.0**: **42 skills**,
  **35 upstream pins**, **7 internal-IP entries**; Azure fixture count unchanged.
- No automatic updates, cleanup, credential resets, MCP startup sweeps, internal
  database writes or scheduled scans. Intentional pins/exclusions remain intact.
- Local tests and outstanding runtime/behavioral limits are recorded in the
  [validation record](docs/maintenance/copilot-doctor-validation.md).

## 4.35.0 — Proposed / Unreleased

Adds [`progress-guard`](skills/progress-guard/SKILL.md) **1.1.0 draft source
candidate**: execution memory and bounded recovery, with a compaction preparation
and selective-readback protocol. Reuses existing plans/todos; no supervisors,
automatic hooks or claims of runtime/tool preemption.

- Proposed plugin/marketplace MINOR **4.34.0 → 4.35.0**: **41 skills**,
  **35 upstream pins**, **31 auto-tier pins**, **6 internal-IP entries** and
  **25 registered Azure fixtures**. No Azure enrollment is needed.
- Skill MINOR **1.0.0 → 1.1.0** adds native CLI control guidance, host/SDK
  boundaries, selective recovery and approved fresh-session handoffs.
  Optional `read --recent 0` omits historical events without changing storage
  or the existing six-event default.
- Local tests cover persistence, output selection and packaging, not actual
  compaction effectiveness. Behavioral trials, native package loading and
  promotion remain pending in the
  [validation record](docs/maintenance/progress-guard-validation.md).
- Complete catalog contract expectations and candidate allowlists, without
  weakening checks or changing existing skills' acceptance gates.

## Unreleased — Historical-document sanitization

- Replace personal filesystem paths, session identifiers and managed-identity
  identifiers in historical documentation and contributor guidance with
  placeholders. Preserve technical findings and public built-in role IDs.
- Add two offline regression cases for these historical-document boundaries.
- This subset changes no skill contracts or versions, runtime code, fixtures,
  deployment templates or live CI configuration. Skill-level sanitization remains
  deferred pending its required validation evidence.
- No Git history rewrite or publication approval for private-upstream content
  is included.

## 4.34.0 — Proposed / Unreleased

Adds [`web-experience-design`](skills/web-experience-design/SKILL.md)
**1.0.0 source candidate**: task-first web experiences with content and navigation
before styling, real-content wireframes, meaningful icons and motion, optional
design tools, and observable browser task verification.

- Proposed plugin/marketplace MINOR **4.33.0 → 4.34.0**: **40 skills**,
  **35 upstream pins**, **31 auto-tier pins**, **5 internal-IP entries** and
  **25 registered Azure fixtures**. No Azure enrollment is added for this local
  web-design workflow.
- Separate refinement, audit and structural-design paths; no mandatory theme,
  stack, model, external generator or global installation.
- Add local contract tests and three explicitly unexecuted output scenarios.
  Packaging checks are not generated-UI acceptance.
- Keep the existing candidate gates intact. New output acceptance, native skill
  loading and release/global promotion remain pending in the
  [validation record](docs/maintenance/web-experience-design-validation.md).

## Unreleased — upstream workflow integration

Keep the existing awesome-gbb skill names and entry points; integrate verified
official workflow changes rather than replacing the catalog.

- [`foundry-routines`](skills/foundry-routines/SKILL.md) MINOR **1.0.6 → 1.1.0**:
  SDK/azd lifecycle, declarative routines, supported event prerequisites and
  live-observed update/readback boundaries.
- [`foundry-skill-catalog`](skills/foundry-skill-catalog/SKILL.md) MAJOR
  **1.2.0 → 2.0.0**: native versions/default promotion, selected pinned
  consumption and build-only bundles without a MAF dependency. The entry-point
  name and adapter constructor remain, but the API/dependency and file-copy
  migration is explicit; stale selected-output directories fail before writes.
- [`foundry-evals`](skills/foundry-evals/SKILL.md) MINOR **1.3.2 → 1.4.1**:
  supported agent-target evaluation, explicit captured-response fallback,
  numeric per-item results and corrected citation URL checks. Review fixes
  share the timeout budget across HTTP calls/pages, reject late results and
  bound cleanup separately.
- [`foundry-toolbox`](skills/foundry-toolbox/SKILL.md) MINOR **2.1.2 → 2.2.0**:
  direct/nested consent handling, Streamable HTTP approval discovery and exact
  proxy tool names through Copilot SDK registration/dispatch, retaining GA
  Toolbox and stable Tool Search.
- [`foundry-vnet-deploy`](skills/foundry-vnet-deploy/SKILL.md) MINOR
  **1.2.1 → 1.3.0**: ownership-aware intake and read-only network inventory;
  vendored templates/Citadel interfaces remain unchanged.
- Unit CI installs the evaluation transport clients. Pin validation preserves
  explicit tenant-cache and judge selectors without inheriting unrelated secrets.

Sanitized manual evidence and its limits are recorded with each changed skill.
Execution on standing CI resources is not a GitHub Actions run or a blanket
release/quality certification. External event delivery, full OAuth lifecycle,
private-network runtime inference and the documented routine response-readback
limitation remain explicitly separate from the proven paths.

## 4.33.0 — Proposed / Unreleased

Adds [`agent-framework-harness`](skills/agent-framework-harness/SKILL.md)
**1.0.3** as the runtime-level contract for Microsoft Agent Framework
`create_harness_agent`, including verified defaults and provider ordering,
compaction, bounded plan/execute composition, session recovery, hosted adapter
wiring, an offline construction smoke, and a registered live Foundry fixture.

- Proposed plugin/marketplace MINOR **4.32.0 → 4.33.0**:
  **39 skills**, **35 upstream pins**, **31 auto-tier pins**, and
  **25 registered fixtures**.
- Preserve the unpublished AgentOps and delegated MCP auth candidate status and
  every existing ACA Jobs, MCP auth, and AgentOps catalog entry.
- Use a runner-owned Azure CLI login in the Harness CI fixture rather than
  asking the Copilot process to exchange GitHub identity tokens.
- Provision the pinned smoke interpreter inside the approved workspace;
  execute one canonical probe and verify its receipt before accepting PASS.
- Execute only the Harness smoke directly in its runner-controlled CI step
  under the maintainer-approved exception; no agent-authored result is authoritative.
- Keep deployment, identity, RBAC, rollout, and lifecycle in
  [`foundry-hosted-agents`](skills/foundry-hosted-agents/SKILL.md)
  **2.2.1**, whose reciprocal ownership routing now points runtime
  composition to `agent-framework-harness`;
  deterministic governance remains in
  [`foundry-agt`](skills/foundry-agt/SKILL.md).

## 4.32.0 — Proposed / Unreleased

**Draft checkpoint, not a release.** Adds
[`foundry-mcp-auth`](skills/foundry-mcp-auth/SKILL.md) **1.3.0 candidate** for
custom delegated OAuth, strict MCP resource-server policy and canonical
Prompt/Toolbox/Hosted composition. Detailed results and open acceptance gates
are maintained in the [validation notes](docs/maintenance/foundry-mcp-auth-validation.md),
not in reusable skill instructions. No four-path, multi-user or release approval.

- Proposed plugin/marketplace MINOR **4.31.0 → 4.32.0**:
  **38 skills**, **34 upstream pins**, **30 auto-tier pins**, **24 registered fixtures**.
- [`azd-patterns`](skills/azd-patterns/SKILL.md) MINOR **1.5.2 → 1.6.0**:
  additive private-network, identity and Basic project-host modules.
- [`foundry-toolbox`](skills/foundry-toolbox/SKILL.md) PATCH **2.1.1 → 2.1.2**,
  [`foundry-hosted-agents`](skills/foundry-hosted-agents/SKILL.md) PATCH **2.1.3 → 2.1.4**,
  [`foundry-prompt-agents`](skills/foundry-prompt-agents/SKILL.md) PATCH **1.1.9 → 1.1.10**,
  and [`foundry-mcp-aca`](skills/foundry-mcp-aca/SKILL.md) PATCH **1.2.5 → 1.2.6**:
  delegated-auth ownership and compatibility clarifications.
- Preserve the existing jobs implementation and separate dependency cohorts.
  Local checks and manual live evidence do not waive pending CI or human gates.
- Opt-in inbound-token proof returns the authenticated caller's actual
  validated identity claims; default receipts remain pseudonymous. Raw tokens
  are never returned or logged. Fresh live proof is recorded in the notes.
- Identity view returns actual claims at the top level without synthetic
  identity labels. Shared Prompt/Hosted instructions render those claims
  after a fresh identity-tool call, including normal-language follow-ups.
- The opt-in view also preserves actual optional `upn`, `preferred_username`
  and `name` claims from the verified bearer; no UPN inference, Graph lookup
  or default-mode identity disclosure.
- Consolidate local installation/dependency and version/default-operation
  guidance. Add an explicit service-default tool-selection option without
  changing existing invocation behavior. Source-reviewed Fabric, OneDrive
  and SharePoint profiles remain preparation only: no licensed-service tests,
  downstream OBO runtime or automatic resource grants.
- Scope PR Azure tests to changed skills and declared dependencies when only
  independent local test jobs change. Shared execution changes and ambiguous
  workflow comparisons retain full coverage; main/scheduled canaries and
  required checks are unchanged.

## 4.31.0 — Proposed / Unreleased

**Draft candidate eligible for PR validation.** These notes describe proposed
catalog changes, not merged, released, or production-ready.
Completed **corrected-source manual execution PASS**;
**quality FAIL (4/5 thresholds)**; **Doctor readiness BLOCKED**;
**release PENDING**. CI results and candidate SHA will be recorded in the PR. The
[sanitized validation record](docs/maintenance/foundry-agentops-validation.md)
documents manual evidence as of 2026-09-05, before PR CI: the corrected
166.5-second manual CLI-user cycle separately from the historical 5/5 cycle,
not production readiness. The draft addition is not publicly installable
through the default install while unmerged; no released downstream pin is available.

### Added

- [`foundry-agentops`](skills/foundry-agentops/SKILL.md) **1.0.0**: complete
  per-agent adoption and release-evidence workflow using exactly Azure AgentOps
  **0.14.0** (`agentops-accelerator==0.14.0`). Covers native result/evidence review,
  Doctor diagnostics, regression-baseline decisions, and standalone versus
  Threadlight workflow ownership. Citadel controls, Threadlight pipelines/final
  readiness, and specialist skill contracts remain authoritative.
- Foundry Building Blocks catalog registration, README adoption guidance,
  generated static catalog entries, and discovery keywords: `agentops`,
  `agent-operations`, `release-evidence`, `doctor`, `regression-baseline`.
- Sanitized prior and corrected live-manual provenance, with separate execution,
  quality, Doctor readiness, and CI/release status. The corrected eval returned
  exit 2 (fluency 2 below threshold 3) despite an exact expected response match;
  its execution checker passed. Doctor and its evidence checker returned exit 2
  with valid blocked evidence: 2 critical findings, 8 warnings, 1 info.
  Current-fixture and private-evidence fingerprints bind the corrected result;
  prior fingerprints remain distinct. No retries or shared-environment repair.
  Stored-response purge remains unproven under approved service retention. Generated
  draft entries link that record rather than advertising a public install.

### Changed

- Proposed plugin/marketplace MINOR **4.30.0 → 4.31.0**, with synchronized
  descriptions and counts: **36 → 37 skills**, **32 → 33 upstream pins**,
  **28 → 29 auto-tier pins**, **22 → 23 registered fixtures**. Registration is
  not evidence that the unchanged CI/SP fixture or full matrix has passed.
- [`foundry-evals`](skills/foundry-evals/SKILL.md) PATCH **1.3.1 → 1.3.2**:
  one adoption-workflow cross-reference; deep evaluators/datasets stay here.
- [`foundry-observability`](skills/foundry-observability/SKILL.md) PATCH
  **1.2.3 → 1.2.4**: one adoption-workflow cross-reference; OTel/App Insights
  wiring stays here.
- [`foundry-agt`](skills/foundry-agt/SKILL.md) PATCH **2.0.0 → 2.0.1**:
  one adoption-workflow cross-reference; AGT runtime/policy enforcement stays here.

The three specialist changes do not alter Azure commands, code samples, or
description triggers. AgentOps aggregates their evidence; it never replaces them.

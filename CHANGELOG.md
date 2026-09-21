# Changelog

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

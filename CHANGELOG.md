# Changelog

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

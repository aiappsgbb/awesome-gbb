# Progress guard validation

`progress-guard` 2.1.0 has approved source publication and local package
synchronization. Source availability is not proof of agent behavior.

## Compact protocol candidate

The core recovery/evidence rules live in SKILL.md; assignment, approval and
terminal acceptance details live in children.md. Kickoffs carry task-specific
context and a short skill reference rather than repeating the protocol.
Compaction/storage guidance refers to those rules instead of restating them.
Coordinator-only execution, genuine block/resume, terminal deduplication,
native/safety gates, scoped UNKNOWN, independent work and prior evidence remain.

Successful append confirmation no longer requires a full readback on every write.
Recovery, uncertain persistence, changed inputs and final acceptance still require
current state. Optional `append --event -` accepts complete JSON through stdin,
retaining file input, schema 1 and the same transaction/validation/receipt.
Coordinator acceptance inspects sufficient relevant proof; missing/inconsistent
claims need targeted clarification, not blind trust or duplicate execution.

Five additional cases cover stdin/file compatibility and failure atomicity,
task-only kickoffs, selective acceptance and snapshot boundaries. The resulting
54 contract cases comprise 52 bundled tests and two catalog packaging cases.
These are executable data tests and static wording checks, not observed behavior.
The next-real-task criteria in scenarios.md have not been started. No private
global instructions are included in the source or validation record. On
2026-10-01, the owner explicitly authorized source publication followed by
supported local package synchronization without waiting for that trial.
This changes the delivery gate, not the evidence: observed behavior remains
untested.

Local validation on 2026-10-01: all 54 contract/packaging cases passed; catalog
lint, plugin structure and generated-site link validation passed. The four
runtime guidance files were reduced from 55,923 to 34,284 UTF-8 bytes
(7,602 to 4,358 whitespace-separated words). This is a measured text reduction,
not a token, latency or model-quality result. The approved personal 2.1.0
installation matched the complete eleven-file source manifest and passed all
52 bundled tests. Native CLI discovery selected that personal copy; an existing
session's native skill/global adoption was not established. Managed plugin
synchronization follows accepted upstream availability, with complete payload
parity and runtime discovery checked separately from version labels.

## Coordinator separation candidate

Version 2 intentionally changes the prior orchestration contract: a coordinator
routes implementation, executable checks, integration and deployment to authorized
executors rather than doing that work itself. It reads final evidence and keeps
the consolidated ledger. Solo work stays direct; an explicit role transition
reconciles child ownership before execution resumes.

Children return one terminal result per assignment execution: completed, failed,
or blocked/decision-required. Ordinary recovery stays inside the mandate.
Intermediate dependency/ownership/head changes stay local, not separate notices.
A genuine block is terminal until the parent resolves it and explicitly resumes
the same assignment, allowing a later deduplicated terminal revision. Safety,
cancellation and required native permission/input gates remain immediate exceptions.
The coordinator records accepted/failed/blocked disposition and routes the concrete
next action, not progress polls or routine publication phase gates.

Eight added cases cover optional role persistence/shape, legacy records and schema
1 compatibility, scripted block/resume receipts, compatible failed packets and
static contract clauses. There are **49 ProgressGuard contract cases** (47 bundled
and two packaging). These are local data/wording checks, not observed coordinator
behavior, native compaction or model-compliance evidence.

Local validation on 2026-09-30: all 49 contract cases and three site-preservation
regressions passed; catalog lint, plugin integrity and generated-site link checks
passed. The site was rebuilt; unrelated footer/freshness-age-only churn was excluded
from the focused diff. No Azure path changed or required live testing.

The controlled coordinator trials in the scenario matrix remain unexecuted.
Native loading of the complete personal 2.0.0 package succeeded on 2026-09-30;
this does not certify plugin discovery, compaction or model compliance.
A personal installation or upstream source merge is not a catalog-wide release
or permission to retrofit active sessions. Exact
installation hashes, backup and native-load outcome belong in private session
evidence, not public machine inventory.

## Prior 1.4.0 approval reconciliation

Before asking approval, compare the current user mandate with the exact operation,
target/increment and material effect. Covered ordinary work proceeds; an uncovered
effect requires one precise decision whose actual result survives recovery.
Unavailable replies are not consent and do not justify repeated unchanged asks.
Revocation, narrowing or changed effects invalidate only affected authority;
host/tool gates, explicit limits and UNKNOWN reconciliation remain mandatory.

Optional `approvals` records retain scoped decision identity, provenance and result
in existing snapshots and bounded terminal output. Eight new executable helper
cases cover explicit-release records, review/new-permission blocks, unavailable
reply recovery, paraphrases versus different targets, revoked/changed authority
with unaffected evidence retained, UNKNOWN, invalid records and the byte cap.
There are **41 ProgressGuard contract cases** (39 bundled and two packaging).
The helper checks declared data, not authorization truth or semantic equivalence.
It does not ask questions, grant permission or install an approval platform.

The existing scenario matrix adds controlled approval trials with observable
expected actions. These have **not been executed as observed agent trials**;
no native compaction or model evaluation is claimed. Source and CI evidence for
this candidate belong in its PR, separately from historical results below.

## Prior 1.3.0 scale-out contract

The additive 1.3.0 contract assigns end-to-end outcomes with explicit write
ownership, ordinary authorized operations, true dependencies and escalation
boundaries. Shared capacity is distinct from write conflict. A blocker preserves
`blocks`/`does_not_block` scopes without releasing UNKNOWN effects or dependent
reconciliation work. Limits are optional declarations, never guessed budgets.

Optional `assignment_scope`, `declared_limits`, `blocker_scope`, `evidence_delta`
and `coordination_change` fields use the existing JSON state/schema. The helper
checks declared shape and simple contradictions, preserves them in the existing
4 KiB terminal packet and never sends notifications or schedules operations.
The prior actionable dependency-change/ownership-release notice exception is
removed in 2.0.0. Its evidence field remains compatible and terminal-only.

Ten new deterministic tests exercise scripted sibling records, conflict blocking,
duplicate/unchanged receipts, affected proof deltas, same-assignment effect-free
correction, UNKNOWN preservation, a healthy long-build record, optional-field
compatibility/errors and output size. Combined with the existing 21 bundled cases
and two packaging cases, the candidate has **33 local contract tests**.

The tests provide decisions as input. They do **not** demonstrate an agent chose
correctly, detect real path/resource aliases, prove independence, enforce cloud
write exclusion or measure interventions/throughput. No coordinator/child model
evaluation, real long build, Azure operation or native loading trial was run for
this candidate. Those observed-behavior gates remain pending. Exact source and CI
results belong in the candidate PR; previous results below are historical.

## Prior 1.2.1 clarification

The 1.2.1 clarification retains a failed-discovery fallback across compaction and
distinguishes no-progress review thresholds from task expiry. Ordinary corrections
may consume the existing bounded recovery only inside current authorization and
with evidence excluding uncertain effects. Explicit limits, permissions and
UNKNOWN reconciliation remain mandatory. Static wording checks are not behavioral
acceptance; the added scenarios remain unexecuted.

## Child coordination follow-up

The 1.1.0 contract described bounded child returns but did not specify mandatory
child loading, quiet intermediate work, assignment-bound terminal reports or
parent receipt/acceptance handling. The follow-up adds those instructions and
an optional read-only `handoff` command. It does not alter the SQLite schema.

Nine synthetic handoff cases cover terminal-state gating, completion consistency,
assignment binding, exact UTF-8 size limits, unchanged default history behavior
via the existing suite, retained unknown operations, stable report identities,
and separate child/parent ledgers with duplicate-receipt rejection. Together with
the twelve existing cases and two packaging cases these are **23 local tests**.
These checks exercise helpers and persisted data, not model compliance or
suppression of App-generated notifications. The parent deduplication/integration
sequence remains an instruction contract, not an installed orchestrator.

Native child loading, terminal-only delivery, actual parent consolidation after
notifications, stale-result handling and multi-child compaction require observed
trials. Do not call these scenarios passed because the instructions exist.
No active customer sessions are modified for this validation.

Local predecessor validation on 2026-09-24: the **39-test targeted set passed**
(23 progress-guard cases plus 16 site/adjacent packaging regressions).
Reapplying the approved change to current main passed **41 targeted tests**
(23 progress-guard cases plus 18 site/adjacent packaging regressions).
Full local discovery found **1409 tests**, current main's 1400 plus nine;
discovery is not execution of the full suite.
Catalog lint, plugin integrity and the generated site's root-relative link
validation passed. Remote validation evidence belongs to the new follow-up PR;
the prior 1.1.0 CI result does not cover these new changes.

## Prior 1.1.0 local validation scope

The twelve bundled persistence/output-selection cases cover latest-snapshot/history reads,
stale/skipped revisions, duplicate event keys, append-only history,
evidence requirements for progress, invalid state, independent work items,
fallback CLI roundtrip/stale writes, missing-database reads, snapshot-only recovery,
bounded work-scoped history, and invalid history arguments without side effects.
Two catalog tests additionally check packaging, links and pending acceptance.

The synthetic snapshot-only test excludes a large old event while preserving
the latest state, failed-attempt conditions and an unknown operation handle.
It asserts output is less than half the default history read for that fixture;
this is a byte-output check, not measured token savings or native compaction.

## Review correction

The initial PR head's local 25-test subset passed, but CI run
[35834241728](https://github.com/aiappsgbb/awesome-gbb/actions/runs/35834241728)
ran 1,359 tests and failed six catalog assertions: stale version/count
expectations, a missing proposed changelog entry and candidate allowlist drift.
The follow-up updates those contracts rather than waiving them. The PR records
the follow-up test outcomes separately from this initial failed run.

Follow-up local results (2026-09-23): **58 targeted tests passed**, including
all six formerly failing catalog tests, the twelve bundled helper cases and two
new packaging cases. Catalog lint, plugin validation and 50 generated HTML pages
with zero broken root-relative links also passed.

The broader local run is **not green**: 1,356 tests ran, with four errors and
32 skips. The errors are in unchanged private-hosted-bootstrap SDK tests;
the local environment has `azure-ai-projects` 2.1.0 and `openai` 2.37.0, whereas
CI installs the workflow's newer bounded versions. No unrelated SDK code or
assertions were relaxed. The full CI rerun, not this local result, must establish
the updated head's catalog-wide status.

## Reproduce

Run from the repository root:

```bash
python3 -m unittest discover -s skills/progress-guard/tests -p 'test_*.py' -v
python3 -m unittest scripts.tests.test_progress_guard -v
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 scripts/build-site.py --out docs/
```

The catalog adapter loads the same bundled tests into the existing unit-test
job; it does not duplicate their implementation. The draft PR records the
actual command outcomes. The helper uses only Python's standard library and
SQLite with JSON support; this skill has no Azure path to live-test or upstream
package pin to refresh.

## Not yet established

- The [behavioral scenarios](../../skills/progress-guard/tests/scenarios.md)
  have **not been executed as observed agent trials**. Passing persistence
  tests does not prove instruction-following, better recovery, or fewer loops.
- Native runtime discovery and invocation of the repository/plugin package
  have not been tested.
- The native `/compact` sequence, host-specific control availability and
  before/after context usage have not been exercised. CLI/SDK guidance is
  documentation-backed, not a live runtime or performance acceptance claim.
- SQLite constraints validate storage shape and consistency, not the truth
  or sufficiency of evidence.
- A skill cannot preempt an in-flight hung tool. Initial waits are not
  deadlines, and this package installs no hooks, timers, supervisors or watchers.

Review and observed behavioral acceptance remain pending. Installation does
not alter global instructions or activate an automatic routing policy.

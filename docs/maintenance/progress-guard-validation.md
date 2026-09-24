# Progress guard validation

`progress-guard` 1.2.0 is a follow-up candidate to the source merged in PR #511.
Source availability is not release approval or proof of agent behavior.

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

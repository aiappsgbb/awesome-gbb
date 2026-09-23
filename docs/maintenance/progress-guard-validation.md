# Progress guard validation

`progress-guard` 1.0.0 is a draft source candidate. Publication as a draft PR is
not release approval or proof of agent behavior.

## Local validation scope

The nine bundled persistence cases cover latest-snapshot/history reads,
stale/skipped revisions, duplicate event keys, append-only history,
evidence requirements for progress, invalid state, independent work items,
fallback CLI roundtrip/stale writes, and missing-database reads.

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
- SQLite constraints validate storage shape and consistency, not the truth
  or sufficiency of evidence.
- A skill cannot preempt an in-flight hung tool. Initial waits are not
  deadlines, and this package installs no hooks, timers, supervisors or watchers.

Review and observed behavioral acceptance remain pending. Installation does
not alter global instructions or activate an automatic routing policy.

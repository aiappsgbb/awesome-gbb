# Manual skill freshness runbook

Use this runbook when the weekly freshness detector must keep filing issues,
but auto-assignment to the GitHub Copilot coding agent is temporarily unsafe
or unavailable.

## Operational contract

- **Detection always stays on.** `skill-freshness.yml` keeps running in both
  modes; never disable the detector or the cron.
- **Manual mode is the safe fallback.** Auto-tier issues stay human-owned and
  carry `manual-review`.
- **Copilot mode restores assignment.** Auto-tier issues go back to
  `@Copilot`; `automation_tier: issue_only` stays human-only in both modes.

## 1) Set manual mode

```bash
gh variable set FRESHNESS_EXECUTION_MODE --repo aiappsgbb/awesome-gbb --body manual
```

This makes scheduled runs conservative even if a future operator forgets to
pass an override.

## 2) Preview the next run

```bash
gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=true -f execution_mode=repository
```

`execution_mode=repository` means “use the repo variable.” If the variable is
missing, the workflow safely falls back to `manual`.

## 3) Run it live

```bash
gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=false -f execution_mode=repository
```

## 4) Inspect runs and issues

Recent workflow runs:

```bash
gh run list --repo aiappsgbb/awesome-gbb --workflow "Skill freshness" --limit 5
```

Suggested issue checks:

```bash
gh issue list --repo aiappsgbb/awesome-gbb --label freshness --limit 20
gh issue list --repo aiappsgbb/awesome-gbb --label manual-review --limit 20
```

In **manual** mode, confirm:

- detection still opened or updated freshness issues;
- auto-tier issues have `manual-review`;
- auto-tier issues are not assigned to `@Copilot`;
- `issue_only` issues remain human-only.

## 5) Restore Copilot mode

Set the repo back to Copilot mode:

```bash
gh variable set FRESHNESS_EXECUTION_MODE --repo aiappsgbb/awesome-gbb --body copilot
```

Dry-run once:

```bash
gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=true -f execution_mode=repository
```

Then run it live once:

```bash
gh workflow run skill-freshness.yml --repo aiappsgbb/awesome-gbb -f dry_run=false -f execution_mode=repository
```

The workflow uses the assignment PAT (`COPILOT_ASSIGN_PAT`, passed to the
script as `GH_ASSIGN_TOKEN`) for **both** Copilot assignment and Copilot
removal. The default `GITHUB_TOKEN` cannot reliably assign or remove the
Copilot bot, so ownership reconciliation depends on that PAT being present.

In **copilot** mode, confirm:

- auto-tier issues lose `manual-review`;
- auto-tier issues are assigned to `@Copilot`;
- `issue_only` issues are still human-only.

## 6) Failure behavior

If Copilot assignment, bot PR creation, or ownership reconciliation looks
wrong:

1. **Immediately return to manual mode** with the variable command above.
2. Dry-run once, then live-run once in repository mode.
3. Continue triage from the manual queue.

**Never disable detection.** The fallback is “manual review required,” not
“stop checking freshness.”

## 7) Manual queue triage rules

| State | When to use it | Required action |
|---|---|---|
| `salvage` | The issue is still current and existing work can be continued safely | Keep one active path, update the issue with current status, and continue from the freshest valid branch/PR |
| `superseded` | A newer upstream change, issue, or PR has made the older work obsolete | Close or comment with a link to the replacement issue/PR and stop spending time on the stale path |
| `blocked` | The work is still current but cannot proceed yet because of credentials, Azure state, CI, or fixture dependencies | Record the blocker, owner, and unblock condition directly on the issue before pausing it |

Prefer a bare release such as `1.25.3` in `packages[].version`. The detector
also accepts existing `~=1.25.3` and `==1.25.3` entries when comparing the
pinned release with PyPI: an identical release is not drift. This is **not**
range satisfaction; a newer critical SDK patch still requires review even
when a compatible-release install would already accept it. Prerelease
suffixes remain significant, and compound/range/wildcard specifications are
not treated as identical fixed releases.

For an older issue reporting only `~=1.25.3` to `1.25.3`, confirm there are
no other signals before closing it as a false positive. In a consolidated
issue, an independent upstream lookup failure or real version change remains
open even after the same-version noise is removed.

The separate `freshness-tests.yml` PR workflow runs these detector,
issue-lifecycle and runbook-preservation regressions without Azure credentials
or issue writes. It does not change the scheduled detector or required branch
checks.

## 8) Azure evidence reminder

Any refresh that touches Azure paths still needs live evidence before close or
merge:

- link the green `skill-test.yml` / `copilot-cli-matrix` run, **or**
- paste the manual Azure validation output you used.

`pip install` + import smoke is not enough for Azure-connected skills. Manual
mode changes ownership, not the validation bar.

## 9) Manual upstream SHA tracking and incomplete checks

Execution mode controls **issue ownership**, not what gets checked. For a
vendored GitHub upstream whose SHA is maintained by a human, declare
`upstream.sha_tracking: manual` and a non-empty
`upstream.sha_tracking_reason` in its schema-v2 pin. Keep the upstream identity
and last-vendored SHA. Omission means `automatic`, preserving existing pins.
The validator and detector reject invalid policies; neither infers an exception
from repository visibility, an HTTP failure, or a skill name.

A manual SHA check is reported explicitly as **not verified automatically**.
It does not create a recurring refresh issue by itself. PyPI, known-issue,
public-documentation and validation-age checks continue, including existing
package holds. An existing issue such as #356 still needs human reconciliation:
changing a check to manual must not automatically mark earlier work completed.
Do not refresh `last_validated`, package versions or the vendored SHA merely
to change this policy.

Lookup failures are **incomplete detection**, not proof of version drift.
Failed checks remain actionable and human-owned, including in Copilot mode,
and make the detector exit non-zero. Mixed reports retain the severity of
their verified drift and explicitly list failed checks. Documentation 404/410
responses remain link-rot signals; access failures, throttling, server errors
and transport failures require investigation rather than an invented new URL.

Automatic closure requires a discovered, fully checked pin with no remaining
findings. Failed checks, manually tracked SHA checks and absent pins cannot
be closed based on silence. Unreadable or malformed pin files stop discovery
before issue writes. Freshness success is not live Azure validation.
Failed, malformed or explicitly incomplete GitHub issue searches block the
corresponding upsert/closure; they are never treated as an empty result that
permits creating a duplicate issue.

Reports and issue bodies describe the requested ownership policy, not an
assignment that has already succeeded. Actual assignment/removal errors remain
workflow failures. Keep human assignees and the manual-mode fallback intact.

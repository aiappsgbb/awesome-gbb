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

## 8) Azure evidence reminder

Any refresh that touches Azure paths still needs live evidence before close or
merge:

- link the green `skill-test.yml` / `copilot-cli-matrix` run, **or**
- paste the manual Azure validation output you used.

`pip install` + import smoke is not enough for Azure-connected skills. Manual
mode changes ownership, not the validation bar.

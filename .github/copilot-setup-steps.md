# Copilot coding agent — setup steps

This file is auto-read by the GitHub Copilot coding agent before it
starts work on an issue assigned to `@Copilot` in this repo.

## When you pick up a freshness refresh issue

Issues labeled `freshness` + `automation` are produced by the weekly
`Skill freshness` workflow. Each one targets exactly one skill and
embeds the machine-runnable Verification Checklist.

### What to do

1. **Read the issue body completely.** It contains:
   - The drift signal (SHA / package / closed upstream issue / link rot / age)
   - The exact value to write to the pin file front-matter
   - The Verification Checklist (a bash script)
   - The Acceptance Criteria

2. **Open the pin file** at `skills/<skill>/references/upstream-pin.md`.
   Its YAML front-matter is the source of truth. The `validation.script`
   field has the same script as the issue body — they're kept in sync.

3. **Run the validation script.** Use the sandbox's `bash`, `python`,
   and `pip` — those are all you need. **Never** use `az` or other
   cloud CLIs; `automation_tier: auto` skills are designed not to
   require them. If validation requires credentials, the issue would
   have been opened as `issue_only` (no automation_tier=auto label) and
   you should NOT have picked it up.

4. **On success**: edit the pin file's front-matter:
   - `upstream.pinned_sha` → new SHA (for SHA-drift issues)
   - `packages[*].version` → new version (for PyPI-drift issues)
   - `known_issues[*].status` → `closed_upstream_fixed` (for issue-closure events)
   - `last_validated` → today (ISO 8601, e.g. `2026-05-15`)
   - `validated_by` → `copilot-bot`

5. **Bump SKILL.md `metadata.version` PATCH** (X.Y.Z → X.Y.(Z+1)).
   Touch nothing else in SKILL.md — the YAML frontmatter line is the
   only allowed edit unless the issue explicitly tells you to use
   `[skill-rewrite]`.

6. **Open the PR**. Title: `chore(<skill>): re-pin upstream → <short-sha>`
   or similar conventional message. Include `Co-authored-by: Copilot
   <223556219+Copilot@users.noreply.github.com>`.

7. **On failure**: comment on the issue with the failure output and
   STOP. Do NOT open a PR. A human will triage.

## Hard rules (per AGENTS.md § 4)

These are enforced by `automation-pr-gate.yml` — your PR will be
rejected if you violate them.

| Rule | How to comply |
|------|---------------|
| **One skill per PR** | Touch only `skills/<one-skill>/`. The issue scope IS the PR scope. |
| **No reference data edits** | Never modify `references/data-realism/**`. Those files are canon per AGENTS.md § 2.2. |
| **No SKILL.md body changes** | Edit only the YAML frontmatter unless the issue says `[skill-rewrite]`. |
| **PATCH bumps only** | Pin refreshes are PATCH (Z increments by 1). |
| **Description ≤ 1024 chars** | If a description gets long, find content to drop — don't push the ceiling. |

### ⚠️ No global search-and-replace across files

**Do NOT** run `sed -i 's/1.3.0/1.4.0/g'` (or the IDE equivalent) across
the repo. SKILL.md body and pin-file body often contain **historical
proof-of-validation text** like `verified against agent-framework 1.3.0`
or `Initial wrapper. Pinned to AGT 3.6.0 + MAF 1.3.0`. Those are
deliberate historical records, not values to refresh.

Only edit the explicit fields the issue lists:
- `upstream.pinned_sha` (for SHA drift)
- `packages[*].version` AND its sibling `validation.script` default
  (for package drift; the script needs the new default for re-validation)
- `known_issues[*].status` (for closure events)
- `last_validated`, `validated_by`, `known_issues_count`
- `metadata.version` in SKILL.md (PATCH bump only)

Everything else — including version refs in SKILL.md body and pin-file
prose sections — stays. If body refreshes are warranted, the issue
template will explicitly include `[skill-rewrite]` in the Acceptance
Criteria.

## Opt-in tags (only for issues that explicitly authorize them)

If the issue body tells you to include one of these tags in the commit
message, do so — the gate uses them to unlock specific kinds of edit:

- `[skill-rewrite]` — body edits to SKILL.md (e.g. removing a workaround
  note after upstream fixed the bug)
- `[multi-skill]` — cross-cutting edit (rare; usually only for
  AGENTS.md / README / workflow changes that touch multiple skills)
- `[scrub-canon]` — edit to `references/data-realism/**` (extremely
  rare; only after a citation update; ALWAYS requires human reviewer)

If the issue does NOT mention these tags, **do not use them**.

## Reading list before your first task

1. [`AGENTS.md`](../AGENTS.md) — read § 2 (invariants), § 4 (mass-edit
   safety), § 5 (versioning), § 9 (freshness lifecycle).
2. The pin file you're about to update — read it end-to-end.
3. The SKILL.md frontmatter (not the body unless `[skill-rewrite]`).

## Tools available in your sandbox

- `git` — to read history, capture commit subjects
- `python3` + `pip` — for PyPI installs and import-smoke tests
- `node` + `npm` — for any JS-side smoke tests
- `curl` + `gh` — for link checks and (optional) GitHub API queries
- Standard Unix utils (`grep`, `sed`, `yq`, `jq`)

Tools **not** available (by design):
- `az` / Azure CLI
- `azd`
- Foundry SDK with live project access
- Any tool requiring secret credentials

If your task seems to need any of these, the issue was mis-labeled —
stop and comment on it.

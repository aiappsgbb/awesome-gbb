# Copilot coding agent — setup steps

This file is auto-read by the GitHub Copilot coding agent before it
starts work on an issue assigned to `@Copilot` in this repo.

## When you pick up a freshness refresh issue

Issues labeled `freshness` + `automation` are produced by the weekly
`Skill freshness` workflow. Each one targets exactly one skill and
consolidates ALL drift signals with impact classification
(🔴 CRITICAL, 🟠 HIGH, 🟡 MEDIUM, 🟢 LOW). The highest-impact signal
determines the issue label (`impact:critical`, `impact:high`, etc.).

### What to do

1. **Read the issue body completely.** It contains:
   - All drift signals for this skill, ordered by impact (highest first)
   - Each signal's classification (CRITICAL / HIGH / MEDIUM / LOW)
   - The exact fields to update in the pin file front-matter

2. **Open the pin file** at `skills/<skill>/references/upstream-pin.md`.
   Its YAML front-matter is the source of truth. The `validation.script`
   field contains the runnable bash script you'll execute to verify the
   refresh.

3. **Run the validation script.** Use the sandbox's `bash`, `python`,
   and `pip` — those are all you need. **Never** use `az` or other
   cloud CLIs; `automation_tier: auto` skills are designed to validate
   with pip + Python only (no Azure credentials). If the pin file's
   `validation.requires` includes `azure_subscription` or
   `foundry_project`, the issue would have been opened as `issue_only`
   and you should NOT have picked it up.

   ⚠️ The `pin-validation.yml` CI job will **re-run your
   validation.script** on the PR runner and assert every
   `expected_output` substring is present. If you skip the validation
   locally and the CI run fails, your PR is rejected. There is no
   "trust me, I tested it" path.

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

### Impact-aware validation

The issue title contains the impact level. Adjust your approach accordingly:

| Impact | What to do |
|--------|-----------|
| 🟢 LOW | Patch bump or link rot — auto-covered by `~=` cap. Bump pin, validate, PR. |
| 🟡 MEDIUM | MINOR bump, SHA drift, or validation age. Bump pin, validate, PR. For MINOR bumps, run `python scripts/validate-skills.py` to check for deprecated API patterns in SKILL.md code blocks. If deprecated APIs found → include `[skill-rewrite]` in commit message and fix the code samples. |
| 🟠 HIGH | Upstream KI closed — workaround removal opportunity. After bumping pin, run `python scripts/validate-skills.py`. If the workaround can be removed, include `[skill-rewrite]` in commit message. |
| 🔴 CRITICAL | MAJOR bump. Expect breaking changes. If `validate-skills.py` reports deprecated APIs and you can't fix them confidently → comment on the issue with findings and STOP. Do NOT open a broken PR. |

For HIGH and CRITICAL issues, the `validate-skills.py` script scans
SKILL.md code blocks for `DEPRECATED_API_PATTERNS`. If it flags any
stale imports or function calls, those code samples need updating —
which requires `[skill-rewrite]` opt-in in the commit message.

## Hard rules (per AGENTS.md § 4)

These are enforced by `automation-pr-gate.yml` + `pin-validation.yml`
on every PR — your PR will be rejected if you violate them.

| Rule | How to comply |
|------|---------------|
| **One skill per PR** | Touch only `skills/<one-skill>/`. The issue scope IS the PR scope. |
| **No reference data edits** | Never modify `references/data-realism/**`. Those files are canon per AGENTS.md § 2.2. |
| **No SKILL.md body changes** | Edit only the YAML frontmatter unless the issue says `[skill-rewrite]`. |
| **PATCH bumps only** | Pin refreshes are PATCH (Z increments by 1). |
| **Description ≤ 1024 chars** | If a description gets long, find content to drop — don't push the ceiling. |
| **Validation actually runs** | `pin-validation.yml` re-executes your `validation.script` on the PR runner and asserts every `expected_output` substring. **You cannot fake "tested OK".** |
| **Pin/cap policy on pip** | Every pip install in `validation.script` MUST use `~=X.Y.Z` (compatible release with implicit cap) — never bare `==`, never bare `>=`, never unpinned. Pre-releases (a/b/rc/dev) are the only `==` exception. |

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
4. [`AGENTS.md` § 2.7](../AGENTS.md) — testing tiers (T0–T3). Know which
   tier your change requires.

## 🔴 Reminder for human reviewers merging coding-agent PRs

The coding agent runs `validation.script` (pip + import). This is T1.
**It is NOT a live Azure test (T3).** Per AGENTS.md § 2.9, if the
refreshed skill connects to Azure (model calls, credential chains,
Realtime WebSocket, ACA deploys), a human MUST verify with real Azure
API calls before merging. The coding agent cannot do this — its sandbox
has no Azure credentials.

**Do not merge a pin-refresh PR for an Azure-connected skill unless the
PR description or a review comment includes evidence of live Azure
testing.** "CI lint passed" and "validation.script passed" are necessary
but NOT sufficient.

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

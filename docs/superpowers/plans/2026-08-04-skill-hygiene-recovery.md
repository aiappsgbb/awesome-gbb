# Skill Hygiene Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the existing freshness backlog, review all 35 skill contracts, and land current critical/high upgrades with the repository's required Azure evidence.

**Architecture:** The round is coordinated by one tracking issue but executed through one-skill worktree sessions and one-skill PRs. Existing bot PRs are evaluated once and either salvaged, superseded, or blocked; major upgrades receive a fresh skill-specific design and implementation plan after authoritative upstream research.

**Tech Stack:** GitHub issues/PRs, Python freshness and validation scripts, `unittest`, PyPI/GitHub upstream metadata, Microsoft Learn and SDK source, Copilot-CLI Azure E2E matrix, static documentation generator.

---

## Program boundaries

- The manual-mode infrastructure plan must land first:
  `docs/superpowers/plans/2026-08-04-manual-freshness-mode.md`.
- Never edit two skill bodies in one PR.
- Never repair a superseded bot branch indefinitely; recreate current work from
  `main`.
- Never merge an Azure-connected change without T3 evidence.
- Major upstream changes require a skill-specific approved design and plan
  before implementation.
- Keep no more than two independent skill PRs active.

---

### Task 1: Create the authoritative baseline and tracker

**Files:**
- Read: all `skills/*/SKILL.md`
- Read: all `skills/*/references/upstream-pin.md`
- Create outside repo: `/tmp/awesome-gbb-freshness-2026-08-04.md`
- Create on GitHub: one hygiene tracking issue

- [ ] **Step 1: Refresh local main references**

Run:

```bash
git fetch origin main --prune
git status --short
```

Expected: fetch succeeds and the worktree has no unexpected changes.

- [ ] **Step 2: Generate the current detector report**

Run:

```bash
GH_TOKEN="$(gh auth token)" GH_REPO=aiappsgbb/awesome-gbb \
python3 scripts/check-freshness.py \
  --upsert-issues \
  --consolidated \
  --execution-mode manual \
  --labels freshness,automation \
  --dry-run \
  --output /tmp/awesome-gbb-freshness-2026-08-04.md \
  --print-report
```

Expected baseline from 2026-08-04: 25 drift events across 31 pinned skills,
consolidated into 4 critical, 7 high, and 14 medium skill issues. If counts
change, the new report is authoritative and the tracker records the delta.

- [ ] **Step 3: Inventory all open bot PRs**

Run:

```bash
gh pr list --repo aiappsgbb/awesome-gbb --state open --limit 100 \
  --json number,title,author,isDraft,mergeable,statusCheckRollup,updatedAt,url \
  --jq '.[] | select(.author.login=="app/copilot-swe-agent") |
    [.number,.mergeable,.updatedAt,.title,.url] | @tsv' \
  | sort -n > /tmp/awesome-gbb-bot-prs.tsv
wc -l /tmp/awesome-gbb-bot-prs.tsv
```

Expected starting count: `16`.

- [ ] **Step 4: Create the hygiene epic**

Use the session's `create_issue` tool with:

- title: `August 2026 manual skill hygiene and upgrade round`
- labels: `freshness`, `triage`
- body: link the approved design and both implementation plans; paste the
  current detector summary; add one checklist row for each directory returned
  by `find skills -mindepth 1 -maxdepth 1 -type d | sort`; include columns for
  issue, PR, impact, upstream delta, review depth, disposition, T0/T1/T2/T3,
  owner, and next action.

The body must state the exit criteria from the approved design verbatim.

- [ ] **Step 5: Record the tracker number in the working session**

Do not edit skill files. Store the issue number in the session todo state and
use it in every subsequent PR body.

---

### Task 2: Triage all 16 bot-authored PRs once

**Files:**
- Read only: PR diffs and current issue bodies
- GitHub mutations: comments, close, update branch, or merge

- [ ] **Step 1: Inspect scope contamination first**

Review:

```bash
gh pr diff 394 --repo aiappsgbb/awesome-gbb --name-only
gh pr diff 397 --repo aiappsgbb/awesome-gbb --name-only
gh pr diff 425 --repo aiappsgbb/awesome-gbb --name-only
```

Expected starting observations:

- #394 includes an out-of-scope file named `=4.0,`;
- #397 is an empty WIP PR;
- #425 includes `.upstream-pin-smoke/gbb-humanizer/repo`.

Unless the branch has changed, classify all three as `superseded`, comment with
the scope violation, and close them. Recreate any still-valid work from clean
`main`.

- [ ] **Step 2: Compare likely superseded version PRs with current issues**

Review PR/issue pairs:

| PR | Skill | Current issue |
|---:|---|---:|
| #381 | `foundry-agt` | #377 |
| #383 | `foundry-caphost-lifecycle` | #379 |
| #389 | `foundry-mcp-aca` | #384 |
| #391 | `foundry-memory` | #386 |
| #416 | `foundry-doc-vision-speech` | #414 |
| #417 | `foundry-hosted-agents` | #415 |
| #421 | `foundry-teams-bot` | #419 |
| #423 | `foundry-toolbox` | #420 |
| #427 | `foundry-skill-catalog` | #418 |

For every pair run:

```bash
while read -r pr issue; do
  gh pr view "$pr" --repo aiappsgbb/awesome-gbb \
    --json files,commits,statusCheckRollup,updatedAt
  gh issue view "$issue" --repo aiappsgbb/awesome-gbb \
    --json body,labels,updatedAt
done <<'EOF'
381 377
383 379
389 384
391 386
416 414
417 415
421 419
423 420
427 418
EOF
```

Compare every proposed pin with the latest values in the issue body. If any
target is behind, close as `superseded`; do not patch the bot branch.

- [ ] **Step 3: Review current-but-failing candidates**

Inspect:

| PR | Skill | Starting concern |
|---:|---|---|
| #393 | `foundry-observability` | dependent `foundry-cost-monitoring` fixture failed |
| #426 | `ghcp-hosted-agents` | unit and live fixture failed |

Classify as `salvage` only if the pin targets still match the current issue,
the diff is limited to the skill contract, and the failure has a bounded fix.
Otherwise close and recreate.

- [ ] **Step 4: Revalidate current green candidates**

Inspect #430 (`foundry-prompt-agents`) and #431 (`foundry-routines`). Both
target `azure-ai-projects` 2.4.0 and started green on 2026-08-04.

Run:

```bash
gh pr update-branch 430 --repo aiappsgbb/awesome-gbb
gh pr update-branch 431 --repo aiappsgbb/awesome-gbb
```

Expected: branches update or report already current; required and matrix checks
run against current `main`.

- [ ] **Step 5: Update the epic**

Record exactly one disposition for each starting PR:

`381, 383, 389, 391, 393, 394, 397, 416, 417, 421, 423, 425, 426, 427, 430, 431`.

The count of recorded dispositions must be 16 before starting new upgrade PRs.

---

### Task 3: Salvage prompt agents and routines in dependency order

**Files:**
- Review: `skills/foundry-prompt-agents/**` from PR #430
- Review: `skills/foundry-routines/**` from PR #431

- [ ] **Step 1: Review #430 against authoritative SDK evidence**

Verify `azure-ai-projects` 2.4.0 release notes and installed imports used by
`foundry-prompt-agents`. Confirm the PR changes only the pin contract and PATCH
skill version.

- [ ] **Step 2: Require fresh checks**

Wait for:

- `validate`
- `gate`
- `validate-pins`
- `unit-tests`
- `catalog-lint`
- `copilot-cli-matrix (foundry-prompt-agents)`
- `copilot-cli-matrix (foundry-evals)`
- `copilot-cli-matrix (foundry-routines)`

Expected: all required fanout checks pass on the updated branch.

- [ ] **Step 3: Merge #430**

Run:

```bash
gh pr merge 430 --repo aiappsgbb/awesome-gbb --squash --delete-branch
```

Expected: PR merges. If branch protection blocks the merge, resolve the named
missing review/check; never bypass.

- [ ] **Step 4: Update and review #431 after #430 lands**

Run `gh pr update-branch 431`, verify its diff and live routines fixture, then
merge with the same branch-protection rule.

- [ ] **Step 5: Run a detector dry run**

Expected: `foundry-prompt-agents` and `foundry-routines` no longer appear if no
new upstream drift arrived. If they remain, reopen the review instead of
closing issues manually.

---

### Task 4: Complete the 35-skill contract review

**Files:**
- Read: every `skills/*/SKILL.md`
- Read: pin or `last_validated.yaml` for every skill
- Read: `.github/skill-deps.yml`
- Update: hygiene epic only

- [ ] **Step 1: Run catalog-wide structural checks**

Run:

```bash
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 scripts/build-site.py \
  --out /tmp/awesome-gbb-site-validation \
  --validate
```

Expected: all commands exit `0`.

- [ ] **Step 2: Review each skill contract**

For each skill, record:

1. fixed frontmatter shape, SemVer, and description length;
2. accurate `USE FOR` / `DO NOT USE FOR` boundary;
3. current upstream links and known issues;
4. valid cross-skill anchors and dependency edges;
5. reference-file SSOT compliance;
6. `azd` deployment compliance when infrastructure is involved;
7. fixture or manual-Azure exception coverage;
8. generated docs presence.

Mark review depth `deep` for all critical/high skills and `contract` for all
others.

- [ ] **Step 3: Verify the review count**

Run:

```bash
find skills -mindepth 1 -maxdepth 1 -type d | wc -l
find skills -path '*/references/upstream-pin.md' | wc -l
find skills -path '*/references/last_validated.yaml' | wc -l
```

Expected: `35`, `31`, and `4`.

The epic must contain 35 reviewed rows before the round can close.

---

### Task 5: Research and plan the critical wave

**Files:**
- Read: issue #420 and `skills/foundry-toolbox/**`
- Read: issue #415 and `skills/foundry-hosted-agents/**`
- Read: issue #384 and `skills/foundry-mcp-aca/**`
- Read: issue #392 and `skills/foundry-voice-live/**`
- Create: one approved design and implementation plan per skill when its
  documented contract changes

- [ ] **Step 1: Rebase `foundry-toolbox` research**

Start from the existing GA design/plan, but re-audit MCP 2.0,
`agent-framework` 1.13.0, `azure-ai-projects` 2.4.0, and the current
`agent-framework-foundry-hosting` beta. Do not reuse old signatures without
installing and inspecting the new packages.

- [ ] **Step 2: Audit `foundry-hosted-agents`**

Verify the same shared runtime packages plus
`agent-framework-foundry` 1.10.4. Land this skill before its dependent
`foundry-mcp-aca` and `ghcp-hosted-agents` fanout.

- [ ] **Step 3: Audit `foundry-mcp-aca`**

Treat MCP 2.0 and `azure-mgmt-appcontainers` 5.0.0 as independent major
migrations. Also verify `azure-cosmos` 4.16.3. A passing import smoke is not
evidence that the server, management client, Bicep, or ACA fixture contract is
unchanged.

- [ ] **Step 4: Resolve the Voice Live cap decision**

In a disposable virtual environment run:

```bash
python3 -m venv /tmp/voice-live-compat
/tmp/voice-live-compat/bin/python -m pip install -U pip
/tmp/voice-live-compat/bin/pip install "fastrtc==0.0.34" "gradio==6.22.0"
```

If dependency resolution still fails because FastRTC requires Gradio below 6,
retain an evidence-backed hold and track the upstream release that can lift it.
If it succeeds, design and live-test the Gradio 6 migration. Independently
review the OpenAI 2.52.0 minor update.

- [ ] **Step 5: Produce four skill-specific plans**

Each plan must name exact source signatures, files, tests, fixture changes, pin
changes, version bump, docs generation, and live-Azure proof. Do not begin
implementation until its design is approved.

---

### Task 6: Execute critical upgrades one skill per PR

**Files:**
- Modify only the current skill, directly related catalog prose, and generated
  docs in each PR

- [ ] **Step 1: Execute `foundry-toolbox`**

Use its approved refreshed plan. Run targeted red/green tests, pin validation,
catalog validation, docs generation, and live fixture. Merge before beginning
the hosted-agent dependency chain if the changes affect shared contracts.

- [ ] **Step 2: Execute `foundry-hosted-agents`**

Require live hosted deployment/invoke evidence and fanout for
`foundry-mcp-aca` and `ghcp-hosted-agents`.

- [ ] **Step 3: Execute `foundry-mcp-aca`**

Require live ACA deploy, MCP invoke, and teardown evidence. Do not accept a
pin-only PR for either major dependency.

- [ ] **Step 4: Execute the Voice Live decision**

Either merge the verified migration or merge the verified cap/known-issue
refresh. In both cases the live WSS/API surface must be proven.

- [ ] **Step 5: Run the detector**

Expected: zero unexplained critical items. A deliberate cap may remain only
with an open known issue, reproduction evidence, owner, and unblock condition.

---

### Task 7: Execute the high wave

**Files:**
- One skill per PR:
  `foundry-agt`, `foundry-doc-vision-speech`, `foundry-skill-catalog`,
  `foundry-teams-bot`, `azure-backup-readiness`

- [ ] **Step 1: Audit current package/source contracts**

Read the current freshness issue, upstream changelog, installed package source,
canonical references, and fixture before editing. Shared Agent Framework
research may be linked, not copied.

- [ ] **Step 2: Implement and validate each skill independently**

For each PR run:

```bash
python3 scripts/run-pin-validation.py --base origin/main
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 scripts/build-site.py --out docs/
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
git diff --check
```

Expected: all local commands exit `0`; the PR's change-gated live matrix passes.

- [ ] **Step 3: Use correct commit opt-ins**

Pin/frontmatter-only refreshes use a normal PATCH commit. Any body, canonical
reference, or fixture contract change includes `[skill-rewrite]`. Do not use
`[multi-skill]` in a one-skill refresh.

- [ ] **Step 4: Treat backup as a clean recreation**

PR #397 started empty. Recreate `azure-backup-readiness` from current `main`,
run its unit tests, and require the registered live Azure fixture.

- [ ] **Step 5: Re-run freshness**

Expected: no unexplained high items. Any block includes evidence, owner, and a
date/release condition.

---

### Task 8: Disposition medium and internal-IP work

**Files:**
- Update: hygiene epic
- Optional: one-skill PRs that already meet the low-risk rule

- [ ] **Step 1: Review all medium items**

For every medium skill choose one:

- merge now: current, low risk, complete validation;
- defer to named release/version;
- block on named upstream issue or Azure capability;
- close as detector/query noise with evidence.

- [ ] **Step 2: Review internal-IP validation dates**

Check:

- `auto-demo-producer`
- `azure-tenant-isolation`
- `gbb-pptx`
- `ip-catalog`

Update validation metadata only when the documented manual validation was
actually performed.

- [ ] **Step 3: Preserve manual-only Azure exceptions**

Do not auto-run `citadel-hub-deploy` or `foundry-vnet-deploy`. If either is
changed, attach manual live evidence per AGENTS.md section 2.9.

---

### Task 9: Close the round

**Files:**
- Update: hygiene epic
- Verify: repo and GitHub state

- [ ] **Step 1: Run final local validation**

Run:

```bash
python3 scripts/validate-skills.py
python3 scripts/build-plugins.py --check
python3 scripts/build-site.py --validate
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
```

Expected: all commands exit `0`.

- [ ] **Step 2: Generate the final freshness report**

Run the detector in manual dry-run mode. Expected: no unexplained critical or
high drift.

- [ ] **Step 3: Verify PR hygiene**

Run:

```bash
gh pr list --repo aiappsgbb/awesome-gbb --state open --limit 100 \
  --json number,author,title \
  --jq '.[] | select(.author.login=="app/copilot-swe-agent") |
    [.number,.title] | @tsv'
```

Expected: no stale bot PRs from the starting set.

- [ ] **Step 4: Verify all exit criteria**

The epic must show:

- 35 reviewed skills;
- 16 starting PR dispositions;
- every critical/high item merged or evidence-backed blocked/capped;
- every medium item dispositioned;
- T3 evidence for every merged Azure change;
- manual-mode scheduled run proven;
- docs current.

- [ ] **Step 5: Close the epic**

Post the final detector report and links to merged PRs, then close the hygiene
epic. Keep the repository in manual mode until the organization explicitly
restores GHCP and the rollback procedure succeeds.

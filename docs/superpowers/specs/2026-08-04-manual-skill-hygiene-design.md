# Manual Skill Hygiene and Upgrade Round - Design

- **Date:** 2026-08-04
- **Status:** Approved (design phase)
- **Repository:** `awesome-gbb`
- **Branch:** `unsafecode-manual-skill-hygiene`
- **Operating model:** risk-tiered manual recovery
- **PR shape:** one infrastructure PR, then one skill per PR

---

## 1. Problem

The catalog's freshness detector is running, but assignment is no longer a
reliable execution mechanism. On 2026-08-04:

- the detector found 25 drift events across 31 pinned skills;
- 4 skills were critical, 7 high, and 14 medium;
- 16 pull requests authored by `app/copilot-swe-agent` were still open;
- several older PRs were green but already superseded by newer releases;
- the Copilot bot remained assignable and the 2026-08-03 freshness workflow
  succeeded, so workflow health did not prove that assigned work would run;
- the current dry-run classified `citadel-hub-deploy` as medium while its
  issue still showed the high-impact label from the preceding scheduled run;
  exact label replacement already exists, but needs regression coverage so the
  next live upsert is guaranteed to reconcile that state.

The catalog needs a bounded manual recovery round that reduces current risk,
cleans up stale automation output, and leaves a reversible fallback for future
periods when GitHub Copilot coding-agent execution is unavailable.

---

## 2. Goals and non-goals

### Goals

- Review all 35 skills at contract level.
- Deep-review every current critical and high skill against authoritative
  upstream sources.
- Reconcile all 16 open bot-authored PRs as `salvage`, `superseded`, or
  `blocked`.
- Execute critical and high upgrades in dependency-aware waves.
- Require live Azure evidence for every changed Azure-connected contract.
- Add a reversible manual execution mode without disabling freshness
  detection.
- Prove exact impact-label reconciliation and reconcile stale bot ownership.
- Leave every medium item with a reviewed disposition and next action.
- Finish with no unexplained critical/high drift and no stale bot PRs.

### Non-goals

- No mega-PR containing multiple skill bodies.
- No deep source audit of every medium or internal-IP skill.
- No normalization of canonical reference data.
- No speculative upgrades that cannot be verified against a real upstream
  release and, where applicable, live Azure.
- No deletion of the Copilot assignment path; it must remain restorable.
- No new skill creation during this round.

---

## 3. Operating model

The round has four phases.

### Phase 0 - Stabilize intake

Land one infrastructure PR that introduces
`FRESHNESS_EXECUTION_MODE=manual|copilot`, with `manual` as the safe fallback.
The scheduled workflow continues to detect drift and upsert issues in both
modes.

In `manual` mode the workflow:

- does not assign new work to `copilot-swe-agent`;
- removes stale Copilot ownership from open freshness issues;
- applies a `manual-review` label;
- preserves exact `impact:*` label replacement so each issue has exactly one
  current impact label, with a regression test for impact changes;
- still uploads the freshness report artifact.

In `copilot` mode the current assignment behavior resumes and the
`manual-review` label is removed. A workflow-dispatch override supports a
one-run dry run without changing the repository variable.

Document operation in `docs/maintenance/manual-skill-freshness.md`, including
the dry-run command, mode switch, queue generation, PR disposition rules,
validation evidence requirements, and restoration procedure.

### Phase 1 - Reconcile the queue

Review every open bot-authored PR against the 2026-08-04 detector output and
current upstream releases.

| Disposition | Required condition | Action |
|---|---|---|
| `salvage` | Current versions, scoped diff, correct version bump, and repairable validation state | Rebase, re-run all required checks, review, and merge |
| `superseded` | Newer upstream drift or a replacement PR makes the branch obsolete | Close with a link to the current issue or replacement PR |
| `blocked` | Current work is valid but cannot pass because of a confirmed upstream, Azure, or fixture dependency | Record evidence, owner, and unblock condition |

Old green checks are not sufficient. Every salvage candidate must be rebased,
compared with current drift, and revalidated.

The first salvage candidates are:

1. `foundry-prompt-agents` PR #430;
2. dependent `foundry-routines` PR #431.

Both were current and green on 2026-08-04, but still require current review and
live fixture evidence.

### Phase 2 - Execute critical and high waves

Keep at most two independent skill PRs active. Serialize dependency chains.

#### Wave 1 - Critical runtime contracts

1. `foundry-toolbox`
2. `foundry-hosted-agents`
3. `foundry-mcp-aca`
4. `foundry-voice-live` as an independent compatibility decision

The first three share MCP 2.0, Agent Framework, and Foundry SDK drift.
`foundry-hosted-agents` lands before its dependent ACA and GHCP-hosted fixture
fanout. Shared release research may be reused, but each skill keeps its own PR,
evidence, and version decision.

`foundry-voice-live` must explicitly choose between upgrading and retaining a
documented compatibility cap because Gradio crossed a major boundary. A cap is
acceptable only when backed by a reproduced incompatibility and an upstream
tracking link.

#### Wave 2 - High upgrades

1. `foundry-agt`
2. `foundry-doc-vision-speech`
3. `foundry-skill-catalog`
4. `foundry-teams-bot`
5. `azure-backup-readiness`

These skills are independent for PR purposes. Shared upstream release notes
should be linked rather than copied into each PR.

### Phase 3 - Review medium and internal-IP skills

Contract-review all remaining skills. Merge a medium upgrade in this round
only when it is already current, low risk, and has complete validation
evidence. Otherwise record its blocker or next release target and defer it.

The four unpinned internal-IP skills receive the same contract review, using
their `last_validated.yaml` or documented manual-validation contract instead
of an upstream pin.

---

## 4. Per-skill review contract

Every skill receives the following checks:

1. Frontmatter has the fixed shape, correct name, valid SemVer, and a
   description no longer than 1024 characters.
2. `USE FOR` and `DO NOT USE FOR` triggers still match the skill boundary.
3. Upstream links resolve and known-issue states are current.
4. Cross-skill links, section anchors, and `.github/skill-deps.yml` edges are
   accurate.
5. Reference-file headers resolve to real SKILL.md headings and canonical code
   is not duplicated inline.
6. Azure deployment guidance uses `azd` unless an existing documented
   exception applies.
7. Azure-connected skills have a registered fixture or documented manual-test
   exception.
8. Generated documentation reflects the source skill.

Critical and high skills additionally require an adversarial source review:

- read release notes and migration guidance;
- verify imports, classes, constructors, methods, parameters, defaults, and
  environment variables against authoritative source or SDK code;
- inspect every canonical reference file affected by the release;
- validate workarounds and remove them only when the upstream fix is proven;
- record compatibility implications for every major release;
- update the fixture when the consumer contract changes.

No critical or high item may be resolved by changing only a pin when the
documented consumer contract has changed.

---

## 5. Validation and failure handling

A skill change is complete only when:

1. T0 catalog validation passes.
2. The pin validation script and required import smoke pass.
3. Changed Azure behavior is exercised through the registered Copilot-CLI
   fixture.
4. `citadel-hub-deploy` and `foundry-vnet-deploy` include manual live-Azure
   evidence when changed.
5. Dependency fanout passes.
6. The static docs site is rebuilt and committed.
7. The PR states the upstream sources, version decision, validation evidence,
   and any remaining limitation.

Failures use four classifications:

| Class | Treatment |
|---|---|
| Skill regression | Fix the skill or reference implementation before merge |
| Upstream incompatibility | Add an evidence-backed cap or block the issue |
| Fixture or CI defect | Fix the test contract separately; do not weaken assertions |
| Environmental transient | Use the existing bounded retry policy |

Only environmental transients are retried automatically. Broad catches,
silent fallbacks, and success-shaped defaults are forbidden.

---

## 6. Tracking and ownership

Create one hygiene epic with one row per skill and these fields:

- skill;
- current freshness issue;
- open PR;
- current impact;
- upstream deltas;
- review depth (`contract` or `deep`);
- disposition;
- T0, T1, T2, and T3 state;
- owner;
- next action or blocker.

The epic is coordination only. Individual skill issues and one-skill PRs remain
the executable units. Two independent PRs may run in parallel; dependency
chains remain serial.

---

## 7. Exit criteria

The round is complete when:

- all 35 skills have a recorded review;
- all 16 starting bot PRs are merged, superseded, or explicitly blocked;
- every current critical/high drift is merged or capped with evidence, an
  owner, and an unblock condition;
- every medium item has a reviewed disposition;
- each open freshness issue has exactly one current impact label;
- no issue implies active Copilot ownership while manual mode is enabled;
- all merged Azure changes include live evidence;
- generated docs are current;
- the freshness detector has been run once in dry-run mode and once on
  schedule in manual mode;
- the final detector report contains no unexplained critical/high drift.

---

## 8. Rollback

Manual mode is operational state, not a permanent fork of the workflow. To
restore autonomous assignment:

1. set `FRESHNESS_EXECUTION_MODE=copilot`;
2. run the workflow in dry-run mode and verify the intended queue;
3. run one live dispatch;
4. confirm Copilot assignment succeeds on an auto-tier issue;
5. remove `manual-review` only through the workflow's reconciliation path.

If assignment fails, return the variable to `manual`; detection and issue
updates continue without losing backlog state.

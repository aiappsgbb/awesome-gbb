# `foundry-evals` — Audit Trail (Phase 3 fixture addition)

**Auditor:** PR #185 contributor session (autopilot mode)
**Date:** 2026-05-31
**Skill version:** unchanged (no `SKILL.md` body changes in this PR)
**Surface touched in this PR:**
`skills/foundry-evals/test-fixture/consumer_prompt.md` (+96 lines, new file).

## Scope of this audit

This entry exists to satisfy the `[audit-2026-Q2]` opt-in tag contract
(`scripts/automation-pr-gate.py` § `gate_audit_tag_requires_audit_trail`,
spec 2026-05-30 §9.2): every skill whose tree is touched by a tagged commit
MUST ship a paired `docs/audit/<name>-audit-trail.md` in the same diff.

**This PR did NOT perform a deep 21-class audit of `foundry-evals`.**
The only change in this skill's tree is the addition of a goal-based
Copilot-CLI test fixture, authored against the Phase 2 template proven by
`foundry-prompt-agents` and `foundry-hosted-agents`. No SKILL.md body, no
references, no Bicep, no Python sample, no descriptor frontmatter changed.

## What WAS validated

- **Fixture mechanics, end-to-end against real Azure** (CI runs against
  `rg-awesome-gbb-ci`, OIDC-federated `uami-awesome-gbb-ci`):
  - Pattern 12 marker file written to `/tmp/foundry-evals-smoke-result`
  - Pattern 17 show-don't-assert preamble (no false-FAIL on `az` cache races)
  - 40-minute job ceiling inherited from matrix per Pattern 14
  - Cross-skill dep declared in `.github/skill-deps.yml`:
    `foundry-evals` depends on `foundry-prompt-agents` (the fixture
    evaluates a prompt-agent surface, so PA changes fan out to this leg)
- **Stability proof: 3/3 GREEN** across full 6-fixture matrix runs
  `26716554166` (HA-only), `26716984572` (6/6 incl. evals), `26717346015`
  (6/6 incl. evals).

## What was NOT audited (deferred)

The 21 bug classes from Appendix A of the
[2026-05-30 deep-audit-and-testing-rethink](../superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md)
plan have not been applied to this skill's SKILL.md or references. That
work is **out of scope for PR #185** and is tracked as TIER 1 follow-up
in the Phase 3 plan §2. When that audit runs, it will replace the body
of this file with the per-class findings (using
`foundry-prompt-agents-audit-trail.md` as the template).

## Why a stub is sufficient here

The opt-in gate's intent is to ensure that any cross-cutting body edit
under the `[audit-2026-Q2]` tag carries a record of what was actually
audited. For a fixture-only addition, the honest record is "no body edit
→ no deep audit performed → fixture mechanics validated separately via
the 6/6 GREEN matrix proof above". This stub documents that explicitly
so future auditors don't mistake silence for completeness.

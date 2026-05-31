# `foundry-memory` — Audit Trail (Phase 3 fixture addition)

**Auditor:** PR #185 contributor session (autopilot mode)
**Date:** 2026-05-31
**Skill version:** unchanged (no `SKILL.md` body changes in this PR)
**Surface touched in this PR:**
`skills/foundry-memory/test-fixture/consumer_prompt.md` (+108 lines, new file).

## Scope of this audit

This entry exists to satisfy the `[audit-2026-Q2]` opt-in tag contract
(`scripts/automation-pr-gate.py` § `gate_audit_tag_requires_audit_trail`,
spec 2026-05-30 §9.2): every skill whose tree is touched by a tagged commit
MUST ship a paired `docs/audit/<name>-audit-trail.md` in the same diff.

**This PR did NOT perform a deep 21-class audit of `foundry-memory`.**
The only change in this skill's tree is the addition of a goal-based
Copilot-CLI test fixture, authored against the Phase 2 template proven by
`foundry-prompt-agents` and `foundry-hosted-agents`. No SKILL.md body, no
references, no Python sample, no descriptor frontmatter changed.

## What WAS validated

- **Fixture mechanics, end-to-end against real Azure** (CI runs against
  `rg-awesome-gbb-ci`, OIDC-federated `uami-awesome-gbb-ci`):
  - Pattern 12 marker file written to `/tmp/foundry-memory-smoke-result`
  - Pattern 17 show-don't-assert preamble
  - 40-minute job ceiling inherited from matrix per Pattern 14
  - Embedding deployment SKU constraint observed: Sweden Central requires
    `GlobalStandard` for `text-embedding-3-small` (Pattern 21 in AGENTS.md
    § 9.7)
- **RBAC fix shipped in this PR (Pattern 23 in AGENTS.md § 9.7):** Foundry
  project SAMI (the *third* identity, distinct from account SAMI and the
  CI UAMI) was missing `Cognitive Services OpenAI User` + `Cognitive
  Services User` at account scope. Server-side memory consolidation worker
  was returning 401 against the chat deployment. RBAC grant applied to
  `8c1b62da-…` at scope `aif-awesome-gbb-ci`; verified GREEN within
  ≥5-min AAD propagation window.
- **Stability proof: 2/3 GREEN** across the full 6-fixture matrix runs
  `26716984572` (6/6 incl. memory) and `26717346015` (6/6 incl. memory).
  Pre-RBAC run `26714879734` is the documented 401 case that motivated
  Pattern 23.

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
audited. For a fixture-only addition + RBAC infra fix (not a SKILL.md
edit), the honest record is "no body edit → no deep audit performed →
fixture mechanics + RBAC fix validated separately via the 2/3 GREEN
matrix proof above + Pattern 23 documentation in AGENTS.md § 9.7". This
stub documents that explicitly so future auditors don't mistake silence
for completeness.

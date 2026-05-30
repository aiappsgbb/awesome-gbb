# Audit Trails

Per-skill audit records produced by the 2026-Q2 deep audit (spec
[`docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md`](../superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md),
plan [`docs/superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md`](../superpowers/plans/2026-05-30-deep-audit-and-testing-rethink.md)).

One file per audited skill: `<skill-name>-audit-trail.md`.

## Format

````markdown
# <skill-name> — Audit Trail

**Auditor:** <agent-id or human handle>
**Date:** YYYY-MM-DD
**Bug-class scan:** all 21 classes from Appendix A of the spec
**Findings (verbatim list):**
1. <class N> — <one-line description> — file:line → fix in commit <sha>
2. ...

**Fixture:** [`../../skills/<name>/test-fixture/consumer_prompt.md`](../../skills/<name>/test-fixture/consumer_prompt.md)

**CI matrix run that proved the fix:** <link to GHA run>

**Open items (deferred):** <if any, with rationale>
````

Skills excluded from this audit: `citadel-hub-deploy`, `foundry-vnet-deploy` (multi-resource greenfield deploys; remain `automation_tier: issue_only`).

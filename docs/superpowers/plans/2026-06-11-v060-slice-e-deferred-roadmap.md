# Implementation Plan — v0.6.0 Slice E: Deferred-to-v0.7.0 Roadmap Notes

**Spec:** [`docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md`](../specs/2026-06-11-v060-upstream-landings-design.md) §4.5, Q-E1
**Slice:** E (last of the v0.6.0 cut — pure signpost, no capability)
**Closes:** nothing outright. Documents the **deferral** of #269 (`foundry-iq` PE-posture audit) and #270 (`foundry-hosted-agents` thread-retention reader) to v0.7.0.
**Depends on:** nothing. Independent of Slices A–D; can land in any order.

---

## Reconciliation note (2026-06-18, re-grounded)

This plan was drafted alongside the spec on 2026-06-11 and **re-grounded against
the live threadlight `sibling-skills-map.md` (main) and live awesome-gbb `main`
on 2026-06-18** while folding Slices A+B into the landing PR (#286). Three facts
sharpened it:

1. **No host-skill READMEs exist.** A live check shows **only 4 of 33 skills have
   a `README.md`** (`azure-monitor-alert-baseline`, `azure-sre-agent`,
   `citadel-hub-deploy`, `foundry-rbac-audit`) — and **neither `foundry-iq` nor
   `foundry-hosted-agents` is among them.** There is nothing to append to, so the
   faithful realization of the spec's "README append" is to **CREATE a minimal
   `README.md`** in each host skill containing only the Roadmap signpost. See E-2.

2. **Open Question E-1 is RESOLVED by threadlight's own contract.** The current
   `threadlight-production-ready/references/sibling-skills-map.md` on `main` maps
   **MDL-011 → `foundry-hosted-agents`** (input contract `subscription_id`,
   `resource_group`, `retention_days`) — *not* `foundry-memory`. `foundry-memory`
   exists (v1.1.0) but threadlight's map does not select it. The host-skill choice
   is therefore decided upstream, not by us. README for #270 goes in
   **`foundry-hosted-agents`** (v1.11.0). E-1 closed.

3. **The deferred contracts are now exact** (sourced from the threadlight map, not
   paraphrased), so the roadmap notes can name the precise signature v0.7.0 must
   build:

   | Finding | Host skill (live ver) | Threadlight input contract |
   | --- | --- | --- |
   | **MDL-010** (#269) | `foundry-iq` (v1.3.2; map note "≥ 0.3.0" satisfied) | `subscription_id`, `resource_group`, `private_endpoint_required: true` |
   | **MDL-011** (#270) | `foundry-hosted-agents` (v1.11.0) | `subscription_id`, `resource_group`, `retention_days` |

**⚠️ Discrepancy to flag (heads-up for the threadlight-side flip, NOT our change):**
the threadlight map lists MDL-010 and MDL-011 in its **"Currently mapped"** table
*without* the `(planned)` tag — i.e. it presents them as if the audit helpers
already exist. **They do not** (#269/#270 are still open; `foundry-iq` and
`foundry-hosted-agents` expose no such method today). Until v0.7.0 ships the
helpers, threadlight should keep MDL-010/MDL-011 `kind: manual`, exactly like the
four rows that ARE tagged `(planned)`. The roadmap notes below say this explicitly
so a reader of the map doesn't flip the finding early and hit a missing-method
failure. (Fixing the map tag is a threadlight-repo edit — out of our scope.)

Everything else in the spec's Slice E scope holds: **no code, no SKILL.md edits,
no pin updates, no version bumps, 1 commit.**

---

## Goal

Make the v0.7.0 deferral of #269 and #270 **discoverable from the host skills
themselves** so a future maintainer (or the threadlight flip-protocol runbook)
lands on the right issue without spelunking the tracker. This is a documentation
signpost — it ships zero behavior.

When this slice lands, threadlight's v0.6.0 cut is complete: MDL-010 (#269) and
MDL-011 (#270) remain `kind: manual` with a documented, issue-linked reason,
and the catalog records why.

---

## What ships

Two new minimal `README.md` files (one per host skill), each ≤ ~25 lines:

```
skills/foundry-iq/README.md            (NEW)
skills/foundry-hosted-agents/README.md (NEW)   ← host confirmed via threadlight map (E-1 resolved)
```

Each contains exactly:

- `# <skill-name>` title line
- one-sentence description of what the skill does today (1 line, copied/condensed
  from the skill's own SKILL.md `description` — no new claims)
- `## Roadmap` section with a single "Planned for v0.7.0" paragraph naming the
  issue, its threadlight finding ID, and a one-line "what flipping it gets us"
- `## See also` section linking the SKILL.md and the upstream issue

No other files change. No `SKILL.md`, no `references/`, no `upstream-pin.md`, no
`plugin.json`, no `marketplace.json`, no `docs/` rebuild (READMEs are not indexed
by `build-site.py`; confirm in Task 2).

---

## README content templates

### `skills/foundry-iq/README.md`

```markdown
# foundry-iq

Knowledge-source (Knowledge IQ) management for Microsoft Foundry — create and
query knowledge indexes backing agents and retrieval.

## Roadmap

**Planned for v0.7.0 — private-endpoint posture audit
([#269](https://github.com/aiappsgbb/awesome-gbb/issues/269)).**
An `audit()` method that introspects each knowledge source's AI Search backing
and reports private-endpoint / public-network-access state. Threadlight's
`sibling-skills-map.md` already names the expected contract:
`audit(subscription_id, resource_group, private_endpoint_required=True) -> dict`.
Deferred from v0.6.0 because it intersects private-endpoint discovery
(`foundry-vnet-deploy`, an `issue_only` manual-validation skill) and needs its own
design conversation. This unblocks threadlight finding **MDL-010**, which **must
stay `kind: manual` until this method ships** — the threadlight map currently lists
MDL-010 without the `(planned)` tag, but no such method exists here yet.

## See also

- [`SKILL.md`](SKILL.md) — the skill contract
- [#269](https://github.com/aiappsgbb/awesome-gbb/issues/269) — the deferred work
```

### `skills/foundry-hosted-agents/README.md`  *(host confirmed — E-1 resolved)*

```markdown
# foundry-hosted-agents

Build, deploy, and invoke Foundry hosted agents (BYOK container agents on ACA)
via `azd`, including identity/RBAC wiring and the FoundryChatClient bootstrap.

## Roadmap

**Planned for v0.7.0 — thread-retention reader
([#270](https://github.com/aiappsgbb/awesome-gbb/issues/270)).**
A read-only `audit()` method to enumerate a hosted agent's conversation threads
and report oldest-thread age against a declared retention window so a pilot can
prove data-lifecycle posture. Threadlight's `sibling-skills-map.md` names the
expected contract: `audit(subscription_id, resource_group, retention_days) -> dict`,
and maps the finding to **this skill** (not `foundry-memory`). This unblocks
threadlight finding **MDL-011**, which **must stay `kind: manual` until this method
ships** — the threadlight map currently lists MDL-011 without the `(planned)` tag,
but no such method exists here yet.

## See also

- [`SKILL.md`](SKILL.md) — the skill contract
- [#270](https://github.com/aiappsgbb/awesome-gbb/issues/270) — the deferred work
```

> The finding IDs (MDL-010 / MDL-011) come from the threadlight sibling-skills
> map. If they have drifted, drop the bold ID and keep the issue link — the issue
> is the durable anchor.

---

## Tasks

This slice is docs-only, so the TDD loop degenerates to "gates green + manual
link check." There is no code under test. Each task is one reviewable unit.

### Task 1 — Create `foundry-iq/README.md`

- [ ] Confirm `skills/foundry-iq/README.md` does not already exist (`test ! -f`).
- [ ] Read `skills/foundry-iq/SKILL.md` frontmatter `description` to source the
      one-line summary verbatim-ish (no new capability claims).
- [ ] Write the file from the template above.
- [ ] **Check:** `python scripts/validate-skills.py` still passes (a new README
      must not trip frontmatter/structure checks — it shouldn't, READMEs are
      unvalidated, but confirm).

### Task 2 — Create `foundry-hosted-agents/README.md`

- [ ] E-1 is resolved: host is **`foundry-hosted-agents`** (threadlight map maps
      MDL-011 here, not `foundry-memory`). No decision pending.
- [ ] Confirm the target README does not already exist.
- [ ] Source the one-line summary from the chosen skill's SKILL.md `description`.
- [ ] Write the file from the template above.
- [ ] **Check:** `python scripts/build-plugins.py --check` passes (structure
      intact; a README in a skill dir is benign).
- [ ] **Check:** `build-site.py` does NOT need a rerun — grep the script to
      confirm it ingests `SKILL.md` only, not `README.md`. If it DOES ingest
      READMEs, rebuild `docs/` and include the regenerated files. (Expected: no
      rebuild needed.)

### Task 3 — Commit

- [ ] Stage the two new READMEs only.
- [ ] Commit message:
      ```
      docs(roadmap): signpost v0.7.0 deferral of #269 + #270 in host READMEs

      Slice E of the v0.6.0 cut. Pure documentation — creates minimal READMEs
      in foundry-iq and foundry-hosted-agents with a "Planned for v0.7.0"
      Roadmap section pointing at the deferred issues. No code, no SKILL.md,
      no pin, no version bump.

      Host skill for #270 confirmed foundry-hosted-agents per the live
      threadlight sibling-skills-map (MDL-011). Each note instructs the
      threadlight side to keep MDL-010/011 kind: manual until v0.7.0 ships
      the audit() helpers.

      Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
      ```
- [ ] **Commit tags:** include `[multi-skill]` if the `automation-pr-gate.yml`
      gate flags two-skill-dir changes. It targets SKILL.md *body* edits, and
      these are net-new READMEs (no SKILL.md touched), so it should pass ungated —
      but `[multi-skill]` is cheap insurance. Do NOT add `[skill-rewrite]` (no
      SKILL.md body changed).

### Task 4 — Verify gates

- [ ] `python scripts/validate-skills.py` → all pass (33 SKILL.md unchanged).
- [ ] `python scripts/build-plugins.py --check` → 33 skills, version unchanged.
- [ ] No `metadata.version` changed anywhere (grep the diff).
- [ ] Manual link check: the two `#269`/`#270` URLs resolve.

---

## What this slice deliberately does NOT do

- ❌ No `audit()` implementation in either skill (that IS v0.7.0 — #269/#270).
- ❌ No SKILL.md edits — keeps the gate quiet and avoids version churn.
- ❌ No version bump on either skill or the plugin — READMEs are optional
   extended docs (AGENTS.md §1); a roadmap signpost is not a capability change.
   (See Open Question E-2 if a reviewer disagrees.)
- ❌ No pin-file changes — neither skill's upstream contract moves.
- ❌ No threadlight-repo changes — the `kind: manual → sibling-skill` flips for
   MDL-010/011 do NOT happen here; they're v0.7.0 follow-ups on the threadlight
   side per their flip-protocol runbook.

---

## Open questions

### E-1 · #270 host skill — RESOLVED: `foundry-hosted-agents` (per live threadlight map)

~~The spec §4.5 point 4 notes #270's issue body names **either** `foundry-hosted-agents`
**or** `foundry-memory`.~~ **Resolved 2026-06-18.** The current threadlight
`sibling-skills-map.md` on `main` maps **MDL-011 → `foundry-hosted-agents`** with
contract `audit(subscription_id, resource_group, retention_days)`. `foundry-memory`
exists (v1.1.0) but the map does not select it. The host-skill choice is decided
upstream; the README for #270 goes in **`foundry-hosted-agents`**. No further
confirmation needed for either this docs slice or the v0.7.0 implementation slice.

### E-2 · Does creating a new README warrant a version bump?

Spec §4.5 says "no version bumps." AGENTS.md §5 treats docs-only changes as PATCH
*at most*, and §1 calls README "optional extended docs." A brand-new file is
arguably MINOR ("new … reference file"), but a roadmap signpost ships no
capability and is not under `references/`. **Recommendation: no bump** — follow
the spec. Flag for the reviewer; if they want strict §5 adherence, a PATCH bump
on each host SKILL.md (`x.y.z → x.y.(z+1)`) is the fallback, which would then also
require a `docs/` rebuild and a `[skill-rewrite]`-tagged commit. Default to the
lighter path.

### E-3 · README convention vs the 4 existing READMEs

The 4 existing skill READMEs (Slice C's two, plus `citadel-hub-deploy`,
`azure-sre-agent`) use a heavier shape (`## Quick start / Authentication /
Threadlight integration / Out of scope / See also`). Slice E's host skills have
no `Quick start` to write (the capability doesn't exist yet), so the minimal
`title + Roadmap + See also` shape is intentional and correct. **No action** —
just noting the asymmetry so a reviewer doesn't flag the minimal READMEs as
"incomplete." They are complete for their purpose.

---

## Done criteria

- [ ] `skills/foundry-iq/README.md` exists with the Roadmap → #269 signpost.
- [ ] `skills/foundry-hosted-agents/README.md` (or `foundry-memory`, per E-1)
      exists with the Roadmap → #270 signpost.
- [ ] `validate-skills.py` + `build-plugins.py --check` green; no version drift.
- [ ] One commit, Co-authored-by trailer, both issue links resolve.
- [ ] E-1 logged for threadlight; E-2 default (no bump) applied unless reviewer
      overrides.

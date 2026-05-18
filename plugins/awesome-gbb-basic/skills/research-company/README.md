# research-company

Profile a real-world organisation against the public web and emit a
structured **org-brief** YAML detailed enough to drive a
**digital-clone-grade** fork of an agentic substrate.

See [`SKILL.md`](SKILL.md) for the canonical procedure.

## Files

| File | What it is |
|---|---|
| [`SKILL.md`](SKILL.md) | The thirteen-phase procedure. Strict frontmatter (≤1024 char description, semver). |
| [`references/brief-schema.md`](references/brief-schema.md) | Authoritative schema for the output YAML. |
| [`references/industry-primers/`](references/industry-primers/) | Canonical industry shorthand — regulator IDs, entity kinds, workflow names, KPI sets — per vertical. **Canon** ([AGENTS.md § 2.2](../../AGENTS.md#22--reference-data-files-are-canon--do-not-normalize)) — do not normalize. |

## What's in scope

A **thin overlay** of company-specific facts. The brief captures only
what an industry primer can't infer:

- Identity, ownership, size, geography
- ~10 subsidiaries (legal entities)
- ~10 named ELT leaders
- 3–5 strategic themes from last 24 months press
- Stack overrides where the company has publicly disclosed

Vertical breadth (function tree, regulator catalogue, entity kinds,
proposed-domain library, rituals, KPI cinematics) lives in the
matching industry primer. `compose-org` reads both at fork time.

## What's NOT in scope

- Single-process deep dives → use `threadlight-design`
- Pitch decks → use a deck generator
- Code generation → out of scope for any research skill
- Exhaustive personae harvest — `compose-org` expands archetypes
  from the primer via faker at fork time
- Domains / regulators / KPIs / rituals — those are primer canon

## Output

Always writes to `briefs/<slug>-org-brief.yaml` (relative to operator
cwd). `briefs/` is gitignored — per-engagement output stays out of
the public catalog. See [AGENTS.md § 2.5](../../AGENTS.md#25--per-engagement-output-stays-in-briefs).

Target size: **300–500 lines**. Anything > 800 suggests harvesting
things the primer already covers.

## Changelog

- **2.0.0** (MAJOR) — Slimmed to thin-overlay design. Removed
  `org_chart[]`, `vertical_entity_kinds[]`, `proposed_domains[]`,
  `regulators[]`, `cadenced_rituals[]`, `kpi_cinematics[]`,
  `functions[]` from the brief schema; those sections now live
  exclusively in the matching industry primer. Procedure cut from
  13 phases to 4. Target brief size cut from 1,500–3,000 lines to
  300–500.
- **1.0.0** — Initial version (thirteen-phase, fat-brief).

---
name: research-company
description: >
  Emit a thin org-brief YAML profiling a target organisation — the
  company-specific overlay that pairs with an industry primer to drive
  a digital-clone-grade substrate fork. The brief captures only what
  the vertical can't infer: identity, ownership, size, geography,
  ~10 subsidiaries, the named ELT, 3–5 strategic themes, and any
  stack overrides the company publicly disclosed. Function tree,
  regulator set, entity kinds, proposed-domain library, rituals, KPIs
  all come from the matching industry primer. Four-phase procedure;
  claims carry confidence + sources[]; gaps go in uncertainties[],
  never invented.
  USE FOR: profile a company before a customer pilot, generate an
  org-brief, prepare a customer-flavoured demo fork.
  DO NOT USE FOR: single-process design (use threadlight-design),
  pitch-deck authoring, code generation, exhaustive personae harvest
  (compose-org expands archetypes via faker at fork time).
metadata:
  version: "2.0.1"
---

# research-company

Profile an organisation from public web sources and produce a **thin**
org-brief YAML — the company-specific facts that an industry primer
can't infer.

## Mental model

```
  industry primer        +        org brief         =     fork inputs
  (vertical canon)                (this skill)            (compose-org reads both)
  ───────────────────────         ──────────────────
  • function tree                 • identity (name, brand voice)
  • regulator catalogue           • ownership + size + geo
  • entity-kind set               • ~10 subsidiaries
  • 25+ proposed-domain library   • ~10 named ELT leaders
  • stack vendor candidates       • 3–5 strategic themes
  • rituals + KPI cinematics      • stack overrides (when public)
                                  • narrative-arc seeds (recent press)
```

If a vertical primer exists in
[`references/industry-primers/`](references/industry-primers/), the
research run is **thin** — 30–45 minutes of web work, ~300–500 lines
of YAML. If no primer exists, write one first (see
[`industry-primers/README.md`](references/industry-primers/README.md))
and graduate it before producing a brief.

## When to use

- Profile a target organisation before a customer pilot or workshop
- Spin up a customer-flavoured demo fork
- Produce a reviewable spec a customer SME can sanity-check

## Output convention

```
briefs/<slug>-org-brief.yaml
```

where `<slug>` is the kebab-case form of the target's short name
(≤ 16 chars). `briefs/` is gitignored — per-engagement output stays
out of the public skill catalog. See
[AGENTS.md § 2.1 — Skills are agnostic](../../AGENTS.md#21-skills-are-agnostic).

## Tooling priority

For every factual claim, point at one or more rows in `sources[]`,
gathered via:

1. **`web_fetch` against the target's own properties** — `/about`,
   `/leadership`, latest annual report or capital-markets-day PDF,
   `/press` or `/newsroom`, `/governance`. Self-reported data is
   `confidence: medium` unless cross-corroborated.
2. **`web_search` for cross-corroboration** — two independent
   secondary sources concurring lifts to `confidence: high`.
3. **`web_fetch` against authoritative third parties** — Wikipedia,
   national company registry (Companies House / SEC EDGAR / etc.),
   regulator filings, news of record.
4. **`web_search` for stack-override signal** — vendor case studies
   where the target's logo appears, recent partnership press
   ("Company X selects Vendor Y for …").

Never rely on a single answer-engine summary.

## Output schema

The output conforms to [`references/brief-schema.md`](references/brief-schema.md).
The schema is **deliberately thin** — only the company-specific
sections are required. Industry-standard sections (functions,
entity kinds, proposed domains, regulators, rituals, KPIs) are
**optional** in the brief; `compose-org` reads them from the primer
when absent.

Key rules:

- Every `Fact` requires `{value, confidence, source_refs?, notes?}`.
- Every `Source` row needs `{id, url, accessed, kind, used_for}`.
- Truly-missing fields go in `uncertainties[]`.
- `meta.status` walks `in_progress` → `needs_review` → `ready`.

## The four phases

### Phase 0 — Bootstrap

Create `briefs/<slug>-org-brief.yaml` with skeleton keys + empty
arrays. Pick the matching primer; if none exists, stop and write
one first.

### Phase A — Identity, ownership, size, geography (10 min)

Sources: Wikipedia + `/about` + last annual report. Fill:

- `identity.{name, short_name, slug, domain, description,
  brand_voice, industry, sub_industry, tagline}`
- `ownership.{structure, parent, ticker, founded, key_shareholders}`
- `size.{employees, revenue_usd, revenue_currency, revenue_period,
  customers_count, assets_count}` —
  `assets_count` is the **vertical-native scale signal** (on-net
  buildings for telco; aircraft for airline; dealers for OEM)
- `geo.{hq, regions, countries_present, key_hubs, footprint_notes}`

### Phase B — Subsidiaries + leadership (15 min)

- `subsidiaries[]`: walk the national registry. Cap at 15 — holding
  + materially-sized opcos. Each `{id, name, country, role,
  regulator (reference the primer's regulator id), confidence}`.

- `leadership[]`: just the publicly-named ELT from `/leadership`,
  typically 8–15 rows. Map each to a canonical persona `role` from
  the primer where one fits (ceo, cfo, coo, cpo, gc, dpo, cdo …);
  free-form for vertical-specific titles (e.g. `chief_ai_officer`).
  **No LinkedIn-stalking for sub-ELT depth** — the primer's
  archetype tree fills levels 3–6 at fork time.

### Phase C — Strategic themes + stack overrides (10 min)

- `strategic_themes[]`: 3–5 themes drawn from the last 24 months of
  press releases + the most recent annual report's CEO letter.
  Each row gets a one-paragraph value, a `function_focus[]` (ids
  from the primer's function tree), a `timeline_hint`, and cites
  one or more press releases. These seed `narrative_arcs.py` and
  `cadenced_rituals.py` overrides at fork time.

- `stack_overrides[]`: ONLY systems the company has publicly
  disclosed (in press releases, joint vendor case studies, or
  earnings calls). Examples: "Company X selected Amdocs for OSS",
  "Company X built an agentic AI engine with Microsoft". Don't list
  inferred systems — those come from the primer's stack-candidate
  table at fork time.

### Phase D — Cross-check & finalise (5–10 min)

Pick three `confidence: high` claims at random. Re-run `web_search`
and confirm. Downgrade any that don't recheck.

Validate against the schema:

- Required sections (`meta`, `identity`, `ownership`, `size`, `geo`,
  `sources`) all populated.
- Every `Fact` has `confidence`.
- Every `source_refs[]` entry exists in `sources[]`.
- `meta.status` → `needs_review`.

Print a short summary:

- counts: subsidiaries N, leadership N, strategic_themes N,
  stack_overrides N, sources N
- 3 highest-confidence claims
- 3 most material uncertainties
- one-line `compose-org` invocation hint

Wait for operator sign-off before flipping `meta.status` to `ready`.

## Output budget

A thin org-brief lands at **300–500 lines of YAML**. Anything > 800
suggests you're harvesting things the primer already covers — stop
and trim. The breadth lives in the primer; the brief is the overlay.

## Iterating the skill

When a generated brief looks wrong, **fix this SKILL.md or the
matching primer**, not the brief. Two runs against the same target
should diff to nothing meaningful except `accessed` dates.

## Downstream re-use

Once `meta.status: ready`, hand off to `compose-org` (sibling
skill, to be authored). That skill reads the brief + the matching
primer and forks a target substrate repo into a customer-flavoured
clone. The brief provides company facts; the primer provides
vertical breadth. Together they drive the fork.

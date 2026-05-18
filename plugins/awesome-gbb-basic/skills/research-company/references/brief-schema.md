# Brief Schema (v3 — thin overlay)

Authoritative output schema for the
[`research-company`](../SKILL.md) skill. Every brief produced by the
skill conforms to the YAML below.

## Design intent

The brief is a **thin overlay** of company-specific facts. Vertical
breadth (function tree, regulator catalogue, entity kinds,
proposed-domain library, rituals, KPI cinematics) lives in the
matching industry primer under
[`industry-primers/`](industry-primers/). `compose-org` reads both
brief + primer at fork time.

## Output path

`briefs/<slug>-org-brief.yaml` (relative to operator cwd).
`briefs/` is gitignored.

## Confidence discipline

Every factual field carries a `confidence` discriminator:

| Level | Meaning |
|---|---|
| `high` | Two or more independent public sources agree |
| `medium` | One authoritative source (company site, annual report, regulator filing) |
| `low` | One secondary source (analyst aggregator, news article) |
| `inferred` | Deduced from the vertical / industry pattern, not directly stated |
| `unknown` | No public information found; logged in `uncertainties[]` |

## Schema (JSON-Schema 2020-12, expressed as YAML)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
$id: "https://zava-design-skills.dev/research-company/brief.schema.yaml"
title: "research-company thin org-brief"
type: object
required: [meta, identity, ownership, size, geo, sources]
additionalProperties: false

$defs:

  Confidence:
    type: string
    enum: [high, medium, low, inferred, unknown]

  Fact:
    type: object
    required: [value, confidence]
    additionalProperties: false
    properties:
      value:        {}                                       # scalar or list
      confidence:   { $ref: "#/$defs/Confidence" }
      source_refs:  { type: array, items: { type: string } } # ids from `sources[]`
      notes:        { type: string }

  Source:
    type: object
    required: [id, url, accessed]
    additionalProperties: false
    properties:
      id:        { type: string, pattern: "^[a-z][a-z0-9-]*$" }
      url:       { type: string, format: uri }
      accessed:  { type: string, format: date }
      kind:
        type: string
        enum: [official-site, wikipedia, annual-report, regulator, analyst, news, jobs-board, vendor-case-study, other]
      used_for:  { type: array, items: { type: string } }

  Uncertainty:
    type: object
    required: [field, note]
    additionalProperties: false
    properties:
      field:     { type: string }
      note:      { type: string }
      followup:  { type: string }

properties:

  meta:
    type: object
    required: [generated_by, generated_at, status, schema_version, primer]
    additionalProperties: false
    properties:
      generated_by:    { const: "research-company" }
      generated_at:    { type: string, format: date-time }
      status:
        type: string
        enum: [in_progress, ready, needs_review]
      schema_version:  { const: 3 }
      primer:          { type: string, description: "industry-primer filename, e.g. 'telco', 'airline'" }
      reviewer:        { type: string }

  identity:
    type: object
    required: [name, slug, description]
    additionalProperties: false
    properties:
      name:           { type: string }
      slug:           { type: string, pattern: "^[a-z][a-z0-9-]*$" }
      short_name:     { type: string }
      domain:         { type: string }
      description:    { $ref: "#/$defs/Fact" }
      brand_voice:    { $ref: "#/$defs/Fact" }
      industry:       { $ref: "#/$defs/Fact" }
      sub_industry:   { $ref: "#/$defs/Fact" }
      tagline:        { $ref: "#/$defs/Fact" }

  ownership:
    type: object
    required: [structure]
    additionalProperties: false
    properties:
      structure:       { $ref: "#/$defs/Fact" }
      parent:          { $ref: "#/$defs/Fact" }
      ticker:          { $ref: "#/$defs/Fact" }
      founded:         { $ref: "#/$defs/Fact" }
      key_shareholders:
        type: array
        items: { $ref: "#/$defs/Fact" }

  size:
    type: object
    additionalProperties: false
    properties:
      employees:       { $ref: "#/$defs/Fact" }
      revenue_usd:     { $ref: "#/$defs/Fact" }
      revenue_currency: { $ref: "#/$defs/Fact" }
      revenue_period:  { $ref: "#/$defs/Fact" }
      customers_count: { $ref: "#/$defs/Fact" }
      assets_count:
        $ref: "#/$defs/Fact"
        description: "Vertical-native scale signal (buildings / aircraft / dealers / branches / plants)."

  geo:
    type: object
    required: [hq]
    additionalProperties: false
    properties:
      hq:              { $ref: "#/$defs/Fact" }
      regions:
        type: array
        items: { $ref: "#/$defs/Fact" }
      countries_present: { $ref: "#/$defs/Fact" }
      key_hubs:
        type: array
        items: { $ref: "#/$defs/Fact" }
      footprint_notes:
        type: array
        items: { $ref: "#/$defs/Fact" }

  subsidiaries:
    description: "Cap 15. Each row references a regulator from the primer."
    type: array
    maxItems: 15
    items:
      type: object
      required: [id, name, confidence]
      additionalProperties: false
      properties:
        id:          { type: string, pattern: "^[a-z][a-z0-9-]*$" }
        name:        { type: string }
        country:     { type: string }
        role:
          type: string
          enum: [holding, opco, holding+opco, regional-hub, joint-venture, dormant, financing-vehicle]
        regulator:   { type: string, description: "id from the primer's regulator catalogue" }
        confidence:  { $ref: "#/$defs/Confidence" }
        source_refs: { type: array, items: { type: string } }
        notes:       { type: string }

  leadership:
    description: "Publicly-named ELT only — typically 8–15 rows."
    type: array
    maxItems: 20
    items:
      type: object
      required: [role, confidence]
      additionalProperties: false
      properties:
        role:        { type: string, description: "canonical persona id from the primer where one fits, else free-form snake_case" }
        name:        { type: string }
        title:       { type: string }
        function:    { type: string, description: "function id from the primer" }
        confidence:  { $ref: "#/$defs/Confidence" }
        source_refs: { type: array, items: { type: string } }
        notes:       { type: string }

  strategic_themes:
    description: "3–5 narrative seeds from the last 24 months of press / annual reports."
    type: array
    minItems: 3
    maxItems: 8
    items:
      type: object
      required: [id, headline, summary, confidence]
      additionalProperties: false
      properties:
        id:             { type: string, pattern: "^[a-z][a-z0-9-]*$" }
        headline:       { type: string }
        summary:        { type: string }
        function_focus:
          type: array
          items: { type: string, description: "function ids from the primer" }
        timeline_hint:  { type: string }
        confidence:     { $ref: "#/$defs/Confidence" }
        source_refs:    { type: array, items: { type: string } }

  stack_overrides:
    description: |
      ONLY systems the company publicly disclosed (press releases,
      joint case studies, earnings calls). Inferred systems come from
      the primer's stack-candidate table at fork time — do NOT list
      them here.
    type: array
    maxItems: 12
    items:
      type: object
      required: [id, role, vendor, confidence]
      additionalProperties: false
      properties:
        id:          { type: string, pattern: "^[a-z][a-z0-9-]*$" }
        role:
          type: string
          description: "role band id; should match an id in the primer's stack-vendor table"
        vendor:      { type: string, description: "e.g. 'Amdocs Network Inventory', 'Microsoft Azure OpenAI'" }
        confidence:  { $ref: "#/$defs/Confidence" }
        source_refs: { type: array, items: { type: string } }
        notes:       { type: string }

  market_position:
    type: object
    additionalProperties: false
    properties:
      competitors:
        type: array
        items: { $ref: "#/$defs/Fact" }
      segment_blurb: { $ref: "#/$defs/Fact" }

  customers_or_segments:
    type: object
    additionalProperties: false
    properties:
      mode:
        type: string
        enum: [b2c, b2b, b2b2c, mixed]
      customer_segments:
        type: array
        items: { $ref: "#/$defs/Fact" }
      key_accounts:
        type: array
        items: { $ref: "#/$defs/Fact" }

  sources:
    type: array
    minItems: 6
    items: { $ref: "#/$defs/Source" }

  uncertainties:
    type: array
    items: { $ref: "#/$defs/Uncertainty" }
```

## What's intentionally NOT in this schema

The following sections **used to** appear in earlier drafts but were
moved to the industry primer (their natural home):

- `functions[]` — function tree
- `org_chart[]` — sub-ELT persona archetypes (`compose-org` expands at fork time)
- `vertical_entity_kinds[]` — Kuzu node-table set
- `proposed_domains[]` — vertical-specific workflow library
- `regulators[]` — full regulator catalogue (subsidiaries reference by id)
- `cadenced_rituals[]` — rituals
- `kpi_cinematics[]` — HUD KPIs
- `stack.systems[]` candidate library — only company-specific overrides stay here

This is the "thin overlay" cut: the brief carries deltas, the primer
carries breadth. `compose-org` is responsible for joining them.

## Cross-references in the brief

- `subsidiaries[].regulator` → an `id` in the primer's regulator catalogue
- `leadership[].role` → a canonical persona id from the primer (where one fits)
- `leadership[].function` → a function id from the primer
- `strategic_themes[].function_focus[]` → function ids from the primer
- `stack_overrides[].role` → a role-band id from the primer
- `*.source_refs[]` → `id`s in `sources[]`

The brief is valid only when every cross-reference resolves. The
primer name is recorded in `meta.primer` so `compose-org` knows which
file to load.

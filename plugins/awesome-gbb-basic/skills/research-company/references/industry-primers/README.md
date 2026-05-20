# Industry Primers

Canonical industry shorthand consumed by
[`../../SKILL.md`](../../SKILL.md). Each primer captures, for one vertical:

- Sub-segment taxonomy (which kind of <vertical> is the target?)
- Canonical `vertical_entity_kinds[]` set
- Canonical `functions[]` list with hero hints
- Canonical regulator IDs per material country
- Proposed-domain starter library
- Stack-system role bands and typical vendors
- Canonical cadenced rituals
- Canonical KPI cinematics

> **Canon.** These files are deliberate, sourced from public industry
> documentation. Do NOT normalize the published shorthand they
> document. See [AGENTS.md § 2.2](../../../../AGENTS.md).

## Index

| Vertical | Primer | Status |
|---|---|---|
| Telco | [`telco.md`](telco.md) | ✅ Full |
| Airline | [`airline.md`](airline.md) | 🚧 Stub |
| Automotive OEM | [`auto-oem.md`](auto-oem.md) | 🚧 Stub |
| Banking (FSI) | [`banking.md`](banking.md) | 🚧 Stub |
| Retail | [`retail.md`](retail.md) | 🚧 Stub |

Stubs get expanded the first time the `research-company` skill is
invoked against a target in that vertical. The full Telco primer is
the worked example.

## Adding a new primer

1. Pick a vertical not already in the index.
2. Copy `telco.md` as a template.
3. Fill the sections from public industry-association documents,
   regulator websites, and analyst writeups.
4. **Cite sources for any non-obvious shorthand** (codes, formats,
   ID structures). Future scrub agents will not normalize what they
   can see is canonical.
5. Add a row to the index above.
6. Bump `metadata.version` in
   [`../../SKILL.md`](../../SKILL.md) by MINOR (a new reference file is
   a new capability — see [AGENTS.md § 5 — Versioning](../../../../AGENTS.md)).

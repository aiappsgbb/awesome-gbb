# Experience and visual contracts

Use existing project documentation where it already owns these decisions.
The filenames below are conventions, not required new files for every task.
Contracts are development artifacts; do not embed them in shipped HTML comments,
hidden DOM, client data, source maps or publicly served directories.

## Experience contract

For a new surface or structural redesign, record the following in an existing
brief or a small `SITE.md`. For a local fix, a scoped change note can suffice.

```markdown
# Experience contract

## Scope and authority
Target and write boundary:
Task/audience:
Existing brand and constraints:
Direction approved by the user:
Out of scope:

## Content and tasks
Required units, sources and consequential caveats:
Task | Starting state | Expected outcome | Required content

## Views and transitions
Chosen model and rejected alternative, with reasons:
View | Reader question | Content shown | Detail available
Transition | State carried | URL | Focus | Return

## Delivery and verification
Narrow-screen relationships:
Applicable loading, empty, error and recovery states:
Print/offline requirement or explicit exclusion:
Checks and evidence locations:
Open decisions and stop conditions:
```

Populate decisions with the actual content, not abstract placeholders left in
the handoff. A transition such as "Back works" is underspecified: name the
collection, query, selection and relevant position it must restore.

### Example: one bounded transition

An analyst filters a comparison to available options and searches "annual",
opens Option B, then follows its evidence link. Back must restore the same
filter, query and selected option; a footer CTA changing the audience must
not discard them. The direct link must reconstruct the selected option without
requiring a prior visit. These are proposed acceptance conditions, not a claim
that any implementation already passes.

## Visual contract

Prefer existing design tokens and components over a parallel design document.
If a `DESIGN.md` is useful, distinguish precise values from prose explaining
their roles. Extracted values are observations; consolidation is a proposed
change requiring authority, not an invisible part of extraction.

The following **illustrative fragment** shows structured values and references,
not a default palette or a complete production design system:

```yaml
name: Example visual contract
colors:
  ink: "#17212B"
  surface: "#FFFFFF"
  action: "#2455A4"
  on-action: "#FFFFFF"
typography:
  body:
    fontFamily: system-ui
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
spacing:
  compact: 0.5rem
  regular: 1rem
rounded:
  control: 0.25rem
components:
  action:
    backgroundColor: "{colors.action}"
    textColor: "{colors.on-action}"
    rounded: "{rounded.control}"
```

When using the Google DESIGN.md format, verify its current schema and pin the
optional tooling version before adoption. It has used an `alpha` format; do
not claim all files called DESIGN.md share a compatible schema.

The prose should cover the product's visual character, typography and measure,
spacing hierarchy, surfaces, component states, responsive behavior, iconography,
visual explanations, and motion/reduced-motion rules. Only include relevant
sections. Do not impose a universal font pair, shadow, grid, corner radius or
dark mode.

## Authority and lifecycle

1. Product truth, explicit user constraints, existing brand and applicable
   accessibility requirements bound the work.
2. The approved experience contract owns content priority and navigation.
3. The visual contract owns the design vocabulary inside that structure.
4. Generators and implementation tools execute these choices; they do not
   silently override them.

Respect higher-priority runtime and repository instructions. If contracts
conflict, surface the conflict and obtain a decision rather than averaging
incompatible directions.

Keep one owner per decision. Derive CSS/theme tokens from the same values where
the stack supports it; otherwise verify parity. After implementation, reconcile
the document with what actually shipped. Do not record an imagined design
system and defend it against the rendered result.

## Evidence record

Reuse the project's test report or keep a small local table:

`task/check | conditions | expected | observed | evidence | status`

Use **observed**, **source-inferred**, **not checked**, or **blocked**.
For executed checks, also record whether the observation meets the expected
outcome. An agent-authored "PASS" file is not independent evidence that an
interaction occurred.

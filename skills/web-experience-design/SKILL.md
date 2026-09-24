---
name: web-experience-design
description: >
  Design and improve task-centered web experiences: executive HTML reports,
  analytical comparisons, catalogs, dashboards, interactive tools, documentation,
  informational sites and navigable HTML presentations. Turn complex content into
  clear views, useful visual explanations and working navigation before styling.
  USE FOR: web experience design, information architecture, content hierarchy,
  too much text, long scrolling pages, findability, list-detail flows, responsive
  navigation, meaningful icons and motion, SITE.md, DESIGN.md, browser UX review,
  printable or offline HTML. Use independently or with an approved visual tool;
  no mandatory theme, framework, model or external service.
  DO NOT USE FOR: backend-only work, cloud deployment, native mobile apps,
  PowerPoint authoring, prose-only editing or formal accessibility certification.
metadata:
  version: "1.0.1"
---

# Web Experience Design

Make the next useful action obvious, the important content understandable, and
the detail easy to retrieve. A complete document is not automatically a usable
interface. Attractive screenshots are not evidence of a working experience.

**Merged source; release pending:** output acceptance and cross-runtime discovery remain
pending; see [validation boundaries](README.md#validation-and-boundaries).

## Choose the scope

Identify the target, task and write boundary before changing anything. Reuse
the brief, existing design system, approved decisions and repository conventions.
Ask only material unanswered questions, one at a time through the available
question tool. Do not restart discovery or ask for arbitrary taste preferences.

| Request | Path |
|---|---|
| Audit or plan only | Inspect and propose; do not fix, install or publish. |
| Small refinement | Preserve structure, behavior and brand; state the local intent, make the bounded change, verify affected paths. No full redesign workshop. |
| New experience or structural redesign | Complete the workflow below; obtain direction approval before substantial implementation. |

Choose the primary visitor task: **understand**, **decide**, **operate**,
**find**, **act**, or **present**. Mixed experiences may use different modes in
different views. These are routing hints, not templates. Load only the relevant
part of [architecture](references/architecture.md).

## 1. Establish content and a baseline

Read the real material before choosing a layout. Record the reader's questions,
required content, evidence, consequential caveats, actions and delivery constraints.
Separate facts, interpretation and proposed copy. Never invent claims, sources,
testimonials, prices, user research or customer results to fill a composition.

For a redesign, inspect the current rendered experience where possible. Define
3-5 representative tasks, or fewer for a genuinely smaller change, with explicit
starting state and observable outcomes **before editing**. Include returning to
information, not only a first visit. If a user wants a before/after but supplied
no disappointing artifact, request one; do not choose an easy artificial baseline.

Preserve an original or use version control. Record actual viewport, URL/state,
paths, search effort, hidden essentials and context loss. Do not infer human task
times from automation. If the app cannot run, label source-only findings and
unverified visual/interaction behavior rather than claiming a browser audit.

## 2. Decide the structure

Map each required content unit to an initial view, detail, source or complete
reading/export view. Remove redundancy only with a reason; moving content must
not make it disappear from search, links or export.

Explicitly choose among **addressable dynamic views**, **multiple pages**,
**a hybrid**, or **linear reading**. Explain the choice in terms of the tasks.
Do not default to a long all-open page, tiny text, twenty tabs, nested scrolling,
scroll hijacking or a carousel of essential information. Long-form reading is
valid when intentional, not the only way to retrieve a specific answer.

Specify navigation labels, current location, direct links, Back/Forward, filter
and selection state, focus/return behavior, narrow-screen changes, and applicable
search, empty and error states. A header link and a footer CTA performing the
same navigation must preserve the same relevant context.

Show a monochrome wireframe with enough **real content** to expose density and
wrapping. Offer two structurally different alternatives only when a real tradeoff
exists, not two palettes of the same page. Obtain explicit direction approval;
if already approved, reuse it. With no answer mechanism, stop at a labeled proposal
unless the user has already authorized those decisions.

Use [contracts](references/contracts.md) to record the smallest durable
experience contract. Reuse an existing file; do not create a bureaucracy of
duplicate briefs, manifests and acceptance receipts.

## 3. Give the experience a visual language

Read [craft](references/craft.md) before visual implementation. Preserve an
existing brand; otherwise derive type, spacing, composition, imagery and component
character from the subject and use context. Distinctive does not mean unfamiliar.
No universal palette, serif pairing, card grid, sidebar or mandatory animation.

Choose how to explain each idea: concise text, comparison table, diagram, chart,
image or interaction. Use semantic icons with visible labels where meaning is
ambiguous. Define purposeful motion for state, continuity and feedback, with a
reduced-motion alternative. Do not satisfy these requirements with decorative
arrows and a page-load fade.

Document approved visual rules in the project's existing system or a focused
`DESIGN.md`; token values and their implementation must agree. The
[contract reference](references/contracts.md#visual-contract) distinguishes a
structured design document from a task/navigation contract.

External generators and other design skills are **optional executors**, not
authorities that may replace the approved structure. Consult
[integrations](references/integrations.md) only when using one. Never silently
upload content, install tools, enable hooks, create accounts or expand scope.

## 4. Build the approved scope

Prefer the existing stack and native semantics. A dynamic experience does not
require a heavy framework; multiple pages do not require a backend. Use actual
content and data shapes, including long labels and missing values.

Implement the navigation/state contract across every entry point, including
deep links, alternate audiences, browser history and recovery paths. No fake
controls, placeholder destinations, simulated loading or fabricated availability.
Wire charts, tables, status and sources to the same underlying content.

Keep ordinary page scrolling usable. On mobile, change relationships between
views where necessary instead of stacking the entire desktop. If offline or
print is required, implement that delivery mode deliberately; hidden, unfetched
or virtualized content is not automatically present in a complete export.

## 5. Verify the experience

Follow [verification](references/verification.md). Execute the agreed tasks
against the rendered result with real content and record expected versus observed
outcomes. Inspect desktop, narrow screens and intermediate states, not only the
hero. Check keyboard/focus, applicable contrast and reflow, icons/motion, assets,
links, meaningful data displays and recovery; verify print/offline when required.

Distinguish **observed**, **source-inferred**, **not checked**, and **blocked**.
Never call a missing browser check a pass, an automated walkthrough a user study,
a linter a usability certificate, or a self-assigned score a quality measurement.

Batch findings and fixes coherently, then repeat affected tasks and regressions.
Stop for a scope/budget decision if another pass makes no material progress;
do not keep generating pages or polishing without an end condition.
Unresolved required behavior blocks a success claim. Report it plainly.

## Handoff and reuse

Lead with the delivered outcome, supported by the paths actually exercised.
Identify changed behavior, material limits and skipped checks without dumping
every log into the interface or chat. Keep development notes out of shipped pages.
Stop temporary servers you started unless the user requested retention.

Before promoting this method to a global default, run the
[acceptance scenarios](tests/scenarios.md): report, comparison/tool and a
different informational identity. Include the user's real baseline when one
exists. Obtain acceptance; do not overwrite unrelated personal skills or global
instructions. Source availability, discovery, invocation, workflow application
and output quality are separate checks.

## Reference map

| Load when needed | Purpose |
|---|---|
| [architecture](references/architecture.md) | Deliverable routing, structural choices and content editing |
| [contracts](references/contracts.md) | Experience and visual contracts without duplicate sources of truth |
| [craft](references/craft.md) | Typography, composition, icons, visual explanation and motion |
| [verification](references/verification.md) | Task evidence, accessibility, responsive and delivery checks |
| [integrations](references/integrations.md) | Optional tools, compatibility, privacy, cost and authority |
| [evidence](references/evidence.md) | Sources, dates, applicability and conflicts; not mandatory upfront research |

# Architecture and content

Use this reference for `SKILL.md` steps 1-2. Start with what a reader needs to
understand or do, not with a component inventory.

## Route by task, not file extension

| Experience | Primary work | Useful structure | Failure to avoid |
|---|---|---|---|
| Executive report | Understand a conclusion and decide what follows | Decision summary, evidence-linked topics, complete reading/print view if required | A long report with a decorative hero and a conclusion at the bottom |
| Comparison | Evaluate alternatives against common criteria | Simultaneous criteria matrix, selection and relevant filters | One tab per option that requires remembering values |
| Catalog or analytical tool | Find, inspect, act and return | Searchable collection and addressable details with preserved state | Marketing introduction repeated before every consultation |
| Documentation | Find an answer, follow a procedure, verify a reference | Topic hierarchy, local index, search when justified, stable anchors | Endless topic dumping or vague labels such as "Explore" everywhere |
| Informational site | Understand an offer, service or subject and take the next step | Subject-specific pages and an intelligible entry point | An application shell when a few clear pages suffice |
| HTML presentation | Follow an argument while retaining access to detail | Explicit sequence, keyboard navigation, index and complete export when required | An obligatory carousel reused for ordinary reading |

Modes can mix. A tool's introduction may persuade while its working surface
supports operation. Do not use mode names as reasons to change established brand.

## Content inventory

For structural work, map each meaningful unit:

| Unit | Reader question/task | Importance | Source / date / uncertainty | Destination |
|---|---|---|---|---|
| Conclusion | What should I do? | Essential | Evidence and conditions that could change it | Initial decision view |
| Comparable attributes | Which option meets my criteria? | Task-dependent | Shared units, definitions and missing values | Comparison |
| Method and full evidence | Why should I trust this? | Supporting | Provenance and limits | Named detail/source view |
| Operational constraint | What must not happen? | Essential when consequential | Actual scope, not marketing | Beside the affected action/outcome |

These are roles, not mandatory sections. Adapt to the actual material.

Before changing copy, classify the edit: **keep visible**, **rewrite without loss**,
**move to detail**, or **remove duplication**. Record reasons for substantive cuts.
Do not reduce word count by deleting qualifications, sources or difficult cases.

## Choose a navigation model

| Model | Choose when | Cost to address |
|---|---|---|
| Dynamic addressable views | Users repeatedly filter, inspect and return within a stable domain | URL/state restoration, focus, search of hidden content, reload and export |
| Multiple pages | Topics are independently useful and worth bookmarking/sharing | Consistent navigation, cross-topic discovery and return context |
| Hybrid | A topic site includes a genuinely interactive comparison or tool | Make page transitions and local state changes distinguishable |
| Linear reading | Sequence is necessary to understand the argument, or the reader explicitly chooses the complete document | Local index, anchors and an alternative consultation route when needed |

One HTML file can contain several addressable views. A collection of files can
still behave like an endless wall of content. Judge the reader's path, not the
framework or file count.

## Pick components for a reason

- **Tabs:** a few related views that need not be seen together; never one per
  arbitrary source heading. Page navigation uses links; local tab panels need
  the tab keyboard/state contract.
- **Disclosure:** optional detail with a predictable label. Do not hide the
  conclusion, decisive caveat or controls needed to complete the primary task.
- **List-detail:** preserve the selected item and collection context. On narrow
  screens, separate list and detail when simultaneous display stops being useful.
- **Table:** comparable values or records with common fields. Preserve units,
  headers and relationships on mobile; a deliberate table scroll region may be
  better than cards that destroy comparison.
- **Cards:** coherent, independently meaningful objects or destinations, not a
  compulsory wrapper around every paragraph.
- **Search and filters:** shortcuts over a meaningful structure, not a substitute
  for it. State the scope, expose active constraints and explain zero results.
- **Pagination / load more:** choose for collection size, retrieval and return
  needs. A long article, lazy loading and infinite-result loading are different
  problems. No automatic "paginate everything" rule.
- **Breadcrumbs:** hierarchy, not a fabricated history of prior clicks.

## Navigation/state contract

For each transition specify:

`origin -> destination -> state carried -> URL -> focus -> return`

Include primary nav, footer CTAs, breadcrumbs, audience/view changes, share links,
reload and browser Back/Forward. Equivalent entry points must not disagree.
Do not expose confidential search text or records in shareable URLs.

Keep global navigation separate from local navigation and controls. A link
called "Process library" must not silently reset the selected collection if it
is presented as a jump to the current results. Name scope-changing actions.

## Density and editing

Count competing decisions, mandatory openings, context switches and facts the
reader must remember. Words, DOM count and whitespace percentage are diagnostic
signals, not a cognitive-load score.

Use label + concise outcome + meaningful state for selection surfaces. Put full
explanation where the reader evaluates the selected item. Repeating the same
warning in five phrasings makes it harder to identify the one that matters.

Good: a visible "Historical evidence; current acceptance not recorded" state,
with date, scope and source in an accessible evidence view.

Bad: removing the limitation to make a cleaner card, or preceding every answer
with a page of repeated implementation disclaimers.

## Adapt the work, not just the columns

Specify how a reader changes views, finds controls and returns at narrow widths.
Do not shrink fonts or turn every desktop region into one long vertical stack.
Keep essential state visible and navigation reachable without covering content
or keyboard focus. Avoid nested scroll regions unless the task genuinely needs
them, and test the exception.

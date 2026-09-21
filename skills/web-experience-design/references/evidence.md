# Evidence and applicability

This is an original workflow, not a copy of a brand system or an upstream skill.
Use these sources for the relevant unresolved question; do not fetch them all
before every task.

**Reference date and access date: 2026-09-21.** Undated live pages are guidance
observed at that date, not proof of when a practice was introduced. Recheck
version-sensitive technical details before adopting a dependency.

| Source / author | Publication or update | Evidence type | Application and limit |
|---|---|---|---|
| [WCAG 2.2, W3C](https://www.w3.org/TR/2024/REC-WCAG22-20241212/) | 2024-12-12 Recommendation | Normative technical standard | Accessibility requirements with levels and exceptions; not an aesthetic or usability score |
| [Tabs Pattern, W3C WAI APG](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) | Not exposed | Technical pattern guidance | Keyboard and semantic contract; not a substitute for page-navigation links or conformance testing |
| [Layout, Apple HIG](https://developer.apple.com/design/human-interface-guidelines/layout) | 2026-09-09 metadata | Product guidance | Hierarchy, grouping and adaptability; native-platform styling is not a web template |
| [Motion, Apple HIG](https://developer.apple.com/design/human-interface-guidelines/motion) | 2025-09-09 metadata | Product guidance | Purpose, brevity, interruption and alternatives; not a requirement to animate every surface |
| [Tabs, GOV.UK Design System](https://design-system.service.gov.uk/components/tabs/) | Not exposed | Component guidance | Hiding content has a cost; avoid tabs for simultaneous comparison or mandatory sequential reading |
| [Tabs, Used Right, Evan Sunwall / NN/g](https://www.nngroup.com/articles/tabs-used-right/) | 2024-08-02; reviewed 2026-09-02 | Professional synthesis | Distinguishes panel tabs and navigation tabs; not a universal maximum number |
| [Accordions on Desktop, Huei-Hsin Wang / NN/g](https://www.nngroup.com/articles/accordions-on-desktop/) | 2023-07-30 | Professional guidance | Disclosure versus discoverability and interaction cost; shorter is not always simpler |
| [Comparison Tables, Kate Moran and Taylor Dykes / NN/g](https://www.nngroup.com/articles/comparison-tables/) | 2024-02-09 | Professional guidance | Aligned comparable attributes reduce memory demands; not all objects merit a table |
| [Information Scent, Raluca Budiu / NN/g](https://www.nngroup.com/articles/information-scent/) | 2020-02-02 | Applied HCI theory | Labels and context predict value relative to a task; no measured effect promised for a new design |
| [Icon Usability, Aurora Harley / NN/g](https://www.nngroup.com/articles/icon-usability/) | 2014-07-27 shown | Guidance with reported observations | Familiar meanings and visible labels; conventions can change, so test the audience |
| [Pagination, infinite scroll and load more, Christian Holst](https://www.smashingmagazine.com/2016/03/pagination-infinite-scrolling-load-more-buttons/) | 2016-03-01 | Reported ecommerce usability research | Distinguishes browsing and retrieval; does not prove pagination always wins or generalize directly to reports |
| [Navigation, GitHub Primer](https://primer.style/product/ui-patterns/navigation/) | Not exposed | Design-system guidance | Context, URL and adaptive parent-detail relationships; no requirement to use its component library |
| [Data table, IBM Carbon](https://carbondesignsystem.com/components/data-table/usage/) | Not exposed | Design-system guidance | Useful density, space and data controls; not a spreadsheet replacement |
| [Identify user needs, Government Digital Service](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/plan-manage-content/identify-user-needs/) | Not exposed | Content-design methodology | Needs and acceptance before components; public-service action emphasis is not a ban on understanding as a goal |
| [Web Vitals, Google](https://web.dev/articles/vitals) | 2024-10-31 update | Technical metric guidance | Field versus lab and device segmentation; not a measure of content value or visual quality |
| [Working with the History API, MDN contributors](https://developer.mozilla.org/en-US/docs/Web/API/History_API/Working_with_the_History_API) | 2025-08-01 | Technical documentation | State and browser history mechanics; implementation still needs focus, reload and return checks |
| [Printing, MDN contributors](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Media_queries/Printing) | 2025-11-07 | Technical documentation | Print styles and events; cannot restore content never rendered |
| [Same-origin policy, MDN contributors](https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy) | 2026-09-17 | Technical documentation | File origins can be opaque/implementation-dependent; localhost success is not offline-file proof |
| [DESIGN.md specification, Google Stitch](https://stitch.withgoogle.com/docs/design-md/specification/) | `alpha` observed; page undated | Format specification | Token/prose separation and extensibility; independent of whether the remote service is used |

## Resolve conflicts explicitly

- A stakeholder's preference for direct access is a requirement, not proof that
  nobody scrolls. Avoid mandatory long-page traversal without imposing "never scroll".
- A component library's card-heavy layout is a product convention, not a universal
  information architecture. Likewise, anti-card or anti-serif rules are not research.
- WCAG thresholds, platform guidance, heuristics and stakeholder preferences have
  different authority. Do not label every 44px recommendation a web AA requirement.
- Native HIG and marketing references are not interchangeable. Extract clarity,
  hierarchy and feedback principles rather than importing a whole brand.
- Existing generator instructions demonstrate possible capabilities, not comparative
  output quality. No controlled benchmark proving a particular skill is best for
  every report or tool is claimed here.

Read source guidance critically. Preserve source dates, context and limits when
they support a consequential design decision. Do not use popularity, gallery
screenshots, marketing promises or invented attention-span statistics as evidence.

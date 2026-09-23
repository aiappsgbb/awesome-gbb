# Web Experience Design

An independent, task-first workflow for useful, distinctive web experiences.
It addresses content overload and poor findability before choosing colors or
components. It is not a theme library or a wrapper around a design service.

**Version 1.0.0 is a source candidate, not a claim of accepted output quality.**
The repository's validation record is at
`docs/maintenance/web-experience-design-validation.md`.
No global installation is performed by the skill.

## Use it for

Executive reports, analytical comparisons, catalogs, dashboards, interactive
tools, documentation, informational websites and navigable HTML presentations.
Small changes stay small; new structures require direction approval.

Example requests:

> Use web-experience-design to audit this report. Find the recommendation, compare
> two options and trace one claim to its source. Do not edit yet.

> Use web-experience-design to turn this material into a consultable experience.
> Preserve all required content. Compare dynamic views and separate pages before
> choosing the structure; show a real-content wireframe for approval.

> Use web-experience-design to fix this filter-to-detail return path. Keep the
> existing brand and layout, and verify direct links and browser Back.

> Use web-experience-design for a standalone offline HTML report with a complete
> print view. No external fonts, analytics or design service.

## What it produces

The scope determines the artifacts, not a fixed pipeline:

- a content/task map and baseline for a structural change;
- an approved experience contract, reusing existing project documentation;
- a coherent visual system, expressed in existing tokens or `DESIGN.md`;
- the requested implementation and observed task results;
- a clear boundary around what was not checked or could not be completed.

It does not require one theme, stack, model, browser vendor or generator.
An approved design tool may produce visuals, but it does not own content truth,
navigation or acceptance.

## Runtime requirements

Reading and planning need file/content access and a way to confirm material
decisions. Implementation needs the project's normal coding tools. Rendered
verification needs an available browser or an explicitly documented alternative.
If those capabilities are unavailable, the skill reports the limitation instead
of installing a tool or declaring an untested result complete.

Load `SKILL.md` through your runtime's supported skill mechanism. Resolve its
references from the directory containing that file, not an assumed project path.
Reading the file manually is useful for inspection, but is not proof that native
skill discovery or invocation works.

## Validation and boundaries

From the repository root, the local contract tests protect packaging, links,
examples and key guardrails:

```bash
python3 -m unittest scripts.tests.test_web_experience_design_contract
```

Those tests do **not** prove generated UI quality. The
[scenario pack](tests/scenarios.md) defines separate execution and acceptance
checks before release/global promotion. No Azure resources or credentials are
required by this skill, and it does not provision infrastructure.

The workflow is original catalog guidance informed by the
[source register](references/evidence.md). No third-party skill implementation,
brand assets or proprietary fonts are bundled.

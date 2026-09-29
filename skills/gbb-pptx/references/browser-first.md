# Optional browser-first delivery

This is a workflow contract, not a bundled HTML-to-PPTX converter. The direct
`python-pptx` path remains the default. Use browser-first when fast visual
iteration helps a new composition and an available export path can meet the
requested output. Do not install a framework or external service just to begin.

## Decide the output before styling

Reuse the brief and approved storyboard. Confirm what the recipient must edit:
titles/body text, shapes, chart data, table cells, diagrams, notes, or none.
"Editable PPTX" must identify these objects, not merely the file extension.
Also record target aspect ratio, brand/template, font availability, accessibility,
offline requirements and the presentation application where it will be used.
Ask the user or coordinator only for material missing decisions.

| Output | Appropriate when | Boundary |
|---|---|---|
| Slide-sized images in PPTX | Visual fidelity matters and the user accepts a presentation-only artifact | Text and chart data are not native editable objects; notes, alt text and links need separate preservation |
| Native PowerPoint objects | The recipient must reuse/edit specific content | Restrict styling to supported mappings; text metrics and layout can differ from the browser |
| Hybrid | Editable text/objects and rasterized complex visuals are explicitly acceptable | Identify which elements are images; a native heading does not make the whole slide editable |

Never silently rasterize required editable content to make an export succeed.
Do not assume that PDF-to-PPTX repairs this trade-off or that a vector image
becomes editable chart data. If an established corporate template is mandatory,
prove that the chosen path preserves its required masters/layouts; otherwise
prefer direct generation or the existing-file editing workflow.

## Prove export early

Before polishing the full deck, export a representative sample with the intended
converter and record its actual version. Include the hardest content present:
long title/body, non-ASCII text, a table or chart, a diagram, citations and notes.
Use the real target fonts and intended page dimensions.

Open/render the actual PPTX and check fidelity, readable sources, note retention,
slide count and the required editable objects. Inspect converter warnings and
per-element or whole-slide image fallbacks. Do not hide failures behind an
otherwise successful process exit.

If the sample fails, simplify unsupported styles, use direct native generation,
or ask for a changed output contract. Do not finish a beautiful HTML deck before
discovering its PowerPoint delivery path cannot satisfy the requirements.
An unverified converter remains a prototype, not a production default.

## Iterate in the browser

1. Render discrete fixed-size slide canvases, not a long responsive page chopped
   into screenshots. The preview may scale to fit the window; slide geometry
   should remain the agreed aspect ratio.
2. Keep the storyboard as the content source of truth and use stable slide IDs.
   Reconcile approved wording changes there; do not maintain two independently
   rewritten narratives. Preserve source, caveat and note associations.
3. Use the existing brand/design guidance when available. Browser tooling expands
   composition options but does not require elaborate effects, card grids or a
   visual quota. Do not let decoration displace the evidence.
4. Serve local assets on a trusted local path where appropriate. Wait for fonts,
   images and charts to finish loading; select a stable animation/click state.
   Do not upload confidential content/assets or enable external generators to
   make a preview work. Review remote asset requests before using private data.
5. Inspect each slide visually, with Playwright or the available browser tool.
   Check clipping, overflow, margins, text size, chart labels, contrast and
   hierarchy. DOM bounds help detect problems but do not establish legibility.
6. Correct the source and recheck affected slides. Screenshot comparisons can
   detect regressions, not judge narrative or aesthetic quality. Use a consistent
   browser/font environment; record unavailable checks honestly.

## Export and verify again

Export the complete deck only after the early proof and browser review.
Freeze content for the export; preserve intentional changes in the storyboard.
Check whether click steps create extra slides and whether interactive states,
links or notes are lost. Do not deliver surprise duplicates or empty states.

Render/open the PPTX itself, not the HTML again. Compare it with the approved
preview for line breaks, font substitution, clipping, chart labels, source
visibility and emphasis. Verify content and notes against the storyboard and
exercise the required edits in the target application when possible.
If the target application is unavailable, report that check as unverified.

An image-only route requires explicit acceptance and meaningful text alternatives
or an accessible companion where needed. Hidden speaker notes alone do not
provide an accessible reading path. Do not claim accessibility certification.
Keep the approved HTML/source for reproduction if requested; disclose all
material fidelity and editability limitations at delivery.

## Tool evidence, not a supported-converter claim

Official documentation consulted 2026-09-29; these are candidates to assess,
not tested/export-pinned dependencies of this skill.

| Source | Documented boundary |
|---|---|
| [Marp CLI](https://github.com/marp-team/marp-cli/blob/main/README.md) | Standard PPTX uses prerendered images with presenter notes. Editable export is experimental, warns of lower fidelity and does not preserve presenter notes. |
| [Slidev export documentation](https://github.com/slidevjs/slidev/blob/main/docs/guide/exporting.md) | Standard PPTX uses images and notes. Main-branch documentation also describes editable export with rasterized elements, possible whole-slide fallback, font/wrapping limits and click-step expansion. Verify availability in the exact installed release. |
| [PptxGenJS HTML conversion](https://gitbrent.github.io/PptxGenJS/docs/html-to-powerpoint.html) | Documented HTML conversion is table-oriented, not a general mapping of arbitrary HTML/CSS pages to native slide objects. |
| [Playwright screenshots](https://playwright.dev/docs/screenshots) and [visual comparisons](https://playwright.dev/docs/test-snapshots) | Useful for capture and regression inspection; browser output varies with environment and does not establish PowerPoint rendering correctness. |

## Model choice

Keep this skill model-neutral. Prefer capabilities appropriate to the work:
content reasoning, visual inspection, tool execution and correction from actual
renders. A user preference for a model is valid; do not turn it into a universal
quality ranking or silently switch the session's model.

If comparing models, use the same source, brief, audience, time allowance,
output/editability requirements and available tools. Separate model effects
from workflow effects by comparing the same rendering path first; record exact
versions and dates, actual completion, content fidelity, visual issues, repair
effort and observed cost/latency. A single successful deck is not proof that
one model family is always superior. This skill contains no GPT/Opus benchmark.

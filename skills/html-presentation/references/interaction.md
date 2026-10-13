# Web-native presentation interaction

## Delivery contract

Build a continuous, responsive visual narrative. Scroll connects the argument;
clicks explore evidence, relationships or optional depth. Give each beat a
content-driven composition and preserve the document's natural flow.

Choose an interaction for each beat rather than adding every fashionable effect:

| Audience task | Useful device | Keep visible |
| --- | --- | --- |
| Follow change over time | Scrolling chronology beside a sticky explanation | Dates, qualification and event status |
| Compare unlike evidence | Clickable evidence inspector | All headline values and their different claim states |
| Understand a system | Clickable labeled architecture with contextual explanations | Entire path, boundaries and proposal/preview status |
| Investigate optional depth | Native details/summary | The conclusion and any caveat that changes it |
| Navigate a guided talk | Chapter anchors and subtle scroll progress | The continuous document |

Use sticky positioning sparingly and release it at the end of its containing
block. On mobile, stack
the visual and explanation, remove sticky positioning and keep touch targets
usable. Respect zoom and short viewport heights.

All essential content is present and visible in the initial HTML. JavaScript
may enhance optional inspectors, progress and current-chapter indication, but
is not needed to read the argument. Start optional inspector controls disabled,
then enable them only after validating their targets. Without JavaScript, show
all inspector explanations. The bundled runtime scopes state to each inspector.

Keep stable chapter IDs, native anchor links, ordinary keyboard behavior and
browser history. Scroll-position indication is independent of URL updates. Deep links
into a closed disclosure or inspector must expose their target. Label native
buttons and reflect selection with aria-pressed; native Tab/Enter/Space work.
Keep a live status area for actual errors rather than success-shaped fallbacks.

Source records belong in an accessible local disclosure or appendix, with exact
locators and claim-specific links. Source clicks open the appropriate record;
they preserve the narrative's evidence selection. Keep source descriptions local
and their original URLs available as ordinary hyperlinks. Use optional context
for additional explanation.

Reduced motion disables smooth scrolling and non-essential transitions.
Keep core text visible from the initial HTML. Print all explanations and sources,
allow normal page flow, and omit interactive navigation.

## Evidence explorer markup

`assets/template.html` contains a complete synthetic pilot example using the
bundled runtime and CSS. Its explorer can be copied as a coherent unit:

```html
<div class="inspector" data-inspector>
  <div class="inspector-choices" role="group" aria-label="Choose pilot evidence">
    <button type="button" data-inspect="completion-detail" disabled>
      Completion: 6 of 8 without help
    </button>
    <button type="button" data-inspect="timing-detail" disabled>
      Timing: 4-minute median, no baseline
    </button>
  </div>
  <div class="inspector-readout" aria-live="polite" aria-atomic="true">
    <article class="inspection" id="completion-detail" data-inspection>
      <h3>Completion observation</h3>
      <p>Six of eight participants completed the workflow without help.</p>
    </article>
    <article class="inspection" id="timing-detail" data-inspection>
      <h3>Timing observation</h3>
      <p>Median completion time was four minutes. No baseline was measured.</p>
    </article>
  </div>
</div>
```

Each `data-inspect` value matches exactly one `data-inspection` element's unique
`id` in the same `data-inspector` container. Keep controls initially disabled
and all explanations initially visible. On successful initialization, `story.js`
enables controls, sets `aria-controls` and `aria-pressed`, selects the first
record and exposes the selected explanation. Each explorer maintains its own
state. Native Tab/Enter/Space activate the controls.

Preserve all headline facts and material caveats in the controls or adjacent
primary copy. Selection changes optional explanatory depth. Without JavaScript
all explanations stay readable; print exposes every record. Use unique IDs when
adding another explorer.

For a claim-specific source link, match its native fragment and `data-source`
to the source record ID inside `details#sources`:

```html
<a href="#source-pilot" data-source="source-pilot">Pilot source</a>
<details class="sources-area" id="sources" open>
  <summary>Sources and qualifications</summary>
  <article class="source-record" id="source-pilot">
    <h3>Synthetic authoring fixture</h3>
    <p>These example observations are supplied in assets/template.html.</p>
  </article>
</details>
```

For actual evidence, add the exact inspected locator to the source record.
The runtime opens the disclosure when a citation or direct fragment reaches
that record. Its initial `open` state also makes sources visible without
JavaScript. Include `div#status` with `role="status"` for initialization errors.

## Actual-browser acceptance

| Surface | Check |
| --- | --- |
| Whole narrative | Every claim, visual and source matches the storyboard |
| Desktop | Deliberate rhythm and readable content; sticky elements do not cover text |
| Narrow | Natural flow at 390px and 320px; no horizontal page overflow |
| Navigation | Anchors, deep links, browser Back, current chapter and native scrolling |
| Inspectors | Every selection, scoped state, keyboard activation and clear labels |
| Context/sources | Disclosures open; cited records are reachable and legible |
| Accessibility | Landmarks, headings, alt text, visible focus, contrast, zoom |
| Reduced motion | No required animation or forced smooth scroll |
| Offline | Reload without network; embedded art and interactions work |
| No JavaScript | Argument and all inspector details remain readable |
| Print | All explanations/sources visible; no clipped or hidden content |
| Failures | Missing assets fail build; malformed interaction targets are reported |

Static checks enforce a markup/resource contract, not visual quality or audience
comprehension. Render the actual artifact and inspect multiple scroll positions,
not just its hero. Report unperformed checks honestly.

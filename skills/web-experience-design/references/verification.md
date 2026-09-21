# Verify the experience, not the screenshot

Use available browser and project test tools. Do not install a browser, add
analytics or start a paid service merely to initialize this workflow.
Missing capabilities are explicit limitations.

## Before and after

Preserve the baseline URL, state, source version or file hash, viewport, zoom,
data and relevant permissions. Agree task outcomes before changing the design.
Use the same meaningful tasks and content after the change.

For each task record:

- starting state and expected outcome;
- actual labels/destinations used;
- activations, mandatory openings and context changes;
- scrolling needed for reading versus searching;
- facts the reader must remember across views;
- result, errors, return state and evidence location.

Scroll distance in pixels or viewport heights requires viewport/zoom context.
Wheel-event counts are device-dependent. Automation timings are not human
usability timings. Qualitative visual judgment must have reasons, not a
self-assigned "premium" score.

## Execute the navigation contract

Test a direct link in a fresh page, reload, browser Back/Forward and explicit
return controls. Repeat through secondary CTAs and alternate audience/view
links; these often lose state even when the primary path works.

Verify query, filters, collection, selection and relevant position/focus.
Check empty results caused by text separately from empty results caused by
availability or permissions. Recovery should address the actual cause.

A source link may require authorization. Record whether the source was reached,
not merely whether an anchor exists. An unauthenticated 404 is not proof that a
private source is missing, and does not authorize bypassing access controls.

## Inspect the whole rendered result

| Area | Observable checks |
|---|---|
| Content | Required units reachable; caveats preserved; sources connected to claims; no invented facts or unexplained omissions |
| Navigation | Predictable labels, current location, direct links, functional controls and consistent return behavior |
| Responsive | Representative desktop and narrow viewports; long labels/data; transitions between layouts; no accidental overflow or lost tasks |
| Keyboard | Logical traversal, visible focus, no trap, correct widget keys, opening/closing behavior and focus return |
| Semantics | Landmarks/headings, labels, native controls, accessible names/states; charts and tables retain meaning |
| Visual craft | Hierarchy, typography, grouping, alignment, informative icons, meaningful imagery and coherent states |
| Motion | Appropriate feedback and continuity, interruptibility, reduced-motion equivalent, no content gated by animation |
| Robustness | Loading/error/empty/recovery paths where applicable, assets available, meaningful console/network errors resolved |
| Performance | Relevant available lab measurements with conditions; avoid unnecessary assets/dependencies and layout shift |
| Delivery | Actual offline/print behavior if required, not an assumption from the source code |

Capture representative views and intermediate states, open the screenshots and
confirm they show the intended content. Wait for assets and a known UI state,
not arbitrary long sleeps. A full-page thumbnail can hide wrapping, clipping
and unreadable details.

Do not mask overflow with clipping or truncation that makes required content
unreachable. Deliberate two-dimensional tables need usable boundaries, labels
and keyboard access rather than a blanket failure on horizontal scrolling.

## Accessibility distinctions

Use the applicable WCAG version and criteria; these examples are not a complete
conformance checklist:

- WCAG 2.2 AA 1.4.3: normal text contrast 4.5:1; large text 3:1, with exceptions.
  Large text means 18 pt or 14 pt bold, not simply 18 px.
- 1.4.11: applicable non-text controls/state indicators need 3:1 contrast.
- 1.4.4: text resize up to 200% without loss, within its defined scope.
- 1.4.10: reflow at 320 CSS px for vertical text content, with exceptions for
  content requiring a two-dimensional layout. A narrow viewport check alone
  is not a complete browser-zoom assessment.
- 2.5.8 AA: 24 by 24 CSS px targets or an applicable exception. Do not confuse
  this with the 44 by 44 enhanced AAA criterion or native platform units.
- 2.4.7 and 2.4.11: visible focus and focused components not entirely obscured.
- 2.3.3 animation from interactions is AAA; automatic moving content may have
  separate pause/stop/hide requirements. Respect the user's reduced-motion
  preference regardless of whether AAA is the declared target.

Automated scanners and accessibility snapshots do not replace a real screen
reader test. Report which assistive-technology checks actually ran.

## Print, offline and performance

For print, render all required content from the same data source, including
unmounted views and virtualized rows. Check pagination, table headers, clipping,
source information and a useful reading order in the actual output.
An emulated print stylesheet alone does not prove the document prints correctly.

For offline, distinguish a hosted offline-capable app, a local bundle and a
single `file://` HTML. Test the actual opening mode with the network unavailable;
relative fetches, modules, fonts and browser storage may behave differently.
Do not promise offline behavior from a successful localhost preview.

Core Web Vitals field targets are LCP <= 2.5 s, INP <= 200 ms and CLS <= 0.1
at the 75th percentile, segmented by device. Lab measurements are diagnostics,
not proof of those field percentiles. Do not invent field data or install
analytics without authorization.

## Exit and evidence

Every required task must have a result, not just a screenshot. Preserve all
required content, functional controls and applicable safety boundaries.
List unresolved blockers and unexecuted checks. Do not claim "all verified"
when browser, screen reader, print or offline checks were unavailable.

Fix related findings in coherent batches; repeat the affected tasks and
regressions. If a round resolves no material finding, or needs a new scope or
budget, stop and ask rather than silently extending the work.

Final output: outcome, meaningful changes, evidence scope and remaining limits.
Keep private logs, identifiers and sources out of public artifacts. Stop only
the temporary processes started for this work, using their recorded handles.

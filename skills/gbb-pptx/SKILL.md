---
name: gbb-pptx
description: >
  Plan, review and generate content-first PowerPoint (PPTX) presentations.
  Build audience-specific arguments, evidence-backed messages and storyboards
  before rendering with python-pptx; preserve approved content and existing themes.
  Confirm audience and deck structure; optionally iterate visuals in a browser
  with an explicit PowerPoint editability contract and early export proof.
  USE FOR: create PowerPoint, generate PPTX, make slide deck, build presentation,
  convert markdown to slides, pitch deck, report as PPTX, create slides,
  gbb-pptx, gbb deck, dark-themed deck, slide content, presentation storyline,
  presentation content audit, executive briefing, technical presentation,
  training slides, evidence review, speaker notes, slide storyboard.
  DO NOT USE FOR: direct editing of existing PPTX files (use `pptx` for file
  operations; use this skill for editorial review), PDF generation, Google Slides.
metadata:
  version: "2.3.0"
---

# GBB PPTX Deck Generator Skill

> **Renamed from `pptx` in v2.0.0** to avoid name collision with the upstream
> Anthropic-style `pptx` skill (which also creates presentations and supports
> reading/editing existing `.pptx` files). This GBB variant generates fresh
> dark/light-themed pitch decks from Markdown using `python-pptx`. Both can
> coexist at user scope — invoke this one with the `gbb-pptx` / "GBB deck" /
> "dark-themed deck" trigger phrases.

Build a presentation worth following before making a PowerPoint worth looking at.
Use `python-pptx` as the default generator for new files; retain the dark/light
presets and generation patterns below. Browser-first visual iteration is optional,
not a promise of lossless HTML-to-PPTX conversion. Content quality is not
established by a valid file or attractive slides.

## When to Use

Invoke this skill when the user asks to:
- Create a PowerPoint / PPTX presentation
- Generate a slide deck
- Convert markdown content into slides
- Build a pitch deck or report as PPTX
- Audit slide content, improve a storyline, or revise specific messages
- Prepare an executive briefing, technical explanation, training or read-ahead

## Prerequisites

Editorial work needs only accessible source material, not a Python installation.
For file generation, use an available `python-pptx` environment; install only
when missing and permitted by the host:

```bash
pip install python-pptx
```

## How It Works

Choose the smallest path that meets the request. Reuse existing decisions;
do not repeat discovery or impose a questionnaire.

| Request | Path |
|---|---|
| Audit or plan only | Inspect content and report slide-specific findings; do not rewrite files or render. |
| Targeted revision | Preserve unaffected slides and approved meaning; review changed claims and adjacent transitions. |
| New deck or substantial rewrite | Brief -> evidence -> storyline -> storyboard -> editorial review -> generation -> delivery check. |
| Render approved content | Preserve wording, facts and sources; proceed to generation. Flag material contradictions rather than silently rewriting. |

For an existing deck, use `pptx` to extract text, notes and relevant visuals.
Text extraction alone can miss a chart's message or image-only slide; mark such
content unreviewed until inspected. This skill owns editorial decisions, not
in-place PPTX manipulation. Do not run two generators against the same output.

### Establish the brief

Identify the audience, what they already know, their main question, and what
they should understand, decide or be able to do afterwards. Record duration,
language, source material, required content and delivery mode: **live talk**,
**standalone reading**, or both. Ask only material unanswered questions.
Label assumptions; do not invent audience research or decision authority.

For a new deck or structural rewrite, confirm the **audience and depth** with
the user or session coordinator before fixing the storyline. An explicit brief
or authorized coordinator handoff counts as confirmation; do not ask again.
If missing or contradictory, ask one focused question through the host's question
tool, or route it to the coordinator. Without an answer, keep the outline
provisional rather than silently deciding the audience.

Executive framing emphasizes decisions, implications and concise evidence.
Technical framing explains mechanisms, examples, interfaces and limits at the
depth needed for the task. Technical does not automatically mean more slides;
respect the time available. For mixed audiences, confirm the primary objective
and layer detail rather than averaging their needs.

A live slide supports a speaker; a read-ahead must explain itself. If both are
needed, derive two views from the same content, not one compromise with hidden
essential context. Honor the user's requested scope and output format.

### Build the argument

Read [content planning](references/content.md) for new storylines and
[evidence rules](references/evidence.md) when using factual claims or data.
Start from the audience's question, inspect the material, then formulate a
provisional central message. Test it against contrary evidence. Change or
qualify the message when the evidence disagrees; do not cherry-pick support.

Choose a structure for the actual purpose: decision, explanation, persuasion,
training or update. Write a title-only storyline before laying out slides.
Each step must answer a relevant question and connect to the next. Source
document headings are not automatically slide boundaries.

### Give a complete deck a beginning and an ending

For a new complete deck, default to **cover -> introduction/framing -> development
-> wrap-up/closing**. Use a cover with a meaningful title, presentation date and
speaker or team attribution. Confirm missing cover metadata; do not invent a
speaker/team or silently use today's date as the event date. Keep unresolved
fields in the draft brief, not placeholders in a supposedly finished file.
An explicit user-approved omission is valid.

The introduction establishes the problem, context or question and why the topic
matters; an agenda is optional. For executives, surface the recommendation early.
The development follows the purpose-specific argument. End with a substantive
takeaway and the relevant decision, next step, learning check or open question.
The wrap-up may itself be the closing slide; do not add a redundant "Thank you"
slide to satisfy a count. Put optional backup material after the main closing.

These are default roles, not a fixed number of slides or mandatory section
dividers. A short deck can combine roles; simplified slides are welcome. Do not
prepend a cover to an excerpt, retrofit a targeted revision, or restructure an
approved deck without a relevant request. See [content planning](references/content.md).

### Draft the storyboard

Use [the storyboard template](templates/storyboard.md), or equivalent fields
in an existing brief. Keep one content source of truth, not duplicate manifests.
For each substantive slide, specify its role, message, support, implication,
material caveat, source and placement between slide, notes and appendix.
See [worked examples](references/examples.md) for concrete rewrites.

Prefer message titles over topic labels when making an argument. The title
must not claim more than its support. Cover slides, agendas, questions and
exercises need not pretend to be factual assertions. One coherent message can
require several facts; do not enforce three bullets, ten slides or a word quota.

Choose a chart, diagram, comparison, example or text because it explains the
message. A decorative icon is not evidence. Keep claims intelligible to the
audience: define unfamiliar terms, show mechanisms, give concrete examples.
Never manufacture metrics, quotations, testimonials or citations to fill a slide.

### Review before rendering

Apply [editorial and delivery review](references/review.md). Check the title
sequence for gaps and repetition, each claim against its evidence, and whether
important objections, alternatives and limits remain visible. Run the voice
pass on titles, bullets, notes and alt text. Estimate timing
including explanation, demos and discussion; label estimates until rehearsed.

If sources are insufficient, identify the missing proof and its consequence.
Offer a qualified draft or targeted evidence request, not a fabricated conclusion.
Reuse prior approvals. For substantial new direction, settle material open
decisions before expensive rendering; an authorized end-to-end request does not
need a second routine approval gate. Audit-only work stops at findings.

### Generate and verify

Choose the rendering path before styling. Keep direct `python-pptx` generation
for routine work, approved layouts and short edits. If browser-first iteration
would help a new visual composition, read
[browser-first delivery](references/browser-first.md): agree what must remain
editable, prove export on representative slides early, then iterate and export
the complete deck. Do not assume arbitrary HTML/CSS converts into native shapes.
Do not silently replace an editable deliverable with slide-sized images.

For the direct path, generate a Python script using the patterns below, then
produce the `.pptx`.
Use approved branding; presets are options, not reasons to change the content.
Do not shrink away readability or silently drop qualifications to fit a layout.
Split or restructure overloaded slides while preserving the argument.

Reopen the generated file and compare its text, chart/table values and notes
with the storyboard. Verify numbers, sources and material caveats survived.
Inspect rendered slides for readability, clipping and misleading visual emphasis
when a renderer is available. A successful import is not visual QA. If rendering
or application opening is unavailable, report that limitation explicitly.
For browser-first work, the browser review is an intermediate check, not final
PowerPoint QA. Verify the exported slides, notes, fonts, slide count and agreed
editable objects; disclose any rasterized elements or fallback slides.

Deliver the requested artifact, not internal review chatter inside the deck.
State material unresolved content or delivery limitations. For editorial-only
requests, a reviewed storyboard is the output; do not generate an unwanted file.

## Core Patterns

### Slide Setup (16:9 Widescreen)

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.333)   # 16:9
prs.slide_height = Inches(7.5)
```

### Background Color

```python
def set_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color
```

### Text Box

```python
def text_box(slide, left, top, width, height, text,
             font_size=14, color=RGBColor(0xF1,0xF5,0xF9),
             bold=False, align=PP_ALIGN.LEFT, font="Segoe UI"):
    box = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height))
    box.text_frame.word_wrap = True
    p = box.text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font
    p.alignment = align
    return box
```

### Bullet List

```python
def bullet_list(slide, left, top, width, height, items,
                font_size=14, color=RGBColor(0xF1,0xF5,0xF9)):
    box = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, text in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"▸  {text}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.name = "Segoe UI"
        p.space_before = Pt(14)
    return box
```

### Rounded Rectangle Card

```python
def card(slide, left, top, width, height,
         fill=RGBColor(0x16,0x20,0x36),
         border=RGBColor(0x1E,0x29,0x3B)):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = border
    shape.line.width = Pt(1)
    return shape
```

### Accent Bar (decorative line)

```python
def accent_bar(slide, left, top, width=1.2, height=0.055,
               color=RGBColor(0x38,0x9F,0xF7)):
    s = slide.shapes.add_shape(
        1, Inches(left), Inches(top), Inches(width), Inches(height))
    s.fill.solid()
    s.fill.fore_color.rgb = color
    s.line.fill.background()
```

### Speaker Notes

```python
def add_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text
```

For content-first decks, notes should explain rather than simply repeat the
slide. Put the full source locator and optional spoken transition here, but keep
qualifications that change the headline's meaning on the slide itself.

> **Voice pass (required for new or materially edited copy).** Before content
> approval, and again after material copy edits, apply the voice row in
> [editorial review](references/review.md) to titles, bullets, notes and alt
> text in the deck's language. Where installed, use
> [`gbb-humanizer`](../gbb-humanizer/): its short-copy mode for titles,
> bullets and alt text (keep them concise and parallel; do not expand them),
> and full prose mode for notes (`gbb-seller-pitch.md` voice sample for
> seller decks). Preserve sources, numbers, uncertainty, quotations, technical
> names and approved wording; recheck meaning afterwards. After approval, voice
> changes beyond mechanical fixes follow the approval contract. A lexical scan
> can flag candidates; it does not prove natural copy.

### Save with Lock Detection

```python
import os, time
out = "output.pptx"
if os.path.exists(out):
    try:
        with open(out, "ab"): pass
    except PermissionError:
        ts = time.strftime("%Y%m%d-%H%M%S")
        out = f"output-{ts}.pptx"
prs.save(out)
```

## Theme Presets

These are optional rendering presets. Follow an existing brand or explicit user
choice; content review does not require a theme change.

### Dark Navy (ThreadLight style)
```python
BG      = RGBColor(0x0F, 0x17, 0x2A)  # Background
CARD    = RGBColor(0x16, 0x20, 0x36)  # Card fill
BLUE    = RGBColor(0x38, 0x9F, 0xF7)  # Primary accent
CYAN    = RGBColor(0x06, 0xB6, 0xD4)  # Secondary accent
WHITE   = RGBColor(0xF1, 0xF5, 0xF9)  # Primary text
MUTED   = RGBColor(0x94, 0xA3, 0xB8)  # Secondary text
DIM     = RGBColor(0x64, 0x74, 0x8B)  # Tertiary text
GREEN   = RGBColor(0x22, 0xC5, 0x5E)  # Success
AMBER   = RGBColor(0xF5, 0x9E, 0x0B)  # Warning/highlight
RED     = RGBColor(0xEF, 0x44, 0x44)  # Error/negative
```

### Light Corporate
```python
BG      = RGBColor(0xFF, 0xFF, 0xFF)
CARD    = RGBColor(0xF8, 0xFA, 0xFC)
BLUE    = RGBColor(0x00, 0x78, 0xD4)  # Microsoft Blue
WHITE   = RGBColor(0x1A, 0x1A, 0x2E)  # Dark text on light
MUTED   = RGBColor(0x60, 0x60, 0x60)
```

## Slide Layout Recipes

These recipes are rendering starting points, not narrative structures. A layout,
decorative accent or three-item example does not determine what must be said.
For live projection, adapt text size to the actual room and viewing distance.

### Title Slide
- Include the confirmed presentation date and speaker or team attribution
- Apply the complete-deck default above; do not invent missing metadata
- Accent bar at ~30% from top
- Title: 44-48pt bold
- Tagline: 20-22pt accent color
- Subtitle: 14pt muted
- Footer: 11pt dim at bottom

### Content Slide with Bullets
- Accent bar at top-left
- Title: 28-30pt bold
- Bullet list: 14-15pt with ▸ prefix and 14-18pt spacing
- Optional highlight quote at bottom in accent color

### Two-Column Comparison
- Two side-by-side cards (each ~5.4" wide on 16:9)
- Column headers in accent colors
- ✓ / ✗ prefixes for positive / negative items

### Card Grid (2×3 or 2×2)
- Cards with title (accent color, bold) + description (muted)
- Column spacing: `x = margin + col * card_pitch`

### Timeline / Steps
- Numbered badge cards (accent fill)
- Title + description on same row
- Optional time value right-aligned

## Tips

- Use `Inches()` for all positioning — never raw EMU values
- 16:9 canvas is 13.333 × 7.5 inches; keep content within 1" margins
- Font hierarchy: Title 28-48pt → Heading 16-20pt → Body 12-15pt → Caption 10-11pt
- Use `word_wrap = True` on all text frames
- Keep text boxes slightly taller than needed to prevent clipping
- Reopen with `python-pptx` for file integrity; also perform the content and rendered checks above
- For locked files (open in PowerPoint), auto-version the output filename

## Example: Complete Slide

```python
slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout
set_bg(slide, BG)
accent_bar(slide, 1, 0.6)
text_box(slide, 1, 0.8, 11, 0.6, "Slide Title Here", 30, WHITE, True)
bullet_list(slide, 1, 1.7, 11, 4, [
    "First bullet point with key insight",
    "Second bullet point with supporting data",
    "Third bullet point with call to action",
], 15, WHITE)
card(slide, 1, 5.5, 11.3, 1)
text_box(slide, 1.4, 5.65, 10.5, 0.7,
         '"Closing quote or key takeaway"', 14, CYAN)
add_notes(slide, "Speaker notes with source links here")
prs.save("output.pptx")
```

This is a mechanical rendering example, not a content-quality exemplar. Replace
its placeholders with reviewed storyboard content; use the worked examples for
message, evidence and caveat choices.

## Validation boundaries

The [acceptance scenarios](tests/scenarios.md) exercise editorial decisions;
automated contract checks do not prove model behavior or audience comprehension.
Preserve the historical generation check in
[the validation record](references/last_validated.yaml). Do not claim a
before/after improvement on a real deck without the original and an observed
comparison. Source changes are not automatic installation or release.

## Reference map

Load only the relevant reference; do not read every file for a two-slide edit.

| Reference | Use |
|---|---|
| [Content planning](references/content.md) | Audience questions, narrative choices and content allocation |
| [Evidence](references/evidence.md) | Provenance, calculations, uncertainty and research basis |
| [Examples](references/examples.md) | Before/after rewrites with reasoning and limits |
| [Review](references/review.md) | Editorial checks, severity and post-render preservation |
| [Browser-first delivery](references/browser-first.md) | Optional HTML iteration, editability, early export proof and model-selection limits |
| [Storyboard](templates/storyboard.md) | Reusable minimal content contract |
| [Acceptance scenarios](tests/scenarios.md) | Behavioral probes and actual-output acceptance |

## See Also

| Skill | Use When |
|-------|----------|
| [**gbb-humanizer**](../gbb-humanizer/) | **Voice pass** before content approval and after material copy edits: short-copy mode for titles, bullets and alt text (concise, parallel, not expanded), prose mode for speaker notes. Use the `gbb-seller-pitch.md` voice sample for seller decks. Covers English and Italian tells. |
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Generates the SpecKit + `overview.html` that this deck's slides typically narrate — the deck is often a re-projection of the same content for an audience that prefers slides to long-form HTML. |

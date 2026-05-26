---
name: gbb-pptx
description: >
  Generate professional PowerPoint (PPTX) presentations using python-pptx
  (the AI Apps GBB dark/light pitch-deck generator).
  USE FOR: create PowerPoint, generate PPTX, make slide deck, build presentation,
  convert markdown to slides, pitch deck, report as PPTX, create slides,
  gbb-pptx, gbb deck, dark-themed deck.
  DO NOT USE FOR: editing existing PPTX files (use the upstream `pptx` skill),
  PDF generation, Google Slides.
metadata:
  version: "2.0.1"
---

# GBB PPTX Deck Generator Skill

> **Renamed from `pptx` in v2.0.0** to avoid name collision with the upstream
> Anthropic-style `pptx` skill (which focuses on reading/editing existing
> `.pptx` files via markitdown). This GBB variant generates fresh
> dark/light-themed pitch decks from Markdown using `python-pptx`. Both can
> coexist at user scope — invoke this one with the `gbb-pptx` / "GBB deck" /
> "dark-themed deck" trigger phrases.

Generate professional, dark-themed PowerPoint (PPTX) presentations using `python-pptx`.

## When to Use

Invoke this skill when the user asks to:
- Create a PowerPoint / PPTX presentation
- Generate a slide deck
- Convert markdown content into slides
- Build a pitch deck or report as PPTX

## Prerequisites

```bash
pip install python-pptx
```

## How It Works

1. **Define slide content** — either from user instructions or by reading a markdown file
2. **Generate a Python script** using the patterns below
3. **Run the script** to produce the `.pptx` file

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

> **Polish pass (optional but recommended).** Speaker notes are pure prose
> read aloud during the demo — AI-prose tells degrade credibility. After
> the deck is assembled, run [`gbb-humanizer`](../gbb-humanizer/) over the
> notes text using the pre-canned `gbb-seller-pitch.md` voice sample.
> **Do not** humanize slide bullets or titles — those need to stay punchy
> and parallel; the humanizer's section-aware mode skips them by default.

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

### Title Slide
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
- Test with `python -c "from pptx import Presentation; ..."` to validate
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

## See Also

| Skill | Use When |
|-------|----------|
| [**gbb-humanizer**](../gbb-humanizer/) | **Polish pass** for speaker notes after the deck is generated. Section-aware mode skips slide bullets and titles (which need to stay punchy and parallel) and only rewrites the prose inside `notes_slide.notes_text_frame.text`. Use the pre-canned `gbb-seller-pitch.md` voice sample. |
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Generates the SpecKit + `overview.html` that this deck's slides typically narrate — the deck is often a re-projection of the same content for an audience that prefers slides to long-form HTML. |

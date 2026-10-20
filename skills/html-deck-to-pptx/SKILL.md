---
name: html-deck-to-pptx
description: >
  Convert an existing HTML slide deck (reveal.js, section.slide or .slide
  layouts, keyboard-driven decks) into a native, editable PowerPoint file:
  real text runs, shapes, linear gradients, tables, bullets, hyperlinks,
  speaker notes and embedded videos, with only icons and diagrams rasterized.
  Includes automatic visual QA that renders the PPTX in PowerPoint or
  LibreOffice and ranks slides by difference from the HTML. Local Node.js and
  Playwright tooling; no Azure resources.
  USE FOR: html to pptx, html deck to powerpoint, convert slides to editable
  pptx, export reveal.js to powerpoint, make the HTML deck reusable in
  PowerPoint, share deck as pptx, recycle slides.
  DO NOT USE FOR: planning or building a deck from scratch (use gbb-pptx or
  html-presentation), image-only PDF export, editing an existing PPTX file.
metadata:
  version: "1.0.0"
---

# HTML deck → editable PowerPoint

One command converts every slide of an HTML deck into native PowerPoint objects, then a second
command proves the result visually. Work from evidence: run QA, look at the worst sheets, fix, rerun.

## Setup (once per machine)

```bash
S="$SKILL_DIR/scripts"   # SKILL_DIR = this skill's absolute directory
[ -d "$S/node_modules" ] || (cd "$S" && npm ci --silent)
```

Needs Node ≥ 18. A browser is resolved automatically: Playwright Chromium, else installed
Microsoft Edge, else Google Chrome. Optional: `ffmpeg` (video re-encode/captions), `pdftoppm`
(poppler) plus Microsoft PowerPoint (macOS) or LibreOffice for QA. Everything runs locally:
no Azure resources, models or network services are used beyond the npm install and any remote
assets the deck itself loads.

## Workflow

1. **Convert** (the input folder is served read-only over a local HTTP server; nothing is written next to it):
   ```bash
   node "$S/html2pptx.mjs" deck.html -o out/Deck.pptx [options]
   ```
   Read the summary: slide count, navigation used (`native`, `scroll`, `keys`, `forced`),
   font mapping, warnings for slides with no text or isolated via CSS.
2. **QA**: `node "$S/qa.mjs" out/Deck.pptx` renders the PPTX, compares every slide with the HTML
   screenshot taken during conversion, writes `out/Deck.work/qa/sheet-NN.png` (HTML left, PPTX
   right) and prints the most different slides. Typical healthy values: 2–8% (anti-aliasing and font
   metrics). Look at the sheets of the top slides yourself — a low score cannot detect slides that are
   empty in both renders, which is why the converter warns about empty slides.
3. **Fix** with options (below) or small HTML/CSS changes in a copy of the deck, rerun 1–2. Use
   `--slides 3,7-9` to iterate quickly on a few slides.
4. **Deliver**: offer the full file and, when videos are large, a `--no-video` variant (poster images,
   usually a few MB) for people who only want to recycle slides. State what is native and what is an
   image, and carry over any confidentiality label of the source deck.

## Options

| Option | Use |
|---|---|
| `--selector CSS` | Slides are not auto-detected (default tries reveal.js, `section.slide`, `.slide`, `[data-slide]`, …) |
| `--size WxH` | Override design size (default: slide/stage layout size; 16:9 → 13.333×7.5 in) |
| `--slides 1,3,5-8` | Convert a subset |
| `--hide CSS` | Deck chrome that still shows (nav arrows, counters, watermarks) |
| `--player-selector CSS` | Wrapper of a custom video player (default: closest `.player`/`.video` around a `<video>`) |
| `--no-video` | Poster image instead of embedded video |
| `--burn-captions` | Burn `<track>` VTT or `data-cues` captions into the embedded video (PowerPoint has no portable caption track) |
| `--video-speed 1.25` / `--video-crf 28` | Re-time / re-encode embedded videos |
| `--font-map "Inter=Aptos,Roboto=Arial"` | Map web fonts to installed fonts |
| `--keep-fonts` | Keep original font names (recipients must have them installed) |
| `--font-fallback NAME` | Font for generic families (default Segoe UI) |
| `--no-builds` | Keep build steps/fragments hidden (default shows the final state) |
| `--settle MS` | Longer wait for decks with slow transitions (default 350) |
| `--browser msedge` | Force a browser |
| `--title/--author/--company/--subject` | Document properties |

## What becomes what

- **Native & editable**: text (runs, bold/italic/underline, colour, letter-spacing, highlights,
  hyperlinks incl. in-deck `#slide` links), single linear-gradient fills, gradient borders, gradient
  text, rounded rectangles/ovals, borders (dashed), drop shadows, tables (cell fills, padding, bottom
  borders, spans), bullets/numbering, speaker notes (`aside.notes`, `.notes`, `data-notes`,
  `.notes [data-for=N]`), embedded MP4 with poster.
- **Images**: `<svg>`, `<img>`, `<canvas>`, iframes, elements with filters/masks/transforms/clip-path,
  multi-layer or radial/conic backgrounds, pseudo-element decorations. Blend-mode/masked images are
  baked into the slide background image.
- **Fonts**: each CSS stack resolves to its first Office-safe font (Segoe UI, Aptos, Calibri, Georgia,
  Palatino Linotype, Consolas, …); otherwise serif → Georgia, mono → Consolas, sans → fallback.
  Segoe weights map to Segoe UI Light/Semilight/Semibold. Single-line table cells are shrunk
  slightly when the substitute font would wrap.

See [references/fidelity.md](references/fidelity.md) for limitations, authoring tips that maximise
editability and troubleshooting.

## Self-test

`tests/fixture/deck.html` is a self-contained synthetic deck (gradient cards with SVG icons,
bullets, numbering, a table, in-deck and external links, speaker notes). Convert it and run QA to
check a new machine before converting real decks:

```bash
node "$S/html2pptx.mjs" "$SKILL_DIR/tests/fixture/deck.html" -o /tmp/h2p-fixture/Fixture.pptx
node "$S/qa.mjs" /tmp/h2p-fixture/Fixture.pptx
```

Expect 4 native slides, 3 rasterized icons and per-slide differences of a few percent.

## Rules

- Never modify the source deck or its repository; convert from it and write outputs elsewhere.
- Do not claim fidelity without looking at the QA sheets; report residual differences honestly.
- Large outputs are usually videos: check `--video-crf`, offer `--no-video`.
- Decks often contain internal or confidential material: keep the PPTX in the same distribution scope
  as the source and say so when handing it over.

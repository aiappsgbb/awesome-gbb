# Fidelity, authoring tips and troubleshooting

## How the converter works

1. Serves the deck folder on `127.0.0.1` (Range-capable, so videos load) and opens it in headless
   Chromium at the deck's design size with device scale factor 2.
2. Detects slides, then shows each one using, in order: reveal.js API or `#id` hash → document scroll
   → keyboard (`Home`, `ArrowRight`) → CSS isolation (last resort; also reveals transparent build
   steps). Animations are finished and transitions disabled; deck chrome outside the slide is hidden.
3. Waits until the slide frame is stable, screenshots it as the QA reference, walks the DOM and emits
   native items. Elements PowerPoint cannot express are screenshotted in isolation (transparent PNG,
   or JPEG when opaque). The slide background is captured with all content hidden.
4. Builds the PPTX with pptxgenjs, injects DrawingML gradients (fills, lines, text), deduplicates
   identical media.

Geometry: 1 CSS px = 13.333 in / design width; font px → pt = 960 / design width (16:9).
Single-line text is centred on its CSS line box (font-metric independent); multi-line text uses a
line-spacing multiple plus a correction for PowerPoint's handling of spacing below 100%.

## Known limitations

- Radial/conic/multi-layer gradients, filters, blend modes, masks, transforms → images.
- `backdrop-filter` blur is dropped (the fill is kept).
- Text inside SVG stays part of the SVG image (not editable).
- Web fonts are substituted unless installed for PowerPoint (`--keep-fonts`); wrapping may differ
  slightly in multi-line text. Use `--font-map` to a metric-compatible font when a deck depends on it.
- CSS columns, `writing-mode`, text on paths and per-character effects are approximated.
- Videos: MP4/H.264 embeds everywhere; other formats need ffmpeg. Captions only via `--burn-captions`.
- Interactive state (tabs, accordions, hover) is captured as currently displayed.
- Build steps are shown in their final state; PowerPoint animations are not generated.

## Authoring tips for decks that convert well

- Use real text elements (not text in SVG/canvas/images) for anything people will edit.
- Prefer single `linear-gradient` backgrounds and simple borders/shadows on cards.
- Keep slides a fixed design size (e.g. 1600×900) scaled by the deck, one element per slide.
- Put speaker notes in `<aside class="notes">` inside each slide.
- Give slides `id`s (hash navigation is the fastest, most reliable path) and in-deck links `href="#id"`.
- Use MP4 (H.264/AAC) for video, with a `poster`.
- Use fonts with Office equivalents (Segoe UI, Aptos, Calibri, Georgia, Consolas).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No slides found` | `--selector` with the slide element selector |
| Only first slide has content, others empty/`forced` | Deck navigation not detected: check it reacts to `ArrowRight`; increase `--settle`; otherwise `--selector` on the slide element and CSS isolation shows content |
| Nav arrows/counter visible in PPTX | `--hide ".nav, .counter"` |
| Content cut or misplaced on a scaled stage | `--size WxH` with the deck's design size; increase `--settle` |
| Text wraps differently | `--font-map` to the font actually used, or `--keep-fonts` if recipients have it |
| Big file | `--video-crf 30`, `--no-video` variant |
| QA: `render failed` | macOS: grant Automation permission for PowerPoint, or use `--renderer libreoffice` |
| Browser fails to launch | `cd scripts && npx playwright install chromium`, or `--browser msedge` |

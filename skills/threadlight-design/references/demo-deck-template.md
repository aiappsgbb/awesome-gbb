# `demo-deck.html` — Cinematic Talk Deck

> **Read this first**: this document is **NOT a template**. It's a **kit of
> parts** for building a single-file cinematic talk deck tailored to ONE live
> customer moment. Reusing the same 10–14 slides for every PoC is the fastest
> way to make a room feel cheap, generic, and AI-generated. The grammar is
> stable. The copy, numbers, and emphasis are bespoke.

`demo-deck.html` is the **LIVE TALK artifact**: keyboard-paced, full-screen,
and designed to be spoken over in **≤ 8 minutes**. It is **NOT** a brief. It is
**NOT** a dossier. It is **NOT** a crib sheet. It **REPLACES** `overview.html`,
because `overview.html` turned out to be the wrong shape for a live customer
moment.

> **Primary customer-facing artifact.** If a threadlight PoC is demoable, this
> is the thing the customer should remember. `overview.html`, `experience.html`,
> `prep-guide.html`, and `SPEC.md` support it; they do not outrank it in the
> room.

## When to generate

- Any threadlight PoC with `internal-no-demo: false` (the default). **Mandatory.**
- Any workshop, exec readout, or seller-led meeting where someone will
  full-screen the browser and talk over it.
- Any PoC that needs a clean replacement for legacy `overview.html`.

Skip only when:

- `internal-no-demo: true`
- The artefact is strictly internal and no live customer moment exists
- A separate instruction explicitly says “no deck”

---

## The 10–14 slide grammar

Think in **grammar**, not recipe. The VF3 v4 deck that finally stuck landed at
12 slides because it split the live handoff into a cue slide plus a pure-black
holding slide. VF3 v8 then added a preview-answer insurance slide and a
hub-spoke architecture slide. Most PoCs still land at 11 or 12. Ten is
acceptable only when one conditional slide is collapsed into its neighbor.

> **Kit of parts, not a recipe.** The row order below is the stable grammar.
> The exact copy, numbers, reveals, and emphasis come from the SPEC, AGENTS.md,
> and the actual live path you intend to show.

| # | Slide type | Status | Purpose | SPEC clauses that activate it | Recommended length | Recommended reveals | What NOT to put on it |
|---|------------|--------|---------|--------------------------------|--------------------|--------------------|-----------------------|
| 1 | Cold-open | **Mandatory** | Brandmark + journey name + headline. Silence the room fast. A dark cinematic hero **or** a brand-flood hero are both valid. | Every deck; pull customer name, journey name, and the sharpest claim from `SPEC § 1`. | 1 headline + optional 1 support line; ~15–25 seconds. | 2 states max; dark hero with brand-accent gradient is valid. | No paragraphs, architecture, dates, seller names, or licensed logo. |
| 2 | Context | **Conditional** | Restate the customer's stated goal so the deck feels anchored to the brief. | `SPEC § 1` goal / problem statement / mission. | 1 quote, contrast, or 2-panel setup; ~20–30 seconds. | 2–4 reveals. | No personas. No platform diagram. |
| 3 | Friction | **Conditional** | Quantify the current-state tax with **3 numeric pain points**. This is one of the mandatory brand-flood panels. | `SPEC § 3` business rules, pain-point logs, current-state constraints. | 3 numbers + 1 foot line; ~30–40 seconds. | 3–6 reveals. | No invented stats. No anecdotal persona scene. |
| 4 | The shift | **Conditional** | Show before / after, today / from now, or current / target state. Optional place to spend the fourth brand-flood panel if the story needs lift. | `SPEC § 9` functional success criteria. | 2–3 cards or panels; ~25–40 seconds. | 3–6 reveals. | No roadmap promises. No delivery plan. |
| 5 | Live-demo cue | **Mandatory** | Hand the room from talk track to the live invocation: “Now let's watch.” | Any PoC with `internal-no-demo: false` and a real demo path. | 1 short cue; split into cue + pure-black holding card only if you need clean alt-tab time. | 1–3 reveals. | No screenshots, setup monologue, or hard sell. |
| 6 | Skill chain | **Mandatory** | Decode what just happened into an exact tool sequence. | `AGENTS.md` **Foundry tools required** + `SPEC § 6` tool contracts. | 1 chain + 3–4 callouts; ~30–45 seconds. | Reveal chain in groups, callouts last. | No invented tool names, pseudo-tools, or raw transport labels. |
| 7 | Platform stack | **Mandatory** | Show the 6-layer cake that makes the demo credible. | Architecture / deployment clauses, surfaces, tools, memory, and observability sections. | 6 layers, read top-down; ~30–45 seconds. | 4–6 reveals. | No bare-text pills. No vendor soup. |
| 8 | Scale | **Conditional** | Prove this is a pattern, not a one-off. Use **3 numeric horizons**. Optional place to spend the fourth brand-flood panel. | Scale targets, nonfunctional sections, phased posture, future-state clauses. | 3 horizon blocks; ~25–35 seconds. | 3–6 reveals. | No effort estimate or firm dates. |
| 9 | Posture | **Conditional** | Rhythm break: light-inverse governance / trust posture slide. Optional place to spend the fourth brand-flood panel if you need more heat before the close. | `SPEC § 11` governance posture and hard guardrails. | 4–6 pills; ~20–30 seconds. | 3–6 reveals. | No policy essay or legal wall of text. |
| 10 | Follow-up proposal | **Mandatory** | Put 3 concrete next steps on the table so the room has something specific to react to. This is one of the mandatory brand-flood panels. | Every external demo; pull the steps from the strongest post-demo technical path. | 3 steps max, then stop talking. | 3–5 reveals. | No delivery commitment, dates, effort, or “pick one journey.” |
| 11 | Close | **Mandatory** | Bookend the open: brandmark echo + “Thank you.” + Microsoft × Customer co-brand bar. This is one of the mandatory brand-flood panels. | Every deck. | 1 beat; ~5–10 seconds. | 2–3 reveals. | No seller names, emails, phone numbers, or CTA. |

Practical packaging rules:

- **11 slides** is the default shape.
- **12–14 slides** are acceptable when the Preview answer, Architecture, and/or
  the row-5 cue split earn their keep.
- **10 slides** is acceptable only when one conditional slide is merged into an
  adjacent conditional slide. Never drop rows **1, 5, 6, 7, 10, or 11**.

> Dark hero with brand-accent gradient is a valid cinematic opening (VF3
> reference deck uses this). Brand-flood panels must still hit **≥ 4 total**:
> **friction + follow-up proposal + close** are mandatory, plus at least one
> more chosen from **hero, the shift, scale, or posture**.

---

## Preview answer slide (visual insurance)

**When to use.** Conditional but recommended when there's a live demo. Put it
between **The shift** (slide 4) and the **Live-demo cue** (slide 5/6).

**Purpose.** Show what a real answer looks like **before** the live demo. If
the demo wobbles, flip back to this slide.

**Structure**
- `.preview-panel` — dark background, rounded corners, visible border.
- `.preview-q` — italic question.
- `.preview-a` — answer body with `<strong>` highlights.
- `.preview-cite` — citation block with a `.pill` version badge + source
  reference.
- Footer line: `Citation. Version. Source page. Every time — not sometimes.`

**Speaker note guidance.** “This sets the audience's expectation. If the live
demo wobbles later, they've already seen a real answer.”

---

## CSS token table

The deck works because a small set of tokens does a lot of work: **brand flood**,
**neutral dark**, **one light inverse**, **one safe brandmark**, and **one
consistent chrome system**.

### Root tokens (verbatim from VF3)
```css
    :root {
      /* === Vodafone Three brand-aligned palette === */
      --vf-red:        #E60000;
      --vf-red-bright: #FF2A2A;
      --vf-red-dark:   #A00000;
      --vf-red-deep:   #4d0606;
      --bg-0:          #0A0A0A;
      --bg-1:          #141414;
      --bg-2:          #1F1F1F;
      --light-bg:      #FAFAFA;
      --light-bg-2:    #F1F1F1;
      --text:          #FFFFFF;
      --text-dark:     #0A0A0A;
      --muted:         #B3B3B3;
      --muted-dark:    #5C5C5C;
      --line:          rgba(255, 255, 255, 0.12);
      --line-dark:     rgba(10, 10, 10, 0.12);

      /* MS corporate quadrant (logo only) */
      --ms-orange: #F25022;
      --ms-green:  #7FBA00;
      --ms-blue:   #00A4EF;
      --ms-yellow: #FFB900;

      --display: "Inter", "SF Pro Display", "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
      --mono:    "JetBrains Mono", "SF Mono", "Cascadia Mono", Consolas, "Liberation Mono", monospace;
      --ease:     cubic-bezier(.21, .61, .35, 1);
      --ease-out: cubic-bezier(.16, 1, .3, 1);
    }
```

These are the canonical VF3 root tokens. For another customer, keep the **roles**
and swap only the brand values.

| Token | VF3 value | Generic alias / meaning | Use in the deck |
|-------|-----------|-------------------------|-----------------|
| `--vf-red` | `#E60000` | `--brand-primary` | Primary brand flood, glyph accent, progress bar start. |
| `--vf-red-bright` | `#FF2A2A` | `--brand-bright` | Highlight edge, reveal emphasis, progress bar end. |
| `--vf-red-dark` | `#A00000` | `--brand-dark` | Gradient shadow edge, deeper flood base. |
| `--vf-red-deep` | `#4d0606` | `--brand-deep` | Darkest brand field. |
| `--bg-0` | `#0A0A0A` | `--deck-black` | Global dark substrate. |
| `--bg-1` | `#141414` | `--deck-charcoal` | Dark gradient top / neutral panel lift. |
| `--bg-2` | `#1F1F1F` | `--deck-charcoal-2` | Optional secondary dark stop. |
| `--light-bg` | `#FAFAFA` | `--deck-paper` | Light-inverse posture / shift slides. |
| `--light-bg-2` | `#F1F1F1` | `--deck-paper-2` | Gradient tail for the light slide. |
| `--text` | `#FFFFFF` | `--text-light` | Default dark-slide text. |
| `--text-dark` | `#0A0A0A` | `--text-dark` | Default light-slide text. |
| `--muted` | `#B3B3B3` | `--muted-light` | Secondary copy on dark slides. |
| `--muted-dark` | `#5C5C5C` | `--muted-dark` | Secondary copy on light slides. |
| `--line` | `rgba(255, 255, 255, 0.12)` | `--line-light` | Dark-slide dividers and borders. |
| `--line-dark` | `rgba(10, 10, 10, 0.12)` | `--line-dark` | Light-slide borders and pill outlines. |
| `--ms-orange` | `#F25022` | Microsoft quadrant | MS logo only. |
| `--ms-green` | `#7FBA00` | Microsoft quadrant | MS logo only. |
| `--ms-blue` | `#00A4EF` | Microsoft quadrant | MS logo only. |
| `--ms-yellow` | `#FFB900` | Microsoft quadrant | MS logo only. |
| `--display` | `Inter` stack | Display font stack | Headlines and deck-wide sans. |
| `--mono` | `JetBrains Mono` stack | Monospace font stack | Tool names, counters, HUD, labels. |
| `--ease` | `cubic-bezier(.21, .61, .35, 1)` | Standard ease | Slide opacity / UI chrome movement. |
| `--ease-out` | `cubic-bezier(.16, 1, .3, 1)` | Snappier ease-out | Reveals and scale-in transitions. |

Map the brand quartet explicitly:
```css
:root {
  --brand-primary: var(--vf-red);
  --brand-bright: var(--vf-red-bright);
  --brand-dark: var(--vf-red-dark);
  --brand-deep: var(--vf-red-deep);
}
```

### Structural hooks

| Hook | What it does | Canonical guidance |
|------|--------------|-------------------|
| `.bg-{brand}-flood` | Full-bleed brand panel | Use for the slides that need pressure or bookend force. Think hero / friction / follow-up proposal / close. |
| `.bg-light` | Light-inverse rhythm break | Use once, maybe twice. It should feel like a breath, not a second theme. |
| `.reveal.d1` … `.reveal.d6` | Staged entrance classes | VF3 uses 0.08–0.84s delays. Tune to the brand, but keep it human. |
| `data-states="N"` | Per-slide sub-state machine | Lets one slide advance through N reveal states before the controller moves on. |
| `.cobrand` | Hero / follow-up top chrome | Always Microsoft × Customer. Right-hand label stays anonymous. |
| `.brandmark` | Safe customer logo substitute | Monogram + white circle + brand flood card. |
| `.layer .tech` + `.ico` | Platform stack pill grammar | Every pill gets an icon prefix. Bare text pills look unfinished. |
| `.preview-panel` / `.preview-q` / `.preview-a` / `.preview-cite` | Visual-insurance answer shell | Use before a live demo to show the citation pattern the room should expect. |
| `.arch-diagram` / `.arch-hub` / `.arch-connector` / `.arch-spoke` | Hub-spoke architecture frame | Left hub, vertical access-contract connector, right pilot spoke. |
| `.arch-gov-row` / `.arch-gov-card` / `.gov-link` | Governance card strip | 3 equal cards under the diagram, each with an explicit repo link. |
| `.discussion-row` + `.discussion-card` | 3-card closing layout | Reuse for follow-up proposal steps (or legacy discussion prompts). Equal weight. |
| `.close-brandmark` / `.close-thanks` / `.close-cobrand-block` / `.close-stack` / `.slide.is-center` | Final-slide bookend system | Keep the close sparse, centered, and anonymous. |
| `.note` + `[data-for="N"]` | Speaker notes mapping | Exactly one note per slide. `data-for` must equal slide index. |

Canonical background + reveal pattern:
```css

.bg-red-flood::before {
  content: ""; position: absolute; inset: 0; z-index: -1;
  background:
    radial-gradient(1400px 800px at 50% 40%, rgba(255, 50, 50, 0.18), transparent 60%),
    linear-gradient(135deg, var(--vf-red) 0%, var(--vf-red-dark) 100%);
}
.bg-light::before {
  content: ""; position: absolute; inset: 0; z-index: -1;
  background:
    radial-gradient(900px 500px at 20% 18%, rgba(230, 0, 0, 0.06), transparent 60%),
    linear-gradient(180deg, var(--light-bg) 0%, var(--light-bg-2) 100%);
}
.reveal { opacity: 0; transform: translateY(24px); transition: opacity .7s var(--ease-out), transform .8s var(--ease-out); }
.slide.is-active .reveal.in { opacity: 1; transform: translateY(0); }
.reveal.d1 { transition-delay: 0.08s; }
.reveal.d2 { transition-delay: 0.20s; }
.reveal.d3 { transition-delay: 0.34s; }
.reveal.d4 { transition-delay: 0.50s; }
.reveal.d5 { transition-delay: 0.66s; }
.reveal.d6 { transition-delay: 0.84s; }
```

Sub-state example:
```html
<section class="slide is-active bg-dark" data-states="2">
  <div class="brandmark reveal d1">…</div>
  <h1 class="display reveal d2">…</h1>
  <p class="lead reveal d3 state-2">This line appears on the second Space press.</p>
</section>
```

---

## JS controller pattern

Keep the controller tiny, deterministic, and **slide-count agnostic**. The VF3
deck works because the script does **not** hard-code a slide total; it asks the
DOM how many slides exist, then updates the counter, notes, and progress bar
from that.

### Keyboard map

| Key | Action |
|-----|--------|
| `Space` / `→` / `PageDown` | Advance slide or sub-state |
| `←` / `PageUp` | Go back one slide or sub-state |
| `F` | Toggle fullscreen |
| `S` | Toggle speaker notes |
| `B` / `.` | Toggle blackout |
| `0–9` | Jump directly (`0` means slide 10) |
| `Home` / `End` | Jump to first / last slide |
| Click stage | Advance |

### Canonical controller (extracted from VF3)
```js
  (function () {
    var stage = document.getElementById('stage');
    var slides = Array.prototype.slice.call(stage.querySelectorAll('.slide'));
    var notes = document.querySelectorAll('.notes .note');
    var notesIdx = document.getElementById('notes-idx');
    var curEl = document.getElementById('cur');
    var totEl = document.getElementById('tot');
    var progress = document.getElementById('progress');
    var body = document.body;

    var current = 0;
    var subState = 1;
    var max = slides.length;
    totEl.textContent = String(max).padStart(2, '0');

    function maxStateOf(idx) {
      var d = slides[idx].getAttribute('data-states');
      return d ? parseInt(d, 10) : 1;
    }

    function applyReveal() {
      var slide = slides[current];
      var els = slide.querySelectorAll('.reveal');
      els.forEach(function (el) {
        var stateMatch = (el.className.match(/state-(\d+)/) || [])[1];
        if (!stateMatch || parseInt(stateMatch, 10) <= subState) {
          el.classList.add('in');
        } else {
          el.classList.remove('in');
        }
      });
    }

    function render() {
      slides.forEach(function (s, i) {
        s.classList.toggle('is-active', i === current);
        s.classList.toggle('is-prev', i < current);
      });
      // reset reveals on outgoing slides so they re-animate next time
      slides.forEach(function (s, i) {
        if (i !== current) {
          s.querySelectorAll('.reveal').forEach(function (el) { el.classList.remove('in'); });
        }
      });
      requestAnimationFrame(applyReveal);

      // HUD
      curEl.textContent = String(current + 1).padStart(2, '0');
      progress.style.width = ((current + 1) / max * 100) + '%';

      // light-slide counter contrast
      var isLight = slides[current].classList.contains('bg-light');
      document.querySelector('.counter').style.color = isLight ? 'var(--muted-dark)' : 'var(--muted)';
      document.querySelector('.counter').querySelector('b').style.color = isLight ? 'var(--text-dark)' : '#FFFFFF';

      // speaker note
      notesIdx.textContent = String(current + 1);
      notes.forEach(function (n) {
        n.classList.toggle('is-active', parseInt(n.getAttribute('data-for'), 10) === current + 1);
      });

      try { sessionStorage.setItem('vf3-deck-slide', String(current)); } catch (e) {}
    }

    function next() {
      var ms = maxStateOf(current);
      if (subState < ms) {
        subState += 1;
        applyReveal();
        return;
      }
      if (current < max - 1) {
        current += 1;
        subState = 1;
        render();
      }
    }
    function prev() {
      if (subState > 1) {
        subState -= 1;
        applyReveal();
        return;
      }
      if (current > 0) {
        current -= 1;
        subState = maxStateOf(current);
        render();
      }
    }
    function jump(n) {
      if (n < 0 || n >= max) return;
      current = n;
      subState = 1;
      render();
    }
    function toggleFullscreen() {
      if (!document.fullscreenElement) {
        (document.documentElement.requestFullscreen || function () {}).call(document.documentElement);
      } else {
        (document.exitFullscreen || function () {}).call(document);
      }
    }
    function toggleNotes() { body.classList.toggle('notes-on'); }
    function toggleBlackout() { body.classList.toggle('blackout'); }

    try {
      var saved = sessionStorage.getItem('vf3-deck-slide');
      if (saved !== null) {
        var n = parseInt(saved, 10);
        if (!isNaN(n) && n >= 0 && n < max) current = n;
      }
    } catch (e) {}
    render();

    document.addEventListener('keydown', function (e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      switch (e.key) {
        case ' ':
        case 'ArrowRight':
        case 'PageDown':
          e.preventDefault(); next(); break;
        case 'ArrowLeft':
        case 'PageUp':
          e.preventDefault(); prev(); break;
        case 'Home': e.preventDefault(); jump(0); break;
        case 'End':  e.preventDefault(); jump(max - 1); break;
        case 'f': case 'F': e.preventDefault(); toggleFullscreen(); break;
        case 's': case 'S': e.preventDefault(); toggleNotes(); break;
        case 'b': case 'B': case '.': e.preventDefault(); toggleBlackout(); break;
        case '0': case '1': case '2': case '3': case '4':
        case '5': case '6': case '7': case '8': case '9':
          e.preventDefault();
          var d = parseInt(e.key, 10);
          var target = d === 0 ? 9 : (d - 1);
          jump(target);
          break;
      }
    });

    stage.addEventListener('click', function (e) {
      if (e.target.closest('.notes')) return;
      next();
    });

    var idleTimer;
    function activity() {
      body.classList.add('active');
      body.classList.remove('idle');
      clearTimeout(idleTimer);
      idleTimer = setTimeout(function () {
        body.classList.add('idle');
        body.classList.remove('active');
      }, 2500);
    }
    document.addEventListener('mousemove', activity);
    document.addEventListener('keydown', activity);
    activity();
  })();
```

What this controller guarantees:

- `slides.length` auto-derives total count, so the HUD stays honest.
- `current` + `subState` form a simple, reliable state machine.
- `data-states="N"` lets Space step through reveal states before the next slide.
- The progress bar updates on every render.
- Notes are a strict 1:1 mapping: `.note[data-for="N"]` ↔ slide `N`.
- `sessionStorage` remembers the current slide if the presenter refreshes.

---

## Brandmark substitute recipe

When the customer's licensed logo is unavailable — which is **most PoCs** — use
a safe substitute, not a bootleg logo.

1. Start from the customer display name.
2. Strip legal suffixes and filler words (`Ltd`, `plc`, `Group`, `Holdings`,
   `The`) unless they are part of the brand.
3. Extract a **2-letter monogram** from the first meaningful words or the
   customer's established acronym.
4. Render it as `.brandmark` with a **white circle glyph** on the brand-flood
   panel.
5. Use a heavy sans (`Inter 800` or system sans-bold).
6. Echo the same mark on slide 1 and the final slide only.

Example:
```html
<span class="brandmark">
  <span class="glyph">VF</span>
  <span class="word">Customer-Journey Advisor</span>
</span>
```

Notes:

- A 24–32px white circle is the safe floor if you tighten the composition.
- The point is **recognizable authorship without trademark risk**.
- **Never** use the customer's actual licensed logo without explicit permission.

---

## Microsoft 4-color SVG (canonical)

Do not redraw this. Copy-paste the literal inline SVG.
```html

<svg class="ms-logo" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg" aria-label="Microsoft">
  <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
  <rect x="12" y="1" width="10" height="10" fill="#7FBA00"/>
  <rect x="1" y="12" width="10" height="10" fill="#00A4EF"/>
  <rect x="12" y="12" width="10" height="10" fill="#FFB900"/>
</svg>
```

Co-brand bar pattern:
```html

<div class="cobrand">
  <div class="left">
    <svg class="ms-logo" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg" aria-label="Microsoft">
      <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
      <rect x="12" y="1" width="10" height="10" fill="#7FBA00"/>
      <rect x="1" y="12" width="10" height="10" fill="#00A4EF"/>
      <rect x="12" y="12" width="10" height="10" fill="#FFB900"/>
    </svg>
    <span class="ms-word">Microsoft</span>
    <span class="x">×</span>
    <span class="ms-word" style="color:#FFFFFF;">{Customer}</span>
  </div>
  <div class="right">{Context label · Month Year}</div>
</div>
```

---

## Tech-stack icon library (18 inline symbols)

The platform and architecture slides only look finished when the pills and
cards carry **real inline symbols**. Bare text pills read like placeholder UI.
VF3 solved this with a single hidden SVG sprite at the top of the body.

> **Copy the whole sprite block once.** Do not rename the symbol IDs. Do not
> swap them for emoji. Do not mix in random third-party icon packs.

Extracted verbatim from the VF3 deck:
```html
  <!-- ===== Icon symbol library (inline SVG sprites for tech-stack pills) ===== -->
  <svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
    <defs>
      <symbol id="ico-window" viewBox="0 0 18 18">
        <rect x="2" y="3" width="14" height="11" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="2" y1="6.5" x2="16" y2="6.5" stroke="currentColor" stroke-width="1.4"/>
        <circle cx="4" cy="5" r="0.5" fill="currentColor"/><circle cx="5.7" cy="5" r="0.5" fill="currentColor"/><circle cx="7.4" cy="5" r="0.5" fill="currentColor"/>
      </symbol>
      <symbol id="ico-teams" viewBox="0 0 18 18">
        <path d="M3 4h12v8a1 1 0 0 1-1 1H7l-3 3v-3a1 1 0 0 1-1-1V4z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <text x="9" y="11" text-anchor="middle" font-size="6" fill="currentColor" font-weight="700" font-family="Inter, sans-serif">T</text>
      </symbol>
      <symbol id="ico-sparkle" viewBox="0 0 18 18">
        <path d="M8.5 1l1.4 4.1L14 7l-4.1 1.4L8.5 13 7.1 8.4 3 7l4.1-1.4L8.5 1z" fill="currentColor"/>
        <path d="M14.2 11l0.65 1.65L16.5 13.3l-1.65 0.65L14.2 15.6l-0.65-1.65L11.9 13.3l1.65-0.65L14.2 11z" fill="currentColor" opacity="0.75"/>
      </symbol>
      <symbol id="ico-cube" viewBox="0 0 18 18">
        <path d="M9 2L2.5 5.5v7L9 16l6.5-3.5v-7L9 2z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M9 9L2.5 5.5M9 9l6.5-3.5M9 9v7" fill="none" stroke="currentColor" stroke-width="1.4"/>
      </symbol>
      <symbol id="ico-chip" viewBox="0 0 18 18">
        <rect x="3.5" y="3.5" width="11" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <circle cx="9" cy="9" r="2.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="3.5" y1="6" x2="2" y2="6" stroke="currentColor" stroke-width="1.4"/>
        <line x1="3.5" y1="12" x2="2" y2="12" stroke="currentColor" stroke-width="1.4"/>
        <line x1="14.5" y1="6" x2="16" y2="6" stroke="currentColor" stroke-width="1.4"/>
        <line x1="14.5" y1="12" x2="16" y2="12" stroke="currentColor" stroke-width="1.4"/>
      </symbol>
      <symbol id="ico-search" viewBox="0 0 18 18">
        <circle cx="8" cy="8" r="5" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="11.7" y1="11.7" x2="15.5" y2="15.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </symbol>
      <symbol id="ico-book" viewBox="0 0 18 18">
        <rect x="3" y="3" width="12" height="11" rx="1" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="5.5" y1="6.5" x2="12.5" y2="6.5" stroke="currentColor" stroke-width="1.2"/>
        <line x1="5.5" y1="9" x2="12.5" y2="9" stroke="currentColor" stroke-width="1.2"/>
        <line x1="5.5" y1="11.5" x2="9.5" y2="11.5" stroke="currentColor" stroke-width="1.2"/>
      </symbol>
      <symbol id="ico-stack" viewBox="0 0 18 18">
        <rect x="2.5" y="3" width="13" height="3.5" rx="0.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <rect x="2.5" y="7.25" width="13" height="3.5" rx="0.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <rect x="2.5" y="11.5" width="13" height="3.5" rx="0.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <circle cx="5" cy="4.75" r="0.5" fill="currentColor"/>
        <circle cx="5" cy="9" r="0.5" fill="currentColor"/>
        <circle cx="5" cy="13.25" r="0.5" fill="currentColor"/>
      </symbol>
      <symbol id="ico-container" viewBox="0 0 18 18">
        <path d="M9 2l6 3v8l-6 3-6-3V5l6-3z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <path d="M3 5l6 3 6-3" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="9" y1="8" x2="9" y2="16" stroke="currentColor" stroke-width="1.4"/>
      </symbol>
      <symbol id="ico-globe" viewBox="0 0 18 18">
        <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <ellipse cx="9" cy="9" rx="6" ry="2.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="3" y1="9" x2="15" y2="9" stroke="currentColor" stroke-width="1.4"/>
        <line x1="9" y1="3" x2="9" y2="15" stroke="currentColor" stroke-width="1.4"/>
      </symbol>
      <symbol id="ico-clock" viewBox="0 0 18 18">
        <circle cx="9" cy="9" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <polyline points="9 5 9 9 12 11" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </symbol>
      <symbol id="ico-shield" viewBox="0 0 18 18">
        <path d="M9 1.5L3 4v5c0 4 2.7 6.5 6 7.5 3.3-1 6-3.5 6-7.5V4L9 1.5z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
        <circle cx="9" cy="8" r="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <line x1="9" y1="9.5" x2="9" y2="12" stroke="currentColor" stroke-width="1.4"/>
      </symbol>
      <symbol id="ico-brackets" viewBox="0 0 18 18">
        <polyline points="6 5 2 9 6 13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        <polyline points="12 5 16 9 12 13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      </symbol>
      <symbol id="ico-chart" viewBox="0 0 18 18">
        <polyline points="2 13 6 9 9 11 14 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        <polyline points="11 4 14 4 14 7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </symbol>
      <!-- architecture icons -->
      <symbol id="ico-gateway" viewBox="0 0 18 18">
        <rect x="2" y="5" width="14" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <line x1="6" y1="5" x2="6" y2="13" stroke="currentColor" stroke-width="1.2"/>
        <line x1="12" y1="5" x2="12" y2="13" stroke="currentColor" stroke-width="1.2"/>
        <circle cx="9" cy="9" r="1.8" fill="currentColor" opacity="0.6"/>
      </symbol>
      <symbol id="ico-policy" viewBox="0 0 18 18">
        <path d="M9 2 L15 5 L15 10 Q15 14 9 16 Q3 14 3 10 L3 5 Z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
        <polyline points="6.5 9 8 10.5 11.5 7" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </symbol>
      <symbol id="ico-telemetry" viewBox="0 0 18 18">
        <circle cx="9" cy="9" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="9" cy="9" r="2" fill="currentColor" opacity="0.5"/>
        <line x1="9" y1="2.5" x2="9" y2="5" stroke="currentColor" stroke-width="1.3"/>
        <line x1="9" y1="13" x2="9" y2="15.5" stroke="currentColor" stroke-width="1.3"/>
        <line x1="2.5" y1="9" x2="5" y2="9" stroke="currentColor" stroke-width="1.3"/>
        <line x1="13" y1="9" x2="15.5" y2="9" stroke="currentColor" stroke-width="1.3"/>
      </symbol>
      <symbol id="ico-hub" viewBox="0 0 18 18">
        <circle cx="9" cy="9" r="3.5" fill="none" stroke="currentColor" stroke-width="1.5"/>
        <circle cx="3" cy="3" r="1.5" fill="currentColor" opacity="0.5"/>
        <circle cx="15" cy="3" r="1.5" fill="currentColor" opacity="0.5"/>
        <circle cx="3" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
        <circle cx="15" cy="15" r="1.5" fill="currentColor" opacity="0.5"/>
        <line x1="5.5" y1="6.8" x2="4" y2="4.5" stroke="currentColor" stroke-width="1" opacity="0.6"/>
        <line x1="12.5" y1="6.8" x2="14" y2="4.5" stroke="currentColor" stroke-width="1" opacity="0.6"/>
        <line x1="5.5" y1="11.2" x2="4" y2="13.5" stroke="currentColor" stroke-width="1" opacity="0.6"/>
        <line x1="12.5" y1="11.2" x2="14" y2="13.5" stroke="currentColor" stroke-width="1" opacity="0.6"/>
      </symbol>
    </defs>
  </svg>
```

Mapping:

| Pill label | Symbol |
|------------|--------|
| Workspace | `#ico-window` |
| Microsoft Teams | `#ico-teams` |
| M365 Copilot Chat | `#ico-sparkle` |
| Microsoft Foundry · hosted agents | `#ico-cube` |
| Microsoft Agent Framework | `#ico-chip` |
| Azure AI Search | `#ico-search` |
| Knowledge Bases · agentic retrieval | `#ico-book` |
| MCP servers | `#ico-stack` |
| Azure Container Apps | `#ico-container` |
| Azure Cosmos DB | `#ico-globe` |
| Retention / audit timestamps | `#ico-clock` |
| Managed Identity | `#ico-shield` |
| Bicep + azd | `#ico-brackets` |
| Application Insights | `#ico-chart` |

Architecture icon purposes:

| Symbol | Meaning | Typical placement |
|--------|---------|-------------------|
| `ico-gateway` | APIM AI Gateway, API management | Architecture hub block |
| `ico-policy` | Policy guard, governance shield | AGT governance card, agent runtime layer |
| `ico-telemetry` | Observability, telemetry | Observability platform layer, hub block |
| `ico-hub` | Hub-spoke topology | Architecture spoke `× 400 spokes` line |

Canonical pill markup:
```html
<span class="tech"><svg class="ico"><use href="#ico-window"/></svg>Workspace</span>
```

---

## Architecture slide (hub-spoke + governance)

**When to use.** Conditional — include when the SPEC has explicit governance
posture or scale targets. It sits after the **Platform stack** slide and before
the **Follow-up proposal**.

**Structure (3 panels)**
- **Hub block (left)** — title `AI Citadel · Governance Hub` (or the
  customer-specific governance brand). Each row uses **Feature → Service**
  format:
  - `LLM governance → Azure API Management (AI Gateway)`
  - `Policy mesh → APIM policy fragments + JWT auth`
  - `Usage tracking → Azure Cosmos DB`
  - `Observability → App Insights + Log Analytics (OTel)`
  - `Network isolation → Private endpoints + VNet + DNS`
- **Connector** — vertical line with `Access contract` label
  (`writing-mode: vertical`).
- **Spoke block (right)** — title `Journey spoke · this pilot`. List the
  pilot's services (Foundry, AI Search, MCP, Cosmos). Final row:
  `× N spokes — same pattern, same hub`.
- **Governance cards (below, 3-col)** — each card has a name, 2-line
  description, and repo link. Standard cards:
  - `AI Citadel` → `Azure-Samples/ai-hub-gateway-solution-accelerator`
  - `AGT` → `microsoft/agent-governance-toolkit`
  - `Foundry` → `ai.azure.com`

**CSS classes**
- `.arch-diagram` — 3-column grid: hub | connector | spoke
- `.arch-hub`
- `.arch-spoke`
- `.arch-connector`
- `.arch-gov-row` — 3-column grid
- `.arch-gov-card`
- `.gov-link` — clickable repo links

---

## Follow-up proposal slide (replaces Discussion)

**Why.** The old Discussion slide with 3 open questions felt pointless after a
strong technical demo. A concrete follow-up proposal gives the audience
something to react to.

**Structure**
- Reuse `.discussion-row` + `.discussion-card`.
- Use `<span class="qnum">Step 01</span>` / `Step 02` / `Step 03` labels —
  not `Question`.
- Make each card a concrete action:
  - `Pick 5 high-friction journeys`
  - `Deploy AI Citadel hub`
  - `Governance + eval baseline`

**Speaker note guidance.** “Read each step as a concrete proposal, not a wish.
These are options on the table, not commitments.”

**Brand note.** This is still one of the mandatory brand-flood panels.

---

## Migration: legacy `overview.html` → meta-refresh redirect

When upgrading an existing PoC, do **not** leave the old brief pretending to be
the live deck. Collapse it to a tiny redirect and archive the old content.

1. Move the previous file to `overview.html.bak`.
2. Replace `overview.html` with this redirect shell.
3. Add `specs/*.html.bak` to `.gitignore`.

Redirect shell:
```html

<!doctype html><html><head><meta charset="utf-8">
<title>{Customer-Journey Advisor} — redirecting</title>
<meta http-equiv="refresh" content="0; url=demo-deck.html">
<script>location.replace('demo-deck.html');</script>
</head><body><p>This page has moved to <a href="demo-deck.html">demo-deck.html</a>.</p></body></html>
```

`.gitignore` addition:
```gitignore
specs/*.html.bak
```

### AGENTS.md § Tool display aliases (optional)

The **canonical name** is whatever appears in `AGENTS.md` **Foundry tools required**
column 1. Period. If the wire-level MCP transport name is uglier
(`vf3-journey-kb__mcp__search`) but the runtime alias is `vf3_journey_kb`, the
alias wins for deck copy — that is what ships in the runtime and what the user
actually types or says.

If a tool needs a shorter display label for the deck, add an explicit
`AGENTS.md § Tool display aliases` block. Pattern 6 then treats those aliases as
canonical **in addition to** the column-1 names.

```md
| Canonical | Display alias |
|---|---|
| vf3_journey_kb | Journey KB |
| vf3_get_account | Account lookup |
```

---

## "Reasons a deck gets rejected" — anti-pattern list

These are not hypothetical. They are the exact classes of mistake that caused
multiple rejected deck drafts before the VF3 v4 form stuck.

1. **Personas in the deck** — “I EXPLICITLY ASKED TO NOT BUG ME ABOUT USER PERSONA!”
   Personas live in `experience.html`, **not** the deck. Use roles, not names.
2. **Internal jargon leaks** — `OneAsk`, `Sweden Central`, `v1.0`, seller names,
   and contact details are forbidden in customer-facing slides. `prep-guide.html`
   is exempt because it is internal-only.
3. **Fabricated tool names** — do **not** invent `load_skill`-style labels. The
   visible tool-name set on the Skill Chain slide must be a subset of the names
   in `AGENTS.md` **Foundry tools required** column 1, **or** aliases explicitly
   documented in `AGENTS.md § Tool display aliases`. Raw wire-level transport
   names do not belong on the deck.
4. **Wrong palette / third-color accents** — a red telco deck does not need
   cobalt, amber, or purple flourishes. Brand should flood panels, not just
   underline headings.
5. **Commit-language closing** — never end with “we'll build”, “by 12 June”, or
   any other commit phrase. The close pair is **Follow-up proposal + Thank you**.
6. **Missing tech-stack icons** — bare text pills make the Platform and
   Architecture slides look unfinished. Use the 18-symbol inline library.
7. **Contributor signoff on the closing slide** — never put an individual seller
   name, email, or role signoff on the final customer-facing slide.
8. **Sales-close ending** — “Pick one journey by {date}” is not a deck ending.
   The deck should reopen the conversation, not close the deal.

---

## Validation gates (must pass before declaring done)

Run all of these. **ALL must pass.**

```text
- HTMLParser parses with zero errors
- 10–14 <section class="slide"> elements
- Speaker notes count == slide count (1:1 data-for mapping)
- All 4 keyboard chords wired (Space / F / S / B)
- Brand-flood panels ≥ 4 total: friction + follow-up proposal + close are
  mandatory, plus at least 1 of {hero, the-shift, scale, posture}
- Dark hero with brand-accent gradient is valid (VF3 reference deck uses this)
- Brandmark substitute present on slide 1 AND final slide
- MS co-brand bar present on hero AND close
- 18-symbol icon library present; the core 14 platform symbols must be
  referenced via <use href="#ico-XXX">, and the 4 architecture symbols must be
  referenced when the Architecture slide is present
- ZERO hits for internal-jargon deny-list
- ZERO hits for persona first-names
- Tool-name set in deck ⊆ AGENTS.md canonical tool/alias set
- ZERO hits for banned-phrase deny-list ("we'll build", near-term commitment dates, etc.)
- Playwright sanity at 1920×1080: Space advances, S toggles notes, F goes fullscreen,
  B blacks out, Home/End jump correctly
```

Compact automation harness:
```python

from html.parser import HTMLParser
from pathlib import Path
import re

html = Path('specs/demo-deck.html').read_text(encoding='utf-8')
agents = Path('AGENTS.md').read_text(encoding='utf-8')

class V(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errs = []
    def error(self, msg):
        self.errs.append(msg)

v = V(); v.feed(html); assert v.errs == [], v.errs
assert 10 <= len(re.findall(r'<section class="slide\b', html)) <= 14
assert len(re.findall(r'<div class="note(?: is-active)?" data-for="\d+">', html)) == len(re.findall(r'<section class="slide\b', html))
assert all(token in html for token in ['Space', 'fullscreen', 'notes', 'blackout'])
assert len(re.findall(r'<section class="slide[^"]*(?:bg-[^"\s]*flood|bg-red)\b[^"]*"', html)) >= 4
assert 'class="brandmark"' in html and 'class="close-brandmark"' in html
assert 'class="cobrand"' in html and 'class="close-cobrand-block"' in html
symbols = set(re.findall(r'<symbol id="([^"]+)"', html))
uses = set(re.findall(r'<use href="#([^"]+)"', html))
core_symbols = {
    'ico-window', 'ico-teams', 'ico-sparkle', 'ico-cube', 'ico-chip',
    'ico-search', 'ico-book', 'ico-stack', 'ico-container', 'ico-globe',
    'ico-clock', 'ico-shield', 'ico-brackets', 'ico-chart'
}
arch_symbols = {'ico-gateway', 'ico-policy', 'ico-telemetry', 'ico-hub'}
assert len(symbols) == 18 and core_symbols <= symbols and arch_symbols <= symbols
assert core_symbols <= uses
if 'class="arch-diagram"' in html:
    assert arch_symbols <= uses
canonical_tools = set(re.findall(r'^\|\s*`([^`]+)`\s*\|', agents, re.MULTILINE))
alias_section = re.search(r'^## Tool display aliases.*?(?=^## |\Z)', agents, re.MULTILINE | re.DOTALL)
display_aliases = set()
if alias_section:
    for line in alias_section.group(0).splitlines():
        m = re.match(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$', line)
        if m and m.group(1).strip() not in {'Canonical', '---'}:
            display_aliases.add(m.group(2).strip())
allowed_tool_labels = canonical_tools | display_aliases
assert set(re.findall(r'<span class="chain-step[^>]*>([^<]+)</span>', html)) <= allowed_tool_labels
for pattern in [r'\bOneAsk\b', r'\bSweden Central\b', r'\bv1\.0\b', r"we'll build", r'\bpick one journey\b']:
    assert not re.findall(pattern, html, re.IGNORECASE), pattern
```

### Manual / browser checks

- At **1920×1080**, verify `Space`, `S`, `F`, `B`, `Home`, and `End`.
- Notes overlay should track the current slide 1:1.
- Progress bar should move on every slide change.
- Expand the persona deny-list with any first-names used in sibling artefacts,
  then rerun grep.
- Treat any explicit customer-facing delivery date as a fail unless the slide is
  discussing a historical fact.

---

## See Also

- `~/.copilot/skills/threadlight-design/references/experience-template.md` — sibling cinematic for the bespoke dossier
- `~/.copilot/skills/threadlight-design/references/brand-palettes.md` — sector convention fallback when no logo URL captured
- `~/.copilot/skills/gbb-pptx/SKILL.md` — when a 1-slider PPTX leave-behind is requested
- `~/.copilot/skills/auto-demo-producer/SKILL.md` — when a narrated 90s MP4 backup is requested

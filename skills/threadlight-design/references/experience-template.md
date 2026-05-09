# `experience.html` — Bespoke Cinematic Customer Journey

> **Read this first**: this document is **NOT a template**. It's a **kit of
> parts** for designing a bespoke cinematic experience tailored to ONE specific
> business process. Reusing the same layout for every process is the fastest
> way to make a customer-facing demo feel cheap and AI-generated. Each process
> deserves its own visual paradigm.

A second seller-facing artifact that complements `overview.html`. Where the
overview is a **brief**, the experience is a **journey** that makes the
customer feel the pain, the intervention, the outcome, and the trust posture
of *this* process — through visuals native to *its* domain.

> **Optional, but strongly recommended.** Generate `experience.html` for any
> process intended for live customer demos, executive walkthroughs, or
> high-stakes pilots. Skip for purely internal automation specs where no
> human audience will see it.

## When to generate

- The user asks for a "demo", "customer journey", "walkthrough", "story",
  "cinematic", or "experience"
- The process has a clear dramatic moment — a deadline, a wave, a backlog,
  a queue, a deliverable
- A seller will present this live to a customer or executive sponsor

Skip when:

- Pure backend automation with no human audience (still ship `overview.html`)
- Customer is highly technical and prefers raw spec content (overview only)
- Time-constrained fast-PoC where overview.html is sufficient

---

## The bespoke design discipline

### Step 1 — Identify the **process DNA**

Read the SPEC.md, AGENTS.md / `specs/manifest.json`, and `overview.html` to
extract:

| Element | Question | Example (KYC) | Example (network-fault) |
|---------|----------|---------------|-------------------------|
| **Protagonist** | Who is the human under pressure? | KYC analyst at 8:47am | NOC engineer at 06:14 UTC |
| **Artifact** | What deliverable is being produced? | A signed onboarding decision | A clean topology graph |
| **Moment of truth** | What's the dramatic deadline? | Regulator examiner arrives 9am | SLA breach in 11 minutes |
| **Backlog number** | The N that the agent multiplies impact across | 340 cases | 73 active alarms |
| **Hard guardrail** | The "agent must NOT do X" rule | No autonomous KYC approvals | No autonomous transit moves |

That five-line extract is the brief. Every visual decision flows from it.

### Step 2 — Pick the **visual paradigm**

DO NOT default to a 4-act narrative scroll. Pick the paradigm that *is* the
process. The catalog below shows successful exemplars — adapt freely or invent
a new one if the process needs it.

### Step 3 — Compose three movements

Every cinematic experience has three felt phases (regardless of paradigm):

1. **Density that hurts** — the customer sees the problem at full scale (an
   alarm storm, a stuck pipeline, a 47-folder backlog, a calm world about to
   stop being calm).
2. **Zoom into one** — the camera focuses on a single case so the customer
   understands the depth of agent reasoning, with citations to BR-XXX.
3. **The wave processed** — pull back; the agent has scaled across the
   backlog; counters scrub down to zero; some items routed to humans (proves
   guardrails). Land softly on a calm trust panel (visual inversion).

The **transitions between movements** are where the cinematic feeling lives.
Use GSAP ScrollTrigger to scrub, pin, fade, and stagger.

### Step 4 — Land on a **trust panel**

The closing panel is consistent across paradigms (intentional — it's the
"contract" with the customer):

- Visual inversion (light if the journey was dark, dark if it was light)
- 6 trust pillars derived from SPEC.md business rules — each with BR-XXX badge
- Skill catalog (from AGENTS.md / specs/manifest.json) as code-pill list
- 3 CTAs: ↗ overview.html · ↗ SPEC.md · ← back to catalog
- Footer: "Microsoft AI Apps · {Industry} Reference Catalog · {Process Name} · Bespoke experience · Spec version 1.0"

---

## Paradigm catalog (exemplars)

| Paradigm | Best for | Catalog reference |
|----------|----------|-------------------|
| **4-act narrative scroll** | Cases with a strong time-of-day arc and emotional pain (regulatory, customer-trust) | `01-fsi/kyc-onboarding/specs/experience.html` |
| **Live topology graph** | Network/graph-shaped processes; nodes + edges + health states | `03-telco/network-fault-triage/specs/experience.html` |
| **Kanban pipeline (live)** | Order/case flow through stages; "stuck → moving" drama | `03-telco/order-fallout-resolution/specs/experience.html` |
| **World dot-density map** | Geographically distributed processes (supply chain, fleet, branch ops) | `04-manufacturing/supplier-risk-monitoring/specs/experience.html` |
| **Dossier / binder pages** | Document-as-deliverable processes (credit memo, M&A diligence) | `01-fsi/smb-credit-memo/specs/experience.html` |
| **Dispatch console (split)** | Inbound stream + decision stream side-by-side (FNOL, contact center) | `01-fsi/insurance-fnol-triage/specs/experience.html` |
| **Ledger + regulatory clock** | Investigation processes with a hard regulatory deadline | `01-fsi/card-dispute-investigation/specs/experience.html` |
| **Editorial campaign cover** | Marketing/merchandising deliverables with a print-lock | `02-retail/promo-planning-copilot/specs/experience.html` |
| **Magazine spread (Vogue-grade)** | Vision-skill-heavy product enrichment | `02-retail/pim-catalog-enrichment/specs/experience.html` |
| **Conveyor belt** | Physical-flow processes (fulfillment, returns, inspection) | `02-retail/returns-triage/specs/experience.html` |
| **Tender document compose** | Multi-section corporate deliverables (RFP, quote, proposal) | `03-telco/b2b-quote-to-order/specs/experience.html` |
| **CAD blueprint annotated** | Engineering / technical-spec retrieval with citations | `04-manufacturing/engineering-knowledge-copilot/specs/experience.html` |
| **Control-room dual-dashboard** | Handover / shift-change processes | `04-manufacturing/shift-handover-briefing/specs/experience.html` |

If a new process doesn't fit any of these — invent a new one. Some untapped
paradigms: courtroom evidence binder, hospital triage board, air-traffic
control radar, recipe assembly, archaeological dig, music-score arrangement.

---

## The cinematic toolkit (copy-paste-safe)

These are the **technical primitives** every paradigm uses. They are not the
design — they are the engine that powers any design you choose.

### CDN scripts (head)

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
```

**No `defer`.** GSAP must initialize before the IIFE runs.

### Inline head script (gating + fallback)

```html
<script>
  document.documentElement.classList.add('gsap-anim');
  setTimeout(() => {
    if (typeof gsap === 'undefined') {
      document.documentElement.classList.remove('gsap-anim');
    }
  }, 2500);
</script>
```

CSS pre-hides animation targets only when `.gsap-anim` is on `<html>`. The
2.5s fallback guarantees content is visible if GSAP fails to load (offline,
CSP block, network glitch).

### Reduced-motion override (mandatory)

```css
@media (prefers-reduced-motion: reduce) {
  .gsap-anim *,
  .gsap-anim *::before,
  .gsap-anim *::after {
    transition: none !important;
    animation: none !important;
    transform: none !important;
    opacity: 1 !important;
  }
}
```

### Color palettes (pick one per paradigm; do not blend)

| Mood | Background | Body | Accent | Inversion (trust panel) |
|------|------------|------|--------|--------------------------|
| **Cinematic dark** | `#0a0a0a` → `#1a1a1a` | `#fef9f1` | `#f59e0b` warm amber | cream `#faf6ed` |
| **NOC / cockpit** | `#040712` | `#e9eef7` | `#3aa9ff` signal blue, `#ff4757` alarm | cream |
| **Banking dossier** | parchment `#f3ede3` | navy `#1a2238` | brass `#a07a3a` | navy inversion |
| **Editorial magazine** | white `#faf8f5` | ink `#0c0d10` | oxblood `#7c1d1f` | ink inversion |
| **Industrial control** | charcoal `#0d1117` | warm white | machine-amber `#fbbf24` | cream |
| **Geographic / map** | midnight `#0c1115` | parchment | alert amber + lithium violet | cream |
| **Warehouse kinetic** | slate `#1a1a1a` | warm white | cardboard tan + sorting colors | sage `#dcebd9` |

NEVER use generic AI-purple gradients, teal, or "tech blue".

### Typography palettes

- **Cinematic dark / NOC**: Inter or system-ui body + Cascadia Mono / Consolas for IDs
- **Dossier / Banking / Tender / Engineering / Card-dispute**: Source Serif 4 or Spectral (Google Fonts) body + Cascadia Mono for IDs
- **Editorial magazine**: Bodoni Moda or Playfair Display (Google Fonts) display + clean sans body
- **Industrial control**: Inter body + JetBrains Mono / Consolas for numbers

One webfont via CDN is acceptable. Two is excessive.

### GSAP motion vocabulary

Pick 3-5 motion primitives that fit the paradigm. Don't use all of them.

- `gsap.from(el, {y: 60, opacity: 0, duration: 0.9})` — character/word/element entrance
- `gsap.to(el, {scrub: true})` with ScrollTrigger — scrub a counter or a transform with scroll position
- `ScrollTrigger.create({pin: true, trigger: el, start: "top top", end: "+=2000"})` — pin a hero region while content scrolls past
- Stagger animations: `gsap.from('.item', {y: 40, opacity: 0, stagger: 0.06})` — for grids and lists
- SVG path drawing: `gsap.fromTo(path, {strokeDashoffset: pathLen}, {strokeDashoffset: 0, scrollTrigger})` — for dependency graphs, leader lines, blueprint annotations
- Color crossfade: `gsap.to(node, {fill: '#34d399'})` — for healing nodes, resolved cards
- Camera-pull-back: `gsap.to(container, {scale: 0.6, scrollTrigger})` — for "from one case to the wall"

### Transition layer (subtle, not gimmicky)

Between movements, use a soft visual transition — not a hard cut. Options:

- A 1px sweep line that crosses the viewport and "wipes" the next section in
- A color bleed: `::after { background: linear-gradient(to bottom, transparent, currentBg) }` to soften the seam between sections
- A pin-and-fade: pin the previous section briefly while fading content underneath

---

## Whitelabel discipline (mandatory — customer-facing)

The deny-list below MUST return zero hits. Run grep before you ship.

```
GBB | FY26 | CSU | OCP | ECIF | MTC | EBC | @microsoft.com
threadlight | citadel | black belt
Moneta | ARGUS | NetCracker | Amdocs | BSS-Magic | Genie
Microsoft confidential | For internal use
[any seller-team member names]
```

For telco specifically: vendor names like NetCracker / Amdocs / Genie are
forbidden — say "OSS / BSS / order management" or "quote engine" generically.

For every customer/case/order/transaction in the demo: synthesize plausible
data. Realistic vocabulary is good; real customer names are not.

---

## Validation checklist (before you ship)

Run all of these. ALL must pass.

```python
# 1. HTMLParser (no parse errors)
from html.parser import HTMLParser
class V(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errs = []
    def error(self, msg):
        self.errs.append(msg)
v = V()
v.feed(open('experience.html', encoding='utf-8').read())
assert v.errs == [], v.errs

# 2. Whitelabel deny-list returns zero hits
import re
data = open('experience.html', encoding='utf-8').read()
patterns = [r'\bGBB\b', r'\bFY26\b', r'\bCSU\b', r'\bOCP\b', r'\bECIF\b',
            r'\bMTC\b', r'\bEBC\b', r'@microsoft\.com', r'\bthreadlight\b',
            r'\bcitadel\b', r'\bblack belt\b', r'Moneta', r'ARGUS',
            r'Microsoft confidential', r'For internal use']
hits = [(p, len(re.findall(p, data, re.IGNORECASE))) for p in patterns
        if re.findall(p, data, re.IGNORECASE)]
assert not hits, hits

# 3. Bespoke quality (NOT a copy-of-KYC)
assert not re.search(r'id="act-[1-4]"', data), 'act-N IDs forbidden — invent your own structure'
assert 'giant-counter' not in data, 'giant-counter element belongs to KYC only'
```

Plus a Playwright spot-check at 1440×900:

- The signature interaction visibly works (counter scrubs, topology heals,
  pages assemble, dashboard transitions, etc.)
- Bidirectional scroll works (scroll back, content un-animates correctly)
- `prefers-reduced-motion: reduce` test (all motion suppressed, content visible)
- Whitelabel grep on rendered DOM also clean (some content is JS-injected)

---

## Anti-patterns (do not do these)

- ❌ Reusing `act-1`, `act-2`, `act-3`, `act-4` IDs from KYC — invent your own structural IDs that match the paradigm (`pipeline-board`, `topology-canvas`, `binder-cover`, `dispatch-console`, `ledger-view`, etc.)
- ❌ Reusing the `giant-counter` element — invent a counter form-factor that fits the paradigm (a queue gauge, a depth pill, an SLA ticker)
- ❌ Same color palette across processes — pick the palette that fits the paradigm
- ❌ Same hero copy structure ("X minutes." big-character display) across processes — vary it
- ❌ Generic "AI gradient purple" — never
- ❌ Multiple paradigms mashed together in one experience — pick one and commit
- ❌ Real customer / vendor / seller names — always synthesize
- ❌ Internal Microsoft tokens (deny-list above) — never

---

## File length expectations

Bespoke experiences vary by paradigm:

- Lightweight paradigms (split-screen, ledger, dossier): 60–90 KB
- Medium (Kanban, conveyor, control-room dashboard): 70–120 KB
- Heavy SVG/canvas (topology graph, world map, blueprint): 100–200 KB

Length should be earned by the paradigm, not by padding CSS or duplicating
sections.

---

## Reference implementations

The catalog at `https://github.com/...` (the awesome-gbb threadlight catalog)
contains all 13 reference experiences. Browse them before designing a new
one — visual literacy across the catalog will save hours of false starts.

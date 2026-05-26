---
name: lean-seller-guide
description: >
  Full seller enablement kit for lean toolkit (Spec2Cloud) solutions —
  cinematic HTML demo deck (10+ slides, keyboard-paced, speaker notes),
  threadlight-grade seller prep guide (5-beat demo script, dual-mode
  Seller/SE toggle, discovery questions, objections, MS services map),
  demo rehearsal run-of-show, and ranked killer prompts. Reads spec.md,
  plan.md, verify.md, deploy.md. Run AFTER /lean:deploy completes.
  USE FOR: demo deck, seller guide, demo script, seller prep, field
  readiness, lean toolkit demo, demo preparation, sales enablement,
  pre-sales content, customer demo, demo rehearsal, killer prompts,
  run of show, field enablement, mixed audience demo.
  DO NOT USE FOR: threadlight PoCs (use threadlight-design), deploying
  solutions (use /lean:deploy), designing processes, running agents.
metadata:
  version: "2.0.0"
---

# Lean Seller Guide

## Purpose

Generate a **complete seller enablement kit** from a deployed lean toolkit
(Spec2Cloud) solution. Bridges the gap between the engineering BUILD loop
(Specify → Plan → Implement → Verify → Deploy) and the field SELL motion by
producing four artifacts:

1. **`docs/demo-deck.html`** — cinematic HTML talk deck for the live customer demo
2. **`docs/seller-guide.html`** — internal prep guide with 5-beat demo script and dual-mode toggle
3. **`docs/demo-rehearsal.md`** — beat-by-beat run-of-show (T-24h → T-0 → backup paths)
4. **`docs/killer-prompts.md`** — ranked wow-prompts with expected anchors and wow lines

All artifacts are self-contained (HTML opens in browser, markdown renders in any
viewer). No server, no build step, no dependencies.

## When to Use

Run this skill **after** `/lean:deploy` completes and the solution is live.
Can also run in **draft mode** after `/lean:verify` — the deck and seller guide
will have placeholder URLs that get back-filled once deploy completes.

## Input Requirements

| File | Required | Used for |
|------|----------|----------|
| `./docs/spec.md` | Yes | Scenario narrative, agent capabilities, tool descriptions, business value, demo scenarios, success criteria |
| `./docs/plan.md` | Yes | Architecture choices, resource graph, identity model |
| `./docs/verify.md` | Yes | Smoke test results, trace validation, eval outcomes |
| `./docs/deploy.md` | Yes | Live URLs, resource IDs, deployed model, region |
| `./.azure/deployment-plan.md` | Recommended | Detailed Azure resource graph for architecture slide |
| `azure.yaml` | Optional | Service-to-resource bindings for the architecture diagram |
| `./docs/safe-check-post-deploy.json` | Optional | Gate pass confirmation (from `lean-safe-check`) |

> **Enriched spec.md.** If the agentic-loop post-processor has run, `spec.md`
> contains § Business Value, § Target Audience, § Demo Scenarios, and § Success
> Criteria sections that make this skill's output dramatically better. If those
> sections are missing, the skill asks 3-5 clarifying questions before generating.

---

## Output 1: `docs/demo-deck.html` — Cinematic Talk Deck

A keyboard-paced, full-viewport HTML presentation designed for a **≤ 8 minute
live talk**. This is the primary customer-facing artifact.

### Slide grammar (10-12 slides)

| # | Slide | Status | Content | Source | Duration |
|---|-------|--------|---------|--------|----------|
| 1 | Cold open | **Mandatory** | Solution name + headline claim. Dark cinematic hero. | `spec.md` title + § Business Value pain statement | 15-25s |
| 2 | Context | Conditional | Customer's stated goal — restate so the deck feels anchored | `spec.md` § Target Audience | 20-30s |
| 3 | Friction | **Mandatory** | 3 numeric pain points quantifying the current-state tax | `spec.md` § Business Value + § Success Criteria | 30-40s |
| 4 | The shift | **Mandatory** | Before/after or today/tomorrow — the transformation | `spec.md` § Success Criteria + `verify.md` results | 25-40s |
| 5 | Preview answer | Recommended | Show what a real answer looks like BEFORE the live demo (visual insurance) | `verify.md` smoke test results | 25-35s |
| 6 | Live demo cue | **Mandatory** | Hand the room from talk track to live invocation: "Now let's watch." | `deploy.md` URLs | 10-15s |
| 7 | Skill chain | **Mandatory** | Decode what the agent just did — exact tool sequence with callouts | `spec.md` tool descriptions | 30-45s |
| 8 | Platform stack | **Mandatory** | 6-layer visual stack: Foundry, AI Search, Cosmos, ACA, App Insights, Entra | `plan.md` resource graph | 30-45s |
| 9 | Follow-up | **Mandatory** | 3 concrete next steps — things the customer can say yes to | `spec.md` non-goals as Phase 2 | 20-30s |
| 10 | Close | **Mandatory** | Bookend: solution name echo + "Thank you." + Microsoft co-brand bar | — | 5-10s |

### Design requirements

- **Full-viewport slides** — each `<section class="slide">` is `min-height: 100vh`
- **Keyboard navigation** — Space/→ = next slide, ←/B = back, F = fullscreen, S = speaker notes toggle
- **Speaker notes** — hidden `<aside class="speaker-notes">` per slide, shown with 'S' key
- **Typography** — system-ui font stack, ≥ 36px headings, ≥ 24px body, ≥ 18px speaker notes
- **Color palette** — dark navy `#1a1a2e`, white cards `#ffffff`, accent blue `#0078d4`, subtle gradients
- **SVG icon library** — inline `<svg>` sprite with ≥ 12 service icons (Foundry, AI Search, Cosmos, ACA, App Insights, Entra, Teams, Key Vault, Container Registry, Storage, Redis, API Management)
- **Responsive** — works projected (1920×1080) and on laptop (1440×900)
- **No tech jargon on any slide** — no MCP, UAMI, Bicep, azd, OTel, ACA, DefaultAzureCredential, gpt-5.x model names, Container Apps, FastMCP, region labels
- **Product names only** — Microsoft Foundry, Azure AI Search, Cosmos DB, App Insights, Entra ID, Teams

### Friction slide pattern

The friction slide is the emotional payload. Structure:

```html
<section class="slide slide--friction">
  <h2>Today, this takes <em>[quantified pain]</em></h2>
  <div class="pain-grid">
    <div class="pain-card">
      <span class="pain-number">[X hours]</span>
      <span class="pain-label">[what takes that long]</span>
    </div>
    <!-- 2 more pain cards -->
  </div>
  <p class="pain-footer">[One-line cost statement from spec § Business Value]</p>
  <aside class="speaker-notes">[Speaker note: anchor to customer's own words]</aside>
</section>
```

### Preview answer slide pattern

Visual insurance — show a real agent answer before the live demo:

```html
<section class="slide slide--preview">
  <div class="preview-panel">
    <p class="preview-q"><em>"[Killer prompt K1 from verify.md]"</em></p>
    <div class="preview-a">[Summarized response with <strong>highlighted</strong> data points]</div>
    <div class="preview-cite">Citation. Version. Source. Every time.</div>
  </div>
  <aside class="speaker-notes">This sets the audience's expectation. If the live demo
  wobbles, flip back to this slide — they've already seen a real answer.</aside>
</section>
```

---

## Output 2: `docs/seller-guide.html` — Seller Prep Guide

> **INTERNAL / MICROSOFT CONFIDENTIAL.** Add to `.gitignore` if repo is shared externally.

The comprehensive preparation document for the person presenting. Contains
everything they need to walk in confident and walk out with next steps.

### Mandatory UX features

1. **Dual-mode toggle** — sticky bar at top with 🎤 Seller / 🔧 SE pills.
   Seller mode hides all `se-only` blocks; SE mode shows and auto-opens them.
   Mode persists via `sessionStorage`. Default: Seller mode.

   ```javascript
   function setMode(mode) {
     document.querySelectorAll('.se-only').forEach(el => {
       el.style.display = mode === 'se' ? 'block' : 'none';
     });
     document.querySelectorAll('.mode-pill').forEach(p => {
       p.classList.toggle('active', p.dataset.mode === mode);
     });
     try { sessionStorage.setItem('seller-guide-mode', mode); } catch(e) {}
   }
   // On load: restore persisted mode or default to 'seller'
   document.addEventListener('DOMContentLoaded', () => {
     setMode(sessionStorage.getItem('seller-guide-mode') || 'seller');
   });
   ```

2. **Sticky sidebar TOC** — fixed left nav (`position: fixed; left: 0; width: 200px`)
   with section links. Scroll-spy highlights active section in accent blue.
   Smooth-scroll on click. Main content offset `margin-left: 220px`. Hides on
   mobile (`@media max-width: 900px`).

3. **Font sizing discipline** — the guide is read on a secondary (non-projected)
   screen at arm's length:
   - Body text: ≥ 20px, line-height ≥ 1.6
   - Demo flow steps: ≥ 18px
   - Absolute minimum anywhere: 14px
   - Exception: confidentiality banner (12px, compact padding)

4. **Seller-visible product grid** — in the Architecture section, render a
   6-card emoji grid of Azure product names sellers can pitch:
   ```
   🤖 Microsoft Foundry    🔍 Azure AI Search    💬 Teams + Copilot
   🗄️ Cosmos DB            📊 App Insights       🔐 Entra ID
   ```
   Each card: emoji + product name + one-line value prop. The full wiring
   diagram goes in a `se-only` block below.

### Sections (in order)

#### § 0 · Demo Entrypoint

Live URL from `deploy.md` + how to launch. If pre-deploy (draft mode), show
placeholder: *"[URL populated after /lean:deploy completes]"*.

#### § 0.5 · What's Deployed (MVP Capabilities)

One-screen inventory of what the customer is getting:
- Channels available (web / Teams / Foundry playground)
- Agent's tool surface (one line per tool from `spec.md`)
- Sample data shape ("X records, Y entities")
- Expected response latency ("30-60 seconds per answer")
- Throttle limits if relevant ("5-7 questions per warm period")

Without this panel, sellers improvise with no mental model of what's behind the curtain.

#### § 1 · Executive Summary

3-sentence pitch: problem → solution → why Microsoft. Source from `spec.md`
§ Business Value. No tech jargon.

#### § 2 · Demo Script — The 5-Beat Arc

The seller's runnable script. **Concrete enough to run verbatim** in any
agent surface (Foundry playground, Teams, web endpoint).

**Beat 1 — Opening Hook** (≈ 30 seconds)

One paragraph of customer-facing pain + one tease of the wow moment.
Write in **direct quotes** so the seller can read it aloud:

> *"Today, your team spends [X hours] on [process] — and still misses [Y].
> In the next 8 minutes, I'll show you an agent that does it in [Z seconds],
> with citations for every answer."*

Source: `spec.md` § Business Value pain statement + § Success Criteria primary KPI.

**Beat 2 — Demo Arc (3-5 acts)**

Each act is one prompt → one response → one business anchor. **Every act
MUST contain three labelled sub-blocks in this exact order:**

> **Type this:** `<pre><code>{literal prompt from spec § Demo Scenarios}</code></pre>`
>
> **What you'll see:** {1-2 sentences naming **specific** data points the
> agent will surface — entity names, numbers, deltas. NOT generic ("the agent
> shows results") but concrete ("claims processing reduced from 48h to 3min,
> 12 cases cleared, citation from policy document v2.3").}
>
> **Say:** {one sentence the seller says *after* the response lands, anchoring
> it to business value.}

Source prompts from `spec.md` § Demo Scenarios or `killer-prompts.md`. **Never
paraphrase** — the same string should match what was validated in `verify.md`.

Each act tagged with the capability it demonstrates (small inline label).

**Beat 3 — Bonus Acts** (≥ 3 extras, "use if time allows")

Group in one card with short labels:
- 1-2 depth/cross-cut prompts showing different capabilities
- 1 edge case — data freshness/provenance prompt
- 1 edge case — out-of-scope/guardrail prompt (agent declines correctly)

Each bonus prompt needs only **Type this:** (seller improvises off the response).

**Beat 4 — Reveal Moment**

One paragraph quantifying saved time: contrast manual-effort-today with the
PoC performance. Anchor to the primary KPI from `spec.md` § Success Criteria.
Write in **direct quotes:**

> *"What took your team [X hours] just happened in [Y seconds] — with every
> answer cited back to your source documents. That's [Z]× faster, with an
> audit trail your compliance team can review."*

**Beat 5 — Q&A Handoff**

One sentence transitioning to discovery:

> *"Now I'd like to understand how this would land in your environment —
> can I ask a few things about your current workflow?"*

#### § 3 · Discovery Questions

5-8 questions to deepen the conversation, tailored to the domain:
- "What does this process look like today? Where are the bottlenecks?"
- "Which systems hold the data the agent would need?"
- "Who approves / escalates? What are the SLAs?"
- "How do you measure success today?"
- "What compliance or audit requirements apply?"

#### § 4 · Expected Objections

3-5 likely pushbacks with suggested responses:

| Objection | Response |
|-----------|----------|
| "How do we trust the agent's decisions?" | Every answer is cited. Human-in-the-loop is built in for high-stakes decisions. Full audit trail in App Insights. |
| "What about our legacy systems?" | The agent uses mock data today. Swapping to your real systems is a configuration change, not a rebuild. |
| "How long to production?" | The PoC runs on the same Azure services as production. The path is: connect real data → run evals → deploy to your subscription. |
| "What does this cost?" | See the Architecture section for the exact Azure services. [Point to MS services map.] |
| "Is our data safe?" | Runs in your Azure tenant. Entra ID governs access. No data leaves your boundary. |

#### § 5 · Proof It Works

Evidence that the solution is real and validated:
- Smoke test results from `verify.md` (pass/fail per test)
- End-to-end trace summary (request → tool calls → response time)
- Gate pass from `safe-check-post-deploy.json` if available
- Any eval scores if evals were run

#### § 6 · Architecture (dual-mode)

**Seller view** (default): 6-card product grid (emoji + name + value prop).
No wiring, no engineering detail.

**SE view** (`se-only`): full resource graph from `plan.md` / `deployment-plan.md`:
- Azure resource types and names
- Identity model (UAMI, role assignments)
- Network topology (if relevant)
- Data flow (agent → tools → storage → response)

#### § 7 · Microsoft Services Map

`se-only` section for the commercial conversation:

| Service | SKU | What it does in this solution | Customer pays for |
|---------|-----|-------------------------------|-------------------|
| Microsoft Foundry | Hosted Agent | Agent runtime + model access | Foundry account + model tokens |
| Azure AI Search | Standard S1 | Knowledge retrieval | Search units |
| Cosmos DB | Serverless | Sample data + audit trail | RU consumption |
| ... | ... | ... | ... |

Each service name links to the Azure Calculator pre-selected SKU page where
possible. Without this panel, sellers asking "what do they buy?" have to
reverse-engineer the architecture.

#### § 8 · Next Steps

3-5 concrete proposals:
1. Connect real data sources (replace mocks)
2. Run evaluations with customer-provided test scenarios
3. Deploy to customer's Azure subscription
4. Expand to additional process variants
5. Add governance via AI Gateway (Citadel) for production

#### § 9 · Appendix

`se-only`: exact deployment commands, environment variables, troubleshooting
tips, reset/redeploy instructions from `deploy.md`.

### No tech jargon outside `se-only` blocks

In Seller mode, the guide MUST NOT show: MCP, Responses API, UAMI,
DefaultAzureCredential, ACA, Bicep, azd, gpt-5.x model names, Container Apps,
FastMCP, OTel, region labels, ARM resource IDs. Product names and business
outcomes only.

---

## Output 3: `docs/demo-rehearsal.md` — Run-of-Show

Beat-by-beat stopwatch script for the seller delivering the live talk.
The deck is the *visual*; the rehearsal is the *choreography*.

### Required beats (in order, each timestamped)

| Time | What | Purpose |
|------|------|---------|
| **T-24h** | Bench check — probe all endpoints from `deploy.md`, invoke K1 prompt, verify response | Catch overnight breakage early |
| **T-15 min** | Tab list — open demo deck, live endpoint, App Insights, and seller-guide in separate tabs in the right order | One-glance "everything is up" |
| **T-5 min** | Agent warm-up — invoke K1 and K2 prompts once to clear cold-start cost | Audience never sees first-token-after-cold-start delay |
| **T-0** | Demo arc — K1 → K2 → K3 → reveal → close | ≤ 8 minute total budget |
| **Backup paths** | If live demo fails: flip to Preview Answer slide in deck; fallback to terminal `curl` with K1 prompt; share pre-recorded screen capture if available | Never be stuck with a blank screen |
| **Ship checklist** | Deck open in fullscreen mode, speaker notes off (toggle with S), secondary screen has seller-guide open, lighting OK, mic tested, water at hand | Pre-flight, ~T-2 min |

Each T-0 beat names:
- The killer prompt **verbatim** (by rank: K1, K2, K3)
- The demo-deck slide it corresponds to
- The expected data points the agent returns
- The **wow line** the seller says after the agent finishes

### Backup path detail

```
Primary: live endpoint in browser
  ↓ fails
Fallback 1: demo-deck.html slide 5 (Preview Answer) — pre-rendered real response
  ↓ time allows
Fallback 2: terminal curl to deployed endpoint with K1 prompt body
  ↓ all down
Fallback 3: pre-recorded MP4 demo (if auto-demo-producer skill was run)
```

---

## Output 4: `docs/killer-prompts.md` — Ranked Wow-Prompts

5-7 hand-picked prompts ranked K1-K7 by demo wow-factor. These are the
demo's emotional payload — generic starters ("Tell me about X") burn
the opening seconds; killer prompts trigger the "oh, *that's* what this does"
reaction.

### Row schema

| Rank | Prompt | Expected anchors | Wow line | Works on |
|------|--------|------------------|----------|----------|
| K1 | `{literal prompt — same string validated in verify.md}` | ≥ 1 entity name + ≥ 1 number | "{one sentence the seller says after}" | Web · Teams · Playground |
| K2 | ... | ... | ... | ... |

### Rules

- **Source from verify.md** — every killer prompt should be a prompt that was
  validated during the verify stage (smoke test passed). If `spec.md` has
  § Demo Scenarios, use those as the primary source.
- **Never invent prompts.** The literal string must match what was tested.
- **Expected anchors** must name specific entities and numbers the response
  surfaces — without these, the seller has no way to know if the response is
  "right."
- **Wow line** is what the seller says *after* the response lands, anchoring
  to business value. One sentence, direct quotes.
- K1 is the opening move, K2 is the depth probe, K3+ are cross-cut and edge cases.

### Wiring

- `demo-rehearsal.md` references K1/K2/K3 by rank in the T-0 beat sequence
- `seller-guide.html` Demo Script acts source prompts from this file
- `demo-deck.html` Preview Answer slide uses K1

---

## Workflow

1. Read `docs/spec.md`, `docs/plan.md`, `docs/verify.md`, `docs/deploy.md`
2. Check for enriched sections (§ Business Value, § Demo Scenarios, § Success Criteria).
   If missing, ask 3-5 clarifying questions:
   - "What business problem does this solve, and what does it cost today?"
   - "Who is the audience for this demo? (executive / technical / mixed)"
   - "What are 3 prompts that would wow this audience?"
   - "What does success look like — what's the primary KPI?"
3. Generate `docs/killer-prompts.md` (K1-K7 ranked prompts)
4. Generate `docs/demo-deck.html` (customer-facing, cinematic)
5. Generate `docs/seller-guide.html` (internal, dual-mode, 5-beat demo script)
6. Generate `docs/demo-rehearsal.md` (run-of-show)
7. Add `docs/seller-guide.html` to `.gitignore` if not already excluded
8. Report all four files with instructions to open HTML in browser

---

## Validation checklist (mandatory auto-review)

After generating all artifacts, run these checks before presenting to the user:

- [ ] **`demo-deck.html`** — HTMLParser passes; ≥ 10 `<section class="slide">`
  elements; speaker notes present (one `<aside>` per slide); keyboard
  navigation JS wired (Space, Arrow, F, S); no tech jargon outside speaker
  notes; SVG icon sprite present; responsive at 1440×900
- [ ] **`seller-guide.html`** — dual-mode toggle JS present with
  `setMode()` function; 5-beat demo script complete (opening hook, demo arc
  with ≥ 3 acts each having Type this / What you'll see / Say, bonus acts
  ≥ 3, reveal moment, Q&A handoff); no tech jargon in seller mode; sticky
  sidebar TOC with scroll-spy; font sizing ≥ 14px minimum; product grid
  present; INTERNAL/CONFIDENTIAL banner present
- [ ] **`demo-rehearsal.md`** — all 6 beat rows present (T-24h, T-15min,
  T-5min, T-0, backup paths, ship checklist); T-0 total budget ≤ 8 minutes;
  each killer prompt referenced verbatim by rank
- [ ] **`killer-prompts.md`** — ≥ 3 rows ranked K1-K3+; each row has literal
  prompt + expected anchors (entity + number) + wow line; K1 prompt matches
  preview answer slide in demo-deck
- [ ] **Cross-artifact consistency** — K1 prompt is the same string in
  killer-prompts.md, demo-rehearsal.md T-0, seller-guide.html Act 1, and
  demo-deck.html preview answer slide
- [ ] **No tech jargon leak** — grep demo-deck.html for deny list (MCP,
  UAMI, Bicep, azd, OTel, ACA, DefaultAzureCredential, gpt-5.x, Container
  Apps, FastMCP, region labels). Zero hits.
- [ ] **Seller-guide SE isolation** — in seller mode, grep for the same deny
  list. Zero hits. All engineering content in `se-only` blocks.
- [ ] **Visual validation** — open demo-deck.html in browser at 1440×900.
  Advance through all slides with Space. Verify: no text overflow, every
  slide readable at arm's length, pain numbers visible, no cramped layouts.

---

## Relationship to threadlight-design

This skill is the **lean toolkit equivalent** of the seller-facing artifacts
produced by `threadlight-design`. Both target the same quality bar.

| | threadlight-design | lean-seller-guide v2 |
|---|---|---|
| Input | SPEC.md (13+ structured §§) | spec.md + plan.md + verify.md + deploy.md (flat chain) |
| Pipeline | threadlight (design → deploy → safe-check) | lean toolkit (specify → plan → implement → verify → deploy) |
| Demo deck | `specs/demo-deck.html` (brand-cascade, whitelabel checks) | `docs/demo-deck.html` (brand-neutral Microsoft palette) |
| Prep guide | `specs/prep-guide.html` (5-beat, manifest-driven) | `docs/seller-guide.html` (5-beat, spec-driven) |
| Rehearsal | `specs/demo-rehearsal.md` (killer prompts from eval dataset) | `docs/demo-rehearsal.md` (killer prompts from verify.md) |
| Killer prompts | `tests/killer-prompts.md` (eval-wired, STARTER env vars) | `docs/killer-prompts.md` (verify-wired, not eval-integrated) |
| Experience dossier | `specs/experience.html` (optional cinematic journey) | Not produced (use threadlight-design if needed) |
| Eval scorecard | `tests/eval-summary.md` (from Foundry eval run) | Not produced (verify.md smoke tests serve this role) |
| Timing | Pre-deploy (placeholders) + post-deploy (back-fill) | Post-deploy (one-shot, all live data available) |
| Complexity | ~1700 lines, brand-cascade-aware, manifest-driven | ~500 lines, brand-neutral, file-chain-driven |

Use `threadlight-design` for deep regulated-industry PoCs where a customer SME
reviews the SPEC. Use `lean-seller-guide` for any solution built through the
lean toolkit / agentic-loop flow where the audience is mixed (sellers + SEs)
and the goal is a compelling demo with trustworthy technical depth available
on demand.

## Advanced extensions (from threadlight pipeline)

For scenarios that need more than the lean toolkit provides:

| Need | Install | What it adds |
|------|---------|--------------|
| Human-in-the-loop approval gates | `threadlight-hitl-patterns` | Teams Adaptive Cards, card router, audit trail |
| Operator dashboard | `threadlight-workspace-ui` | React/HTML SPA with streaming, citations, visualizations |
| Scheduled/event-driven triggers | `threadlight-event-triggers` | ACA jobs, Service Bus receivers, cron-triggered agents |
| Realistic demo data | `threadlight-demo-data-factory` | Per-industry Faker generators, Cosmos seed/reset scripts |
| Local iteration without cloud | `threadlight-local-test` | MAF Agent + Streamlit UI on localhost, zero Azure |
| Completeness gate | `lean-safe-check` | 3-phase validation (spec / pre-deploy / post-deploy) |

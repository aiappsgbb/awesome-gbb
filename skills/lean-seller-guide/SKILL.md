---
name: lean-seller-guide
description: >
  Generate a demo deck and seller prep guide from a lean toolkit (Spec2Cloud)
  solution — reads spec.md, plan.md, deploy.md, and the deployed endpoint to
  produce a cinematic HTML demo deck and an internal seller prep guide with
  dual-mode toggle (Seller / SE). Run AFTER /lean:deploy completes. Works
  with any agentic-loop solution, not just threadlight PoCs.
  USE FOR: demo deck, seller guide, demo script, seller prep, field readiness,
  lean toolkit demo, post-deploy seller content, demo preparation, sales
  enablement, pre-sales content, customer demo, demo rehearsal.
  DO NOT USE FOR: threadlight PoCs (use threadlight-design), deploying
  solutions (use /lean:deploy), designing processes (use threadlight-design),
  running agents, general Q&A.
metadata:
  version: "1.0.0"
---

# Lean Seller Guide

## Purpose

Generate **seller-facing demo content** from a deployed lean toolkit (Spec2Cloud)
solution. This skill bridges the gap between the engineering BUILD loop
(Specify → Plan → Implement → Verify → Deploy) and the field SELL motion by
producing two artifacts:

1. **`docs/demo-deck.html`** — a cinematic HTML talk deck for the live customer demo
2. **`docs/seller-guide.html`** — an internal prep guide for the person presenting

Both artifacts are self-contained HTML files that open in any browser and can be
saved as PDF. No server, no build step, no dependencies.

## When to Use

Run this skill **after** `/lean:deploy` completes and the solution is live.
The skill reads:

- `./docs/spec.md` — what was specified (scenario, requirements, non-goals)
- `./docs/plan.md` — what was planned (architecture, resource graph, RBAC)
- `./docs/deploy.md` — what was deployed (URLs, resource IDs, smoke test results)
- The live endpoint — for screenshots and content grounding

## Input Requirements

The skill expects these files in the workspace (produced by the lean toolkit):

| File | Required | Used for |
|------|----------|----------|
| `./docs/spec.md` | Yes | Scenario narrative, agent capabilities, tool descriptions |
| `./docs/plan.md` | Yes | Architecture choices, resource graph, identity model |
| `./docs/deploy.md` | Yes | Live URLs, resource IDs, deployed model, region |
| `azure.yaml` | Optional | Service-to-resource bindings for the architecture diagram |

## Output Artifacts

### 1. `docs/demo-deck.html` — Customer-Facing Demo Deck

A cinematic HTML presentation designed for a 15-20 minute live demo. Each "slide"
is a full-viewport `<section>` that scrolls vertically (no complex JS frameworks).

**Structure (in order):**

| Slide | Content | Source |
|-------|---------|--------|
| Title | Solution name, customer context, date | `spec.md` title + scenario |
| The Challenge | Business problem in customer language (no tech) | `spec.md` scenario + requirements |
| The Solution | One-sentence value prop + 3-4 capability cards with emojis | `spec.md` agent + tool descriptions |
| Architecture | Visual product grid (seller-friendly: Foundry, AI Search, Cosmos, etc.) | `plan.md` resource graph |
| Live Demo | Step-by-step demo flow with screenshots/prompts | `deploy.md` URLs + `spec.md` tools |
| What's Next | Suggested next steps, expansion paths | `spec.md` non-goals as "Phase 2" |
| Contact | Presenter info placeholder | — |

**Design requirements:**

- Full-viewport slides (`min-height: 100vh`)
- Clean sans-serif font (system-ui stack), large text (≥ 28px headings, ≥ 20px body)
- Neutral color palette (dark navy `#1a1a2e`, white cards, blue accents `#0078d4`)
- No tech jargon on any slide (no MCP, UAMI, Bicep, azd, OTel, ACA)
- Product names only: Microsoft Foundry, Azure AI Search, Cosmos DB, App Insights, Entra ID
- Responsive: works on both projected screen (1920×1080) and laptop (1440×900)

### 2. `docs/seller-guide.html` — Internal Seller Prep Guide

> **INTERNAL / MICROSOFT CONFIDENTIAL.** Add to `.gitignore` if repo is shared externally.

A lean companion for the presenter. Helps them prepare for the customer conversation,
run the demo confidently, anticipate questions, and suggest next steps.

**Mandatory UX features:**

1. **Dual-mode toggle** — sticky bar at top with 🎤 Seller / 🔧 SE pills.
   Seller mode hides all `se-only` blocks; SE mode shows them. Mode persists
   via `sessionStorage`.

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
   ```

2. **Sticky sidebar TOC** — fixed left nav with section links. Scroll-spy
   highlights active section. Hides on mobile (`@media max-width: 900px`).

3. **Font sizing** — minimum 20px body, 18px demo steps, 14px absolute minimum.
   The guide is read on a secondary screen at arm's length.

**Sections (in order):**

| § | Section | Content | Source |
|---|---------|---------|--------|
| 0 | Demo Entrypoint | Live URL from deploy, how to launch | `deploy.md` URLs |
| 1 | Executive Summary | 3-sentence pitch: problem, solution, why Microsoft | `spec.md` |
| 2 | Value Proposition | Business outcomes (not features), competitive edge | `spec.md` requirements |
| 3 | Demo Script | Step-by-step with prompts, expected responses, timing | `spec.md` tools + `deploy.md` |
| 4 | Anticipated Questions | FAQ with suggested answers | Derived from spec non-goals + architecture |
| 5 | Architecture | `se-only`: full resource graph. Seller view: product grid | `plan.md` |
| 6 | Next Steps | Phase 2 ideas, production path, pricing discussion points | `spec.md` non-goals |
| 7 | Appendix | `se-only`: exact deployment commands, troubleshooting | `deploy.md` |

**Demo Script rules:**

- Each step: emoji + action + expected result + timing estimate
- Include exact prompts to type ("Ask the agent: ...")
- Include expected agent responses (summarized from `spec.md` tool descriptions)
- Flag any steps that might fail and backup paths
- Total demo time: 15-20 minutes

**No tech jargon outside `se-only` blocks:**
In Seller mode, do NOT show: MCP, Responses API, UAMI, DefaultAzureCredential,
ACA, Bicep, azd, model names (gpt-5.x), Container Apps, FastMCP, OTel, region labels.
Show product names and business outcomes only.

## Workflow

1. Read `docs/spec.md`, `docs/plan.md`, `docs/deploy.md`
2. Extract: scenario narrative, agent capabilities, tool descriptions, architecture,
   deployed URLs, model/region, smoke test results
3. Generate `docs/demo-deck.html` (customer-facing)
4. Generate `docs/seller-guide.html` (internal, dual-mode)
5. Add `docs/seller-guide.html` to `.gitignore` if not already excluded
6. Report both files to the user with instructions to open in browser

## Relationship to threadlight-design

This skill is the **lean toolkit equivalent** of the seller-facing artifacts
produced by `threadlight-design`. The key differences:

| | threadlight-design | lean-seller-guide |
|---|---|---|
| Input | SPEC.md (threadlight format) | spec.md + plan.md + deploy.md (lean toolkit format) |
| Pipeline | threadlight (design → deploy → safe-check) | lean toolkit (specify → plan → implement → verify → deploy) |
| Scope | Full PoC lifecycle including data models, business rules, mock data | Post-deploy seller enablement only |
| Output | demo-deck + experience + prep-guide + demo-rehearsal | demo-deck + seller-guide (leaner) |

Use `threadlight-design` for deep regulated-industry PoCs. Use `lean-seller-guide`
for any solution built through the lean toolkit / agentic-loop flow.

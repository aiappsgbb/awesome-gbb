# Zava — Technical Briefing

> **Architecture reference for the three-skill digital-clone pipeline.**
> The pitch / hero version of this material lives in
> [`zava-experience.html`](zava-experience.html). This file is the
> substrate map: what the control plane contains, how the skills chain,
> what gets deployed, and what the customer sees.

Zava is a **full-stack agentic control plane** — a React 19 + FastAPI
workspace with persona-driven decision orchestration, real-time SSE fleet
telemetry, a knowledge graph, and OpenTelemetry observability. Instead of
showing customers a slide deck, you show them a **living organisational
twin** running their own processes with their named ELT, their industry's
entity kinds, and their brand colours.

The three skills (in pipeline order):

```
research-company → compose-org → zava-workspace-deploy
```

Source repos (MIT):
- [`arturcrmbot/zava-control-plane`](https://github.com/arturcrmbot/zava-control-plane) — the substrate
- [`arturcrmbot/zava-design-skills`](https://github.com/arturcrmbot/zava-design-skills) — `research-company` + `compose-org` + industry primers

---

## When to invoke (entry-skill picker)

| You start with… | Entry skill | Then chain into… |
|---|---|---|
| A customer name, no brief yet | `research-company` | compose-org → zava-workspace-deploy |
| An existing `org-brief.yaml` | `compose-org` | zava-workspace-deploy |
| A branded fork already built, ready to ship | `zava-workspace-deploy` | (deploy) |
| Want to demo the generic substrate, no branding | `zava-workspace-deploy` | (clone + deploy as-is) |

> **Rule of thumb.** `research-company` always runs first unless you already
> have a signed-off org brief. `compose-org` refuses to run without one.
> `zava-workspace-deploy` works on either the generic or branded substrate.

---

## The chain

### 1. `research-company` ([SKILL.md](skills/research-company/SKILL.md))

**Purpose.** Profile the target company against its public web footprint
and emit a thin `org-brief.yaml` overlay.

**Inputs.**
- A company name or domain (e.g., `vodafone.com`, `Contoso Bank`).
- Optional: an industry primer from `skills/research-company/references/`
  (telco, airline, banking, retail, auto-OEM).

**Outputs.**
- `briefs/<slug>-org-brief.yaml` — identity, ownership, ~10 subsidiaries,
  the publicly named ELT (5–12 executives), 3–5 strategic themes, stack
  overrides, regulatory frame.
- Every claim tagged `high`/`medium`/`low`/`inferred` with `source_refs[]`.
- Gaps land in `uncertainties[]` — nothing is invented.

**Wall clock.** 15–40 minutes depending on web-search depth.

### 2. `compose-org` ([SKILL.md](skills/compose-org/SKILL.md))

**Purpose.** Fork the `zava-control-plane` substrate into a
customer-branded digital clone using the signed-off org brief + the
matching industry primer.

**Inputs.**
- `briefs/<slug>-org-brief.yaml` from step 1.
- The matching industry primer (auto-detected from the brief's `industry` field).

**Outputs.**
- `zava-control-plane-<slug>/` — a standalone repo with:
  - Literal token rebrand (company name, brand colours, logo URLs)
  - Data fabric repacked (subsidiaries, customers, services, cadenced rituals)
  - Kuzu entity-kind tables swapped to the vertical's canonical set
  - Function registry + persona folders regenerated for the named ELT
  - Domain registry extended with 25–35 vertical workflow stubs
  - Node MCP mocks scaffolded for any disclosed stack overrides
  - Data fabric snapshot re-seeded

**Wall clock.** 30–60 minutes. Pauses for operator approval at each
destructive phase.

### 3. `zava-workspace-deploy` ([SKILL.md](skills/zava-workspace-deploy/SKILL.md))

**Purpose.** Build the React SPA, package with FastAPI (or nginx), and
deploy to Azure Container Apps with OpenTelemetry telemetry.

**Inputs.**
- The branded (or generic) `zava-control-plane-<slug>/` fork.
- An Azure subscription with ACA environment.

**Outputs.**
- Live ACA workspace at `https://<app>.azurecontainerapps.io/`
- OTel spans flowing to App Insights
- 170 API routes, SSE fleet streams, React dashboard

**Wall clock.** ~5 minutes (docker build + push + ACA revision).

---

## Substrate architecture

The `zava-control-plane` substrate is a monorepo:

```
zava-control-plane/
├── api/
│   ├── server/routes/          # 167 FastAPI routes across 37 domains
│   ├── shared/types.py         # Pydantic models (THE contract)
│   ├── shared/domains.py       # 37-domain registry
│   └── shared/events.ts        # SSE event type definitions
├── web/
│   ├── client/                 # React 19 + Vite 6 + TailwindCSS 4
│   ├── portal/                 # Candidate portal SPA
│   └── blueprint/              # Blueprint microsite SPA
├── tools/                      # 45+ MCP tool functions
├── data-fabric/                # Kuzu graph DB, seed data, generators
└── functions/                  # Azure Durable Functions orchestrators
```

### Domain registry (37 domains)

The substrate ships 12 **operational** domains (full workflow lifecycle)
and 25 **strategic/cadence** domains (stubs for the compose phase to fill):

**Operational (12):**
`expense-claim` · `travel-preapproval` · `vendor-kyc` ·
`employee-onboarding` · `it-access-request` · `contract-renewal` ·
`perf-review` · `ap-invoice` · `purchase-order` · `contract-review` ·
`privacy-dpia` · `treasury-fx`

**Strategic/cadence (25):**
`hiring` · `creative-campaign` · `employee-transfer` ·
`training-request` · `budget-approval` · `facility-request` ·
`fleet-maintenance` · `insurance-claim` · `loan-origination` ·
`regulatory-filing` · and 15 more defined by the industry primer.

### Route families

| Family | Routes | What it covers |
|--------|--------|----------------|
| Workflows | ~25 | CRUD, tree, in-flight, timeline, by-domain, compose, start |
| Exceptions | ~8 | List, resolve, bulk-resolve, by-workflow |
| Entities | ~12 | List, graph, kinds, stats, pulse, linked, precedents, touched-by |
| SSE Streams | ~5 | Fleet, fleet-manager, orchestration ticker, per-function ambient |
| Blueprint | ~4 | Composition, stream, demo-stream, recorder |
| Policy | ~8 | CRUD, dry-run, propose, change-requests, markdown export |
| Governance | ~6 | Verify, kill CRUD, authority matrix |
| Functions | ~7 | Registry, per-function detail, SSE ambient |
| Personas | ~8 | List, detail, colours, arcs, archetypes |
| Memory | ~8 | v1/v2, dream, recall, seed-demo, history, per-persona |
| Simulator | ~15 | Inject, burst, constellation, fleet-tick, per-domain triggers |
| KPIs | ~4 | Agency, history, decision-latency |
| Fleet economics | ~3 | Summary, by-domain, trending |
| Evals & accuracy | ~6 | List, summary, health, detail, per-domain |
| Portal | ~5 | Apply, status, offer, admin, interview |
| Voice portal | ~5 | Session, RTC, resolve, transcript, canned |
| Demo triggers | ~8 | Brand-overrun, aurora, FX, reset, etc. |
| Misc | ~15 | Accounts, cities, cadences, audit, network, insights, learning |

### SSE event catalog

The control plane emits real-time events via Server-Sent Events (SSE).
The React frontend subscribes to these for live dashboard updates:

| Event | When |
|-------|------|
| `workflow.started` | New workflow instance begins |
| `workflow.phase.started` | A phase within a workflow starts |
| `workflow.phase.completed` | A phase completes successfully |
| `workflow.phase.failed` | A phase fails (retry or escalate) |
| `workflow.exception.detected` | Exception raised during workflow |
| `workflow.hitl.requested` | Human-in-the-loop gate reached |
| `workflow.resolved` | Exception resolved (human or auto) |
| `workflow.completed` | Workflow instance finishes |
| `workflow.sla.breach_imminent` | SLA threshold approaching |
| `workflow.policy.violation` | Policy rule violated |
| `otel.span.emitted` | OTel span recorded |
| `fleet.tick` | Periodic simulator heartbeat |
| `fleet.anomaly.detected` | Anomaly detector fires |
| `fleet.overload` | Load threshold exceeded |

### Pydantic model contract

All API responses use Pydantic v2 with `alias_generator=to_camel`:
Python models are `snake_case`, JSON responses are `camelCase`. This is
the contract the React frontend depends on — never send `snake_case` JSON.

---

## ACA deployment pattern

The `zava-workspace-deploy` skill ships the substrate as a single
Azure Container App:

```
┌──────────────────────────────────────┐
│  Azure Container App (port 8000)     │
│  ┌────────────────────────────────┐  │
│  │  FastAPI (uvicorn)             │  │
│  │  ├── /api/* routes (170)       │  │
│  │  ├── /api/stream/* SSE         │  │
│  │  ├── /health                   │  │
│  │  └── /* → static/index.html    │  │
│  │      (React SPA fallback)      │  │
│  └────────────────────────────────┘  │
│  ┌────────────────────────────────┐  │
│  │  OTel → App Insights           │  │
│  │  (azure-monitor-opentelemetry)  │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

**Key design decisions:**
- **Single container** — the original substrate uses Azure Durable Functions +
  separate SPA hosts. For demo/PoC, a single FastAPI container serving both
  the API and the built React bundle is simpler and cheaper.
- **In-memory orchestration** — replaces Durable Functions with async Python
  coroutines. Same API surface, no external storage dependency.
- **OTel from day one** — `azure-monitor-opentelemetry` auto-instruments
  FastAPI; every request generates spans in App Insights. The `otel.span.emitted`
  SSE event makes telemetry visible in the dashboard.

### Deploy command

```bash
cd zava-control-plane-<slug>
AZURE_CONFIG_DIR=~/.azure-<tenant> azd up
```

---

## How to demo Zava

### Prerequisites

| What | Why |
|------|-----|
| A deployed Zava workspace (ACA URL) | `zava-workspace-deploy` ships this in ~5 min |
| Edge or Chrome (SSE streams need modern EventSource) | Firefox works but lacks the network tab's SSE inspector |
| A second terminal (optional) | For live `curl` calls while the audience watches the dashboard |

### Quick-start: generic substrate (no branding)

If you just need a demo and don't need the customer's brand:

```bash
# Clone the upstream substrate
git clone https://github.com/arturcrmbot/zava-control-plane /tmp/zava-demo
cd /tmp/zava-demo

# Deploy (zava-workspace-deploy handles build + ACA setup)
# The skill will ask for subscription and region — pick swedencentral for lowest latency
AZURE_CONFIG_DIR=~/.azure-<tenant> azd up
```

The dashboard URL appears in the deploy output. Open it in Edge.

### Demo script (10–15 min)

#### Scene 1 — "The org is alive" (2 min)

Open the dashboard root URL. The customer sees:
- **Workflows in flight** — 1 500+ workflows auto-seeded across 12 domains
- **Personas panel** — named executives with coloured avatars and narrative arcs
- **KPI tiles** — agency score, decision latency, fleet economics

> **Talk track:** *"This isn't a wireframe — every workflow, every persona,
> every KPI is live. The data is synthetic but the API surface is identical
> to what runs in production. Let me show you what's behind the curtain."*

#### Scene 2 — "Inject and watch" (3 min)

In a second terminal (or Copilot CLI), inject a burst of expense claims:

```bash
# Inject 5 expense claims
curl -s "$ZAVA_URL/api/simulator/inject" \
  -X POST -H 'Content-Type: application/json' \
  -d '{"domain":"expense-claim","count":5}' | jq .

# Or trigger a full fleet tick (all domains fire)
curl -s "$ZAVA_URL/api/simulator/fleet-tick" -X POST | jq .
```

Switch to the dashboard — the injected workflows appear in real time via SSE.
The audience watches new rows animate in, phases progress, personas make decisions.

> **Talk track:** *"I just triggered 5 new expense claims. Watch the
> dashboard — the SSC Reviewer persona picks them up, checks policy, and
> either auto-approves or escalates to the Finance Controller. All
> decisions are logged, all telemetry flows to App Insights."*

#### Scene 3 — "The API is real" (3 min)

Show the API surface by hitting key endpoints:

```bash
# Health — shows domains, workflow count, simulator status
curl -s "$ZAVA_URL/health" | jq .

# Personas — the named ELT with roles, archetypes, decision counts
curl -s "$ZAVA_URL/api/personas" | jq '.[0:3]'

# KPIs — agency score (how much the AI decides vs. humans)
curl -s "$ZAVA_URL/api/kpis/agency" | jq .

# Fleet economics — cost/throughput per domain
curl -s "$ZAVA_URL/api/fleet/economics" | jq .

# OpenAPI spec — the full contract
curl -s "$ZAVA_URL/openapi.json" | jq '.paths | keys | length'
# → 170
```

> **Talk track:** *"170 routes, 12 domains, 9 SSE event types. This
> isn't a mock — it's the same FastAPI surface your production agents will
> talk to. Every endpoint is documented in the OpenAPI spec."*

#### Scene 4 — "What-if scenarios" (3 min)

Trigger scenario simulators that make the dashboard light up:

```bash
# Scenario: a region fails — watch cascading exceptions
curl -s "$ZAVA_URL/api/simulator/region-failure" -X POST | jq .

# Scenario: a repeat-offender vendor triggers compliance escalation
curl -s "$ZAVA_URL/api/simulator/repeat-offender" -X POST | jq .

# Scenario: a client loss crisis — executive personas convene
curl -s "$ZAVA_URL/api/simulator/crisis/client-loss" -X POST | jq .
```

> **Talk track:** *"These aren't scripted demos — the simulator fires real
> events through the same pipeline your production agents will use. When
> a region fails, the treasury persona hedges, the HR persona pauses
> onboarding, and the dashboard shows the cascade in real time."*

#### Scene 5 — "Your org, your brand" (2 min)

If you ran `research-company` + `compose-org` earlier, the dashboard already
shows the customer's brand, their named executives, their industry's entity
kinds. Point this out:

> **Talk track:** *"This morning we profiled your company from public
> sources. The executives you see here are your real C-suite. The domains
> map to your industry. The brand colours are yours. And it took three
> Copilot skills and about 90 minutes."*

### Key API endpoints for demo

| Endpoint | Method | What it shows |
|----------|--------|---------------|
| `/health` | GET | Domains, workflow count, simulator on/off |
| `/api/workflows?limit=10` | GET | Latest workflows with status + phase |
| `/api/personas` | GET | Named personas with archetypes + decision counts |
| `/api/kpis/agency` | GET | Agency score — AI vs. human decision ratio |
| `/api/kpis/decision-latency` | GET | P50/P95/P99 decision time |
| `/api/fleet/economics` | GET | Cost + throughput per domain |
| `/api/functions` | GET | Function registry (departments) |
| `/api/entities/_stats` | GET | Knowledge graph entity/relationship counts |
| `/api/entities/_pulse` | GET | Recent entity activity |
| `/api/blueprint/composition` | GET | Org composition tree |
| `/api/simulator/inject` | POST | Inject workflows (`{"domain":"...","count":N}`) |
| `/api/simulator/fleet-tick` | POST | Tick all domains (full fleet heartbeat) |
| `/api/simulator/seed-decisions` | POST | Seed persona decisions for agency score |
| `/api/simulator/seed-kpis` | POST | Seed KPI history data |
| `/api/stream/fleet` | GET (SSE) | Real-time fleet event stream |
| `/api/stream/fleet-manager` | GET (SSE) | Manager-level aggregated stream |
| `/openapi.json` | GET | Full OpenAPI 3.1 spec (170 routes) |

### Warming up the demo

The simulator auto-seeds 1 500 workflows on first boot, but KPIs and
persona decisions start at zero. Seed them before the customer arrives:

```bash
# Seed persona decisions (populates agency score)
curl -s "$ZAVA_URL/api/simulator/seed-decisions" -X POST | jq .

# Seed KPI history (populates trend charts)
curl -s "$ZAVA_URL/api/simulator/seed-kpis" -X POST | jq .

# Inject a burst across all domains (makes the dashboard lively)
curl -s "$ZAVA_URL/api/simulator/inject-burst" -X POST \
  -H 'Content-Type: application/json' \
  -d '{"count_per_domain":3}' | jq .
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dashboard shows "connecting…" forever | SSE stream blocked by proxy | Try direct ACA URL, not via corp proxy |
| `/health` returns 502 | Container cold-starting | Wait 15–30 s (ACA min-replicas = 0 by default) |
| KPIs show 0 / no agency score | Decisions not seeded | Run `seed-decisions` + `seed-kpis` |
| Workflows stuck at `in_progress` | Simulator runs but doesn't advance phases | Hit `fleet-tick` to advance; phases auto-advance on a timer |
| OTel not appearing in App Insights | ikey auth disabled, or AI resource misconfigured | Check `APPLICATIONINSIGHTS_CONNECTION_STRING` env var on the ACA |

---

## How Zava + Threadlight compose

### The two halves of the story

**Threadlight** and **Zava** solve different problems at different altitudes:

| | Threadlight | Zava |
|---|---|---|
| **Question it answers** | *"Can we automate this one business process?"* | *"What does the whole organisation look like when AI runs it?"* |
| **Scope** | One business process (expense claims, vendor KYC, claims adjudication) | The entire organisation — 12+ domains, 37 entity kinds, named ELT |
| **Entry point** | `threadlight-design` (in Cowork or CLI) | `research-company` (CLI) |
| **What it builds** | A Foundry hosted agent with MCP tools, eval dataset, and HITL gates | A full-stack control-plane (React + FastAPI) with personas, SSE streams, knowledge graph |
| **Output the customer sees** | A working agent that processes cases in their business domain | A living dashboard with their executives, their brand, their processes running |
| **Technical artefact** | Foundry Agent + ACA MCP servers + Cosmos + App Insights | ACA container with 170 API routes + OTel + SSE |
| **Demo pitch** | *"Here's your claims agent — watch it adjudicate this case"* | *"Here's your entire org — watch 12 process types running simultaneously"* |
| **Telemetry** | Per-agent traces in App Insights | Fleet-wide OTel + SSE real-time dashboard |
| **Wall clock** | 2–4 hours (design → deploy) | 60–90 min (research → compose → deploy) |

### When to use which

| Customer conversation | Use | Why |
|---|---|---|
| *"Show me AI can handle our claims process"* | Threadlight alone | Single process, deep agent demo |
| *"What would an AI-first operating model look like?"* | Zava alone | Fleet-level vision, org-wide dashboard |
| *"We want to see both: the vision AND a working agent"* | Zava + Threadlight | Morning = vision, afternoon = working agent, end of day = both |
| *"We have 5 processes we want to automate"* | Zava + Threadlight | Zava maps the fleet, Threadlight deep-dives 2–3 hero processes |
| Quick internal demo, no customer prep time | Zava generic substrate | Clone + deploy in 10 min, no research/compose needed |

### The full-day workshop (Zava + Threadlight)

This is the recommended flow for strategic accounts where the customer
wants both the vision and a working proof:

```
 Morning (90 min)           Midday (60 min)              Afternoon (90 min)        End of day
┌───────────────────┐  ┌──────────────────────┐  ┌──────────────────────────┐  ┌──────────────┐
│ research-company  │  │ threadlight-design    │  │ threadlight-deploy       │  │ Customer has: │
│ → org-brief.yaml  │→ │ → SPEC.md for 2–3    │→ │ → Foundry agents live    │→ │ • branded     │
│                   │  │   hero processes      │  │                          │  │   dashboard   │
│ compose-org       │  │                       │  │ zava-workspace-deploy    │  │ • 2–3 live    │
│ → branded fork    │  │                       │  │ → dashboard live on ACA  │  │   agents      │
└───────────────────┘  └──────────────────────┘  └──────────────────────────┘  │ • unified     │
                                                                               │   telemetry   │
                                                                               └──────────────┘
```

**Step-by-step commands:**

```bash
# ── Morning: build the org substrate ──
# 1. Profile the customer (15–40 min)
# → Opens research-company skill, produces org-brief.yaml
copilot "research Contoso Bank for a digital-clone demo"

# 2. Compose the branded fork (30–60 min)
# → Opens compose-org skill, produces zava-control-plane-contoso-bank/
copilot "compose the Contoso Bank org using the brief we just created"

# ── Midday: design hero processes ──
# 3. Design 2–3 hero processes within the substrate
copilot "design a vendor-kyc process for Contoso Bank"
copilot "design an expense-claim process for Contoso Bank"
# → Each produces SPEC.md + AGENTS.md + skill files

# ── Afternoon: deploy everything ──
# 4. Deploy the hero agents
copilot "deploy the vendor-kyc agent to Foundry"
copilot "deploy the expense-claim agent to Foundry"
# → Each runs threadlight-deploy → ACA + Foundry hosted agent

# 5. Deploy the branded dashboard
cd zava-control-plane-contoso-bank
AZURE_CONFIG_DIR=~/.azure-<tenant> azd up
# → ACA with 170 routes, branded dashboard, OTel flowing
```

**What the customer sees at end of day:**

1. **The dashboard** — their brand, their executives, their 12+ domains,
   workflow counts ticking up in real time
2. **The hero agents** — click through from the dashboard to see the
   vendor-kyc agent adjudicating a case, the expense-claim agent
   routing approvals
3. **Unified telemetry** — both the dashboard's fleet-level OTel and
   the individual agent traces in the same App Insights workspace
4. **The pitch** — *"This is what your org looks like when AI runs the
   back office. The dashboard is the control plane. The agents are the
   workers. The telemetry is the proof. And we built it all today."*

### Technical integration points

When both Zava and Threadlight are deployed in the same subscription:

| Integration | How | Status |
|---|---|---|
| **Shared App Insights** | Both `foundry-observability` and `zava-workspace-deploy` write to the same workspace if you set the same `APPLICATIONINSIGHTS_CONNECTION_STRING` | ✅ Works today |
| **Dashboard → Agent deep-link** | The Zava dashboard links to per-domain agent endpoints via the function registry | 🔧 Requires manual config of agent URLs in the function registry |
| **SSE from agents into fleet stream** | Threadlight agents can POST events to Zava's `/api/stream/fleet` ingress endpoint | 🔧 Planned — not yet wired |
| **Shared Cosmos** | Both can use the same Cosmos account (different databases) | ✅ Works today |

---

## See also

- [README.md](README.md) — public catalog and install instructions
- [THREADLIGHT.md](THREADLIGHT.md) — Threadlight pipeline technical briefing
- [`skills/research-company/SKILL.md`](skills/research-company/SKILL.md)
- [`skills/compose-org/SKILL.md`](skills/compose-org/SKILL.md)
- [`skills/zava-workspace-deploy/SKILL.md`](skills/zava-workspace-deploy/SKILL.md)
- [`arturcrmbot/zava-control-plane`](https://github.com/arturcrmbot/zava-control-plane) — upstream substrate
- [`arturcrmbot/zava-design-skills`](https://github.com/arturcrmbot/zava-design-skills) — design skills + industry primers

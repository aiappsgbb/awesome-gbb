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

## How Zava + Threadlight compose

| Dimension | Threadlight | Zava | Together |
|-----------|------------|------|----------|
| **Scope** | One business process | Multi-domain organisation | Enterprise operating system |
| **Entry point** | `threadlight-design` (seller/Cowork) | `research-company` (company profiling) | Research → Design per-process → Compose → Deploy |
| **Output** | Deployed Foundry hosted agent | Deployed control-plane dashboard | Dashboard orchestrating Foundry agents |
| **Persona** | Process-level (claims adjuster) | Org-level (CFO, CISO, COO) | Both — executive personas drive fleet, process personas handle cases |
| **Telemetry** | Per-agent App Insights | Fleet-wide OTel + SSE | Unified observability |
| **Demo pitch** | "Here's your claims agent running" | "Here's your org running 12 processes" | "Here's your org, and here's what happens when a new claim arrives" |

**Typical workshop flow:**
1. Morning — `research-company` + `compose-org` (branded substrate)
2. Midday — `threadlight-design` for 2–3 hero processes within the substrate
3. Afternoon — `threadlight-deploy` for the hero agents + `zava-workspace-deploy` for the dashboard
4. End of day — customer has a branded control plane showing their org structure with live agents processing demo cases

---

## See also

- [README.md](README.md) — public catalog and install instructions
- [THREADLIGHT.md](THREADLIGHT.md) — Threadlight pipeline technical briefing
- [`skills/research-company/SKILL.md`](skills/research-company/SKILL.md)
- [`skills/compose-org/SKILL.md`](skills/compose-org/SKILL.md)
- [`skills/zava-workspace-deploy/SKILL.md`](skills/zava-workspace-deploy/SKILL.md)
- [`arturcrmbot/zava-control-plane`](https://github.com/arturcrmbot/zava-control-plane) — upstream substrate
- [`arturcrmbot/zava-design-skills`](https://github.com/arturcrmbot/zava-design-skills) — design skills + industry primers

# Threadlight: Design → Deploy → Demo

Threadlight is a **skill pipeline** for going from a vague customer requirement to a
working Foundry agent demo. It's built for rapid, repeatable PoC delivery by
AI Global Black Belts.

```
                    Customer brief
                          │
                          ▼
              ┌──────────────────────┐
              │  threadlight-design  │  → specs/ (SPEC.md, manifest.json, sample-data, overview.html)
              │   (sellers · Cowork) │     + AGENTS.md + skills/
              └──────────┬───────────┘
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
 foundry-mcp-aca   threadlight-          foundry-iq
 (mock MCP for     local-test            (RAG over your
  inaccessible     (SE inner-loop:       knowledge bases)
  systems)         FoundryChatClient
                   + FastMCP locally,
                   no `azd up` needed)
                         │
                         ▼ (ready to ship)
              ┌──────────────────────┐    ┌──────────────────────┐
              │ threadlight-safe-    │ ←  │  threadlight-deploy  │  → `azd up` → Foundry Hosted Agent
              │ check (pre-deploy)   │    │  (Bicep modules,     │     + ACA MCP + cron jobs + bot
              └──────────┬───────────┘    │   container.py, …)   │
                         │                └──────────┬───────────┘
                         ▼ deploy-time ──────────────┘
              ┌──────────────────────┐
              │ threadlight-safe-    │  → image-probe, job-success, AppIn presence
              │ check (post-deploy)  │     (catches silent partial deploys)
              └──────────┬───────────┘
                         │
   ┌─────────────────────┼──────────────────────┐
   ▼                     ▼                      ▼
foundry-evals    foundry-observability    foundry-teams-bot / -workspace-ui
(score it)       (App Insights + OTel     (expose it to humans)
                  traces from day one)
```

---

## The Pipeline

### 1. Spec It — `threadlight-design`

Turn a vague customer brief into a **durable SpecKit specification**:

- **Discovery interview** — trait-based questions (not fixed archetypes) adapt to any domain
- **SpecKit output** — `specs/SPEC.md` with numbered business rules (BR-XXX), data models
  with system-of-record tracking, tool contracts, system integrations (marking which are mock),
  human interaction points, compliance/governance, eval scenarios
- **Mock data** — `specs/sample-data/*.json` tied to the data models, with migration guide
- **Implementation artifacts** — AGENTS.md + skills derived from the spec, each tracing
  back to specific business rules
- **Seller pitch page** — `specs/overview.html`, a self-contained dark-themed HTML page
  showing the process flow, business rules, data models, integration status badges
- **Workshop dashboard** — optional React app (`specs/dashboard/`) for interactive
  exploration with the customer

**Two modes:**

| Mode | When | What you get |
|------|------|-------------|
| **Full** | Production-bound, stakeholder review | Full interview → checkpoint → review → generate |
| **Fast-PoC** | Demos, rapid prototyping | 2-3 questions → assume defaults → everything in one pass |

**Domain primers** (optional) — for well-known domains like FSI/KYC, a primer file
pre-loads typical business rules, data models, regulations, and vocabulary to accelerate
discovery. Currently available: `fsi-kyc-aml.md`. Team can add more.

### 2. Mock It — `foundry-mcp-aca`

For backend systems you can't access (SAP, Oracle, CRM, corporate DBs):

- Generate a **FastMCP mock server** backed by `specs/sample-data/*.json`
- Tools match the spec's § 6 tool contracts — customer sees real MCP tool calls
- Deploy locally or to ACA — agent connects via `mcp-config.json`
- **Swap path**: when the real system is available, customer changes one URL. Tool
  contracts stay the same — no agent rewrite needed

### 3. Iterate Locally — `threadlight-local-test` *(optional, SE-recommended)*

Before burning a full `azd up` cycle on a customer sandbox, the SE can run the
designed agent **locally** in Copilot CLI / Cowork / Clawpilot:

- Three patterns: MCP-direct (point Copilot at a local FastMCP), full local
  loop (FoundryChatClient against the deployed Foundry account, MCP and
  workspace local), or workspace-only (UI-driven smoke test)
- Pluggable Cosmos via the multi-arch emulator + well-known key
- No tear-down between iterations — change a tool, re-run, demo it

**When to skip:** if the design is a one-shot demo or already-deployed pilot
the SE just needs to refresh.

### 4. Deploy It — `threadlight-deploy`

Generate all Foundry deployment artifacts from the spec + agents:

- `container.py` — GHCP SDK runtime by default (CopilotClient + InvocationAgentServerHost);
  falls back to MAF (Agent + FoundryChatClient + ResponsesHostServer) when Toolbox needed
- `Dockerfile` — uv-based, python:3.12-slim
- `pyproject.toml` — with prerelease handling for hosting packages
- `agent.yaml` + `azure.yaml` — azd ai agent extension scaffold
- `infra/` — vendored Bicep modules per SPEC § 11c selectors (Foundry account,
  ACR, App Insights, Cosmos, AI Search, Service Bus, etc.)
- `mcp-config.json` — wired to mock MCP endpoints (or real ones)
- `copilot-instructions.md` — system prompt derived from AGENTS.md
- `deploy-notes.md` — full deployment guide with mock system warnings

**One command**: `azd up` provisions, builds, deploys, creates the agent.

The skill reads `specs/SPEC.md` for compliance constraints, model selection, trigger
patterns, and mock system handling. It cross-references `foundry-hosted-agents` for
RBAC, `foundry-mcp-aca` for MCP deployment, and `foundry-observability` for the
3-layer telemetry wiring (Bicep substrate → Foundry account-level AppIn connection
→ `configure_azure_monitor()` in each ACA workload).

### 5. Verify It — `threadlight-safe-check` *(mandatory)*

Run after design (pre-deploy) and again after `azd up` (post-deploy). Catches
the silent failure modes that `azd` reports as success:

- **Pre-deploy:** every SPEC § 11c selector maps to a Bicep module +
  `azure.yaml` service + `src/<dir>/`; no orphan modules
- **Post-deploy:** every selector landed as a deployed `Microsoft.*` resource;
  no container running the placeholder helloworld image; no scheduled job
  whose last 5 runs all failed; App Insights resource exists if SPEC declared
  it

> **The Card Dispute v3 audit caught 10 distinct gaps despite `azd up`
> returning 0.** Phase 22 hardening (image-probe + job-success) and Phase 25
> Step 5.6 (App Insights presence) make those gaps fail the gate, not ship
> silently.

### 6. Expose It — `foundry-teams-bot` + `threadlight-workspace-ui` *(optional)*

Two human-facing surfaces:

- **Teams bot** (`foundry-teams-bot`) — Copilot CEA manifest 1.21, bot code,
  Bicep (UAMI + Bot Service + ACA), Teams sideloading. Adaptive Cards 1.5
  for action gates (paired with `threadlight-hitl-patterns`).
- **Workspace UI** (`threadlight-workspace-ui`) — case-list / inbox /
  dashboard / kanban / map shape per process. **ACA-hosted**, not file://
  (mandate). Easy Auth via Entra.

Either, both, or neither — driven by SPEC § 8.

### 7. Eval It — `foundry-evals`

Score the demo using Foundry's built-in evaluators:

- Two-phase invoke+score pattern (workaround for SDK routing bug)
- 6 evaluators: task adherence, completion, intent resolution, coherence,
  tool selection, tool output utilization
- Test dataset auto-generated from spec § 9 eval scenarios (S-XXX ← BR-XXX)
- **Enriched dataset shape** (`tool_calls` + `tool_outputs`) so
  `tool_output_utilization` doesn't FAIL every grounded answer as fabricated
- Tool-use discipline guidance to avoid over-calling tools (kills eval scores)

### 8. Observe It — `foundry-observability`

Always layered into deploy from day one:

- **Layer 1 (Bicep substrate):** App Insights workspace-based + Log Analytics +
  ACA env wiring (always included)
- **Layer 2 (Foundry account-level connection):** postprovision script PUTs the
  AppIn connection on the **account** (not project) so hosted agents
  auto-inject `APPLICATIONINSIGHTS_CONNECTION_STRING`
- **Layer 3 (ACA workload OTel init):** `configure_azure_monitor()` wrapped
  with local-dev safety so `threadlight-local-test` runs don't error

Plus 4 KQL starter queries (first-trace probe, agent-traces, MCP-tool-calls,
silent-cron debug) and a 10-row gap catalog. Closes the silent gap where
`azd up` returned 0 but App Insights stayed empty for the entire pilot
lifetime.

### 9. Land It — `citadel-spoke-onboarding` *(when customer is ready)*

When the PoC becomes production, onboard onto a Citadel landing zone:

- APIM gateway with products + subscriptions
- Access contracts (Bicep parameters + policy XML)
- Key Vault for endpoint + API key storage
- JWT authentication on top of managed identity

---

## Fast-PoC Baseline

Every PoC, regardless of mode, ships with these guarantees:

| Guarantee | How |
|-----------|-----|
| **Keyless auth** | `DefaultAzureCredential` everywhere — no API keys |
| **Callable tools** | Mock MCP server for inaccessible systems — agent actually works |
| **Eval-ready** | Eval dataset from spec scenarios — score the demo on day one |
| **Deployable** | `azd up` scaffold — one command to hosted agent |
| **Pitch-ready** | `specs/overview.html` — open in browser, show the customer |
| **Assumptions documented** | Spec § 12 flags everything assumed (stateless, read-only, etc.) |

---

## What Gets Generated

```
project/
├── specs/
│   ├── SPEC.md                    # SpecKit specification (the durable source of truth)
│   ├── manifest.json              # Machine-readable deployment contract
│   └── sample-data/               # Mock data for inaccessible systems
│       ├── {entity}.json
│       └── README.md              # Migration guide (mock → real)
│
├── .github/skills/                # Coding/dev skills only (NOT process skills)
├── .vscode/mcp.json               # Dev-time MCP config (local servers)
│   └── {skill-name}/SKILL.md
├── AGENTS.md                      # Agent identity, tools, guidelines
│
│   ├── overview.html              # Seller pitch page (self-contained)
│   ├── prep-guide.html           # ⚠️ INTERNAL ONLY — seller prep (add to .gitignore)
│   ├── dashboard/                 # Interactive workshop app (optional, React)
│
├── src/
│   ├── agent/                     # Hosted agent container (from threadlight-deploy)
│   │   ├── container.py           # GHCP SDK runtime (default) or MAF
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── copilot-instructions.md
│   │   ├── skills/                # Process skills (from threadlight-design)
│   │   ├── config/                # Process configuration (URLs, thresholds)
│   │   └── mcp-config.json        # Runtime MCP config
│   │
│   ├── mcp/                       # Mock MCP server (from foundry-mcp-aca)
│   │   ├── server.py              # FastMCP tools backed by sample data
│   │   ├── data/                  # Copied from specs/sample-data/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── bot/                       # Teams bot (optional, from foundry-teams-bot)
│       ├── bot.py, app.py, Dockerfile
│       ├── build_manifest.py      # Builds copilot_package.zip
│       └── teams_package/
│
├── agent.yaml                     # ⚠️ MUST be at root (azd ai agent reads this)
├── azure.yaml                     # ⚠️ MUST be at root (azd reads this)
├── infra/                         # Bicep scaffold
├── scripts/                       # Infra hooks only (postprovision, postdeploy)
├── tests/                         # Test/invocation scripts
│   └── invoke_agent.py            # Smoke test — invoke the deployed agent
└── deploy-notes.md                # Deployment guide
```

---

## Companion Skills

| Skill | Role | Required? |
|-------|------|-----------|
| `foundry-hosted-agents` | RBAC, identity model, agent.yaml schema, model defaults (gpt-5.4 for production), MCP wiring | **Always** |
| `foundry-mcp-aca` | MCP server deployment (mock or real) — including the validate-or-reject evidence pattern | When mocking systems |
| `foundry-observability` | App Insights + OTel telemetry from day one — closes the silent gap | **Always** (`azd up` doesn't guarantee telemetry without this) |
| `threadlight-safe-check` | Pre-deploy + post-deploy completeness gate — image-probe, job-success, AppIn presence | **Always** (run before and after every deploy) |
| `threadlight-local-test` | SE inner-loop iteration without `azd up` — Cowork-friendly | Recommended for SEs |
| `threadlight-event-triggers` | Non-interactive trigger receivers (ACA Jobs cron + KEDA consumers) | When SPEC § 10b declares triggers |
| `threadlight-workspace-ui` | Workspace UI per process — ACA-hosted, Easy Auth | When SPEC § 8 declares a workspace |
| `threadlight-hitl-patterns` | Adaptive Card 1.5 flows for the 7 canonical action gates | When SPEC § 8 has HITL gates |
| `threadlight-demo-data-factory` | Synthetic data + Cosmos seed/reset (anchored on industry realism canons) | When SPEC § 11d declares demo data |
| `foundry-evals` | Post-deployment evaluation patterns + continuous loop | For scoring demos |
| `foundry-teams-bot` | Teams + M365 Copilot CEA integration | When Teams or M365 Copilot needed |
| `foundry-iq` | Enterprise RAG with agentic retrieval | When knowledge grounding needed |
| `foundry-doc-vision-speech` | Vision (gpt-5.4 family), DocIntel v4, Speech (STT/TTS) | When SPEC § 7b needs document/image/voice modalities |
| `ghcp-hosted-agents` | GHCP SDK runtime (Invocations protocol, SSE) | For long-running agents (>120s) |
| `azd-patterns` | azd hooks, ACA Job deployment, **silent-failure debug ladder** | For advanced azd workflows |
| `azure-tenant-isolation` | Multi-tenant `az` / `azd` isolation for concurrent shells | When working across >1 Azure tenant |
| `citadel-spoke-onboarding` | Production landing zone — APIM, Access Contracts, JWT | Post-pilot opt-in |

---

## Running a Customer Workshop

> **Personas:** sellers craft the pitch in **Copilot Cowork** with `threadlight-design`; SEs run hands-on workshops with `threadlight-local-test` and/or `threadlight-deploy`.

A typical 2-hour customer workshop on a deployed PoC follows this rough rhythm. (For a deeper facilitator runbook with timing, demo scripts, and per-process beats, ask the SE to consult the `WORKSHOP-RUNBOOK.md` in their threadlight workspace.)

| Phase | Time | What | Skill |
|-------|------|------|-------|
| **Pre-flight (before the customer joins)** | 10 min | Tenant/sub isolation guard; smoke probe agent + MCP; reset demo data | `azure-tenant-isolation`, `threadlight-demo-data-factory` |
| **0 — Frame the pain** | 10 min | Walk the seller pitch (`specs/overview.html`); confirm the named pain still resonates | `threadlight-design` (output) |
| **1 — Walk the SPEC** | 25 min | Read SPEC § 1 (pain), § 5–6 (data + tools), § 8 (HITL gates), § 9 (eval scenarios) on screen with the LOB SME | `threadlight-design` (output) |
| **2 — Live demo** | 30 min | One golden-path scenario end-to-end — agent reasoning trace + tool calls + audit trail visible in workspace | `threadlight-deploy` (deployed) + `threadlight-workspace-ui` |
| **3 — Push the edges** | 20 min | Run 2–3 hard scenarios from § 9; show how HITL gates fire; show observability traces in App Insights | `foundry-evals`, `foundry-observability` |
| **4 — Customize live** | 20 min | Tweak a business rule or add a tool inline; re-run the case in `threadlight-local-test` to show iteration speed | `threadlight-local-test` |
| **5 — Hand-off** | 5 min | Show the `azd up` flow + the safe-check post-deploy gate; agree next steps | `threadlight-deploy`, `threadlight-safe-check` |

> [!TIP]
> **Mandatory pre-flight checks** to avoid mid-workshop embarrassment: (1) `az account show` matches the customer's sandbox sub; (2) `threadlight-safe-check --phase post-deploy` returns `gaps: []`; (3) one warm-up agent call has succeeded in the last 5 minutes (cold-start can take 20s+); (4) `foundry-observability` first-trace probe KQL returns ≥ 1 row.

---

## Install

```bash
# Install the core pipeline skills
gh skill install aiappsgbb/awesome-gbb threadlight-design --scope user
gh skill install aiappsgbb/awesome-gbb threadlight-deploy --scope user
gh skill install aiappsgbb/awesome-gbb threadlight-local-test --scope user
gh skill install aiappsgbb/awesome-gbb threadlight-safe-check --scope user

# Always-on companions
gh skill install aiappsgbb/awesome-gbb foundry-hosted-agents --scope user
gh skill install aiappsgbb/awesome-gbb foundry-mcp-aca --scope user
gh skill install aiappsgbb/awesome-gbb foundry-observability --scope user
gh skill install aiappsgbb/awesome-gbb foundry-evals --scope user

# Helpful when working across tenants
gh skill install aiappsgbb/awesome-gbb azure-tenant-isolation --scope user
```

---

## Quick Start

```
> Design a KYC onboarding process for a bank. Fast PoC mode.

# threadlight-design runs:
# - Loads fsi-kyc-aml.md domain primer
# - Asks 2-3 essential questions
# - Generates specs/ + AGENTS.md + skills + specs/overview.html
# - Proceeds directly to implementation (no checkpoint pause)

> Now deploy it

# threadlight-deploy runs:
# - Reads specs/SPEC.md
# - Generates container.py, Dockerfile, azd project
# - Wires mock MCP for SAP/CRM
# - azd up → hosted agent running

> Score it

# foundry-evals runs:
# - Uses spec § 9 scenarios as test dataset
# - Invokes agent, scores with Foundry evaluators
```

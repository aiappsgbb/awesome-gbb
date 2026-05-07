# Threadlight: Design → Deploy → Demo

Threadlight is a **skill pipeline** for going from a vague customer requirement to a
working Foundry agent demo. It's built for rapid, repeatable PoC delivery by
AI Global Black Belts.

```
Customer brief → threadlight-design → specs + agents + skills + pitch page
                                              ↓
                  foundry-mcp-aca → mock MCP for inaccessible systems
                                              ↓
                    threadlight-deploy → azd up → working demo
                                              ↓
                      foundry-evals → score it    foundry-teams-bot → Teams
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
- **Seller pitch page** — `spec-overview.html`, a self-contained dark-themed HTML page
  showing the process flow, business rules, data models, integration status badges
- **Workshop dashboard** — optional React app (`spec-dashboard/`) for interactive
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

### 3. Deploy It — `threadlight-deploy`

Generate all Foundry deployment artifacts from the spec + agents:

- `container.py` — GHCP SDK runtime by default (CopilotClient + InvocationAgentServerHost);
  falls back to MAF (Agent + FoundryChatClient + ResponsesHostServer) when Toolbox needed
- `Dockerfile` — uv-based, python:3.12-slim
- `pyproject.toml` — with prerelease handling for hosting packages
- `agent.yaml` + `azure.yaml` — azd ai agent extension scaffold
- `infra/` — vendored Bicep (Foundry project, ACR, monitoring)
- `mcp-config.json` — wired to mock MCP endpoints (or real ones)
- `copilot-instructions.md` — system prompt derived from AGENTS.md
- `deploy-notes.md` — full deployment guide with mock system warnings

**One command**: `azd up` provisions, builds, deploys, creates the agent.

The skill reads `specs/SPEC.md` for compliance constraints, model selection, trigger
patterns, and mock system handling. It cross-references `foundry-hosted-agents` for
RBAC and `foundry-mcp-aca` for MCP deployment details.

### 4. Expose It — `foundry-teams-bot` (optional)

Add a Teams bot frontend so the customer can chat with the agent in Teams:

- Bot code (`copilot/bot.py`) with streaming, `!reset`, error handling
- Bicep (UAMI, Bot Service + MsTeamsChannel, ACA)
- Teams manifest with sideloading support
- Only included when the spec calls for Teams or the user asks

### 5. Eval It — `foundry-evals`

Score the demo using Foundry's built-in evaluators:

- Two-phase invoke+score pattern (workaround for SDK routing bug)
- 6 evaluators: task adherence, completion, intent resolution, coherence,
  tool selection, tool output utilization
- Test dataset auto-generated from spec § 9 eval scenarios (S-XXX ← BR-XXX)
- Tool-use discipline guidance to avoid over-calling tools (kills eval scores)

### 6. Land It — `citadel-spoke-onboarding` (when customer is ready)

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
| **Pitch-ready** | `spec-overview.html` — open in browser, show the customer |
| **Assumptions documented** | Spec § 12 flags everything assumed (stateless, read-only, etc.) |

---

## What Gets Generated

```
project/
├── specs/
│   ├── SPEC.md                    # SpecKit specification (the durable source of truth)
│   ├── manifest.json              # Checkpoint metadata
│   └── sample-data/               # Mock data for inaccessible systems
│       ├── {entity}.json
│       └── README.md              # Migration guide (mock → real)
│
├── .github/skills/                # Agent skills (derived from spec)
│   └── {skill-name}/SKILL.md
├── AGENTS.md                      # Agent identity, tools, guidelines
├── skill-manifest.json            # Machine-readable deployment contract
├── config/{name}.json             # Process configuration
│
├── spec-overview.html             # Seller pitch page (self-contained)
├── spec-dashboard/                # Interactive workshop app (optional, React)
│
├── src/
│   ├── agent/                     # Hosted agent container (from threadlight-deploy)
│   │   ├── container.py           # GHCP SDK runtime (default) or MAF
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── copilot-instructions.md
│   │   ├── skills/                # Skills copied for container
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
│       └── teams_package/
│
├── agent.yaml                     # ContainerAgent definition
├── azure.yaml                     # azd extension config
├── infra/                         # Bicep scaffold
├── scripts/                       # Hooks
├── deploy-notes.md                # Deployment guide
│
└── .copilot/mcp-config.json       # Dev-time MCP config
```

---

## Companion Skills

| Skill | Role | Required? |
|-------|------|-----------|
| `foundry-hosted-agents` | RBAC, identity model, agent.yaml schema, deps, troubleshooting | **Always** |
| `foundry-mcp-aca` | MCP server deployment — including mock MCP for demos | When mocking systems |
| `foundry-evals` | Post-deployment evaluation patterns | For scoring demos |
| `foundry-teams-bot` | Teams bot integration | When Teams needed |
| `foundry-iq` | Enterprise RAG with agentic retrieval | When knowledge grounding needed |
| `ghcp-hosted-agents` | GHCP SDK runtime (Invocations protocol, SSE) | For long-running agents (>120s) |
| `azd-patterns` | azd hooks, ACA job deployment, infra scripting | For advanced azd workflows |

---

## Install

```bash
# Install the core pipeline skills
gh skill install aiappsgbb/awesome-gbb threadlight-design --scope user
gh skill install aiappsgbb/awesome-gbb threadlight-deploy --scope user

# Install companion skills as needed
gh skill install aiappsgbb/awesome-gbb foundry-hosted-agents --scope user
gh skill install aiappsgbb/awesome-gbb foundry-mcp-aca --scope user
gh skill install aiappsgbb/awesome-gbb foundry-evals --scope user
```

---

## Quick Start

```
> Design a KYC onboarding process for a bank. Fast PoC mode.

# threadlight-design runs:
# - Loads fsi-kyc-aml.md domain primer
# - Asks 2-3 essential questions
# - Generates specs/ + AGENTS.md + skills + spec-overview.html
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

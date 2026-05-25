# Demo Guide — awesome-gbb

Single reference guide for demoing the **awesome-gbb** skill catalog.

## Quick start

**Default demo install:** use the Threadlight plugin. It gives you the best single bundle for live demos because it brings the main pipeline plus the supporting Azure / Foundry skills most meetings need.

```bash
copilot plugin marketplace add aiappsgbb/awesome-gbb
copilot plugin install awesome-gbb-threadlight@awesome-gbb
copilot plugin list
```

| Verify | What to look for |
|---|---|
| `copilot plugin list` | `awesome-gbb-threadlight@awesome-gbb` appears in the installed plugin list |
| Skill availability | The agent can activate [threadlight-design](skills/threadlight-design/), [threadlight-deploy](skills/threadlight-deploy/), [zava-workspace-deploy](skills/zava-workspace-deploy/), and the supporting Foundry skills |

## Demo menu

| Demo | Best for | Core story | Primary skills |
|---|---|---|---|
| **Threadlight** | Technical leads, developers, solution sellers | One business process from SPEC to live Azure workflow | [threadlight-design](skills/threadlight-design/), [threadlight-demo-data-factory](skills/threadlight-demo-data-factory/), [threadlight-local-test](skills/threadlight-local-test/), [threadlight-deploy](skills/threadlight-deploy/) |
| **Zava** | C-suite, transformation leaders, enterprise architects | Full agentic operating model across an enterprise control plane | [zava-workspace-deploy](skills/zava-workspace-deploy/) |
| **Foundry stack** | Architects, platform owners, developers | Hosted agents with tools, governance, and full traceability | [foundry-hosted-agents](skills/foundry-hosted-agents/), [foundry-mcp-aca](skills/foundry-mcp-aca/), [foundry-agt](skills/foundry-agt/), [foundry-observability](skills/foundry-observability/) |

## Threadlight Demo

### What it shows

| Stage | Skill | What to show |
|---|---|---|
| 1 | [threadlight-design](skills/threadlight-design/) | Turn a vague process brief into `specs/SPEC.md` |
| 2 | [threadlight-demo-data-factory](skills/threadlight-demo-data-factory/) | Generate realistic demo data and seed/reset assets |
| 3 | [threadlight-local-test](skills/threadlight-local-test/) | Run the workflow locally before cloud deployment |
| 4 | [threadlight-deploy](skills/threadlight-deploy/) | Ship the process to Azure Container Apps |
| 5 | [threadlight-safe-check](skills/threadlight-safe-check/) | Prove the deployed system is safe, wired, and policy-aligned |
| 6 | [foundry-evals](skills/foundry-evals/) + [foundry-observability](skills/foundry-observability/) | Show eval results, traces, and telemetry in App Insights |

### 5-minute exec pitch

**Talk track:** **“Here’s what AI agents look like when they run a real business process.”**

1. Open [threadlight-design](skills/threadlight-design/) output and show the generated SPEC.
2. Point out that the process is explicit: steps, tools, business rules, HITL gates, and eval scenarios.
3. Show the deployed workflow running in Azure, not just a mock slide.
4. Land on the business value: repeatable process design, observable execution, and governed deployment.

### 15-minute technical walkthrough

| Time | Move | Point |
|---|---|---|
| 0–3 min | Generate or open a SPEC from [threadlight-design](skills/threadlight-design/) | Design is codified as a reusable process contract |
| 3–5 min | Show seeded records from [threadlight-demo-data-factory](skills/threadlight-demo-data-factory/) | Demo data, reset scripts, and realism are first-class |
| 5–7 min | Run the flow locally with [threadlight-local-test](skills/threadlight-local-test/) | Inner-loop iteration happens before Azure spend |
| 7–10 min | Deploy with [threadlight-deploy](skills/threadlight-deploy/) | Same process moves cleanly into ACA |
| 10–12 min | Show HITL gates and validation from [threadlight-safe-check](skills/threadlight-safe-check/) | Human approval points are part of the design, not bolted on |
| 12–15 min | Open App Insights / trace view via [foundry-observability](skills/foundry-observability/) and review [foundry-evals](skills/foundry-evals/) | You get observability and quality scoring, not a black box |

### Key skills involved

- [threadlight-design](skills/threadlight-design/)
- [threadlight-local-test](skills/threadlight-local-test/)
- [threadlight-deploy](skills/threadlight-deploy/)
- [foundry-observability](skills/foundry-observability/)
- Supporting: [threadlight-demo-data-factory](skills/threadlight-demo-data-factory/), [threadlight-safe-check](skills/threadlight-safe-check/), [foundry-evals](skills/foundry-evals/)

## Zava Demo

### What it shows

- **38 concurrent workflow domains**
- **79 persona roles**
- Entity graph and fleet manager
- Real-time SSE activity feed
- Operator UI, candidate portal, and blueprint/constellation views

### Live URL pattern

| Surface | URL pattern | Use |
|---|---|---|
| Operator UI | `https://<FQDN>/` | Main control plane and simulator |
| Candidate Portal | `https://<FQDN>/portal/` | External candidate journey |
| Constellation / Blueprint | `https://<FQDN>/blueprint/` | Enterprise-wide composition view |

### 5-minute exec pitch

1. Open the Operator UI at `https://<FQDN>/`.
2. Trigger **constellation** and let all domains start processing in real time.
3. Watch the SSE feed update live.
4. Open the entity graph / blueprint view.
5. Land the message: **“This is what enterprise-scale AI orchestration looks like when many business domains run together.”**

### 15-minute technical walkthrough

| Time | Move | Point |
|---|---|---|
| 0–2 min | Open Operator UI and pick a role | One control plane, many personas |
| 2–4 min | Trigger constellation | 38 domains can execute concurrently |
| 4–7 min | Inspect `expense-claim` | 4-phase workflow with policy and approval logic |
| 7–9 min | Show a HITL gate | Senior decisions remain explicitly human-controlled |
| 9–11 min | Open `https://<FQDN>/portal/` | Same platform, different persona surface |
| 11–13 min | Show entity graph / relationships | The org runs on shared entities, not isolated demos |
| 13–15 min | Open `https://<FQDN>/blueprint/` | Constellation view makes orchestration visible |

### Domain talking points

| Domain | What to say |
|---|---|
| `expense-claim` | Policy enforcement: threshold checks, approvals, and payment sequencing |
| `hiring` | 10-phase pipeline: long-running orchestration across candidate lifecycle |
| `vendor-kyc` | Compliance as code: verification and governance embedded into the workflow |
| `creative-campaign` | Multi-modal agents: content generation and visual steps in one process |

### Known limitations

- **HITL auto-resolve in fake mode:** gates clear automatically for fast demos.
- **No real LLM calls with `LLM_RUNTIME=fake`:** responses are template-driven.
- **Mem0 disabled:** memory falls back to the non-Mem0 demo path.

### Key skill

- Primary: [zava-workspace-deploy](skills/zava-workspace-deploy/)
- Optional pre-demo setup: [research-company](skills/research-company/), [compose-org](skills/compose-org/)

## Foundry Stack Demo

### What it shows

- A hosted agent deployed with [foundry-hosted-agents](skills/foundry-hosted-agents/)
- MCP tools exposed from ACA with [foundry-mcp-aca](skills/foundry-mcp-aca/)
- Deterministic governance and audit with [foundry-agt](skills/foundry-agt/)
- Traces and telemetry landing in App Insights through [foundry-observability](skills/foundry-observability/)

### 5-minute exec pitch

**Talk track:** **“Here’s an AI agent running in Azure with full audit trail and governance.”**

1. Open the hosted agent and invoke a tool-backed task.
2. Show the MCP tool path and explain that tools are remotely governed infrastructure, not local hacks.
3. Show AGT policy enforcement or audit artifacts.
4. Open App Insights and show traces for the same run.

### Suggested demo flow

| Step | Skill | Show |
|---|---|---|
| 1 | [foundry-hosted-agents](skills/foundry-hosted-agents/) | Agent deployment, identity, and runtime |
| 2 | [foundry-mcp-aca](skills/foundry-mcp-aca/) | Tool endpoint hosted on ACA |
| 3 | [foundry-agt](skills/foundry-agt/) | Governance policy, allow/deny, audit trail |
| 4 | [foundry-observability](skills/foundry-observability/) | Telemetry, traces, and operational evidence |

### Key skills

- [foundry-hosted-agents](skills/foundry-hosted-agents/)
- [foundry-mcp-aca](skills/foundry-mcp-aca/)
- [foundry-agt](skills/foundry-agt/)
- [foundry-observability](skills/foundry-observability/)

## Prep Checklist

| Check | Status before demo | Notes |
|---|---|---|
| Azure subscription tagged for the engagement | Required | [azd-patterns](skills/azd-patterns/) covers tagging discipline, including MCAP tagging |
| Tenant isolation configured | **MANDATORY** | Use [azure-tenant-isolation](skills/azure-tenant-isolation/) before any Azure action |
| Shared ACR + App Insights ready | Required | Reuse shared infra for faster demo setup |
| Foundry AI Services account ready | Required | Pre-provision model access and RBAC |
| `gpt-4.1` deployment available | Required | Baseline model for hosted-agent demos |
| `text-embedding-3-large` deployment available | Required | Needed for retrieval / memory / embedding flows |
| Citadel APIM gateway available | Optional, recommended | Best enterprise story for gateway governance and shared model access |
| `azd` installed | Required | Default deployment path in this catalog |
| Docker installed | Required | Needed for ACA image build/push flows |
| Node.js installed | Required | Needed for SPA / portal / tooling flows |
| Python 3.11+ installed | Required | Baseline for most agent and infra scripts |
| `uv` installed | Recommended | Fast Python env/bootstrap workflow |

## Per-audience scripts

| Audience | Duration | Show | Core message | Skills |
|---|---|---|---|---|
| **C-suite** | 5 min | Zava constellation → live feed → entity graph | **“This is what AI orchestration looks like at enterprise scale.”** | [zava-workspace-deploy](skills/zava-workspace-deploy/) |
| **Technical leads** | 15 min | Threadlight end-to-end: design → data → local test → deploy → telemetry | **“The process is designed, testable, deployable, and observable.”** | [threadlight-design](skills/threadlight-design/), [threadlight-local-test](skills/threadlight-local-test/), [threadlight-deploy](skills/threadlight-deploy/), [foundry-observability](skills/foundry-observability/) |
| **Architects** | 30 min | Citadel hub + spoke governance, VNet isolation, RBAC model | **“This platform is governable, segmentable, and enterprise-ready by design.”** | [citadel-hub-deploy](skills/citadel-hub-deploy/), [citadel-spoke-onboarding](skills/citadel-spoke-onboarding/), [foundry-vnet-deploy](skills/foundry-vnet-deploy/), [azure-tenant-isolation](skills/azure-tenant-isolation/), [foundry-agt](skills/foundry-agt/) |
| **Developers** | 30 min | Live build: design a new process, run it locally, then deploy it | **“You can go from idea to runnable agent workflow in one working session.”** | [threadlight-design](skills/threadlight-design/), [threadlight-local-test](skills/threadlight-local-test/), [threadlight-deploy](skills/threadlight-deploy/) |

## See also

- [README.md](README.md)
- [THREADLIGHT.md](THREADLIGHT.md)
- [AGENTS.md](AGENTS.md)

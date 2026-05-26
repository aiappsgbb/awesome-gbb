# Demo Guide — awesome-gbb

Single reference guide for demoing the **awesome-gbb** skill catalog.

## Quick start

**Default demo install:** use the awesome-gbb plugin plus [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills) for the full pipeline.

```bash
copilot plugin marketplace add aiappsgbb/awesome-gbb
copilot plugin install awesome-gbb@awesome-gbb

copilot plugin marketplace add aiappsgbb/threadlight-skills
copilot plugin install threadlight-skills@threadlight-skills
copilot plugin list
```

| Verify | What to look for |
|---|---|
| `copilot plugin list` | `awesome-gbb@awesome-gbb` and `threadlight-skills@threadlight-skills` appear |
| Skill availability | The agent can activate `threadlight-design`, `threadlight-deploy`, and the supporting Foundry skills. For Zava skills, install [zava-constellation](https://github.com/aiappsgbb/zava-constellation). |

## Demo menu

| Demo | Best for | Core story | Primary skills |
|---|---|---|---|
| **Threadlight** | Technical leads, developers, solution sellers | One business process from SPEC to live Azure workflow | See [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills) |
| **Zava** | C-suite, transformation leaders, enterprise architects | Full agentic operating model across an enterprise control plane | [zava-constellation](https://github.com/aiappsgbb/zava-constellation) |
| **Foundry stack** | Architects, platform owners, developers | Hosted agents with tools, governance, and full traceability | [foundry-hosted-agents](skills/foundry-hosted-agents/), [foundry-mcp-aca](skills/foundry-mcp-aca/), [foundry-agt](skills/foundry-agt/), [foundry-observability](skills/foundry-observability/) |

## Threadlight Demo

> **Threadlight skills have moved to
> [aiappsgbb/threadlight-skills](https://github.com/aiappsgbb/threadlight-skills).**
> See that repo for the full demo guide, pipeline walkthrough, and experience page.

## Zava Demo

> **Zava demo content has moved to
> [aiappsgbb/zava-constellation](https://github.com/aiappsgbb/zava-constellation).**

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
| **C-suite** | 5 min | Zava constellation → live feed → entity graph | **"This is what AI orchestration looks like at enterprise scale."** | [zava-constellation](https://github.com/aiappsgbb/zava-constellation) |
| **Technical leads** | 15 min | Threadlight end-to-end: design → data → local test → deploy → telemetry | **"The process is designed, testable, deployable, and observable."** | [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills), [foundry-observability](skills/foundry-observability/) |
| **Architects** | 30 min | Citadel hub + spoke governance, VNet isolation, RBAC model | **“This platform is governable, segmentable, and enterprise-ready by design.”** | [citadel-hub-deploy](skills/citadel-hub-deploy/), [citadel-spoke-onboarding](skills/citadel-spoke-onboarding/), [foundry-vnet-deploy](skills/foundry-vnet-deploy/), [azure-tenant-isolation](skills/azure-tenant-isolation/), [foundry-agt](skills/foundry-agt/) |
| **Developers** | 30 min | Live build: design a new process, run it locally, then deploy it | **"You can go from idea to runnable agent workflow in one working session."** | [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills) |

## See also

- [README.md](README.md)
- [Threadlight skills](https://github.com/aiappsgbb/threadlight-skills)
- [AGENTS.md](AGENTS.md)

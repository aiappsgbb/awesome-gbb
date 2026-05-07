# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-12-blue)](#skills-catalog)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Contents

- [What Are Skills?](#what-are-skills)
- [Skills Catalog](#skills-catalog)
  - [🏗️ Agent Design & Deployment](#️-agent-design--deployment)
  - [📊 Content Generation](#-content-generation)
  - [🔍 Discovery](#-discovery)
- [How to Use](#how-to-use)
- [Repository Structure](#repository-structure)
- [Threadlight: Design → Deploy → Demo](#threadlight-design--deploy--demo)
- [Contributing](#contributing)

---

## What Are Skills?

Skills are reusable, composable building blocks for AI agents. Each Skill encodes domain expertise as a structured markdown file (`SKILL.md`) that **GitHub Copilot CLI** (or any compatible agentic runtime) can load and execute.

These are **developer-oriented skills** — they help you build, deploy, and ship faster. A skill tells the agent **what to do**, **when to activate**, and **how to do it** — step by step.

---

## Skills Catalog

### 🏗️ Agent Design & Deployment

| Skill | Description |
|-------|-------------|
| [**threadlight-design**](skills/threadlight-design/) | Spec out any business process — produces a durable SpecKit specification (business rules, data models, tool contracts, mock data) then derives AGENTS.md + Skills from it |
| [**threadlight-deploy**](skills/threadlight-deploy/) | Generate all deployment artifacts for Microsoft Foundry Hosted Agents — container.py, Dockerfile, azd project, Teams bot. One-command deploy via `azd up` |
| [**foundry-hosted-agents**](skills/foundry-hosted-agents/) | Reference guide for the refreshed Foundry hosted agents preview (April 2026) — `Agent` + `FoundryChatClient` + `ResponsesHostServer`, identity model, RBAC, troubleshooting |
| [**foundry-teams-bot**](skills/foundry-teams-bot/) | Connect a Foundry Hosted Agent to Microsoft Teams — bot code, Bicep infrastructure, Teams manifest, UAMI auth, and ACA deployment |
| [**ghcp-hosted-agents**](skills/ghcp-hosted-agents/) | Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) — BYOK auth, Invocations protocol, SSE streaming, for long-running tool loops |
| [**foundry-mcp-aca**](skills/foundry-mcp-aca/) | Deploy custom MCP servers as Azure Container Apps or Azure Functions — Cosmos DB MCPToolKit, Playwright MCP, protocol requirements, auth patterns |
| [**foundry-evals**](skills/foundry-evals/) | Evaluate Foundry hosted agents — two-phase invoke+score pattern, 6 built-in evaluators, dataset creation, RBAC, tool-use discipline |
| [**foundry-iq**](skills/foundry-iq/) | Build enterprise RAG with Foundry IQ — Azure AI Search Knowledge Agents, agentic retrieval, multi-hop reasoning, citation-backed responses |

### 📊 Content Generation

| Skill | Description |
|-------|-------------|
| [**pptx**](skills/pptx/) | Generate professional PowerPoint presentations using python-pptx — dark & light themes, card layouts, bullet lists, speaker notes |
| [**auto-demo-producer**](skills/auto-demo-producer/) | Produce narrated video demos of web apps automatically — Playwright browser recording + edge-tts neural narration + ffmpeg assembly into polished MP4 |

### 🔍 Discovery

| Skill | Description |
|-------|-------------|
| [**ip-catalog**](skills/ip-catalog/) | Discover AI Apps GBB IP catalog via MCP — search, list, filter, and inspect intellectual property assets including metadata and READMEs |

---

## How to Use

**Install with `gh` CLI:**

```bash
gh skill install aiappsgbb/awesome-gbb <skill-name> --scope user
```

**Or with `npx skills`:**

```bash
npx skills add aiappsgbb/awesome-gbb --skill <skill-name> -g
```

**As a project-level skill (scoped to a repo):**

```bash
gh skill install aiappsgbb/awesome-gbb <skill-name>
```

> [!TIP]
> Skills like **pptx**, **auto-demo-producer**, and **foundry-hosted-agents** are great candidates for global install (`--scope user` / `-g`) — they're useful across all your projects. Design and deployment skills like **threadlight-design** and **threadlight-deploy** work well at project scope.

---

## Repository Structure

```
skills/
  <skill-name>/
    SKILL.md          # Skill definition (frontmatter + instructions)
    README.md         # Optional: extended docs, examples, changelog
```

---

## Threadlight: Design → Deploy → Demo

Threadlight is a **skill pipeline** for going from a vague customer requirement to a
working Foundry agent demo. It's built for rapid, repeatable PoC delivery.

```
Customer brief → threadlight-design → specs + agents + skills
                                              ↓
                    threadlight-deploy → azd up → working demo
                                              ↓
                      foundry-evals → score it    foundry-teams-bot → Teams exposure
```

### The Flow

| Step | Skill | What happens |
|------|-------|-------------|
| **1. Spec it** | `threadlight-design` | Discovery interview → SpecKit specification (business rules, data models, tool contracts, mock data) → AGENTS.md + Skills |
| **2. Mock it** | `foundry-mcp-aca` | Generate FastMCP mock server for inaccessible backend systems — customer sees real MCP tool calls with sample data |
| **3. Deploy it** | `threadlight-deploy` | Generate container.py, Dockerfile, azd project, wire mock MCP → `azd up` → hosted agent running |
| **4. Expose it** | `foundry-teams-bot` | Optional: add Teams bot frontend so customer can chat with the agent in Teams |
| **5. Eval it** | `foundry-evals` | Score the demo with Foundry evaluators using scenarios from the spec |
| **6. Land it** | `citadel-spoke-onboarding` | When the customer wants production: onboard onto Citadel landing zone with APIM gateway + governance |

### Fast-PoC Mode

For rapid demos, `threadlight-design` has a **fast-PoC mode** — minimal questions,
sensible defaults (keyless auth, mock MCP, stateless assumed), everything generated
in one pass. Every PoC ships with:

- ✅ Keyless auth (`DefaultAzureCredential`)
- ✅ Mock MCP server for inaccessible systems (customer swaps URL when onboarding)
- ✅ Eval dataset from spec scenarios
- ✅ Deployable scaffold (`azd up` ready)

### Companion Skills

The Threadlight pipeline leans on these companion skills for specialized tasks:

| Skill | Role in pipeline |
|-------|-----------------|
| `foundry-hosted-agents` | RBAC, identity model, agent.yaml schema, troubleshooting reference |
| `foundry-mcp-aca` | MCP server deployment — including mock MCP for demos |
| `foundry-evals` | Post-deployment evaluation patterns |
| `foundry-teams-bot` | Teams bot integration (optional) |
| `ghcp-hosted-agents` | Alternative runtime for long-running agents (>120s tool loops) |
| `foundry-iq` | Enterprise RAG with agentic retrieval (knowledge grounding) |

---

## Contributing

1. **Fork & branch** — create a feature branch from `main`.
2. **Add your Skill** — place it under `skills/<your-skill-name>/SKILL.md`.
3. **Open a PR** — describe the scenario, target audience, and any dependencies.
4. **Peer review** — at least one GBB team member must approve before merge.

### Skill Quality Checklist

- [ ] Clear, concise `description` in frontmatter
- [ ] Well-defined trigger phrases (when should the skill activate?)
- [ ] Actionable instructions (the agent *does* the work, not just advises)
- [ ] No secrets or credentials embedded
- [ ] Tested with at least one agentic runtime

## License

This project is licensed under the [MIT License](LICENSE).

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

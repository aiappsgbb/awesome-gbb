# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-14-blue)](#skills-catalog)
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
| [**foundry-hosted-agents**](skills/foundry-hosted-agents/) | Reference guide for the refreshed Foundry hosted agents preview (April 2026) — `Agent` + `FoundryChatClient` + `ResponsesHostServer`, identity model, RBAC, troubleshooting |
| [**foundry-teams-bot**](skills/foundry-teams-bot/) | Connect a Foundry Hosted Agent to Microsoft Teams — bot code, Bicep infrastructure, Teams manifest, UAMI auth, and ACA deployment |
| [**ghcp-hosted-agents**](skills/ghcp-hosted-agents/) | Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) — BYOK auth, Invocations protocol, SSE streaming, for long-running tool loops |
| [**foundry-mcp-aca**](skills/foundry-mcp-aca/) | Deploy custom MCP servers as Azure Container Apps or Azure Functions — Cosmos DB MCPToolKit, Playwright MCP, mock MCP for demos, protocol requirements |
| [**foundry-evals**](skills/foundry-evals/) | Evaluate Foundry hosted agents — two-phase invoke+score pattern, 6 built-in evaluators, dataset creation, RBAC, tool-use discipline |
| [**foundry-iq**](skills/foundry-iq/) | Build enterprise RAG with Foundry IQ — Azure AI Search Knowledge Agents, agentic retrieval, multi-hop reasoning, citation-backed responses |
| [**azd-patterns**](skills/azd-patterns/) | Tips and patterns for Azure Developer CLI (azd) — hooks, postdeploy/postprovision, ACA job deployment, infrastructure scripting conventions |
| [**foundry-cross-resource**](skills/foundry-cross-resource/) | Cross-resource model invocation via AI Gateway (APIM) — use models from another Foundry resource or shared pool |

> [!NOTE]
> **Threadlight** (`threadlight-design` + `threadlight-deploy`) is our skill pipeline for rapid PoC delivery: customer brief → spec → mock → deploy → demo. See [THREADLIGHT.md](THREADLIGHT.md) for the full flow and companion skills.

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

# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-7-blue)](#skills-catalog)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Contents

- [What Are Skills?](#what-are-skills)
- [Skills Catalog](#skills-catalog)
  - [🏗️ Agent Design & Deployment](#️-agent-design--deployment)
  - [📊 Content Generation](#-content-generation)
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
| [**threadlight-design**](skills/threadlight-design/) | Design agentic workflows — turn any business process into a structured folder of Skills + AGENTS.md, ready for Foundry deployment |
| [**threadlight-deploy**](skills/threadlight-deploy/) | Generate all deployment artifacts for Microsoft Foundry Hosted Agents — container.py, Dockerfile, azd project, Teams bot. One-command deploy via `azd up` |
| [**foundry-hosted-agents**](skills/foundry-hosted-agents/) | Reference guide for the refreshed Foundry hosted agents preview (April 2026) — `Agent` + `FoundryChatClient` + `ResponsesHostServer`, identity model, RBAC, troubleshooting |
| [**foundry-teams-bot**](skills/foundry-teams-bot/) | Connect a Foundry Hosted Agent to Microsoft Teams — bot code, Bicep infrastructure, Teams manifest, UAMI auth, and ACA deployment |
| [**ghcp-hosted-agents**](skills/ghcp-hosted-agents/) | Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) — BYOK auth, Invocations protocol, SSE streaming, for long-running tool loops |

### 📊 Content Generation

| Skill | Description |
|-------|-------------|
| [**pptx**](skills/pptx/) | Generate professional PowerPoint presentations using python-pptx — dark & light themes, card layouts, bullet lists, speaker notes |
| [**auto-demo-producer**](skills/auto-demo-producer/) | Produce narrated video demos of web apps automatically — Playwright browser recording + edge-tts neural narration + ffmpeg assembly into polished MP4 |

---

## How to Use

**Install a skill from GitHub:**

```bash
gh skill install aiappsgbb/awesome-gbb/skills/<skill-name>
```

**Or with npx:**

```bash
npx @anthropic/copilot-cli skill install aiappsgbb/awesome-gbb/skills/<skill-name>
```

**As a project-level skill (scoped to a repo):**

```bash
cp -r skills/<skill-name> .github/skills/<skill-name>
```

> [!NOTE]
> **Looking to deploy skill-based agents to Microsoft Foundry?** See [threadlight-design](skills/threadlight-design/) to design your agent workflow, [threadlight-deploy](skills/threadlight-deploy/) to generate deployment artifacts, [foundry-hosted-agents](skills/foundry-hosted-agents/) for the refreshed preview reference, and [ghcp-hosted-agents](skills/ghcp-hosted-agents/) for the GitHub Copilot SDK variant.

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

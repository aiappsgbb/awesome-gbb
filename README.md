# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-28-blue)](#skills-catalog)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Contents

- [What Are Skills?](#what-are-skills)
- [Featured Pipeline: Threadlight](#-featured-pipeline-threadlight)
- [Supported Coding Runtimes](#supported-coding-runtimes)
- [Skills Catalog](#skills-catalog)
  - [🏗️ Foundry Building Blocks](#️-foundry-building-blocks)
  - [🛠️ Cross-Cutting Helpers](#️-cross-cutting-helpers)
  - [📊 Content Generation](#-content-generation)
  - [🔍 Discovery](#-discovery)
- [How to Use](#how-to-use)
- [Repository Structure](#repository-structure)
- [Contributing](#contributing)

---

## What Are Skills?

Skills are reusable, composable building blocks for AI agents. Each Skill encodes domain expertise as a structured markdown file (`SKILL.md`) that any compatible agentic coding runtime can load and execute.

These are **developer-oriented skills** — they help you build, deploy, and ship faster. A skill tells the agent **what to do**, **when to activate**, and **how to do it** — step by step.

---

## 🧵 Featured Pipeline: Threadlight

**Threadlight** is the flagship end-to-end pipeline in this catalog: a chain
of eight `threadlight-*` skills that take a customer from a one-paragraph
brief through spec → local test → deploy → safe-check gate → demo. It's
opinionated about the order skills run in, the cross-skill contracts they
share (SPEC.md sections, kebab-case selectors, the three-lifecycle gate),
and the persona split — `threadlight-design` is the seller / Cowork entry
point; the rest run in a real shell (Copilot CLI, Coding Agent, Cursor, …)
during workshops.

> 📖 **The full pipeline narrative, per-skill summary, selector vocabulary
> and customer-workshop runbook live in [THREADLIGHT.md](THREADLIGHT.md).**
> The individual skills are also listed under `skills/threadlight-*/` and
> install the same way as everything else in this repo.

---

## Supported Coding Runtimes

Skills are agnostic Markdown contracts — they load in any runtime that understands the `SKILL.md` shape. The catalog is verified against the runtimes below.

| Runtime | Shell + package installs | Long-running processes | Best for |
|---|---|---|---|
| **GitHub Copilot CLI** (`gh copilot`) | ✅ Full | ✅ | **Primary target**. Every skill works end-to-end. |
| **GitHub Copilot Coding Agent** (cloud) | ✅ Full | ✅ | All skills, hands-off cloud runs. |
| **Cursor** | ✅ Full | ✅ | All skills (load via project `.cursorrules` shim). |
| **VS Code GitHub Copilot Chat** | ✅ Full | ✅ | All skills (terminal-attached). |
| **Claude Code** (`clawpilot`) | ✅ Full | ✅ | All skills. |
| **Microsoft Copilot Cowork** | ❌ Restricted | ❌ | Spec / pitch / config-gen skills only — see callout below. |

> [!IMPORTANT]
> **Microsoft Copilot Cowork compatibility caveat.** Cowork is the recommended
> seller surface for `threadlight-design` (it shines at structured-document
> generation), but its sandbox **does not allow `pip`/`npm`/`uv` installs,
> cannot shell out to `azd`/`az`/`docker`/`gh`, and cannot run long-lived
> processes**. As a rule of thumb, only a handful of skills are Cowork-friendly:
>
> - **`threadlight-design`** — the seller pitch + spec generator (its primary home).
> - **`ip-catalog`** — read-only MCP discovery of the GBB IP catalog.
> - **`gbb-pptx`** — pitch-deck generator (works as long as `python-pptx` is
>   available in the Cowork Python sandbox).
> - **`gbb-humanizer`** — pure prose-polish pass over `overview.html`,
>   prep-guide, demo script, or speaker notes (text-only, no shell needed).
>
> Everything else in this catalog assumes a real shell. Skills that deploy,
> build containers, run evals against a live model, render videos, or run a
> local FastMCP **will not work in Cowork** — use Copilot CLI, Coding Agent,
> Cursor, VS Code Copilot Chat, or Claude Code instead. They may still
> **author** their artifacts in Cowork (markdown / Bicep / Dockerfile is text),
> but the `azd up` / build / eval step needs a real shell. Plan workshops
> accordingly.

---

## Skills Catalog

### 🏗️ Foundry Building Blocks

Reference patterns for Microsoft Foundry hosted agents, MCP servers, evals, RAG, vision/speech, and observability.

| Skill | Description |
|-------|-------------|
| [**foundry-hosted-agents**](skills/foundry-hosted-agents/) | Refreshed hosted-agents preview — `Agent` + `FoundryChatClient` + `ResponsesHostServer`, identity model, RBAC, MCP wiring, **`SkillsProvider` progressive skill loading** vs. legacy concat, troubleshooting |
| [**foundry-teams-bot**](skills/foundry-teams-bot/) | Connect a hosted agent to Microsoft Teams + M365 Copilot (CEA manifest 1.21) — bot code, Bicep, Teams manifest, UAMI auth, ACA deployment |
| [**ghcp-hosted-agents**](skills/ghcp-hosted-agents/) | Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) — BYOK auth, Invocations protocol, SSE streaming, long-running tool loops |
| [**foundry-mcp-aca**](skills/foundry-mcp-aca/) | Deploy custom MCP servers as ACA / Azure Functions — Cosmos MCPToolKit, Playwright MCP, mock MCP, **validate-or-reject** evidence enforcement |
| [**foundry-evals**](skills/foundry-evals/) | Evaluate hosted agents — two-phase invoke+score, 6 built-in evaluators, enriched-dataset shape (`tool_calls` + `tool_outputs`), continuous loop |
| [**foundry-iq**](skills/foundry-iq/) | Enterprise RAG with Foundry IQ — Azure AI Search Knowledge Bases, agentic retrieval, multi-hop reasoning, citation-backed responses, **hosted-agent runtime identity callout** + **7-item bootstrap hardening checklist** (no-`az rest`-uploads, fail-fast, key sanitization, 32k-byte chunking, RBAC propagation wait, post-upload count verify, idempotent recovery) |
| [**foundry-doc-vision-speech**](skills/foundry-doc-vision-speech/) | Wire vision (gpt-5.4 family), Document Intelligence v4, and Azure Speech (STT/TTS) into a hosted agent — MCP and native Toolbox patterns + RBAC matrix |
| [**foundry-observability**](skills/foundry-observability/) | End-to-end App Insights + Log Analytics + OpenTelemetry across hosted agents, MCP servers, ACA jobs, bot, workspace — **closes the silent-telemetry gap** where `azd up` returns 0 but AppIn stays empty |
| [**foundry-cross-resource**](skills/foundry-cross-resource/) | Cross-resource model invocation via AI Gateway (APIM) — use models from another Foundry resource or a shared pool |
| [**foundry-vnet-deploy**](skills/foundry-vnet-deploy/) | Deploy Foundry with **Agent Setup inside a private VNet** — guided interview generates `.bicepparam`, runs `az deployment group create` with fixed-timestamp anti-duplication retry, supports new/existing VNet + reused CosmosDB / Storage / AI Search / private DNS zones, **optional spoke→hub peering + APIM private DNS link modules for Citadel-spoke combinations** |
| [**foundry-toolbox**](skills/foundry-toolbox/) | Wire the Foundry Toolbox into hosted agents — managed multi-tool MCP endpoint with all 7 tool types (`mcp` / `web_search` / `azure_ai_search` / `code_interpreter` / `file_search` / `openapi` / `a2a_preview`), the mandatory `Foundry-Features: Toolboxes=V1Preview` header, **the four silent traps** (`ping` / `prompts/list` / non-streaming `tools/call` / reserved `FOUNDRY_*` env vars), the `azure_ai_search`-is-INDEX-not-KB nuance, version promote/rollback flow, and `azd ai agent init` declarative `kind: toolbox` deployment |
| [**foundry-skill-catalog**](skills/foundry-skill-catalog/) | Foundry Skills REST API (`{project}/skills`) — project-level store for instruction-only `SKILL.md` files. Documents the **JSON-mode-is-WRITE-ONLY trap** (instructions submitted at create are never returned by GET / list / download / `?include=`), the quoted-frontmatter → HTTP 500 trap, the mandatory `Foundry-Features: Skills=V1Preview` header, and ships a verified **`FoundrySkillsSource(SkillsSource)`** adapter so `agent_framework.SkillsProvider` can consume Foundry skills at runtime (not just file-copy at build time) |

### 🛠️ Cross-Cutting Helpers

Multi-skill scaffolding and operational discipline used by the Threadlight pipeline and standalone Foundry deployments.

| Skill | Description |
|-------|-------------|
| [**azd-patterns**](skills/azd-patterns/) | Tips and patterns for Azure Developer CLI (`azd`) — hooks, postdeploy/postprovision, ACA Job deployment, **silent-failure debug playbook** (6-rung diagnostic ladder). |
| [**azure-tenant-isolation**](skills/azure-tenant-isolation/) | Multi-tenant Azure CLI / AZD isolation for concurrent terminal sessions — index-file driven, per-tenant `AZURE_CONFIG_DIR` + `az account show` two-layer guard. |
| [**citadel-spoke-onboarding**](skills/citadel-spoke-onboarding/) | Onboard a GenAI app or Foundry project as a spoke into an AI Citadel Governance Hub — Access Contracts, APIM connections, Key Vault secrets, product policies, JWT auth. **Combines with `foundry-vnet-deploy` for VNet-isolated spokes** (Option B Foundry Connection auth posture mandatory). |
| [**gbb-humanizer**](skills/gbb-humanizer/) | Remove signs of AI-generated writing from prose — 29 patterns from Wikipedia's "Signs of AI writing" (em-dash overuse, rule-of-three, AI vocabulary, copula avoidance, sycophantic openers, signposting), two-pass rewrite + AI-tell audit. **Ships pre-canned GBB voice samples** (seller pitch + technical blog), **section-aware mode** (skip code/tables/SME quotes), **density-preserving guardrail** so domain rule-of-three lists survive. Adapted from [blader/humanizer](https://github.com/blader/humanizer) v2.5.1 (MIT). |
| [**ghcp-cli-config**](skills/ghcp-cli-config/) | Bootstrap GitHub Copilot CLI for GBB workflows — 6 recommended MCP servers (mslearn, Azure, Playwright, context7, tavily, mem0), `settings.json` baseline (model, `sessionSync`, `allowedUrls`, `trustedFolders`), work-iq plugin family for Microsoft staff, `autoApprove` safe-default matrix, and a **fresh-machine bootstrap procedure** the agent can execute step-by-step. Distilled from a live GBB engineer's `~/.copilot/`. |

### 📊 Content Generation

| Skill | Description |
|-------|-------------|
| [**gbb-pptx**](skills/gbb-pptx/) | Generate professional PowerPoint presentations using python-pptx — dark & light themes, card layouts, bullet lists, speaker notes. (Renamed from `pptx` in v2.0.0 to avoid collision with the upstream Anthropic `pptx` skill.) |
| [**auto-demo-producer**](skills/auto-demo-producer/) | Produce narrated video demos of web apps automatically — Playwright browser recording + edge-tts neural narration + ffmpeg assembly into polished MP4 |

### 🔍 Discovery

| Skill | Description |
|-------|-------------|
| [**ip-catalog**](skills/ip-catalog/) | Discover AI Apps GBB IP catalog via MCP — search, list, filter, and inspect intellectual property assets including metadata and READMEs |

---

## How to Use

**Install with `gh` CLI:**

> [!TIP]
> **First time on Copilot CLI?** Install [**ghcp-cli-config**](skills/ghcp-cli-config/) first — it bootstraps `~/.copilot/` with the 6 recommended MCP servers (`mslearn`, `Azure`, `Playwright`, `context7`, `tavily`, `mem0`), a sensible `settings.json` baseline, and the work-iq plugin family for Microsoft staff. The agent can run the bootstrap end-to-end on a fresh machine.

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
> **Recommended global install for sellers + SEs:** `threadlight-design`, `threadlight-deploy`, `threadlight-local-test`, `threadlight-safe-check`, `foundry-hosted-agents`, `foundry-observability`, `azure-tenant-isolation`. Other skills can stay at project scope.

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

> [!IMPORTANT]
> **Read [AGENTS.md](AGENTS.md) first** if you (or a sub-agent acting on your
> behalf) are about to edit any skill. It captures the invariants — agnostic
> wording, reference-data canon, `metadata.version` rules, the mass-edit
> safety rails — that **are not enforced by CI** and have bitten us in
> production.

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

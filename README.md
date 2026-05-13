# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-25-blue)](#skills-catalog)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Contents

- [What Are Skills?](#what-are-skills)
- [Supported Coding Runtimes](#supported-coding-runtimes)
- [Skills Catalog](#skills-catalog)
  - [🏗️ Foundry Building Blocks](#️-foundry-building-blocks)
  - [🧵 Threadlight Pipeline](#-threadlight-pipeline)
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
> processes**. Code-heavy skills that depend on those things — anything that
> deploys, builds containers, runs evals against a live model, generates
> binary artifacts (PPTX/MP4), or runs a local FastMCP — **will not work in
> Cowork**. Use Copilot CLI or Coding Agent for those. Cheat-sheet:
>
> | ✅ Works in Cowork (markdown / JSON / config gen) | ❌ Needs a real shell (Copilot CLI, Coding Agent, Cursor, …) |
> |---|---|
> | `threadlight-design` · `threadlight-hitl-patterns` · `threadlight-event-triggers` (scaffold spec) · `threadlight-demo-data-factory` (data spec) · `citadel-spoke-onboarding` (config gen) · `ip-catalog` (read-only MCP) · `azure-tenant-isolation` (config files) · `foundry-cross-resource` (spec/Bicep authoring) | `threadlight-deploy` · `threadlight-local-test` · `threadlight-safe-check` · `threadlight-workspace-ui` · `foundry-hosted-agents` · `ghcp-hosted-agents` · `foundry-mcp-aca` · `foundry-evals` · `foundry-iq` · `foundry-doc-vision-speech` · `foundry-observability` · `foundry-teams-bot` · `foundry-vnet-deploy` · `foundry-toolbox` · `azd-patterns` · `gbb-pptx` · `auto-demo-producer` |
>
> Skills in the right column may still **author** their artifacts in Cowork
> (the markdown / Bicep / Dockerfile generation step is text), but you'll
> need a real shell to **execute** the resulting `azd up` / build / eval /
> deploy step. Plan workshops accordingly.

---

## Skills Catalog

> [!TIP]
> **Two primary personas use these skills:**
> - **Sellers** (non-technical, in Microsoft Copilot Cowork) — start with `threadlight-design` to tailor-craft a use-case pitch.
> - **Solution Engineers** (technical, running customer workshops) — use `threadlight-local-test` for fast inner-loop iteration, then `threadlight-deploy` for the customer sandbox.
>
> See [THREADLIGHT.md](THREADLIGHT.md) for the end-to-end pipeline and a customer-workshop runbook.

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

### 🧵 Threadlight Pipeline

End-to-end skill chain for rapid PoC delivery: customer brief → spec → local test → deploy → safe-check gate → demo. See [THREADLIGHT.md](THREADLIGHT.md) for the flow.

| Skill | Description |
|-------|-------------|
| [**threadlight-design**](skills/threadlight-design/) | Spec out a business process or customer use case (FSI, MFG, Retail, Telco, etc.) — durable SpecKit + AGENTS.md + skills + mock data + seller pitch page (`overview.html`). Cowork-friendly. |
| [**threadlight-deploy**](skills/threadlight-deploy/) | Take a designed project and generate Foundry deployment artifacts — `container.py`, `Dockerfile`, `agent.yaml`, `azure.yaml`, Bicep modules. One-command `azd up` to a hosted agent. |
| [**threadlight-local-test**](skills/threadlight-local-test/) | **For SEs.** Run a design output locally (FoundryChatClient + FastMCP + workspace UI + sample data) without `azd up` — fast iteration in Copilot CLI / Cursor / Clawpilot (needs a real shell — not Cowork). |
| [**threadlight-safe-check**](skills/threadlight-safe-check/) | **Mandatory** three-lifecycle completeness gate (design / pre-deploy / post-deploy) — selectors → resources, image-probe (no placeholder), job-success, App Insights presence. Catches silent partial deploys. |
| [**threadlight-event-triggers**](skills/threadlight-event-triggers/) | Scaffold non-interactive trigger receivers — ACA Jobs (cron) + KEDA-scaled consumers (Service Bus / Event Grid) + idempotency. |
| [**threadlight-workspace-ui**](skills/threadlight-workspace-ui/) | Curated, framework-agnostic workspace UI reference per process (case-list, dashboard, console, kanban, map) with action toolbar + audit viewer. **ACA-hosted**, not file:// |
| [**threadlight-hitl-patterns**](skills/threadlight-hitl-patterns/) | Teams Adaptive Card 1.5 flows + bot UX for the seven canonical action gates (approve, edit-and-approve, reject, escalate, signoff, audit-view, request-info). |
| [**threadlight-demo-data-factory**](skills/threadlight-demo-data-factory/) | Per-domain synthetic data + Cosmos seed / reset scripts. Anchors on industry realism canons (FSI canon ready; Retail / Telco / MFG drafted as pilots ship). |

### 🛠️ Cross-Cutting Helpers

Multi-skill scaffolding and operational discipline used by the Threadlight pipeline and standalone Foundry deployments.

| Skill | Description |
|-------|-------------|
| [**azd-patterns**](skills/azd-patterns/) | Tips and patterns for Azure Developer CLI (`azd`) — hooks, postdeploy/postprovision, ACA Job deployment, **silent-failure debug playbook** (6-rung diagnostic ladder). |
| [**azure-tenant-isolation**](skills/azure-tenant-isolation/) | Multi-tenant Azure CLI / AZD isolation for concurrent terminal sessions — index-file driven, per-tenant `AZURE_CONFIG_DIR` + `az account show` two-layer guard. |
| [**citadel-spoke-onboarding**](skills/citadel-spoke-onboarding/) | Onboard a GenAI app or Foundry project as a spoke into an AI Citadel Governance Hub — Access Contracts, APIM connections, Key Vault secrets, product policies, JWT auth. **Combines with `foundry-vnet-deploy` for VNet-isolated spokes** (Option B Foundry Connection auth posture mandatory). |

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

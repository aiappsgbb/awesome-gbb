# 🧠 Awesome GBB Skills

> A curated collection of agentic Skills by **AI Global Black Belts** at Microsoft.

[![Skills](https://img.shields.io/badge/skills-25-blue)](#skills-catalog)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Contents

- [What Are Skills?](#what-are-skills)
- [Featured Pipeline: Threadlight](#-featured-pipeline-threadlight) _(moved to [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills))_
- [Featured Workspace: Zava](https://github.com/aiappsgbb/zava-constellation)
- [Demo Guide](DEMOS.md)
- [Supported Coding Runtimes](#supported-coding-runtimes)
- [Skills Catalog](#skills-catalog)
  - [🏗️ Foundry Building Blocks](#️-foundry-building-blocks)
  - [🛠️ Cross-Cutting Helpers](#️-cross-cutting-helpers)
  - [🛡️ Governance](#️-governance)
  - [📊 Content Generation](#-content-generation)
  - [🧬 Org Composition](#-org-composition)
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

> **Threadlight has moved to its own repo →
> [aiappsgbb/threadlight-skills](https://github.com/aiappsgbb/threadlight-skills)**
>
> Eight `threadlight-*` skills that take a customer from a one-paragraph brief
> through spec → local test → deploy → safe-check gate → demo. See the
> [live experience page](https://aiappsgbb.github.io/threadlight-skills/).
>
> Install alongside awesome-gbb for the full pipeline:
> ```bash
> copilot plugin marketplace add aiappsgbb/threadlight-skills
> copilot plugin install threadlight-skills@threadlight-skills
> ```

---

## 🏙️ Featured Workspace: Zava

> **Zava has moved to its own repo →
> [aiappsgbb/zava-constellation](https://github.com/aiappsgbb/zava-constellation)**
>
> Three skills (`research-company` → `compose-org` → `zava-workspace-deploy`)
> that take a company name and produce a deployed, branded digital-clone
> workspace on Azure. See the
> [live experience page](https://aiappsgbb.github.io/zava-constellation/).
>
> **Zava + Threadlight = full story.** Threadlight (in
> [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills))
> designs and deploys individual business-process agents. Zava wraps them in a
> multi-domain control plane with fleet orchestration and a polished dashboard.

---

## Supported Coding Runtimes

Skills are agnostic Markdown contracts — they load in any runtime that understands the `SKILL.md` shape. The catalog is verified against the runtimes below.

| Runtime | Shell + package installs | Long-running processes | Best for |
|---|---|---|---|
| **GitHub Copilot CLI** (`gh copilot`) | ✅ Full | ✅ | **Primary target**. Every skill works end-to-end. |
| **GitHub Copilot App** ([`github/app`](https://github.com/github/app)) | ✅ Full | ✅ | **Desktop GUI built on the CLI** — inherits skills, MCP servers, plugins, hooks. Best for users who prefer a click-installer (DMG/EXE/AppImage) over `npm install -g`. Public preview. |
| **GitHub Copilot Coding Agent** (cloud) | ✅ Full | ✅ | All skills, hands-off cloud runs. |
| **Cursor** | ✅ Full | ✅ | All skills (load via project `.cursorrules` shim). |
| **VS Code GitHub Copilot Chat** | ✅ Full | ✅ | All skills (terminal-attached). Agent-mode also supports the agent-plugin bundle format (preview). |
| **Claude Code** (`clawpilot`) | ✅ Full | ✅ | All skills. Native plugin format (`.claude-plugin/plugin.json`) is auto-detected by VS Code and Copilot too. |
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

Reference patterns for Microsoft Foundry agents (prompt and hosted), memory, MCP servers, evals, RAG, vision/speech, and observability.

| Skill | Description |
|-------|-------------|
| [**foundry-prompt-agents**](skills/foundry-prompt-agents/) | Create declarative Foundry agents — model + instructions + tools, no containers, no custom code. `PromptAgentDefinition`, tool wiring (web search, code interpreter, file search, MCP, OpenAPI), versioning, structured inputs, agent applications |
| [**foundry-voice-live**](skills/foundry-voice-live/) | Build real-time voice agents with Azure Voice Live (GA 2025-10-01). Three-rung migration from Realtime → Voice Live → +Agent in 3 lines. Semantic VAD, echo cancel, Neural HD voices, benchmark pattern, Gradio + FastRTC UI |
| [**foundry-hosted-agents**](skills/foundry-hosted-agents/) | Refreshed hosted-agents preview — `Agent` + `FoundryChatClient` + `ResponsesHostServer`, identity model, RBAC, MCP wiring, **`SkillsProvider` progressive skill loading** vs. legacy concat, troubleshooting |
| [**foundry-memory**](skills/foundry-memory/) | Native Foundry Memory Store API for persistent agent memory — user profiles, chat summaries, scope isolation via `{{$userId}}` / `x-memory-user-id`, semantic recall, and memory tool wiring as the catalog replacement for Mem0 |
| [**foundry-teams-bot**](skills/foundry-teams-bot/) | Connect a hosted agent to Microsoft Teams + M365 Copilot (CEA manifest 1.21) — bot code, Bicep, Teams manifest, UAMI auth, ACA deployment |
| [**ghcp-hosted-agents**](skills/ghcp-hosted-agents/) | Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) — BYOK auth, Invocations protocol, SSE streaming, long-running tool loops |
| [**foundry-mcp-aca**](skills/foundry-mcp-aca/) | Deploy custom MCP servers as ACA / Azure Functions — Cosmos MCPToolKit, Playwright MCP, mock MCP, **validate-or-reject** evidence enforcement |
| [**foundry-evals**](skills/foundry-evals/) | Evaluate hosted agents — two-phase invoke+score, 6 built-in evaluators, enriched-dataset shape (`tool_calls` + `tool_outputs`), continuous loop |
| [**foundry-iq**](skills/foundry-iq/) | Enterprise RAG with Foundry IQ — Azure AI Search Knowledge Bases, agentic retrieval, multi-hop reasoning, citation-backed responses, **hosted-agent runtime identity callout** + **7-item bootstrap hardening checklist** (no-`az rest`-uploads, fail-fast, key sanitization, 32k-byte chunking, RBAC propagation wait, post-upload count verify, idempotent recovery) |
| [**foundry-doc-vision-speech**](skills/foundry-doc-vision-speech/) | Wire vision (gpt-5.4 family), Document Intelligence v4, and Azure Speech (STT/TTS) into a hosted agent — MCP and native Toolbox patterns + RBAC matrix |
| [**foundry-observability**](skills/foundry-observability/) | End-to-end App Insights + Log Analytics + OpenTelemetry across hosted agents, MCP servers, ACA jobs, bot, workspace — **closes the silent-telemetry gap** where `azd up` returns 0 but AppIn stays empty |
| [**foundry-cross-resource**](skills/foundry-cross-resource/) | Cross-resource model invocation via AI Gateway (APIM) — use models from another Foundry resource or a shared pool |
| [**foundry-vnet-deploy**](skills/foundry-vnet-deploy/) | Deploy Foundry with **Agent Setup inside a private VNet** — guided interview generates `.bicepparam`, runs `az deployment group create` with fixed-timestamp anti-duplication retry, supports new/existing VNet + reused CosmosDB / Storage / AI Search / private DNS zones, **optional spoke→hub peering + APIM private DNS link modules for Citadel-spoke combinations** |
| [**foundry-toolbox**](skills/foundry-toolbox/) | Use Foundry Toolbox GA with stable `AIProjectClient.toolboxes` CRUD, Toolbox-specific SDK models, authenticated `FoundryToolbox` hosted-agent wiring, immutable version promotion/rollback, the `azure_ai_search`-is-INDEX-not-KB boundary, and explicitly preview Tool Search (`tool_search` + `call_tool`) without the retired preview feature header |
| [**foundry-skill-catalog**](skills/foundry-skill-catalog/) | Foundry Skills REST API (`{project}/skills`) — project-level store for instruction-only `SKILL.md` files. Documents the **JSON-mode-is-WRITE-ONLY trap** (instructions submitted at create are never returned by GET / list / download / `?include=`), the quoted-frontmatter → HTTP 500 trap, the mandatory `Foundry-Features: Skills=V1Preview` header, and ships a verified **`FoundrySkillsSource(SkillsSource)`** adapter so `agent_framework.SkillsProvider` can consume Foundry skills at runtime (not just file-copy at build time) |

### 🛠️ Cross-Cutting Helpers

Multi-skill scaffolding and operational discipline used by the [Threadlight pipeline](https://github.com/aiappsgbb/threadlight-skills) and standalone Foundry deployments.

| Skill | Description |
|-------|-------------|
| [**azd-patterns**](skills/azd-patterns/) | Tips and patterns for Azure Developer CLI (`azd`) — hooks, postdeploy/postprovision, ACA Job deployment, **silent-failure debug playbook** (6-rung diagnostic ladder). |
| [**azure-tenant-isolation**](skills/azure-tenant-isolation/) | Multi-tenant Azure CLI / AZD isolation for concurrent terminal sessions — index-file driven, per-tenant `AZURE_CONFIG_DIR` + `az account show` two-layer guard. |
| [**gbb-humanizer**](skills/gbb-humanizer/) | Remove signs of AI-generated writing from prose — 29 patterns from Wikipedia's "Signs of AI writing" (em-dash overuse, rule-of-three, AI vocabulary, copula avoidance, sycophantic openers, signposting), two-pass rewrite + AI-tell audit. **Ships pre-canned GBB voice samples** (seller pitch + technical blog), **section-aware mode** (skip code/tables/SME quotes), **density-preserving guardrail** so domain rule-of-three lists survive. Adapted from [blader/humanizer](https://github.com/blader/humanizer) v2.5.1 (MIT). |
| [**ghcp-cli-config**](skills/ghcp-cli-config/) | Bootstrap GitHub Copilot CLI for GBB workflows — 6 recommended MCP servers (mslearn, Azure, Playwright, context7, tavily, mem0), `settings.json` baseline (model, `sessionSync`, `allowedUrls`, `trustedFolders`), work-iq plugin family for Microsoft staff, `autoApprove` safe-default matrix, and a **fresh-machine bootstrap procedure** the agent can execute step-by-step. Distilled from a live GBB engineer's `~/.copilot/`. |
| [**paygo-ptu-cost-analyzer**](skills/paygo-ptu-cost-analyzer/) | Headless PAYGO-vs-PTU cost analysis for Azure OpenAI deployments — vendored analyzer (`analysis.py` / `formatting.py` / `models.json` / 2× KQL) from [`aiappsgbb/ptu-paygo-mix`](https://github.com/aiappsgbb/ptu-paygo-mix) `@e1786f8` with the Streamlit UI stripped out. Ingests **CSV / Log Analytics KQL / synthetic** and emits a 4-file report (markdown + JSON + 2× PNG charts) with PTU sizing across configurable percentiles, monthly/yearly term pricing, global/data-zone tier rates, and a recommendation rule (target percentile under PAYGO baseline). Ships **two KQL paths** — default uses `InputTokens − ProcessedPromptTokens` for cached-token derivation; `active_tokens.kql` is the fallback for telemetry configs that only expose `ActiveTokens`. CLI: `python references/run_report.py --csv input.csv --model gpt-5.4 --tier global --out-dir ./report`. |

### 🛡️ Governance

The **AI Citadel** governance ladder — three skills that compose into
defence-in-depth for production agent platforms:

1. **Layer 1 (gateway infra)** — `citadel-hub-deploy` stands up the
   shared APIM AI gateway + Foundry control plane + telemetry sink.
2. **Layer 1 (per-spoke wiring)** — `citadel-spoke-onboarding` connects
   each agent project to the hub via per-team Access Contracts.
3. **Layer 1.5 (in-process)** — `foundry-agt` wraps the Microsoft Agent
   Governance Toolkit around the agent runtime itself, catching attacks
   the gateway can't see (intent classification, capability allow/deny,
   hash-chained audit, OWASP ASI 2026 coverage). The 26.67% (prompt-only)
   vs 0.00% (deterministic AGT) red-team gap is why both layers matter.

Compose with `foundry-hosted-agents` / [`threadlight-deploy`](https://github.com/aiappsgbb/threadlight-skills) (in-process
middleware), `foundry-vnet-deploy` (VNet-isolated spokes), or
`azd-patterns` (sidecar pattern).

| Skill | Description |
|-------|-------------|
| [**citadel-hub-deploy**](skills/citadel-hub-deploy/) | Deploy the **AI Citadel Governance Hub** (Layer 1 infra) — APIM AI Gateway + 2× Microsoft Foundry control plane + Cosmos usage telemetry + Logic App billing + 4 LLM APIs (Azure OpenAI / OpenAI Realtime / Universal LLM / Unified AI wildcard) + 13 Private DNS Zones + Managed Redis semantic cache. Wraps `Azure-Samples/ai-hub-gateway-solution-accelerator` `citadel-v1` branch (azd template, MIT) at a pinned commit; **does NOT fork or vendor upstream Bicep**. Ships 3 curated env profiles (`pilot-quickstart`, `enterprise-baseline`, `vnet-isolated-spoke-aware`), pre-flight checklist, live audit notes against a real `rg-citadel-hub-01` deployment in Sweden Central (resource inventory + APIM smoke calls + latency baselines + 8 Known Issues incl. `api-key` header convention + `max_completion_tokens` GPT-5.4 migration). |
| [**citadel-spoke-onboarding**](skills/citadel-spoke-onboarding/) | Onboard a GenAI app or Foundry project as a spoke into an AI Citadel Governance Hub — Access Contracts, APIM connections, Key Vault secrets, product policies, JWT auth. **Combines with `foundry-vnet-deploy` for VNet-isolated spokes** (Option B Foundry Connection auth posture mandatory). Pairs with `citadel-hub-deploy` for the full Layer 1 story. |
| [**foundry-agt**](skills/foundry-agt/) | Wrap the [Microsoft Agent Governance Toolkit (AGT)](https://github.com/microsoft/agent-governance-toolkit) v3.6.0 around Foundry hosted agents, MCP servers, and Citadel spokes. **Path A** (in-process MAF middleware, GBB-verified ~8–12 µs/eval on Win + Py 3.13) for hosted agents; **Path B** (ACA sidecar) for non-MAF workloads; **Path C** (Citadel adapter) for governed spokes. Ships 3 starter YAML policies (default conservative / HITL gate / PII deny), the `create_governance_middleware(...)` factory snippet (working — upstream Foundry doc shows stale kwargs that no longer exist), an ACA-sidecar Bicep fragment, and **5 field-tested Known Issues** (Windows UTF-8 CLI trap, stale Foundry-doc kwargs, `Agent` ctor rename, RogueDetection setup gotcha, verifier version skew). Wrapper skill — upstream is canon, links don't duplicate. |
| [**azure-sre-agent**](skills/azure-sre-agent/) | GBB wrapper for [Azure SRE Agent](https://learn.microsoft.com/en-us/azure/sre-agent/) (preview). **Thin** — uses Microsoft's official toolchain at [`microsoft/sre-agent`](https://github.com/microsoft/sre-agent) (Bicep + Terraform + azd + PS deploy backends, `bin/` CLI) and plugin marketplace at [`Azure/sre-agent-plugins`](https://github.com/Azure/sre-agent-plugins). Adds the three things MS won't ship: **3 GBB recipes** (`citadel-routed`, `foundry-hosted-agents`, `threadlight-pilot-handover`) in upstream byte-exact shape; **2 GBB plugins** (`gbb-citadel`, `gbb-foundry`) with 5 expert skills (JWT 403 debug, APIM throttle, hosted-agent deploy triage, BYOK 401, AOAI quota); a **pre-flight runbook** for the gotchas the official docs assume away (Zscaler `*.azuresre.ai`, region scarcity, `Microsoft.App` RP); and **`data_plane.py`** so other awesome-gbb skills (Threadlight) can post incidents via HTTP trigger. |

### 📊 Content Generation

| Skill | Description |
|-------|-------------|
| [**gbb-pptx**](skills/gbb-pptx/) | Generate professional PowerPoint presentations using python-pptx — dark & light themes, card layouts, bullet lists, speaker notes. (Renamed from `pptx` in v2.0.0 to avoid collision with the upstream Anthropic `pptx` skill.) |
| [**auto-demo-producer**](skills/auto-demo-producer/) | Produce narrated video demos of web apps automatically — Playwright browser recording + edge-tts neural narration + ffmpeg assembly into polished MP4 |

### 🧬 Org Composition & Zava Workspace

> **Moved to [aiappsgbb/zava-constellation](https://github.com/aiappsgbb/zava-constellation)** —
> `research-company`, `compose-org`, and `zava-workspace-deploy`.

### 🔍 Discovery

| Skill | Description |
|-------|-------------|
| [**ip-catalog**](skills/ip-catalog/) | Discover AI Apps GBB IP catalog via MCP — search, list, filter, and inspect intellectual property assets including metadata and READMEs |

---

## How to Use

> [!TIP]
> **Browse the full catalog →** <https://fluffy-carnival-6qny72q.pages.github.io/> — searchable skill index, per-skill detail pages, plugin install commands, and an [`llms.txt`](https://fluffy-carnival-6qny72q.pages.github.io/llms.txt) machine-readable listing for AI agents. Mirrors the [`github/awesome-copilot`](https://awesome-copilot.github.com/) site pattern.

> [!TIP]
> **Install all 28 skills in one command via plugin.** The catalog ships as a single [Copilot CLI plugin](plugin.json):
>
> ```bash
> # Register the marketplace once:
> copilot plugin marketplace add aiappsgbb/awesome-gbb
>
> # Install all skills:
> copilot plugin install awesome-gbb@awesome-gbb
> ```
>
> The plugin also works in the [Copilot Desktop App (preview)](https://github.com/github/app), [VS Code Copilot Chat agent mode (preview)](https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode), and [Claude Code](https://docs.anthropic.com/en/docs/claude-code/plugins) — same `plugin.json` spec, cross-runtime auto-detect.

**Or install one skill at a time with `gh` CLI:**

> [!TIP]
> **First time on Copilot CLI?** Install [**ghcp-cli-config**](skills/ghcp-cli-config/) first — it bootstraps `~/.copilot/` with the 6 recommended MCP servers (`mslearn`, `Azure`, `Playwright`, `context7`, `tavily`, `mem0`), a sensible `settings.json` baseline, and the work-iq plugin family for Microsoft staff. The agent can run the bootstrap end-to-end on a fresh machine.

> [!TIP]
> **Prefer a GUI over the terminal?** Install the [**GitHub Copilot App**](https://github.com/github/app) (public preview) — a native macOS / Windows / Linux desktop application built on Copilot CLI. Because it shares `~/.copilot/`, **every skill in this catalog works in the app out of the box** — same `gh skill install` commands, same MCP servers, same plugins. Lower-friction onramp for SEs and sellers who don't live in a terminal.
>
> - **Business / Enterprise subscribers:** Download today: [Mac (Apple Silicon)](https://github.com/github/app/releases/latest/download/GitHub-Copilot-darwin-arm64.dmg) · [Windows](https://github.com/github/app/releases/latest/download/GitHub-Copilot-windows-x64-setup.exe) · [Linux AppImage](https://github.com/github/app/releases/latest/download/GitHub-Copilot-linux-x64.AppImage) · [Mac (Intel)](https://github.com/github/app/releases/latest/download/GitHub-Copilot-darwin-x64.dmg) · [Windows (ARM)](https://github.com/github/app/releases/latest/download/GitHub-Copilot-windows-arm64-setup.exe)
> - **Pro / Pro+ subscribers:** [Sign up for early access](https://gh.io/github-app) (waitlist).
> - **Docs + walkthrough:** <https://gh.io/github-app-docs>
> - **First-launch tip:** if you have Copilot CLI installed already, the app picks up your existing `~/.copilot/` automatically. Otherwise run the [**ghcp-cli-config**](skills/ghcp-cli-config/) skill from inside the app to seed the directory.

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
> **Recommended global install for sellers + SEs:** `foundry-hosted-agents`, `foundry-observability`, `azure-tenant-isolation` (from awesome-gbb) plus the full [threadlight-skills](https://github.com/aiappsgbb/threadlight-skills) plugin. For Zava skills, see [zava-constellation](https://github.com/aiappsgbb/zava-constellation). Other skills can stay at project scope.

---

## Agentic Loop — The BUILD → RUN → SCALE Pipeline

The [`agentic-loop`](https://github.com/aiappsgbb/agentic-loop) initiative provides the **orchestration layer** that drives awesome-gbb skills through a 5-stage development loop: **Specify → Plan → Implement → Verify → Deploy**. It uses the [Lean Toolkit (Spec2Cloud)](https://github.com/Azure-Samples/Spec2Cloud) plugin and an `agentic-loop` skill that applies GBB defaults (Foundry hosted agents, model selection, region picker) and recommends which awesome-gbb skills to install for each spec.

**Quick setup:**

```bash
# 1. Install the lean toolkit plugin (5-stage loop)
copilot plugin marketplace add Azure-Samples/Spec2Cloud
copilot plugin install lean@Spec2Cloud

# 2. Install the agentic-loop skill (GBB defaults + skill recommender)
gh skills install aiappsgbb/agentic-loop agentic-loop --dir .github/skills --agent github-copilot

# 3. Run the loop
copilot -p "/lean:specify <your idea here>"
```

The agentic-loop skill will recommend awesome-gbb skills based on your spec's content — foundational skills for every build, plus specialized skills when the spec mentions evals, governance, MCP, VNet isolation, or production gateway patterns. See the [getting-started playbook](https://github.com/aiappsgbb/agentic-loop/tree/main/playbooks/getting-started) for a step-by-step walkthrough.

---

## How we test — six CI gates, four testing tiers, live Azure

Every skill in this catalog is a **contract**: the code samples in `SKILL.md` are the exact code a consumer will copy. If a sample doesn't run, the skill is broken. To keep that contract honest as upstream SDKs move, we run a self-healing test+freshness pipeline on real Azure infrastructure — not just lint.

```mermaid
flowchart LR
    PR[PR opened] --> G1[skill-validation<br/>T0 lint]
    PR --> G2[automation-pr-gate<br/>mass-edit invariants]
    PR --> G3[pin-validation<br/>T1 re-runs validation.script]
    PR --> G4[skill-test<br/>T2 import smoke + T3 E2E Azure]
    G1 & G2 & G3 & G4 --> M{all green?}
    M -- yes --> R[human review + merge]
    M -- yes, Copilot PR --> A[auto-merge-copilot<br/>squash-merges]
    CRON[weekly cron] --> F[skill-freshness<br/>drift detection]
    F --> ISSUE[consolidated issue<br/>impact-classified] --> COP[@Copilot opens PR] --> PR
```

**Six CI gates** (see [`.github/workflows/`](.github/workflows/)):

| Gate | When | What it checks |
|------|------|----------------|
| [`skill-validation.yml`](.github/workflows/skill-validation.yml) | Every PR | Frontmatter parses, description ≤ 1024 chars, valid SemVer, no forbidden strings, pin files conform to schema, plugin manifests version-consistent |
| [`automation-pr-gate.yml`](.github/workflows/automation-pr-gate.yml) | Every PR | Mass-edit invariants (no normalization of reference canon, no cross-skill body edits without `[multi-skill]`, no MAJOR bumps from metadata-only changes) |
| [`pin-validation.yml`](.github/workflows/pin-validation.yml) | Every PR touching `skills/<skill>/` | **Re-runs `validation.script` on the runner** for the pin file of every changed skill — no "trust me, I tested" path |
| [`skill-freshness.yml`](.github/workflows/skill-freshness.yml) | Weekly cron | Detects SHA drift, PyPI version bumps, upstream KI closures, link rot, validation age — opens one consolidated issue per skill with `impact:critical/high/medium/low` label |
| [`skill-test.yml`](.github/workflows/skill-test.yml) | Every PR + push to main + weekly cron | T2 import smoke (all auto-tier pins) + **T3 E2E Azure** (deploys agents, calls models, verifies the credential chain works against real resources in `<ci-resource-group>`) |
| [`auto-merge-copilot.yml`](.github/workflows/auto-merge-copilot.yml) | On check-suite completion | Auto-approves and squash-merges Copilot PRs once all gates pass — closes the freshness loop without a human bottleneck |

**Four testing tiers** (see [AGENTS.md § 9.8](AGENTS.md#98--skill-testing-tiers)) — each subsumes the ones below:

- **T0 · Lint** — frontmatter parses, description ≤ 1024, no forbidden strings, deprecated-API scan passes. Every PR.
- **T1 · Pin validation** — `validation.script` runs end-to-end; every `expected_output` substring must appear in stdout. Required on pin-file changes.
- **T2 · Import smoke** — `pip install <pinned-version>` + `python -c "from X import Y"` for every import in SKILL.md code samples. Required on MINOR/MAJOR upstream bumps.
- **T3 · E2E Azure** — deploys real agents, makes real API calls (Foundry, ACA, ACR), verifies the credential chain works end-to-end. CI has OIDC-federated credentials and dedicated infra (`<ci-foundry-account>`, `<ci-container-registry>`, `<ci-container-app-env>`, `gpt-5.4-mini`, `text-embedding-3-small`). Required for any skill that tells consumers to connect to Azure.

**Self-healing freshness loop.** Every wrapper skill ships a machine-readable [`upstream-pin.md`](scripts/templates/upstream-pin.template.md). The weekly cron runs five drift detectors (SHA, PyPI, upstream-issue closure, link rot, validation age), consolidates signals into one issue per skill with an impact label, and assigns auto-tier skills to **`@Copilot`**. The coding agent refreshes the pin, opens a PR, the six gates above validate it live against Azure, and `auto-merge-copilot` squash-merges on green. A human only intervenes when impact is `critical` or the pin requires credentials the agent doesn't have.

**Patterns from the trenches.** The pipeline is what it is because 25 hard-won patterns (LAW ingestion lag, OIDC TTL on teardown, ARM cross-resource cache lag, Foundry project-MI vs caller-UAMI 401s, autoregressive marker priming, Copilot-CLI 429 throttling, …) are baked into the workflows and fixture authoring rules. Each pattern carries a forensic provenance link to the run that exposed it. See [AGENTS.md § 9.7](AGENTS.md#97--azure-ci-credentials-and-e2e-infrastructure) for the full list, or the [Engineering page](https://aiappsgbb.github.io/awesome-gbb/engineering/) for a curated tour.

---

## Repository Structure

```
README.md                 # This file — catalog index + install instructions
DEMOS.md                  # Demo guide for Foundry walkthroughs
AGENTS.md                 # Contributor & sub-agent safety guide
plugin.json               # Single plugin manifest (all 28 skills via "skills/")
skills/
  <skill-name>/
    SKILL.md              # Skill definition (frontmatter + instructions)
    README.md             # Optional: extended docs, examples, changelog
```

---

## Contributing

> [!IMPORTANT]
> **Read [AGENTS.md](AGENTS.md) first** if you (or a sub-agent acting on your
> behalf) are about to edit any skill. It captures the invariants — agnostic
> wording, reference-data canon, `metadata.version` rules, the mass-edit
> safety rails — most of which are **now enforced by CI** (see § 9 of
> AGENTS.md and the [`automation-pr-gate`](.github/workflows/automation-pr-gate.yml)
> workflow).

1. **Fork & branch** — create a feature branch from `main`.
2. **Add your Skill** — place it under `skills/<your-skill-name>/SKILL.md`.
3. **Open a PR** — describe the scenario, target audience, and any dependencies.
4. **Peer review** — at least one GBB team member must approve before merge.

### Skill Quality Checklist

- [ ] Clear, concise `description` in frontmatter (≤ 1024 chars — CI-enforced)
- [ ] Well-defined trigger phrases (when should the skill activate?)
- [ ] Actionable instructions (the agent *does* the work, not just advises)
- [ ] No secrets or credentials embedded
- [ ] Tested with at least one agentic runtime
- [ ] If the skill wraps an external repo/SDK: include `references/upstream-pin.md`
      from [`scripts/templates/upstream-pin.template.md`](scripts/templates/upstream-pin.template.md)
      so the freshness lifecycle picks it up

### 🪴 Freshness lifecycle

Wrapper skills (those citing a `github.com/<org>/<repo>` or pinning a
preview SDK version) ship a machine-readable `references/upstream-pin.md`
declaring their upstream contract. The
[`Skill freshness`](.github/workflows/skill-freshness.yml) GitHub Action
runs weekly and opens a per-skill GitHub issue when it detects:

- SHA drift on the pinned upstream branch
- PyPI version drift on a pinned package
- Closure of an upstream issue documented in `known_issues[]`
- Link rot on a documented URL
- Validation age > 180 days

Issues for skills with `automation_tier: auto` are **assigned to
`@Copilot`** — the GitHub Copilot coding agent autonomously executes the
pin file's `validation.script` and opens a PR. The standard CI gates
([`skill-validation`](.github/workflows/skill-validation.yml) and
[`automation-pr-gate`](.github/workflows/automation-pr-gate.yml)) review
the PR. A human reviews and merges. See [AGENTS.md § 9](AGENTS.md) for
the full lifecycle convention.

## License

This project is licensed under the [MIT License](LICENSE).

## Code of Conduct

This project follows the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

---
name: threadlight-deploy
description: >
  Take a designed agent project (from threadlight-design or manually crafted) and generate
  all deployment artifacts for Microsoft Foundry Hosted Agents. Reads specs/SPEC.md,
  AGENTS.md, and skills to produce container.py, Dockerfile, pyproject.toml, azd project,
  and deploy-notes.md. One-command deployment via `azd up`.
  USE FOR: deploy to Foundry, make this deployable, generate deployment files, Foundry hosted agent,
  containerize agent, prepare for Foundry, package agent, deploy agent, hosted deployment,
  agent deployment, azd deploy, azd up.
  DO NOT USE FOR: designing the process (use threadlight-design), running evals (use foundry-evals),
  Teams bot deep dive (use foundry-teams-bot), MCP server deployment (use foundry-mcp-aca),
  GHCP SDK variant (use ghcp-hosted-agents), tenant/subscription isolation for azd (use azure-tenant-isolation).
metadata:
  version: "1.1.6"
---

# Foundry Hosted Agent Deploy

Take a project folder (containing AGENTS.md, `src/agent/skills/`, config/, etc.) and enrich
it with all files needed to deploy as a **Microsoft Foundry Hosted Agent**.

**Default runtime: GHCP SDK** (`CopilotClient` + `InvocationAgentServerHost`, Invocations
protocol). Falls back to **MAF** (`Agent` + `FoundryChatClient` + `ResponsesHostServer`,
Responses protocol) when Toolbox tools or custom `@tool` functions are needed.

Uses the **`azd ai agent` extension** for declarative deployment — `azure.yaml` defines
agent configuration, model deployments, and container resources; `azd up` handles everything.

## When to Use

- User has a designed agent project and wants to deploy it to Foundry
- User asks to "make this deployable" or "package for Foundry"
- User wants to containerize their agent for hosted deployment
- User asks for Dockerfile, container runtime, or deployment files
- User asks about MCP tools in Foundry hosted agents

## Why Hosted Agents (not Prompt/Declarative Agents)

Foundry offers simpler agent types (`PromptAgentDefinition`, `DeclarativeAgentDefinition`)
that run on Foundry's servers with no custom container. However, these **cannot** support:

- **SkillsProvider** — progressive skill discovery and on-demand loading
- **Custom tools** — `@tool(approval_mode="never_require")` Python functions
- **Complex orchestration** — multi-step workflows, custom error handling
- **Custom telemetry** — OpenTelemetry instrumentation with Azure Monitor
- **Instruction injection** — runtime `COSMOS_DATABASE` substitution, tool-use discipline

For any agent that uses **skills, custom middleware, or complex logic**, you MUST use
`HostedAgentDefinition` with a custom container.

## Prerequisites

The input folder MUST have:
- `AGENTS.md` — agent identity, skills, tools, behavioral guidelines
- `src/agent/skills/*/SKILL.md` — one or more skill definitions

Recommended (from `threadlight-design`):
- `specs/SPEC.md` — SpecKit specification (business rules, data models, integrations, compliance)
- `specs/manifest.json` — checkpoint metadata (process name, phase, status)
- `specs/sample-data/*.json` — mock data for inaccessible systems
- `specs/manifest.json` — machine-readable deployment contract
- `src/agent/config/*.json` — process configuration

> [!IMPORTANT]
> **Dependency skills.** This skill references content from other skills instead of
> duplicating it. Check that companion skills are available:
>
> | Skill | When Needed |
> |-------|------------|
> | `foundry-hosted-agents` | **Always** — RBAC, identity model, agent.yaml schema, dependency versions, troubleshooting |
> | `threadlight-design` | **Always** — produces SPEC.md sections this skill consumes (§ 5b, § 7b, § 8, § 8b, § 9, § 10b, § 11b, § 11c, § 11d) |
> | `azd-patterns` | **Always** — Bicep module library that Phase 6 (Module Composer) reads from |
> | `foundry-iq` | **Default for every process** — provisions the Knowledge Agent + AI Search index for SPEC § 7 knowledge sources |
> | `foundry-teams-bot` | If Teams integration is needed |
> | `foundry-mcp-aca` | If deploying custom MCP servers as ACA or Azure Functions |
> | `threadlight-workspace-ui` | If SPEC § 8b specifies an operator workspace |
> | `threadlight-hitl-patterns` | If SPEC § 8 declares any human action gate (approve/edit-and-approve/reject/escalate/signoff/audit-view/request-info) |
> | `threadlight-event-triggers` | If SPEC § 10b declares any event-driven, scheduled, or webhook trigger |
> | `threadlight-demo-data-factory` | If SPEC § 5 marks any system as `mock` (almost always true for pilots) |
> | `foundry-doc-vision-speech` | If SPEC § 7b selects any vision / DocIntel / Speech model |
> | `foundry-evals` | For post-deployment evaluation AND continuous evaluation: **Plan A** (default) — Foundry's built-in scheduled evaluations (no extra infra). **Plan B** (fallback) — ACA Job cron eval that reads from App Insights and writes to Workbook (use only when Plan A doesn't yet support hosted-agent eval kinds you need). Phase 6 includes the ACA Job ONLY when SPEC § 9 sets `continuous_eval.plan: "B"` |
> | `citadel-spoke-onboarding` | **Phase 7 (opt-in)** — runs ONLY when SPEC § 11b sets `governance_hub.required: yes` |
>
> Use `/skills list` to check availability. If missing, install from `aiappsgbb/awesome-gbb`.

## Workflow

```
Phase 0  →  Phase 1   →  Phase 2  →  Phase 3   →  Phase 4   →  Phase 5  →  Phase 6  →  Phase 6.5 →  Phase 6.7    →  Phase 7
Poly-repo   Analyze      Generate    Validate     Teams Bot    azd        Module      Demo data     Prep-guide       Citadel
guard       SPEC +       runtime     scaffold     (optional)   project    composer    seed (when    live walkthrough handoff
            AGENTS.md    files                                  scaffold   (Bicep)     mocks exist)  back-fill        (opt-in)
```

---

## Phase 0: Poly-Repo Guard (mandatory pre-flight)

**Rule**: each threadlight process gets ONE repo. ONE repo = ONE process = ONE
`azd up`. **Never multi-process repos.**

### Why

We learned this the hard way in older multi-process repos. Multi-process
repos:
- Inflate Bicep into one giant template with 70% `if` blocks
- Force unrelated processes to share azd env, breaking iteration
- Make customer hand-off awkward (they only want one process; they get all 13)
- Concentrate blast radius — one botched deploy takes down siblings

### Pre-flight checklist (run this FIRST, before Phase 1)

Inspect the input folder. If ANY of these are true, **stop and ask the user
to split the repo before proceeding**:

- More than one `specs/SPEC.md` exists at any depth
- More than one `AGENTS.md` exists at any depth
- The folder name contains a plural / catalog noun (`processes/`, `catalog/`, `pilots/`)
- The folder contains nested `specs/<process-slug>/SPEC.md` siblings
- A previous run produced an `azure.yaml` with multiple `services:` entries that
  point to different agent containers

### How to split

```
Before (rejected):                  After (each is its own azd up):
<multi-process-repo>/             <your-process-repo>/
├── <process-a>/                    ├── specs/
│   ├── specs/                       │   └── SPEC.md
│   └── src/                         ├── src/
├── <process-b>/                    └── azure.yaml
│   ├── specs/
│   └── src/                         retail-pim-enrichment/
└── azure.yaml  (← shared)           ├── specs/
                                     │   └── SPEC.md
                                     ├── src/
                                     └── azure.yaml
```

The `threadlight-design` skill respects this by default — it generates one
self-contained subtree per process. This skill enforces it.

---

## MCP in Foundry

Hosted agent containers connect to MCP servers using `client.get_mcp_tool()` from
`FoundryChatClient`. The container loads `mcp-config.json` at startup and creates
tool instances for each configured server.

```
┌────────────────────────┐     HTTPS      ┌─────────────────────┐
│  Hosted Agent Container │ ─────────────► │  MCP ACA            │
│  client.get_mcp_tool()  │               │  (e.g. Cosmos MCP)  │
│  Agent + ResponsesHost  │               │  Port 8080 /mcp     │
└────────────────────────┘                └─────────────────────┘
```

**How it works:**
- Container loads `mcp-config.json` at startup (or `MCP_SERVER_URL` env var)
- Creates `client.get_mcp_tool(name=..., url=..., approval_mode="never_require")` per server
- Passes tools to `Agent(tools=[...])` alongside skill-loaded instructions
- Container manages the entire MCP lifecycle

**MCP protocol requirements (ALL 6 must return HTTP 200):**
1. `initialize` — Protocol handshake
2. `notifications/initialized` — Client notification
3. `tools/list` — Discover available tools
4. `prompts/list` — Required by agent-framework (even if empty)
5. `resources/list` — Required by agent-framework (even if empty)
6. `logging/setlevel` — Set log level (lowercase!)

### Custom MCP Servers

For data stores not covered by Foundry built-ins, deploy your own MCP server:

| Option | Best For | Endpoint Pattern |
|--------|----------|-----------------|
| **Azure Container App** | Cosmos DB, custom APIs | `https://<aca>.azurecontainerapps.io/mcp` |
| **Azure Functions** | Lightweight, consumption-billed | `https://<func>.azurewebsites.net/runtime/webhooks/mcp` |

**Transport requirements:**
- Foundry only accepts **remote HTTP** MCP endpoints (no stdio/local)
- ACA: Streamable HTTP at `/mcp` endpoint (JSON-RPC over HTTP POST)
- Azure Functions: HTTP Streamable transport
- Non-streaming tool call timeout: **100 seconds**
- Private MCP (VNet) requires Standard Agent Setup

---

## Phase 1: Analyze the Design

Read all available input files in this priority order:

#### 1a. Read `specs/manifest.json` (if exists)
Machine-readable deployment contract from `threadlight-design`. Provides:
- Process name, traits, business rule count
- Mock systems list → flag for deploy-notes warnings
- Compliance constraints → inform model/region selection

#### 1b. Read `specs/SPEC.md` (if exists)
SpecKit specification from `threadlight-design`. Extract:
- **§ 5 System Integrations** → which are mock vs real → drives MCP config
- **§ 6 Tool Contracts** → map to Foundry tools or MCP servers
- **§ 8 Human Interaction Points** → Teams bot needed? Which channels?
- **§ 9 Success Criteria** → eval scenarios for post-deploy validation (→ `foundry-evals`)
- **§ 10 Trigger & Run Model** → model capacity, container resources
- **§ 11 Security/Compliance** → regulatory constraints, data retention

#### 1c. Read `AGENTS.md` and all skills (always)
Core deployment inputs:

1. **Which Foundry tools are needed** (from the "Foundry Tools Required" table)
2. **Which MCP servers are needed** (custom tools beyond built-ins)
3. **Storage strategy** (Cosmos via MCP, AI Search, Blob, etc.)
5. **Model requirements** (which model deployment, TPM needs)
6. **Skills list** (for SkillsProvider registration)

#### 1d. Choose runtime variant

| | **GHCP SDK (default)** | **MAF (fallback)** |
|--|----------------------|-------------------|
| **Runtime** | `CopilotClient` + `InvocationAgentServerHost` | `Agent` + `FoundryChatClient` + `ResponsesHostServer` |
| **Protocol** | Invocations (SSE streaming) | Responses |
| **Skill loading** | `SkillsProvider` (progressive) | `SkillsProvider.from_paths()` (progressive, recommended) **OR** `_load_skills()` concat (legacy) |
| **MCP** | `mcp_servers` parameter | `client.get_mcp_tool()` |
| **Custom `@tool`** | ❌ Not supported | ✅ Supported |
| **Foundry Toolbox** | ❌ Not available | ✅ `client.get_toolbox()` |
| **Tool loop timeout** | No limit (SSE keeps alive) | 120s gateway timeout |
| **Auth** | BYOK (`DefaultAzureCredential` → bearer token) | `DefaultAzureCredential` → `FoundryChatClient` |

**Decision rules:**
- **Default to GHCP** — preferred runtime, progressive skills, no timeout limits
- **Use MAF when**: agent needs Foundry Toolbox (web_search, code_interpreter) OR custom `@tool` functions OR **file generation** (save_report → XLSX/PDF/CSV)
- **Use MAF when**: agent primarily does data queries with fast MCP tools — MAF is 10-20x faster for these (19s vs 220s+). The 20-34 extra `load_skill`-shaped calls per query are **`CopilotClient` runtime overhead**, NOT `SkillsProvider` overhead — `SkillsProvider` itself only adds +1 `load_skill` per skill the agent activates per query, and works on both runtimes (see `foundry-hosted-agents` § Skill Loading)
- If the spec doesn't indicate either way → use GHCP

#### 1e. Choose model access pattern

| Pattern | When to Use | How |
|---------|------------|-----|
| **Direct deployment** (default) | You deploy the model in your own Foundry project | `azure.yaml` `config.deployments` — model created by `azd up` |
| **AI Gateway (APIM)** | Use an existing model on another Foundry resource, or a shared/governed model pool | `ApiManagement` connection in the Foundry project → APIM routes to backend AI Services |

**Use AI Gateway when:**
- Customer has existing model deployments they want to reuse
- A shared model pool is managed centrally (e.g., Citadel hub)
- Governance requires routing through APIM (logging, rate limiting, policies)
- You need models from a different Azure region or subscription

> **See `foundry-cross-resource` skill** for the full AI Gateway setup —
> APIM connection creation, `connectionName/deploymentName` pattern,
> Bicep for managed connections, and troubleshooting.

When using AI Gateway:
- **Remove** the model from `azure.yaml` `config.deployments` (it's already deployed elsewhere)
- Set `MODEL_DEPLOYMENT_NAME` in `agent.yaml` to `connectionName/deploymentName`
- Ensure the Foundry project has an `ApiManagement` connection to the APIM gateway
- **Use `authType: "AAD"` (recommended)** — no Key Vault needed. ApiKey auth requires a Key Vault on the project, which our Bicep scaffold doesn't create.
- Works with both GHCP SDK (BYOK) and MAF (FoundryChatClient) — routing is transparent

> **See `ghcp-hosted-agents` skill** for the full GHCP reference (container.py template,
> pyproject.toml, agent.yaml, invocation patterns, troubleshooting).
> **See `foundry-hosted-agents` skill** for the full MAF reference.

---

## Phase 2: Generate Deployment Artifacts

Create these files in the project root:

### 1. `src/agent/copilot-instructions.md` — Agent System Prompt

Transform AGENTS.md into a runtime system prompt:

```markdown
# {Agent Name}

{Purpose from AGENTS.md — 2-3 sentences}

## Behavioral Guidelines

{Copy behavioral guidelines from AGENTS.md}

## Available Tools

{List the MCP/built-in tools with usage guidance}

## Compliance

{Copy compliance constraints from AGENTS.md}
```

**Rules:**
- Keep it concise (500-1500 words) — this is injected every turn
- Remove deployment metadata, local dev info, tables that reference SKILL.md paths
- Focus on WHAT the agent should DO, not how it's implemented
- Include tool-use discipline directive (see reference)

### 2. `src/agent/skills/` Directory

Skills are generated directly by `threadlight-design` into `src/agent/skills/`.
No copying needed — deploy reads them in place.

```
skills/
├── scan-competitor-x/
│   └── SKILL.md
├── generate-report/
│   └── SKILL.md
└── detect-changes/
    └── SKILL.md
```

These are surfaced to the agent through `SkillsProvider` (recommended,
progressive disclosure) **or** loaded at startup by a `_load_skills()`
helper that appends them to instructions (legacy concat). See
`foundry-hosted-agents` § Skill Loading for the trade-off and a
production-tested defensive `_build_skills_provider()` helper.

### 3. `src/agent/mcp-config.json` — MCP Server Configuration

> **NOTE:** This config is used by the container runtime. At startup, `_load_mcp_config()`
> reads this file, expands `${ENV_VAR}` placeholders, and creates tools via `client.get_mcp_tool()`.

Map configured MCP servers for Foundry runtime (NOT local dev):

```json
{
  "servers": {
    "cosmos-tools": {
      "type": "http",
      "url": "${MCP_SERVER_URL}/mcp"
    }
  }
}
```

**Rules:**
- Use `${ENV_VAR}` placeholders — resolved at container start
- Remove local-only servers (Playwright MCP, local Azure MCP, stdio servers)
- Only include servers accessible from Foundry containers (remote HTTP endpoints)
- The runtime expands env vars automatically

**Foundry tool → runtime mapping:**

| Design Tool | Runtime | Notes |
|-------------|---------|-------|
| Browser Automation | **MCP ACA** — deploy Playwright as a remote MCP server | Local Playwright cannot run inside hosted agent containers. Use `npx @playwright/mcp` on ACA. |
| Web Search | **Foundry Toolbox** — `client.get_toolbox("toolbox-name")` | Built-in Toolbox tool type. No Bing resource needed. *MAF only.* |
| Code Interpreter | **Foundry Toolbox** — add `code_interpreter` to Toolbox | Computation and data processing. *MAF only.* |
| File Generation | **Custom `@tool`** — `save_report` writing to `$HOME` | XLSX (openpyxl), PDF (fpdf2), CSV/HTML (text). Downloadable via session files API + FileConsentCard in Teams. *MAF only.* See `foundry-hosted-agents` skill § File Generation. |
| **Knowledge sources (docs, policies, KB)** | **Foundry IQ** — Azure AI Search with agentic retrieval | For static/semi-static knowledge (policies, regulations, product docs). See `foundry-iq` skill. Creates Knowledge Base with query planning + citations. |
| **API data (dynamic, transactional)** | **MCP ACA** — custom or mock MCP server | For live data (CRM, orders, transactions). See `foundry-mcp-aca` skill. |
| **Cosmos DB** | **MCP ACA** — .NET MCPToolKit (10 tools out of the box) | See `foundry-mcp-aca` Option A. Deploy as `src/mcp/` or shared ACA. |
| Azure AI Search (direct) | Foundry Toolbox or custom MCP | Use Toolbox if available, or deploy custom MCP ACA |
| Custom data store | Custom MCP server (deploy as ACA or Azure Functions) | Proven pattern — see `foundry-mcp-aca` |

> **Knowledge vs API data:** Use the spec § 7 (Knowledge Sources) vs § 5 (System Integrations)
> distinction to choose:
> - **Knowledge sources** (documents, policies, search indexes) → **Foundry IQ** (agentic retrieval
>   with query planning, multi-hop reasoning, citations). See `foundry-iq` skill.
> - **API data** (CRM, ERP, transactional systems) → **MCP server** (mock or real).
>   See `foundry-mcp-aca` skill.
> - **Cosmos DB** → MCPToolKit as `src/mcp/` — provides 10 tools, deploy as ACA.

> **Key constraints for MAF hosted agents:**
>
> 1. **No local browser** — hosted agent containers are headless Python environments.
>    Deploy browser automation as a remote MCP server on ACA.
>
> 2. **Foundry Toolbox is the preferred tool source** — create a Toolbox with `web_search`
>    and/or `code_interpreter` tools. Load via `client.get_toolbox("name")` in container.py.
>    The Toolbox is an MCP endpoint managed by the platform — no infrastructure to deploy.
>
> 3. **Session files for report output** — custom `@tool` functions can write files to
>    `Path.home()` (agent's `$HOME`). Files persist across turns and are downloadable via
>    the session files API: `GET .../sessions/{sid}/files/content?path=filename`.

### Foundry Toolbox Setup

Create a Toolbox via REST API (or automate in a postprovision hook):

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
curl -X POST "$PROJECT_ENDPOINT/toolboxes/my-tools/versions?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: Toolboxes=V1Preview" \
  -d '{"tools":[{"type":"web_search","name":"web_search"},{"type":"code_interpreter","name":"code_interpreter"}]}'
```

In container.py, load as async:
```python
toolbox = await client.get_toolbox(os.environ["TOOLBOX_NAME"])
agent = Agent(client=client, tools=[mcp_tool, toolbox], ...)
```

### Content Filtering for Sensitive Domains

Agents in tobacco, pharma, weapons, or other regulated domains trigger Azure OpenAI's
default content filters (severity: `Medium`) on legitimate queries. Create a custom RAI
policy with `High` severity thresholds and apply to the model deployment:

```bash
# Create policy
az rest --method PUT \
  --url ".../raiPolicies/my-ci-policy?api-version=2025-10-01-preview" \
  --body '{"properties":{"mode":"Blocking","basePolicyName":"Microsoft.DefaultV2","contentFilters":[
    {"name":"Hate","blocking":true,"enabled":true,"severityThreshold":"High","source":"Prompt"},
    {"name":"Hate","blocking":true,"enabled":true,"severityThreshold":"High","source":"Completion"},
    {"name":"Violence","blocking":true,"enabled":true,"severityThreshold":"High","source":"Prompt"},
    {"name":"Violence","blocking":true,"enabled":true,"severityThreshold":"High","source":"Completion"},
    {"name":"Selfharm","blocking":true,"enabled":true,"severityThreshold":"High","source":"Prompt"},
    {"name":"Selfharm","blocking":true,"enabled":true,"severityThreshold":"High","source":"Completion"},
    {"name":"Jailbreak","blocking":true,"enabled":true,"source":"Prompt"}
  ]}}'

# Apply to deployment
echo '{"properties":{"raiPolicyName":"my-ci-policy"}}' > /tmp/rai.json
az rest --method PATCH \
  --url ".../deployments/gpt-5.4-mini?api-version=2026-03-15-preview" \
  --headers "Content-Type=application/json" --body @/tmp/rai.json
```

**Automate via postprovision hook** — add to `azure.yaml`:
```yaml
hooks:
    postprovision:
        shell: pwsh
        run: 'cd infra/scripts && uv sync --frozen --quiet && uv run postdeploy.py'
```

The hook script creates the Toolbox, RAI policy, and Teams manifest idempotently.

### 4. `src/agent/container.py` — Agent Runtime

Generate the container runtime based on the chosen variant (see Phase 1 § 1d).

#### GHCP SDK variant (default)

**Copy the reference template** from the `ghcp-hosted-agents` skill's
`references/container.py` and adapt:

- Model provider: BYOK with `DefaultAzureCredential` → bearer token
- Instructions: loaded from `copilot-instructions.md`
- Skills: loaded via `SkillsProvider` from `skills/` directory (progressive discovery)
- MCP: configured via `mcp_servers` parameter

The runtime uses `CopilotClient` + `InvocationAgentServerHost`:
1. `CopilotClient` with BYOK auth (DefaultAzureCredential → bearer token)
2. `SkillsProvider` reads `skills/` directory for progressive skill loading
3. MCP servers configured via `mcp_servers` parameter
4. `InvocationAgentServerHost` serves the Invocations protocol (SSE streaming)
5. Diagnostic HTTP server on import failure (keeps container alive for debugging)

#### MAF variant (when Toolbox or custom @tool needed)

**Copy the reference template** from the `foundry-hosted-agents` skill or
`references/container-runtime-template.py` and adapt:

The runtime uses `Agent` + `FoundryChatClient` + `ResponsesHostServer`:
1. `FoundryChatClient` with `DefaultAzureCredential` for Foundry auth
2. **Skill loading** — `SkillsProvider.from_paths(skills_dir)` wired via
   `context_providers=[skills_provider]` for progressive disclosure
   (recommended), **or** legacy `_load_skills()` that reads all SKILL.md
   files and appends to instructions. Pick one — never both. See
   `foundry-hosted-agents` § Skill Loading for the trade-off.
3. `_create_mcp_tools()` creates tools via `MCPStreamableHTTPTool` with a
   `parse_tool_results` extractor (avoids the [<Content>] repr leak)
4. `ResponsesHostServer(agent).run()` serves the Responses protocol
5. Diagnostic HTTP server on import failure

**Do NOT write the container runtime from scratch** — always start from the reference
template in the corresponding skill.

#### Custom Tools (Function Tools)

`Agent` accepts a `tools` parameter for custom Python functions the agent can invoke
at runtime. This is useful for capabilities not covered by MCP — e.g., API calls,
data lookups, or computations.

**Recommended approach — `@tool` decorator:**

```python
from agent_framework import tool
from typing import Annotated
from pydantic import Field

@tool(approval_mode="never_require")
def search_web(
    query: Annotated[str, Field(description="Search query")],
) -> str:
    """Search the web and return results."""
    # Call your search API here
    return "search results..."
```

**Pass to agent:**
```python
agent = Agent(
    client=client,
    instructions=instructions,
    tools=[search_web, mcp_tool_1],
    default_options={"store": False},
    # ...
)
```

**Constraints:**
- Both sync and async functions supported
- Use `Annotated[type, Field(description=...)]` for parameter documentation
- Tool results are returned as text to the LLM for reasoning

> **Tip:** Custom tools are a practical workaround for missing platform capabilities.
> For example, if you need web search but can't use MCP, define a custom tool that
> calls a search API (Tavily, SerpAPI, etc.) directly from Python.

### 5. `src/agent/pyproject.toml` — Python Dependencies

**Copy from `references/pyproject-template.toml`** and replace `__PROJECT_NAME__`:

```toml
[project]
name = "__PROJECT_NAME__-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "agent-framework-core==1.3.0",
    "agent-framework-foundry==1.3.0",
    "agent-framework-foundry-hosting>=1.0.0a260421",
    "azure-identity>=1.19.0,<1.26.0a0",
    "mcp>=1.10.0",
    "python-dotenv>=1.0.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"

[tool.setuptools]
packages = []
```

**CRITICAL: Uses `uv` (not `pip`)** — the `prerelease = "if-necessary-or-explicit"` setting
lets uv resolve prerelease packages that have explicit prerelease markers in their version
specs (e.g. `>=1.0.0a260421`), while keeping all other packages on GA (e.g. `azure-identity`
resolves to 1.25.3 GA, NOT 1.26.0b2 beta). Do NOT use `"allow"` — it pulls beta versions
of azure-identity and other packages unintentionally.

> **🛑 PROVEN-WORKING REFERENCE PINS**
>
> The recipe above is the validated working set. Earlier guidance recommended
> **open ranges** (`agent-framework-core>=1.0.0`) plus an explicit
> `azure-ai-agentserver-responses>=1.0.0b4` — that resolves to a stack uv
> accepts at install time but that crashes the container at first invocation,
> returning the opaque `server_error/model:""`.
>
> **Mandatory rules:**
> - **Pin** `agent-framework-core==1.3.0` and `agent-framework-foundry==1.3.0`. NOT open ranges.
> - **Drop** any explicit `azure-ai-agentserver-responses` line. Let `agent-framework-foundry-hosting`
>   pull its own pinned transitive (`==1.0.0b4` currently, but the right value for whatever
>   foundry-hosting wants).
> - **Add** explicit `mcp>=1.10.0`. `agent-framework-core 1.3.0` does NOT auto-pull it, and
>   `MCPStreamableHTTPTool` will fail at runtime without it.
> - **Include** `[tool.setuptools] packages = []` — uv needs it to resolve cleanly when
>   the project itself isn't installed (`uv sync --no-install-project`).
> - **Reference**: keep a canonical `src/agent/pyproject.toml` in each process repo
>   and diff against the validated working shape when in doubt.

> **⚠️ Dependency Pinning & Future Updates**
>
> The refreshed hosted agents preview (April 2026) uses these packages:
>
> | Package | Version | Type | Notes |
> |---------|---------|------|-------|
> | `agent-framework` | `>=1.1.0` | ✅ Stable | Meta-package; pulls in core + foundry + openai |
> | `agent-framework-foundry-hosting` | `>=1.0.0a260421` | ⚠️ Alpha | Bridge AF↔protocol; pins agentserver-core==2.0.0b2 + agentserver-responses==1.0.0b4 |
> | `azure-identity` | `>=1.19.0` | ✅ Stable | DefaultAzureCredential for Foundry auth |
>
> **When updating deps in the future:**
> 1. Check PyPI for new versions of `agent-framework-foundry-hosting`
> 2. Inspect its `Requires-Dist` metadata for pinned agentserver versions
> 3. Test locally first: `docker build --platform linux/amd64 -t test-agent .` then
>    `docker run --rm -p 8088:8088 --env-file .env test-agent` — check for import errors
> 4. Run the hosted agent smoke test (`test_hosted_agent.py`)
> 5. Update the pinned versions in BOTH `pyproject-template.toml` AND this SKILL.md code block

If the agent uses OpenTelemetry, add:
```
azure-monitor-opentelemetry>=1.6.4
opentelemetry-sdk>=1.27.0
```

### 6. `src/agent/Dockerfile` — Self-Contained Container

**Copy from `references/dockerfile-template`** and adapt:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Uses uv for dependency management (prerelease support for hosting package)
# Pin uv:0.7 — uv:latest (0.8+) resolves prereleases differently and may pick
# incompatible pre-built wheels. Validated working pin.
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project \
    && rm -rf /root/.cache

COPY container.py .
COPY copilot-instructions.md .
COPY skills/ skills/
COPY mcp-config.json .

EXPOSE 8088

CMD [".venv/bin/python", "container.py"]
```

**Key facts:**
- Self-contained — NO base image dependency, NO ACR reference
- Uses **uv** (not pip) for dependency management — `prerelease = "if-necessary-or-explicit"` in pyproject.toml
- Port 8088 is the standard Foundry agent port
- `azd deploy` builds the container remotely — no local Docker needed
- `--platform linux/amd64` only needed for local builds (Foundry runs AMD64)
- Entrypoint is `.venv/bin/python` (uv creates a virtualenv)
- ResponsesHostServer handles liveness probes natively — no HEALTHCHECK needed

### 7. `deploy-notes.md` — Deployment Guide

```markdown
# Deployment Guide

## Architecture

This agent deploys as a **Microsoft Foundry Hosted Agent** using the
`azd ai agent` extension. `azd up` handles everything declaratively.

```
┌─────────────────────────────────────────┐
│  Azure Resources (provisioned by Bicep)  │
│  ┌─────────────────────────────────┐    │
│  │  Foundry Platform                │    │
│  │  ┌───────────────────────────┐  │    │
│  │  │  Hosted Agent Container    │  │    │
│  │  │  - src/agent/container.py  │  │    │
│  │  │  - copilot-instructions.md │  │    │
│  │  │  - skills/                 │  │    │
│  │  └──────────┬────────────────┘  │    │
│  │             │                    │    │
│  │  ┌──────────▼────────────────┐  │    │
│  │  │  MCP ACA (if needed)       │  │    │
│  │  └───────────────────────────┘  │    │
│  └─────────────────────────────────┘    │
│                                          │
│  ┌─────────────────────────────────┐    │
│  │  Bot ACA (Teams integration)     │    │
│  │  - bot.py → Foundry Hosted Agent │    │
│  └──────────┬──────────────────────┘    │
│             │                            │
│  ┌──────────▼──────────────────────┐    │
│  │  Azure Bot Service + Teams       │    │
│  └──────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## Prerequisites

- Azure CLI (`az`) and Azure Developer CLI (`azd`) installed
- `azd ai agent` extension: `azd extension install azure.ai.agents` (≥0.1.30-preview)
- Azure subscription with Contributor + **Azure AI Project Manager** on Foundry project
- Set `AZURE_TENANT_ID` in azd env: `azd env set AZURE_TENANT_ID <your-tenant-id>`

> **Tenant hygiene before `azd up`.** If you work across multiple Azure
> tenants, set up per-tenant `AZURE_CONFIG_DIR` / `AZD_CONFIG_DIR` in
> the calling shell **first** — see the **`azure-tenant-isolation`**
> skill. Without isolation, an `azd up` here may silently deploy into
> whatever subscription another shell last `az account set` against.

> **`azd` has its own auth chain — `az login` is not enough.**
> `azd ai agent show`, `azd deploy`, and the rest of the `azd` family
> use **`AzureDeveloperCliCredential`**, which reads tokens from
> `$AZD_CONFIG_DIR/auth/` — completely separate from the `az` CLI
> token cache under `$AZURE_CONFIG_DIR`. Even with both env vars
> pointed at the same alias, an `az login --tenant <id>` does **NOT**
> satisfy `azd`. You must run **`azd auth login --tenant-id <id>`**
> in addition to `az login`. Symptoms when missed: `azd ai agent show`
> hangs or returns `ERROR: not logged in. Try running 'azd auth
> login'`, even though `az account show` works fine. This is the #2
> "what changed?" trap after the multi-sub gotcha — bake both into
> your shell startup script.
>
> Verified working sequence (per-shell, after the alias env vars are
> exported per `azure-tenant-isolation`):
>
> ```bash
> az login --tenant "$TENANT_ID"
> az account set --subscription "$DEFAULT_SUB"
> azd auth login --tenant-id "$TENANT_ID"   # NOT optional
> az account show --query "{tenant:tenantId, sub:name}" -o table
> ```

## Deploy Steps

1. **Deploy everything with one command:**
   ```bash
   azd env set AZURE_TENANT_ID <your-tenant-id>
   azd up
   ```
   The `azd ai agent` extension handles:
   - Provisions Azure resources (Foundry project, ACR, monitoring, Bot Service, ACA)
   - Deploys the model (declared in azure.yaml)
   - Builds the agent container remotely via ACR
   - Creates the hosted agent version in Foundry
   - **Auto-assigns `Azure AI User` to agent identity** (requires `Azure AI Project Manager` + `AZURE_TENANT_ID`)
   - Builds and deploys the Teams bot to ACA

2. **Test the agent:**
   ```bash
   azd ai agent invoke "Hello! What can you do?"
   ```
   Or open the Foundry portal → Agents → find your agent → Chat playground.

3. **If you get 401 errors after deploy:**
   The extension's postdeploy hook auto-assigns RBAC. If it failed (missing
   `AZURE_TENANT_ID`), manually assign roles — see Identity & RBAC reference.

4. **If the bot returns `server_error` in Teams:**
   Stale conversations from previous agent versions cause persistent `server_error`.
   Type `!reset` in the Teams chat, or the bot auto-retries with a fresh conversation.

5. **Grant deployer Cosmos data-plane RBAC for verification probes (mandatory if `cosmos-db` selected):**

   `azd up` grants the agent UAMI Cosmos data-plane access, but **NOT** the deployer
   principal. Every post-deploy verification probe — counting rows, inspecting
   `kyc-audit-log` to prove BR-XXX persistence, checking `kyc-cases` for stuck
   case_ids — fails `Forbidden — principal does not have RBAC permissions to
   perform action Microsoft.DocumentDB/databaseAccounts/readMetadata` until you
   manually grant it. **Verified across recent pilots.** Add this as the FIRST step
   of any post-deploy verification runbook:

   ```bash
   ME=$(az ad signed-in-user show --query id -o tsv)
   az cosmosdb sql role assignment create \
     -g "$AZURE_RESOURCE_GROUP" -a "$AZURE_COSMOS_ACCOUNT_NAME" \
     --role-definition-id 00000000-0000-0000-0000-000000000001 \
     --principal-id "$ME" --scope "/"
   sleep 25   # RBAC propagation
   ```

   Use role `00000000-0000-0000-0000-000000000001` = `Cosmos DB Built-in Data
   Reader` (read-only is sufficient for verification; for write probes use
   `00000000-0000-0000-0000-000000000002` = Data Contributor). For a permanent
   fix, add this to the `postdeploy.py` hook in `infra/scripts/`.

6. **Cosmos firewall pilot-posture (mandatory if `cosmos-db` selected) — see `foundry-mcp-aca` SKILL.md § "Cosmos firewall + ACA egress" for the full runbook.** Quick check:

   ```bash
   az cosmosdb show -g "$AZURE_RESOURCE_GROUP" -n "$AZURE_COSMOS_ACCOUNT_NAME" \
     --query "{publicNetAccess:publicNetworkAccess,ipRules:ipRules,bypass:networkAclBypass}" -o json
   ```

   If `publicNetAccess: Disabled` OR `ipRules: []` (and ACA-side writes are
   failing), apply the runbook from `foundry-mcp-aca`. The `azd-patterns`
   `cosmos-db.bicep` module defaults to `pilotPosture=true` to avoid this trap
   on fresh pilots; the `ipRules` array still needs the ACA egress IP added
   post-deploy (extracted from the `ca-*-cosmos-mcp-*` ACA logs).

## Bot Implementation Notes

> **See the `foundry-teams-bot` skill** for complete bot implementation — code patterns,
> file sending, user identity, Bicep wiring, re-provision safety, and troubleshooting.

Key rule: bot MUST use `get_openai_client(agent_name=...)` — NOT the old `agent_reference` pattern.

## Authentication

- **KEYLESS ONLY** — never use API keys for Azure services
- Each hosted agent gets a **dedicated Entra identity** at deploy time (platform-managed)
- `FoundryChatClient` / `CopilotClient` uses `DefaultAzureCredential` in the container
- **Shared UAMI for all other resources**: Bot ACA, MCP ACA, postprovision hooks, and
  any other deployed resource should share **one User-Assigned Managed Identity**:
  - Created by `infra/bot/uami.bicep` (or a shared `infra/identity/uami.bicep`)
  - Assigned to: Bot ACA, MCP ACA, and any other ACA/Function
  - `AZURE_CLIENT_ID` env var set on all ACAs pointing to the shared UAMI
  - RBAC: assign `Azure AI User` on Foundry account + project, `Cognitive Services OpenAI User`,
    plus any data-plane roles (Cosmos, Search, etc.) to this single UAMI
- **Azure AI Project Manager** role required at project scope to deploy

> **Why one shared UAMI?** Multiple system-assigned MIs mean multiple RBAC assignments
> to manage. A single shared UAMI simplifies RBAC, Bicep, and troubleshooting —
> one identity, one set of role assignments, one place to debug auth failures.

## Health Probes

`ResponsesHostServer` handles liveness and readiness probes natively — no custom
middleware needed.

## Monitoring & Telemetry

The Bicep scaffold creates Application Insights + Log Analytics workspace when
`ENABLE_MONITORING=true` (default). But you also need to **connect AppInsights to
the Foundry project** for eval telemetry and agent tracing to work.

### What the scaffold provides

- `infra/core/monitor/` — creates Application Insights + Log Analytics workspace
- `APPLICATIONINSIGHTS_CONNECTION_STRING` — **RESERVED by the platform** for hosted
  agents. Do NOT set it in agent.yaml — the platform injects it automatically.

### What you must do manually (or via postprovision hook)

1. **Create an AppInsights connection on the Foundry ACCOUNT (not project):**

   The Foundry **account** needs an `AppInsights` connection so that agent traces
   and eval telemetry appear in the Foundry portal. This is NOT automatic.

   > **Key details:**
   > - Category is `AppInsights` (NOT `ApplicationInsights`)
   > - Target is the **ARM resource ID** (NOT the connection string)
   > - Metadata must include `ApiType: Azure`
   > - Connection is at **account level**, not project level

   ```bash
   # Via Azure REST API
   ACCOUNT_SCOPE="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
   APPINSIGHTS_ARM_ID="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Insights/components/<appinsights>"

   az rest --method PUT \
     --url "${ACCOUNT_SCOPE}/connections/<connection-name>?api-version=2025-10-01-preview" \
     --body '{
       "properties": {
         "category": "AppInsights",
         "target": "'${APPINSIGHTS_ARM_ID}'",
         "authType": "AAD",
         "metadata": {
           "ApiType": "Azure"
         }
       }
     }'
   ```

2. **RBAC for telemetry — ALL identities need access:**

   | Identity | Role | Scope | Why |
   |----------|------|-------|-----|
   | **Agent instance identity** | `Monitoring Metrics Publisher` | Application Insights | Agent container writes telemetry |
   | **Agent blueprint identity** | `Monitoring Metrics Publisher` | Application Insights | Platform internal telemetry |
   | **Project managed identity** | `Log Analytics Data Reader` | Log Analytics workspace | Read telemetry for evaluations |
   | **Shared UAMI** (bot, MCP) | `Log Analytics Data Reader` | Log Analytics workspace | Postdeploy hooks read telemetry |

   Get agent identities from `azd ai agent show` → `instance_identity.principal_id`
   and `blueprint.principal_id`. Assign to both.

   ```bash
   APPINSIGHTS_ID="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Insights/components/<appinsights>"

   # Agent identities (both instance + blueprint) — WRITE telemetry
   az role assignment create --assignee <INSTANCE_PRINCIPAL_ID> --role "Monitoring Metrics Publisher" --scope $APPINSIGHTS_ID
   az role assignment create --assignee <BLUEPRINT_PRINCIPAL_ID> --role "Monitoring Metrics Publisher" --scope $APPINSIGHTS_ID

   # Project MI — READ telemetry for evals
   az role assignment create --assignee <PROJECT_MI_PRINCIPAL_ID> --role "Log Analytics Data Reader" --scope $LOG_ANALYTICS_ID
   ```

### OpenTelemetry in container (MANDATORY — guarded init only)

> **Why this is mandatory, not optional.** The platform's
> `APPLICATIONINSIGHTS_CONNECTION_STRING` auto-injection is
> **best-effort, not contractual** — it can silently fail (for example,
> in some regions: AppIn account-level connection persisted
> with `credentials: null` after AAD-rejected → ApiKey-silent-drop;
> platform never injected the env var). When it fails AND `container.py`
> calls raw `configure_azure_monitor()` at the top of `main()`, the SDK
> raises `ValueError`, the container exits before `ResponsesHostServer`
> binds, and Foundry returns `server_error`/`model:""` on every smoke —
> with ZERO telemetry to debug it (because telemetry init is what
> crashed). The agent itself is fine; only the unguarded init kills it.
>
> **Hosted-agent `container.py` MUST wrap the init defensively** —
> use `init_telemetry()` from `foundry-observability`'s
> `references/python/otel_init.py`, OR inline an 8-line equivalent
> that no-ops on missing env / SDK import / SDK raise. See the
> `foundry-observability` skill (gap rows O-011 / O-012) for the
> full forensic and reference helper.

Add to `pyproject.toml`:

```toml
azure-monitor-opentelemetry>=1.6.4
opentelemetry-sdk>=1.27.0
```

And initialize in `container.py` — **guarded helper, NOT raw call**:

```python
# At module top
import logging, os
logger = logging.getLogger(__name__)

def _init_telemetry() -> None:
    """Guarded telemetry init — never lets a missing/broken AppIn kill the container."""
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn:
        logger.info("APPIN connection string not set — telemetry disabled (agent functional)")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=conn)
    except Exception as exc:  # noqa: BLE001
        logger.warning("App Insights telemetry init skipped: %s (agent functional)", exc)

def main() -> None:
    _init_telemetry()           # FIRST line — guarded, never raises
    # ... rest of main() ...
```

> **Anti-pattern (will silently kill your PoC):**
> `configure_azure_monitor()` as the first line of `main()` with no
> try/except. Causes the entire PoC to fail on any telemetry-platform
> glitch. The agent works fine without telemetry — let it.

> **Note:** The platform attempts to inject `APPLICATIONINSIGHTS_CONNECTION_STRING`
> into hosted agent containers automatically (best-effort) — do NOT declare
> it in `agent.yaml`, it is reserved. `create_version` rejects it with
> `invalid_request_error` (request IDs are available in platform logs).

## Evaluations

> **See the `foundry-evals` skill** for the complete evaluation guide — two-phase
> invoke+score pattern, 6 built-in evaluators, RBAC for judge models, and score interpretation.

### Generated eval files

If `specs/SPEC.md` § 9 contains evaluation scenarios (S-XXX), generate:

#### `tests/eval_dataset.jsonl`

One line per scenario, derived from spec § 9:

```jsonl
{"id": "S-001", "query": "Process loan: credit score 780, income $120K, amount $50K", "expected": "Approved", "business_rules": ["BR-001", "BR-003"], "category": "happy-path"}
{"id": "S-002", "query": "Process loan: credit score 520", "expected": "Declined", "business_rules": ["BR-001"], "category": "negative"}
{"id": "S-003", "query": "Process loan: credit score 580, DTI 40%", "expected": "Sent to human review", "business_rules": ["BR-001", "BR-002"], "category": "boundary"}
```

Each line maps directly to a scenario row in the spec.

#### `tests/run_evals.py`

Invoke + score script using the `foundry-evals` two-phase pattern.
**MUST** include three Windows-survival defenses from day one — every
PoC that has skipped them has lost full eval batches mid-run (see
`foundry-evals` SKILL § "Eval scripts on Windows: cp1252 trap"):

1. **UTF-8 stdout wrap** so the agent's `→` / em-dashes don't crash
2. **`safe()` ASCII-strip** on every agent string before printing
3. **Incremental JSON writes** after each scenario, not at the end

```python
"""Run eval scenarios against the deployed agent.

Windows-survival defenses baked in (DO NOT REMOVE):
- UTF-8 stdout wrap so the agent's non-ASCII output cannot crash us
- safe() ASCII-strip when printing agent strings
- Incremental JSON writes so a mid-run crash keeps prior results
"""
import io, json, sys, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace", line_buffering=True)

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import APIError

PROJECT_ENDPOINT = "<from azd env>"
AGENT_NAME = "<from agent.yaml>"
RESULTS_PATH = Path("tests/eval-results.json")

def safe(s, n=None):
    if s is None:
        return ""
    if n:
        s = s[:n]
    return s.encode("ascii", errors="replace").decode("ascii")

project = AIProjectClient(endpoint=PROJECT_ENDPOINT,
                          credential=DefaultAzureCredential(),
                          allow_preview=True)
oai = project.get_openai_client(agent_name=AGENT_NAME)

dataset = [json.loads(line) for line in
           Path("tests/eval_dataset.jsonl").read_text(encoding="utf-8").splitlines()
           if line.strip()]

# Cold-start retry loop (foundry-evals warmup pattern)
for attempt in range(1, 5):
    try:
        w = oai.responses.create(input="Reply 'OK' if ready.", stream=False)
        if w.status == "completed":
            break
    except Exception as e:
        print(f"[warmup] attempt={attempt} EXC: {safe(str(e), 200)}")
    if attempt < 4:
        time.sleep(60)

results = []
RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

for item in dataset:
    sid = item["id"]
    print(f"--- {sid} [{item.get('category', '')}] ---")
    t0 = time.time()
    rec = {"id": sid, **item}
    try:
        r = oai.responses.create(input=item["query"], stream=False)
        elapsed = time.time() - t0
        out_text = ""
        for o in (r.output or []):
            for c in (getattr(o, "content", None) or []):
                t = getattr(c, "text", None)
                if t:
                    out_text += t.value if hasattr(t, "value") else str(t)
        rec.update({"status": r.status, "elapsed_s": round(elapsed, 1),
                    "response_id": r.id, "output_len": len(out_text),
                    "output_first_400": safe(out_text, 400)})
        print(f"  status={r.status} elapsed={elapsed:.1f}s")
        print(f"  output_first_400: {safe(out_text, 400)!r}")
    except APIError as e:
        rec.update({"status": "api_error", "code": e.code,
                    "elapsed_s": round(time.time() - t0, 1)})
    except Exception as e:
        rec.update({"status": "exception", "exc_type": type(e).__name__,
                    "exc_msg": safe(str(e), 300),
                    "elapsed_s": round(time.time() - t0, 1)})
    results.append(rec)
    # Write after EVERY scenario - mid-run crash keeps prior results
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    time.sleep(5)

print(f"\n{len(results)} scenarios invoked. Run foundry-evals to score.")
```

Run with `python -X utf8 tests/run_evals.py` (or set `PYTHONUTF8=1` /
`PYTHONIOENCODING=utf-8` in the parent shell) for a 4th defense layer.

#### `tests/invoke_agent.py`

Simple smoke test — invoke the deployed agent with a single message (already covered).

---

## Phase 3: Validate & Auto-Review (mandatory)

After generating all files, **walk through this checklist item by item**. Every
generated file must be accounted for. This is the single most important step —
if you skip it, broken or missing files ship to the user.

### Output Checklist

Check every file. Mark each ✅ or fix before presenting.

#### `src/agent/` — Hosted agent container
- [ ] `src/agent/container.py` — exists, matches chosen runtime (GHCP or MAF)
- [ ] `src/agent/Dockerfile` — uses `python:3.12-slim`, `uv sync`, copies all agent files
- [ ] `src/agent/pyproject.toml` — correct deps for chosen variant, `prerelease = "if-necessary-or-explicit"`
- [ ] `src/agent/copilot-instructions.md` — exists, 500-1500 words, matches AGENTS.md
- [ ] `src/agent/skills/` — has all skills from AGENTS.md, no extra, no missing
- [ ] `src/agent/config/` — process configuration from spec (if applicable)
- [ ] `src/agent/mcp-config.json` — only remote HTTP servers, includes mock MCP endpoints for mocked systems, no unresolved `${ENV_VAR}` placeholders
- [ ] `src/agent/agent.yaml` — copy of root `agent.yaml` (must be in both locations)

#### `src/mcp/` — MCP server (if mocked systems or Cosmos)
- [ ] `src/mcp/server.py` — tools match spec § 6 contracts for mocked systems
- [ ] `src/mcp/data/` — sample data copied from `specs/sample-data/`
- [ ] `src/mcp/Dockerfile` — builds and runs the MCP server
- [ ] `src/mcp/requirements.txt` — includes `fastmcp`
- [ ] *(Skip this section entirely if no mocked systems and no Cosmos)*

#### `src/bot/` — Teams bot (if Teams needed)
- [ ] `src/bot/bot.py` — uses `get_openai_client(agent_name=...)` (NOT `agent_reference`)
- [ ] `src/bot/app.py` — aiohttp server with MsalConnectionManager
- [ ] `src/bot/Dockerfile` — python:3.12-slim, port 80
- [ ] `src/bot/requirements.txt` — includes microsoft-agents-* + openai
- [ ] `src/bot/build_manifest.py` — replaces all manifest tokens; **MUST fail loudly** if `BOT_APP_ID` env var is missing or still a placeholder (e.g. `<uami-client-id>`) — silent fallback to a placeholder produces a zip that passes `azd deploy` but fails Teams schema validation at sideload time with `String "<uami-client-id>" does not match regex pattern`. Guard: `if not bot_id or bot_id.startswith("<"): raise SystemExit("BOT_APP_ID not set")`
- [ ] `src/bot/teams_package/manifest.json` — has `__BOT_APP_ID__` placeholder tokens ready for postprovision (NEVER literal `<uami-client-id>` — use double-underscore `__` tokens that are obviously wrong if leaked)
- [ ] **Bot ACA env block has ALL FOUR `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` vars** (CLIENTID, TENANTID, AUTHORITYENDPOINT, **AUTHTYPE=`UserManagedIdentity`**) — missing `AUTHTYPE` is a silent-killer bug: bot looks healthy from outside, JWT probe passes, every real Teams message returns HTTP 500 with AADSTS7000216. See `foundry-teams-bot` skill § Bicep snippet.
- [ ] **Bot Service `appType: UserAssignedMSI`** with `msaAppId` = UAMI clientId AND `msaAppMSIResourceId` = UAMI ARM ID
- [ ] *(Skip this section entirely if Teams not needed)*

#### Root config files (MUST be at repo root — azd requires this)

> **`agent.yaml` and `azure.yaml` stay at repo root**, NOT under `src/`.
> The `azd ai agent` extension and `azd` CLI look for them at the repo root.
> Only the *source code* (container.py, Dockerfile, skills, etc.) goes under `src/`.
> The `project: ./src/agent` field in `azure.yaml` tells azd where the Dockerfile is.
>
> **`agent.yaml` must ALSO be copied to `src/agent/`** — the extension reads it from
> root for agent creation, but the container build context needs it in the service dir
> for the hosted agent version to resolve correctly. Keep both in sync.

- [ ] `agent.yaml` — `kind: hosted` (top-level), protocols `1.0.0`, resources `{cpu, memory}`, NO `FOUNDRY_PROJECT_ENDPOINT`
- [ ] `azure.yaml` — `host: azure.ai.agent`, `project: ./src/agent`, model in `config.deployments`, `requiredVersions` for extension
- [ ] `azure.yaml` — if `src/mcp/` exists: MCP service declared with `host: containerapp`, `project: ./src/mcp`
- [ ] `deploy-notes.md` — references `azd up`, lists mock systems with swap instructions

#### `infra/` — Bicep scaffold
- [ ] `infra/main.bicep` — exists
- [ ] `infra/main.parameters.json` — `ENABLE_CAPABILITY_HOST=false`
- [ ] `infra/core/` — vendored modules present
- [ ] `infra/bot/` — present if Teams included, absent if not

#### `scripts/` — Hooks
- [ ] Postprovision/postdeploy hooks present if needed (Toolbox, RBAC, manifest)

#### `tests/` — Eval and smoke test
- [ ] `tests/invoke_agent.py` — smoke test script
- [ ] `tests/eval_dataset.jsonl` — one line per spec § 9 scenario (if spec exists)
- [ ] `tests/run_evals.py` — invoke+score script (if spec exists)

#### Global checks
- [ ] No secrets or API keys in any generated file
- [ ] No hardcoded local file paths
- [ ] Runtime variant (GHCP/MAF) consistent across container.py, pyproject.toml, Dockerfile
- [ ] All `__PLACEHOLDER__` tokens replaced with actual values
- [ ] Shared UAMI: one UAMI for bot + MCP ACA + hooks; `AZURE_CLIENT_ID` set on all ACAs
- [ ] AppInsights connection to Foundry project exists (or postprovision hook creates it)
- [ ] **`container.py` wraps telemetry init defensively** (no raw `configure_azure_monitor()` at module/main scope — use `_init_telemetry()` or `init_telemetry()` helper that no-ops on missing env / SDK import / SDK raise; see `foundry-observability` gap O-011)

#### SPEC § 11c module-selector cross-check (MANDATORY)

> **Use the consolidated `threadlight-safe-check` skill** for the
> mechanical implementation of this check (and Phase 3.5 below). The
> manual matrix below is preserved for documentation; the canonical
> automation is:
>
> ```bash
> python -m threadlight.safe_check --phase pre-deploy
> ```
>
> Wire it as an `azd hooks predeploy` so missing services abort the
> docker build before wasting an ACR push.

> **Why this exists.** A recent investigation-style PoC shipped
> with `infra/bot/aca.bicep`, `infra/bot/bot-service.bicep`, and a
> `src/workspace/index.html` ` but `azure.yaml` only declared two
> services (`agent` + `mcp`), `infra/main.bicep` only wired `mcpApp`,
> and the workspace had no `Dockerfile`. Result: SPEC § 11c said
> `aca-bot: yes` and `aca-job: yes`; deployment ended up with **0 bot
> resources, 0 jobs, 0 workspace ACAs** ` and the deploy still
> reported success. `threadlight-safe-check --phase pre-deploy` would
> have caught this.

For **every `yes` row** in SPEC § 11c, walk this matrix:

| Selector | Must exist in `azure.yaml` services | Must be referenced from `infra/main.bicep` | Must have source under `src/` |
|---|---|---|---|
| `aca-mcp` | `host: containerapp`, `project: ./src/mcp` | `module mcpApp '<host>/container-app.bicep'` | `src/mcp/Dockerfile` + `server.py` |
| `aca-bot` | `host: containerapp`, `project: ./src/bot` | `module botAca 'bot/aca.bicep'` AND `module botService 'bot/bot-service.bicep'` | `src/bot/Dockerfile` + `bot.py` + `app.py` + `teams_package/manifest.json` |
| `aca-job` | `host: containerapp.job` (or postdeploy `az containerapp job create`) | `module job 'jobs/aca-job.bicep'` (or `core/host/container-app-job.bicep`) | `src/jobs/<name>/Dockerfile` + `main.py` (cron entrypoint) |
| `workspace-ui` (SPEC § 8b non-empty) | `host: containerapp`, `project: ./src/workspace` | `module workspaceAca 'core/host/container-app.bicep'` | `src/workspace/Dockerfile` + ACA-served HTML/SPA. **NOT just a static `index.html` opened from `file://`** ` see `threadlight-workspace-ui` Hosting section |
| `foundry-iq-index` | n/a (provisioned by `postprovision` hook) | `module knowledge 'modules/ai-search.bicep'` (the index) | `scripts/postprovision.py` calls `provision_knowledge_base()` |

For **every `yes` selector**, all three columns MUST be checked. If any
is missing: **STOP**, fix the gap, do not proceed to `azd up`.

#### Bicep-module orphan check (MANDATORY)

For every `infra/<dir>/*.bicep` file in the repo, run:

```bash
# From repo root
for f in $(find infra -name '*.bicep' -not -path '*/core/*' -not -path '*/modules/*'); do
    base=$(basename "$f" .bicep)
    if ! grep -q "module .*'.*$base\.bicep'" infra/main.bicep; then
        echo "ORPHAN: $f is not referenced from infra/main.bicep"
    fi
done
```

Orphan modules confuse future readers ("is this needed? was the deploy
broken?"). Either **wire them in** or **delete them**. No middle
ground. A recent PoC carried orphan
`infra/bot/aca.bicep` and `infra/bot/bot-service.bicep` for an entire
deploy cycle ` they looked deployed when reading `infra/`, but
weren't.

#### `src/`-folder orphan check (MANDATORY)

Mirror of the above for source code. For every `src/<dir>/`:

| Source folder | Must be declared in `azure.yaml` services | Action if not |
|---|---|---|
| `src/agent/` | `host: azure.ai.agent` | required ` always present |
| `src/mcp/` | `host: containerapp` (named `mcp`) | wire it OR delete `src/mcp/` |
| `src/bot/` | `host: containerapp` (named `bot`) | wire it OR delete `src/bot/` |
| `src/workspace/` | `host: containerapp` (named `workspace`) **AND** must have `Dockerfile` | wire it OR explicitly mark in SPEC § 8b as "demo-only static page" with no ACA hosting |
| `src/jobs/<name>/` | `host: containerapp.job` (named `<name>`) OR postdeploy `az containerapp job create` | wire it OR delete |

Same rule: orphan source folders are a deploy bug. Either ship them or
remove them.

**If any check fails:** fix it before presenting. Do not leave broken artifacts.

---

## Phase 3.5: Post-deploy completeness gate (MANDATORY)

> **Canonical implementation: `threadlight-safe-check` skill.** Invoke as
> `python -m threadlight.safe_check --phase post-deploy` immediately after
> `azd up` returns 0 (and wire as `azd hooks postdeploy`). The detailed
> step-by-step below is preserved for understanding what the gate does;
> in practice run the consolidated CLI rather than reimplementing.

> **Why this is non-negotiable.** "PoC complete" is NOT the same as
> "`azd up` returned 0". It means **every Azure resource declared by
> SPEC § 11c is in `az resource list`, every channel declared by SPEC
> § 8 is reachable, and every scheduled job is running**. Without
> this gate, a recent PoC was reported "deployed
> and evaluated" with `aca-bot`, `aca-job`, and `workspace-ui` all
> silently missing. Run this gate **before** announcing success.

### Step 1 ` capture deployed state

```bash
# Make sure azure-tenant-isolation env vars are set first
RG=$(azd env get-value AZURE_RESOURCE_GROUP)
az resource list -g "$RG" \
   --query "[].{type:type, name:name}" -o json > tests/deployed-resources.json
az containerapp list -g "$RG" \
   --query "[].{name:name, fqdn:properties.configuration.ingress.fqdn, state:properties.runningStatus}" \
   -o json > tests/deployed-containerapps.json
az containerapp job list -g "$RG" \
   --query "[].{name:name, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" \
   -o json > tests/deployed-jobs.json
```

### Step 2 ` build expected list from SPEC

For every `yes` row in SPEC § 11c, look up the expected resource
type(s):

| Selector | Expected `Microsoft.*` resource types |
|---|---|
| `foundry-account` | `Microsoft.CognitiveServices/accounts` (account + nested project) |
| `cosmos-db` | `Microsoft.DocumentDB/databaseAccounts` |
| `ai-search` | `Microsoft.Search/searchServices` |
| `app-insights` | `Microsoft.Insights/components` + `Microsoft.OperationalInsights/workspaces` |
| `acr` | `Microsoft.ContainerRegistry/registries` |
| `uami` | `Microsoft.ManagedIdentity/userAssignedIdentities` |
| `aca-environment` | `Microsoft.App/managedEnvironments` |
| `aca-mcp` | `Microsoft.App/containerApps` (1 named `*-mcp-*` or `ca-mcp-*`) |
| `aca-bot` | `Microsoft.App/containerApps` (1 named `*-bot-*`) **AND** `Microsoft.BotService/botServices` |
| `aca-job` | `Microsoft.App/jobs` (1 per cron entry) |
| `workspace-ui` | `Microsoft.App/containerApps` (1 named `*-workspace-*` or `*-ui-*`) |
| `event-grid` | `Microsoft.EventGrid/topics` (or `systemTopics`) |
| `service-bus` | `Microsoft.ServiceBus/namespaces` |
| `key-vault` | `Microsoft.KeyVault/vaults` (only if explicitly `yes` ` keyless-by-default) |
| `storage-blob` | `Microsoft.Storage/storageAccounts` |
| `foundry-iq-index` | `Microsoft.Search/searchServices` (named `*-iq-*`) AND `azd env get-value FOUNDRY_IQ_KB_NAME` resolves |

### Step 3 ` diff and assert

```python
# tests/postdeploy_gate.py ` make this part of the deploy script.
import json, sys
from pathlib import Path

deployed = json.loads(Path("tests/deployed-resources.json").read_text())
deployed_types = {r["type"] for r in deployed}

# Build expected from SPEC § 11c. Hand-maintain this list per process,
# or read it from specs/manifest.json -> deployment_manifest.expected_resource_types
expected = {
    "Microsoft.CognitiveServices/accounts",
    "Microsoft.DocumentDB/databaseAccounts",
    "Microsoft.Search/searchServices",
    "Microsoft.App/managedEnvironments",
    "Microsoft.App/containerApps",     # mcp + bot + workspace
    "Microsoft.App/jobs",              # deadline-watcher cron
    "Microsoft.BotService/botServices",
    "Microsoft.ManagedIdentity/userAssignedIdentities",
    "Microsoft.ContainerRegistry/registries",
    "Microsoft.Insights/components",
}

missing = expected - deployed_types
if missing:
    print(f"GAP: missing resource types: {missing}")
    sys.exit(1)

# Per-app instance checks for the ACAs (counts matter ` 3 ACAs expected)
acas = json.loads(Path("tests/deployed-containerapps.json").read_text())
aca_names = {a["name"] for a in acas}
required_aca_patterns = {"mcp": False, "bot": False, "workspace": False}
for n in aca_names:
    for k in required_aca_patterns:
        if k in n.lower(): required_aca_patterns[k] = True
unmet = [k for k, v in required_aca_patterns.items() if not v]
if unmet:
    print(f"GAP: missing required ACA roles: {unmet}")
    sys.exit(1)

print("OK - post-deploy completeness gate passed")
```

### Step 4 ` channel reachability

For every Human Interaction channel in SPEC § 8, run a smoke check:

```bash
# Workspace UI ` HTTP 200 on the FQDN
WORKSPACE_FQDN=$(jq -r '.[] | select(.name | contains("workspace")) | .fqdn' tests/deployed-containerapps.json)
[ -n "$WORKSPACE_FQDN" ] && curl -fsSL "https://$WORKSPACE_FQDN/" -o /dev/null && echo "workspace OK"

# Bot ` ACA running + Bot Service registered
BOT_NAME=$(jq -r '.[] | select(.name | contains("bot")) | .name' tests/deployed-containerapps.json)
[ -n "$BOT_NAME" ] && az containerapp show -g "$RG" -n "$BOT_NAME" --query properties.runningStatus -o tsv

# Scheduled jobs ` cron expression matches SPEC § 10b
az containerapp job list -g "$RG" --query "[].{name:name, schedule:properties.configuration.scheduleTriggerConfig.cronExpression}" -o table
```

### Step 5 ` write the gate result

Persist `tests/postdeploy-manifest.json`:

```json
{
  "deployed_at": "2026-05-10T22:30:00Z",
  "rg": "rg-<your-process>-poc",
  "checked_selectors": ["foundry-account", "cosmos-db", "ai-search", "aca-mcp", "aca-bot", "aca-job", "workspace-ui"],
  "deployed_resources": ["` types ` "],
  "channels": [
    { "name": "Analyst Workspace", "fqdn": "ca-workspace-`.`.azurecontainerapps.io", "status": "OK" },
    { "name": "Teams adaptive card", "bot_name": "ca-bot-`", "status": "OK" }
  ],
  "scheduled_jobs": [
    { "name": "deadline-watcher", "schedule": "*/15 * * * *", "status": "OK" }
  ],
  "gaps": []
}
```

> **`gaps` MUST be empty for "PoC complete".** If non-empty, the
> deploy is incomplete ` either fix the gap (preferred) or update
> SPEC § 11c to flip the selector to `no` with a documented reason
> ("scheduled job deferred to v2"). Silently shipping with gaps is
> the failure mode this whole gate exists to prevent.

### Anti-pattern: "the agent runs in the portal so we're done"

The PoC is **NOT done** when:
- Only the hosted agent + 1 MCP ACA are deployed but SPEC § 11c
  declared more (`aca-bot`, `aca-job`, `workspace-ui`).
- The smoke probe / eval invokes the agent successfully but the
  agent's deployed surface area doesn't match SPEC § 8 channels.
- Bicep modules are present in `infra/` but not wired into
  `main.bicep` (orphans).
- Source folders exist under `src/` but aren't declared in
  `azure.yaml` services.
- `tests/postdeploy-manifest.json` doesn't exist or has non-empty
  `gaps[]`.

If any of the above is true, the PoC is partial. Communicate that
honestly to the user (with the gap list) instead of declaring
victory.

---

## Key Architecture Decisions

### Why Hosted Agents (not Prompt/Declarative)?

Prompt agents and Declarative agents run on Foundry's servers — no custom container.
They support platform-managed MCP tools via `MCPTool`. However, they CANNOT:

- Load skills dynamically via `SkillsProvider`
- Run custom ASGI middleware (normalise arguments, liveness probes)
- Inject runtime configuration into instructions (COSMOS_DATABASE, tool-use discipline)
- Execute complex multi-step orchestration with custom error handling

**Rule of thumb:** If the agent needs `SkillsProvider` or custom middleware → Hosted Agent.
If it's a simple Q&A agent with built-in tools → Prompt Agent is simpler.

### Why SkillsProvider instead of hardcoded instructions?

- **Progressive disclosure** — agent loads skills on-demand, not all at once
- **Smaller context** — instructions stay short; details load when needed
- **Modularity** — add/remove skills without changing copilot-instructions.md

### Why GHCP SDK (Default Runtime)?

- **No timeout**: Invocations protocol uses SSE — no 120s gateway timeout on long tool loops
- **Streaming**: SSE event stream for real-time output
- **Simpler MCP**: `mcp_servers` parameter vs manual `get_mcp_tool()` calls

> Note: progressive skill loading via `SkillsProvider` is **NOT** a GHCP-only
> feature — MAF supports it equally well. See `foundry-hosted-agents`
> § Skill Loading for the MAF wiring (`context_providers=[skills_provider]`).

### When to Use MAF Instead

- Agent needs **Foundry Toolbox** (`web_search`, `code_interpreter`) — only available via `client.get_toolbox()`
- Agent needs **custom `@tool` Python functions** — GHCP doesn't support them
- Agent needs **file generation** (`save_report` @tool → XLSX/PDF/CSV via session files API)
- Agent needs **Toolbox + MCP** in the same runtime
- Agent primarily does **data queries with fast MCP tools** — MAF is 10-20x faster because GHCP's `load_skill` overhead dominates (20-34 extra tool calls per query). Benchmark: MAF+gpt-5.4-mini = 19s vs GHCP+gpt-5.4-mini = 220s for the same data query.

### Tool-Use Discipline

The container runtime auto-injects a "Tool-Use Discipline" section into instructions.
This is CRITICAL for eval scores — without it, agents over-call tools
(list_databases, get_schema) on every turn, causing `tool_selection` failures
(30-50% instead of 80%+).

---

## Reference: Container Runtime Architecture

### GHCP SDK variant (default)

```
container.py (GHCP variant)
│
├── _load_instructions()
│   └── Read copilot-instructions.md
│
├── SkillsProvider(skills_directory="skills/")
│   └── Progressive skill loading on demand
│
├── CopilotClient(model_provider=BYOK, mcp_servers=[...])
│   └── DefaultAzureCredential → bearer token
│
└── InvocationAgentServerHost(agent).run()  →  port 8088 (SSE)
```

### MAF variant (fallback)

```
container.py (MAF variant)
│
├── _load_instructions()
│   └── Read copilot-instructions.md (+ config.json) — base prompt ONLY
│
├── Skill loading — pick ONE:
│   ├── (option A, recommended)
│   │     SkillsProvider.from_paths("skills/")
│   │     └── Progressive disclosure: advertise (~100 tok/skill) → load_skill on demand
│   └── (option B, legacy)
│         _load_skills()
│         └── Read skills/**/SKILL.md → append to instructions (concat at startup)
│
├── _load_mcp_config()
│   ├── Try /app/mcp-config.json (with ${ENV_VAR} expansion)
│   └── Fall back to MCP_SERVER_URL env var
│
├── FoundryChatClient(project_endpoint, model, credential)
│   └── DefaultAzureCredential — keyless auth to Foundry
│
├── _create_mcp_tools(client, config)
│   └── MCPStreamableHTTPTool(url, parse_tool_results=_extractor)
│
├── Agent(
│     client, instructions, tools,
│     context_providers=[skills_provider] if option A else [],
│     default_options={"store": False},
│   )
│
└── ResponsesHostServer(agent).run()  →  port 8088
```

---

## Reference: Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FOUNDRY_PROJECT_ENDPOINT` | ✅ (auto) | **RESERVED — platform injects automatically.** Do NOT declare in agent.yaml. Container reads via `os.environ`. |
| `AZURE_AI_PROJECT_ENDPOINT` | No | Alternative endpoint name (fallback in container.py) |
| `AZURE_CONTAINER_REGISTRY_ENDPOINT` | ✅ | ACR endpoint (set by azd from Bicep) |
| `AZURE_CLIENT_ID` | Bot only | UAMI client ID for bot (set in ACA env vars by Bicep) |
| `PROJECT_ENDPOINT` | Bot only | Project endpoint for bot (set in ACA env vars by Bicep) |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | ✅ | Model deployment name (declared in agent.yaml env_vars — user-defined, NOT reserved) |
| `MODEL_DEPLOYMENT_NAME` | No | Fallback model name (prefer AZURE_AI_MODEL_DEPLOYMENT_NAME) |
| `MCP_SERVER_URL` | No | Legacy single MCP server URL (prefer mcp-config.json) |
| `PORT` | No | Listen port (default: 8088) |

> **Reserved environment variables:** All `FOUNDRY_*` and `AGENT_*`
> prefixed variables are reserved by the platform. Do NOT declare them in
> `agent.yaml` `environment_variables` — the platform injects them automatically.
> Declaring them causes `invalid_payload` errors at `create_version` time.
>
> **Also reserved:** `APPLICATIONINSIGHTS_CONNECTION_STRING`.
> Even when the platform's auto-injection silently fails (see Gotchas table for
> the AppIn AAD-rejected / ApiKey-silent-drop trap), you CANNOT escape-hatch by
> setting it in `agent.yaml` — `create_version` fails immediately with
> `invalid_request_error`: "Environment variable
> 'APPLICATIONINSIGHTS_CONNECTION_STRING' is reserved for platform use" (request
> ID available in platform logs). The only safe path is a
> guarded `_init_telemetry()` in `container.py` so the agent runs even when AppIn
> is broken — see the OpenTelemetry section above.

---

## Reference: Identity & RBAC

> **See the `foundry-hosted-agents` skill** for the complete RBAC reference — identity model,
> required role assignments for deployer/project MI/agent identities, manual assignment
> commands, and RBAC propagation timing.

**Essential for deploy (quick reference):**
- Each hosted agent gets **two Entra identities** at deploy time (instance + blueprint)
- Both need `Azure AI User` on Foundry account AND project
- Deployer needs `Azure AI Project Manager` on the project
- Set `AZURE_TENANT_ID` in azd env for postdeploy RBAC auto-assignment
- RBAC propagation takes 5-15 minutes for new service principals

---

## Reference: Bicep Parameters (Refreshed Preview)

The scaffold's `infra/main.parameters.json` includes these critical parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `ENABLE_HOSTED_AGENTS` | `false` (set to `true` by extension preprovision hook) | Enables hosted agent infrastructure (ACR, agent capabilities) |
| `ENABLE_CAPABILITY_HOST` | **`false`** | **MUST be false for refreshed preview.** Capability hosts were removed — setting `true` causes provisioning errors. |
| `ENABLE_MONITORING` | `true` | Creates Application Insights + Log Analytics |
| `USE_EXISTING_AI_PROJECT` | `false` | Set `true` to point at existing Foundry project |

> **⚠️ `ENABLE_CAPABILITY_HOST=false` is mandatory.** The refreshed preview removed
> capability host creation. The old default was `true` (for initial preview). If your
> Bicep still defaults to `true`, provisioning will fail or create unnecessary resources.
>
> **⚠️ MIGRATION: Delete existing CapabilityHosts.** If the Foundry account had a previous
> initial preview deployment, an old CapabilityHost resource may still exist. Its presence
> blocks the refreshed preview API — you'll get `"The requested experience is not available
> for this subscription"` even with `ENABLE_CAPABILITY_HOST=false`. Delete it:
> ```bash
> az rest --method DELETE --url "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/capabilityHosts/agents?api-version=2025-10-01-preview"
> ```
> Deletion takes 2-5 minutes. Also remove the `capabilityHosts` resource from `ai-project.bicep`.

### Region Availability

Not all regions support hosted agents. If you get `"The requested experience is not
available for this subscription"` during `azd deploy`, try a different region.

**Known working regions (April 2026):** `northcentralus`, `eastus`, `swedencentral`, `canadacentral`, `australiaeast`
**Known failing regions:** `eastus2` (returned "experience not available" in testing)

> Always check [Region availability](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#region-availability)
> for the latest supported regions.

---

## Reference: MCP ACA Deployment

> **See the dedicated `foundry-mcp-aca` skill** for full details on deploying MCP servers
> as Azure Container Apps or Azure Functions — including Cosmos DB MCPToolKit, Playwright MCP,
> protocol requirements, Bicep modules, and authentication patterns.

### Mock Systems → Mock MCP Server

For systems marked **mock** in the spec, generate a mock MCP server using
`foundry-mcp-aca` Option D (Mock MCP). This ensures the demo agent has callable
tools backed by sample data — the customer sees real MCP tool calls.

For systems using **Cosmos DB**, generate a Cosmos MCPToolKit deployment using
`foundry-mcp-aca` Option A — provides 10 tools out of the box.

1. Run the `foundry-mcp-aca` skill to generate `src/mcp/` from spec tool contracts
2. Deploy to ACA (or run locally for dev)
3. Wire the endpoint into `src/agent/mcp-config.json`:

```json
{
  "servers": {
    "mock-tools": {
      "type": "http",
      "url": "${MOCK_MCP_URL}/mcp"
    }
  }
}
```

4. Add to `deploy-notes.md`:

```
📎 Mock Systems (demo data — swap when onboarding):
  - {system-name}: mock MCP at ${MOCK_MCP_URL}
    → See foundry-mcp-aca skill to deploy real MCP when system is accessible.
    → Tool contracts stay the same — only the endpoint URL changes.
```

---

## Reference: Static-Site Showroom Deploy (nginx ACA + Easy Auth)

> **When to use.** A **static showroom** (lobby + catalog + cinematic process
> walkthroughs) is a classic adjacent need to a hosted-agent pilot — the
> seller wants a single URL to put on a slide that gates by Entra ID.
> Same `azure-tenant-isolation` discipline, same `acme-shared` ACR, same
> Communication Blue brand bar — but the **runtime is nginx, not an agent**,
> and the **2-phase Easy Auth wiring** below is non-negotiable. This is
> NOT modeled in SPEC § 11c (it's not a per-process agent repo); ship it
> as a sibling `infra/` folder with the static HTML.

### The chicken-and-egg problem

ACA `secrets[].keyVaultUrl` references are validated at **provisioning
time**, not at runtime. So you cannot do this in one Bicep deploy:

```
1. Create KV
2. Create ACA app with secrets:[{ name: 'easyauth-client-secret',
                                  keyVaultUrl: '<kv>/secrets/easyauth-client-secret',
                                  identity: <uami> }]
3. Mint AAD client secret (needs the ACA FQDN as redirect URI…)
4. Write secret to KV
```

Step 2 fails: KV secret doesn't exist yet → `unable to fetch secret`.
Reordering doesn't help — the AAD client secret needs the ACA FQDN to
register the redirect URI, which needs the ACA created first.

### The fix: 2-phase Bicep with `wireAuth` toggle

Add a single `bool` param to your Bicep module and gate two things on it:

```bicep
// infra/modules/site.bicep
@description('Phase 2 toggle: when true, wires the ACA secret reference + Easy Auth. Phase 1 = false.')
param wireAuth bool = false

// ... UAMI, KV, role assignments, ACA env all unconditional ...

resource site 'Microsoft.App/containerApps@2024-10-02-preview' = {
  name: 'showroom-site'
  // ...
  properties: {
    configuration: {
      // GATED: empty array on phase 1, real reference on phase 2
      secrets: wireAuth ? [
        {
          name: 'easyauth-client-secret'
          keyVaultUrl: '${kv.properties.vaultUri}secrets/easyauth-client-secret'
          identity: uami.id
        }
      ] : []
      ingress: { external: true, targetPort: 80 /* ... */ }
      registries: [{ server: '${acrName}.azurecr.io', identity: uami.id }]
    }
    template: {
      containers: [{
        image: imageRef
        name: 'site'
        resources: { cpu: json('0.5'), memory: '1Gi' }
        probes: [
          { type: 'Liveness',  httpGet: { path: '/healthz', port: 80 } }
          { type: 'Readiness', httpGet: { path: '/healthz', port: 80 } }
        ]
      }]
      scale: { minReplicas: 1, maxReplicas: 5 /* ... */ }
    }
  }
}

// GATED: only created on phase 2
resource auth 'Microsoft.App/containerApps/authConfigs@2024-10-02-preview' = if (wireAuth) {
  parent: site
  name: 'current'                // MUST be literal 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: easyAuthClientId
          clientSecretSettingName: 'easyauth-client-secret'
          openIdIssuer: 'https://sts.windows.net/${tenant().tenantId}/v2.0'
        }
        validation: { allowedAudiences: easyAuthAllowedAudiences }
      }
    }
    login: { tokenStore: { enabled: true } }
  }
}
```

### deploy.ps1 orchestration (canonical)

```powershell
# Phase 1: foundation (KV, UAMI, RBAC, ACA env, ACA app — NO auth)
az deployment sub create --name "site-p1-$ts" --location $Location `
    --template-file infra/main.bicep `
    --parameters wireAuth=false imageRef=$imageRef <other-params>

# Between phases: grant Secrets Officer + mint + write secret
az role assignment create --assignee-object-id $deployerOid `
    --assignee-principal-type User --role 'Key Vault Secrets Officer' `
    --scope "/subscriptions/$subId/resourceGroups/$rg/providers/Microsoft.KeyVault/vaults/$kvName"
Start-Sleep 30  # RBAC propagation — non-negotiable

$cred = az ad app credential reset --id $clientId `
    --display-name 'showroom-site' --append `
    --end-date (Get-Date).AddMonths(12).ToString('yyyy-MM-ddTHH:mm:ssZ') `
    -o json | ConvertFrom-Json
az keyvault secret set --vault-name $kvName --name easyauth-client-secret `
    --value $cred.password --output none

# Phase 2: re-deploy with auth wired
az deployment sub create --name "site-p2-$ts" --location $Location `
    --template-file infra/main.bicep `
    --parameters wireAuth=true imageRef=$imageRef <other-params>

# Post: register redirect URI (idempotent)
$existing = az ad app show --id $clientId --query 'web.redirectUris' -o json | ConvertFrom-Json
$redirectUri = "https://$siteFqdn/.auth/login/aad/callback"
if ($existing -notcontains $redirectUri) {
    $merged = @($existing + $redirectUri | Select-Object -Unique)
    az ad app update --id $clientId --web-redirect-uris @merged --output none
}
```

### Smoke test the gate (3 expected behaviours)

```powershell
$url = "https://$siteFqdn"
# HEAD: 401 with WWW-Authenticate Bearer + correct authorization_uri (tenant + client_id)
curl -sI $url
# GET (browser-like): 302 → login.windows.net/<tenant>/oauth2/v2.0/authorize?...client_id=<appId>...
curl -s -o NUL -w "HTTP %{http_code} → %{redirect_url}\n" -A "Mozilla/5.0" $url
# GET /healthz: also gated (no path exclusions by default) → 401/302
```

### nginx Dockerfile + nginx.conf (canonical static-site shape)

`Dockerfile`:
```dockerfile
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY . /usr/share/nginx/html/
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf \
 && chown -R nginx:nginx /usr/share/nginx/html
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz || exit 1
```

`nginx.conf`:
```nginx
server {
    listen 80;
    server_tokens off;
    gzip on; gzip_types text/css application/javascript image/svg+xml;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    location = /healthz { return 200 'ok\n'; add_header Content-Type text/plain; }

    location ~* \.(html?)$ { add_header Cache-Control "public, max-age=300"; }
    location ~* \.(css|js|png|jpe?g|svg|woff2?)$ { add_header Cache-Control "public, max-age=2592000, immutable"; }

    root /usr/share/nginx/html;
    index index.html;
    # NO SPA fallback — multi-page site, 404 should 404
}
```

`.dockerignore` (deny-list — ACR Tasks uploads everything but `COPY .` honors this):
```
.git/
infra/
docs/
00-research/
**/*.md
**/.vscode/
deploy.ps1
```

### Anti-patterns

- ❌ Single Bicep deploy with `secrets:` reference + `authConfigs` + post-deploy KV write → ACA fails to provision
- ❌ Hard-coding role GUIDs (typo Bicep deploys without erroring then fails at role-assignment provisioning) — always look up via `az role definition list --name '<role>' --query '[0].name' -o tsv`
- ❌ `az rest --headers Content-Type=application/json` for redirect URI updates (Windows CLI parses `--headers` inconsistently) — use `az ad app update --web-redirect-uris …` instead
- ❌ `az ad app credential reset` without `--append` (replaces ALL existing secrets — disrupts every other ACA app sharing the same app reg)
- ❌ Forgetting `Start-Sleep 30` after `az role assignment create` for KV Secrets Officer (RBAC propagation is real and `keyvault secret set` will return 403 if you race it)

---

## Reference: SDK Deployment (via `azd ai agent` Extension)

The `azd ai agent` extension (`azure.ai.agents >= 0.1.0-preview`) handles hosted agent
deployment declaratively. No custom deploy scripts are needed.

### How it works

1. **azure.yaml** declares `host: azure.ai.agent` for the agent service
2. **Model deployments** are declared in `config.deployments` (not in Bicep)
3. **Pre-provision hooks** set env vars: `ENABLE_HOSTED_AGENTS`, `AI_PROJECT_DEPLOYMENTS`
4. **azd up** runs: provision → deploy model → build container (ACR remote) → create agent

```yaml
# azure.yaml — agent + MCP service declaration
services:
  my-agent:
    project: ./src/agent
    host: azure.ai.agent
    language: docker
    docker:
      remoteBuild: true
    config:
      container:
        resources:
          cpu: "1"
          memory: 2Gi
      deployments:
        - model:
            format: OpenAI
            name: gpt-5.4-mini
            version: "2026-03-17"
          name: gpt-5.4-mini
          sku:
            capacity: 120
            name: GlobalStandard

  # MCP server as ACA (if src/mcp/ exists — mock or Cosmos)
  mcp:
    project: ./src/mcp
    host: containerapp
    language: python
    docker:
      path: ./src/mcp/Dockerfile
      context: ./src/mcp
      remoteBuild: true
```

> **If `src/mcp/` exists**, the MCP ACA service MUST be in azure.yaml — otherwise
> `azd up` won't build or deploy it and the agent has no MCP tools at runtime.
> Set `MCP_SERVER_FQDN` in agent.yaml env vars to `${SERVICE_MCP_FQDN}` (azd
> resolves this to the deployed ACA's FQDN after provisioning).
>
> **MCP ACA also needs:**
> - Shared UAMI assigned (for `DefaultAzureCredential` inside the MCP server)
> - `AcrPull` role on the ACR for the UAMI (so ACA can pull the container image)
> - `minReplicas: 1` in Bicep (cold start from scale-to-0 adds 200-500s latency)

### Install the extension

```bash
azd extension install azure.ai.agents
```

### Manual agent deployment (alternative)

If not using the extension, you can deploy manually using the Foundry SDK:

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    HostedAgentDefinition,
    ProtocolVersionRecord,
    AgentProtocol,
)
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = AIProjectClient(endpoint=endpoint, credential=credential, allow_preview=True)

definition = HostedAgentDefinition(
    container_protocol_versions=[
        ProtocolVersionRecord(
            protocol=AgentProtocol.RESPONSES,
            version="1.0.0",
        )
    ],
    cpu="1",
    memory="2Gi",
    image=f"<acr>.azurecr.io/<agent>:{unix_timestamp}",
    environment_variables={
        # NOTE: FOUNDRY_PROJECT_ENDPOINT is RESERVED — platform auto-injects it
        "AZURE_AI_PROJECT_ENDPOINT": "https://...",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": "gpt-5.4",  # default for production agents; gpt-5.4-mini only for trivial 1-2-step flows
    },
)

version = client.agents.create_version(
    agent_name="agent-my-process",
    definition=definition,
    metadata={"enableVnextExperience": "true"},
)
```

> **Image tags MUST be unique** (use unix timestamp). Foundry deduplicates
> `create_version` when the tag matches a previous version.
> **`metadata={"enableVnextExperience": "true"}`** is required for the refreshed preview.

---

## Phase 4: Teams Bot (optional)

> **See the `foundry-teams-bot` skill** for complete Teams integration — bot.py, app.py,
> Dockerfile, Bicep modules (UAMI, Bot Service, ACA), Teams manifest, and sideloading.

Teams integration is **optional** — only include it if:
- The spec's § 8 Human Interaction Points specifies Teams as a channel
- The user explicitly asks for Teams exposure
- The `specs/manifest.json` includes conversational interaction traits

If included, the scaffold adds `copilot/` (bot code) and `infra/bot/` (Bicep) to
the azd project. The `foundry-teams-bot` skill's `templates/` directory provides
ready-to-copy files.

> **MANDATORY: start from `bot-streaming.py`, not `bot.py`.** The default
> bot template MUST be the streaming variant (`foundry-teams-bot/templates/copilot/bot-streaming.py`).
> The non-streaming variant (`bot.py`) is **legacy/fallback only** — it
> collects all SSE chunks into a list and sends one big `send_activity()`
> at the end. Result: 60+ seconds of typing-dots silence in Teams,
> followed by a wall of text. Bad UX, makes the demo feel broken.
>
> The streaming variant uses `StreamingResponse` from
> `microsoft_agents.hosting.core.app.streaming.streaming_response` —
> `queue_informative_update()` shows interim status, `queue_text_chunk()`
> streams text progressively, `await end_stream()` finalises. Degrades
> gracefully on non-streaming channels (DirectLine, web chat).
>
> Origin: recent pilot retrospective — bot deployed without streaming;
> user got 60s silence + wall-of-text and thought the bot was broken.
> The streaming refactor is ~30 LOC. There is no reason to ship the
> collect-then-send variant for a Teams pilot.

**If the agent generates files** (XLSX/PDF reports via `save_report` @tool):
- Add `"supportsFiles": true` to the manifest bot config
- The bot must implement the full FileConsentCard flow (see `foundry-teams-bot` skill § Sending Files to Teams)
- The bot captures `agent_session_id` from `response.completed`, lists/downloads files from the session files API, then sends FileConsentCard → invoke handler → OneDrive upload → FileInfoCard

---

## Phase 5: Generate azd Project (Extension-Based Scaffold)

Generate a complete `azd up`-ready project using the **`azd ai agent` extension**
(`azure.ai.agents >= 0.1.0-preview`). The extension handles container build, model
deployment, and hosted agent creation declaratively — no custom deploy scripts needed.

The scaffold uses **vendored Bicep modules** from the official
[azd-ai-starter-basic](https://github.com/Azure-Samples/azd-ai-starter-basic)
template. This ensures correct resource structure for the extension while remaining
self-contained (no network dependency on the template repo).

### Step 1: Copy the scaffold

Copy the **entire** `references/scaffold/` directory into the project root.
This adds:

```
project/
├── agent.yaml                # Agent definition (ContainerAgent schema)
├── azure.yaml                # azd config — extension declares agent + bot services
├── src/
│   ├── agent/                # Phase 2 files go here
│   │   ├── container.py
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── copilot-instructions.md
│   │   ├── skills/
│   │   ├── config/
│   │   └── mcp-config.json
│   │
│   ├── mcp/                  # Mock/Cosmos MCP server (if needed)
│   │   ├── server.py
│   │   ├── data/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── bot/                  # Teams bot (optional)
│       ├── bot.py
│       ├── app.py
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── build_manifest.py # Builds copilot_package.zip for sideloading
│       └── teams_package/
│           ├── manifest.json
│           ├── color.png
│           └── outline.png
│
├── infra/
│   ├── main.bicep
│   ├── main.parameters.json
│   ├── abbreviations.json
│   ├── bot/                  # Teams bot infrastructure (optional)
│   │   ├── uami.bicep
│   │   ├── aca.bicep
│   │   ├── bot-service.bicep
│   │   └── fetch-container-image.bicep
│   └── core/                 # Vendored from azd-ai-starter-basic (DO NOT MODIFY)
│       ├── ai/
│       ├── host/
│       ├── monitor/
│       ├── search/
│       └── storage/
│
├── scripts/                # Infra hooks only (postprovision, postdeploy)
│
└── src/bot/                # build_manifest.py lives with bot code
```

### Step 2: Replace placeholder tokens

Replace these tokens **in all copied files**:

| Token | Value | Source | Files |
|-------|-------|--------|-------|
| `__PROJECT_NAME__` | kebab-case agent name (e.g., `tech-news-digest`) | AGENTS.md | `agent.yaml`, `azure.yaml`, `src/bot/bot.py`, `pyproject.toml` |
| `__AGENT_DESCRIPTION__` | One-line agent description | AGENTS.md | `agent.yaml` |
| `__AGENT_NAME__` | Display name (e.g., `Tech News Digest`) | AGENTS.md | `infra/bot/bot-service.bicep` |
| `__MODEL_NAME__` | Model name (default: `gpt-5.4`) | AGENTS.md or default | `azure.yaml` |
| `__MODEL_DEPLOYMENT_NAME__` | Model deployment name (default: same as `__MODEL_NAME__`) | AGENTS.md or default | `agent.yaml` |
| `__MODEL_VERSION__` | Model version — **must match model name** (see lookup table below) | Azure model catalog | `azure.yaml` |
| `__MODEL_CAPACITY__` | TPM capacity (default: `120`) | Default | `azure.yaml` |
| `__DEVELOPER_NAME__` | Developer/org name for Teams manifest | User/org | `src/bot/teams_package/manifest.json` |
| `__BOT_APP_ID__` | UAMI client ID for bot (replaced at postprovision) | Bicep output | `src/bot/teams_package/manifest.json` |

> **⚠️ `__BOT_APP_ID__` silent-placeholder trap.** The postprovision hook runs
> `build_manifest.py` which reads `BOT_APP_ID` from the environment. `azd`
> injects Bicep outputs as env vars during hooks, so this works during `azd up`.
> But if anyone runs the script **manually** (e.g., `python scripts/build_manifest.py`
> without first exporting the var), a silent fallback like `os.environ.get("BOT_APP_ID",
> "<uami-client-id>")` produces a manifest that:
> - Passes `azd deploy` without error (the zip is valid, just has wrong IDs)
> - Fails at Teams sideload with: `String "<uami-client-id>" does not match regex
>   pattern "^[0-9a-fA-F]{8}-..."` on `id`, `copilotAgents[0].id`, and `bots[0].botId`
>
> **Fix:** `build_manifest.py` MUST raise `SystemExit` if `BOT_APP_ID` is empty or
> starts with `<`. Never use a human-readable fallback for UUID fields — use
> `00000000-0000-0000-0000-000000000000` if you must have a default (it's obviously
> wrong but passes the regex), or better, just fail.

> **Note**: Model deployment is now declared in `azure.yaml` `config.deployments` —
> NOT in Bicep. The `azd ai agent` extension handles model creation via pre-provision hooks.

#### Model Version Lookup

> **See the `foundry-hosted-agents` skill** for the complete model version lookup table.

Verify with: `az cognitiveservices account list-models --resource-group <rg> --name <account> -o table`

### Step 3: Generate `deploy-notes.md`

Generate the deployment guide using the template in Phase 2 § 7, replacing
`{Agent Name}` with the actual agent display name.

### How `azd up` works with the extension

```
azd up
  ├── azd provision → Bicep creates Azure resources
  │   ├── Foundry AI Account + Project (core/ai/ai-project.bicep)
  │   ├── Azure Container Registry (created by ai-project when hosted agents enabled)
  │   ├── Application Insights + Log Analytics (core/monitor/)
  │   ├── UAMI for bot (bot/uami.bicep)
  │   ├── ACA Environment + Bot Container App (bot/aca.bicep)
  │   └── Azure Bot Service + MsTeamsChannel (bot/bot-service.bicep)
  │
  ├── postprovision hook → builds Teams manifest package
  │   └── scripts/build_manifest.py → src/bot/copilot_package.zip
  │
  ├── azd ai agent extension (automatic) →
  │   ├── Deploys model from azure.yaml config.deployments
  │   ├── Builds agent container remotely via ACR
  │   └── Creates hosted agent version in Foundry
  │
  └── azd deploy → builds other containers, deploys to ACA
      ├── Builds src/mcp/ container via ACR (if MCP service declared)
      ├── Builds src/bot/ container via ACR (if bot service declared)
      └── Deploys to ACA (external ingress)
```

### Complete output structure

After all phases, the project should contain:

```
project/                    # ← REPO ROOT
├── AGENTS.md               # Original design (unchanged)
├── specs/                   # SpecKit (from threadlight-design, unchanged)
│
├── agent.yaml              # ⚠️ MUST be at root AND copied to src/agent/
├── azure.yaml              # ⚠️ MUST be at root — azd reads this
│
├── src/
│   ├── agent/              # Hosted agent container
│   │   ├── container.py    # Runtime (GHCP default or MAF fallback)
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── copilot-instructions.md
│   │   ├── skills/         # Process skills
│   │   ├── config/         # Process configuration
│   │   └── mcp-config.json # Runtime MCP config
│   │
│   ├── mcp/                # Mock/custom MCP server (if mocked systems or Cosmos)
│   │   ├── server.py       # FastMCP tools backed by sample data
│   │   ├── data/           # Copied from specs/sample-data/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   └── bot/                # Teams bot (optional)
│       ├── bot.py
│       ├── app.py
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── build_manifest.py  # Builds copilot_package.zip
│       └── teams_package/  # Manifest + icons
│
├── infra/                  # Bicep scaffold
│   ├── main.bicep
│   ├── main.parameters.json
│   ├── core/               # Vendored from azd-ai-starter-basic
│   └── bot/                # Bot infra (optional)
│
├── scripts/                # Infra hooks only (postprovision, postdeploy)
│
├── tests/                  # Test/invocation scripts
│   └── invoke_agent.py     # Smoke test — invoke deployed agent
│
└── deploy-notes.md         # Deployment guide
```

---

## Phase 6: Module Composer (Bicep) — read SPEC § 11c, include exactly the right modules

Phase 5 above bootstraps the agent / azd skeleton. Phase 6 wires the
**process-specific infrastructure** by reading SPEC § 11c (Tech Stack module
selectors) and composing only the modules that process actually needs.

### Why a composer (not one big main.bicep)

Each of the 13 catalog processes uses a different mix of services:
- KYC needs `cosmos + search + foundry-iq + doc-intel + speech` (no event-grid)
- Order Fallout needs `cosmos + service-bus + aca-job + aca-mcp` (no doc-intel/speech)
- Supplier Risk needs `cosmos + foundry-iq + event-grid + storage-blob`

A monolithic `main.bicep` would be 70% `if` blocks. The composer pattern
includes **only the modules SPEC § 11c explicitly selects**, plus the
always-on baseline (`uami` + `acr` + `app-insights` + `foundry-account`).

### Step 1 — Read SPEC § 11c

The spec writes § 11c as the **canonical kebab-case selector table**
defined in `threadlight-design/references/speckit-template.md` § 11c.
Phase 6 reads that table verbatim — the rows are the source of truth
for module inclusion. Example excerpt:

```markdown
| Module             | Selected? | Purpose in this process                          |
| `cosmos-db`        | yes       | Persistent case state, audit log                 |
| `ai-search`        | yes       | Foundry IQ Knowledge Base backing                |
| `foundry-iq-index` | yes       | KB: kyc-policies (sources: blob/policies/kyc/)   |
| `azure-vision`     | yes       | Damage-photo classification                       |
| `aca-job`          | yes       | sla-watcher cron `*/15 * * * *`                  |
| `aca-mcp`          | yes       | customer-data MCP                                |
| `aca-bot`          | yes       | Teams bot for analyst HITL                       |
```

**Selector vocabulary is THE contract.** Use the kebab-case names from
the SPEC template verbatim — every other place in the toolchain
(`azd-patterns` Bicep module library, this composer) must match. Do
**not** invent a parallel YAML/camelCase namespace; that creates
silent no-ops where the composer doesn't recognize the SPEC's selector
and produces a Bicep tree missing the module the SPEC asked for.

### Step 1.5 — Apply SPEC implications

Per `speckit-template.md` § 11c, certain selectors imply others. Phase 6
**enforces** these silently — not failures, additions:

| When SPEC selects… | Composer auto-adds | Reason |
|--------------------|---------------------|--------|
| `aca-bot` | `aca-mcp` (if not already selected) | Bot needs MCP for case lookups |
| `event-grid` | `aca-job` (if not already selected) | Need a receiver for events |
| `service-bus` | `aca-job` (if not already selected) | Need a consumer for the queue |
| `foundry-iq-index` | `ai-search`, `storage-blob` | KB infra dependencies |

Surface the auto-additions in the composer's stdout so the user sees
``adding `aca-mcp` because `aca-bot` was selected'' — silent additions
that surprise the user are anti-pattern.

### Step 2 — Resolve module set (canonical inclusion order)

**Always include** (not in § 11c selectors — these are baseline):
`uami → acr → app-insights → foundry-account`. Notice **`key-vault` is
NOT in the always-include set** — Threadlight pilots are keyless by
mandate (managed identity end-to-end). Only include `key-vault` when
SPEC § 11c explicitly selects `key-vault: yes` because the process
integrates with a customer-side service that demands a literal API key.

`cosmos-db` is the most common selection (case state, audit) but is
**conditional** — a stateless single-call agent doesn't need it.

Conditionally include based on SPEC § 11c selector rows:
- `cosmos-db: yes` → include `cosmos-db.bicep`
- `ai-search: yes` → include `ai-search.bicep`
- `foundry-iq-index: yes` → include `foundry-iq-index.bicep` (delegates to `foundry-iq` skill)
- `azure-vision`/`doc-intel`/`azure-speech` `: yes` → include corresponding modules (delegates to `foundry-doc-vision-speech` skill)
- `event-grid`/`service-bus`/`storage-blob` `: yes` → include corresponding modules
- `aca-mcp: yes` → include `aca-mcp.bicep` per server (delegates to `foundry-mcp-aca` skill)
- `aca-job: yes` → include `aca-job.bicep` per job (delegates to `threadlight-event-triggers` skill)
- `aca-bot: yes` → include `aca-bot.bicep` (delegates to `foundry-teams-bot` skill)

### Step 3 — Compose `infra/main.bicep`

> **Phase 5 vs Phase 6 — what each writes.** Phase 5 (`azd ai agent init`)
> stubs `infra/main.bicep` with the always-create baseline + agent
> definition extension hooks ONLY. Phase 6 **edits** that stub: it adds
> the `module foo 'modules/foo.bicep' = if (deployFoo) { ... }` blocks
> for the SPEC-selected modules and writes the corresponding files into
> `infra/modules/`. The stub from Phase 5 stays as the orchestrator;
> Phase 6 fills it in. **Never overwrite `main.bicep` from scratch in
> Phase 6** — that drops the agent extension wiring from Phase 5.

Generate `infra/main.bicep` as a thin orchestrator that calls each included
module in order, threads outputs through, and emits the env vars the agent
container needs. Every output the agent reads at runtime MUST appear in
`agent.yaml`'s `environment_variables:` block (with the correct schema —
see Step 4).

```bicep
// infra/main.bicep — extended by Phase 6 from the Phase 5 stub
module uami 'modules/uami.bicep' = { /* always */ }
module acr 'modules/acr.bicep' = { /* always */ }
module appInsights 'modules/app-insights.bicep' = { /* always — see foundry-observability skill for layers 2 + 3 */ }
module cosmos 'modules/cosmos-db.bicep' = if (deployCosmosDb) { /* ... */ }

module search 'modules/ai-search.bicep' = if (deployAiSearch) { /* ... */ }
module foundryIQ 'modules/foundry-iq-index.bicep' = if (deployFoundryIqIndex) {
  params: { searchService: search.outputs.serviceName, knowledgeBases: knowledgeBases }
}
module vision 'modules/azure-vision.bicep' = if (deployAzureVision) { /* ... */ }
// ... and so on for each selected module ...

module foundryAccount 'modules/foundry-account.bicep' = { /* always, last */ }

// Outputs surfaced to azd .env (consumed by agent.yaml via env-var substitution)
output AZURE_COSMOS_ENDPOINT string = deployCosmosDb ? cosmos.outputs.endpoint : ''
output AZURE_COSMOS_DATABASE string = deployCosmosDb ? cosmos.outputs.databaseName : ''
output AZURE_SEARCH_ENDPOINT string = deployAiSearch ? search.outputs.endpoint : ''
output AZURE_FOUNDRY_IQ_INDEX string = deployFoundryIqIndex ? foundryIQ.outputs.indexNames[0] : ''
output AZURE_VISION_DEPLOYMENT_NAME string = deployAzureVision ? vision.outputs.deploymentName : ''
```

### Step 4 — Wire outputs to `agent.yaml`

`agent.yaml` is the Foundry hosted-agent definition. Its
`environment_variables` field is a **list of `{name, value}` objects** (not
a flat dict), and the values are resolved by the **azd .env at agent-deploy
time**, not by Bicep interpolation. Phase 6 maps Bicep outputs into the
azd .env (Step 3 emits the `output` declarations above; azd populates them
into `.azure/<env>/.env` after `azd provision`); `agent.yaml` then
references them as `${VAR_NAME}`.

```yaml
# agent.yaml (Phase 6 amends)
environment_variables:
  - name: COSMOS_ENDPOINT
    value: ${AZURE_COSMOS_ENDPOINT}
  - name: COSMOS_DATABASE
    value: ${AZURE_COSMOS_DATABASE}
  - name: SEARCH_ENDPOINT
    value: ${AZURE_SEARCH_ENDPOINT}
  - name: FOUNDRY_IQ_INDEX
    value: ${AZURE_FOUNDRY_IQ_INDEX}
  - name: VISION_DEPLOYMENT_NAME
    value: ${AZURE_VISION_DEPLOYMENT_NAME}
  - name: MCP_CUSTOMER_DATA_URL
    value: ${AZURE_MCP_CUSTOMER_DATA_URL}
  # AZURE_CLIENT_ID is auto-injected by the agent-runtime when bound to a UAMI
  # APPLICATIONINSIGHTS_CONNECTION_STRING is auto-injected when an App Insights
  # resource is associated with the Foundry project — do NOT set it here.
```

> **Schema gotchas** observed in earlier rounds:
> - `environment_variables` is a list of `{name, value}` dicts, not a flat
>   key→value mapping. The Foundry hosted-agent schema validator rejects
>   the flat form silently in some preview revs.
> - You can't use Bicep interpolation (`${cosmos.outputs.endpoint}`)
>   inside `agent.yaml` — the agent control plane doesn't see Bicep
>   outputs. Always go via azd .env.
> - Don't set `APPLICATIONINSIGHTS_CONNECTION_STRING` — it's reserved
>   and auto-injected when the project + App Insights are associated.
>   Setting it manually causes telemetry collisions.

### Step 5 — Hook scripts (postprovision / postdeploy)

If SPEC § 11c selects modules that need post-provision wiring (e.g.,
`foundry-iq-index` needs to run a Knowledge Agent provisioning script
after AI Search is up; `aca-job` needs `publish_aca` to push the job
image; `aca-bot` needs the Teams manifest sideload), Phase 6 **merges**
its hook needs with whatever Phase 5 already wrote. Never overwrite an
existing `hooks:` block — that's how the Phase 5 Teams-manifest hook
gets clobbered. Read, merge, write.

The merged form chains `&&`-style with a single shell invocation per
hook to preserve order:

```yaml
# azure.yaml (after Phase 6 merge)
hooks:
  postprovision:
    shell: pwsh
    run: |
      cd infra/scripts && uv sync --frozen
      uv run bootstrap_foundry_iq.py
      uv run sideload_teams_manifest.py   # added in Phase 5
  postdeploy:
    shell: pwsh
    run: |
      cd infra/scripts && uv sync --frozen
      uv run publish_aca_jobs.py
      uv run publish_aca_mcp.py
```

> **`bootstrap_foundry_iq.py` MUST follow `foundry-iq/SKILL.md` § Bootstrap script: hardening checklist.**
> The seven-point checklist (no `az rest` for uploads, fail-fast on rc, key
> sanitization regex, content chunking for the 32766-byte term limit, RBAC
> propagation wait, post-upload count verification, idempotent recovery script)
> is mandatory — silent bootstrap failures here = empty index = silent agent
> quality regression that doesn't show up until evals run. The hosted-agent
> identity callout in that same skill file (blueprint + instance MIs need
> `Search Index Data Reader` directly; project / account MIs are insufficient)
> drives whether you also need a `postdeploy_grant_agent_search_rbac.py` hook
> — add it whenever the consumer is a Foundry hosted agent.

For more than two scripts, write a `infra/scripts/postdeploy.py`
dispatcher that invokes each subscript in order — that keeps `azure.yaml`
stable across spec changes. The dispatcher pattern is documented in
`azd-patterns/SKILL.md` § "Cross-platform deployment scripts".

These scripts are **vendored into the project** so they don't depend on
network access at deploy time. The factory shapes are defined by `azd-patterns`.

### Step 6 — Validation

Phase 6 ends with three checks (all must pass before Phase 7):

```bash
# 1. Compile check — catches schema errors before deploy
az bicep build --file infra/main.bicep

# 2. Preview the deployment plan against your azd env
azd provision --preview

# 3. Validate agent.yaml against the Foundry hosted-agent schema
azd ai agent validate
```

> **The full Bicep module catalog** lives in `azd-patterns/SKILL.md` →
> "Composable Bicep Module Library". This skill orchestrates inclusion;
> azd-patterns owns the module shapes.

---

## Phase 6.5: Demo Data Seed (MANDATORY when SPEC § 5 marks any system as `mock`)

> **Why this is mandatory.** SPEC § 5 declares which systems are `mock`
> (almost always true for pilots). For each `mock` system backed by
> Cosmos, the deployment provisions empty containers — and unless a seed
> step runs, the deployed agent answers "not found" or "no records" on
> every realistic prompt. The `threadlight-demo-data-factory` skill
> generates `specs/sample-data/*.json` AND `scripts/seed_data.py`, but
> Phase 6.5 is what actually invokes the seed at deploy time.
>
> Origin: recent pilot retrospective — `azd up` returned 0, the agent
> deployed cleanly, the user typed `CASE-<id>` (a realistic golden
> case from `specs/sample-data/*.json`), the agent
> correctly reported "not found" because Cosmos was empty of that ID.
> The demo looked broken; it wasn't — it just had no data. 4 hours
> diagnosing what should have been a postdeploy seed step.

### Step 1 — Verify the demo-data-factory artifacts exist

Phase 1 (Analyze) reads SPEC § 5. If any system has `mock: yes`:

- ✅ `specs/sample-data/*.json` — at least one JSON per Cosmos container
  the spec declares (cases, customers, screening, risk-assessments, etc.)
- ✅ `scripts/seed_data.py` — the upsert script following the
  `threadlight-demo-data-factory` `Semaphore(8)` pattern
- ✅ `scripts/reset_data.py` — wipes Cosmos and re-runs `seed_data.py`
  (for re-runs after schema changes)

If any of the above is missing, **invoke `threadlight-demo-data-factory`
NOW** to generate them. Do not proceed to Step 2 until they exist.

### Step 2 — Grant Cosmos data-plane RBAC to the deployer

This is the single most common blocker. Cosmos data-plane writes
require **`Cosmos DB Built-in Data Contributor`** (role definition ID
`00000000-0000-0000-0000-000000000002`) — control-plane Owner is NOT
sufficient. Grant the deployer principal:

```bash
DEPLOYER_OID=$(az ad signed-in-user show --query id -o tsv)
COSMOS_ID=$(az cosmosdb show -g $RG -n $COSMOS_ACCOUNT --query id -o tsv)
az cosmosdb sql role assignment create -g $RG -a $COSMOS_ACCOUNT \
  --role-definition-id "00000000-0000-0000-0000-000000000002" \
  --principal-id "$DEPLOYER_OID" \
  --scope "$COSMOS_ID"
sleep 30   # RBAC propagation
```

For the **agent + bot UAMI** (so the runtime can read/write Cosmos via
the MCP server), the same role is required at the same scope. The Bicep
in `infra/modules/cosmos-db.bicep` should declare this assignment for
the shared UAMI; verify it's there.

### Step 3 — Wire the seed into the postdeploy hook chain

Append to `azure.yaml`:

```yaml
hooks:
  postdeploy:
    shell: pwsh
    run: |
      cd scripts && uv sync --frozen --quiet
      uv run seed_data.py
```

If a `postdeploy` hook already exists from Phase 5/6 (Toolbox setup,
Teams manifest sideload, AppIn connect), **merge** rather than overwrite:

```yaml
hooks:
  postdeploy:
    shell: pwsh
    run: |
      cd infra/scripts && uv sync --frozen --quiet
      uv run postdeploy.py     # dispatcher: toolbox + manifest + appin + seed
```

The dispatcher pattern (`infra/scripts/postdeploy.py`) is documented in
`azd-patterns/SKILL.md` § "Cross-platform deployment scripts".

### Step 4 — Verify

`scripts/seed_data.py` should print one line per file: `→ <file>
<container> (N docs)` and end with `✅ upserted N   ❌ errors 0`. The
post-deploy completeness gate (`threadlight-safe-check --phase
post-deploy` Step 5.8) then asserts that for each container declared
in SPEC § 5b with `seed_from: sample-data`, document count is non-zero.
If either step fails, the PoC is incomplete; do NOT declare victory.

---

## Phase 6.7: Update Seller Prep-Guide with Live MVP Walkthrough (when applicable)

**Trigger**: `specs/prep-guide.html` exists in the repo **AND** the Phase 3.5
post-deploy completeness gate passed (i.e., `tests/postdeploy-manifest.json`
exists with `gaps: []`).

**Skip silently** when:
- `specs/prep-guide.html` is absent (deploy was run on a repo that didn't
  go through `threadlight-design`, or the seller prep-guide was deliberately
  not generated). This phase is **additive-only** — it never fails the deploy.
- The post-deploy gate did not pass. Resolve the gap first; back-filling a
  walkthrough that points at a half-deployed PoC is worse than no walkthrough.

> **Why this phase exists.** `threadlight-design` writes the
> "Demo Script (high-level)" section of `specs/prep-guide.html` deploy-agnostic
> by construction (no FQDNs, no commands). That's correct — the seller may
> open the prep-guide in Cowork before any infra exists. But the seller still
> needs the **concrete** walkthrough once the PoC is live: the workspace URL
> to open, the Teams package to sideload, the exact prompts to type, the
> reset / eval / smoke commands. Phase 6.7 closes that loop in one shot,
> immediately after `azd up` returns clean.
>
> **Recent "what was missing?" data point.** A pilot shipped with a complete
> `prep-guide.html` Demo Script and a passing post-deploy gate, but the
> seller had to hand-correlate `azd env get-values | grep FQDN`, the eval
> dataset, and the bot package path on the morning of the demo. Phase 6.7
> removes that scramble.

### Step 1 — Decide whether to run

```bash
test -f specs/prep-guide.html || { echo "skip: no prep-guide.html"; exit 0; }
test -f tests/postdeploy-manifest.json || { echo "skip: no postdeploy-manifest"; exit 0; }
jq -e '.gaps == []' tests/postdeploy-manifest.json > /dev/null \
  || { echo "skip: post-deploy gaps non-empty"; exit 0; }
```

### Step 2 — Gather concrete artifacts

Pull from the artifacts already produced by Phase 3.5 + Phase 5 + Phase 6.5:

| What | From | How |
|---|---|---|
| Workspace UI FQDN | `tests/deployed-containerapps.json` | `jq -r '.[] \| select(.name \| contains("workspace")) \| .fqdn'` |
| Bot Container App name | `tests/deployed-containerapps.json` | `jq -r '.[] \| select(.name \| contains("bot")) \| .name'` |
| Teams sideload package | repo path | `src/bot/copilot_package.zip` (built by Phase 4 / `build_teams_manifest.py`) |
| Cron jobs + schedules | `tests/deployed-jobs.json` | `jq -r '.[] \| "\(.name) (\(.schedule))"'` |
| Mock MCP FQDN (if seeded) | `tests/deployed-containerapps.json` | `jq -r '.[] \| select(.name \| contains("mcp")) \| .fqdn'` |
| Reset / seed command | repo path | `python scripts/seed_data.py --reset` (when Phase 6.5 ran) |
| Eval command | repo path | `python tests/run_evals.py` |
| Smoke-test command | repo path | `python tests/invoke_agent.py "<prompt>"` |
| Sample queries (3–5) | `specs/SPEC.md` § 9 | grep `S-\d+ .*happy` rows OR read `tests/eval_dataset.jsonl` and pick the first 3–5 happy-path inputs verbatim |
| Resource group | `azd env get-value AZURE_RESOURCE_GROUP` | for the appendix |
| Foundry project endpoint | `azd env get-value AZURE_AI_PROJECT_ENDPOINT` | for the appendix |

> **Sample queries are not optional.** If `tests/eval_dataset.jsonl` is empty
> or SPEC § 9 has no happy-path scenarios, the back-fill **cannot proceed** —
> the seller would be left with "open the workspace" and no idea what to type.
> Halt, log the gap, and ask the user to either fix § 9 or run
> `threadlight-demo-data-factory` to regenerate the dataset.

### Step 3 — Replace the placeholder, or append if absent

Open `specs/prep-guide.html` and choose ONE of two strategies:

**Strategy A (preferred — design v1.3.0+).** If the file contains a
`<section id="demo-entrypoint">` placeholder block (emitted by
`threadlight-design` v1.3.0+), **replace** that entire block in place
with the populated walkthrough below. This keeps the seller's prep-guide
top-to-bottom flow intact (the placeholder appears at the top of the
file, where sellers expect the entrypoint info).

**Strategy B (legacy — design v1.2.x).** If no `id="demo-entrypoint"`
placeholder exists, **append** the walkthrough section immediately after
the existing `<section id="demo-script">` (or, if the file uses no `id`
attributes, after the `<h2>Demo Script</h2>` sibling block — older
prep-guides may use `<h2>Demo Script (high-level)</h2>`; match either).
**Never overwrite** the existing Demo Script — its acts already contain
the literal **Type this: / What you'll see: / Say:** prompts the seller
will run (generated by `threadlight-design` 1.2.0+); this phase only adds
the **runtime appendix** the seller needs once the PoC is actually
deployed (workspace URL, Teams sideload steps, the same prompts as a
copy-paste list, and reset/eval/smoke commands).

**In both strategies**, wrap the populated walkthrough in
`<details class="se-only">` (per `threadlight-design` v1.3.0+
Cross-cutting Pattern 3 — SE-only audience-collapsible). The seller's
default view stays clean; one click on the orange `[SA only]` pill
reveals the live URLs + commands when they need them.

> **Why we re-print the prompts here.** The design-side acts narrate the
> demo flow with one prompt per act + the expected response. The
> walkthrough's prompt list is a flat copy-paste convenience for the
> seller (and a smoke-test contract for `tests/run_evals.py`). When the
> two diverge — design-side has a paraphrased prompt, eval dataset has
> the literal one — **the eval dataset wins**. Phase 6.7 quietly logs a
> warning and prefers `tests/eval_dataset.jsonl`.

Section shape (Strategy A — replaces placeholder):

```html
<section id="demo-entrypoint">
  <details class="se-only">
    <summary>
      <span class="audience-pill">SA only</span>
      <strong>Live MVP Walkthrough</strong>
      <span class="hint">workspace URL · sideload · commands · ~5 min</span>
      <span class="chev">▸</span>
    </summary>
    <div class="se-body">
      <p class="callout-warning">
        Generated <time>{ISO-8601 timestamp}</time> from
        <code>tests/postdeploy-manifest.json</code>. Re-run
        <code>threadlight-deploy</code> Phase 6.7 after any redeploy to refresh.
      </p>

      <h3>1. Open the workspace</h3>
      <p>URL: <a href="https://{workspace-fqdn}/">{workspace-fqdn}</a></p>

      <h3>2. Sideload the Teams app (one-time, per tenant)</h3>
      <ol>
        <li>Download <code>src/bot/copilot_package.zip</code> from the repo.</li>
        <li>Teams Admin Center → Manage apps → Upload → select the zip.</li>
        <li>Bot Container App: <code>{bot-name}</code> (already wired to
            Azure Bot Service).</li>
      </ol>

      <h3>3. Run these prompts (in order)</h3>
      <ol>
        {for each sample query, in BR-order}
        <li><code>{query verbatim from eval_dataset.jsonl or SPEC § 9}</code>
            <br><small>demonstrates <strong>BR-{NNN}</strong></small></li>
      </ol>

      <h3>4. Scheduled jobs you can mention</h3>
      <ul>
        {for each row in tests/deployed-jobs.json}
        <li><code>{job-name}</code> — runs <code>{cron}</code></li>
      </ul>

      <h3>5. Reset / re-run / score</h3>
      <pre><code># Reset demo data to a clean state
python scripts/seed_data.py --reset

# Re-score the demo against the eval dataset
python tests/run_evals.py

# One-off smoke check
python tests/invoke_agent.py "{first sample query}"</code></pre>

      <h3>Appendix — environment</h3>
      <ul>
        <li>Resource group: <code>{rg-name}</code></li>
        <li>Foundry project endpoint: <code>{project-endpoint}</code></li>
        <li>Mock MCP endpoint: <code>{mcp-fqdn}</code> <em>(internal — only
            relevant if the customer asks about backend wiring)</em></li>
      </ul>
    </div>
  </details>
</section>
```

For Strategy B (legacy — no `id="demo-entrypoint"` placeholder), use the
same `<details class="se-only">` wrapper but inside a freshly appended
`<section id="live-mvp-walkthrough">`. The `<details>` wrapping rule is
the same; only the outer section name + insertion point differ.

> **Cross-link to design v1.3.0.** The `id="demo-entrypoint"` placeholder
> is one of three structural placeholders that `threadlight-design`
> v1.3.0+ emits in `prep-guide.html`. The other two —
> `id="mvp-capabilities"` (channels / sample data shape / tool surface)
> and `id="ms-services-map"` (commercial Azure / M365 services map) —
> are populated by `threadlight-design` itself from the SPEC and
> deployment_manifest. Phase 6.7 only owns the **demo-entrypoint**
> placeholder; do not touch the other two.

**Idempotency**: if a populated `<details class="se-only">` block already
exists inside `<section id="demo-entrypoint">` (re-deploy case),
**replace** the inner `<details>` block in place (do not append a second
one). Same rule applies inside `<section id="live-mvp-walkthrough">`
under Strategy B. This makes Phase 6.7 safe to re-run after every
`azd deploy`.

### Step 4 — Verify

After write, re-open the file and assert:

- [ ] **Strategy A**: exactly one populated `<details class="se-only">` block exists inside `<section id="demo-entrypoint">`, OR **Strategy B**: exactly one `<section id="live-mvp-walkthrough">` exists with a `<details class="se-only">` wrapper inside
- [ ] Workspace URL resolves to a `containerapps.io` FQDN (sanity-check
      against `tests/deployed-containerapps.json`)
- [ ] Sample-query block has ≥ 3 entries, each tagged with a BR-XXX that
      exists in SPEC § 3
- [ ] Reset / eval / smoke command paths exist on disk (`scripts/seed_data.py`
      only required when Phase 6.5 ran; tolerate absence with a `<!-- skipped:
      no seed_data.py -->` comment instead of a broken link)
- [ ] The original `<section id="demo-script">` (or "Demo Script" `<h2>`) is
      still present and unmodified — Phase 6.7 only owns the demo-entrypoint
      placeholder (Strategy A) or appends a sibling (Strategy B)
- [ ] **Strategy A only**: the other two design v1.3.0+ structural placeholders — `<section id="mvp-capabilities">` and `<section id="ms-services-map">` — are still present and untouched (those belong to `threadlight-design`, not Phase 6.7)

> **Internal-only banner stays.** The "INTERNAL / MICROSOFT CONFIDENTIAL"
> banner at the top of `specs/prep-guide.html` already covers the new
> section. Do not add a second banner; do not weaken the existing one.

### Step 5 — Tell the user

Print one line at the end of Phase 6.7, regardless of skip/run:

```
Phase 6.7: prep-guide live walkthrough → <appended | refreshed | skipped: {reason}>
```

The seller opens `specs/prep-guide.html` in a browser and now has a single
file containing both the offline-friendly narrative (from `threadlight-design`)
and the live-deploy walkthrough (from this phase).

---

## Phase 7: Citadel Handoff (opt-in)

**Trigger**: SPEC § 11b sets `governance_hub.required: yes`.

If the customer wants the deployed agent to land as a **spoke under their
AI Governance Hub** (centralized model gateway, key vault inheritance,
APIM policies, JWT auth), Phase 7 invokes the `citadel-spoke-onboarding`
skill AFTER the base deployment is provisioned.

### Why this is opt-in (not default)

- Citadel adds APIM connection wiring + product policy + JWT auth steps that
  are unnecessary for cx who just want a PoC running in their tenant
- Customers with no Citadel hub in place would face an extra dependency
- Pilot stage usually doesn't need governance — that comes when production-bound
- Adding Citadel later is a clean, additive change (no rewrite); doing it
  early when not needed is wasted setup

### When SPEC § 11b sets `governance_hub.required: yes`

Phase 7 reads SPEC § 11b for the rest of the AI Governance Hub spoke
posture:

```yaml
# specs/SPEC.md § 11b (when governance_hub.required: yes)
governance:
  governance_hub:
    required: yes
    hub_endpoint: https://hub-prod.<customer-apim>.azure-api.net
    access_contracts:
      - hub-llm-gateway
      - hub-knowledge-search
    secrets_via_keyvault: true
    jwt_auth: true
```

Then it hands off to `citadel-spoke-onboarding` (the **AI Citadel
Governance Hub** is the reference implementation; the SPEC field is
named generically because some customers run other hub products):

```
1. Run base azd up (Phase 5 + 6 complete) — agent deploys to its own tenant
2. Invoke citadel-spoke-onboarding skill with:
   - hub_endpoint
   - access_contracts list
   - the agent's UAMI principal (so APIM can grant it product subscription)
3. citadel-spoke-onboarding produces:
   - APIM connection in the Foundry project pointing to hub gateway
     (use Option B — Foundry Connection — NOT Option A; Option A breaks
     the keyless-by-mandate posture for threadlight pilots)
   - Key Vault references replacing direct AOAI keys
   - Updated agent.yaml with `MODEL_DEPLOYMENT_NAME = connectionName/deploymentName`
   - JWT validation policy on the agent endpoint
   - Validation notebook to prove end-to-end works
4. Redeploy agent (azd deploy <service>) to pick up the new MODEL_DEPLOYMENT_NAME
```

### When `governance_hub.required: no` (or missing)

Phase 7 is a **no-op** — log "Governance hub onboarding skipped per SPEC
§ 11b" and end. Customer can re-enable later by setting
`governance_hub.required: yes` in SPEC § 11b and running
`threadlight-deploy` Phase 7 again (it is incrementally re-runnable).

> **See `citadel-spoke-onboarding` skill** for the full step-by-step
> onboarding procedure, APIM access contract details, and validation
> notebook.

---

## Gotchas & Hard-Won Lessons

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent returns empty responses | TPM too low — 429 rate limits | Use ≥300K TPM deployment |
| **`FOUNDRY_PROJECT_ENDPOINT` in agent.yaml** | **All `FOUNDRY_*` and `AGENT_*` env vars are reserved by the platform (injected automatically)** | **Remove from `environment_variables` in agent.yaml. Container reads it via `os.environ` at runtime.** |
| **Hosted agent returns `server_error`/`model:""` on every smoke; AppIn 0 rows; container looks healthy in `azd ai agent show`** | `container.py` calls raw `configure_azure_monitor()` as the first line of `main()` with no try/except. When the platform fails to auto-inject `APPLICATIONINSIGHTS_CONNECTION_STRING` (e.g. AppIn account-level connection persisted with `credentials: null` — see next row), the SDK raises `ValueError` and the container crashes before `ResponsesHostServer` binds. Foundry runtime then sees no agent → `server_error`. **The agent itself is fine.** | Wrap telemetry init in `_init_telemetry()` helper that no-ops on missing env / SDK ImportError / SDK exception. NEVER call `configure_azure_monitor()` raw at module/main scope. See `foundry-observability` skill, gap rows O-011 / O-012 for the full forensic and reference template. |
| **AppInsights connection PUT returns 400 ValidationError on `authType: AAD`; ApiKey fallback returns 200 but GET shows `credentials: null` (silent server-side drop)** | Platform gap on account-RP scope `2025-10-01-preview` in some regions (correlation IDs available). Connection persists with `isDefault: true` but no usable secret → platform never auto-injects `APPLICATIONINSIGHTS_CONNECTION_STRING` into hosted agents | **No code workaround exists today.** Ship the agent with guarded `_init_telemetry()` (preceding row) so it functions without telemetry. File a support ticket with the correlation IDs. If AppIn telemetry is non-negotiable, pivot region (`eastus` / `northcentralus` are the best initial bets — verify auto-injection works BEFORE committing to a redeploy) |
| **`template.kind` validation error** | **agent.yaml uses wrong schema — `template:` nesting is for `agent.manifest.yaml` (samples only)** | **Use ContainerAgent schema: `kind: hosted` at top level, NOT `template.kind`. Schema: `ContainerAgent.yaml`** |
| **"Experience not available" on create_version** | **Region does not support hosted agents OR `ENABLE_CAPABILITY_HOST=true` (removed in refreshed preview)** | **Set `ENABLE_CAPABILITY_HOST=false` in `main.parameters.json`. Try `northcentralus`, `eastus`, `swedencentral`. Avoid `eastus2`.** |
| **Agent 401 on `storage/history`** | **Agent's Entra identity missing `Azure AI User` on project scope, OR RBAC not yet propagated (5-15 min for new SPs)** | **Assign `Azure AI User` to BOTH `instance_identity` AND `blueprint` principal IDs on Foundry account + project. Wait 15 min, then redeploy to force new session.** |
| **401 PermissionDenied on agent invoke (caller)** | **Calling user/principal missing `Azure AI User` on Foundry account + project** | **Assign `Azure AI User` to your principal on both account and project scope** |
| **`{{chat}}` literal in env vars** | **Mustache `{{template}}` syntax in agent.yaml `environment_variables` is NOT expanded by the azd extension** | **Use literal model deployment names (e.g., `gpt-5.4`) or `__PLACEHOLDER__` tokens** |
| **pip can't resolve agent-framework deps** | **Pre-release `agent-framework-foundry-hosting` and its beta transitive deps** | **Use `uv` with `prerelease = "if-necessary-or-explicit"` in `[tool.uv]`. Do NOT use `"allow"` — it pulls beta azure-identity.** |
| MCP tools not appearing | MCP server returns 400/404 on protocol methods | All 6 JSON-RPC methods must return 200 |
| MCP connection timeout | ACA not started yet | Runtime retries automatically |
| Eval `tool_selection` failures | Agent calls tools unnecessarily | Tool-use discipline directive (auto-injected) |
| `create_version` returns old version | Same image tag as before | Always use unique timestamp tags |
| `DeploymentModelNotSupported` | Wrong model version for the chosen model | Each model has a specific version string — see **Model Version Lookup Table** in Phase 5 § Step 2. Use `az cognitiveservices account list-models` to verify. |
| `azd ai agent` extension missing | Extension not installed | `azd extension install azure.ai.agents` (ensure ≥0.1.30-preview) |
| Bot image overwritten on reprovision | Bicep resets container image | fetch-container-image.bicep + `SERVICE_BOT_RESOURCE_EXISTS` param |
| Skills not loading | Wrong directory path | Must be `skills/` relative to `/app/` |
| Import errors crash container | Missing dependency in pyproject.toml | Diagnostic HTTP server keeps container alive |
| Bot returns "Response could not be saved" | Old-style `agent_reference` invocation | Use `get_openai_client(agent_name=...)` with `allow_preview=True` |
| Bot gets 400 "responses protocol not declared" | **CONFIRMED:** GHCP SDK agent only serves `/invocations`. Bot's `oai.responses.create()` fails. | Bot must use direct HTTP POST to `/protocols/invocations` + SSE parsing for GHCP agents. OR use MAF runtime. See `foundry-teams-bot` skill. |
| Bot auth 401 on /api/messages | UAMI not in CONNECTIONS__ env vars | Set all 4 `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` vars (CLIENTID, TENANTID, AUTHORITYENDPOINT, **AUTHTYPE=UserManagedIdentity**) |
| **Bot returns HTTP 500 with `AADSTS7000216` on every real Teams message** (synthetic JWT probe still passes!) | **Missing `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE` env var → MSAL falls back to ConfidentialClient flow → demands client_secret the keyless deploy never provisioned. Silent-killer auth bug.** | **Add `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity` to bot ACA env in Bicep. Quick patch: `az containerapp update --set-env-vars CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity`. The `safe-check --phase post-deploy` Step 5.7 catches this; channel JWT probe does NOT (JWT middleware fires before outbound token acquisition).** |
| Teams can't find bot | manifest botId mismatch | `botId` must equal UAMI client ID used as `msaAppId` |
| **Teams sideload fails with regex validation error on `id`, `copilotAgents[0].id`, `bots[0].botId`** | **`build_manifest.py` used a silent fallback like `<uami-client-id>` when `BOT_APP_ID` env var was missing** | **Guard in `build_manifest.py`: `if not bot_id or bot_id.startswith("<"): raise SystemExit(...)`. Never use human-readable placeholders for UUID fields. When running the script manually: `$env:BOT_APP_ID = azd env get-value BOT_APP_ID; python scripts/build_manifest.py`** |
| Streaming garbled in Teams | Sending each chunk separately | Collect all chunks, send as single message |
| `azd deploy` fails with Docker error | Missing `remoteBuild: true` in azure.yaml | Add `remoteBuild: true` under `docker:` — azd builds via ACR Tasks, no local Docker |
| **Model deployments not created** | **`azd deploy` doesn't create model deployments — only `azd provision`** | **Run `azd up` (full) or `azd provision` to create model deployments** |
| **Compute not starting** | Agent not invoked yet | Refreshed preview provisions compute on first request; deprovisions after 15min idle |
| **Protocol version error** | Using old `"v1"` format | Use semver `"1.0.0"` in agent.yaml and SDK code |
| **`azd ai agent show` hangs or says "not logged in"** | `azd` has its own auth chain (`AzureDeveloperCliCredential`) — `az login` does NOT populate it, even with `AZURE_CONFIG_DIR` set | Run `azd auth login --tenant-id <id>` in the same shell. The `azd` token cache lives in `$AZD_CONFIG_DIR/auth/`, separate from `az`'s. Bake both `az login` and `azd auth login` into your shell startup script. |
| **`postdeploy` fails with AZURE_TENANT_ID** | Extension postdeploy hook expects tenant ID for RBAC auto-assignment | **Set `AZURE_TENANT_ID` in azd env. Without it, postdeploy can't assign `Azure AI User` to agent identity → runtime 401 on storage** |
| **Two identities in `azd ai agent show`** | Refreshed preview creates `instance_identity` + `blueprint` per agent | Both need RBAC — assign same roles to both principal IDs |
| **MCP `server_url` invalid URI error** | `${ENV_VAR}` in mcp-config.json not set → expands to empty string → `/mcp` is not a valid URI | **Only include MCP servers with deployed endpoints. Remove entries with unresolved env vars. The container skips empty URLs, but `FoundryChatClient.get_mcp_tool()` registers them and Foundry rejects at runtime.** |
| **Deployer needs `Azure AI Project Manager`** | The extension postdeploy hook auto-assigns `Azure AI User` to agent identity, but needs role-assignment permission to do so | **Assign `Azure AI Project Manager` to deployer on Foundry project scope. Also set `AZURE_TENANT_ID` in azd env.** |
| **MCP ACA 200-500s cold start** | Default 0.5 CPU / scale-to-0 causes massive latency | Use 1 CPU / 2Gi minimum, set `minReplicas: 1` in Bicep (see `foundry-mcp-aca` skill) |
| **Missing `[tool.setuptools] packages = []`** | GHCP SDK pyproject.toml needs it for uv to resolve correctly | Add `[tool.setuptools]\npackages = []` to pyproject.toml |
| **Bicep missing `AZURE_AI_PROJECT_ID` output** | Postprovision/postdeploy hooks need the ARM resource ID | Bicep must output `AZURE_AI_PROJECT_ID` (full ARM resource ID, not just endpoint) |
| **CognitiveServices API version wrong** | Using old `2024-10-01` API | Use `2025-10-01-preview` for connections and agent management |
| **Hooks fail on Windows** | `shell: sh` in azure.yaml hooks | Use `shell: pwsh` for cross-platform compatibility |
| **gpt-4.1 encrypted content error** | gpt-4.1 deprecated, doesn't support encrypted content | Default to `gpt-5.4-mini` |
| **Evals show no telemetry** | AppInsights not connected to Foundry account | Create `AppInsights` connection on the **account** (not project). Category: `AppInsights`, target: ARM resource ID, metadata: `ApiType: Azure`. See Monitoring section. |
| **`azd up --no-prompt` fails with multiple subs** | azd can't auto-select subscription | Set `AZURE_SUBSCRIPTION_ID` in azd env: `azd env set AZURE_SUBSCRIPTION_ID <sub-id>` |
| **`config.deployments` fails silently — no model created** | Extension creates model during provision but doesn't error if it fails | Verify with `az cognitiveservices account deployment list --resource-group <rg> --name <account> -o table` after `azd provision` |
| **Cross-RG ACR needs manual AcrPull** | ACR in different resource group from ACA | Manually assign `AcrPull` to the shared UAMI on the ACR. Bicep auto-assignment only works same RG. |
| **ACA missing `azd-service-name` tag** | azd can't find the ACA for updates on redeploy | Add `azd-service-name: <service>` tag to all ACA resources in Bicep |
| **MCP ACA needs `registries` config in ACA** | ACA can't pull image from ACR without registry auth | Add `registries: [{ server: acrEndpoint, identity: uami.id }]` to ACA configuration in Bicep (NOT admin creds, NOT system MI) |
| **ACA `secrets[].keyVaultUrl` fails at create-time** when KV secret doesn't exist yet | Secret refs are validated **at ACA provisioning**, not at runtime. Cannot create ACA + KV secret + auth wiring in a single Bicep deploy when the secret value comes from `az ad app credential reset` (which needs the ACA's FQDN as redirect URI… circular). | **2-phase Bicep deploy with a `wireAuth bool = false` param.** Phase 1: deploy ACA with empty `secrets:` array + skipped `authConfigs`. Between phases: grant deployer `Key Vault Secrets Officer`, mint client secret on the app reg via `az ad app credential reset --append --display-name <label>`, write to KV. Phase 2: re-deploy with `wireAuth=true` to wire the secret reference + `authConfigs`. See **Static-Site Showroom Deploy** reference below. |
| **`enableRbacAuthorization=true` on KV** — Owner can't write secrets | KV with RBAC mode requires data-plane role; Owner only grants control plane | Assign `Key Vault Secrets Officer` (`b86a8fe4-44ce-4948-aee5-eccb2c155cd7`) to the deployer principal, wait **25-30s** for RBAC propagation before `az keyvault secret set` |
| **PowerShell array param `--parameters key=[\"$oid\"]` corrupts JSON** | Quote escaping between PowerShell + az CLI strips the inner `"`, leaving `[bare-guid]` which fails JSON parse | Either pass arrays via a parameters JSON file, OR drop the array param from Bicep and grant the role via post-deploy `az role assignment create` |
| **Wrong built-in role GUID hard-coded in Bicep** | Easy to typo (`...406e-8b5a-...` vs `...408a-b874-...`); deploy doesn't fail until role-assignment resource provisions | **NEVER hard-code role GUIDs from memory.** Look up via `az role definition list --name "<role>" --query "[0].name" -o tsv`. Useful pins: AcrPull `7f951dda-4ed3-4680-a7ca-43fe172d538d` · KV Secrets User `4633458b-17de-408a-b874-0445c86b69e6` · KV Secrets Officer `b86a8fe4-44ce-4948-aee5-eccb2c155cd7` |
| **`az rest --headers Content-Type=application/json` fails on Windows** ("non atteso" / "unexpected") | The `--headers` flag has inconsistent parsing between az CLI versions and locales | For redirect-URI updates, use `az ad app update --id <appId> --web-redirect-uris uri1 uri2 …` (replaces the full array — read existing first, merge, then update) |
| **`az ad app credential reset` without `--append` blows away other secrets** | Default behavior is REPLACE, not append | Always pass `--append --display-name <label>`. Verify with `az ad app credential list --id <appId>` after |
| **Redeploying ANY MCP service (`azd deploy <mcp>`) silently breaks the running agent** — every tool call returns `404 Session not found`, agent self-reports `case read failed` / `query failed` on EVERY call, MCP container is `Healthy`, MCP logs show `POST /mcp HTTP/1.1" 404 Not Found` WITHOUT a preceding `new transport with session ID: ...` line | Agent's MCP client caches the `mcp-session-id` from the previous initialize handshake. New MCP container = sessions wiped. Agent does NOT auto-re-handshake on `Session not found`. External probes to `/mcp` with proper Accept headers return `200 OK` — confirming the path is fine, the SESSION is gone | **Treat MCP + agent as a coupled deploy pair on running pilots.** After `azd deploy <mcp-service>`, also run `azd deploy <agent-service>` (creates new agent version, fresh MCP session pool) AND restart the bot replica: `az containerapp revision restart -g <rg> -n <bot-aca> --revision $(az containerapp revision list -g <rg> -n <bot-aca> --query "[?properties.active] | [0].name" -o tsv)`. Alternative: wait ~15 min idle for refreshed-preview auto-deprovision. See `foundry-mcp-aca` skill v1.0.3 for the full diagnostic table (FastMCP 3.x mount-path 404 vs stale-session 404). |

> **See `foundry-hosted-agents`** for additional troubleshooting, migration guide,
> and detailed RBAC scenarios.

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](../threadlight-design/) | Spec out the business process first (produces specs/ + AGENTS.md + skills that this skill consumes) |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | Reference for RBAC, identity model, agent.yaml schema, dependencies, troubleshooting |
| [**foundry-iq**](../foundry-iq/) | **Default for every process** — provisions the AI Search index + Knowledge Agent (consumed in Phase 6 via `foundry-iq-index.bicep`) |
| [**foundry-doc-vision-speech**](../foundry-doc-vision-speech/) | Vision / Document Intelligence / Speech models — consumed in Phase 6 when SPEC § 7b selects them |
| [**foundry-teams-bot**](../foundry-teams-bot/) | Deep dive on Teams bot integration (bot.py, manifest, Bicep, sideloading) |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Deploy custom MCP servers as ACA or Azure Functions |
| [**foundry-evals**](../foundry-evals/) | Evaluate agent quality + **continuous evaluation**: Plan A (default) Foundry built-in scheduled evals, Plan B (fallback) ACA Job (reads SPEC § 9 KPI table) |
| [**threadlight-safe-check**](../threadlight-safe-check/) | **Mandatory post-deploy completeness gate** — invoked from `predeploy` / `postdeploy` hooks; verifies every SPEC § 11c selector maps to deployed resources, all channels reach, all jobs are wired. Run this before declaring victory or kicking off `foundry-evals` |
| [**foundry-observability**](../foundry-observability/) | **Always layered into deploy from day one.** Owns the 3-layer telemetry pattern (Bicep substrate → Foundry account-level AppIn connection → `configure_azure_monitor()` in each ACA workload). Without this, `azd up` returns 0 but App Insights stays empty for the entire pilot lifetime — the silent gap observed in recent pilots. The post-deploy hook MUST call `connect_foundry_appinsights.py` and every ACA workload entry point MUST start with `init_telemetry(role=...)` |
| [**threadlight-local-test**](../threadlight-local-test/) | **For SEs.** Optional fast inner-loop before `azd up` — run the designed agent locally (FoundryChatClient + FastMCP + workspace + sample data) in Copilot CLI / Cowork / Clawpilot. Skip when the spec is a one-shot demo or already-deployed pilot |
| [**threadlight-workspace-ui**](../threadlight-workspace-ui/) | Generates the operator workspace from SPEC § 8b (case-list, inbox, dashboard, console, kanban, map) |
| [**threadlight-hitl-patterns**](../threadlight-hitl-patterns/) | Generates Adaptive Cards + audit trail for SPEC § 8 action gates |
| [**threadlight-event-triggers**](../threadlight-event-triggers/) | Generates trigger receivers from SPEC § 10b (ACA Job cron/manual, Functions, ACA consumer) |
| [**threadlight-demo-data-factory**](../threadlight-demo-data-factory/) | Generates realistic demo data when SPEC § 5 marks any system as `mock` |
| [**ghcp-hosted-agents**](../ghcp-hosted-agents/) | Alternative runtime — GHCP SDK with Invocations protocol (for long-running agents >120s) |
| [**citadel-spoke-onboarding**](../citadel-spoke-onboarding/) | **Phase 7 (opt-in)** — onboards as a spoke under an AI Governance Hub when SPEC § 11b sets `governance_hub.required: yes` |
| [**foundry-cross-resource**](../foundry-cross-resource/) | AI Gateway (APIM) — use models from another Foundry resource or shared pool |
| [**azure-tenant-isolation**](../azure-tenant-isolation/) | Per-tenant `AZURE_CONFIG_DIR` / `AZD_CONFIG_DIR` so `azd up` always lands in the right tenant + subscription |
| [**azd-patterns**](../azd-patterns/) | `azd` hooks, ACA job deployment, **Composable Bicep Module Library** (the source of every module Phase 6 includes) |

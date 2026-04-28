---
name: threadlight-deploy
description: >
  Take a designed agent project folder (AGENTS.md, skills, config) and generate all
  deployment artifacts for Microsoft Foundry Hosted Agents: container.py (Agent +
  FoundryChatClient + ResponsesHostServer), Dockerfile (uv-based), pyproject.toml,
  copilot-instructions.md, mcp-config.json, skills/, full azd project (azure.yaml,
  vendored Bicep, Teams bot), and deploy-notes.md. One-command deployment via `azd up`.
  USE FOR: deploy to Foundry, make this deployable, generate deployment files, Foundry hosted agent,
  containerize agent, prepare for Foundry, create Dockerfile for agent, package agent,
  deploy agent, make it runnable, hosted deployment, agent deployment, MCP tools in Foundry,
  Teams integration, Teams bot, connect to Teams, Teams channel, azd deploy, azd up.
  DO NOT USE FOR: designing the process (use threadlight-design), running evals (use testing-and-evals).
---

# Foundry Hosted Agent Deploy

Take a project folder (containing AGENTS.md, `.github/skills/`, config/, etc.) and enrich
it with all files needed to deploy as a **Microsoft Foundry Hosted Agent** using the
Microsoft Agent Framework (MAF) variant. Uses the **`azd ai agent` extension** for
declarative deployment — `azure.yaml` defines agent configuration, model deployments,
and container resources; `azd up` handles everything (provision, build, deploy, create agent).

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
- `.github/skills/*/SKILL.md` — one or more skill definitions (or `skills/`)
- `config/*.json` — process configuration (optional but recommended)

## Workflow

```
Read AGENTS.md → Map tools → Choose MCP strategy → Generate runtime files → Validate → Generate azd project (extension scaffold) → Deploy notes
```

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

Read `AGENTS.md` and all skills to determine:

1. **Which Foundry tools are needed** (from the "Foundry Tools Required" table)
2. **Which MCP servers are needed** (custom tools beyond built-ins)
3. **MCP servers needed** (custom tools beyond built-ins, deployed as ACA or Azure Functions)
4. **Storage strategy** (Cosmos via MCP, AI Search, Blob, etc.)
5. **Model requirements** (which model deployment, TPM needs)
6. **Skills list** (for SkillsProvider registration)

---

## Phase 2: Generate Deployment Artifacts

Create these files in the project root:

### 1. `copilot-instructions.md` — Agent System Prompt

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

### 2. `skills/` Directory

Copy each `.github/skills/*/SKILL.md` → `skills/*/SKILL.md`:

```
skills/
├── scan-competitor-x/
│   └── SKILL.md
├── generate-report/
│   └── SKILL.md
└── detect-changes/
    └── SKILL.md
```

These are loaded at startup by `_load_skills()` and appended to instructions.
The agent discovers all skill content through its system prompt.

### 3. `mcp-config.json` — MCP Server Configuration

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

**Foundry tool → runtime mapping (MAF variant):**

| Design Tool | MAF Runtime | Notes |
|-------------|-------------|-------|
| Browser Automation | **MCP ACA** — deploy Playwright as a remote MCP server | Local Playwright cannot run inside hosted agent containers. Use the official Playwright MCP Docker image or `npx @playwright/mcp` packaged in an ACA. See `mcp-aca-reference.md`. |
| Code Interpreter | Platform MCP / custom tool | Use Foundry Toolbox MCP endpoint if available, or a custom `@tool` function |
| Azure AI Search | Platform MCP / custom tool | Use Foundry Toolbox MCP endpoint if available, or a custom `@tool` function |
| Bing Search / Web Search | **MCP server** or **custom tool** (Python function calling a search API) | Deploy a web search MCP server as ACA, or define a custom `@tool` function that calls a search API (Tavily, SerpAPI, etc.). |
| Cosmos DB | MCP ACA (e.g., .NET MCPToolKit — see MCP ACA reference) | Proven pattern |
| Custom data store | Custom MCP server (deploy as ACA or Azure Functions) | Proven pattern |

> **Key constraints for MAF hosted agents:**
>
> 1. **No local browser** — hosted agent containers are headless Python environments.
>    Playwright, Selenium, etc. cannot run locally. Deploy browser automation as a
>    remote MCP server on ACA (e.g., `mcr.microsoft.com/playwright/mcp` or a custom
>    container running `npx @playwright/mcp --port 8080`).
>
> 2. **No built-in web search** — use a web search MCP server or custom `@tool`
>    function calling a search API (proven pattern).
>
> 3. **Foundry Toolbox MCP** — the refreshed preview supports platform-managed MCP
>    tools via the Foundry Toolbox endpoint. Use `client.get_mcp_tool()` to connect.
>    Note: some tools may require `Foundry-Features: Toolsets=V1Preview` header.

### 4. `container.py` — MAF Runtime

**Copy the reference template** at `references/container-runtime-template.py` into the
project root as `container.py`. Then adapt:

- Model: set `AZURE_AI_MODEL_DEPLOYMENT_NAME` env var default to match agent's target model
- Instructions: loaded from `copilot-instructions.md` at startup
- Skills: loaded from `skills/` directory and appended to instructions
- MCP: loaded from `mcp-config.json` → `client.get_mcp_tool()` for each server

The runtime uses `Agent` + `FoundryChatClient` + `ResponsesHostServer` from the
Microsoft Agent Framework. Auth is handled by `DefaultAzureCredential` passed to
`FoundryChatClient` — no BYOK workarounds needed.

The runtime handles:
1. `FoundryChatClient` with `DefaultAzureCredential` for Foundry auth
2. `_load_skills()` reads all SKILL.md files and appends to instructions
3. `_create_mcp_tools()` creates tools via `client.get_mcp_tool()`
4. `ResponsesHostServer(agent).run()` serves the Responses protocol
5. Diagnostic HTTP server on import failure (keeps container alive for debugging)

**Do NOT write the container runtime from scratch** — always start from the reference template.

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

### 5. `pyproject.toml` — Python Dependencies

**Copy from `references/pyproject-template.toml`** and replace `__PROJECT_NAME__`:

```toml
[project]
name = "__PROJECT_NAME__-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "agent-framework-core>=1.0.0",
    "agent-framework-foundry>=1.0.0",
    "agent-framework-foundry-hosting>=1.0.0a260421",
    "azure-ai-agentserver-responses>=1.0.0b4",
    "azure-identity>=1.19.0,<1.26.0a0",
    "python-dotenv>=1.0.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"
```

**CRITICAL: Uses `uv` (not `pip`)** — the `prerelease = "if-necessary-or-explicit"` setting
lets uv resolve prerelease packages that have explicit prerelease markers in their version
specs (e.g. `>=1.0.0a260421`), while keeping all other packages on GA (e.g. `azure-identity`
resolves to 1.25.3 GA, NOT 1.26.0b2 beta). Do NOT use `"allow"` — it pulls beta versions
of azure-identity and other packages unintentionally.

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

### 6. `Dockerfile` — Self-Contained Container

**Copy from `references/dockerfile-template`** and adapt:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Uses uv for dependency management (prerelease support for hosting package)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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
│  │  │  - container.py (MAF)      │  │    │
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
- `azd ai agent` extension: `azd extension install azure.ai.agents` (≥0.1.27-preview)
- Azure subscription with Contributor + **Azure AI Project Manager** on Foundry project
- Set `AZURE_TENANT_ID` in azd env: `azd env set AZURE_TENANT_ID <your-tenant-id>`

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

## Authentication

- **KEYLESS ONLY** — never use API keys for Azure services
- Each hosted agent gets a **dedicated Entra identity** at deploy time
- `FoundryChatClient` uses `DefaultAzureCredential` in the container
- Bot uses User-Assigned Managed Identity (UAMI) for Bot Service auth
- Grant downstream resource RBAC to the **agent's identity** (not project MI)
- **Azure AI Project Manager** role required at project scope to deploy

## Health Probes

`ResponsesHostServer` handles liveness and readiness probes natively — no custom
middleware needed.

## Evaluations

After deployment, run Foundry cloud evals:
- 6 built-in evaluators: intent_resolution, task_adherence, task_completion,
  coherence, tool_selection, tool_output_utilization
- All evaluator names use `builtin.` prefix
- Minimum 300K TPM recommended for eval runs
```

---

## Phase 3: Validate

After generating files, validate:

- [ ] `copilot-instructions.md` exists and is 500-1500 words
- [ ] `skills/` has at least one SKILL.md
- [ ] `container.py` exists and uses `Agent` + `FoundryChatClient` + `ResponsesHostServer`
- [ ] `pyproject.toml` includes split packages: `agent-framework-core`, `agent-framework-foundry`, `agent-framework-foundry-hosting`
- [ ] `pyproject.toml` has `prerelease = "if-necessary-or-explicit"` in `[tool.uv]` (NOT `"allow"`)
- [ ] `pyproject.toml` pins `azure-identity>=1.19.0,<1.26.0a0` (prevent beta pull)
- [ ] `Dockerfile` uses `python:3.12-slim` (NOT a custom base image)
- [ ] `Dockerfile` uses `uv sync` (NOT `pip install`)
- [ ] `Dockerfile` copies `container.py`, `copilot-instructions.md`, `skills/`
- [ ] `mcp-config.json` only has remote servers (no local-only, no stdio)
- [ ] `azure.yaml` exists with `host: azure.ai.agent` service and `requiredVersions` for extension
- [ ] `azure.yaml` has model deployment in `config.deployments` section
- [ ] `agent.yaml` exists with `kind: hosted` (top-level, ContainerAgent schema), protocols (version `1.0.0`), resources `{cpu, memory}`
- [ ] `agent.yaml` does NOT include `FOUNDRY_PROJECT_ENDPOINT` env var (reserved — platform injects it)
- [ ] `agent.yaml` does NOT nest under `template:` — `kind`, `protocols`, `resources` are top-level
- [ ] `infra/main.bicep` exists (subscription-scope Bicep)
- [ ] `copilot/bot.py` and `copilot/app.py` exist
- [ ] `copilot/bot.py` uses `get_openai_client(agent_name=...)` (NOT `agent_reference`)
- [ ] No secrets or API keys in any generated file
- [ ] No local file paths hardcoded
- [ ] `deploy-notes.md` references `azd up` as the deployment command

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

### Why MAF (Microsoft Agent Framework)?

- **Official path**: All Foundry hosted agent samples use `Agent` + `FoundryChatClient`
- **Simple auth**: `DefaultAzureCredential` passed to `FoundryChatClient` — no BYOK hacks
- **MCP integration**: `client.get_mcp_tool()` is cleaner than `MCPStreamableHTTPTool`
- **ResponsesHostServer**: Native Responses protocol bridge, handles liveness probes
- **Custom tools**: `@tool(approval_mode="never_require")` with Annotated type hints
- **Dedicated identity**: Each agent gets its own Entra identity at deploy time

### Tool-Use Discipline

The container runtime auto-injects a "Tool-Use Discipline" section into instructions.
This is CRITICAL for eval scores — without it, agents over-call tools
(list_databases, get_schema) on every turn, causing `tool_selection` failures
(30-50% instead of 80%+).

---

## Reference: Container Runtime Architecture

```
container.py (MAF variant — self-contained)
│
├── _load_instructions()
│   └── Read copilot-instructions.md
│
├── _load_skills()
│   └── Read skills/**\/SKILL.md → append to instructions
│
├── _load_mcp_config()
│   ├── Try /app/mcp-config.json (with ${ENV_VAR} expansion)
│   └── Fall back to MCP_SERVER_URL env var
│
├── FoundryChatClient(project_endpoint, model, credential)
│   └── DefaultAzureCredential — keyless auth to Foundry
│
├── _create_mcp_tools(client, config)
│   └── client.get_mcp_tool(name, url, headers, approval_mode)
│
├── Agent(client, instructions, tools, default_options={"store": False})
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

> **Reserved environment variables (April 2026):** All `FOUNDRY_*` and `AGENT_*` prefixed
> variables are reserved by the platform. Do NOT declare them in `agent.yaml`
> `environment_variables` — the platform injects them automatically. Declaring them causes
> `invalid_payload` errors at `create_version` time.

---

## Reference: Identity & RBAC (Refreshed Preview)

The refreshed hosted agents preview (April 2026) changed the identity model significantly.

### Identity Model

Each hosted agent gets **two identities** at deploy time:

| Identity | Field in `azd ai agent show` | Purpose |
|----------|------------------------------|---------|
| **Instance identity** | `instance_identity.principal_id` | The agent's dedicated Entra service principal. Used for runtime operations. |
| **Blueprint identity** | `blueprint.principal_id` | Agent blueprint identity. Used by the platform for internal operations. |

Both identities are created automatically when the agent is deployed — no manual setup needed.
The project also has its own **managed identity** (separate from the agent identities).

### Required RBAC Assignments

**For the deploying user/principal** (you):

| Role | Scope | Purpose |
|------|-------|---------|
| `Azure AI Project Manager` | Foundry project | Create agents, deploy versions |
| `Azure AI User` | Foundry account + project | Invoke agents, access models |
| `Contributor` | Resource group | Create Azure resources (Bicep) |
| `Container Registry Repository Writer` | ACR | Push container images |

**For the project managed identity** (auto-assigned by Bicep if permissions allow):

| Role | Scope | Purpose |
|------|-------|---------|
| `Azure AI User` | Foundry account | Model inference via project endpoint |
| `Container Registry Repository Reader` | ACR | Pull container images at runtime |
| `Log Analytics Data Reader` | Log Analytics workspace | Telemetry for evaluations |

**For the agent identities** (instance + blueprint — both need the same roles):

| Role | Scope | Purpose |
|------|-------|---------|
| `Azure AI User` | Foundry account | Model inference |
| `Azure AI User` | Foundry project | Access project-scoped APIs (storage, history) |
| `Cognitive Services OpenAI User` | Foundry account | Direct OpenAI endpoint access |

> **CRITICAL:** The agent's identities need `Azure AI User` on BOTH the account AND the
> project. Missing either causes `PermissionDenied` / 401 errors at runtime — the platform's
> internal `FoundryStorageProvider` calls `storage/history/item_ids` and gets 401 if RBAC
> is missing.
>
> **RBAC propagation takes 5-15 minutes** for newly created Entra service principals.
> If you get persistent 401s after deploying, wait and retry. If still failing after 15 min,
> redeploy the agent (`azd deploy <service>`) to force a new session.

### How to assign RBAC post-deploy

After `azd up` deploys the agent, read the identity from `azd ai agent show`:

```bash
# Get agent identities
azd ai agent show
# Look for instance_identity.principal_id and blueprint.principal_id

# Assign to both identities (replace <PRINCIPAL_ID> with each)
ACCOUNT_SCOPE="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
PROJECT_SCOPE="$ACCOUNT_SCOPE/projects/<project>"

az role assignment create --assignee <PRINCIPAL_ID> --role "Azure AI User" --scope $ACCOUNT_SCOPE
az role assignment create --assignee <PRINCIPAL_ID> --role "Azure AI User" --scope $PROJECT_SCOPE
az role assignment create --assignee <PRINCIPAL_ID> --role "Cognitive Services OpenAI User" --scope $ACCOUNT_SCOPE
```

> **Reference**: [Hosted agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions)

### Agent Invocation (Refreshed Preview)

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="<project_endpoint>",
    credential=DefaultAzureCredential(),
    allow_preview=True,  # REQUIRED for agent_name parameter
)

# Agent-bound client — routes to dedicated endpoint automatically
oai = project.get_openai_client(agent_name="my-agent")
response = oai.responses.create(input="Hello!", stream=False)
print(response.output_text)
```

> **Note:** `allow_preview=True` is required on `AIProjectClient` for the `agent_name`
> parameter. Without it, the SDK doesn't route to the agent's dedicated endpoint.
>
> **REST invocation** requires the `Foundry-Features: HostedAgents=V1Preview` header:
> ```
> curl -X POST "$BASE_URL/agents/my-agent/endpoint/protocols/openai/responses?api-version=2025-11-15-preview" \
>   -H "Authorization: Bearer $TOKEN" \
>   -H "Foundry-Features: HostedAgents=V1Preview" \
>   -d '{"input": "Hello!", "stream": false}'
> ```

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

### Region Availability

Not all regions support hosted agents. If you get `"The requested experience is not
available for this subscription"` during `azd deploy`, try a different region.

**Known working regions (April 2026):** `northcentralus`, `eastus`, `swedencentral`, `westus`
**Known failing regions:** `eastus2` (returned "experience not available" in testing)

> Always check [Region availability](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#region-availability)
> for the latest supported regions.

---

## Reference: MCP ACA Deployment

For Cosmos DB or custom data stores, deploy an MCP server as an Azure Container App.

### Option A: Shared .NET MCPToolKit (Cosmos DB)

A pre-built .NET Cosmos DB MCPToolKit image provides 10 tools:

| Tool | Type | Purpose |
|------|------|---------|
| `list_databases` | Read | List all Cosmos databases |
| `list_collections` | Read | List containers in a database |
| `find_document_by_id` | Read | Get single document by id |
| `text_search` | Read | Text search across documents |
| `query_documents` | Read | SQL query against a container |
| `get_approximate_schema` | Read | Infer schema from sample docs |
| `get_recent_documents` | Read | Get N most recent documents |
| `vector_search` | Read | Semantic vector search |
| `upsert_document` | Write | Create or update a document |
| `delete_document` | Write | Delete a document by id |

Deploy per-project ACA with env vars: `COSMOS_ENDPOINT`, `COSMOS_DATABASE`,
`COSMOS_AUTH_KEY`, `DEV_BYPASS_AUTH`. Source: `cosmos-mcp-toolkit/` in repo root.

### Option B: Azure Functions (Consumption)

```bash
azd init --template remote-mcp-functions-python -e my-mcp-server
func start                    # Test locally
azd up                        # Deploy to Azure
# Endpoint: https://{app}.azurewebsites.net/runtime/webhooks/mcp
```

### Option C: Custom ACA

Build a custom Docker image with your MCP tools and deploy as ACA.
The agent connects via `mcp-config.json` with `${ENV_VAR}` URLs.

### MCP Server Requirements (for container-level MCP)

- Must handle ALL 6 JSON-RPC methods (initialize, notifications/initialized,
  tools/list, prompts/list, resources/list, logging/setlevel)
- Must return HTTP 200 for all methods (even if body is empty `{}`)
- Use Streamable HTTP transport (HTTP POST with JSON-RPC at `/mcp`)
- Port 8080 is convention for ACA MCP servers
- Health endpoint at `/health` (separate from MCP protocol)

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
# azure.yaml — agent service declaration
services:
  my-agent:
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
            version: "2026-03-05"
          name: gpt-5.4-mini
          sku:
            capacity: 120
            name: GlobalStandard
```

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
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": "gpt-5.4-mini",
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

## Phase 4: Teams Bot (included in scaffold)

The Teams bot is deployed automatically as part of the scaffold (Phase 5). The bot
code lives in `copilot/` and connects Teams users to the Foundry hosted agent.

> **Full code templates**: See `references/scaffold/copilot/` for bot.py, app.py,
> Dockerfile, and requirements.txt. See `references/teams-bot-reference.md` for
> additional details on manifest and sideloading.

### Architecture

```
Teams → Azure Bot Service (UAMI) → Bot ACA (copilot/bot.py) → Foundry Hosted Agent
```

### What the scaffold provides:

1. **`copilot/bot.py`** — Streams responses from the hosted agent to Teams
   - Uses `get_openai_client(agent_name=...)` for agent-bound invocation
   - Collects all chunks into a single message before sending
2. **`copilot/app.py`** — aiohttp server on port 80 with `/api/messages` and JWT auth
3. **`copilot/Dockerfile`** — python:3.12-slim, port 80
4. **`copilot/requirements.txt`** — microsoft-agents-* SDK + azure-identity + openai
5. **`infra/bot/bot-service.bicep`** — Azure Bot Service with UAMI auth + MsTeamsChannel
6. **`infra/bot/aca.bicep`** — ACA environment + bot container app (external ingress)

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
├── agent.yaml                # Agent definition (ContainerAgent schema — kind/protocols/resources at TOP LEVEL)
├── azure.yaml                # azd config — extension declares agent + bot services
├── infra/
│   ├── main.bicep            # Subscription-scope orchestrator (starter-basic + bot)
│   ├── main.parameters.json  # azd env var bindings
│   ├── abbreviations.json    # azd naming conventions
│   ├── bot/                  # Teams bot infrastructure
│   │   ├── uami.bicep        # User-Assigned Managed Identity (for Bot Service auth)
│   │   ├── aca.bicep         # ACA environment + bot container app
│   │   ├── bot-service.bicep # Azure Bot Service + MsTeamsChannel
│   │   └── fetch-container-image.bicep  # Prevents image overwrite on reprovision
│   └── core/                 # Vendored from azd-ai-starter-basic (DO NOT MODIFY)
│       ├── ai/               # Foundry project, connections, ACR role assignment
│       ├── host/             # ACR creation
│       ├── monitor/          # Log Analytics + Application Insights
│       ├── search/           # AI Search + Bing (optional, used if configured)
│       └── storage/          # Storage account (optional, used if configured)
├── scripts/
│   └── build_teams_manifest.py  # postprovision: builds copilot_package.zip for Teams sideloading
└── copilot/                  # Teams bot code
    ├── bot.py                # Streaming handler (Foundry → Teams via AIProjectClient)
    ├── app.py                # aiohttp server (/api/messages + JWT auth)
    ├── Dockerfile            # python:3.12-slim, port 80
    ├── requirements.txt      # microsoft-agents-* + azure-ai-projects SDK
    └── teams_package/        # Teams manifest template (filled at postprovision)
        ├── manifest.json     # devPreview schema with __BOT_APP_ID__ placeholders
        ├── color.png         # 192×192 app icon
        └── outline.png       # 32×32 outline icon
```

### Step 2: Replace placeholder tokens

Replace these tokens **in all copied files**:

| Token | Value | Source | Files |
|-------|-------|--------|-------|
| `__PROJECT_NAME__` | kebab-case agent name (e.g., `tech-news-digest`) | AGENTS.md | `agent.yaml`, `azure.yaml`, `copilot/bot.py`, `pyproject.toml` |
| `__AGENT_DESCRIPTION__` | One-line agent description | AGENTS.md | `agent.yaml` |
| `__AGENT_NAME__` | Display name (e.g., `Tech News Digest`) | AGENTS.md | `infra/bot/bot-service.bicep` |
| `__MODEL_NAME__` | Model name (default: `gpt-5.4`) | AGENTS.md or default | `azure.yaml` |
| `__MODEL_DEPLOYMENT_NAME__` | Model deployment name (default: same as `__MODEL_NAME__`) | AGENTS.md or default | `agent.yaml` |
| `__MODEL_VERSION__` | Model version — **must match model name** (see lookup table below) | Azure model catalog | `azure.yaml` |
| `__MODEL_CAPACITY__` | TPM capacity (default: `120`) | Default | `azure.yaml` |
| `__DEVELOPER_NAME__` | Developer/org name for Teams manifest | User/org | `copilot/teams_package/manifest.json` |
| `__BOT_APP_ID__` | UAMI client ID for bot (replaced at postprovision) | Bicep output | `copilot/teams_package/manifest.json` |

> **Note**: Model deployment is now declared in `azure.yaml` `config.deployments` —
> NOT in Bicep. The `azd ai agent` extension handles model creation via pre-provision hooks.

#### Model Version Lookup Table

**`__MODEL_VERSION__` depends on the model** — using the wrong version causes
`DeploymentModelNotSupported` errors. Look up the correct version here:

| Model Name | Version | SKU |
|-----------|---------|-----|
| `gpt-5.4` | `2026-03-05` | GlobalStandard |
| `gpt-5.4-pro` | `2026-03-05` | GlobalStandard |
| `gpt-5.4-mini` | `2026-03-17` | GlobalStandard |
| `gpt-5.4-nano` | `2026-03-17` | GlobalStandard |
| `gpt-5.3-codex` | `2026-02-24` | GlobalStandard |
| `gpt-5.3-chat` | `2026-03-03` | GlobalStandard |
| `gpt-5.2` | `2025-12-11` | GlobalStandard |
| `gpt-5.2-codex` | `2026-01-14` | GlobalStandard |
| `gpt-5.2-chat` | `2025-12-11` | GlobalStandard |
| `gpt-5.1` | `2025-11-13` | GlobalStandard |
| `gpt-5.1-codex` | `2025-11-13` | GlobalStandard |
| `gpt-5` | `2025-08-07` | GlobalStandard |
| `gpt-5-mini` | `2025-08-07` | GlobalStandard |
| `gpt-5-nano` | `2025-08-07` | GlobalStandard |
| `gpt-4.1` | `2025-04-14` | GlobalStandard |
| `gpt-4.1-mini` | `2025-04-14` | GlobalStandard |
| `gpt-4.1-nano` | `2025-04-14` | GlobalStandard |

> **Source**: [Azure OpenAI Models](https://learn.microsoft.com/azure/ai-services/openai/concepts/models).
> Versions change when new model releases are published — always verify against the
> current catalog before deploying. If unsure, run:
> `az cognitiveservices account list-models --resource-group <rg> --name <account> --query "[?contains(model.name,'gpt-5.4')].{name:model.name,version:model.version}" -o table`

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
  │   └── scripts/build_teams_manifest.py → copilot/copilot_package.zip
  │
  ├── azd ai agent extension (automatic) →
  │   ├── Deploys model from azure.yaml config.deployments
  │   ├── Builds agent container remotely via ACR
  │   └── Creates hosted agent version in Foundry
  │
  └── azd deploy → builds bot container, deploys to ACA
      ├── Builds copilot/ container via ACR remote build
      └── Deploys to Bot ACA (external ingress)
```

### Complete output structure

After all phases, the project should contain:

```
project/
├── AGENTS.md               # Original design (unchanged)
├── .github/skills/          # Original skills (unchanged)
├── config/                  # Original config (unchanged)
│
├── agent.yaml              # Phase 5: agent definition (REQUIRED by extension)
├── azure.yaml              # Phase 5: azd config (extension + bot + postprovision hook)
├── infra/                  # Phase 5: vendored Bicep (core/ + bot/)
├── scripts/
│   └── build_teams_manifest.py  # Phase 5: postprovision → copilot_package.zip
├── copilot/                # Phase 5: Teams bot (4 files + teams_package/)
│   └── teams_package/      # Teams manifest template + icons
│
├── container.py            # Phase 2: MAF runtime (Agent + FoundryChatClient + ResponsesHostServer)
├── Dockerfile              # Phase 2: agent container (uv-based)
├── pyproject.toml          # Phase 2: agent dependencies (uv + prerelease)
├── copilot-instructions.md # Phase 2: runtime system prompt
├── skills/                 # Phase 2: copied skills (loaded into instructions at startup)
├── mcp-config.json         # Phase 2: MCP server config
└── deploy-notes.md         # Phase 5: deployment guide
```

---

## Gotchas & Hard-Won Lessons

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent returns empty responses | TPM too low — 429 rate limits | Use ≥300K TPM deployment |
| **`FOUNDRY_PROJECT_ENDPOINT` in agent.yaml** | **All `FOUNDRY_*` and `AGENT_*` env vars are reserved by the platform (injected automatically)** | **Remove from `environment_variables` in agent.yaml. Container reads it via `os.environ` at runtime.** |
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
| `azd ai agent` extension missing | Extension not installed | `azd extension install azure.ai.agents` (ensure ≥0.1.27-preview) |
| Bot image overwritten on reprovision | Bicep resets container image | fetch-container-image.bicep + `SERVICE_BOT_RESOURCE_EXISTS` param |
| Skills not loading | Wrong directory path | Must be `skills/` relative to `/app/` |
| Import errors crash container | Missing dependency in pyproject.toml | Diagnostic HTTP server keeps container alive |
| Bot returns "Response could not be saved" | Old-style `agent_reference` invocation | Use `get_openai_client(agent_name=...)` with `allow_preview=True` |
| Bot auth 401 on /api/messages | UAMI not in CONNECTIONS__ env vars | Set all 3 `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` vars |
| Teams can't find bot | manifest botId mismatch | `botId` must equal UAMI client ID used as `msaAppId` |
| Streaming garbled in Teams | Sending each chunk separately | Collect all chunks, send as single message |
| `azd deploy` fails with Docker error | Missing `remoteBuild: true` in azure.yaml | Add `remoteBuild: true` under `docker:` — azd builds via ACR Tasks, no local Docker |
| **Model deployments not created** | **`azd deploy` doesn't create model deployments — only `azd provision`** | **Run `azd up` (full) or `azd provision` to create model deployments** |
| **Compute not starting** | Agent not invoked yet | Refreshed preview provisions compute on first request; deprovisions after 15min idle |
| **Protocol version error** | Using old `"v1"` format | Use semver `"1.0.0"` in agent.yaml and SDK code |
| **`postdeploy` fails with AZURE_TENANT_ID** | Extension postdeploy hook expects tenant ID for RBAC auto-assignment | **Set `AZURE_TENANT_ID` in azd env. Without it, postdeploy can't assign `Azure AI User` to agent identity → runtime 401 on storage** |
| **Two identities in `azd ai agent show`** | Refreshed preview creates `instance_identity` + `blueprint` per agent | Both need RBAC — assign same roles to both principal IDs |
| **MCP `server_url` invalid URI error** | `${ENV_VAR}` in mcp-config.json not set → expands to empty string → `/mcp` is not a valid URI | **Only include MCP servers with deployed endpoints. Remove entries with unresolved env vars. The container skips empty URLs, but `FoundryChatClient.get_mcp_tool()` registers them and Foundry rejects at runtime.** |
| **Deployer needs `Azure AI Project Manager`** | The extension postdeploy hook auto-assigns `Azure AI User` to agent identity, but needs role-assignment permission to do so | **Assign `Azure AI Project Manager` to deployer on Foundry project scope. Also set `AZURE_TENANT_ID` in azd env.** |

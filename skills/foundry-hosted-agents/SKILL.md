---
name: foundry-hosted-agents
description: >
  Deploy, evaluate, and manage Foundry agents end-to-end: Docker build, ACR push,
  hosted/prompt agent create, container start, batch eval, prompt optimization,
  agent.yaml, dataset curation from traces. Covers the refreshed hosted agents
  preview (April 2026): Agent + FoundryChatClient + ResponsesHostServer pattern,
  azd ai agent extension, identity model, RBAC, and troubleshooting.
---

# Microsoft Foundry Hosted Agents — Reference Guide

Production-tested patterns for deploying hosted agents on Microsoft Foundry
(refreshed preview, April 2026). Covers the `Agent` + `FoundryChatClient` +
`ResponsesHostServer` (MAF) variant exclusively.

## When to Use

- Deploying a custom container agent to Foundry
- Debugging hosted agent failures (401, 500, import errors)
- Setting up RBAC for agent identities
- Configuring `agent.yaml`, `azure.yaml`, Bicep parameters
- Understanding the refreshed preview changes (packages, identity, invocation)

---

## Runtime Pattern (MAF Variant)

> **Model selection (verified May 2026, card-dispute v3 PoC).** Default
> to **`gpt-5.4`** for production agents that run instruction chains
> with 10+ tool steps (case investigation, multi-source RAG synthesis,
> regulatory drafting). Use **`gpt-5.4-mini`** only for trivial
> 1-2-step flows (single-tool lookups, formatters). The mini variant's
> tool-call discipline degrades sharply on long chains: in the v3 PoC,
> strict-smoke reproducibility on a 7-skill flow went from **1/3** with
> gpt-5.4-mini to **3/3** with gpt-5.4 (same MCP server, same prompts).
> The mini variant tends to call commit-style tools before evidence is
> gathered — partially mitigated by the validate-or-reject pattern in
> `foundry-mcp-aca`, but gpt-5.4 still fixes the root cause.
>
> **Cost/latency note.** `gpt-5.4` GlobalStandard at 50 capacity costs
> a few cents per scenario at idle the deployment ticks negligibly,
> so the typical pilot cost is dominated by the scenarios you actually
> run. Don't downgrade to mini just to save on the deployment standby.

```python
import os
from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from pydantic import Field
from typing import Annotated

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

@tool(approval_mode="never_require")
def my_tool(query: Annotated[str, Field(description="Input")]) -> str:
    """Tool description."""
    return "result"

agent = Agent(
    client=client,
    instructions="You are a helpful assistant.",
    tools=[my_tool],
    default_options={"store": False},  # Platform manages history
)

server = ResponsesHostServer(agent)
server.run()  # Serves on port 8088
```

**Key points:**
- `FOUNDRY_PROJECT_ENDPOINT` is **injected by the platform** — never declare in agent.yaml
- `default_options={"store": False}` — hosting platform manages conversation history
- `ResponsesHostServer` handles liveness/readiness probes natively
- `DefaultAzureCredential` resolves to the container's App Service managed identity
- Custom tools use `@tool(approval_mode="never_require")` with `Annotated` type hints

### Multi-Agent: Calling Other Foundry Agents as Tools

Use the **client-swap pattern** to connect to existing prompt/hosted agents in the same project:

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.ai.projects.aio import AIProjectClient  # MUST be .aio (async)!
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
    allow_preview=True,  # REQUIRED for agent_name parameter
)

# Create FoundryChatClient, swap its OpenAI client to the agent-bound one
sub_client = FoundryChatClient(project_client=project_client, model="gpt-5.4-mini")
sub_client.client = project_client.get_openai_client(agent_name="my-sub-agent")

sub_agent = Agent(name="my-sub-agent", client=sub_client)

orchestrator = Agent(
    client=FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model="gpt-5.4-mini",
        credential=DefaultAzureCredential(),
    ),
    instructions="You orchestrate sub-agents.",
    tools=[sub_agent.as_tool()],
    default_options={"store": False},
)

ResponsesHostServer(orchestrator).run()
```

**Critical rules:**
- `AIProjectClient` MUST be from `azure.ai.projects.aio` (async) — the sync version returns a sync `OpenAI` client that **silently fails** inside `FoundryChatClient`
- `allow_preview=True` is REQUIRED for `agent_name` to work
- `FoundryChatClient` does NOT accept `agent_name`/`agent_version` — use the client-swap pattern

> **⚠️ DO NOT use `FoundryAgent` for sub-agent delegation.** `FoundryAgent` (v1.1.1) internally
> uses `extra_body={"agent_reference": ...}` which is the OLD initial preview pattern.
> It silently fails in the refreshed preview — tool calls return "Function failed."
> Use the client-swap pattern above instead.

### MCP Tools via FoundryChatClient

> **🔴 Known issue (v1.1.1 + v1.3.0 — bug-009/014).** The
> `client.get_mcp_tool()` path renders MCP `CallToolResult` content as
> `[<Content object at 0x...>]` Python reprs in the model's view. The
> model reads that as "tool failed" and hallucinates an apology even
> though the underlying MCP call succeeded and returned valid JSON.
> Bug confirmed unresolved across two `agent_framework` releases; the
> fix MUST be on the agent client side — server-side `json.dumps(...)`
> is a no-op because the wrapping happens client-side. **Use the
> `MCPStreamableHTTPTool + parse_tool_results` pattern below instead
> — see § "MCP Tools — recommended pattern".**

```python
# 🔴 BUGGY — triggers serialization bug; do not use until upstream fix
mcp_tool = client.get_mcp_tool(
    name="my-mcp",
    url="https://my-mcp-server.azurecontainerapps.io/mcp",
    headers={"Authorization": f"Bearer {token}"},
    approval_mode="never_require",
)
agent = Agent(client=client, tools=[my_tool, mcp_tool], ...)
```

> **URL must be a valid URI** (starts with `http://` or `https://`). Unresolved
> `${ENV_VAR}` placeholders that expand to empty strings cause `invalid_payload`
> errors at runtime.

### MCP Tools — recommended pattern (`MCPStreamableHTTPTool` + `parse_tool_results`)

Use `MCPStreamableHTTPTool` directly with a custom `parse_tool_results`
callback that extracts the `TextContent.text` payload from the MCP
`CallToolResult` and surfaces it to the model as plain JSON. This
sidesteps `FoundryChatClient.get_mcp_tool()` entirely and avoids the
`[<Content object>]` repr leak.

**Worked example** — verified live in card-dispute v3 PoC
(`threadlight-skills/card-dispute-investigation/src/agent/container.py`),
running on a 10-tool MCP server with `gpt-5.4-mini`:

```python
import json
from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def _mcp_text_extractor(result):
    """Convert an MCP CallToolResult into the plain JSON string the model expects.

    Without this callback, agent_framework's default rendering of MCP results
    leaks the Python repr of `[<Content object>]` into the model's view, which
    gpt-5.4-mini reads as a tool failure. We surface the first TextContent
    payload (which the MCP server returns as `json.dumps(...)`) verbatim.
    """
    if getattr(result, "isError", False):
        return json.dumps({
            "error": "mcp_tool_error",
            "content": [str(c) for c in (result.content or [])],
        })
    for c in result.content or []:
        text = getattr(c, "text", None)
        if isinstance(text, str) and text:
            return text
    sc = getattr(result, "structuredContent", None)
    if sc is not None:
        return json.dumps(sc, default=str)
    return json.dumps({"_empty": True})


client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)

mcp_tool = MCPStreamableHTTPTool(
    name="card_disputes_mcp",
    url=f"https://{os.environ['MCP_SERVER_FQDN']}/mcp",
    approval_mode="never_require",
    parse_tool_results=_mcp_text_extractor,   # ⚠️ THE FIX — opts out of default rendering
    request_timeout=60,
)

agent = Agent(client=client, tools=[my_local_tool, mcp_tool], ...)
```

**Why this works:**
- `MCPStreamableHTTPTool` is the lower-level MAF primitive that
  `client.get_mcp_tool()` wraps — bypassing the wrapper avoids the
  buggy renderer.
- `parse_tool_results` is invoked by MAF on every tool result before
  it's rendered into the model's history; returning a plain string
  makes that string what the model sees verbatim.
- The MCP server should return `json.dumps(...)` from each tool
  handler (FastMCP wraps it as a single `TextContent`); the extractor
  unwraps that back to the JSON string.

**When pure-compute logic doesn't need to be on the MCP server,
inline it as `@tool`.** The MCP-vs-`@tool` rule from card-dispute v3:
- **MCP server** for any tool with I/O (DB lookups, file reads,
  external API calls).
- **Inline `@tool`** for pure computation (date math, formatting,
  validation) — cheaper round-trip, no HTTP hop.

**Probe to verify the fix is in place** — dump the raw
`custom_tool_call_output` from a real Foundry trace; the `output`
field should be a plain JSON string (e.g. `{"case_id":"...","status":"..."}`),
NOT `[<agent_framework._types.Content object at 0x...>]`. The
card-dispute PoC ships `tests/probe_mcp_output.py` for this.

> **Status note.** Once the upstream `agent_framework` bug is fixed
> (track at `microsoft-foundry/foundry-samples` issues), the
> `client.get_mcp_tool()` shorthand becomes safe again. Until then,
> the explicit `MCPStreamableHTTPTool` + extractor is the canonical
> pattern. Captured as `gap-009` + `gap-014` in the card-dispute PoC
> retrospective.

### File Generation (@tool pattern)

Agents can generate downloadable files (XLSX, PDF, CSV, HTML) using a custom `@tool`.
Files are written to `$HOME` inside the container; the hosting platform exposes them
via the session files API, and the Teams bot delivers them via FileConsentCard
(see [foundry-teams-bot skill](#sending-files-to-teams)).

```python
@tool(approval_mode="never_require")
def save_report(
    filename: Annotated[str, Field(description="Filename (e.g. report.xlsx, summary.pdf)")],
    content: Annotated[str, Field(description="File content: CSV text, JSON for XLSX, HTML for pdf")],
    format: Annotated[str, Field(description="Format: csv, xlsx, html, or pdf")] = "csv",
) -> str:
    """Save a report file that the user can download."""
    from pathlib import Path
    home = Path.home()
    filepath = home / filename

    if format == "xlsx":
        import openpyxl
        import json as _json
        data = _json.loads(content)
        wb = openpyxl.Workbook()
        ws = wb.active
        if data and isinstance(data, list):
            ws.append(list(data[0].keys()))
            for row in data:
                ws.append(list(row.values()))
        wb.save(str(filepath))
    elif format == "pdf":
        from fpdf import FPDF
        import re
        # Strip CSS but keep structural HTML for write_html()
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", content, flags=re.DOTALL)
        cleaned = re.sub(r'\s+(class|style|id)="[^"]*"', "", cleaned)
        cleaned = cleaned.replace("<table", '<table border="1" width="100%"')
        cleaned = cleaned.replace("<th", '<th bgcolor="#d0d0d0"')
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "", 10)
        pdf.write_html(cleaned)
        pdf.output(str(filepath))
    else:
        filepath.write_text(content, encoding="utf-8")

    return f"Report saved: {filename} ({filepath.stat().st_size:,} bytes). User can download it."
```

**Required dependencies** in `pyproject.toml`:

```toml
dependencies = [
    # ... agent-framework packages ...
    "openpyxl>=3.1.0",   # XLSX generation
    "fpdf2>=2.8.0",      # PDF generation (pure Python, no system deps)
]
```

**Instructions directive** — add to `copilot-instructions.md`:

```markdown
## Report Generation

You have a `save_report` tool for generating downloadable files:
- **XLSX**: JSON array of objects → `save_report(filename="report.xlsx", content=json_data, format="xlsx")`
- **PDF**: HTML content → `save_report(filename="report.pdf", content=html, format="pdf")`
- **CSV**: Raw CSV text → `save_report(filename="report.csv", content=csv, format="csv")`
- **HTML**: HTML content → `save_report(filename="report.html", content=html, format="html")`
```

**Key points:**
- `fpdf2` is pure Python — no Playwright, wkhtmltopdf, or headless Chrome needed
- `fpdf2.write_html()` renders HTML tables with borders and header highlighting
- Files written to `Path.home()` are automatically available via the session files API
- The bot captures `agent_session_id` from the `response.completed` event to locate files
- Wrap each format in try/except to return a clean error if generation fails

> **Validated** — XLSX and PDF file delivery tested end-to-end in Imperial Commercial
> Sales PoC (May 2026). FileConsentCard renders clickable OneDrive cards in Teams.

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "my-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "agent-framework-core==1.3.0",
    "agent-framework-foundry==1.3.0",
    "agent-framework-foundry-hosting>=1.0.0a260421",
    "azure-ai-projects>=2.1.0",
    "azure-identity>=1.19.0,<1.26.0a0",
    "mcp>=1.10.0",
    "python-dotenv>=1.0.0",
    # Add these if using save_report file generation:
    # "openpyxl>=3.1.0",   # XLSX
    # "fpdf2>=2.8.0",      # PDF (pure Python)
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"

[tool.setuptools]
packages = []
```

**Do NOT use `agent-framework>=1.1.0` as a meta-package.** The meta-package's transitive
resolution is non-deterministic across uv versions. Pin `agent-framework-core==1.3.0` and
`agent-framework-foundry==1.3.0` exactly instead. Verified working on linux/amd64 as the
card-dispute-investigation reference shape (May 2026 — supersedes the prior 1.1.1 pinning
guidance, which became fragile once `agent-framework-foundry-hosting` advanced its
transitive pins).

**Mandatory adjacent rules** (lessons from KYC v6-v9 burn cycle):
- **Drop** any explicit `azure-ai-agentserver-responses` line — `agent-framework-foundry-hosting`
  pins the right transitive itself; declaring it explicitly causes uv to resolve a stack that
  passes install but crashes at first invocation with opaque `server_error/model:""`.
- **Add** explicit `mcp>=1.10.0` whenever using `MCPStreamableHTTPTool`. `agent-framework-core 1.3.0`
  does NOT auto-pull it.
- **Include** `[tool.setuptools] packages = []` for clean uv resolution.

**`prerelease = "if-necessary-or-explicit"` is correct** — packages with explicit
prerelease markers (e.g. `>=1.0.0a260421`) resolve to prereleases; everything else
stays GA. Do NOT use `"allow"` — it pulls beta azure-identity 1.26.0b2.

### Dependency Chain (verified on PyPI, May 2026 — card-dispute proven)

| Package | Version | Type | Pulls in |
|---------|---------|------|----------|
| `agent-framework-core` | 1.3.0 | ✅ Stable | pydantic, opentelemetry-api |
| `agent-framework-foundry` | 1.3.0 | ✅ Stable | core, openai, azure-ai-projects |
| `agent-framework-foundry-hosting` | 1.0.0a260423 | ⚠️ Alpha | agentserver-core==2.0.0b2, agentserver-responses==1.0.0b4 |
| `mcp` | ≥1.10.0 | ✅ Stable | Required by MCPStreamableHTTPTool — NOT auto-pulled by core 1.3.0 |
| `azure-identity` | 1.25.3 | ✅ Stable (pinned `<1.26.0a0` to avoid beta) | |

No `override-dependencies` needed — the hosting package pins its own transitive deps.

### Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project && rm -rf /root/.cache
COPY container.py .
COPY copilot-instructions.md .
EXPOSE 8088
CMD [".venv/bin/python", "container.py"]
```

- Port 8088 is the standard Foundry agent port
- `--platform linux/amd64` only needed for local builds
- `azd deploy` builds remotely via ACR — no local Docker needed

---

## agent.yaml (ContainerAgent Schema)

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml

name: my-agent
description: My agent description
kind: hosted
protocols:
  - protocol: responses
    version: 1.0.0
environment_variables:
  - name: MODEL_DEPLOYMENT_NAME
    value: gpt-5.4   # default for production; use gpt-5.4-mini only for trivial 1-2-step flows
resources:
  cpu: "1"
  memory: 2Gi
```

### Critical Rules

| Rule | Why |
|------|-----|
| `kind: hosted` at **top level** | ContainerAgent schema — NOT nested under `template:` |
| Protocol version `1.0.0` | Semver format — NOT `"v1"` (old preview) |
| `resources: {cpu, memory}` flat object | NOT a YAML list `[{kind: model}]` |
| NO `FOUNDRY_PROJECT_ENDPOINT` | Reserved — platform injects it. All `FOUNDRY_*` and `AGENT_*` prefixed vars are reserved |
| NO `APPLICATIONINSIGHTS_CONNECTION_STRING` | Also reserved (verified 2026-05-12, req `820a502e2facc8e1cf46eb3ae71ea26e`). Platform attempts to auto-inject from the account-level `AppInsights` connection — but auto-injection is **best-effort**, can silently fail (see Troubleshooting), and you CANNOT escape-hatch via `agent.yaml`. Use guarded `_init_telemetry()` in `container.py` so the agent survives the failure (see `foundry-observability` gap rows O-011 / O-012) |
| Model deployment in `azure.yaml` | NOT in agent.yaml — declared in `config.deployments` |

> **Two schemas exist — don't confuse them:**
> - `agent.yaml` → **ContainerAgent** schema (what `azd ai agent` extension reads)
> - `agent.manifest.yaml` → foundry-samples format (for sample repos, NOT azd)

---

## azure.yaml (azd ai agent Extension)

```yaml
name: my-project

requiredVersions:
  extensions:
    azure.ai.agents: ">=0.1.25-preview"

services:
  my-agent:
    project: .
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
            name: gpt-5.4
            version: "2026-03-05"
          name: gpt-5.4
          sku:
            capacity: 50
            name: GlobalStandard

infra:
  provider: bicep
  path: ./infra
```

### Model Version Lookup

| Model | Version |
|-------|---------|
| `gpt-5.4` | `2026-03-05` |
| `gpt-5.4-mini` | `2026-03-17` |
| `gpt-5.4-nano` | `2026-03-17` |
| `gpt-5.3-codex` | `2026-02-24` |
| `gpt-5.2` | `2025-12-11` |
| `gpt-5` | `2025-08-07` |
| `gpt-5-mini` | `2025-08-07` |
| `gpt-4.1` | `2025-04-14` |
| `gpt-4.1-mini` | `2025-04-14` |

Verify with: `az cognitiveservices account list-models --resource-group <rg> --name <account> -o table`

---

## Bicep Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `ENABLE_HOSTED_AGENTS` | `false` → set `true` by extension | Enables hosted agent infrastructure |
| `ENABLE_CAPABILITY_HOST` | **`false`** ⚠️ | **MUST be false.** Capability hosts were removed in refreshed preview |
| `ENABLE_MONITORING` | `true` | Application Insights + Log Analytics |

---

## Identity & RBAC

### Agent Identities

Each hosted agent gets **two Entra identities** at deploy time:

| Identity | Field | Purpose |
|----------|-------|---------|
| Instance identity | `instance_identity.principal_id` | Agent's service principal for runtime |
| Blueprint identity | `blueprint.principal_id` | Platform internal operations |

View them with `azd ai agent show`.

> **⚠️ ServiceIdentity Cosmos limitation (gap-003 from card-dispute v3
> PoC).** The instance identity has `servicePrincipalType=ServiceIdentity`,
> which the Cosmos DB data-plane RBAC engine **does not accept** — direct
> role assignments fail with `unsupported type [Unfamiliar]`. The same
> holds for Azure AI Search data-plane in some configurations.
> **Workaround:** route Cosmos / Search access through an MCP server
> backed by a **separate User-Assigned Managed Identity (UAMI)**. Grant
> the data-plane role to that UAMI, give the agent only the MCP tool;
> the agent never touches the data plane directly. Captured as
> `gap-003` in the card-dispute PoC retrospective.

### Required Role Assignments

**Deploying user:**

| Role | Scope | Why |
|------|-------|-----|
| `Azure AI Project Manager` | Foundry project | Create agents + auto-assign RBAC to agent identity |
| `Contributor` | Resource group | Provision Azure resources |

**Agent identities (both instance + blueprint):**

| Role | Scope | Why |
|------|-------|-----|
| `Azure AI User` | Foundry account | Model inference |
| `Azure AI User` | Foundry project | Storage, history, project-scoped APIs |

**Project managed identity:**

| Role | Scope | Why |
|------|-------|-----|
| `Azure AI User` | Foundry account | Model inference via project endpoint |
| `Container Registry Repository Reader` | ACR | Pull container images |

### Auto-Assignment via postdeploy Hook

The `azd ai agent` extension's postdeploy hook **automatically assigns** `Azure AI User`
to the agent identity. For this to work, you need:

1. `Azure AI Project Manager` role on the Foundry project
2. `AZURE_TENANT_ID` set in azd env: `azd env set AZURE_TENANT_ID <tenant-id>`

Without both, postdeploy fails silently and the agent gets 401 at runtime.

### Manual RBAC Assignment (if postdeploy failed)

```bash
# Get agent identities
azd ai agent show
# → instance_identity.principal_id and blueprint.principal_id

ACCT="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
PROJ="$ACCT/projects/<project>"

# For EACH principal ID:
az role assignment create --assignee <PRINCIPAL_ID> --role "Azure AI User" --scope $ACCT
az role assignment create --assignee <PRINCIPAL_ID> --role "Azure AI User" --scope $PROJ
```

> RBAC propagation takes **5-15 minutes** for new service principals. If still failing,
> redeploy (`azd deploy <service>`) to force a new container session.

---

## Deployment Flow

```
azd up
  ├── provision → Bicep (Foundry account, project, ACR, monitoring)
  ├── postprovision hooks (if any)
  ├── azd ai agent extension →
  │   ├── Deploy model (from azure.yaml config.deployments)
  │   ├── Build container remotely via ACR
  │   ├── Create hosted agent version
  │   └── postdeploy → auto-assign Azure AI User to agent identity
  └── deploy other services (bot ACA, etc.)
```

### Invocation

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="<project_endpoint>",
    credential=DefaultAzureCredential(),
    allow_preview=True,  # REQUIRED for agent_name
)
oai = project.get_openai_client(agent_name="my-agent")
response = oai.responses.create(input="Hello!", stream=False)
print(response.output_text)
```

Or via CLI: `azd ai agent invoke "Hello!"`

Or via REST (requires `Foundry-Features: HostedAgents=V1Preview` header):
```
POST {project_endpoint}/agents/{name}/endpoint/protocols/openai/responses
```

### Compute Lifecycle

- **Automatic** — no manual start/stop
- Provisions on first request
- Deprovisions after 15 minutes of inactivity
- No replica management

---

## Region Availability

Not all regions support hosted agents. If you get `"The requested experience is
not available for this subscription"`, try a different region.

**Known working (April 2026):** `northcentralus`, `eastus`, `swedencentral`, `westus`
**Known failing:** `eastus2`

Check [Region availability](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#region-availability) for current list.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `FOUNDRY_PROJECT_ENDPOINT is reserved` | Declared in agent.yaml env vars | Remove it — platform injects automatically |
| `AGENT_* env var is reserved` | All `FOUNDRY_*` and `AGENT_*` prefixed vars are reserved | Use a different prefix (e.g. `TL_SUB_AGENTS`) |
| `session_not_ready` (424) | Container crashed before readiness probe | Check logstream: `curl ...sessions/{sid}:logstream`. Common causes: import error, sync/async mismatch, missing dep |
| Sub-agent tool calls return "Function failed" | `FoundryAgent` uses old `agent_reference` pattern | Use the client-swap pattern: `sub_client.client = project_client.get_openai_client(agent_name=...)` |
| Sub-agent calls silently fail (empty output) | `AIProjectClient` imported from sync (`azure.ai.projects`) | MUST use `azure.ai.projects.aio` — sync `get_openai_client` returns sync OpenAI which fails in async `FoundryChatClient` |
| `PermissionDenied: Principal does not have access` | Agent identity missing `Azure AI User` (53ca6127) on account AND project | Assign on both scopes; `_assign_agent_identity_roles()` does this automatically |
| `Experience not available for this subscription` | Region doesn't support hosted agents, or `ENABLE_CAPABILITY_HOST=true` | Set `ENABLE_CAPABILITY_HOST=false`, try `northcentralus` |
| Eval items have empty responses | Concurrent eval requests overwhelm cold-start container | Use sequential eval with warm-up request first (see `run_evals()` in evals.py) |
| Agent skips evidence-gathering tools and emits hollow packets | gpt-5.4-mini tool-call discipline degrades on long instruction chains (10+ steps); model calls commit-tool before evidence is ready | Two complementary fixes: (1) switch `MODEL_DEPLOYMENT_NAME` to `gpt-5.4` (full); (2) make commit-tools refuse hollow inputs server-side via the validate-or-reject pattern in `foundry-mcp-aca`. The PoC ran 1/3 reproducibility with mini + permissive MCP, **3/3 with gpt-5.4 + validate-or-reject**. |
| `Managed environment provisioning timed out` | CapabilityHost was manually created/deleted | Do NOT create CapabilityHosts — platform manages infrastructure automatically |
| `APPLICATIONINSIGHTS_CONNECTION_STRING is reserved` (HTTP 400 `invalid_request_error` at `create_version`) | Set in `agent.yaml` `environment_variables` OR `HostedAgentDefinition.environment_variables` (e.g. as escape-hatch when platform auto-injection silently failed) | Remove it. Cannot be escape-hatched. You MUST guard `configure_azure_monitor()` defensively in `container.py` instead — use `_init_telemetry()` from `foundry-observability` (gap O-011). Verified 2026-05-12, req `820a502e2facc8e1cf46eb3ae71ea26e` |
| Agent traces not appearing in AppInsights | Agent identities lack `Monitoring Metrics Publisher` OR AppInsights connection missing on account | Assign RBAC to both identity principal IDs. Create `AppInsights` connection on the **account** (not project): category `AppInsights`, target = ARM resource ID, metadata `ApiType: Azure`. |
| **Hosted agent returns `server_error`/`model:""` on every smoke; AppIn 0 rows; `azd ai agent show` reports active** | `container.py` calls raw `configure_azure_monitor()` as the first line of `main()` with no try/except. When the platform fails to auto-inject `APPLICATIONINSIGHTS_CONNECTION_STRING` (e.g. AppIn account-level connection persisted with `credentials: null`), the SDK raises `ValueError`. Container crashes before `ResponsesHostServer` binds. Foundry runtime sees no agent. **The agent itself is fine — telemetry init is what killed it.** | Wrap telemetry init in `_init_telemetry()` (no-ops on missing env / SDK ImportError / any SDK exception). Never call `configure_azure_monitor()` raw at module/main scope. See `foundry-observability` gap row O-011 |
| **AppInsights connection PUT 400 ValidationError "AuthType for AppInsights Connection can only be ApiKey"** | Account-RP scope `2025-10-01-preview` in `swedencentral` (and possibly other regions) rejects `authType: AAD` despite skill guidance. Correlation `46a268ef71ff3893cbde7f9d1917ca7f`, verified 2026-05-12 | Use `authType: ApiKey` with `credentials.key` in body. **BUT:** the key is silently dropped server-side — GET returns `credentials: null` and platform never injects the env var. There is no working workaround at the platform layer. File a support ticket; ship with guarded `_init_telemetry()` so the agent functions without telemetry; consider region pivot |
| **AppInsights connection account-level "1-per-category" limit** | Account-level `AppInsights` connections enforce a single-instance-per-category constraint — cannot create parallel connections in the same account. Re-creation requires DELETE first | DELETE the existing connection BEFORE re-PUT. Use `az rest --method DELETE` with full URI **as a variable** (do NOT inline `?api-version=...` — see next row) |
| **`az rest --method DELETE` strips `?api-version=...` query string when URI is inlined on PowerShell** | PowerShell argument parsing eats the `?api-version=` before `az` sees it. The DELETE then fails with "MissingApiVersionParameter" or behaves inconsistently against the bare resource without the version | Workaround: assign the URI to a variable first, then pass via `--uri $delUri`: `$delUri = "https://management.azure.com/.../connections/<name>?api-version=2025-10-01-preview"; az rest --method DELETE --uri $delUri` |
| ACA job uses old code after deploy | Postdeploy hook fails (`AZURE_AI_PROJECT_ENDPOINT not set`) | Run `cd infra/scripts && uv run deploy_job.py` manually after each `azd deploy` |
| Container starts but `agent_reference` errors in logs | `FoundryAgent` used for sub-agents | Replace with client-swap pattern |
| Protocol version error | Using `"v1"` | Use semver `"1.0.0"` |

### Container Logs (Logstream API)

```bash
# Get session ID from session_not_ready error, then:
curl -H "Authorization: Bearer $TOKEN" -H "Accept: text/event-stream" \
  "$PROJECT_ENDPOINT/agents/orchestrator/versions/$VER/sessions/$SID:logstream?api-version=2025-11-15-preview"
```

Returns SSE events with `{"stream":"stderr","message":"..."}` — shows startup logs, tracebacks.
Also: `azd ai agent monitor --session-id $SID`

### Useful Commands

```bash
azd ai agent show                    # Agent status, identities, version
azd ai agent monitor                 # Stream container logs
azd ai agent invoke "Hello!"         # Quick test
azd deploy <service> --no-prompt     # Redeploy without reprovisioning
```

---

## Migration from Initial Preview (pre-April 2026)

| Initial Preview | Refreshed Preview |
|----------------|-------------------|
| `from_agent_framework(agent).run()` | `ResponsesHostServer(agent).run()` |
| `ChatAgent` | `Agent` (from `agent_framework`) |
| `AzureOpenAIChatClient` | `FoundryChatClient` (from `agent_framework.foundry`) |
| `AzureAIClient(agent_name=...)` | Client-swap: `FoundryChatClient.client = project_client.get_openai_client(agent_name=...)` |
| `@ai_function` | `@tool(approval_mode="never_require")` |
| `azure-ai-agentserver-agentframework` | `agent-framework-foundry-hosting` |
| Protocol version `"v1"` | `"1.0.0"` (semver) |
| `extra_body={"agent_reference": ...}` | `get_openai_client(agent_name=...)` |
| Shared project MI | Dedicated agent Entra identity |
| Manual `start`/`stop` | Automatic compute lifecycle |
| `ENABLE_CAPABILITY_HOST=true` | `ENABLE_CAPABILITY_HOST=false` — NO CapabilityHost creation |
| `project_client.agents.list()` at startup | `TL_SUB_AGENTS` env var (avoids blocking readiness) |
| `azure.ai.projects` (sync) in container | `azure.ai.projects.aio` (ASYNC) — sync silently fails |

> **⚠️ `FoundryAgent` class (v1.1.1) is NOT compatible with refreshed preview.**
> It uses `extra_body={"agent_reference": ...}` internally — the old pattern that silently fails.
> Do NOT use `FoundryAgent` for sub-agent delegation. Use the client-swap pattern instead.

**Deadline:** Initial preview backend retires **May 22, 2026**.

Reference: [Migration guide](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview)

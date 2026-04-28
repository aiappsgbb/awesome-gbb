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
sub_client = FoundryChatClient(project_client=project_client, model="gpt-4.1")
sub_client.client = project_client.get_openai_client(agent_name="my-sub-agent")

sub_agent = Agent(name="my-sub-agent", client=sub_client)

orchestrator = Agent(
    client=FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model="gpt-4.1",
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

```python
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

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "my-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "agent-framework>=1.1.0",
    "agent-framework-foundry-hosting>=1.0.0a260421",
    "azure-ai-projects>=2.1.0",
    "azure-identity>=1.19.0",
    "python-dotenv>=1.0.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"
```

**`prerelease = "if-necessary-or-explicit"` is correct** — packages with explicit
prerelease markers (e.g. `>=1.0.0a260421`) resolve to prereleases; everything else
stays GA. Do NOT use `"allow"` — it pulls beta azure-identity 1.26.0b2.

### Dependency Chain (verified on PyPI, April 2026)

| Package | Version | Type | Pulls in |
|---------|---------|------|----------|
| `agent-framework-core` | 1.1.1 | ✅ Stable | pydantic, opentelemetry-api |
| `agent-framework-foundry` | 1.1.1 | ✅ Stable | core, openai, azure-ai-projects |
| `agent-framework-foundry-hosting` | 1.0.0a260423 | ⚠️ Alpha | agentserver-core==2.0.0b2, agentserver-responses==1.0.0b4 |
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
    value: gpt-5.4-mini
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
            name: gpt-5.4-mini
            version: "2026-03-17"
          name: gpt-5.4-mini
          sku:
            capacity: 120
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
| `Managed environment provisioning timed out` | CapabilityHost was manually created/deleted | Do NOT create CapabilityHosts — platform manages infrastructure automatically |
| `APPLICATIONINSIGHTS_CONNECTION_STRING is reserved` | Passed in `HostedAgentDefinition.environment_variables` | Remove it — platform injects telemetry config |
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

---
name: foundry-prompt-agents
description: >
  Manage Foundry prompt agents — declarative agents that
  combine a model, instructions, and tools without containers or
  custom code. Covers azure-ai-projects SDK (PromptAgentDefinition),
  tool wiring (web search, code interpreter, file search, MCP,
  OpenAPI, Fabric IQ, Work IQ, Tool Search, Skill Reference,
  content-safety boundaries, A2A, browser preview), conversations API,
  versioning, structured inputs, and legacy agent application publishing.
  USE FOR: prompt agent, declarative agent, PromptAgentDefinition,
  azure-ai-projects, agent tools, WebSearchTool, CodeInterpreterTool,
  FileSearchTool, MCPTool, OpenApiTool, FabricIQTool, WorkIQTool,
  ToolSearchTool, SkillReferenceTool, GuardrailTool, A2ATool,
  BrowserAutomationTool, conversations API, structured inputs,
  publish agent, Foundry Agent Service. DO NOT USE FOR: hosted
  container agents (use foundry-hosted-agents), MAF agent framework,
  MCP server deployment (use foundry-mcp-aca), agent evaluation (use
  foundry-evals), Knowledge Base / retrieval (use foundry-iq).
metadata:
  version: "1.2.0"
---

# Microsoft Foundry Prompt Agents — Reference Guide

Create declarative agents in Foundry Agent Service using only a model,
instructions, and tools — **no containers, no custom code, no build step**.
Prompt agents are the fastest path from zero to a working agent.

---

## When to use prompt agents vs hosted agents

| | Prompt agents | Hosted agents |
|---|---|---|
| **Definition** | Declarative (model + instructions + tools) | Code-first (Python/C#/TS in container) |
| **Runtime** | Foundry Agent Service manages everything | You build & deploy a container image |
| **SDK** | `azure-ai-projects` (`PromptAgentDefinition`) | MAF (`agent-framework` + `agent-framework-foundry-hosting`) |
| **Build step** | None — create via SDK, REST, or portal | Dockerfile → ACR → ACA or Foundry hosting |
| **Tools** | Built-in catalog + MCP + OpenAPI + functions | Full programmatic control (any Python library) |
| **Customization** | Instructions + tool config only | Unlimited (custom middleware, state, orchestration) |
| **Best for** | Q&A bots, RAG assistants, tool-using agents with standard tools | Complex orchestration, custom business logic, multi-agent systems |

**Rule of thumb:** Start with a prompt agent. Upgrade to a hosted agent only
when you need custom code that can't be expressed as a tool.

---

## Prerequisites

1. **Microsoft Foundry project** with a deployed model (e.g., `gpt-5-mini`,
   `gpt-5.4-mini`, `gpt-4.1`)
2. **Python 3.9+** with `azure-ai-projects ~= 2.4.0`,
   `azure-identity ~= 1.25.3`, and `httpx ~= 0.28.1`
3. **Azure CLI** authenticated via `az login` (or `DefaultAzureCredential`)
4. **Foundry User role** on the AI Services account (GUID
   `53ca6127-db72-4b80-b1b0-d745d6d5456d`) — same role as hosted agents

```bash
pip install "azure-ai-projects~=2.4.0" "azure-identity~=1.25.3" "httpx~=0.28.1"
```

---

## 1 · Create a prompt agent

A prompt agent is created with `PromptAgentDefinition` — just a model name
and instructions. No container, no Dockerfile, no ACR.

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

PROJECT_ENDPOINT = "<your-project-endpoint>"
# Format: https://<resource>.services.ai.azure.com/api/projects/<project>

project = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
)

agent = project.agents.create_version(
    agent_name="my-assistant",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="You are a helpful assistant that answers general questions.",
    ),
)
print(f"Agent created: {agent.name} v{agent.version} (id: {agent.id})")
```

### REST equivalent

```bash
curl -X POST "https://<resource>.services.ai.azure.com/api/projects/<project>/agents/my-assistant/versions?api-version=v1" \
  -H "Authorization: Bearer $(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)" \
  -H "Content-Type: application/json" \
  -d '{
    "definition": {
      "type": "prompt",
      "model": "gpt-5-mini",
      "instructions": "You are a helpful assistant."
    }
  }'
```

---

## 2 · Add tools

Prompt agents support all tools from the Foundry tool catalog. Add them
via the `tools` parameter on `PromptAgentDefinition`.

### Prepare resources before wiring tools

Follow [tool prerequisites and connections](references/tool-prerequisites.md)
before creating an agent version. A tool definition references resources; it
does not create a vector store, Search index, OAuth connection or browser
resource. Use the declared SDK 2.4 cohort below; a current portal feature or
newer schema is not permission to upgrade an application's runtime.

### Built-in tools

```python
from azure.ai.projects.models import (
    PromptAgentDefinition,
    WebSearchTool,
    CodeInterpreterTool,
    FileSearchTool,
)

agent = project.agents.create_version(
    agent_name="research-assistant",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="You are a research assistant. Search the web and analyze data.",
        tools=[
            WebSearchTool(),                          # real-time web search
            CodeInterpreterTool(),                    # sandboxed Python execution
            FileSearchTool(vector_store_ids=["vs_docs"]),  # RAG over uploaded files
        ],
    ),
)
```

### Available built-in tools

| Tool | Class | Purpose |
|------|-------|---------|
| Web Search | `WebSearchTool` | Real-time web grounding with citations |
| Code Interpreter | `CodeInterpreterTool` | Sandboxed Python for data analysis, charts |
| File Search | `FileSearchTool` | Vector search over uploaded documents |
| Function Calling | via `tools` spec | Agent calls your functions, you execute & return |
| Azure AI Search | via connections | Enterprise search index grounding |
| Bing Grounding | `BingGroundingTool` | Market-specific Bing search |
| SharePoint | via connections | Search SharePoint content |

### Custom tools (MCP, OpenAPI)

For per-user custom OAuth, use the connection-backed builders in the
[foundry-mcp-auth candidate](../foundry-mcp-auth/SKILL.md). It owns delegated
scope enforcement and consent setup; the plain MCP example below is not a
delegation proof. The candidate's live Playground acceptance is still pending.

```python
from azure.ai.projects.models import MCPTool

# MCP server (remote tools)
mcp_tool = MCPTool(
    server_label="my-tools",
    server_url="https://my-mcp-server.azurecontainerapps.io/mcp",
    require_approval="never",
)

agent = project.agents.create_version(
    agent_name="tool-agent",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="Use available tools to answer questions.",
        tools=[mcp_tool],
    ),
)
```

> **OpenAPI tools** (`OpenApiTool`) require an `OpenApiFunctionDefinition`
> with a full spec dict and auth configuration. See the
> [Foundry OpenAPI tool docs](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/openapi)
> for the complete schema.

> **MCP servers for prompt agents** are hosted remotely (not in-process).
> Use `foundry-mcp-aca` skill to deploy MCP servers on Azure Container Apps,
> then wire them here via `MCPTool(server_url=...)`.
> If the tool work needs durable result claims, external callbacks, or
> execution that must outlive one request, fall back to
> [foundry-mcp-aca-jobs](../foundry-mcp-aca-jobs/SKILL.md) for the worker
> path and keep the prompt agent as the orchestrator.

### Build 2026 additions (preview)

Availability is specific to the SDK and service. The examples below use the
public **SDK 2.4** exports `FabricIQPreviewTool`, `WorkIQPreviewTool` and
`BrowserAutomationPreviewTool`. Historical headings are retained for links;
they are not import names. Preview tools require `allow_preview=True` on the
project client. Tool Search, Skills and A2A have separate cohort boundaries.

#### FabricIQTool

Grounds a prompt agent in Microsoft Fabric data via a Fabric workspace
connection.

```python
from azure.ai.projects.models import FabricIQPreviewTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Answer questions about Q3 revenue using Fabric data.",
    tools=[FabricIQPreviewTool(
        project_connection_id="<fabric-connection-id>",
        require_approval="always",
    )],
)
```

Requires a Fabric workspace + a project-scoped connection
(`Microsoft.CognitiveServices/accounts/.../connections/<name>`).
See the [Fabric IQ tool docs](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq).

#### WorkIQTool

Grounds a prompt agent in Microsoft 365 / Graph (mail, calendar,
SharePoint, Teams) via a Work IQ connection.

```python
from azure.ai.projects.models import WorkIQPreviewTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Summarize my unread email threads about the selected project.",
    tools=[WorkIQPreviewTool(project_connection_id="<work-iq-connection-id>")],
)
```

Requires the Work IQ connection and user authorization described in the
[Work IQ tool docs](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq).
Do not reuse Fabric connection settings: connector categories, audiences and
consent are tool-specific.

#### ToolSearchTool

For Toolbox discovery, do not use the obsolete `toolbox_ids` constructor.
Configure `ToolSearchToolboxTool` in a **Toolbox version**, then connect the
Prompt Agent through the documented `MCPTool` bridge to that version's MCP
endpoint. See [`foundry-toolbox` — Prompt Agent bridge](../foundry-toolbox/SKILL.md#prompt-agent-bridge)
for the canonical wiring and token/approval boundary.

Tool Search and Toolbox management are GA; **Prompt/Toolbox integration remains
preview**. A live synthetic test on SDK 2.6.1 verified the Prompt agent actually
called `tool_search` and `call_tool` and returned the public documentation result.
This does not prove delegated-user passthrough. Request-scoped Responses API
deferred-tool search is a different API, not a substitute Toolbox identifier.

#### SkillReferenceTool

This historical heading is retained for navigation, not an available tool
constructor. Do not instantiate `SkillReferenceTool(skill_id=...)`.
Foundry Skills are versioned instruction packages, not a Prompt Agent tool
pack. Use [`foundry-skill-catalog`](../foundry-skill-catalog/SKILL.md) for native
versions, explicit download/injection and resource-aware Toolbox consumers.
SDK 2.7 schema fields alone do not prove native Prompt/harness support; this
skill does not enable that unvalidated route or change the existing SDK pin.

#### GuardrailTool

`GuardrailTool` is **not exported by SDK 2.4** and is not a supported
`PromptAgentDefinition` tool in this cohort. There is no verified Preview alias.
Configure Azure Content Safety (ACS) / service content filtering through its
documented control plane, not an invented tool connection. An instruction
asking the model to scan itself is not an enforced guardrail.

Keep the routing decision in this skill:

- Use the service's configured content-safety policies for prompt-agent
  filtering; verify their actual enforcement separately from tool invocation.
- Call the raw ACS API directly when application code must select
  classifiers, thresholds, and response handling itself.
- Use [`foundry-agt`](../foundry-agt/SKILL.md#why-action-governance-matters)
  only for a MAF hosted-agent process that needs deterministic
  allow/deny by tool name before the tool body executes. You cannot
  insert AGT's in-process middleware into `PromptAgentDefinition`.

AGT does not replace Azure Content Safety; combine the two planes when a
workload needs both content scanning and tool-action governance.

#### A2ATool

Use the GA **protocol 1.0** contract, not `target_agent_id`. The direct SDK
model uses `A2ATool(a2a_version=A2AProtocolVersion.V1_0, project_connection_id=...)`;
the Toolbox model is `A2AToolboxTool`. Protocol 0.3 / `a2a_preview` remains
preview. See [`foundry-toolbox` — A2A management](../foundry-toolbox/SKILL.md#a2a-10-management-without-a-runtime-upgrade)
for the isolated SDK environment, connection audience, actual caller access and
tested Toolbox invocation path. Do not silently upgrade this skill's existing
SDK runtime to import newer models, or assume a hosted peer supports incoming
A2A because its container deployed.

#### BrowserAutomationTool

Lets a prompt agent drive a Playwright-backed remote browser session.
This is a **preview** in the declared cohort, not a claim of future GA.

```python
from azure.ai.projects.models import (
    BrowserAutomationPreviewTool,
    BrowserAutomationToolConnectionParameters,
    BrowserAutomationToolParameters,
    PromptAgentDefinition,
)

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Inspect only the approved synthetic test page.",
    tools=[BrowserAutomationPreviewTool(
        browser_automation_preview=BrowserAutomationToolParameters(
            connection=BrowserAutomationToolConnectionParameters(
                project_connection_id="<browser-connection-id>",
            ),
        ),
    )],
)
```

Use the [Browser Automation setup guide](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/browser-automation)
for the Playwright resource and project connection. Verify against an approved
synthetic page and close the run-owned browser session; do not claim a missing
sibling skill supplies setup or cleanup.

---

## 3 · Chat with the agent

Prompt agents use the **Conversations API** via the OpenAI-compatible client.
This is the same invocation path used by hosted agents.

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

project = AIProjectClient(
    endpoint="<your-project-endpoint>",
    credential=DefaultAzureCredential(),
)
openai = project.get_openai_client()

# Create a conversation (multi-turn session)
conversation = openai.conversations.create()

# First turn
response = openai.responses.create(
    conversation=conversation.id,
    extra_body={"agent_reference": {"name": "my-assistant", "type": "agent_reference"}},
    input="What is the population of Tokyo?",
)
print(response.output_text)

# Follow-up (same conversation → history is maintained)
response = openai.responses.create(
    conversation=conversation.id,
    extra_body={"agent_reference": {"name": "my-assistant", "type": "agent_reference"}},
    input="How does that compare to New York?",
)
print(response.output_text)
```

### Targeting a specific version

```python
response = openai.responses.create(
    conversation=conversation.id,
    extra_body={
        "agent_reference": {
            "name": "my-assistant",
            "version": "3",       # pin to version 3
            "type": "agent_reference",
        }
    },
    input="Hello!",
)
```

---

## 4 · Versioning

Every `create_version` call creates an **immutable** version. You cannot
modify a saved version — create a new one instead.

```python
# Create version 1
v1 = project.agents.create_version(
    agent_name="my-assistant",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="You are a helpful assistant.",
    ),
)
print(f"v{v1.version}")  # → v1

# Create version 2 with improved instructions
v2 = project.agents.create_version(
    agent_name="my-assistant",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="You are a helpful assistant. Be concise and cite sources.",
        tools=[WebSearchTool()],
    ),
)
print(f"v{v2.version}")  # → v2
```

Version history is visible in the Foundry portal playground. You can compare
setup, chat output, and YAML definitions between versions.

> **Agent names are permanent.** Once created, an agent's name cannot be
> changed. Use descriptive, stable names from the start.

### List and delete agents

```python
# List all agents in the project
for agent in project.agents.list():
    latest = agent.versions.get("latest", {})
    print(f"{agent.name}  v{latest.get('version', '?')}  {latest.get('status', '?')}")

# Delete a specific version (positional args: agent_name, agent_version)
project.agents.delete_version("my-assistant", "1")
```

> **`list()` returns `AgentDetails`, not `AgentVersionResponse`.** The list
> objects have a `.versions` dict (keyed by `"latest"`, `"1"`, etc.), not a
> single `.version` attribute. Use `.versions["latest"]["version"]` for the
> current version number.

---

## 5 · Structured inputs (runtime tool customization)

Override tool configuration at runtime without creating a new agent version.
Useful when different users need different vector stores, MCP endpoints, or
file sets.

### Define template variables

```python
agent = project.agents.create_version(
    agent_name="support-agent",
    definition=PromptAgentDefinition(
        model="gpt-5-mini",
        instructions="Answer support questions using the customer's knowledge base.",
        tools=[
            FileSearchTool(vector_store_ids=["vs_base_kb", "{{customer_kb}}"]),
        ],
        structured_inputs={
            "customer_kb": {
                "description": "Vector store ID for the customer's knowledge base",
                "required": True,
                "schema": {"type": "string"},
            }
        },
    ),
)
```

### Provide values at invocation

```python
response = openai.responses.create(
    conversation=conversation.id,
    extra_body={
        "agent_reference": {"name": "support-agent", "type": "agent_reference"},
        "structured_inputs": {"customer_kb": "vs_premium_kb"},
    },
    input="How do I upgrade my account?",
)
```

Supported template properties:

| Tool | Property | Description |
|------|----------|-------------|
| `file_search` | `vector_store_ids` | Array of vector store IDs |
| `code_interpreter` | `container`, `container.file_ids` | Container or file IDs |
| `mcp` | `server_label`, `server_url`, `headers` | MCP server config |

---

## 6 · Publish as an agent application

**Legacy Agent Application flow.** This section applies only to an existing
Agent Application integration. Current Foundry agents can have their own
identity and stable agent endpoint; creating an Agent Application is no longer
the universal publication prerequisite. See the official
[endpoint and publishing migration guide](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-agent-applications).
Existing applications and project-endpoint calls remain supported.

For a legacy integration, publishing is done in the **Foundry portal**:
1. Open your agent in the Agents playground
2. Select a saved version
3. Click **Publish**
4. Get the endpoint URL for integration

> **Identity changes on publish.** The published agent application gets its
> own identity. Permissions assigned to the project identity do NOT
> automatically transfer. Reassign RBAC (Foundry User, Cognitive Services
> OpenAI User, etc.) to the agent application's managed identity after
> publishing.

For a new integration, inspect the actual agent's identity and endpoint using
the current publishing guide. Legacy agents can lack a unique identity; any
replacement/cutover needs explicit authorization and caller/tool-access checks.
Do not delete or recreate a serving agent automatically. The SDK 2.4 examples
here intentionally keep their existing project-endpoint invocation contract;
they do not claim newer endpoint fields or silently upgrade the runtime.

---

## 7 · Identity & RBAC

Distinguish the calling identity from the identity used to access tools.
Legacy agents can use the shared project identity; new agents can have a
unique identity. A legacy Agent Application has a separate identity. Inspect
the selected agent and connection's auth mode rather than inferring tool
permissions from the caller's successful `create_version`.

| Phase | Identity | RBAC needed |
|-------|----------|-------------|
| Management caller | Your user or configured workload identity | Foundry User on the approved scope |
| Tool execution | Project, unique agent, or delegated user identity per connection | Tool-specific access and consent |
| Legacy published application | Agent application managed identity | Application and tool-specific roles |

Required role:
- **Foundry User** (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) on the
  AI Services account (not just the project)

If tools connect to external resources (Azure AI Search, SharePoint, etc.),
the agent identity also needs appropriate roles on those resources.

---

## 8 · Evaluation

Use Foundry evaluators to assess prompt agent quality before publishing.
The same evaluation framework works for both prompt and hosted agents.

```python
# Invoke the agent, then score the response
# See foundry-evals skill for the full two-phase invoke+score pattern
```

Key evaluators for prompt agents:
- **Task adherence** — does the agent follow its instructions?
- **Intent resolution** — does the agent understand what the user wants?
- **Groundedness** — are tool-grounded responses accurate?
- **Safety** — does the agent avoid harmful content?

See the `foundry-evals` skill for the complete evaluation workflow.

---

## 9 · Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `PromptAgentDefinition` not found on import | `azure-ai-projects` < 2.0.0 installed | `pip install "azure-ai-projects~=2.4.0" "azure-identity~=1.25.3" "httpx~=0.28.1"` |
| `ModuleNotFoundError: No module named 'httpx'` on SDK import | `azure-ai-projects` 2.4.0 imports undeclared `httpx` | Install bounded `httpx~=0.28.1` explicitly (use the prerequisite command above) |
| "The project does not exist" | Wrong endpoint format or project not provisioned | Endpoint must be `https://<resource>.services.ai.azure.com/api/projects/<project>` (note `services.ai.azure.com`, not `ai.azure.com`) |
| "Model not found" on create | Model not deployed in the Foundry project | Deploy the model in the portal or via `az` CLI |
| Agent created but chat returns empty | No conversation created, or wrong `agent_reference` | Use `openai.conversations.create()` + correct name in `extra_body` |
| 401 on `create_version` | Missing Foundry User role | Assign `53ca6127-db72-4b80-b1b0-d745d6d5456d` at AI Services account scope |
| `AttributeError: 'AgentDetails' has no attribute 'version'` | Using `.version` on list results instead of `.versions` | `list()` returns `AgentDetails` with `.versions` dict — use `.versions["latest"]["version"]` |
| `delete_version()` missing arg | Using keyword arg `version=` | Use positional: `delete_version("my-agent", "1")` (param name is `agent_version`) |
| Tools not invoked | Instructions don't mention tool usage | Add explicit instructions: "Use web search to find current information" |
| Published agent loses tool access | Agent app identity missing RBAC | Reassign roles to the published identity (not project identity) |
| `extra_body` ignored or errors | OpenAI client version mismatch | Use `project.get_openai_client()` (not standalone `openai` package) |
| Version number not incrementing | Creating under a different agent name | Agent names are permanent — check you're using the same name |
| Structured inputs not applied | Template variable not in `{{...}}` syntax | Use `"{{variable_name}}"` in tool config, provide in `structured_inputs` |

---

## 10 · Quick reference

### Minimum viable agent (5 lines)

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

project = AIProjectClient(endpoint="<endpoint>", credential=DefaultAzureCredential())
project.agents.create_version(
    agent_name="hello",
    definition=PromptAgentDefinition(model="gpt-5-mini", instructions="Be helpful."),
)
```

### Import cheat sheet

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    WebSearchTool,
    CodeInterpreterTool,
    FileSearchTool,
    MCPTool,
    OpenApiTool,
    BingGroundingTool,
    FunctionTool,
    AzureAISearchTool,
    # //build 2026 additions (preview) — see § 2 "Build 2026 additions"
    FabricIQPreviewTool,
    WorkIQPreviewTool,
    BrowserAutomationPreviewTool,
    BrowserAutomationToolParameters,
    BrowserAutomationToolConnectionParameters,
)
```

### Related skills

| Need | Skill |
|------|-------|
| Container/code agents with MAF | `foundry-hosted-agents` |
| Deploy MCP servers for tool wiring | `foundry-mcp-aca` |
| Durable tool execution or callback fallback | `foundry-mcp-aca-jobs` |
| RAG via Knowledge Bases | `foundry-iq` |
| Agent evaluation | `foundry-evals` |
| MAF hosted-agent action governance (not prompt-agent content filtering) | `foundry-agt` |
| Observability & tracing | `foundry-observability` |
| Memory across sessions | [`foundry-memory`](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/create/references/tools/prompt-agent/tool-memory.md) |
| Managed Toolbox and preview Prompt bridge | `foundry-toolbox` |
| Versioned Skills and resource-aware consumers | `foundry-skill-catalog` |
| A2A peer-agent invocation | `foundry-toolbox` (`a2a` GA 1.0 versus `a2a_preview` 0.3) |
| Remote browser automation (SDK 2.4 preview) | [Official browser setup](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/browser-automation) |
| Eval-driven prompt optimization | [Official optimizer workflow](https://github.com/microsoft/azure-skills/blob/main/.github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/agent-optimizer/agent-optimizer.md) |

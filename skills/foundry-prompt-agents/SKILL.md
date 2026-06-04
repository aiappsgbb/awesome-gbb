---
name: foundry-prompt-agents
description: >
  Create and manage Foundry prompt agents — declarative agents that
  combine a model, instructions, and tools without containers or
  custom code. Covers azure-ai-projects SDK (PromptAgentDefinition),
  tool wiring (web search, code interpreter, file search, MCP,
  OpenAPI, Fabric IQ, Work IQ, Tool Search, Skill Reference,
  Guardrail, A2A, Browser Automation), conversations API,
  versioning, structured inputs, and publishing as agent
  applications.
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
  version: "1.1.0"
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
2. **Python 3.9+** with `azure-ai-projects >= 2.0.0` and `azure-identity`
3. **Azure CLI** authenticated via `az login` (or `DefaultAzureCredential`)
4. **Foundry User role** on the AI Services account (GUID
   `53ca6127-db72-4b80-b1b0-d745d6d5456d`) — same role as hosted agents

```bash
pip install "azure-ai-projects~=2.1.0" azure-identity
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

### Build 2026 additions (preview)

The //build 2026 wave shipped seven additional first-class prompt-agent
tools. Each is exposed in `azure-ai-projects ≥ 2.0.0` and wired the same
way as the GA tools above. Cross-references point to the dedicated skills
that cover the connection setup, server-side resources, or governance
contract for each tool — some of those skills are forthcoming in this
catalog (tracked in the //build 2026 update wave); use the upstream Foundry
docs in the meantime.

#### FabricIQTool

Grounds a prompt agent in Microsoft Fabric data via a Fabric workspace
connection.

```python
from azure.ai.projects.models import FabricIQTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Answer questions about Q3 revenue using Fabric data.",
    tools=[FabricIQTool(connection_id="<fabric-connection-id>")],
)
```

Requires a Fabric workspace + a project-scoped connection
(`Microsoft.CognitiveServices/accounts/.../connections/<name>`).
See the [Fabric IQ tool docs](https://learn.microsoft.com/azure/ai-foundry/tools/fabric-iq).

#### WorkIQTool

Grounds a prompt agent in Microsoft 365 / Graph (mail, calendar,
SharePoint, Teams) via a Work IQ connection.

```python
from azure.ai.projects.models import WorkIQTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Summarize my unread email threads about Project Hummingbird.",
    tools=[WorkIQTool(connection_id="<work-iq-connection-id>")],
)
```

Requires an M365 / Graph connection on the Foundry project. The connection
contract is identical to Fabric IQ — see the
[Work IQ tool docs](https://learn.microsoft.com/azure/ai-foundry/tools/work-iq)
for tenant-admin consent + scope guidance.

#### ToolSearchTool

Lets a prompt agent dynamically discover and call tools registered in a
Foundry **toolbox** (server-side MCP bundle) without enumerating every
tool in `tools=[...]`.

```python
from azure.ai.projects.models import ToolSearchTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Use the most appropriate tool for the user's task.",
    tools=[ToolSearchTool(toolbox_ids=["<toolbox-id>"])],
)
```

Toolbox registration is server-side — see the `foundry-toolboxes` skill
(forthcoming in this catalog) for the toolbox lifecycle. ToolSearchTool
is the **consumption** side; `foundry-toolboxes` is the **production**
side.

#### SkillReferenceTool

Lets a prompt agent invoke a published **Foundry Skill** (a declarative
tool pack) by reference, the same way a hosted agent does.

```python
from azure.ai.projects.models import SkillReferenceTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Use the published payments-lookup skill when asked about transactions.",
    tools=[SkillReferenceTool(skill_id="<published-skill-id>")],
)
```

Foundry Skills are managed in the same catalog as Toolboxes — see the
`foundry-toolboxes` skill (forthcoming) for publishing + versioning.

#### GuardrailTool

Wires Azure Content Safety (ACS) as a server-side policy check around the
agent's input and output, expressed as a tool the agent can invoke.

```python
from azure.ai.projects.models import GuardrailTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="Be helpful, but always run the user message through GuardrailTool first.",
    tools=[GuardrailTool(connection_id="<acs-connection-id>")],
)
```

For the **decision** of when to use `GuardrailTool` vs full in-process
governance (AGT) vs raw ACS API calls, see the `foundry-agt` skill — it
carries the canonical decision table.

#### A2ATool

Lets a prompt agent invoke a peer hosted agent (Agent-to-Agent protocol,
GA at //build 2026).

```python
from azure.ai.projects.models import A2ATool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="When asked for current weather, delegate to the weather-bot agent.",
    tools=[A2ATool(target_agent_id="<peer-agent-id>")],
)
```

Identity propagation, peer-agent RBAC, and the project-MI Cog-roles
gotcha (AGENTS.md §9.7 Pattern 23) are covered in the `foundry-a2a`
skill (forthcoming in this catalog).

#### BrowserAutomationTool

Lets a prompt agent drive a Playwright-backed remote browser session
(GA Nov 2026) — useful for forms, multi-page workflows, and pages that
require interactive navigation.

```python
from azure.ai.projects.models import BrowserAutomationTool, PromptAgentDefinition

definition = PromptAgentDefinition(
    model="gpt-5-mini",
    instructions="When asked to fill a form, use BrowserAutomationTool.",
    tools=[BrowserAutomationTool(connection_id="<browser-connection-id>")],
)
```

Connection setup, deterministic-page testing patterns, and Pattern 25
soft-PASS teardown for ephemeral browser sessions are covered in the
`foundry-browser-automation` skill (forthcoming in this catalog).

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

After testing, publish a version to get a **stable endpoint** that can be
shared or embedded in applications.

Publishing is done in the **Foundry portal**:
1. Open your agent in the Agents playground
2. Select a saved version
3. Click **Publish**
4. Get the endpoint URL for integration

> **Identity changes on publish.** The published agent application gets its
> own identity. Permissions assigned to the project identity do NOT
> automatically transfer. Reassign RBAC (Foundry User, Cognitive Services
> OpenAI User, etc.) to the agent application's managed identity after
> publishing.

---

## 7 · Identity & RBAC

Prompt agents run under the **project identity** during development and
under the **agent application identity** after publishing.

| Phase | Identity | RBAC needed |
|-------|----------|-------------|
| Development | Your user (via `az login`) | Foundry User on AI Services account |
| Published | Agent application managed identity | Foundry User + tool-specific roles |

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
| `PromptAgentDefinition` not found on import | `azure-ai-projects` < 2.0.0 installed | `pip install "azure-ai-projects~=2.1.0"` |
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
    FabricIQTool,
    WorkIQTool,
    ToolSearchTool,
    SkillReferenceTool,
    GuardrailTool,
    A2ATool,
    BrowserAutomationTool,
)
```

### Related skills

| Need | Skill |
|------|-------|
| Container/code agents with MAF | `foundry-hosted-agents` |
| Deploy MCP servers for tool wiring | `foundry-mcp-aca` |
| RAG via Knowledge Bases | `foundry-iq` |
| Agent evaluation | `foundry-evals` |
| Agent governance (AGT) — incl. GuardrailTool decision | `foundry-agt` |
| Observability & tracing | `foundry-observability` |
| Memory across sessions | `foundry-memory` |
| In-process toolbox utilities | `foundry-toolbox` |
| Server-side MCP toolboxes + Foundry-Skills (ToolSearchTool / SkillReferenceTool) | `foundry-toolboxes` (forthcoming) |
| A2A peer-agent invocation (A2ATool) | `foundry-a2a` (forthcoming) |
| Remote browser automation (BrowserAutomationTool) | `foundry-browser-automation` (forthcoming) |
| Eval-driven prompt optimization (`azd ai agent eval/optimize/apply` loop) | `foundry-agent-optimizer` (forthcoming) |

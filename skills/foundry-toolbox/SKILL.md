---
name: foundry-toolbox
description: >
  Use Microsoft Foundry Toolbox GA to manage versioned multi-tool bundles
  behind a single MCP endpoint and connect them to hosted agents. Covers
  stable AIProjectClient.toolboxes CRUD, Toolbox-specific SDK models,
  agent_framework_foundry_hosting.FoundryToolbox, authentication,
  immutable-version promotion and rollback, the azd ai toolbox declarative
  path, and preview Tool Search. Distinguishes the GA Toolbox core from
  preview A2A, Work IQ, Fabric IQ, Browser Automation, Reminder, skills, and
  Tool Search; explains that azure_ai_search wraps an index, not a Foundry IQ
  knowledge base. USE FOR: foundry toolbox, toolbox MCP endpoint,
  AIProjectClient toolboxes, FoundryToolbox, toolbox version promote,
  multi-tool MCP endpoint, ToolboxSearchPreviewToolboxTool, kind toolbox,
  host azure.ai.toolbox, toolbox.yaml. DO NOT USE FOR: building MCP servers
  (use foundry-mcp-aca),
  KB-only RAG (use foundry-iq), generic hosted-agent runtime (use
  foundry-hosted-agents), cross-resource models (use foundry-cross-resource).
metadata:
  version: "2.0.0"
  validated: 2026-07-13
---

# Microsoft Foundry Toolbox GA - Reference Guide

The [Foundry Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
is a GA managed resource that bundles versioned tools behind one MCP endpoint.
The platform centralizes connection references, credentials, token refresh,
policy, and immutable-version promotion while the agent connects to one URL.

Use a Toolbox when an agent needs several managed tools, when tool composition
must change without redeploying agent code, or when credentials belong in the
Foundry project rather than the agent container. Stable management uses
`AIProjectClient.toolboxes`. Preview capabilities, including
[Tool Search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
and skills in Toolboxes, retain their preview support terms even though the
parent Toolbox resource is GA.

## Status boundary

| Surface | Status | Canonical contract |
|---|---|---|
| Toolbox resource, versions, promotion, CRUD, and MCP `v1` endpoints | **GA** | `AIProjectClient.toolboxes`; no preview feature header |
| MCP, Web Search, Azure AI Search, Code Interpreter, File Search, OpenAPI | **GA Toolbox tool types** | Toolbox-specific SDK model classes |
| A2A, Work IQ, Fabric IQ, Browser Automation, Reminder | **Preview** | Classes retain `Preview` in their names |
| Tool Search and skills in Toolboxes | **Preview** | Opt in explicitly; no SLA |
| `agent_framework_foundry_hosting.FoundryToolbox` | **Prerelease client package** | High-level consumer for the GA Toolbox MCP endpoint |
| `azure.ai.toolboxes` azd extension `1.0.0-beta.2` | **Beta client extension** | Calls the GA service API without the removed header |

Do not infer a subfeature's status from the Toolbox resource's GA status. A
GA Toolbox can contain a preview tool, but that tool keeps its preview support
and SLA terms.

```
Foundry project
└── Toolbox: agent-tools
    ├── default_version -> 3
    ├── immutable versions: 1, 2, 3
    ├── GA tool models
    │   ├── MCPToolboxTool
    │   ├── WebSearchToolboxTool
    │   ├── AzureAISearchToolboxTool
    │   ├── CodeInterpreterToolboxTool
    │   ├── FileSearchToolboxTool
    │   └── OpenApiToolboxTool
    └── preview tool models
        ├── A2APreviewToolboxTool
        ├── WorkIQPreviewToolboxTool
        ├── FabricIQPreviewToolboxTool
        ├── BrowserAutomationPreviewToolboxTool
        ├── ReminderPreviewToolboxTool
        └── ToolboxSearchPreviewToolboxTool

Version-specific MCP endpoint:
  {project}/toolboxes/agent-tools/versions/3/mcp?api-version=v1

Default-version MCP endpoint:
  {project}/toolboxes/agent-tools/mcp?api-version=v1

Every request:
  Entra bearer token scoped to https://ai.azure.com/.default
  No preview feature header

Consumers:
  Hosted MAF -> FoundryToolbox
  Direct non-Toolbox MCP -> MCPStreamableHTTPTool
  LangGraph / other frameworks -> authenticated Streamable HTTP MCP client
  Prompt Agent Tool Search -> preview MCPTool bridge
```

## Consumption boundary

The GA Toolbox resource exposes authenticated Streamable HTTP MCP endpoints; it
is not itself an Agent `tools[].type`. Use the consumer that matches the host:

| Host | Toolbox consumer | Status |
|---|---|---|
| Hosted Microsoft Agent Framework code | `FoundryToolbox` in the Agent `tools` list | GA Toolbox path through a prerelease hosting wrapper |
| LangGraph or another code framework | Its authenticated Streamable HTTP MCP client | Framework-specific |
| Prompt Agent | `MCPTool` pointing at the Toolbox endpoint with Tool Search enabled | Tool Search preview |

Do not invent `tools=[{"type": "toolbox"}]`; that Agent tool type does not
exist. A Prompt Agent can use the documented Tool Search preview bridge, where
the Toolbox endpoint exposes only `tool_search` and `call_tool`. For stable
hosted production composition, use `FoundryToolbox` in code.

## When to use Toolbox vs alternatives

| Need | Use | Why |
|---|---|---|
| **Multiple managed tools behind one endpoint** | **Toolbox** | Centralized creds, swap tools without agent redeploy, versioning |
| **Single hosted MCP with static API key** | `client.get_mcp_tool()` (`foundry-hosted-agents` § MCP) | Simpler — no toolbox abstraction layer |
| **MCP with short-lived AAD bearer (KB MCP, Storage behind PMI)** | `MCPStreamableHTTPTool` + `header_provider` (`foundry-hosted-agents`) | Toolbox MCP endpoint can wrap it, but direct `header_provider` is one less hop |
| **KB-only RAG with agentic retrieval / multi-hop / citations** | `foundry-iq` (Knowledge Base, NOT Toolbox `azure_ai_search`) | Toolbox `azure_ai_search` wraps an INDEX, not a KB — no query planning or answer synthesis |
| **Custom MCP server you build + deploy** | `foundry-mcp-aca` to build the server, **then wire it INTO a Toolbox** | These compose: build with one skill, manage centrally with this one |
| **Cross-resource model invocation** | `foundry-cross-resource` | Toolbox is for *tools*, not models |
| **Vision / DocIntel / Speech tools** | `foundry-doc-vision-speech` patterns wrapped via Toolbox `openapi` or `mcp` | Toolbox is the consumption layer |

---

## Tool type reference

`ToolboxTool` is the abstract base. Use the concrete subclasses below for
Toolbox versions. Generic Agent models such as `MCPTool` and `WebSearchTool`
belong to Agent definitions and are not the canonical Toolbox 2.3 models.

| SDK model | Wire type | Status | Required configuration |
|---|---|---|---|
| `MCPToolboxTool` | `mcp` | GA | `server_label` plus `server_url` or `connector_id`; optional project connection |
| `WebSearchToolboxTool` | `web_search` | GA | No required fields; optional filters and search context |
| `AzureAISearchToolboxTool` | `azure_ai_search` | GA | `azure_ai_search=AzureAISearchToolResource(...)` |
| `CodeInterpreterToolboxTool` | `code_interpreter` | GA | No required fields; optional container/files |
| `FileSearchToolboxTool` | `file_search` | GA | Vector-store configuration |
| `OpenApiToolboxTool` | `openapi` | GA | `openapi=OpenApiFunctionDefinition(...)` |
| `A2APreviewToolboxTool` | `a2a_preview` | Preview | Remote agent URL and project connection as needed |
| `WorkIQPreviewToolboxTool` | `work_iq_preview` | Preview | Work IQ project connection |
| `FabricIQPreviewToolboxTool` | `fabric_iq_preview` | Preview | Fabric IQ project connection and target server details |
| `BrowserAutomationPreviewToolboxTool` | `browser_automation_preview` | Preview | Browser Automation connection parameters |
| `ReminderPreviewToolboxTool` | `reminder_preview` | Preview | No required fields |
| `ToolboxSearchPreviewToolboxTool` | `toolbox_search_preview` | Preview | No required fields; activates `tool_search` and `call_tool` |

### Per-tool anti-patterns

- **`azure_ai_search` tool:** DO NOT use when you need vector + keyword hybrid search in a VNet-injected agent (file_search VNet support is broken as of May 2026). DO use a custom MCP-wrapped AI Search in those cases, wired via the `mcp` tool type.
- **`file_search` tool:** DO NOT use in VNet-isolated Foundry projects (the file_search backend doesn't yet support PMI in VNet). DO use Cosmos MCP or custom AI Search MCP via `foundry-mcp-aca` or wire directly with `mcp` tool type.
- **`code_interpreter` tool:** DO NOT use for long-running computations (>5 min wall-clock) — the container will timeout and fail silently. DO use ACA Jobs via `azd-patterns` for batch work.
- **`web_search` tool:** DO NOT enable in regulated-data contexts without explicit allow-listing of source domains. DO use the `allowed_domains` parameter when you need to scope results to a restricted set of trusted sources.

---

## Stable Toolbox request contract

The GA request shape is:

| Element | Value |
|---|---|
| AAD token scope | `https://ai.azure.com/.default` |
| Authorization | OAuth 2.0 bearer token minted for the Toolbox scope |
| MCP API version | `?api-version=v1` |
| Preview feature header | **None** |

`azure-ai-projects` 2.3.0 and `FoundryToolbox` apply this contract without
`Foundry-Features: Toolboxes=V1Preview`. Remove that header when migrating
preview-era clients; do not make correctness depend on a retired feature gate.

### Preview-to-GA migration

| Preview-era contract | GA contract |
|---|---|
| `project.beta.toolboxes` | `project.toolboxes` |
| `client.get_toolbox(...)` | `project.toolboxes.get(name)` for the latest version, or `project.toolboxes.get_version(name, version)` for an explicit immutable version |
| `select_toolbox_tools(...)` | Define the exact `tools=[...]` set in a Toolbox version, then consume that version through `FoundryToolbox` |
| Generic `MCPTool`, `WebSearchTool`, `AzureAISearchTool` | `MCPToolboxTool`, `WebSearchToolboxTool`, `AzureAISearchToolboxTool` |
| `Foundry-Features: Toolboxes=V1Preview` | Remove the feature header |
| `AzureAIToolbox` | `agent_framework_foundry_hosting.FoundryToolbox` |
| `create_toolbox_version(...)` in stale examples | `create_version(...)` in SDK 2.3.0 |

This table is the only place presenting obsolete APIs as migration mapping;
status/troubleshooting may name retired header, but fenced canonical code must
not contain preview-era API.

---

## Two endpoint shapes

| Role | Endpoint | When |
|---|---|---|
| **Toolbox developer** | `{project}/toolboxes/{name}/versions/{version}/mcp?api-version=v1` | Test or validate a specific version before promoting it |
| **Toolbox consumer** | `{project}/toolboxes/{name}/mcp?api-version=v1` | Production agents — always serves `default_version` |

The first version of a new toolbox is auto-promoted to `default_version`
(`v1`). Subsequent versions stay un-promoted until you explicitly update
the toolbox's `default_version`.

---

## Auth & RBAC

Grant **Azure AI User** on the Foundry project to each identity that
applies:

| Identity | Required for | Why |
|---|---|---|
| **Developer** | Always | Create / update / promote / delete toolbox versions |
| **Agent identity (UAMI / agent MI)** | Hosted agents calling tools | Agent calls `tools/call` at runtime |
| **End user** | OAuth-based MCP or `UserEntraToken` connections | OBO flow proxies the user's Entra token |

> **Hosted MAF / GHCP agent identity:** the calling identity at runtime
> is `instance_identity.principal_id`, not the project / account MIs. See
> `foundry-iq` § Hosted-agent runtime identity for the full breakdown
> (same identity model applies to Toolbox tool calls).

---

## Low-level MCP compatibility notes

`FoundryToolbox` is the canonical MAF consumer. On MAF 1.11 it handles
per-request Entra authorization, defaults `load_prompts=False`, treats MCP
method-not-found from `ping` as a supported server capability boundary, and
owns connection cleanup.

Custom MCP clients still need these protocol rules:

- do not require `prompts/list`; Toolboxes expose tools;
- keep Streamable HTTP tool calls in streaming mode;
- request tokens for `https://ai.azure.com/.default`; and
- do not add the removed preview feature header.

The hosted platform reserves `FOUNDRY_*` environment variables. Use the
platform-provided `FOUNDRY_PROJECT_ENDPOINT`, and use `TOOLBOX_ENDPOINT` plus
`TOOLBOX_NAME` only when overriding `FoundryToolbox` endpoint discovery.

## Tool-authoring failure modes

When integrating tools into a toolbox or wiring them to an agent, watch for these common authoring mistakes. This table documents how they manifest, root causes, and defensive patterns.

| Symptom | Root cause | DO NOT do | DO instead |
|---|---|---|---|
| Tool not invoked when expected | Tool description too vague or contradicts agent instructions | Write generic tool descriptions like "search for things" | Write specific descriptions naming inputs/outputs/preconditions — e.g. "Search product catalog by name or SKU; returns title + price + stock" |
| Tool invoked too aggressively | Tool description too tempting OR no scoping in agent system prompt | Rely solely on description to control invocation | Add explicit tool-use scope rules in the agent's `instructions=` parameter; e.g. "Only call product_search after confirming the user requested a search" |
| Malformed JSON returned by tool | Tool returns Python object via plain `print()` or `return` | Return non-JSON-serializable objects (dicts, tuples, custom classes without serialization) | Use Pydantic models with `.model_dump()` or explicit `json.dumps()` serialization before returning |
| Tool exception bubbles up as `session_not_ready` (424) | Tool raises unhandled exception → container crashes → no error trace surfaced | Let tool exceptions propagate to the framework | Wrap tool body in `try/except` and return a structured error dict the model can reason about — e.g. `{"error": "...reason...", "retry_in_seconds": 30}` |
| Tool description doesn't match agent intent | Spec says "summarize PDFs" but tool description says "extract text" | Let tool descriptions drift from the agent's stated capabilities | Sync tool descriptions against spec.md § Agent Tools during every spec review — re-check before each promotion |

---

## Step 1 — Create a toolbox version

Python SDK (azure-ai-projects):

```python
import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AISearchIndexResource,
    AzureAISearchToolResource,
    AzureAISearchToolboxTool,
    MCPToolboxTool,
    WebSearchToolboxTool,
)
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=credential,
    ) as project,
):
    toolbox_version = project.toolboxes.create_version(
        name="agent-tools",
        description="Web search + product index + Microsoft Learn MCP",
        tools=[
            WebSearchToolboxTool(),
            AzureAISearchToolboxTool(
                azure_ai_search=AzureAISearchToolResource(
                    indexes=[
                        AISearchIndexResource(
                            index_name="products",
                            project_connection_id="aisearch-conn",
                        ),
                    ],
                ),
            ),
            MCPToolboxTool(
                server_label="mslearn",
                server_url="https://learn.microsoft.com/api/mcp",
                require_approval="never",
            ),
        ],
    )
    print(
        f"Created {toolbox_version.name} "
        f"version {toolbox_version.version}"
    )
```

`project.toolboxes` exposes `create_version`, `get`, `list`, `delete`,
`update`, `get_version`, `list_versions`, `delete_version`; stable management
does not require `allow_preview=True`.

> **Current API matrix (validated 2026-07-13):**
>
> | Package | Validated version | Notes |
> |---|---|---|
> | azure-ai-projects | 2.3.0 | Stable Toolbox management and Toolbox models |
> | agent-framework | 1.11.0 | Agent, chat client, and direct MCP composition |
> | agent-framework-foundry-hosting | 1.0.0a260709 | High-level FoundryToolbox consumer |
> | mcp | 1.28.1 | Streamable HTTP MCP primitives |

The first call creates the toolbox AND version `1`, auto-promoted to
default. Subsequent calls create new versions that stay un-promoted
until you call `update(default_version=...)`.

---

## Step 2 — Wire into a hosted agent

### Pattern A — MAF (Agent + ResponsesHostServer + MCPStreamableHTTPTool)

The doc-recommended pattern. The httpx `Auth` subclass keeps the bearer
token fresh on every transport-level request (avoiding the static-headers
1-hour expiry trap documented in `foundry-hosted-agents` SKILL § MCP).

```python
import os
import httpx
from agent_framework import MCPStreamableHTTPTool
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# --- httpx.Auth subclass that mints a fresh AAD bearer per request ---
class _ToolboxAuth(httpx.Auth):
    requires_request_body = False
    def __init__(self, token_provider):
        self._tp = token_provider
    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._tp()}"
        yield request

# --- Trap-proof MCP tool subclass (no-op ping) ---
class ToolboxMCPTool(MCPStreamableHTTPTool):
    async def _ensure_connected(self):
        if self._client is None:
            await self.connect()

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://ai.azure.com/.default"
)
http_client = httpx.AsyncClient(
    auth=_ToolboxAuth(token_provider),
    timeout=120.0,
)

# Read platform-injected URL — never hard-code
TOOLBOX_ENDPOINT = os.environ["TOOLBOX_AGENT_TOOLS_MCP_ENDPOINT"]

mcp_tool = ToolboxMCPTool(
    name="toolbox",
    url=TOOLBOX_ENDPOINT,
    http_client=http_client,
    load_prompts=False,           # 🔑 trap 2
    request_timeout=120,
)

chat_client = OpenAIChatClient(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=credential,
)

agent = chat_client.as_agent(
    name="my-toolbox-agent",
    instructions="You are a helpful assistant with access to Foundry toolbox tools.",
    tools=[mcp_tool],
)
ResponsesHostServer(agent).run()
```

> **MUST:** Always pass `parse_tool_results=` when using `MCPStreamableHTTPTool`. Without it, the agent sees raw MCP JSON instead of text content, causing confabulated responses.

> **MUST:** Use [`references/python/mcp_text_extractor.py`](references/python/mcp_text_extractor.py) as the canonical extractor (exports `extract_mcp_text` and the backward-compat alias `_mcp_text_extractor`). Do NOT redefine inline — the validator enforces single-source-of-truth.
>
> **MUST:** For the full 3-pattern wiring example (toolbox + direct MCP + local function tools composed into one agent), copy verbatim from [`references/python/toolbox_wiring.py`](references/python/toolbox_wiring.py). It is the canonical SDK-level wiring (high-level `AzureAIToolbox`), complementing the trap-aware low-level pattern shown above (`ToolboxMCPTool` subclass).

```python
from references.python.mcp_text_extractor import extract_mcp_text

learn_mcp = MCPStreamableHTTPTool(
    name="microsoft-learn",
    url="https://learn.microsoft.com/api/mcp",
    parse_tool_results=extract_mcp_text,  # ← MUST include this
)
```

#### Cross-skill ownership

> **MAF runtime wiring (Agent, ChatClient, ResponsesHostServer, ping handling, load_prompts=False) is OWNED by `foundry-hosted-agents` SKILL.** THIS SKILL owns toolbox resource semantics + authentication patterns + multi-tool composition. When in doubt: runtime → `foundry-hosted-agents`; toolbox resource → this SKILL.

#### Canonical MCP result parser (recommended for non-toolbox MCPs too)

When you wire a remote MCP via `MCPStreamableHTTPTool` (toolbox endpoint OR a
public MCP like Microsoft Learn / GitHub MCP), the raw `tools/call` response
contains an array of `content` items with `{"type": "text", "text": "..."}`
shape. MAF 1.7 doesn't unwrap this for you — without a `parse_tool_results`
extractor, the model sees the wire-level JSON envelope instead of just the
text. Models will sometimes parse through it, sometimes not, leading to
"the agent found the docs but didn't cite them" type bugs.

Pass an extractor to the tool constructor:

> **MUST:** Import the canonical extractor from [`references/python/mcp_text_extractor.py`](references/python/mcp_text_extractor.py) (function `extract_mcp_text`). Do NOT redefine inline — the validator enforces single-source-of-truth.

```python
from references.python.mcp_text_extractor import extract_mcp_text

mcp_tool = MCPStreamableHTTPTool(
    name="microsoft-learn",
    url="https://learn.microsoft.com/api/mcp",
    parse_tool_results=extract_mcp_text,   # ← key line
)
```

Verified on the 2026-05-28 learn-assistant pilot: without `parse_tool_results`,
the agent answered "I found articles" but didn't quote them; with the
extractor, every answer cited 4+ `learn.microsoft.com` URLs. Same helper
works for any remote streamable-http MCP.

#### Validated remote-MCP recipe — Microsoft Learn MCP (no-auth, public)

The simplest possible remote-MCP wiring: a public, free, no-auth MCP server.
Verified end-to-end on a hosted-agent pilot (MAF 1.7.0, May 2026) — the
agent ran 4 demo scenarios with 5–6 `learn.microsoft.com` citations per
grounded answer.

```python
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer

from references.python.mcp_text_extractor import extract_mcp_text

learn_mcp = MCPStreamableHTTPTool(
    name="microsoft-learn",
    url="https://learn.microsoft.com/api/mcp",   # public, no-auth, free
    parse_tool_results=extract_mcp_text,
)

agent = Agent(
    client=FoundryChatClient(),                  # MAF 1.7 API
    tools=[learn_mcp],
    instructions=(
        "You are a Microsoft Learn assistant. For every Azure / .NET / "
        "Microsoft 365 question, call the microsoft-learn tool and cite "
        "the article URLs in your answer using inline markdown links."
    ),
)
ResponsesHostServer(agent).run()
```

Why this works without extra plumbing:
- **No auth headers needed** — Learn MCP is public per [Microsoft Learn
  Terms of Use](https://learn.microsoft.com/en-us/legal/termsofuse). No
  bearer token, no API key, no rate-limit ceiling for casual usage.
- **ACA egress is open by default** — no `egressPolicies` required for
  `*.microsoft.com` in standard ACA environments.
- **`parse_tool_results=_mcp_text_extractor` is mandatory** to surface the
  Learn knowledge service's text payloads cleanly — without it, the model
  sees the raw `{"content": [...]}` envelope and citation quality collapses.

This is the canonical no-auth remote-MCP shape; any other public MCP
(GitHub MCP for unauthenticated requests, generic knowledge MCPs) drops
into the same pattern by swapping the `url`.

### Pattern B — ~~MAF convenience helper~~ **REMOVED in MAF 1.3.0**

> **`client.get_toolbox()` and `select_toolbox_tools` were removed in
> `agent-framework-foundry` 1.3.0** ([PR #5671](https://github.com/microsoft/agent-framework/pull/5671) — external repo link; for offline / agent context, key claims summarised in `foundry-hosted-agents` § MAF 1.6.0 update if relevant).
> The MAF team standardized on MCP for all toolbox consumption.
> **Use Pattern A (`MCPStreamableHTTPTool`) instead.**
>
> If you find old code using `client.get_toolbox()`, migrate it to
> Pattern A — the MCP endpoint is the same one `get_toolbox()` was
> calling under the hood.
>
> MAF 1.6.0 added per-tool factory methods (`get_azure_ai_search_tool`,
> `get_sharepoint_tool`, etc.) on `FoundryChatClient` for specific
> hosted tools — but there is no whole-toolbox convenience replacement.
> Use `MCPStreamableHTTPTool` with `allowed_tools` for tool filtering.

### Pattern C — LangGraph

Requires `langchain-azure-ai[tools]>1.2.3`. The platform-injected
`FOUNDRY_AGENT_TOOLBOX_*` env vars are picked up automatically:

```python
from langchain_azure_ai.tools import AzureAIProjectToolbox

toolbox = AzureAIProjectToolbox(toolbox_name=os.environ["TOOLBOX_NAME"])
tools = await toolbox.get_tools()
# Pass `tools` to your StateGraph / agent_executor as usual
```

### Pattern D — GitHub Copilot SDK (bridge)

The Copilot SDK rejects tool names containing dots, so you need a small
bridge that replaces `.` with `_` on the way out and back on the way in:

```python
bridge = McpBridge(endpoint=TOOLBOX_ENDPOINT, token=_get_toolbox_token())
await bridge.initialize()
mcp_tools = await bridge.list_tools()

copilot_tools = [
    {
        "name": t["name"].replace(".", "_"),
        "description": t.get("description", ""),
        "parameters": t.get("inputSchema", {}),
    }
    for t in mcp_tools
]

async def tool_handler(name: str, arguments: dict) -> str:
    # Restore the first underscore back to a dot for MCP routing
    return await bridge.call_tool(name.replace("_", ".", 1), arguments)

agent = Agent(
    tools=copilot_tools,
    tool_handler=tool_handler,
    token=os.environ["GITHUB_TOKEN"],
)
```

`replace("_", ".", 1)` handles the standard `{server_label}.{tool_name}`
shape — only the first underscore is converted back. Tools with
underscores in the trailing component (e.g. `github.list_repos`) survive
the round-trip.

---

## Step 3 — Verify the toolbox loads

Before pointing an agent at a new version, sanity-check it with the raw
MCP client. Use the **versioned endpoint** to validate before promoting:

```python
import asyncio
import os

from azure.identity import DefaultAzureCredential
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def verify(url: str, headers: dict[str, str]) -> None:
    async with streamablehttp_client(
        url,
        headers=headers,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            print(f"Tools found: {len(tools_result.tools)}")
            for toolbox_tool in tools_result.tools:
                description = (toolbox_tool.description or "")[:80]
                print(f"  - {toolbox_tool.name}: {description}")


project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
toolbox_version = "3"
url = (
    f"{project_endpoint}/toolboxes/agent-tools"
    f"/versions/{toolbox_version}/mcp?api-version=v1"
)

with DefaultAzureCredential() as credential:
    token = credential.get_token("https://ai.azure.com/.default").token
    headers = {
        "Authorization": " ".join(("Bearer", token)),
    }
    asyncio.run(verify(url, headers))
```

What to check:

- `len(tools) > 0` — empty means the version isn't provisioned yet (wait
  10s and retry) OR an MCP / A2A connection is broken (see
  troubleshooting)
- Each tool has `name`, `description`, `inputSchema`
- `inputSchema.properties` is present (some MCP servers omit this, which
  breaks OpenAI tool-calling)
- MCP tool names follow `{server_label}.{tool_name}` shape
- `_meta.tool_configuration.require_approval` reflects what you set

---

## Step 4 — Declarative deploy with `azd ai agent init`

Skip the SDK / REST create call entirely — declare toolboxes + connections
in `agent.yaml` and let `azd` handle provisioning, secret injection, and
container deployment. See `foundry-hosted-agents` SKILL § "azure.yaml (azd
ai agent Extension)" for the full scaffold.

```yaml
# agent.yaml — manifest directory
name: my-toolbox-agent
description: MAF agent wired for Foundry toolbox.
metadata:
  tags: ["AI Agent Hosting", "MAF"]
template:
  kind: hosted
  protocols:
    - protocol: responses
      version: 1.0.0
  environment_variables:
    # FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_AGENT_TOOLBOX_* are
    # injected automatically by the platform — do NOT declare them here
    # (Trap 4: FOUNDRY_* is reserved).
    - name: AZURE_AI_MODEL_DEPLOYMENT_NAME
      value: ${AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-5.4}
    - name: TOOLBOX_NAME
      value: ${TOOLBOX_NAME=agent-tools}

parameters:
  github_pat:
    secret: true
    description: GitHub PAT for the GitHub MCP connection

resources:
  - kind: connection
    name: github-mcp-conn
    target: https://api.githubcopilot.com/mcp
    category: RemoteTool
    authType: CustomKeys
    credentials:
      keys:
        Authorization: "Bearer {{ github_pat }}"

  - kind: toolbox
    name: agent-tools
    description: Web search + GitHub MCP
    tools:
      - type: web_search
      - type: mcp
        server_label: github
        server_url: https://api.githubcopilot.com/mcp
        project_connection_id: github-mcp-conn
        require_approval: never
```

Deploy:

```bash
# 1. Manifest dir contains agent.yaml + main.py + Dockerfile + requirements.txt
mkdir my-agent/manifest
# ... copy files ...

# 2. Init — `-m` REQUIRED; do NOT use --no-prompt (Trap: empties {{ param }} secrets)
cd my-agent
PROJECT_ID="/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<acct>/projects/<proj>"
azd ai agent init -m manifest/ --project-id $PROJECT_ID -e dev
# ↑ prompts for github_pat HERE — only safe time to provide secrets

# 3. Required env flags
azd env set enableHostedAgentVNext "true" -e dev
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "gpt-5.4" -e dev

# 4. Provision (creates connections via Bicep)
azd provision -e dev

# 5. Deploy (creates toolbox versions, container image, agent)
azd deploy -e dev

# 6. Smoke test
azd ai agent invoke --new-session "What tools do you have?" --timeout 120
```

> **`-m` is required.** Without it, `azd ai agent init` errors out. `-m`
> can point to a specific `agent.yaml` file or a folder containing one;
> all files in the manifest dir get copied verbatim into
> `src/<agent-name>/`.

---

## Versioning workflow

Toolbox versions are **immutable snapshots**. Every `create` produces a
new `ToolboxVersionObject`. The parent `ToolboxObject.default_version`
controls which version the consumer endpoint serves.

### Create + test + promote

```python
from azure.ai.projects.models import (
    CodeInterpreterToolboxTool,
    WebSearchToolboxTool,
)

new_version = project.toolboxes.create_version(
    name="agent-tools",
    description="Added code interpreter",
    tools=[WebSearchToolboxTool(), CodeInterpreterToolboxTool()],
)

toolbox = project.toolboxes.update(
    name="agent-tools",
    default_version=new_version.version,
)
print(f"Active: {toolbox.default_version}")
```

### Rollback

```python
project.toolboxes.update(name="agent-tools", default_version="2")
```

`default_version` cannot be empty — to "remove" a version, promote
something else first, then `delete_version` the unwanted one.

### List + delete

```python
for version in project.toolboxes.list_versions("agent-tools"):
    print(f"{version.version} created {version.created_at}")
project.toolboxes.delete_version("agent-tools", "1")
```

Numeric version strings are returned and rendered under
`/versions/{version}`.

> **`azd` only supports CREATE** during deployment. Use the SDK or REST
> for list / get / promote / delete.

---

## MCP auth flavors (deeper)

The toolbox uses Foundry's connection registry to resolve MCP credentials.
Pick the connection `authType` that matches your MCP server.

### Key-based (`CustomKeys`)

```yaml
- kind: connection
  name: mcp-conn
  target: https://your-mcp-server.example.com
  category: RemoteTool
  authType: CustomKeys
  credentials:
    keys:
      Authorization: "Bearer {{ mcp_api_key }}"
- kind: toolbox
  name: tools
  tools:
    - type: mcp
      server_label: myserver
      server_url: https://your-mcp-server.example.com
      project_connection_id: mcp-conn
```

### OAuth — managed connector (Foundry Tools Catalog)

```yaml
- kind: connection
  name: github-oauth-conn
  category: RemoteTool
  authType: OAuth2
  target: https://api.githubcopilot.com/mcp
  connectorName: foundrygithubmcp     # name from Foundry Tools Catalog
- kind: toolbox
  name: oauth-tools
  tools:
    - type: mcp
      server_label: github
      project_connection_id: github-oauth-conn
```

### OAuth — custom app registration (BYO)

```yaml
- kind: connection
  name: mcp-oauth-custom-conn
  category: RemoteTool
  authType: OAuth2
  target: https://your-mcp-server.example.com
  authorizationUrl: https://auth.example.com/authorize
  tokenUrl: https://auth.example.com/token
  refreshUrl: https://auth.example.com/token
  scopes: []
  credentials:
    clientID: "{{ oauth_client_id }}"
    clientSecret: "{{ oauth_client_secret }}"
```

### Agent identity (Entra)

For MCP servers that authenticate via Entra and accept the agent's MI as
the caller. **Assign the appropriate RBAC role** on the target resource
to the agent identity first or `tools/list` returns 0:

```yaml
- kind: connection
  name: language-mcp
  category: RemoteTool
  authType: AgenticIdentity
  audience: <entra-audience>          # 🔑 required
  target: https://<resource>.cognitiveservices.azure.com/language/mcp?api-version=2025-11-15-preview
```

> **ARM REST equivalent**: `authType: ProjectManagedIdentity`, audience
> moves to `metadata.audience`. See § ARM REST equivalents below for
> the full mapping and a working PUT body.

### User Entra token (1P OBO)

For MCP servers that need the calling user's identity (mail, calendar,
files):

```yaml
- kind: connection
  name: workiq-mail-conn
  category: RemoteTool
  authType: UserEntraToken
  audience: <entra-app-id>            # 🔑 required — without it, tools/list returns 0
  target: https://agent365.svc.cloud.microsoft/agents/servers/mcp_MailTools
```

> **First-time consent.** OAuth-based MCPs return `CONSENT_REQUIRED`
> (code `-32006`) on first call with a consent URL in `error.message`.
> Surface this to the user, have them open the URL in a browser,
> complete the OAuth flow, then retry. Subsequent calls succeed
> silently.

### ARM REST equivalents (when not using `azd ai agent init`)

Everything above is the **declarative DSL** that `azd ai agent init` /
`azd ai agent provision` consumes. When you provision the same
`RemoteTool` connection imperatively (ARM REST PUT, Bicep, or any
non-azd path — common in BYOC / Bicep-only pilots), the ARM API
**rejects** `authType: AgenticIdentity` AND `authType: AAD` with:

```
ValidationError: AuthType for RemoteTool Connection can only be
  None, CustomKeys, ProjectManagedIdentity, OAuth2, DeveloperConnection,
  UserEntraToken, ...
```

Mapping table (declarative DSL → ARM REST `authType`):

| Declarative `authType` | ARM REST `authType` | Where the audience goes |
|---|---|---|
| `AgenticIdentity` (agent / Entra MI) | **`ProjectManagedIdentity`** | `metadata.audience` |
| `UserEntraToken` (1P OBO) | `UserEntraToken` | `metadata.audience` |
| `OAuth2Managed` (built-in OAuth) | `OAuth2` | `metadata.{authorizationUrl,tokenUrl,scopes,clientId,...}` |
| `Key` | `CustomKeys` | `credentials.keys.{name}` |
| `None` | `None` | (n/a) |

Working ARM REST PUT body for the AgenticIdentity case (Search KB MCP):

```http
PUT /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<acct>/projects/<proj>/connections/<conn-name>?api-version=2025-10-01-preview

{
  "properties": {
    "category": "RemoteTool",
    "target": "https://<search>.search.windows.net/knowledgebases/<kb>/mcp?api-version=2025-11-01-preview",
    "authType": "ProjectManagedIdentity",
    "isSharedToAll": true,
    "metadata": { "audience": "https://search.azure.com" }
  }
}
```

> **SDK split ownership:** `azure-ai-projects` 2.3.0 provides writable
> `project.toolboxes`, while `project.connections` remains read-only for
> project connection discovery. Provision new `RemoteTool` connections with
> Bicep or the documented ARM connection API, then reference the connection
> ID from the Toolbox model.

---

## Tool-by-tool quirks

### `azure_ai_search` — INDEX, not Knowledge Base

Toolbox `azure_ai_search` only exposes `index_name` + `query_type`
(default `vector_semantic_hybrid`) + `top_k` (default 5) + `filter`. It
does **NOT** invoke a Knowledge Base's agentic retrieval (query planning,
multi-hop, answer synthesis with citations).

If you need KB-grade retrieval through a toolbox, use the `mcp` tool
type pointing at the KB MCP endpoint with a connection that authenticates
PMI to `https://search.azure.com/.default`.

> **Cross-skill ownership note:** For producing a KB-MCP server on ACA, see `foundry-mcp-aca`. For consuming a KB via the IQ-style pattern, see `foundry-iq`. **THIS SKILL covers the toolbox WRAPPER pattern for a KB-MCP** — i.e. exposing it as a managed multi-tool through the toolbox endpoint.

**Declarative example (azd ai agent init):**

```yaml
- kind: connection
  name: kb-mcp
  category: RemoteTool
  authType: AgenticIdentity
  audience: https://search.azure.com
  target: https://<search>.search.windows.net/knowledgebases/<kb-name>/mcp?api-version=2025-11-01-preview
- kind: toolbox
  name: tools
  tools:
    - type: mcp
      server_label: kb
      project_connection_id: kb-mcp
```

The trade-off: extra hop through Toolbox, inherits the `ping` trap, but
the Toolbox handles centralized token refresh. See `foundry-iq` SKILL §
"KB access from a hosted MAF agent — three routes" for the direct-wire alternative.

**Imperative provisioning (ARM REST + SDK):** When `azd ai agent init`'s
declarative pipeline is not available (Bicep-only / IaC-only pilots),
provision the connection via ARM REST and the toolbox via the SDK:

```python
import os

import requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPToolboxTool
from azure.identity import DefaultAzureCredential


with DefaultAzureCredential() as credential:
    arm_token = credential.get_token(
        "https://management.azure.com/.default"
    ).token
    connection_url = (
        f"https://management.azure.com/subscriptions/{os.environ['SUB']}"
        f"/resourceGroups/{os.environ['RG']}/providers"
        f"/Microsoft.CognitiveServices/accounts/{os.environ['ACCT']}"
        f"/projects/{os.environ['PROJ']}/connections/kb-mcp"
        f"?api-version=2025-10-01-preview"
    )
    response = requests.put(
        connection_url,
        headers={
            "Authorization": " ".join(("Bearer", arm_token)),
            "Content-Type": "application/json",
        },
        json={
            "properties": {
                "category": "RemoteTool",
                "target": os.environ["KB_MCP_URL"],
                "authType": "ProjectManagedIdentity",
                "isSharedToAll": True,
                "metadata": {"audience": "https://search.azure.com"},
            },
        },
        timeout=60,
    )
    response.raise_for_status()

    with AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=credential,
    ) as project:
        connection = project.connections.get("kb-mcp")
        toolbox_version = project.toolboxes.create_version(
            name="agent-tools",
            tools=[
                MCPToolboxTool(
                    server_label="kb",
                    server_url=os.environ["KB_MCP_URL"],
                    project_connection_id=connection.id,
                    require_approval="never",
                ),
            ],
        )
        project.toolboxes.update(
            name="agent-tools",
            default_version=toolbox_version.version,
        )
```

Consumer endpoint the agent binds to:

```
{FOUNDRY_ENDPOINT}/api/projects/{PROJ}/toolboxes/agent-tools/mcp?api-version=v1
```

### `code_interpreter` & `file_search` — no user isolation

When invoked through a toolbox in a hosted agent context, `code_interpreter`
and `file_search` **share container / vector store state across all users
of the project**. Do not put per-user data in either when deployed
multi-tenant. Use a per-user MCP server backed by Cosmos with row-level
security if you need isolation.

### `file_search` — no VNet support

Unlike every other tool type, `file_search` is **NOT supported** when the
Foundry project uses network isolation (private link). If your customer
mandates VNet (`foundry-vnet-deploy`), drop file_search from the toolbox
and substitute Foundry IQ KB or a custom MCP server backed by AI Search
on a private endpoint.

### `web_search` — first-party billing, no DPA

Grounding with Bing Search is governed by separate terms and is **not
covered by Microsoft's Data Protection Addendum**. Data sent to the Bing
backend leaves Foundry's compliance boundary. Confirm with the customer
before enabling in regulated industries (FSI, HCLS, public sector).

### `openapi` — Foundry project MI must have RBAC

When using `auth.type: managed_identity`, the Foundry **project's** MI
(not the agent's MI) calls the API. Assign the appropriate RBAC role on
the target service to that MI before deploying or every call returns
`401 Unauthorized`.

### Multi-instance — `name` field required

```
400 invalid_payload: Multiple tools without identifiers found...
```

Add a unique `name` field to each instance of the same tool type. The
`name` doubles as the user-facing tool name (without `server_label`
prefix for MCP).

---

## Approval gating (`require_approval`)

The toolbox returns `_meta.tool_configuration.require_approval` on every
tool entry from `tools/list`. **Enforcement is the agent runtime's
responsibility — the MCP endpoint does NOT block `tools/call`** based on
this flag.

```python
async def fetch_approval_map(endpoint, headers):
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as hc:
        resp = await hc.post(
            endpoint,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        resp.raise_for_status()
    return {
        t["name"]: t["_meta"]["tool_configuration"]["require_approval"]
        for t in resp.json().get("result", {}).get("tools", [])
        if t.get("_meta", {}).get("tool_configuration", {}).get("require_approval")
    }
```

In MAF / LangGraph, query at startup, build the approval map, then either:

- inject a system-prompt constraint listing the tools that require user
  confirmation, OR
- use a tool-execution interceptor that pauses for human approval (see
  `threadlight-hitl-patterns` SKILL for the Adaptive Card 1.5 wrapper)

---

## VNet support matrix

| Tool type | VNet | Traffic flow |
|---|---|---|
| `mcp` | ✅ | Through your VNet subnet |
| `azure_ai_search` | ✅ | Through private endpoint |
| `code_interpreter` | ✅ | Microsoft backbone network |
| `web_search` | ✅ | Public endpoint (Bing — outside DPA) |
| `openapi` | ✅ | Depends on target API network configuration |
| `file_search` | ❌ | **Not supported in VNet — drop or substitute** |
| `a2a_preview` | ✅ | Through private endpoint |

Pair this with `foundry-vnet-deploy` SKILL when the customer mandates
network isolation. The `file_search` gap is the most common gotcha —
discover early during design (`threadlight-design` SPEC § 7c).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `server_error` on every invoke, hosted MAF agent | `MCPStreamableHTTPTool._ensure_connected()` ping (Trap 1) | Override `_ensure_connected` with no-op (see Trap 1) |
| `500` on agent startup | Client called `prompts/list` (Trap 2) | `load_prompts=False` |
| `500` on `tools/call` with no streaming | `stream=False` (Trap 3) | Use `stream=True` (default) |
| Custom env var disappeared at runtime | `FOUNDRY_*` reserved (Trap 4) | Rename to `TOOLBOX_*` |
| `tools/list` returns 0 tools (MCP / A2A) | Bad connection creds, missing `audience`, MI lacks RBAC | Verify `project_connection_id` exists; `UserEntraToken` / `AgenticIdentity` need `audience`; check RBAC on target |
| `tools/list` returns 0 tools (OpenAPI) | Malformed OpenAPI spec | Validate spec is OpenAPI 3.0 / 3.1 with `paths`, `operationId`, parameter schemas |
| `tools/list` returns 0 tools (built-in) | Toolbox not provisioned yet, or tool unsupported in region | Wait 10s and retry; check region compatibility table |
| `tools/list` returns fewer tools than expected | `allowed_tools` filter has wrong / misspelled names (case-sensitive) | Remove filter, list all, set exact names from response |
| `400 Multiple tools without identifiers` | Two unnamed instances of same type | Add unique `name` field |
| `CONSENT_REQUIRED` (`-32006`) | First-time OAuth flow | Open URL from `error.message`, complete consent, retry |
| `401` on MCP calls | Expired token or wrong scope | Use `https://ai.azure.com/.default`; refresh token |
| `400` / `404` with no detail | Missing `Foundry-Features: Toolboxes=V1Preview` header | Add the header to every request |
| Tool name not found | MCP names are prefixed with `server_label` | Use `{server_label}.{tool_name}` (or `_` for Copilot SDK) |
| `--no-prompt` left `{{ param }}` empty | `azd ai agent init --no-prompt` skips secret prompts | Re-run init WITHOUT `--no-prompt`; supply secrets interactively |

---

## Cross-skill references

| If you need to… | Go to |
|---|---|
| Build a custom MCP server, then bundle it into a toolbox | `foundry-mcp-aca` (build) → wire into `kind: toolbox` (this skill) |
| Wire a hosted MAF agent (runtime, RBAC, identity, SkillsProvider) | `foundry-hosted-agents` |
| Use `MCPStreamableHTTPTool + header_provider` (per-call AAD) | `foundry-hosted-agents` § "MCP with per-call AAD bearer" |
| Understand the MCP `ping` trap broadly | `foundry-hosted-agents` § "MCP `ping` trap on Foundry-hosted MCP servers" |
| Get KB-grade RAG (planning, multi-hop, citations) | `foundry-iq` (NOT Toolbox `azure_ai_search`) |
| Wrap a KB MCP behind a Toolbox | `foundry-iq` § Common Errors (`/knowledgebases/<n>/mcp` rows) + this skill § "azure_ai_search — INDEX, not KB" |
| Deploy with `azd ai agent` extension | `foundry-hosted-agents` § azure.yaml (azd ai agent Extension) |
| Compose toolbox into a full Threadlight pipeline | `threadlight-deploy` § Foundry Toolbox Setup (uses this skill as the deep dive) |
| Network-isolated deploy (VNet) | `foundry-vnet-deploy` (and check the VNet matrix above for `file_search` gap) |
| HITL approval gating UI | `threadlight-hitl-patterns` |
| Vision / DocIntel / Speech tools wrapped via Toolbox | `foundry-doc-vision-speech` patterns + `openapi` or `mcp` tool type |

---

## Catalog history

- `1.0.0` — initial skill. Covers all 7 tool types, the 4 silent traps,
  MAF / LangGraph / Copilot SDK / azd wire-up, versioning workflow, MCP
  auth flavors, VNet matrix, and cross-references to existing
  `foundry-hosted-agents` and `foundry-iq` Toolbox callouts.

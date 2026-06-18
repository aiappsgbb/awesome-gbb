---
name: foundry-toolbox
description: >
  Wire the Microsoft Foundry Toolbox into hosted agents — a managed
  multi-tool bundle (mcp, web_search, azure_ai_search, code_interpreter,
  file_search, openapi, a2a_preview) behind a single MCP endpoint with
  centralized credentials, token refresh, and versioning. Documents the
  mandatory `Foundry-Features: Toolboxes=V1Preview` header, the four
  silent traps (ping, prompts/list, non-streaming tools/call, reserved
  FOUNDRY_* env vars), the azure_ai_search-is-INDEX-not-KB nuance, and
  the `azd ai agent init` declarative path with `kind: toolbox` +
  `{{ param }}` secrets.
  USE FOR: foundry toolbox, toolbox MCP endpoint, Foundry-Features
  Toolboxes V1Preview, kind toolbox agent.yaml,
  toolbox version promote, multi-tool MCP endpoint, MCPStreamableHTTPTool,
  AzureAIProjectToolbox.
  DO NOT USE FOR: building MCP servers (use foundry-mcp-aca), KB-only
  RAG (use foundry-iq), generic hosted-agent runtime (use
  foundry-hosted-agents), cross-resource models (use
  foundry-cross-resource), Web IQ web grounding (use foundry-webiq).
metadata:
  version: "1.6.2"
  validated: 2026-06-01
---

# Microsoft Foundry Toolbox — Reference Guide

The **Foundry Toolbox** is a managed Foundry resource that bundles multiple
tools (MCP servers, web search, AI Search indexes, code interpreter, file
search, OpenAPI specs, agent-to-agent calls) behind a **single MCP
endpoint** — agents connect to one URL, and the platform handles credential
injection, token refresh, policy enforcement, and version pinning.

Use this skill when an agent needs more than one tool, when you want to
swap or reconfigure tools without redeploying the agent, or when you need
the platform's centralized credential vault for OAuth/Entra/key auth.
Wire-up patterns are documented for **MAF**, **LangGraph**, the **GitHub
Copilot SDK**, and **`azd ai agent init`** declarative deployment.

```
┌───────────────────────────────────────────────────────────────┐
│           Foundry Project (managed namespace)                 │
│                                                                │
│  ┌──────────────────────────────────────────────────┐         │
│  │  Toolbox: my-toolbox                             │         │
│  │   ├─ default_version → v3                        │         │
│  │   ├─ v1, v2, v3 (immutable ToolboxVersionObject) │         │
│  │   └─ tools[]:                                    │         │
│  │      ├─ web_search                               │         │
│  │      ├─ azure_ai_search (INDEX, not KB)          │         │
│  │      ├─ mcp (server_label, project_connection_id)│         │
│  │      ├─ code_interpreter                         │         │
│  │      ├─ file_search (vector_store_ids)           │         │
│  │      ├─ openapi (spec + auth)                    │         │
│  │      └─ a2a_preview (base_url + connection)      │         │
│  └────────────────────┬─────────────────────────────┘         │
│                       │                                        │
│         exposed via:  │                                        │
│   {project}/toolboxes/my-toolbox/mcp?api-version=v1            │
│         (consumer endpoint — always serves default_version)    │
│                       │                                        │
│   {project}/toolboxes/my-toolbox/versions/v3/mcp?...           │
│         (developer endpoint — pin a specific version)          │
└───────────────────────┼────────────────────────────────────────┘
                        │
                        ▼  every request MUST carry:
                  Authorization: Bearer <AAD token, scope https://ai.azure.com/.default>
                  Foundry-Features: Toolboxes=V1Preview
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   MAF Agent      LangGraph Agent   Copilot SDK Agent
  (MCPStreamable  (AzureAIProject   (MCP bridge with
   HTTPTool +      Toolbox          dots→underscores
   httpx.Auth)     one-liner)       in tool names)
```

---

## ⚠️ Toolbox is for code-based agents only (no Prompt / Declarative wiring)

> **Verified end-to-end against a live Foundry project (May 2026):**
> Toolboxes are consumed by an **MCP client running inside the agent's
> code** — MAF (`MCPStreamableHTTPTool`), LangGraph (`AzureAIProjectToolbox`),
> Copilot SDK (custom `McpBridge`), or any framework that speaks
> Streamable-HTTP MCP. **There is no declarative `tools=[{type: "toolbox",
> toolbox_name: ...}]` shape on a Foundry Prompt agent.** The Foundry agent
> runtime accepts only this fixed list of `tools[].type` values:
> `code_interpreter`, `function`, `namespace`, `tool_search`, `file_search`,
> `web_search_preview`, `web_search_preview_2025_03_11`, `image_generation`,
> `mcp`, `custom`, `computer`, `computer_use_preview`, `shell`, `apply_patch`.
> No `toolbox` type.

Why this matters: a Prompt agent can wire *individual* tools (code_interpreter,
mcp pointing at a server, etc.) directly via its `tools` array, but it
**cannot** delegate the bundle-of-tools fan-out to a toolbox endpoint at
the runtime layer. The bundling lives one layer up — in the agent's code.

What about wiring `tools=[{type: "mcp", server_url: <toolbox_mcp_endpoint>}]`?
**Don't.** It passes shape validation at create time, but at invoke time
the agent runtime calls the toolbox MCP endpoint **without** any `Authorization`
header (no project-managed-identity injection), so it gets `401
PermissionDenied` from the toolbox endpoint regardless of what RBAC you
grant the agent's `instance_identity`. Toolboxes need an MCP client that
mints its own bearer token per request — exactly what
`MCPStreamableHTTPTool` + `httpx.Auth` does in Pattern A below.

Other dead ends ruled out by direct testing (May 2026):

- `type: "namespace"` — exists, but `tools[]` inside a namespace only
  accepts `function` and `custom` types. It's a way to group developer
  functions, not a wrapper for toolboxes.
- `type: "tool_search"` — newer OpenAI feature unsupported on
  `gpt-4.1-mini` and has no `toolbox_name` / `namespaces` / `sources` /
  `toolboxes` fields. It's not the toolbox consumer.
- `type: "mcp"` + `project_connection_id` — the runtime DOES resolve the
  connection (proven via a deliberate "not found" error path), but
  toolbox endpoints require a fresh AAD bearer per request. Foundry
  connections that hold static API keys can't authenticate to a toolbox
  endpoint, so this path is blocked at the auth layer.

If you want a Prompt-only agent (no code container) and you need just one
or two tools, wire those tools directly into the Prompt agent's `tools`
array — skip the toolbox abstraction entirely.

---

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

7 tool types. Each can appear at most **once without a `name` field** per
toolbox; for multiple instances of the same type, set a unique `name` on
each. Always add a `description` so the model picks the right tool.

| Type | Required fields | Auth | VNet | Quirks |
|---|---|---|---|---|
| `mcp` | `server_label`, `server_url` | None / Key / OAuth-managed / OAuth-custom / AgenticIdentity (Entra) / UserEntraToken (1P OBO) — via `project_connection_id` | ✅ via VNet subnet | Tool names prefixed `{server_label}.{tool_name}` from the MCP server side; **when wrapped via MAF `MCPStreamableHTTPTool` with `tool_name_prefix=X`, the agent-visible name FLATTENS to `X_{tool_name}` and `server_label` is dropped** (validated MAF 1.3.0 + Toolbox v1, May 2026). `UserEntraToken` requires `audience` field or `tools/list` returns 0 |
| `web_search` | (none) | Bing Grounding (no project conn) or `web_search.custom_search_configuration.project_connection_id` | ✅ public endpoint | Uses Grounding with Bing — first-party, billed separately, **no DPA**. Citations in `content[].resource._meta.annotations[]` |
| `azure_ai_search` | `index_name`, `project_connection_id` | API key or MI via connection | ✅ private endpoint | **Wraps an INDEX, not a Knowledge Base** — no agentic query planning. For KB → use `mcp` tool type pointing at `/knowledgebases/<n>/mcp` (see `foundry-iq`). Defaults `top_k=5`, `query_type=vector_semantic_hybrid` |
| `code_interpreter` | (none); optional `container.file_ids[]` | (none) | ✅ Microsoft backbone | **User isolation NOT supported in hosted agents** — all users share the same container context |
| `file_search` | `vector_store_ids[]` | (none) | ❌ **Not supported in VNet** | **User isolation NOT supported in hosted agents**. Vector stores created via `{project}/openai/v1/vector_stores` |
| `openapi` | `spec`, `auth.type` | `anonymous` / `connection` / `managed_identity` (Foundry project MI) | ✅ depends on target | MI auth requires RBAC on target. Spec must be OpenAPI 3.0 / 3.1 with `paths` + `operationId` |
| `a2a_preview` | `base_url`, `project_connection_id` | Connection-driven (e.g. `RemoteA2A`) | ✅ private endpoint | Calls another agent as a tool |

### Per-tool anti-patterns

- **`azure_ai_search` tool:** DO NOT use when you need vector + keyword hybrid search in a VNet-injected agent (file_search VNet support is broken as of May 2026). DO use a custom MCP-wrapped AI Search in those cases, wired via the `mcp` tool type.
- **`file_search` tool:** DO NOT use in VNet-isolated Foundry projects (the file_search backend doesn't yet support PMI in VNet). DO use Cosmos MCP or custom AI Search MCP via `foundry-mcp-aca` or wire directly with `mcp` tool type.
- **`code_interpreter` tool:** DO NOT use for long-running computations (>5 min wall-clock) — the container will timeout and fail silently. DO use ACA Jobs via `azd-patterns` for batch work.
- **`web_search` tool:** DO NOT enable in regulated-data contexts without explicit allow-listing of source domains. DO use the `allowed_domains` parameter when you need to scope results to a restricted set of trusted sources.

---

## The mandatory `Foundry-Features` header

> **🛑 EVERY request to the toolbox MCP endpoint MUST include the header
> `Foundry-Features: Toolboxes=V1Preview`. Calls that omit this header
> fail.** Include it in HTTP clients, MCP transports, and any SDK wrapper
> that calls the toolbox endpoint.

| Element | Value |
|---|---|
| **HTTP header** | `Foundry-Features: Toolboxes=V1Preview` |
| **AAD token scope** | `https://ai.azure.com/.default` |
| **Bearer header** | `Authorization: Bearer <token>` |
| **API version query** | `?api-version=v1` |

If you forget the `Foundry-Features` header you get a generic 400 / 404
with no useful signal — debug the symptom by curling the endpoint with
`-v` and inspecting your headers FIRST.

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

## The 4 silent traps (CRITICAL — read before wiring)

These are documented in the Microsoft Learn troubleshooting table, but
they're buried at the bottom and they all surface as opaque `500` /
`server_error` responses with no useful log signal.

### Trap 1 — `500` on `send_ping()`

The Foundry Toolbox MCP server **does not implement the optional MCP
`ping` method**. MAF's `MCPStreamableHTTPTool._ensure_connected()` calls
`send_ping()` automatically during agent registration. When it fires, the
agent fails to register and **every invoke returns `server_error` from
the responses endpoint**.

**Fix:** override `_ensure_connected` with a no-op subclass:

```python
from agent_framework import MCPStreamableHTTPTool

class ToolboxMCPTool(MCPStreamableHTTPTool):
    """MCPStreamableHTTPTool that skips the ping-on-connect probe.
    Foundry Toolbox endpoint returns HTTP 500 on `ping`."""
    async def _ensure_connected(self) -> None:  # noqa: D401
        # Skip the ping; assume the transport is healthy.
        if self._client is None:
            await self.connect()
```

This is the **same trap** documented in `foundry-hosted-agents` SKILL §
"MCP `ping` trap on Foundry-hosted MCP servers" — the cross-link is
deliberate: the hosted-agents skill treats it generically (any
Foundry-hosted MCP), this skill treats it specifically (every Toolbox
endpoint by design).

### Trap 2 — `500` on `prompts/list`

The Foundry MCP server does not implement `prompts/list`. Many MCP
clients (including MAF's) call it on init by default.

**Fix:** pass `load_prompts=False` (or framework equivalent):

```python
mcp_tool = ToolboxMCPTool(
    name="toolbox",
    url=TOOLBOX_ENDPOINT,
    http_client=http_client,
    load_prompts=False,           # 🔑 do not call prompts/list
)
```

### Trap 3 — `500` on non-streaming `tools/call`

Non-streaming mode (`stream=False`) is **not supported** for Toolbox MCP
endpoints. Most MCP client SDKs default to streaming — but if you've
explicitly disabled it for debugging, every call will fail.

**Fix:** keep `stream=True` (the default for `streamablehttp_client` and
`MCPStreamableHTTPTool`).

### Trap 4 — `FOUNDRY_*` env-var overwrite

The platform **reserves all environment variables prefixed with
`FOUNDRY_`** and may silently overwrite user-defined values at runtime.
If you name your custom env var `FOUNDRY_TOOLBOX_ENDPOINT`, the runtime
will overwrite it with whatever it injects, and your code will read the
wrong URL with no warning.

**Fix:** rename custom env vars to avoid the `FOUNDRY_` prefix. The
catalog convention is `TOOLBOX_*` (e.g. `TOOLBOX_MCP_ENDPOINT`,
`TOOLBOX_NAME`).

Platform-injected variables you can safely depend on:

| Variable | Set by | Value |
|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Platform | `{project}` base URL |
| `FOUNDRY_AGENT_TOOLBOX_ENDPOINT` | Platform | Toolbox base URL (without `/{toolbox}/mcp` suffix) |
| `TOOLBOX_{NAME}_MCP_ENDPOINT` | Platform | Full per-toolbox endpoint — for toolbox `agent-tools` → `TOOLBOX_AGENT_TOOLS_MCP_ENDPOINT` |

Read these in `main.py` / `container.py` instead of hard-coding URLs.

---

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
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, WebSearchTool, AzureAISearchTool

project = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

toolbox_version = project.beta.toolboxes.create_version(
    name="agent-tools",
    description="Web search + product index + GitHub MCP",
    tools=[
        WebSearchTool(),
        AzureAISearchTool(
            index_name="products",
            project_connection_id="aisearch-conn",
        ),
        MCPTool(
            server_label="github",
            server_url="https://api.githubcopilot.com/mcp",
            require_approval="never",
            project_connection_id="github-mcp-conn",
        ),
    ],
)
print(f"Created {toolbox_version.name} v{toolbox_version.version}")
```

> **SDK signature note:** the actual method on `azure-ai-projects` 2.1.0
> is `client.beta.toolboxes.create_version(name=..., tools=[...])`. The
> Microsoft Learn doc shows `create_toolbox_version(toolbox_name=...)` —
> that's an older name kept in some samples. The SDK exposes
> `create_version`, `get`, `list`, `delete`, `update`, `get_version`,
> `list_versions`, and `delete_version` on `client.beta.toolboxes`.

> **Current API matrix (validated 2026-05-28):**
>
> | Package | Validated version | Notes |
> |---|---|---|
> | agent-framework-core | 1.7.0 | MAF core runtime |
> | agent-framework-foundry | 1.7.0 | Foundry integration; 1.3.0+ removed `get_toolbox()` |
> | agent-framework-foundry-hosting | 1.0.0a260521 | Alpha; ResponsesHostServer (contains May-2026 fixes) |
> | azure-ai-projects | latest GA | SDK toolbox CRUD methods |
> | mcp | 1.10+ | Streamable HTTP transport |
> | httpx | latest | HTTP client for auth flow |
> | Pre-1.6 agent-framework versions | **legacy — not validated for current pilots** | Migrate to 1.6.0+ for production |

The first call creates the toolbox AND its `v1`, auto-promoted to
default. Subsequent calls create new versions that stay un-promoted
until you call `update(default_version=...)`.

`AIProjectClient` must be constructed with **`allow_preview=True`** for
the `client.get_openai_client(agent_name=...)` agent-scoped helper used
in Pattern A below to be available; the toolbox CRUD methods on
`client.beta.toolboxes` work without it.

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
    headers={"Foundry-Features": "Toolboxes=V1Preview"},  # 🔑 mandatory
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
import asyncio, os
from azure.identity import DefaultAzureCredential
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

url = (
    f"{os.environ['FOUNDRY_PROJECT_ENDPOINT']}/toolboxes/agent-tools"
    f"/versions/v3/mcp?api-version=v1"
)
token = DefaultAzureCredential().get_token("https://ai.azure.com/.default").token
headers = {
    "Authorization": f"Bearer {token}",
    "Foundry-Features": "Toolboxes=V1Preview",
}

async def verify():
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            print(f"Tools found: {len(tools_result.tools)}")
            for t in tools_result.tools:
                print(f"  - {t.name}: {(t.description or '')[:80]}")

asyncio.run(verify())
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
# 1. Create new version (does NOT auto-promote, except for the very first)
new_v = project.beta.toolboxes.create_version(
    name="agent-tools",
    description="v4 — added file_search",
    tools=[...new_tool_list...],
)

# 2. Test against the version-specific endpoint (Step 3 verify pattern)
#    OR run a staging agent with the version-specific URL

# 3. Promote — atomically updates default_version
toolbox = project.beta.toolboxes.update(
    toolbox_name="agent-tools",
    default_version=new_v.version,
)
print(f"Active: {toolbox.default_version}")
```

### Rollback

```python
# Promote a previous version back to default
project.beta.toolboxes.update(
    toolbox_name="agent-tools",
    default_version="v2",
)
```

`default_version` cannot be empty — to "remove" a version, promote
something else first, then `delete_version` the unwanted one.

### List + delete

```python
versions = list(project.beta.toolboxes.list_versions("agent-tools"))
for v in versions:
    print(f"{v.version}  created {v.created_at}")

project.beta.toolboxes.delete_version("agent-tools", "v1")
```

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

> **SDK split-ownership trap.** `azure-ai-projects==2.1.0` exposes
> `client.beta.toolboxes.create_version / update / get / list / delete`
> (✅ writeable) BUT `client.connections` is **read-only**
> (`get / list / get_default` only — no `.create()`). So Toolbox can
> be SDK-provisioned end-to-end, but the `RemoteTool` connection MUST
> go via ARM REST PUT (above) or Bicep. This split is undocumented
> upstream and reliably traps anyone porting an `azd ai agent init`
> pilot to a Bicep-only / IaC-only deployment shape.

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
import os, requests
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
arm_token = cred.get_token("https://management.azure.com/.default").token

# 1. Connection — ARM REST PUT (SDK client.connections is read-only)
requests.put(
    f"https://management.azure.com/subscriptions/{os.environ['SUB']}"
    f"/resourceGroups/{os.environ['RG']}/providers"
    f"/Microsoft.CognitiveServices/accounts/{os.environ['ACCT']}"
    f"/projects/{os.environ['PROJ']}/connections/kb-mcp"
    f"?api-version=2025-10-01-preview",
    headers={"Authorization": f"Bearer {arm_token}",
             "Content-Type": "application/json"},
    json={"properties": {
        "category": "RemoteTool",
        "target": os.environ["KB_MCP_URL"],
        "authType": "ProjectManagedIdentity",
        "isSharedToAll": True,
        "metadata": {"audience": "https://search.azure.com"},
    }},
).raise_for_status()

# 2. Toolbox + version — SDK
project = AIProjectClient(endpoint=os.environ["FOUNDRY_ENDPOINT"],
                          credential=cred, allow_preview=True)
project.beta.toolboxes.create_version(
    name="agent-tools",
    tools=[MCPTool(server_label="kb", project_connection_id="kb-mcp")],
)
project.beta.toolboxes.update(name="agent-tools", default_version=1)
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

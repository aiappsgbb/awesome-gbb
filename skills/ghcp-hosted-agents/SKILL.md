---
name: ghcp-hosted-agents
description: >
  Deploy Foundry hosted agents using GitHub Copilot SDK (GHCP) with BYOK
  authentication and Invocations protocol. Alternative to MAF (Agent +
  FoundryChatClient + ResponsesHostServer). Use when you need streaming SSE
  output, progressive skill discovery, or long tool loops (>120s) that hit
  Foundry gateway timeout with Responses protocol.
  USE FOR: ghcp sdk, copilot sdk, github copilot agent, CopilotClient,
  InvocationAgentServerHost, BYOK, bring your own key, invocations protocol,
  SSE streaming agent, long running agent, send_and_wait timeout,
  ghcp hosted agent, copilot client foundry.
  DO NOT USE FOR: MAF agents (use foundry-hosted-agents), prompt agents,
  declarative agents, general Azure deploy.
---

# GHCP SDK Hosted Agents on Foundry

Deploy Foundry hosted agents using the **GitHub Copilot SDK** with BYOK
(Bring Your Own Key) authentication. No `GITHUB_TOKEN` required. Uses the
**Invocations protocol** with SSE streaming for unlimited tool-loop duration.

## When to Use GHCP SDK Instead of MAF

| Consideration | MAF | GHCP SDK |
|---------------|-----|----------|
| **Auth** | `DefaultAzureCredential` → `FoundryChatClient` | BYOK: `DefaultAzureCredential` → bearer token |
| **Protocol** | Responses API (request/response) | Invocations (SSE streaming) |
| **Tool loop limit** | ~120s (Foundry gateway timeout) | ♾️ (SSE keeps connection alive) |
| **Skill discovery** | Manual (load into instructions) | `SkillsProvider` progressive loading |
| **Custom tools** | `@tool` decorator | Not supported (use MCP servers instead) |
| **Toolbox** | `client.get_toolbox()` | Not directly available |
| **Maturity** | Production-proven | Validated (identical eval scores) |

**Use GHCP SDK when:**
- Agent has tool-heavy workflows taking >120s (web scraping, multi-site scanning)
- You need streaming output (events flow continuously to the caller)
- You want `SkillsProvider` progressive skill discovery

**Use MAF when:**
- Agent needs custom `@tool` functions
- Agent needs Foundry Toolbox (`web_search`, `code_interpreter`)
- Simpler deployment (fewer moving parts)

---

## Runtime Pattern (GHCP SDK + Invocations)

**Copy the reference template** at `references/container.py` into the project root.
Then adapt `_load_mcp_servers()` for your MCP server configuration.

The template provides:
1. `_init_byok()` / `_get_provider()` — BYOK auth with `DefaultAzureCredential`
2. `_ensure_session()` — Creates/resumes `CopilotClient` session with provider, skills, MCP
3. `_stream_response()` — Subscribes to session events, yields SSE
4. `handle_invoke()` — `@app.invoke_handler` that returns `StreamingResponse`

```
container.py → CopilotClient + InvocationAgentServerHost → port 8088
  ├── BYOK auth (ai.azure.com scope)
  ├── Skills via skill_directories parameter
  ├── MCP servers via mcp_servers parameter
  └── SSE streaming (no timeout on long tool loops)
```

**Key points:**
- `FOUNDRY_PROJECT_ENDPOINT` is **injected by the platform** — never declare in agent.yaml
- BYOK scope is `https://ai.azure.com/.default` — NOT `cognitiveservices.azure.com`
- Token is static per session — `_get_provider()` mints fresh token each session creation
- `working_directory` should be `$HOME` (hosted agents sandbox filesystem at home dir)
- `system_message` requires dict format: `{"mode": "replace", "content": "..."}`
- `PermissionHandler.approve_all` auto-approves tool calls (required for unattended agents)

---

## Why Invocations Protocol (Not Responses)

The GHCP SDK can also run behind `ResponsesHostServer` using `GitHubCopilotAgent`:

```python
# ⚠️ This pattern DOES NOT WORK for long tool loops on Foundry
from agent_framework_foundry_hosting import ResponsesHostServer
from agent_framework.github import GitHubCopilotAgent

agent = GitHubCopilotAgent(...)
server = ResponsesHostServer(agent)
server.run()
```

**Why it fails:** `GitHubCopilotAgent.send_and_wait()` blocks until the full response
completes. Default timeout is 60s (configurable). But **Foundry's gateway has a ~120s
hard timeout** on non-streaming responses. Any tool-heavy workflow (web scraping,
multi-site scanning) taking >120s returns a gateway timeout.

**Invocations protocol solves this:** SSE events stream continuously, keeping the
connection alive. A query using 50+ tool calls over 5 minutes works perfectly because
events flow throughout.

| Approach | Max Duration | Why |
|----------|-------------|-----|
| ResponsesHostServer + send_and_wait | ~120s | Foundry gateway timeout on non-streaming |
| InvocationAgentServerHost + SSE | Unlimited | Events stream continuously |

---

## agent.yaml

**Copy** `references/agent.yaml` into your project root and adapt:

- `name` — your agent name
- `description` — your agent description
- `environment_variables` — add MCP server FQDNs if needed

**Critical:** Use `protocol: invocations` (not `responses`). Version must be semver `1.0.0`.

---

## pyproject.toml

**Copy** `references/pyproject.toml` into your project root and update `name` and `version`.

**Notes:**
- `github-copilot-sdk` provides `CopilotClient`, session management, event types
- `azure-ai-agentserver-invocations` provides `InvocationAgentServerHost`
- `azure-identity` pinned to avoid pulling beta versions
- `prerelease = "if-necessary-or-explicit"` needed for beta agentserver package

---

## Dockerfile

**Copy** `references/Dockerfile` into your project root. No changes needed for most agents.

---

## BYOK Authentication Deep Dive

BYOK (Bring Your Own Key) lets `CopilotClient` use your Foundry model deployment
instead of GitHub's hosted models. No `GITHUB_TOKEN` needed.

### How It Works

```
CopilotClient.create_session(provider={...})
  └── Routes LLM calls to your Foundry project endpoint
      └── Uses bearer token from DefaultAzureCredential
          └── Scope: https://ai.azure.com/.default
```

### Provider Configuration

```python
provider = {
    "type": "openai",                                    # Provider type
    "base_url": f"{FOUNDRY_ENDPOINT}/openai/v1/",       # Must end with /openai/v1/
    "bearer_token": token.token,                         # From DefaultAzureCredential
    "wire_api": "responses",                             # Use Responses wire format
}
```

### Common BYOK Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Wrong scope | 401 Unauthorized | Use `ai.azure.com` not `cognitiveservices.azure.com` |
| Missing `/openai/v1/` | 404 Not Found | `base_url` must end with `/openai/v1/` |
| Token not refreshed | 401 after ~1h | Mint fresh token per session in `_get_provider()` |
| `type: "azure"` | Connection error | Use `type: "openai"` with `wire_api: "responses"` |
| Missing RBAC | 403 Forbidden | Agent identity needs `Azure AI User` on project + `Cognitive Services OpenAI User` on account |

---

## CopilotClient Session Parameters

```python
session = await client.create_session(
    provider=provider,                    # BYOK provider dict
    model="gpt-5.4",                     # Model deployment name
    system_message={                      # MUST be dict, not string
        "mode": "replace",
        "content": "You are a helpful assistant.",
    },
    skill_directories=["/app/skills"],    # Paths to SKILL.md directories
    mcp_servers=[                         # MCP server configs
        {"name": "playwright", "url": "https://my-mcp.azurecontainerapps.io/mcp"},
    ],
    working_directory=str(Path.home()),   # Must be $HOME for hosted agents
    streaming=True,                       # Enable streaming events
    on_permission_request=PermissionHandler.approve_all,  # Auto-approve tools
)
```

### Session Event Types

| Event Type | Meaning | Action |
|------------|---------|--------|
| `SESSION_IDLE` | Response complete | Stop streaming, yield `done` event |
| `SESSION_ERROR` | Agent error | Yield error event, stop |
| `assistant.message` | Final assistant response | Contains full response text |
| `assistant.message_delta` | Streaming content chunk | Accumulate for progressive display |
| `assistant.streaming_delta` | Raw streaming delta | Lower-level than message_delta |
| `assistant.reasoning` | Reasoning trace | Full reasoning block |
| `assistant.reasoning_delta` | Reasoning chunk | Streaming reasoning |
| `tool.execution_start` | Tool call started | Log for debugging |
| `tool.execution_complete` | Tool call finished | Log for debugging |
| `assistant.turn_start` | New turn | Track turn count |
| `assistant.turn_end` | Turn complete | May have more turns |

---

## Invoking the Agent

### Via curl (SSE streaming)

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"

curl -N -X POST "$ENDPOINT/agents/my-agent/endpoint/protocols/invocations?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: HostedAgents=V1Preview" \
  -d '{"input": "Hello"}'
```

### Parsing SSE Responses

Use `references/invoke_agent.py` as a library or standalone script:

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
export AGENT_NAME="my-agent"
python references/invoke_agent.py "What is the capital of France?"
```

The `invoke_invocations()` function parses both `assistant.message` and
`assistant.message_delta` events, preferring the complete message when available.

**Important:** Always parse both event types. Some responses only emit deltas
without a final complete message event.

---

## Evaluation

### Two-Phase Eval (Invocations Protocol)

Foundry eval SDK's `azure_ai_agent` target does not route to hosted agent endpoints.
Use a two-phase workaround:

1. **Invoke**: Call the agent via Invocations endpoint, collect responses
2. **Score**: Submit query+response pairs to Foundry evaluators

### Eval Data Format for Task Adherence

Task Adherence evaluates whether the agent followed its system instructions.
Include the system message in conversation array format:

```python
eval_item = {
    "query": [
        {"role": "system", "content": "Your system prompt here..."},
        {"role": "user", "content": [{"type": "text", "text": "User question"}]},
    ],
    "response": [
        {"role": "assistant", "content": [{"type": "text", "text": "Agent response"}]},
    ],
}
```

### Eval Judge Model Sensitivity

| Judge Model | Task Adherence | Other Evaluators |
|-------------|---------------|------------------|
| `gpt-5.4` | **7%** (overly strict) | Stable |
| `gpt-5.4-mini` | **86%** (accurate) | Stable |

**Always use `gpt-5.4-mini`** as the judge model for Task Adherence.
`gpt-5.4` penalizes responses for claiming tool usage that can't be verified
from response-only data. All other evaluators (Coherence, Intent Resolution,
Task Completion) are stable across both judge models.

### Validated Scores (14-query benchmark)

| Evaluator | Score | Notes |
|-----------|-------|-------|
| **Coherence** | 100% | Identical to MAF |
| **Intent Resolution** | 100% | Identical to MAF |
| **Task Adherence** | 86% | Identical to MAF (gpt-5.4-mini judge) |
| **Task Completion** | 64% | Identical to MAF |
| **Tool Usage (URLs)** | 100% | All responses contain source URLs |

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| **401 on BYOK** | Wrong scope (`cognitiveservices.azure.com`) | Use `https://ai.azure.com/.default` |
| **`send_and_wait()` timeout** | 60s default + 120s gateway limit | Use Invocations protocol instead of ResponsesHostServer |
| **SSE response 0 chars** | Parser only captures `assistant.message` | Also capture `assistant.message_delta` as fallback |
| **Task Adherence eval 0%** | Using `gpt-5.4` as judge model | Use `gpt-5.4-mini` as judge |
| **CopilotClient needs GITHUB_TOKEN** | Not using BYOK provider | Pass `provider` dict to `create_session()` |
| **`system_message` ignored** | Passed as string | Must be dict: `{"mode": "replace", "content": "..."}` |
| **Skills not loading** | Wrong path format | Use absolute paths in `skill_directories` list |
| **Agent crashes on startup** | Missing `azure-ai-agentserver-invocations` | Add to dependencies, use `prerelease = "if-necessary-or-explicit"` |
| **Gateway timeout (502/504)** | Using Responses protocol for long queries | Switch to Invocations protocol |
| **Token expired during long query** | BYOK token static per session | Token has ~1h validity; for longer sessions, create new session |
| **Token expired during eval runs** | Long eval runs (many scenarios) exhaust the BYOK token | Refresh the provider token per invocation: call `_get_provider()` fresh before each `_ensure_session()`, or create a new session every ~30 min |
| **Container can't resolve packages** | pip doesn't handle pre-release deps | Use `uv` with pre-release settings in `[tool.uv]` |
| **Missing `[tool.setuptools] packages = []`** | uv resolution fails without it | Add to pyproject.toml (see `references/pyproject.toml`) |
| **Bicep missing `AZURE_AI_PROJECT_ID`** | Postdeploy hooks need the ARM resource ID | Bicep must output full ARM resource ID, not just endpoint |
| **CognitiveServices API version wrong** | Using old `2024-10-01` | Use `2025-10-01-preview` for agent management APIs |
| **Hooks fail on Windows** | `shell: sh` in azure.yaml | Use `shell: pwsh` for cross-platform |
| **`azd deploy` uses wrong ACR** | `AZURE_CONTAINER_REGISTRY_ENDPOINT` not set or stale from another project | Run `azd env refresh` or verify `AZURE_CONTAINER_REGISTRY_ENDPOINT` in `azd env list`. Must match the ACR created by your project's Bicep. |
| **ACR push 403 / RBAC error** | Deploying user lacks `AcrPush` on the target ACR | Assign `AcrPush` on the ACR, or use `remoteBuild: true` in `azure.yaml` (builds via ACR Tasks with the project's MI) |

---

## azure.yaml (required for `azd deploy`)

The `azd ai agent` extension needs `azure.yaml` to know where to build the container:

```yaml
name: my-project

requiredVersions:
  extensions:
    azure.ai.agents: ">=0.1.25-preview"

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
```

> **`remoteBuild: true` is critical** — without it, azd tries to build locally with Docker.
> With it, azd pushes source to ACR and builds remotely via ACR Tasks.

---

## Architecture Comparison

```
MAF (Responses Protocol):
  container.py → Agent + FoundryChatClient + ResponsesHostServer → port 8088
    └── Request/response: caller waits for full response
    └── Timeout: ~120s (Foundry gateway)

GHCP SDK (Invocations Protocol):
  container.py → CopilotClient + InvocationAgentServerHost → port 8088
    └── SSE streaming: events flow continuously
    └── Timeout: unlimited (connection kept alive by events)
```

### Decision Matrix

| Factor | Choose MAF | Choose GHCP SDK |
|--------|-----------|----------------|
| Tool loop duration | <120s | >120s |
| Custom `@tool` functions | ✅ Required | ❌ Not supported |
| Foundry Toolbox | ✅ `client.get_toolbox()` | ❌ Not available |
| Streaming output | ❌ Response only | ✅ Event stream |
| Progressive skills | Manual injection | ✅ `SkillsProvider` |
| MCP tools | `client.get_mcp_tool()` | `mcp_servers` parameter |
| Auth complexity | Low (DAC → FoundryChatClient) | Medium (BYOK token minting) |
| Packages | Stable releases | Pre-release beta |

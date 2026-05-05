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

```python
"""Foundry Hosted Agent — GHCP SDK + BYOK via Invocations protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from copilot import CopilotClient
from copilot.session import PermissionHandler
from copilot.generated.session_events import SessionEventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(os.getenv("PROJECT_DIR", "/app")).resolve()

# ---------------------------------------------------------------------------
# BYOK Authentication
# ---------------------------------------------------------------------------

_BYOK_CREDENTIAL = None
_BYOK_ENDPOINT = ""


def _init_byok() -> bool:
    """Initialize BYOK with DefaultAzureCredential.

    CRITICAL: Use ai.azure.com scope, NOT cognitiveservices.azure.com.
    """
    global _BYOK_CREDENTIAL, _BYOK_ENDPOINT
    endpoint = (
        os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
        or os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip().rstrip("/")
    )
    if not endpoint:
        return False
    try:
        from azure.identity import DefaultAzureCredential
        _BYOK_CREDENTIAL = DefaultAzureCredential()
        _BYOK_ENDPOINT = endpoint
        token = _BYOK_CREDENTIAL.get_token("https://ai.azure.com/.default")
        logger.info("BYOK verified: %s", endpoint)
        return True
    except Exception as exc:
        logger.error("BYOK init failed: %s", exc)
        return False


def _get_provider() -> dict | None:
    """Mint a fresh BYOK provider dict for CopilotClient session."""
    if not _BYOK_CREDENTIAL or not _BYOK_ENDPOINT:
        return None
    try:
        token = _BYOK_CREDENTIAL.get_token("https://ai.azure.com/.default")
        return {
            "type": "openai",
            "base_url": f"{_BYOK_ENDPOINT}/openai/v1/",
            "bearer_token": token.token,
            "wire_api": "responses",
        }
    except Exception as exc:
        logger.error("BYOK token failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

app = InvocationAgentServerHost()

_client: CopilotClient | None = None
_session = None
_model = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")
_skills_dir = str(BASE_DIR / "skills")


def _load_instructions() -> str:
    ci = BASE_DIR / "copilot-instructions.md"
    return ci.read_text(encoding="utf-8").strip() if ci.exists() else ""


def _load_mcp_servers() -> list[dict] | None:
    """Load MCP servers from environment variables."""
    servers = []
    # Add any MCP servers your agent needs
    mcp_fqdn = os.environ.get("MCP_SERVER_FQDN", "").strip()
    if mcp_fqdn:
        servers.append({"name": "mcp", "url": f"https://{mcp_fqdn}/mcp"})
    return servers or None


async def _ensure_session():
    """Create or resume a CopilotClient session with BYOK."""
    global _client, _session
    if _session is not None:
        return

    session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID", "")

    _client = CopilotClient()
    await _client.start()

    kwargs: dict[str, Any] = {
        "on_permission_request": PermissionHandler.approve_all,
        "streaming": True,
        "model": _model,
        "working_directory": str(pathlib.Path.home()),
    }

    provider = _get_provider()
    if provider:
        kwargs["provider"] = provider

    instructions = _load_instructions()
    if instructions:
        kwargs["system_message"] = {"mode": "replace", "content": instructions}

    if pathlib.Path(_skills_dir).is_dir():
        kwargs["skill_directories"] = [_skills_dir]

    mcp = _load_mcp_servers()
    if mcp:
        kwargs["mcp_servers"] = mcp

    try:
        if session_id:
            _session = await _client.resume_session(
                session_id,
                **{k: v for k, v in kwargs.items() if k != "session_id"},
            )
        else:
            raise Exception("no session_id")
    except Exception:
        _session = await _client.create_session(**kwargs)


# ---------------------------------------------------------------------------
# SSE Streaming Handler
# ---------------------------------------------------------------------------

async def _stream_response(invocation_id: str, input_text: str):
    """Stream CopilotClient events as SSE."""
    await _ensure_session()
    queue: asyncio.Queue = asyncio.Queue()

    def on_event(event):
        if event.type == SessionEventType.SESSION_IDLE:
            queue.put_nowait(None)  # Signal completion
        elif event.type == SessionEventType.SESSION_ERROR:
            queue.put_nowait(RuntimeError(getattr(event.data, "message", "error")))
        else:
            queue.put_nowait(event)

    unsubscribe = _session.on(on_event)
    try:
        await _session.send(input_text)
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'type': 'error', 'message': str(item)})}\n\n".encode()
                break
            yield f"data: {json.dumps(item.to_dict())}\n\n".encode()

        yield f"event: done\ndata: {json.dumps({'invocation_id': invocation_id})}\n\n".encode()
    finally:
        unsubscribe()


@app.invoke_handler
async def handle_invoke(request: Request) -> Response:
    try:
        data = await request.json()
        input_text = data.get("input", "")
        if not input_text:
            return JSONResponse(status_code=400, content={"error": "missing input"})
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    return StreamingResponse(
        _stream_response(request.state.invocation_id, input_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    _init_byok()
    app.run()
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

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/ContainerAgent.yaml

kind: hosted
name: my-agent
description: Agent using GHCP SDK with Invocations protocol
protocols:
  - protocol: invocations    # NOT responses
    version: 1.0.0
environment_variables:
  - name: MODEL_DEPLOYMENT_NAME
    value: gpt-5.4
  # Add MCP server FQDNs if needed
  # - name: MCP_SERVER_FQDN
  #   value: ${MCP_SERVER_FQDN}
resources:
  cpu: "1"
  memory: 2Gi
```

**Critical:** Use `protocol: invocations` (not `responses`). Version must be semver `1.0.0`.

---

## pyproject.toml

```toml
[project]
name = "my-agent"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "github-copilot-sdk>=0.2.0",
    "azure-ai-agentserver-invocations>=1.0.0b3",
    "azure-identity>=1.19.0,<1.26.0a0",
    "python-dotenv>=1.0.0",
]

[tool.uv]
required-environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]
prerelease = "if-necessary-or-explicit"
```

**Notes:**
- `github-copilot-sdk` provides `CopilotClient`, session management, event types
- `azure-ai-agentserver-invocations` provides `InvocationAgentServerHost`
- `azure-identity` pinned to avoid pulling beta versions
- `prerelease = "if-necessary-or-explicit"` needed for beta agentserver package

---

## Dockerfile

```dockerfile
FROM python:3.12-slim

RUN pip install uv
WORKDIR /app
COPY . .

RUN uv pip install --system --compile-bytecode .

EXPOSE 8088
CMD ["python", "container.py"]
```

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

```python
import json
import requests

def invoke_invocations(endpoint, token, agent_name, query, timeout=600):
    """Invoke via Invocations SSE endpoint and extract response text."""
    url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"
    resp = requests.post(
        url,
        json={"input": query},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Foundry-Features": "HostedAgents=V1Preview",
        },
        stream=True,
        timeout=timeout,
    )
    resp.raise_for_status()

    message_text = ""
    delta_text = ""

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
            event_type = event.get("type", "")
            content = event.get("data", {}).get("content", "")

            if event_type == "assistant.message" and content:
                message_text += content
            elif event_type == "assistant.message_delta" and content:
                delta_text += content
        except json.JSONDecodeError:
            continue

    # Prefer complete message; fall back to accumulated deltas
    return message_text if message_text else delta_text
```

**Important:** Always parse both `assistant.message` AND `assistant.message_delta`.
Some responses only emit deltas without a final complete message event.

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
| **Container can't resolve packages** | pip doesn't handle pre-release deps | Use `uv` with pre-release settings in `[tool.uv]` |

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

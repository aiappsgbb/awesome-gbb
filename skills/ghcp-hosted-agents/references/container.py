"""Foundry hosted agent - Microsoft Copilot SDK 2.0 + BYOK via the Invocations protocol.

Canonical reference template for SKILL.md § "Runtime Pattern (Copilot SDK 2.0 + Invocations)".

Shape (verified against microsoft-copilot-sdk 2.0.1):
  * ``CopilotClient(mode="empty")``: no ambient shell/file tools; every session
    opts into its tools explicitly via ``tools.available_tools``.
  * The native runtime runs in this process (SDK 2.0 default). Its home
    (``base_directory``) lives under ``$HOME``, which Foundry persists per hosted
    session, so the session journal survives turns and idle deprovisioning.
  * BYOK Foundry model through a named provider + model definition, with a
    managed-identity bearer-token callback. No ``GITHUB_TOKEN``; CAPI disabled.
  * Each invocation creates (first turn) or resumes (later turns) the SDK session
    keyed by ``FOUNDRY_AGENT_SESSION_ID`` and disconnects it afterwards. Providers,
    tools, hooks and permissions are re-supplied on every create AND resume:
    callbacks and credentials are never persisted in the journal.
  * ``on_pre_tool_use`` hook is the governance gate: it denies ``DENIED_TOOLS``
    before their handler runs.

Copy this file as ``container.py`` in the agent project root. Replace the sample
tools with your own; keep the allow-list and hook in step with them.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import sys
import time

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from azure.identity.aio import DefaultAzureCredential
from copilot import CopilotClient, RuntimeConnection, define_tool
from copilot.session import NamedProviderConfig, PermissionHandler
from copilot.session_events import SessionEventType
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(os.getenv("PROJECT_DIR", "/app")).resolve()
# Foundry persists $HOME (/home/session) per hosted session; keep the runtime home there.
STATE_DIR = pathlib.Path(os.getenv("COPILOT_STATE_DIR", str(pathlib.Path.home() / ".copilot-sdk"))).resolve()
MODEL = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")
PROVIDER = "foundry"
MODEL_ID = f"{PROVIDER}/chat"
TOKEN_SCOPE = "https://ai.azure.com/.default"

# ---------------------------------------------------------------------------
# BYOK: named provider + managed-identity token callback
# ---------------------------------------------------------------------------

_credential: DefaultAzureCredential | None = None


def _account_url() -> str:
    """Foundry account URL derived from the platform-injected project endpoint."""
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
    if not endpoint or not MODEL:
        raise RuntimeError("Set FOUNDRY_PROJECT_ENDPOINT (platform-injected) and AZURE_AI_MODEL_DEPLOYMENT_NAME")
    return endpoint.split("/api/projects/")[0]


async def _get_token(_args) -> str:
    """Called by the runtime before each model request; returns a raw token (no 'Bearer ')."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return (await _credential.get_token(TOKEN_SCOPE)).token


def _inference_options() -> dict:
    return {
        "providers": [
            NamedProviderConfig(
                name=PROVIDER,
                type="openai",
                wire_api="responses",
                base_url=f"{_account_url()}/openai/v1/",
                bearer_token_provider=_get_token,
            )
        ],
        # model_id = behaviour/capability base model; wire_model = deployment name sent to Foundry.
        "models": [{"provider": PROVIDER, "id": "chat", "model_id": MODEL, "wire_model": MODEL}],
    }


# ---------------------------------------------------------------------------
# Host-owned tools (sample) and governance hook
# ---------------------------------------------------------------------------

ORDERS = {"A1234": {"status": "shipped", "tracking_code": "ZX-4471", "total_eur": 129.90}}
DENIED_TOOLS = {"issue_refund"}


class OrderParams(BaseModel):
    order_id: str = Field(description="Order identifier, for example A1234")


@define_tool(description="Look up an order's status, tracking code and total by order id")
async def get_order(params: OrderParams) -> str:
    order = ORDERS.get(params.order_id.strip().upper())
    return json.dumps(order or {"error": f"order {params.order_id} not found"})


@define_tool(description="Issue a full refund for an order")
async def issue_refund(params: OrderParams) -> str:
    logger.warning("issue_refund handler ran for %s - the deny hook should prevent this", params.order_id)
    return json.dumps({"refunded": params.order_id})


async def _on_pre_tool_use(hook_input, _invocation):
    tool = str(hook_input.get("toolName", "")).split(":")[-1]
    if tool in DENIED_TOOLS:
        logger.info("pre-tool-use hook denied %s", tool)
        return {
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{tool} requires human approval and is blocked for this agent",
        }
    return {"permissionDecision": "allow"}


def _load_mcp_servers() -> dict[str, dict]:
    """Optional remote MCP server; its tools still need an ``mcp:`` allow-list entry."""
    fqdn = os.environ.get("MCP_SERVER_FQDN", "").strip()
    return {"remote": {"type": "http", "url": f"https://{fqdn}/mcp", "tools": ["*"]}} if fqdn else {}


def _session_options() -> dict:
    """Options re-supplied on EVERY create and resume (empty mode requires available_tools)."""
    available = ["custom:get_order", "custom:issue_refund"]
    opts: dict = {
        "model": MODEL_ID,
        "working_directory": str(pathlib.Path.home()),
        "github": {"capi": {"enabled": False}},
        "inference": _inference_options(),
        "permissions": {"on_request": PermissionHandler.approve_all},
        "hooks": {"handlers": {"on_pre_tool_use": _on_pre_tool_use}},
        "events": {"streaming": True},
        "tools": {"definitions": [get_order, issue_refund], "available_tools": available},
    }
    instructions = BASE_DIR / "copilot-instructions.md"
    if instructions.exists():
        opts["system_message"] = {"mode": "replace", "content": instructions.read_text(encoding="utf-8").strip()}
    mcp = _load_mcp_servers()
    if mcp:
        opts["mcp"] = {"servers": mcp}
        available.append("mcp:*")
    return opts


# ---------------------------------------------------------------------------
# Client lifecycle and per-invocation session
# ---------------------------------------------------------------------------

app = InvocationAgentServerHost()
_client: CopilotClient | None = None
_client_start_ms: float | None = None
_lock = asyncio.Lock()


async def _ensure_client() -> CopilotClient:
    global _client, _client_start_ms
    if _client is None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        # for_default = in-process unless COPILOT_SDK_DEFAULT_CONNECTION=stdio (crash-isolated subprocess).
        client = CopilotClient(
            mode="empty",
            runtime=RuntimeConnection.for_default(base_directory=str(STATE_DIR)),
            github={"use_logged_in_user": False},
        )
        await client.start()
        _client, _client_start_ms = client, (time.perf_counter() - t0) * 1000
        logger.info("Copilot runtime started in %.0f ms (state=%s)", _client_start_ms, STATE_DIR)
    return _client


async def _open_session(session_id: str):
    client = await _ensure_client()
    opts = _session_options()
    if (STATE_DIR / "session-state" / session_id).is_dir():
        return await client.resume_session(session_id, **opts), "resumed"
    return await client.create_session(session_id=session_id, **opts), "created"


def _sse(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, default=str)}\n\n".encode()


async def _stream_response(invocation_id: str, input_text: str):
    session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID", "") or "local-dev"
    async with _lock:  # one turn at a time per sandbox
        t0 = time.perf_counter()
        session, state = await _open_session(session_id)
        yield _sse({"type": "host.session", "data": {
            "state": state,
            "runtime_start_ms": round(_client_start_ms or 0),
            "session_open_ms": round((time.perf_counter() - t0) * 1000),
        }})
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(event):
            if event.type == SessionEventType.SESSION_IDLE:
                queue.put_nowait(None)
            elif event.type == SessionEventType.SESSION_ERROR:
                queue.put_nowait(RuntimeError(getattr(event.data, "message", "session error")))
            else:
                queue.put_nowait(event)

        unsubscribe = session.on(on_event)
        try:
            await session.send(input_text)
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, Exception):
                    yield _sse({"type": "error", "message": str(item)})
                    break
                yield _sse(item.to_dict())
            yield f"event: done\ndata: {json.dumps({'invocation_id': invocation_id})}\n\n".encode()
        finally:
            unsubscribe()
            # Release in-memory state; the journal under STATE_DIR keeps the conversation.
            await session.disconnect()


@app.invoke_handler
async def handle_invoke(request: Request) -> Response:
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("body is not a JSON object")
        input_text = data.get("input")
        if not isinstance(input_text, str) or not input_text.strip():
            raise ValueError('missing or empty "input" field')
    except (json.JSONDecodeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_request",
                "message": 'Request body must be a JSON object with a non-empty "input" string, '
                           'e.g. {"input": "What can you help me with?"}',
            },
        )
    return StreamingResponse(
        _stream_response(request.state.invocation_id, input_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    try:
        _account_url()
    except RuntimeError as exc:
        sys.exit(f"Error: {exc}")
    logger.info("Copilot SDK 2.0 + Invocations starting (model=%s, state=%s)", MODEL, STATE_DIR)
    app.run()

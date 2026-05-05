"""Foundry Hosted Agent — GHCP SDK + BYOK via Invocations protocol.

Reference template for deploying a hosted agent using the GitHub Copilot SDK
with BYOK authentication and SSE streaming. No GITHUB_TOKEN required.

Usage:
    Copy this file as container.py in your agent project root.
    Adapt _load_mcp_servers() for your MCP server configuration.
"""

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(os.getenv("PROJECT_DIR", "/app")).resolve()

# ---------------------------------------------------------------------------
# BYOK Authentication
# ---------------------------------------------------------------------------
# CRITICAL: Use ai.azure.com scope, NOT cognitiveservices.azure.com.
# Token is static per session — mint fresh via _get_provider() each time.

_BYOK_CREDENTIAL = None
_BYOK_ENDPOINT = ""


def _init_byok() -> bool:
    """Initialize BYOK with DefaultAzureCredential."""
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
        logger.info("BYOK verified: %s (expires in %ds)", endpoint, int(token.expires_on - time.time()))
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
# Instructions & MCP
# ---------------------------------------------------------------------------

def _load_instructions() -> str:
    ci = BASE_DIR / "copilot-instructions.md"
    return ci.read_text(encoding="utf-8").strip() if ci.exists() else ""


def _load_mcp_servers() -> list[dict] | None:
    """Load MCP servers from environment variables.

    Adapt this function for your agent's MCP server configuration.
    Each server needs a name and a URL (https endpoint with /mcp path).
    """
    servers = []
    mcp_fqdn = os.environ.get("MCP_SERVER_FQDN", "").strip()
    if mcp_fqdn:
        servers.append({"name": "mcp", "url": f"https://{mcp_fqdn}/mcp"})
    return servers or None


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

app = InvocationAgentServerHost()

_client: CopilotClient | None = None
_session = None
_model = os.getenv("MODEL_DEPLOYMENT_NAME", "gpt-5.4")
_skills_dir = str(BASE_DIR / "skills")


async def _ensure_session():
    """Create or resume a CopilotClient session with BYOK."""
    global _client, _session
    if _session is not None:
        return

    session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID", "")

    _client = CopilotClient()
    await _client.start()
    logger.info("CopilotClient started (BYOK, no GITHUB_TOKEN)")

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
            logger.info("Resumed session: %s", session_id)
        else:
            raise Exception("no session_id")
    except Exception:
        _session = await _client.create_session(**kwargs)
        logger.info("Created new session")


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


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("GHCP SDK + BYOK (Invocations) starting")
    _init_byok()
    app.run()

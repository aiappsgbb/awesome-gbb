"""Foundry Hosted Agent — GHCP SDK + BYOK via Invocations protocol.

Reference template for deploying a hosted agent using the GitHub Copilot SDK
with BYOK authentication and SSE streaming.

Two auth modes, selected automatically from environment variables:
  * BYOK Foundry model: ``FOUNDRY_PROJECT_ENDPOINT`` (auto-injected by the
    platform) + ``AZURE_AI_MODEL_DEPLOYMENT_NAME`` -> Managed Identity.
    No ``GITHUB_TOKEN`` required.
  * GitHub Copilot model: ``GITHUB_TOKEN`` set -> uses GitHub-hosted models.
    Fallback path; useful for local dev or quickstarts.

Usage:
    Copy this file as ``main.py`` in your agent project root.
    Adapt ``_load_mcp_servers()`` for your MCP server configuration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import sys
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from copilot import CopilotClient
from copilot.session import PermissionHandler, ProviderConfig
from copilot.generated.session_events import SessionEventType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = pathlib.Path(os.getenv("PROJECT_DIR", "/app")).resolve()

# ---------------------------------------------------------------------------
# BYOK Authentication
# ---------------------------------------------------------------------------
# Primary shape (matches the official Microsoft sample, ~2x faster than the
# legacy dict form): ProviderConfig(type="azure", base_url=<bare project
# endpoint>, wire_api="responses").
#
# The SDK appends the ``?api-version=...`` query param itself when
# ``type="azure"`` — do NOT add ``/openai/v1/`` to the URL.
#
# Token scope is ``https://ai.azure.com/.default`` (NOT
# ``cognitiveservices.azure.com`` — renamed in the May 2026 Foundry
# data-plane rename).

_BYOK_CREDENTIAL = None
_BYOK_ENDPOINT = ""
_MODEL = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "") or os.getenv("MODEL_DEPLOYMENT_NAME", "")


def _init_byok() -> bool:
    """Initialise the BYOK credential. Returns False if BYOK is not configured."""
    global _BYOK_CREDENTIAL, _BYOK_ENDPOINT
    endpoint = (
        os.getenv("FOUNDRY_PROJECT_ENDPOINT", "").strip().rstrip("/")
        or os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip().rstrip("/")
    )
    if not endpoint or not _MODEL:
        return False
    try:
        from azure.identity import DefaultAzureCredential
        _BYOK_CREDENTIAL = DefaultAzureCredential()
        _BYOK_ENDPOINT = endpoint
        token = _BYOK_CREDENTIAL.get_token("https://ai.azure.com/.default")
        logger.info("BYOK verified: %s (model=%s, token expires in %ds)",
                    endpoint, _MODEL, int(token.expires_on - time.time()))
        return True
    except Exception as exc:
        logger.error("BYOK init failed: %s", exc)
        return False


def _get_provider() -> ProviderConfig | None:
    """Mint a fresh BYOK ProviderConfig for CopilotClient session.

    Returns ``None`` when BYOK is not configured — caller falls back to the
    GITHUB_TOKEN path.
    """
    if not _BYOK_CREDENTIAL or not _BYOK_ENDPOINT:
        return None
    try:
        token = _BYOK_CREDENTIAL.get_token("https://ai.azure.com/.default").token
        return ProviderConfig(
            type="azure",
            base_url=_BYOK_ENDPOINT,
            wire_api="responses",
            bearer_token=token,
        )
    except Exception as exc:
        logger.error("BYOK token mint failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Instructions & MCP
# ---------------------------------------------------------------------------

def _load_instructions() -> str:
    ci = BASE_DIR / "copilot-instructions.md"
    return ci.read_text(encoding="utf-8").strip() if ci.exists() else ""


def _load_mcp_servers() -> list[dict] | None:
    """Load MCP servers from environment variables.

    Adapt this function for your agent's MCP server configuration. Both
    ``list[dict]`` (used here) and ``dict[str, dict]`` are accepted by the
    SDK; ``list[dict]`` reads slightly more naturally.

    Each entry needs a ``name`` and either ``url`` (HTTP MCP) or ``command``
    (stdio MCP). Pass an HTTPS URL ending in ``/mcp`` for HTTP servers.
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
_skills_dir = str(BASE_DIR / "skills")


async def _ensure_session() -> None:
    """Create or resume a CopilotClient session. Lazy — runs once per worker."""
    global _client, _session
    if _session is not None:
        return

    session_id = os.environ.get("FOUNDRY_AGENT_SESSION_ID", "")

    provider = _get_provider()
    github_token = os.environ.get("GITHUB_TOKEN", "")

    if provider:
        # BYOK mode: Foundry model via Managed Identity, no token needed.
        _client = CopilotClient()
    elif github_token:
        # Copilot mode: GitHub-hosted models via personal/app token.
        _client = CopilotClient(github_token=github_token)
    else:
        raise RuntimeError(
            "No auth configured. Set FOUNDRY_PROJECT_ENDPOINT + "
            "AZURE_AI_MODEL_DEPLOYMENT_NAME (BYOK Foundry) or GITHUB_TOKEN (GHCP)."
        )

    await _client.start()
    logger.info("CopilotClient started (mode=%s)", "BYOK" if provider else "GITHUB_TOKEN")

    kwargs: dict[str, Any] = {
        "on_permission_request": PermissionHandler.approve_all,
        "streaming": True,
        "working_directory": str(pathlib.Path.home()),
        "provider": provider,
        "model": _MODEL or None,
    }

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
            _session = await _client.resume_session(session_id, **kwargs)
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
            queue.put_nowait(None)
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
                "message": (
                    'Request body must be a JSON object with a non-empty "input" string, '
                    'e.g. {"input": "What can you help me with?"}'
                ),
            },
        )
    return StreamingResponse(
        _stream_response(request.state.invocation_id, input_text),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    has_token = bool(os.environ.get("GITHUB_TOKEN"))
    has_byok = _init_byok()
    if not has_token and not has_byok:
        sys.exit(
            "Error: Set GITHUB_TOKEN (Copilot model) or "
            "FOUNDRY_PROJECT_ENDPOINT + AZURE_AI_MODEL_DEPLOYMENT_NAME "
            "(BYOK Foundry model)"
        )
    logger.info("GHCP SDK + Invocations starting (BYOK=%s, GITHUB_TOKEN=%s)", has_byok, has_token)
    app.run()

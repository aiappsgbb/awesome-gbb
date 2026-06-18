"""Canonical Web IQ MCP grounding wiring for a Foundry hosted agent.

Source of truth for the prose example in `../../SKILL.md § Native MCP path`.

This module is the single source of truth for connecting Microsoft Web IQ's
native MCP endpoint to a Foundry hosted agent built on the Microsoft Agent
Framework (MAF). It provides two `MCPStreamableHTTPTool` builders — one for
API-key (static header) auth, one for Microsoft Entra (bearer) auth — plus a
citation-extracting result parser.

NOTHING here is invented from the Web IQ API surface. The endpoint URL, the
API-key header NAME, the Entra scope, and the response field names are all
read from environment variables / marked with `# CONFIRM:` so the consumer
supplies the real values from their gated Web IQ docs. MCP tool/method names
are discovered at runtime via the JSON-RPC `tools/list` handshake — they are
never hardcoded.

Required env vars (set from YOUR Web IQ docs / Playground):
    WEBIQ_MCP_ENDPOINT     - streamable-HTTP MCP URL
    WEBIQ_API_KEY          - the key / subscription secret           (api-key auth)
    WEBIQ_API_KEY_HEADER   - the header NAME the key rides in        (api-key auth)
    WEBIQ_ENTRA_SCOPE      - OAuth2 scope/resource, e.g. api://<app-id>/.default
                                                                      (entra auth)

Dependencies (already present in a hosted-agent container):
    agent-framework, httpx, azure-identity
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import httpx

# MAF imports. These resolve inside a hosted-agent container; this file is
# syntax-validated by CI, not executed there.
from agent_framework import MCPStreamableHTTPTool


# --------------------------------------------------------------------------- #
# Citation extraction
# --------------------------------------------------------------------------- #
# Web IQ returns provenance per passage. The MCP envelope shape
# (CallToolResult.content[].text) is standard MCP; the JSON *inside* each text
# block is Web IQ specific. We unwrap the envelope (known), then defensively
# map the inner fields (CONFIRM against your Web IQ response schema).

# CONFIRM: replace these with the exact JSON keys from your Web IQ response
# schema. They are intentionally conservative guesses, flagged so nothing
# ships as an authoritative invented field name.
_CITATION_KEYS = {
    "title": ("title",),        # CONFIRM: source title key
    "url": ("url",),            # CONFIRM: source URL key
    "snippet": ("snippet",),    # CONFIRM: passage/snippet key
    "timestamp": ("timestamp",),  # CONFIRM: freshness/published key
    "provenance": ("provenance",),  # CONFIRM: provenance/source key
}


def _first_present(obj: dict[str, Any], candidates: Iterable[str]) -> Any:
    for key in candidates:
        if key in obj:
            return obj[key]
    return None


def _normalize_citation(record: dict[str, Any]) -> dict[str, Any]:
    """Map one Web IQ result record into a normalized citation dict."""
    return {
        field: _first_present(record, keys)
        for field, keys in _CITATION_KEYS.items()
    }


def _iter_result_records(payload: Any) -> list[dict[str, Any]]:
    """Pull a list of result records out of a parsed Web IQ JSON payload.

    Web IQ may return either a bare list or an object wrapping a results
    array. CONFIRM the wrapper key against your schema.
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("results", "value", "items", "data"):  # CONFIRM wrapper key
            inner = payload.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
    return []


def _webiq_result_parser(result: Any) -> str:
    """`parse_tool_results` callback for the Web IQ MCP tool.

    Unwraps the standard MCP `CallToolResult.content[].text` envelope so the
    model never sees a `[<Content object>]` repr, then attaches a compact,
    normalized citation list parsed from the inner Web IQ JSON.

    Returns a plain string (text + a `Sources:` block) suitable for direct
    injection into the model context.
    """
    texts: list[str] = []
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")

    for block in content or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            texts.append(text)

    joined = "\n".join(texts).strip()

    citations: list[dict[str, Any]] = []
    for chunk in texts:
        try:
            parsed = json.loads(chunk)
        except (ValueError, TypeError):
            continue
        citations.extend(_normalize_citation(r) for r in _iter_result_records(parsed))

    if not citations:
        return joined or "[Web IQ returned no grounding results]"

    sources = "\n".join(
        f"- {c.get('title') or '(untitled)'} — {c.get('url') or '(no url)'}"
        f" [{c.get('timestamp') or 'n/a'}]"
        for c in citations
    )
    return f"{joined}\n\nSources:\n{sources}" if joined else f"Sources:\n{sources}"


# --------------------------------------------------------------------------- #
# Tool builders
# --------------------------------------------------------------------------- #
def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Populate it from your Web IQ docs / Playground "
            f"(see SKILL.md § 'What you must capture from your Web IQ docs')."
        )
    return value


def build_webiq_mcp_tool_apikey(*, request_timeout: float = 60.0) -> MCPStreamableHTTPTool:
    """Web IQ MCP tool authenticated by a static API-key header.

    The key must ride on EVERY request — including the JSON-RPC `initialize` /
    `tools/list` bootstrap — so it is set as a default header on an
    `httpx.AsyncClient` passed via `http_client=`. Current MAF
    `MCPStreamableHTTPTool` has **no** `headers=` parameter (it is accepted
    for backward compatibility but silently ignored), and a per-call
    `header_provider=` only covers `tools/call` — it misses the bootstrap and
    401s on a server that gates discovery. The static-header client mirrors
    the Entra path in `build_webiq_mcp_tool_entra`.
    """
    endpoint = _require_env("WEBIQ_MCP_ENDPOINT")
    api_key = _require_env("WEBIQ_API_KEY")
    # CONFIRM: WEBIQ_API_KEY_HEADER is the exact header NAME from the Web IQ
    # auth docs (e.g. a subscription-key or x-api-key style header).
    header_name = _require_env("WEBIQ_API_KEY_HEADER")

    http_client = httpx.AsyncClient(headers={header_name: api_key}, timeout=request_timeout)

    return MCPStreamableHTTPTool(
        name="webiq_grounding",
        url=endpoint,
        http_client=http_client,
        approval_mode="never_require",
        parse_tool_results=_webiq_result_parser,
        request_timeout=request_timeout,
    )


class _EntraBearerAuth(httpx.Auth):
    """httpx auth flow that stamps `Authorization: Bearer <token>` on EVERY
    request, including the MCP bootstrap handshake.

    Tokens are fetched from azure-identity for the Web IQ scope and cached
    until ~5 min before expiry.
    """

    def __init__(self, scope: str) -> None:
        # Imported lazily so api-key-only consumers need not install identity.
        from azure.identity import DefaultAzureCredential

        self._scope = scope
        self._credential = DefaultAzureCredential()
        self._token: str | None = None
        self._expires_on: int = 0

    def _bearer(self) -> str:
        import time

        if self._token is None or time.time() > (self._expires_on - 300):
            token = self._credential.get_token(self._scope)
            self._token = token.token
            self._expires_on = token.expires_on
        return self._token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._bearer()}"
        yield request


def build_webiq_mcp_tool_entra(*, request_timeout: float = 60.0) -> MCPStreamableHTTPTool:
    """Web IQ MCP tool authenticated by a Microsoft Entra bearer token.

    Uses an `httpx.AsyncClient(auth=...)` passed via `http_client=` so the
    bearer covers the `initialize` / `tools/list` bootstrap as well as
    `tools/call`. Do NOT also pass `header_provider=` — a per-call provider
    misses the handshake and 401s on AAD-gated bootstrap (see SKILL.md
    § 'Microsoft Entra auth — bearer token').
    """
    endpoint = _require_env("WEBIQ_MCP_ENDPOINT")
    scope = _require_env("WEBIQ_ENTRA_SCOPE")

    http_client = httpx.AsyncClient(auth=_EntraBearerAuth(scope), timeout=request_timeout)

    return MCPStreamableHTTPTool(
        name="webiq_grounding",
        url=endpoint,
        http_client=http_client,
        approval_mode="never_require",
        parse_tool_results=_webiq_result_parser,
        request_timeout=request_timeout,
    )

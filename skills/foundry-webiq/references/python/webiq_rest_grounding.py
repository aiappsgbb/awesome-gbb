"""Canonical Web IQ REST grounding tool for a Foundry hosted agent.

Source of truth for the prose example in `../../SKILL.md § REST fallback path`.

A minimal, env-driven REST grounding call wrapped as an in-process agent
tool, for teams who prefer REST over Web IQ's native MCP endpoint. Unlike the
MCP path, REST gives you no runtime tool auto-discovery — YOU own the request
and response shape, so the route, query params, and response keys must be
confirmed from your gated Web IQ REST docs. Every assumed shape is flagged
`# CONFIRM:` so nothing ships as an invented contract.

Required env vars (set from YOUR Web IQ docs / Playground):
    WEBIQ_REST_ENDPOINT    - REST base URL
    WEBIQ_API_KEY          - the key / subscription secret
    WEBIQ_API_KEY_HEADER   - the header NAME the key rides in

Dependencies (already present in a hosted-agent container):
    agent-framework, httpx
"""

from __future__ import annotations

import os
from typing import Any

import httpx

# MAF decorator that exposes a plain callable to the model as a tool. This
# resolves inside a hosted-agent container; CI only syntax-checks this file.
from agent_framework import ai_function


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Populate it from your Web IQ docs / Playground "
            f"(see SKILL.md § 'What you must capture from your Web IQ docs')."
        )
    return value


def _normalize_results(payload: Any) -> list[dict[str, Any]]:
    """Pull normalized citations out of a Web IQ REST JSON payload.

    CONFIRM the wrapper key and the per-record field keys against your Web IQ
    REST response schema.
    """
    records: list[dict[str, Any]] = []
    if isinstance(payload, list):
        records = [r for r in payload if isinstance(r, dict)]
    elif isinstance(payload, dict):
        for key in ("results", "value", "items", "data"):  # CONFIRM wrapper key
            inner = payload.get(key)
            if isinstance(inner, list):
                records = [r for r in inner if isinstance(r, dict)]
                break

    citations: list[dict[str, Any]] = []
    for r in records:
        citations.append(
            {
                "title": r.get("title"),          # CONFIRM: source title key
                "url": r.get("url"),              # CONFIRM: source URL key
                "snippet": r.get("snippet"),      # CONFIRM: passage/snippet key
                "timestamp": r.get("timestamp"),  # CONFIRM: freshness key
                "provenance": r.get("provenance"),  # CONFIRM: provenance key
            }
        )
    return citations


@ai_function(
    name="webiq_web_search",
    description=(
        "Ground the answer on fresh, cited open-web context via Microsoft "
        "Web IQ. Returns ranked passages with title, URL, snippet, and "
        "timestamp."
    ),
)
async def webiq_web_search(
    query: str,
    *,
    count: int = 5,
    freshness: str | None = None,
) -> list[dict[str, Any]]:
    """Call the Web IQ REST endpoint and return normalized citations.

    Args:
        query: the natural-language grounding query.
        count: number of passages to request.
        freshness: optional freshness window (CONFIRM accepted values).
    """
    endpoint = _require_env("WEBIQ_REST_ENDPOINT")
    api_key = _require_env("WEBIQ_API_KEY")
    header_name = _require_env("WEBIQ_API_KEY_HEADER")

    # CONFIRM: request shape (verb, path, param names, body vs query string)
    # against your Web IQ REST reference. The shape below is a conservative
    # placeholder — adjust to the documented contract.
    params: dict[str, Any] = {"q": query, "count": count}
    if freshness:
        params["freshness"] = freshness

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            endpoint,
            params=params,
            headers={header_name: api_key},
        )
        response.raise_for_status()
        return _normalize_results(response.json())

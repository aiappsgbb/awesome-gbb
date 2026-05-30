"""Canonical MCP text-content extractor for MCPStreamableHTTPTool.

Source of truth for the prose example in `../../SKILL.md § Canonical MCP
result parser (recommended for non-toolbox MCPs too)`.

Why this file exists (TB2 from PR #180):
    When you wire a remote MCP via MCPStreamableHTTPTool (toolbox endpoint
    OR a public MCP like Microsoft Learn / GitHub MCP), the raw tools/call
    response contains an array of `content` items with the shape:
        {"type": "text", "text": "..."}
    MAF 1.6 does NOT unwrap this for you. Without a `parse_tool_results=`
    extractor, the model sees the wire-level JSON envelope instead of just
    the text — leading to "the agent found the docs but didn't cite them"
    type bugs (verified on 2026-05-28 learn-assistant run).

Usage:
    from agent_framework import MCPStreamableHTTPTool
    from references.python.mcp_text_extractor import extract_mcp_text

    learn_mcp = MCPStreamableHTTPTool(
        name="microsoft-learn",
        url="https://learn.microsoft.com/api/mcp",
        parse_tool_results=extract_mcp_text,  # ← MUST include this
    )

The function handles both the canonical envelope shape and string
fallbacks so a malformed MCP response won't crash the agent.
"""

from __future__ import annotations

from typing import Any


def extract_mcp_text(raw: Any) -> str:
    """Pull plain text from MCP tool-call envelopes.

    Handles both `{"content": [{"type": "text", "text": "..."}, ...]}`
    and fallback string responses. Use on any MCPStreamableHTTPTool to
    surface grounding cleanly to the model.

    Args:
        raw: The raw MCP tool-call response (typically a dict, but can
            be a string if the MCP misbehaves).

    Returns:
        A single string with all text-typed content items joined by
        double newlines, or `str(raw)` as the safe fallback.
    """
    if isinstance(raw, dict) and "content" in raw:
        parts: list[str] = []
        for item in raw["content"]:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n\n".join(parts) if parts else str(raw)
    return str(raw)


# Aliases for backward-compat with existing prose that uses the
# underscored leading name (some pilots imported `_mcp_text_extractor`).
_mcp_text_extractor = extract_mcp_text

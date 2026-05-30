"""Canonical FastMCP server for ACA — streamable-HTTP transport.

Source of truth for the prose example in `../../SKILL.md § Example:
Custom Python MCP Server`.

CRITICAL — three lines this template prevents from going wrong:

    1. `transport="streamable-http"` (M3): the legacy `transport="http"`
       bare form is stale. FastMCP > 2.0 expects the dashed name.
    2. `host="0.0.0.0"` (M2): bare `MCP.run()` defaults to stdio
       transport which reads stdin instead of binding a port. ACA
       marks the container unhealthy. Always bind 0.0.0.0 for cloud.
    3. `port=int(os.environ.get("PORT", "8080"))` (M2 again): ACA
       sets PORT via env var. Hardcoding 8080 works in dev but breaks
       the moment ACA decides to put your container behind a different
       port.

Plus: NEVER call one `@mcp.tool()`-decorated function from inside another
— `@mcp.tool()` wraps the function in a FunctionTool object that isn't
callable from Python. Extract shared logic into a plain `_helper()` and
call THAT from both tool functions.

Producer scope: use this template when YOU are deploying an MCP server to
ACA. If you're CONSUMING a remote MCP from a Foundry hosted agent, see
`foundry-hosted-agents` SKILL § MCP Tools instead.
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

mcp = FastMCP("my-tools")


def _search_backend(query: str) -> list[dict]:
    """Plain helper — both tools that need this call it.
    NEVER decorate this with @mcp.tool; that breaks Python-side calls."""
    # Call your backend API here.
    return [{"order_id": "ORD-001", "status": "shipped"}]


@mcp.tool()
async def search_orders(query: str) -> list[dict]:
    """Search orders by keyword."""
    return _search_backend(query)


@mcp.tool()
async def search_orders_filtered(query: str, status: str) -> list[dict]:
    """Search orders, filtered by status — calls the same helper."""
    all_results = _search_backend(query)
    return [r for r in all_results if r["status"] == status]


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",   # M3: not bare "http"
        host="0.0.0.0",                # M2: not the stdio default
        port=int(os.environ.get("PORT", "8080")),
    )

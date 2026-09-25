"""Canonical management-only Toolbox service models.

Source of truth for `../../SKILL.md § A2A 1.0 management without a runtime upgrade`
and `../../SKILL.md § Tool Search`. Requires the isolated management requirements,
not a change to the hosted MAF stack. No authentication or network calls.
"""

from azure.ai.projects.models import (
    A2AProtocolVersion,
    A2AToolboxTool,
    MCPToolboxTool,
    ToolConfig,
    ToolSearchToolboxTool,
)


def a2a_peer(connection_id: str) -> A2AToolboxTool:
    if not connection_id or not connection_id.strip():
        raise ValueError("An approved RemoteA2A project connection is required")
    return A2AToolboxTool(
        name="peer-agent",
        project_connection_id=connection_id,
        a2a_version=A2AProtocolVersion.V1_0,
    )


def searchable_mcp(
    server_label: str,
    server_url: str,
    connection_id: str | None,
    tool_configs: dict[str, ToolConfig],
) -> list[MCPToolboxTool | ToolSearchToolboxTool]:
    if not all(value and value.strip() for value in (server_label, server_url)):
        raise ValueError("An approved MCP label and URL are required")
    if connection_id is not None and not connection_id.strip():
        raise ValueError("A project connection must be nonempty, or None for an approved no-auth server")
    return [
        MCPToolboxTool(
            server_label=server_label,
            server_url=server_url,
            project_connection_id=connection_id,
            require_approval="always",
            tool_configs=tool_configs,
        ),
        ToolSearchToolboxTool(),
    ]

"""Canonical connection-backed Prompt and Toolbox definitions.

Source of truth for `../../SKILL.md § Agent integration`.
Importing and build_definitions are local. create_bindings is an explicitly
opt-in cloud write and must not run before Gate B.
"""

from urllib.parse import urlsplit

from azure.ai.projects.models import MCPTool, MCPToolboxTool, PromptAgentDefinition


INSTRUCTIONS = (
    "Use who_am_i and list_my_demo_items to answer questions about the caller's "
    "synthetic demo data. Never infer an identity from a prompt or invent a receipt. "
    "If authorization is required or denied, report that; do not claim tool success."
)


def build_definitions(
    model: str, mcp_url: str, connection_id: str,
) -> tuple[PromptAgentDefinition, MCPToolboxTool]:
    url = urlsplit(mcp_url)
    if (
        not model.strip() or not connection_id.strip()
        or url.scheme != "https" or not url.hostname
        or url.username or url.password or url.query or url.fragment
        or url.path != "/mcp"
    ):
        raise ValueError("Model, connection ID, and an HTTPS /mcp endpoint are required")
    fields = {
        "server_label": "delegated-demo",
        "server_url": mcp_url,
        "project_connection_id": connection_id,
        "require_approval": "never",
        "allowed_tools": ["who_am_i", "list_my_demo_items"],
    }
    return (
        PromptAgentDefinition(model=model, instructions=INSTRUCTIONS, tools=[MCPTool(**fields)]),
        MCPToolboxTool(**fields),
    )

def build_prompt_toolbox_definition(model: str, toolbox_url: str, bridge_connection_id: str) -> PromptAgentDefinition:
    """The outer first-party user-token bridge is separate from inner custom OAuth."""
    url = urlsplit(toolbox_url)
    if (
        not model.strip() or not bridge_connection_id.strip()
        or url.scheme != "https" or not url.hostname
        or not url.hostname.endswith(".services.ai.azure.com")
        or "/toolboxes/" not in url.path or not url.path.endswith("/mcp")
        or url.username or url.password or url.fragment or url.query != "api-version=v1"
    ):
        raise ValueError("A first-party Toolbox endpoint and its native bridge connection are required")
    return PromptAgentDefinition(
        model=model, instructions=INSTRUCTIONS,
        tools=[MCPTool(server_label="delegated-toolbox", server_url=toolbox_url,
                       project_connection_id=bridge_connection_id, require_approval="never")],
    )


def create_bindings(
    project, model: str, mcp_url: str, connection_name: str, name: str, *, approved: bool = False,
):
    """GATE B WRITE: only call after explicit approval and isolated Azure preflight."""
    if approved is not True:
        raise PermissionError("Gate B approval and isolated preflight are required before cloud writes")
    if not name.strip() or not connection_name.strip():
        raise ValueError("Explicit agent and connection names are required")
    connection = project.connections.get(connection_name, include_credentials=False)
    if connection.target.rstrip("/") != mcp_url.rstrip("/"):
        raise ValueError("Connection target differs from the requested MCP endpoint")
    prompt, toolbox_tool = build_definitions(model, mcp_url, connection.id)
    toolbox = project.toolboxes.create_version(
        name=f"{name}-tools", tools=[toolbox_tool],
        description="Read-only custom MCP with per-user OAuth",
    )
    # A subsequent failure is not rolled back silently: preserve the created version
    # for explicit inspection/cleanup under the approved resource allow-list.
    agent = project.agents.create_version(agent_name=name, definition=prompt)
    return agent, toolbox

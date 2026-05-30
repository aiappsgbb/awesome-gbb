"""Canonical toolbox wiring sample — MAF 1.6 + Foundry Toolbox.

Source of truth for the prose example in `../../SKILL.md § Step 2 —
Wire the toolbox into the agent`.

Validates the cross-skill ownership rule: this file shows the toolbox-
to-Agent wiring, which is owned by `foundry-toolbox` SKILL. The Agent
runtime construction itself (Agent + FoundryChatClient + ResponsesHostServer)
is owned by `foundry-hosted-agents` SKILL — see
`../../foundry-hosted-agents/references/python/main.py` for that side.

Demonstrates 3 patterns:
    1. AzureAIToolbox — reads a Foundry toolbox version, returns
       MCPStreamableHTTPTool instances ready to plug into Agent(tools=[...]).
    2. Direct MCPStreamableHTTPTool — for non-toolbox MCPs (Microsoft Learn,
       GitHub MCP, etc.). Always pass `parse_tool_results=extract_mcp_text`.
    3. Composing both — toolbox tools + a couple of direct MCP tools
       alongside local @tool-decorated functions.

Verified against MAF 1.6.0 + azure-ai-projects 2.1.0 on May 2026 pilots.
"""

from __future__ import annotations

import os

from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import AzureAIToolbox, FoundryChatClient
from azure.identity import DefaultAzureCredential

from references.python.mcp_text_extractor import extract_mcp_text


def _build_toolbox_tools() -> list:
    """Pattern 1 — pull tools from a Foundry toolbox version.

    The toolbox is created server-side via `client.beta.toolboxes.create_version(...)`
    (see SKILL.md § Step 1). AzureAIToolbox.from_paths_or_names fetches the
    latest version's tools and returns them ready to wire.
    """
    toolbox = AzureAIToolbox(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        toolbox_name="agent-tools",
        credential=DefaultAzureCredential(),
    )
    return toolbox.get_tools()


def _build_learn_mcp() -> MCPStreamableHTTPTool:
    """Pattern 2 — wire a public MCP directly (no toolbox needed)."""
    return MCPStreamableHTTPTool(
        name="microsoft-learn",
        url="https://learn.microsoft.com/api/mcp",
        parse_tool_results=extract_mcp_text,  # MUST include — see TB2
    )


@tool(approval_mode="never_require")
def echo(message: str) -> str:
    """Local function tool — for demo purposes only."""
    return f"echo: {message}"


def main() -> None:
    """Pattern 3 — compose toolbox tools + direct MCP + local function."""
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    tools = []
    tools.extend(_build_toolbox_tools())
    tools.append(_build_learn_mcp())
    tools.append(echo)

    agent = Agent(
        client=client,
        instructions="You are a helpful assistant. Use the tools to ground your answers.",
        tools=tools,
        default_options={"store": False},
    )

    # Hand off to ResponsesHostServer in container.py — see foundry-hosted-agents.
    return agent


if __name__ == "__main__":
    main()

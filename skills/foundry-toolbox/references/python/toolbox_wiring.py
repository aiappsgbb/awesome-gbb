"""Canonical toolbox wiring sample - MAF 1.11 + Foundry Toolbox GA.

Source of truth for the prose example in `../../SKILL.md § Step 2 —
Wire into a hosted agent`.

Validates the cross-skill ownership rule: this file shows Toolbox-to-Agent
wiring, which is owned by the `foundry-toolbox` skill. The hosted runtime
construction is owned by `foundry-hosted-agents`.

Demonstrates three patterns:
    1. FoundryToolbox - resolves the Toolbox MCP endpoint, authenticates each
       request, and forwards the hosted request call ID.
    2. Direct MCPStreamableHTTPTool - for non-Toolbox MCP servers such as
       Microsoft Learn. Always pass parse_tool_results=extract_mcp_text.
    3. Composition - Toolbox, direct MCP, and local function tools on one Agent.

Validated against agent-framework 1.11.0, agent-framework-foundry-hosting
1.0.0a260709, and azure-ai-projects 2.3.0 in July 2026.
"""

from __future__ import annotations

import os

from agent_framework import Agent, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox
from azure.identity import DefaultAzureCredential

from references.python.mcp_text_extractor import extract_mcp_text


def _build_foundry_toolbox(
    credential: DefaultAzureCredential,
) -> FoundryToolbox:
    """Build the GA Toolbox consumer from the hosting environment contract."""
    return FoundryToolbox(credential)


def _build_learn_mcp() -> MCPStreamableHTTPTool:
    """Wire a public non-Toolbox MCP server directly."""
    return MCPStreamableHTTPTool(
        name="microsoft-learn",
        url="https://learn.microsoft.com/api/mcp",
        parse_tool_results=extract_mcp_text,
    )


@tool(approval_mode="never_require")
def echo(message: str) -> str:
    """Return the supplied message for a local-tool composition example."""
    return f"echo: {message}"


def main() -> Agent:
    """Compose a Foundry Toolbox, direct MCP, and local function."""
    credential = DefaultAzureCredential()
    toolbox = _build_foundry_toolbox(credential)
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential,
    )

    return Agent(
        client=client,
        instructions=(
            "You are a helpful assistant. Use the available tools to ground "
            "your answers."
        ),
        tools=[toolbox, _build_learn_mcp(), echo],
        default_options={"store": False},
    )


if __name__ == "__main__":
    main()

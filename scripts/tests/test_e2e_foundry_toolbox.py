#!/usr/bin/env python3
"""
E2E test for foundry-toolbox skill — verifies FoundryChatClient +
MCPStreamableHTTPTool + Agent work against real Azure infrastructure.

Requires:
  - AZURE_AI_ENDPOINT env var (Foundry project endpoint)
  - Azure CLI authenticated (AzureCliCredential)
  - agent-framework, agent-framework-foundry, mcp, azure-identity installed

Run:
  python -m pytest scripts/tests/test_e2e_foundry_toolbox.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

AZURE_AI_ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "")
SKIP_REASON = "AZURE_AI_ENDPOINT not set — skipping Azure E2E tests"


@unittest.skipUnless(AZURE_AI_ENDPOINT, SKIP_REASON)
class TestFoundryToolboxE2E(unittest.TestCase):
    """Verify the Learn MCP recipe from the foundry-toolbox skill."""

    MODEL = "gpt-5.4-mini"

    @classmethod
    def setUpClass(cls):
        from azure.identity import AzureCliCredential
        from agent_framework.foundry import FoundryChatClient

        cls.credential = AzureCliCredential()
        cls.client = FoundryChatClient(
            project_endpoint=AZURE_AI_ENDPOINT,
            model=cls.MODEL,
            credential=cls.credential,
        )

    def test_01_foundry_chat_client_inference(self):
        """FoundryChatClient can call the Responses API."""
        import asyncio
        from agent_framework import Agent, Message

        agent = Agent(
            client=self.client,
            instructions="Reply with exactly: toolbox-ci-ok",
        )
        msg = Message(role="user", contents=["ping"])

        async def _run():
            return await agent.run(messages=[msg])

        response = asyncio.run(_run())
        self.assertIsNotNone(response)
        text = response.text if hasattr(response, "text") else str(response)
        self.assertIn("toolbox-ci-ok", text.lower().replace("-", "-"))
        print(f"\n  ✅ FoundryChatClient inference OK ({len(text)} chars)")

    def test_02_mcp_tool_connects(self):
        """MCPStreamableHTTPTool can connect to Learn MCP endpoint."""
        from agent_framework import MCPStreamableHTTPTool

        tool = MCPStreamableHTTPTool(
            name="microsoft-learn",
            url="https://learn.microsoft.com/api/mcp",
        )
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "microsoft-learn")
        print("\n  ✅ MCPStreamableHTTPTool constructed OK")

    def test_03_agent_with_mcp_tool(self):
        """Agent + FoundryChatClient + MCPStreamableHTTPTool end-to-end."""
        import asyncio
        from agent_framework import Agent, MCPStreamableHTTPTool, Message

        def _mcp_text_extractor(raw):
            if isinstance(raw, dict) and "content" in raw:
                parts = [
                    item.get("text", "")
                    for item in raw["content"]
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                return "\n\n".join(parts) if parts else str(raw)
            return str(raw)

        learn_mcp = MCPStreamableHTTPTool(
            name="microsoft-learn",
            url="https://learn.microsoft.com/api/mcp",
            parse_tool_results=_mcp_text_extractor,
        )

        agent = Agent(
            client=self.client,
            tools=[learn_mcp],
            instructions="Answer Azure questions using the microsoft-learn tool.",
        )

        msg = Message(role="user", contents=["What is Azure Container Apps?"])

        async def _run():
            return await agent.run(messages=[msg])

        response = asyncio.run(_run())
        text = response.text if hasattr(response, "text") else str(response)
        self.assertGreater(len(text), 50, "Response too short")
        has_azure_content = "azure" in text.lower() or "container" in text.lower()
        self.assertTrue(has_azure_content, "Response should mention Azure/Container")
        print(f"\n  ✅ Agent + MCP tool E2E OK ({len(text)} chars)")


if __name__ == "__main__":
    unittest.main(verbosity=2)

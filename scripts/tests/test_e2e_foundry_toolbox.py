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
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLBOX_REFS = REPO_ROOT / "skills" / "foundry-toolbox" / "references" / "python"
if str(TOOLBOX_REFS) not in sys.path:
    sys.path.insert(0, str(TOOLBOX_REFS))

from mcp_text_extractor import extract_mcp_text as _mcp_text_extractor  # noqa: E402

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
        """Agent + FoundryChatClient + MCPStreamableHTTPTool end-to-end.

        Imports the canonical `_mcp_text_extractor` from
        `skills/foundry-toolbox/references/python/mcp_text_extractor.py`
        so this test stays in sync with the SKILL.md prose example
        (SSOT — see AGENTS.md § 7).

        Wraps `agent.run()` in tenacity exponential backoff so transient
        429s from the public Learn MCP endpoint (observed on weekly
        sweeps) don't fail the live-Azure gate. We rebuild the agent and
        the MCP tool on every retry because the streamable-HTTP session
        is not guaranteed to be reusable after a mid-call failure.
        """
        import asyncio
        from agent_framework import Agent, MCPStreamableHTTPTool, Message
        from tenacity import (
            retry,
            retry_if_not_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=2, min=4, max=30),
            reraise=True,
            retry=retry_if_not_exception_type(AssertionError),
        )
        async def _run_once():
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
            return await agent.run(messages=[msg])

        response = asyncio.run(_run_once())
        text = response.text if hasattr(response, "text") else str(response)
        self.assertGreater(len(text), 50, "Response too short")
        has_azure_content = "azure" in text.lower() or "container" in text.lower()
        self.assertTrue(has_azure_content, "Response should mention Azure/Container")
        print(f"\n  ✅ Agent + MCP tool E2E OK ({len(text)} chars)")


if __name__ == "__main__":
    unittest.main(verbosity=2)

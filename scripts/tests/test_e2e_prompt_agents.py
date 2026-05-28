#!/usr/bin/env python3
"""
E2E test for foundry-prompt-agents skill — creates a prompt agent on Azure,
chats with it, verifies the response, and cleans up.

Requires:
  - AZURE_AI_ENDPOINT env var (Foundry project endpoint)
  - Azure CLI authenticated (AzureCliCredential)
  - azure-ai-projects >= 2.1.0 and azure-identity installed

Run:
  python -m pytest scripts/tests/test_e2e_prompt_agents.py -v
  # or directly:
  python scripts/tests/test_e2e_prompt_agents.py
"""

from __future__ import annotations

import os
import sys
import unittest

# Skip entire module if Azure endpoint is not configured
AZURE_AI_ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "")
SKIP_REASON = "AZURE_AI_ENDPOINT not set — skipping Azure E2E tests"


@unittest.skipUnless(AZURE_AI_ENDPOINT, SKIP_REASON)
class TestPromptAgentE2E(unittest.TestCase):
    """Full lifecycle test: create → chat → list → delete."""

    AGENT_NAME = "ci-e2e-prompt-agent-test"
    MODEL = "gpt-5.4-mini"  # cheapest model in CI infra

    @classmethod
    def setUpClass(cls):
        # Lazy imports so the module loads even without the SDK
        from azure.identity import AzureCliCredential
        from azure.ai.projects import AIProjectClient
        from azure.ai.projects.models import PromptAgentDefinition

        cls.PromptAgentDefinition = PromptAgentDefinition
        cls.project = AIProjectClient(
            endpoint=AZURE_AI_ENDPOINT,
            credential=AzureCliCredential(),
        )
        cls.created_version = None

    @classmethod
    def tearDownClass(cls):
        """Best-effort cleanup of the test agent."""
        if cls.created_version:
            try:
                cls.project.agents.delete_version(
                    cls.AGENT_NAME, str(cls.created_version)
                )
                print(f"\n  ✅ Cleaned up {cls.AGENT_NAME} v{cls.created_version}")
            except Exception as e:
                print(f"\n  ⚠️  Cleanup failed: {e}", file=sys.stderr)

    def test_01_create_agent(self):
        """Create a prompt agent with PromptAgentDefinition."""
        agent = self.project.agents.create_version(
            agent_name=self.AGENT_NAME,
            definition=self.PromptAgentDefinition(
                model=self.MODEL,
                instructions=(
                    "You are a CI test assistant. "
                    "When asked 'ping', respond with exactly: 'pong-ci-ok'"
                ),
            ),
        )
        self.__class__.created_version = agent.version
        self.assertEqual(agent.name, self.AGENT_NAME)
        self.assertIsNotNone(agent.version)
        print(f"\n  ✅ Created {agent.name} v{agent.version}")

    def test_02_chat_with_agent(self):
        """Chat with the agent via conversations API and verify response."""
        self.assertIsNotNone(
            self.created_version, "Agent not created — test_01 must run first"
        )

        openai = self.project.get_openai_client()
        conversation = openai.conversations.create()
        self.assertIsNotNone(conversation.id)

        response = openai.responses.create(
            conversation=conversation.id,
            extra_body={
                "agent_reference": {
                    "name": self.AGENT_NAME,
                    "type": "agent_reference",
                }
            },
            input="ping",
        )

        response_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for c in item.content:
                    if hasattr(c, "text"):
                        response_text += c.text

        self.assertIn("pong", response_text.lower())
        print(f"\n  ✅ Agent responded: {response_text[:80]}")

    def test_03_list_agents(self):
        """List agents and verify the test agent appears."""
        found = False
        for agent in self.project.agents.list():
            if agent.name == self.AGENT_NAME:
                found = True
                self.assertIn("latest", agent.versions)
                break
        self.assertTrue(found, f"Agent {self.AGENT_NAME} not found in list")
        print(f"\n  ✅ Found {self.AGENT_NAME} in agent list")


if __name__ == "__main__":
    unittest.main(verbosity=2)

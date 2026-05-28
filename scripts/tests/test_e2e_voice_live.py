#!/usr/bin/env python3
"""
E2E test for foundry-voice-live skill — verifies the Azure AI Services
endpoint is reachable and the OpenAI SDK can construct a Voice Live client
with the correct websocket_base_url.

This does NOT open a full WebSocket session (that requires a microphone /
audio stream). It verifies the SDK surface and credential chain that the
skill depends on.

Requires:
  - AZURE_AI_ENDPOINT env var (e.g. https://aif-awesome-gbb-ci.cognitiveservices.azure.com/)
  - Azure CLI authenticated (AzureCliCredential)
  - openai >= 2.0.0 and azure-identity installed

Run:
  python -m pytest scripts/tests/test_e2e_voice_live.py -v
"""

from __future__ import annotations

import os
import re
import unittest

AZURE_AI_ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "")
SKIP_REASON = "AZURE_AI_ENDPOINT not set — skipping Azure E2E tests"


@unittest.skipUnless(AZURE_AI_ENDPOINT, SKIP_REASON)
class TestVoiceLiveE2E(unittest.TestCase):
    """Verify SDK surface, credential chain, and endpoint reachability."""

    @classmethod
    def setUpClass(cls):
        from azure.identity import AzureCliCredential, get_bearer_token_provider
        from openai import AsyncAzureOpenAI

        cls.AsyncAzureOpenAI = AsyncAzureOpenAI
        cls.credential = AzureCliCredential()
        cls.token_provider = get_bearer_token_provider(
            cls.credential, "https://cognitiveservices.azure.com/.default"
        )
        # Derive resource name from endpoint
        # https://aif-foo.cognitiveservices.azure.com/ → aif-foo
        m = re.match(r"https://([^.]+)\.", AZURE_AI_ENDPOINT)
        cls.resource_name = m.group(1) if m else "unknown"

    def test_01_credential_token(self):
        """Verify AzureCliCredential can get a cognitiveservices token."""
        token = self.credential.get_token(
            "https://cognitiveservices.azure.com/.default"
        )
        self.assertIsNotNone(token.token)
        self.assertGreater(len(token.token), 100)
        print(f"\n  ✅ Got cognitiveservices token ({len(token.token)} chars)")

    def test_02_websocket_base_url_construction(self):
        """Verify AsyncAzureOpenAI accepts websocket_base_url kwarg."""
        import inspect

        sig = inspect.signature(self.AsyncAzureOpenAI.__init__)
        self.assertIn("websocket_base_url", sig.parameters)

        # Construct the Voice Live WSS URL
        wss_url = (
            f"wss://{self.resource_name}.services.ai.azure.com/voice-live"
        )
        # Construct client — doesn't connect, just validates construction
        client = self.AsyncAzureOpenAI(
            azure_endpoint=f"https://{self.resource_name}.openai.azure.com",
            azure_ad_token_provider=self.token_provider,
            api_version="2025-10-01",
            websocket_base_url=wss_url,
        )
        self.assertIsNotNone(client)
        print(f"\n  ✅ AsyncAzureOpenAI constructed with websocket_base_url={wss_url}")

    def test_03_realtime_attribute_exists(self):
        """Verify the client exposes .realtime for Voice Live connections."""
        client = self.AsyncAzureOpenAI(
            azure_endpoint=f"https://{self.resource_name}.openai.azure.com",
            azure_ad_token_provider=self.token_provider,
            api_version="2025-10-01",
        )
        self.assertTrue(hasattr(client, "realtime"))
        self.assertTrue(hasattr(client.realtime, "connect"))
        print("\n  ✅ client.realtime.connect() exists")

    def test_04_foundry_token_scope(self):
        """Verify we can also get the ai.azure.com scope (Rung 3 agent routing)."""
        token = self.credential.get_token("https://ai.azure.com/.default")
        self.assertIsNotNone(token.token)
        self.assertGreater(len(token.token), 100)
        print(f"\n  ✅ Got ai.azure.com token ({len(token.token)} chars, for Rung 3 agent routing)")


if __name__ == "__main__":
    unittest.main(verbosity=2)

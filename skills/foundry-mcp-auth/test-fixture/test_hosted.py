"""Offline checks of the released wrapper, NOT trusted platform caller evidence."""

import importlib.metadata
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from azure.core.credentials import AccessToken
from agent_framework_foundry_hosting._toolbox import _ToolboxAuth
from references.python import hosted_agent


class HostedTests(unittest.IsolatedAsyncioTestCase):
    async def test_released_auth_fetches_token_and_call_context_per_request(self):
        calls = []

        class Credential:
            async def get_token(self, scope):
                calls.append(scope)
                return AccessToken("local-platform-placeholder", 9999999999)

        auth = _ToolboxAuth(Credential(), "https://ai.azure.com/.default")
        for call_id in ("call-a", "call-b"):
            context = SimpleNamespace(platform_headers=lambda: {"x-agent-foundry-call-id": call_id})
            with patch("agent_framework_foundry_hosting._toolbox.get_request_context", return_value=context):
                request = httpx.Request("POST", "https://example.services.ai.azure.com/toolbox")
                async for outbound in auth.async_auth_flow(request):
                    self.assertEqual(outbound.headers["x-agent-foundry-call-id"], call_id)
                    self.assertEqual(outbound.headers["authorization"], "Bearer local-platform-placeholder")
                    self.assertNotIn("x-agent-user-id", outbound.headers)
        self.assertEqual(calls, ["https://ai.azure.com/.default"] * 2)

    async def test_runtime_import_and_dependency_boundary(self):
        self.assertTrue(callable(hosted_agent.main))
        self.assertTrue(importlib.metadata.version("azure-ai-projects").startswith("2.3."))
        self.assertEqual(importlib.metadata.version("agent-framework-foundry-hosting"), "1.0.0b260730")
        self.assertTrue(importlib.metadata.version("mcp").startswith("1.29."))


if __name__ == "__main__":
    unittest.main()

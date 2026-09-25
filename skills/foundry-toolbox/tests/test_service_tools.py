"""Offline serialization checks for the isolated management path."""

import importlib.util
import unittest
from pathlib import Path

from azure.ai.projects.models import A2APreviewToolboxTool, ToolConfig


SOURCE = Path(__file__).resolve().parents[1] / "references/python/service_tools.py"
SPEC = importlib.util.spec_from_file_location("service_tools", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ServiceToolsTests(unittest.TestCase):
    def test_a2a_has_explicit_ga_protocol(self):
        self.assertEqual(
            MODULE.a2a_peer("approved-peer").as_dict(),
            {
                "name": "peer-agent",
                "type": "a2a",
                "a2a_version": "1.0",
                "project_connection_id": "approved-peer",
            },
        )

    def test_preview_model_is_not_silently_migrated(self):
        self.assertEqual(
            A2APreviewToolboxTool(project_connection_id="existing-peer").as_dict()["type"],
            "a2a_preview",
        )

    def test_search_keeps_source_keys_and_approval(self):
        tools = MODULE.searchable_mcp(
            "catalog", "https://example.test/mcp", "approved-mcp",
            {
                "*": ToolConfig(pin=False),
                "lookup_order": ToolConfig(pin=True, additional_search_text="shipping parcel"),
            },
        )
        self.assertEqual(
            [tool.as_dict() for tool in tools],
            [
                {
                    "type": "mcp",
                    "server_label": "catalog",
                    "server_url": "https://example.test/mcp",
                    "project_connection_id": "approved-mcp",
                    "require_approval": "always",
                    "tool_configs": {
                        "*": {"pin": False},
                        "lookup_order": {"pin": True, "additional_search_text": "shipping parcel"},
                    },
                },
                {"type": "toolbox_search"},
            ],
        )

    def test_empty_configuration_does_not_invent_pins(self):
        tools = MODULE.searchable_mcp(
            "catalog", "https://example.test/mcp", "approved-mcp", {}
        )
        self.assertEqual(tools[0].tool_configs, {})
        self.assertNotIn("authorization", tools[0].as_dict())

    def test_missing_connection_rejected(self):
        for value in ("", " "):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.a2a_peer(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.searchable_mcp("catalog", "https://example.test/mcp", value, {})

    def test_public_no_auth_server_needs_no_connection_resource(self):
        tools = MODULE.searchable_mcp(
            "learn", "https://learn.microsoft.com/api/mcp", None, {}
        )
        payload = tools[0].as_dict()
        self.assertNotIn("project_connection_id", payload)
        self.assertEqual(payload["require_approval"], "always")


if __name__ == "__main__":
    unittest.main()

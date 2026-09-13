"""Contract tests for the nested Toolbox OAuth consent error envelope."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "skills/foundry-toolbox/references/python/toolbox_consent.py"
SKILL = ROOT / "skills/foundry-toolbox/SKILL.md"


def envelope(*errors: dict) -> dict:
    return {
        "code": -32006,
        "message": "tools/list failed for tool sources " + json.dumps({"errors": list(errors)}),
    }


def source_error(code: str = "CONSENT_REQUIRED", message: str = "https://consent.example/login?data=opaque") -> dict:
    return {"name": "source", "type": "mcp", "error": {"code": code, "message": message}}


class ToolboxConsentTests(unittest.TestCase):
    def load_module(self):
        self.assertTrue(MODULE.is_file(), "canonical nested consent parser is missing")
        spec = importlib.util.spec_from_file_location("toolbox_consent", MODULE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_extracts_nested_url_not_outer_human_readable_message(self) -> None:
        module = self.load_module()
        requests = module.extract_consent_requests(envelope(source_error()))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].source, "source")
        self.assertEqual(requests[0].url, "https://consent.example/login?data=opaque")

    def test_preserves_every_connection_requiring_consent(self) -> None:
        module = self.load_module()
        other = source_error(message="https://consent.example/second")
        other["name"] = "second"
        requests = module.extract_consent_requests(envelope(source_error(), other))
        self.assertEqual([request.source for request in requests], ["source", "second"])

    def test_preserves_documented_direct_consent_message(self) -> None:
        module = self.load_module()
        requests = module.extract_consent_requests(
            {"code": -32006, "message": "User consent is required. Please visit: https://consent.example/login"}
        )
        self.assertEqual(requests[0].source, "toolbox")
        self.assertEqual(requests[0].url, "https://consent.example/login")

    def test_receipt_repr_does_not_log_opaque_consent_query(self) -> None:
        module = self.load_module()
        requests = module.extract_consent_requests(envelope(source_error()))
        self.assertNotIn("opaque", repr(requests))
        self.assertNotIn("https://", repr(requests))

    def test_non_consent_source_error_is_not_silently_dropped(self) -> None:
        module = self.load_module()
        response = envelope(source_error(), source_error("CONNECTION_FAILED", "backend unavailable"))
        with self.assertRaisesRegex(module.ToolboxConsentError, "non-consent"):
            module.extract_consent_requests(response)

    def test_outer_error_code_alone_is_not_proof_of_consent(self) -> None:
        module = self.load_module()
        with self.assertRaises(module.ToolboxConsentError):
            module.extract_consent_requests({"code": -32006, "message": "backend unavailable"})

    def test_rejects_different_rpc_error_without_leaking_message(self) -> None:
        module = self.load_module()
        with self.assertRaises(module.ToolboxConsentError) as caught:
            module.extract_consent_requests({"code": -32601, "message": "sensitive raw payload"})
        self.assertNotIn("sensitive", str(caught.exception))

    def test_rejects_malformed_or_empty_source_envelopes(self) -> None:
        module = self.load_module()
        for message in ("prefix {broken}", 'prefix {"errors":[]}', 'prefix {"errors":"bad"}'):
            with self.subTest(message=message):
                with self.assertRaises(module.ToolboxConsentError):
                    module.extract_consent_requests({"code": -32006, "message": message})

    def test_rejects_bad_connection_shape(self) -> None:
        module = self.load_module()
        for entry in ({}, {"name": "source", "error": []}, {"error": {"code": "CONSENT_REQUIRED"}}):
            with self.subTest(entry=entry):
                with self.assertRaises(module.ToolboxConsentError):
                    module.extract_consent_requests(envelope(entry))

    def test_rejects_non_https_or_credential_bearing_consent_urls(self) -> None:
        module = self.load_module()
        for url in ("javascript:alert(1)", "http://consent.example/", "/relative", "https://user:pass@consent.example/"):
            with self.subTest(url=url):
                with self.assertRaises(module.ToolboxConsentError):
                    module.extract_consent_requests(envelope(source_error(message=url)))

    def test_rejects_trailing_unparsed_content(self) -> None:
        module = self.load_module()
        response = envelope(source_error())
        response["message"] += " trailing unparsed data"
        with self.assertRaises(module.ToolboxConsentError):
            module.extract_consent_requests(response)

    def test_skill_links_parser_and_does_not_recommend_prompt_only_approval(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("(references/python/toolbox_consent.py)", skill)
        self.assertIn("nested", skill.split("> **First-time consent.**", 1)[1].split("###", 1)[0])
        self.assertNotIn("inject a system-prompt constraint listing the tools", skill)

    def test_tool_names_follow_the_proxy_discovery_contract(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("{server_label}___{tool_name}", skill)
        self.assertNotIn("MCP tool names follow `{server_label}.{tool_name}`", skill)

    def test_approval_discovery_uses_the_mcp_transport_not_plain_json_post(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        section = skill.split("## Approval gating (`require_approval`)", 1)[1].split("\n## ", 1)[0]
        self.assertIn("async def fetch_approval_map(endpoint, headers)", section)
        self.assertIn("await session.initialize()", section)
        self.assertIn("await session.list_tools()", section)
        self.assertNotIn("resp.json()", section)
        self.assertNotIn("httpx.AsyncClient", section)


if __name__ == "__main__":
    unittest.main()

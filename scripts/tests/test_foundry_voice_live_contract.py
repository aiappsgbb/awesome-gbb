#!/usr/bin/env python3
"""Focused exact-contract test for the foundry-voice-live pin refresh."""

from __future__ import annotations

import pathlib
import re
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
PIN = ROOT / "skills" / "foundry-voice-live" / "references" / "upstream-pin.md"


class FoundryVoiceLivePinContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pin = PIN.read_text(encoding="utf-8")
        cls.frontmatter = yaml.safe_load(cls.pin.split("---", 2)[1])
        cls.validation_script = cls.frontmatter["validation"]["script"]
        validation_python = re.search(
            r"python - <<'PY'\n(?P<body>.*?)\nPY(?:\n|$)",
            cls.validation_script,
            flags=re.DOTALL,
        )
        if validation_python is None:
            raise AssertionError("validation Python heredoc not found")
        cls.validation_python = validation_python.group("body")

    def test_upstream_pin_matches_voice_live_sdk_13_contract(self) -> None:
        self.assertEqual(
            self.frontmatter["packages"],
            [
                {
                    "name": "openai",
                    "version": "2.53.0",
                    "specifier": "~=2.53.0",
                    "source": "pypi",
                },
                {
                    "name": "azure-identity",
                    "version": "1.25.3",
                    "specifier": "~=1.25.3",
                    "source": "pypi",
                },
                {
                    "name": "fastrtc",
                    "version": "0.0.34",
                    "specifier": "~=0.0.34",
                    "source": "pypi",
                },
                {
                    "name": "gradio",
                    "version": "5.50.0",
                    "specifier": "~=5.50.0",
                    "source": "pypi",
                    "hold_below": "6.0.0",
                    "hold_reason": "KI-001",
                },
                {
                    "name": "azure-ai-voicelive",
                    "version": "1.3.0",
                    "specifier": "~=1.3.0",
                    "source": "pypi",
                },
            ],
        )

        self.assertEqual(self.frontmatter["known_issues_count"], 1)
        self.assertEqual(len(self.frontmatter["known_issues"]), 1)
        self.assertEqual(
            self.frontmatter["known_issues"][0],
            {
                "id": "KI-001",
                "description": "FastRTC 0.0.34 requires gradio>=4,<6; hold Gradio below 6 until FastRTC lifts its upper bound.",
                "upstream_url": "https://github.com/gradio-app/fastrtc/issues/428",
                "status": "open",
                "workaround_location": 'SKILL.md § "Dependencies"',
            },
        )
        self.assertEqual(str(self.frontmatter["last_validated"]), "2026-08-05")
        self.assertEqual(self.frontmatter["validated_by"], "ricchi")

        self.assertEqual(
            self.frontmatter["docs_to_revalidate"],
            [
                "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live",
                "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to",
                "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-04-10",
                "https://learn.microsoft.com/azure/foundry-classic/openai/concepts/audio",
            ],
        )
        self.assertNotIn("azure/ai-foundry/openai/concepts/audio", self.pin)
        self.assertNotIn("2026-07-15", "\n".join(self.frontmatter["docs_to_revalidate"]))

        for specifier in (
            '"openai~=2.53.0"',
            '"azure-identity~=1.25.3"',
            '"fastrtc~=0.0.34"',
            '"gradio~=5.50.0"',
            '"azure-ai-voicelive[aiohttp]~=1.3.0"',
        ):
            with self.subTest(specifier=specifier):
                self.assertIn(specifier, self.validation_script)

        for token in (
            "import inspect",
            "from importlib.metadata import version",
            "import gradio",
            "import fastrtc",
            "from fastrtc import AsyncStreamHandler, WebRTC, wait_for_item",
            "from openai import AsyncAzureOpenAI",
            "from azure.ai.voicelive.aio import connect",
            "from azure.ai.voicelive.models import AzureSemanticVad",
            'assert "endpoint" in connect_sig.parameters',
            'assert "credential" in connect_sig.parameters',
            'assert "api_version" in connect_sig.parameters',
            'assert "model" in connect_sig.parameters',
            'assert connect_sig.parameters["api_version"].default == "2026-07-15"',
            'assert "azure_endpoint" in init_sig.parameters',
            'assert "azure_deployment" in init_sig.parameters',
            'assert "api_version" in init_sig.parameters',
            'assert "websocket_base_url" in init_sig.parameters',
            'assert hasattr(AsyncAzureOpenAI, "realtime")',
            'assert version("openai").startswith("2.53.")',
            'assert version("azure-identity").startswith("1.25.")',
            'assert version("fastrtc").startswith("0.0.34")',
            'assert version("gradio").startswith("5.50.")',
            'assert version("azure-ai-voicelive").startswith("1.3.")',
            '"create_response"',
            '"auto_truncate"',
            '"interrupt_response"',
            'print("voicelive-sdk-13-default-2026-07-15")',
            'print("openai-253-realtime-surface")',
            'print("fastrtc-gradio5-compatible")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.validation_python)

        compile(self.validation_python, "<foundry-voice-live-pin-validation>", "exec")
        self.assertEqual(
            self.frontmatter["validation"]["expected_output"],
            [
                "openai.AsyncAzureOpenAI OK",
                "azure.identity.aio OK",
                "fastrtc OK",
                "gradio OK",
                "voicelive-sdk-13-default-2026-07-15",
                "openai-253-realtime-surface",
                "fastrtc-gradio5-compatible",
                "VALIDATION_PASSED",
            ],
        )

        for row in (
            "| `openai` | `~=2.53.0` | `AsyncAzureOpenAI.realtime.connect()` + `websocket_base_url` kwarg |",
            "| `azure-identity` | `~=1.25.3` | `DefaultAzureCredential` + `get_bearer_token_provider` async |",
            "| `fastrtc` | `~=0.0.34` | `AsyncStreamHandler`, `WebRTC`, `wait_for_item`; requires `gradio>=4,<6` |",
            "| `gradio` | `~=5.50.0` | Blocks UI, state management; held below 6 by KI-001 |",
            "| `azure-ai-voicelive` | `~=1.3.0` | Native `connect()` default API version `2026-07-15` + `AzureSemanticVad` GA fields |",
        ):
            with self.subTest(row=row):
                self.assertIn(row, self.pin)
        self.assertIn("### Known issues", self.pin)
        self.assertIn("#### KI-001 - FastRTC blocks Gradio 6", self.pin)
        self.assertIn(
            "FastRTC `0.0.34` declares `gradio>=4,<6`, so this pin holds "
            "`gradio~=5.50.0` and records the hold with `hold_below: \"6.0.0\"` "
            "+ `hold_reason: KI-001` until upstream issue #428 resolves.",
            " ".join(self.pin.split()),
        )


if __name__ == "__main__":
    unittest.main()

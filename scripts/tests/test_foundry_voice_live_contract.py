#!/usr/bin/env python3
"""Focused exact-contract test for the foundry-voice-live pin refresh."""

from __future__ import annotations

import json
import pathlib
import re
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
PIN = ROOT / "skills" / "foundry-voice-live" / "references" / "upstream-pin.md"
SKILL = ROOT / "skills" / "foundry-voice-live" / "SKILL.md"
FIXTURE = ROOT / "skills" / "foundry-voice-live" / "test-fixture" / "consumer_prompt.md"
README = ROOT / "README.md"
PLUGIN = ROOT / "plugin.json"
MARKETPLACE = ROOT / ".github" / "plugin" / "marketplace.json"

VOICE_LIVE_README_ROW = (
    "| [**foundry-voice-live**](skills/foundry-voice-live/) | Build real-time voice agents "
    "with Azure Voice Live (GA 2026-04-10) through a four-rung migration from Azure OpenAI "
    "Realtime to the native Voice Live SDK. Covers semantic VAD, echo cancellation, Neural HD "
    "voices, Foundry agent routing, benchmark patterns, and the FastRTC 0.0.34 plus Gradio 5.50 "
    "compatibility boundary |"
)


def _fenced_blocks(markdown: str, language: str) -> list[str]:
    return [
        match.group("body")
        for match in re.finditer(
            rf"```{re.escape(language)}\n(?P<body>.*?)\n```",
            markdown,
            flags=re.DOTALL,
        )
    ]


def _python_heredoc(markdown: str) -> str:
    for block in _fenced_blocks(markdown, "bash"):
        match = re.search(r"python3 <<'PY'\n(?P<body>.*?)\nPY(?:\n|$)", block, flags=re.DOTALL)
        if match:
            return match.group("body")
    raise AssertionError("fixture Python heredoc not found")


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*"
    r")?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class FoundryVoiceLivePublicationContractTests(unittest.TestCase):
    def test_catalog_versions_are_semver_and_match_marketplace(self) -> None:
        plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
        marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))

        self.assertRegex(plugin["version"], SEMVER_RE)
        self.assertEqual(
            marketplace["metadata"]["version"],
            plugin["version"],
        )
        for index, entry in enumerate(marketplace["plugins"]):
            with self.subTest(plugin_index=index):
                self.assertEqual(entry["version"], plugin["version"])

    def test_readme_contains_exact_foundry_voice_live_publication_row(self) -> None:
        readme = README.read_text(encoding="utf-8")
        rows = [
            line
            for line in readme.splitlines()
            if line.startswith("| [**foundry-voice-live**](skills/foundry-voice-live/) |")
        ]

        self.assertEqual(rows, [VOICE_LIVE_README_ROW])


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
            'assert version("fastrtc").startswith("0.0.")',
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


class FoundryVoiceLiveSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.skill_flat = " ".join(cls.skill.split())
        cls.frontmatter = yaml.safe_load(cls.skill.split("---", 2)[1])

    def test_frontmatter_version_and_description_contract(self) -> None:
        self.assertEqual(
            list(self.frontmatter.keys()),
            ["name", "description", "metadata"],
        )
        self.assertEqual(self.frontmatter["name"], "foundry-voice-live")
        self.assertEqual(self.frontmatter["metadata"], {"version": "1.4.0"})
        self.assertLessEqual(len(self.frontmatter["description"]), 1024)

    def test_sdk_13_ga_api_contract_is_explicit(self) -> None:
        for phrase in (
            "validated native stack is `azure-ai-voicelive[aiohttp]~=1.3.0`",
            "SDK 1.3 defaults `connect()` to `2026-07-15`",
            'this skill deliberately passes `api_version="2026-04-10"`',
            "do not remove until a separate `2026-07-15` migration is tested end-to-end",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.skill_flat)

        for connect_call in re.findall(
            r"async with connect\(\n(?P<body>.*?\n)\s*\) as conn:",
            self.skill,
            flags=re.DOTALL,
        ):
            with self.subTest(connect_call=connect_call[:80]):
                self.assertRegex(
                    connect_call,
                    r"(?s)credential=.*?api_version=\"2026-04-10\".*?model=",
                )

        self.assertNotIn('api_version="2026-07-15"', self.skill)

    def test_dependencies_and_compatibility_hold(self) -> None:
        for dependency in (
            '"openai~=2.53.0"',
            '"azure-identity~=1.25.3"',
            '"fastrtc~=0.0.34"',
            '"gradio~=5.50.0"',
            '"azure-ai-voicelive[aiohttp]~=1.3.0"',
            '"av>=16.0.0,<17.0.0"',
            '"pydantic-settings>=2.10.1"',
            '"aiohttp>=3.12.15"',
            '"fastapi>=0.116.1"',
            '"uvicorn>=0.35.0"',
        ):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, self.skill)

        for phrase in (
            "FastRTC `0.0.34` requires Gradio `<6`",
            "`gradio~=5.50.0` remains pinned until KI-001 closes",
            "Gradio 6 is not independently installable for this stack",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.skill_flat)

    def test_section_12_opening_states_ga_and_shim_contract(self) -> None:
        section_12_opening = re.search(
            r"## 12 · 2026-04-10 GA Deltas\n\n(?P<body>.*?)(?:\n### 12\.1)",
            self.skill,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_12_opening)
        body = " ".join(section_12_opening.group("body").split())
        for phrase in (
            "live-proven on API `2026-04-10`",
            "SDK 1.3 defaults to `2026-07-15`",
            "every Rung 4 `connect(...)` call passes `2026-04-10` explicitly",
            "Rungs 2-3 send equivalent payloads through the OpenAI shim",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, body)

    def test_stale_dependency_and_version_claims_are_absent(self) -> None:
        for stale in (
            '"openai>=2.0.0"',
            '"azure-identity>=1.24.0"',
            '"fastrtc>=0.0.34"',
            '"gradio>=5.42.0"',
            "azure-ai-voicelive[aiohttp]~=1.2.0",
            "stable `1.2.0`",
            "# default in 1.2.0",
            "~=1.2.0",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.skill)


class FoundryVoiceLiveFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.fixture_flat = " ".join(cls.fixture.split())
        cls.python = _python_heredoc(cls.fixture)
        cls.fixture_without_python = cls.fixture.replace(cls.python, "")
        cls.bash_blocks = _fenced_blocks(cls.fixture, "bash")

    def test_fixture_is_self_contained_and_first_bash_action_acknowledges_skill_contract(self) -> None:
        first_bash_lines = [
            line.strip()
            for line in self.bash_blocks[0].splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertEqual(first_bash_lines[0], 'echo "skills/foundry-voice-live/SKILL.md"')

        for required in (
            "self-contained execution smoke",
            "Do NOT open/read the whole skill file",
            "never invoke `copilot` recursively",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.fixture)

        for forbidden in (
            "Do whatever the skill tells you",
            "read the skill's `SKILL.md` first",
            "Read it before you write any code",
            "find /",
            "git grep",
            "rg ",
            "copilot -p",
            "copilot --version",
            "npm install -g @github/copilot",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.fixture)

    def test_fixture_installs_only_sdk_13_bounded_dependencies(self) -> None:
        expected_install = (
            'python3 -m pip install --quiet \\\n'
            '  "azure-ai-voicelive[aiohttp]~=1.3.0" \\\n'
            '  "azure-identity~=1.25.3"'
        )
        self.assertIn(expected_install, self.fixture)
        self.assertEqual(self.fixture.count("python3 -m pip install --quiet"), 1)
        self.assertNotIn("python3 -m pip install --quiet --upgrade pip", self.fixture)

    def test_fixture_documents_explicit_ga_api_version_for_sdk_13(self) -> None:
        for required in (
            "SDK 1.3 now defaults 2026-07-15",
            'passes `api_version="2026-04-10"` explicitly',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.fixture_flat)

        for forbidden in (
            "~=1.2.0",
            'SDK defaults: api_version="2026-04-10"',
            "the SDK default",
            "do not override",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.fixture)

        self.assertIn('api_version="2026-04-10"', self.fixture)
        self.assertIn('api_version="2026-04-10"', self.skill)

    def test_fixture_python_uses_explicit_ga_connect_shape_and_runtime_evidence(self) -> None:
        expected_connect = (
            "async with connect(\n"
            "            endpoint=voicelive_endpoint,\n"
            "            credential=cred,\n"
            '            api_version="2026-04-10",\n'
            '            model="gpt-realtime",\n'
            "        ) as conn:"
        )
        self.assertIn(expected_connect, self.python)
        self.assertIn(
            "SDK 1.3 defaults 2026-07-15; the fixture preserves the "
            "live-proven 2026-04-10 API.",
            self.python,
        )

        for evidence in (
            'print("VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3")',
            'print(f"VOICELIVE_EVENT type={event.type}")',
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, self.python)

        for prose_only_token in (
            "VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3",
            "VOICELIVE_EVENT type=",
        ):
            with self.subTest(prose_only_token=prose_only_token):
                self.assertNotIn(prose_only_token, self.fixture_without_python)

    def test_fixture_preserves_wss_roundtrip_and_marker_contract(self) -> None:
        for token in (
            "InputTextContentPart",
            "UserMessageItem",
            'text="say hi"',
            "ServerEventType.SESSION_CREATED",
            "ServerEventType.SESSION_UPDATED",
            "ServerEventType.CONVERSATION_ITEM_CREATED",
            "ServerEventType.RESPONSE_CREATED",
            "ServerEventType.RESPONSE_TEXT_DELTA",
            "ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DELTA",
            "ServerEventType.RESPONSE_DONE",
            "ServerEventType.ERROR",
            "FAIL: server error event",
            "voice-live-roundtrip-ok",
            "/tmp/foundry-voice-live-smoke-result",
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-voice-live-smoke-result",
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > /tmp/foundry-voice-live-smoke-result",
            "byte content is what CI grades",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)

    def test_fixture_only_uses_smoke_result_literals_in_authoritative_printf_commands(self) -> None:
        authoritative_lines = (
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-voice-live-smoke-result",
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > /tmp/foundry-voice-live-smoke-result",
        )
        stripped = self.fixture
        for line in authoritative_lines:
            stripped = stripped.replace(line, "")

        self.assertNotIn("SMOKE_RESULT=", stripped)


if __name__ == "__main__":
    unittest.main()

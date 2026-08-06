#!/usr/bin/env python3
"""Focused exact-contract test for the foundry-voice-live pin refresh."""

from __future__ import annotations

import ast
import asyncio
from enum import Enum
import json
import pathlib
import re
from types import SimpleNamespace
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


def _load_fixture_event_helpers() -> dict[str, object]:
    python = _python_heredoc(FIXTURE.read_text(encoding="utf-8"))
    tree = ast.parse(python)
    helper_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name not in {"main", "record"}
    ]
    module = ast.Module(body=helper_defs, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {
        "asyncio": asyncio,
        "ServerEventType": FakeServerEventType,
        "record": lambda message: None,
        "print": lambda *args, **kwargs: None,
        "RuntimeError": RuntimeError,
        "getattr": getattr,
        "str": str,
    }
    exec(compile(module, "<foundry-voice-live-fixture-helpers>", "exec"), namespace)
    if "await_completed_response" not in namespace:
        raise AssertionError("fixture helper await_completed_response not found")
    return namespace


def _fixture_python_ast() -> ast.Module:
    return ast.parse(_python_heredoc(FIXTURE.read_text(encoding="utf-8")))


def _is_name(node: ast.AST | None, *names: str) -> bool:
    return isinstance(node, ast.Name) and node.id in names


def _is_asyncio_run_main_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and _is_name(node.func.value, "asyncio")
    ):
        return False
    return (
        len(node.args) == 1
        and isinstance(node.args[0], ast.Call)
        and _is_name(node.args[0].func, "main")
        and not node.keywords
    )


def _is_connect_async_with(node: ast.AST) -> bool:
    if not isinstance(node, ast.AsyncWith) or len(node.items) != 1:
        return False
    item = node.items[0]
    return (
        isinstance(item.context_expr, ast.Call)
        and _is_name(item.context_expr.func, "connect")
        and _is_name(item.optional_vars, "conn")
    )


def _is_suppressing_with(node: ast.AST) -> bool:
    if not isinstance(node, (ast.With, ast.AsyncWith)):
        return False
    for item in node.items:
        context = item.context_expr
        if isinstance(context, ast.Call):
            context = context.func
        if (
            isinstance(context, ast.Attribute)
            and context.attr == "suppress"
            and _is_name(context.value, "contextlib")
        ) or _is_name(context, "suppress"):
            return True
    return False


def _handler_matches_runtime_error_or_broader(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    if _is_name(handler.type, "RuntimeError", "Exception", "BaseException"):
        return True
    if isinstance(handler.type, ast.Tuple):
        return any(
            _is_name(elt, "RuntimeError", "Exception", "BaseException")
            for elt in handler.type.elts
        )
    return False


def _handler_reraises(handler: ast.ExceptHandler) -> bool:
    return any(isinstance(node, ast.Raise) and node.exc is None for node in ast.walk(handler))


def _position_after(left: ast.AST, right: ast.AST) -> bool:
    left_pos = (getattr(left, "lineno", 0), getattr(left, "col_offset", 0))
    right_pos = (
        getattr(right, "end_lineno", getattr(right, "lineno", 0)),
        getattr(right, "end_col_offset", getattr(right, "col_offset", 0)),
    )
    return left_pos > right_pos


class FakeServerEventType(Enum):
    SESSION_CREATED = "session.created"
    RESPONSE_DONE = "response.done"
    ERROR = "error"


class FakeStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INCOMPLETE = "incomplete"
    IN_PROGRESS = "in_progress"


class FakeAsyncStream:
    def __init__(self, events: list[object], *, never_end: bool = False) -> None:
        self._events = list(events)
        self._never_end = never_end

    def __aiter__(self) -> "FakeAsyncStream":
        return self

    async def __anext__(self) -> object:
        if self._events:
            return self._events.pop(0)
        if self._never_end:
            await asyncio.sleep(3600)
        raise StopAsyncIteration


def _event(event_type: object, *, status: object = None, error: object = None) -> object:
    response = SimpleNamespace(status=status) if status is not _NO_RESPONSE else None
    return SimpleNamespace(type=event_type, response=response, error=error)


_NO_RESPONSE = object()


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
            "ItemType",
            "MCPApprovalResponseRequestItem",
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
                "voicelive-mcp-approval-request-response-surface",
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
            "| `azure-ai-voicelive` | `~=1.3.0` | Native `connect()` default API version `2026-07-15`, `AzureSemanticVad` GA fields, and MCP approval request/response item models |",
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

    def test_pin_smoke_imports_real_mcp_approval_symbols(self) -> None:
        for token in (
            "ItemType",
            "MCPApprovalResponseRequestItem",
            "assert MCPServer is not None",
            "assert MCPApprovalType is not None",
            "assert MCPApprovalResponseRequestItem is not None",
            "assert MCPApprovalType.NEVER",
            "assert MCPApprovalType.ALWAYS",
            'assert ItemType.MCP_APPROVAL_REQUEST.value == "mcp_approval_request"',
            'assert ItemType.MCP_APPROVAL_RESPONSE.value == "mcp_approval_response"',
            'print("voicelive-mcp-approval-request-response-surface")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.validation_python)

        self.assertNotIn("MCPApprovalMode", self.validation_python)
        self.assertNotIn("mcp_" + "tool_approval", self.validation_python)
        self.assertIn(
            "voicelive-mcp-approval-request-response-surface",
            self.frontmatter["validation"]["expected_output"],
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

    def test_mcp_approval_uses_sdk_13_symbol_and_wire_event_name(self) -> None:
        section_12_2 = re.search(
            r"### 12\.2 · MCP server tools mid-turn\n\n(?P<body>.*?)(?:\n### 12\.3)",
            self.skill,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_12_2)
        body = section_12_2.group("body")

        for required in (
            "MCPApprovalType",
            "MCPApprovalResponseRequestItem",
            "ItemType.MCP_APPROVAL_REQUEST",
            "ItemType.MCP_APPROVAL_RESPONSE",
            "require_approval=MCPApprovalType.NEVER",
            "require_approval=MCPApprovalType.ALWAYS",
            "mcp_approval_request",
            "mcp_approval_response",
            "await conn.conversation.item.create(",
            "item=MCPApprovalResponseRequestItem(",
            "approval_request_id=event.item.id",
            "approve=True",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

        self.assertRegex(
            body,
            r"await conn\.conversation\.item\.create\(\s*"
            r"item=MCPApprovalResponseRequestItem\(\s*"
            r"approval_request_id=event\.item\.id,\s*"
            r"approve=True,\s*"
            r"\)\s*"
            r"\)",
        )

        for stale in ("MCPApprovalMode", "MCPToolApprovalRequest", "mcp_" + "tool_approval"):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.skill)

    def test_aiohttp_missing_extra_error_uses_real_sdk_13_importerror(self) -> None:
        real_prefix = "ImportError: aiohttp is required for azure-ai-voicelive"
        self.assertIn(real_prefix, self.skill)
        for stale in (
            "RuntimeError: aiohttp not installed",
            "RuntimeError: aiohttp",
            "aiohttp not installed",
            "aiohttp transport is required",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.skill)


class FoundryVoiceLiveFixtureEventStateMachineTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.helpers = _load_fixture_event_helpers()
        cls.await_completed_response = cls.helpers["await_completed_response"]

    async def _run(
        self,
        events: list[object],
        *,
        timeout_seconds: float = 0.01,
        never_end: bool = False,
        records: list[str] | None = None,
    ) -> tuple[object, list[str]]:
        if records is None:
            records = []
        self.helpers["record"] = records.append
        result = await self.helpers["await_completed_response"](
            FakeAsyncStream(events, never_end=never_end),
            timeout_seconds=timeout_seconds,
        )
        return result, records

    def assert_no_terminal_record(self, records: list[str]) -> None:
        self.assertFalse(
            any(record.startswith("VOICELIVE_TERMINAL") for record in records),
            f"failure path emitted terminal success evidence: {records!r}",
        )

    async def test_session_created_then_timeout_fails(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            await self._run(
                [_event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE)],
                never_end=True,
                records=records,
            )
        self.assert_no_terminal_record(records)
        self.assertEqual(records, ["VOICELIVE_EVENT type=session.created"])

    async def test_session_created_then_completed_response_done_succeeds_and_records_audit(self) -> None:
        result, records = await self._run(
            [
                _event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE),
                _event(FakeServerEventType.RESPONSE_DONE, status=FakeStatus.COMPLETED),
            ],
        )

        self.assertEqual(result, "completed")
        self.assertEqual(
            records,
            [
                "VOICELIVE_EVENT type=session.created",
                "VOICELIVE_TERMINAL type=response.done status=completed",
            ],
        )

    async def test_server_error_event_fails_immediately(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "server error event"):
            await self._run([_event(FakeServerEventType.ERROR, error="boom")], records=records)
        self.assert_no_terminal_record(records)
        self.assertEqual(records, [])

    async def test_stream_ending_before_response_done_fails(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "stream ended before response.done"):
            await self._run(
                [_event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE)],
                records=records,
            )
        self.assert_no_terminal_record(records)
        self.assertEqual(records, ["VOICELIVE_EVENT type=session.created"])

    async def test_response_done_completed_before_session_created_fails_specifically(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "response.done received before session.created"):
            await self._run(
                [_event(FakeServerEventType.RESPONSE_DONE, status=FakeStatus.COMPLETED)],
                records=records,
            )
        self.assert_no_terminal_record(records)
        self.assertEqual(records, [])

    async def test_immediately_empty_stream_fails_before_session_created_specifically(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "stream ended before session.created"):
            await self._run([], records=records)
        self.assert_no_terminal_record(records)
        self.assertEqual(records, [])

    async def test_unrelated_first_event_does_not_record_fake_session_evidence(self) -> None:
        result, records = await self._run(
            [
                _event("response.created", status=_NO_RESPONSE),
                _event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE),
                _event(FakeServerEventType.RESPONSE_DONE, status=FakeStatus.COMPLETED),
            ],
        )

        self.assertEqual(result, "completed")
        self.assertEqual(
            records,
            [
                "VOICELIVE_EVENT type=session.created",
                "VOICELIVE_TERMINAL type=response.done status=completed",
            ],
        )

    async def test_response_done_failed_fails(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "status=failed"):
            await self._run(
                [
                    _event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE),
                    _event(FakeServerEventType.RESPONSE_DONE, status=FakeStatus.FAILED),
                ],
                records=records,
            )
        self.assert_no_terminal_record(records)
        self.assertEqual(records, ["VOICELIVE_EVENT type=session.created"])

    async def test_response_done_cancelled_fails(self) -> None:
        records: list[str] = []
        with self.assertRaisesRegex(RuntimeError, "status=cancelled"):
            await self._run(
                [
                    _event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE),
                    _event(FakeServerEventType.RESPONSE_DONE, status=FakeStatus.CANCELLED),
                ],
                records=records,
            )
        self.assert_no_terminal_record(records)
        self.assertEqual(records, ["VOICELIVE_EVENT type=session.created"])

    async def test_response_done_non_completed_statuses_fail(self) -> None:
        cases = (
            (FakeStatus.INCOMPLETE, "incomplete"),
            (FakeStatus.IN_PROGRESS, "in_progress"),
            (None, "None"),
        )
        for status, status_label in cases:
            with self.subTest(status=status_label):
                records: list[str] = []
                expected = rf"response\.done status={re.escape(status_label)} is not completed"
                with self.assertRaisesRegex(RuntimeError, expected):
                    await self._run(
                        [
                            _event(FakeServerEventType.SESSION_CREATED, status=_NO_RESPONSE),
                            _event(FakeServerEventType.RESPONSE_DONE, status=status),
                        ],
                        records=records,
                    )
                self.assert_no_terminal_record(records)
                self.assertEqual(records, ["VOICELIVE_EVENT type=session.created"])


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
        self.assertIn(
            "ImportError: aiohttp is required for azure-ai-voicelive",
            self.fixture,
        )
        self.assertNotIn("aiohttp transport is required", self.fixture)

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
            'record("VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3")',
            'record("VOICELIVE_EVENT type=session.created")',
            'record("VOICELIVE_TERMINAL type=response.done status=completed")',
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, self.python)

        for prose_only_token in (
            "VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3",
            "VOICELIVE_EVENT type=",
            "VOICELIVE_TERMINAL type=",
        ):
            with self.subTest(prose_only_token=prose_only_token):
                self.assertNotIn(prose_only_token, self.fixture_without_python)

    def test_fixture_main_awaits_completed_response_before_success_print(self) -> None:
        tree = _fixture_python_ast()
        mains = [
            node
            for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "main"
        ]
        self.assertEqual(len(mains), 1)
        main = mains[0]

        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        asyncio_run_main_calls = [
            node for node in ast.walk(tree) if _is_asyncio_run_main_call(node)
        ]
        self.assertEqual(
            len(asyncio_run_main_calls),
            1,
            "fixture must contain exactly one asyncio.run(main()) call",
        )
        self.assertIsInstance(tree.body[-1], ast.Expr)
        self.assertIs(
            tree.body[-1].value,
            asyncio_run_main_calls[0],
            "module tail must be a bare top-level asyncio.run(main()) Expr",
        )

        awaited_calls = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and _is_name(node.value.func, "await_completed_response")
        ]
        self.assertEqual(len(awaited_calls), 1)
        await_node = awaited_calls[0]
        call = await_node.value

        self.assertEqual(len(call.args), 1)
        self.assertIsInstance(call.args[0], ast.Name)
        self.assertEqual(call.args[0].id, "conn")
        self.assertEqual(len(call.keywords), 1)
        timeout_keyword = call.keywords[0]
        self.assertEqual(timeout_keyword.arg, "timeout_seconds")
        self.assertIsInstance(timeout_keyword.value, ast.Constant)
        self.assertEqual(timeout_keyword.value.value, 60.0)

        containing_stmt: ast.AST = await_node
        while containing_stmt in parents and not isinstance(containing_stmt, ast.Expr):
            containing_stmt = parents[containing_stmt]
        self.assertIsInstance(containing_stmt, ast.Expr)

        connect_blocks = [node for node in ast.walk(main) if _is_connect_async_with(node)]
        self.assertEqual(len(connect_blocks), 1)
        connect_block = connect_blocks[0]
        self.assertIn(
            containing_stmt,
            connect_block.body,
            "await_completed_response must be a direct statement in the connect(...) as conn body",
        )

        forbidden_control_flow = (
            ast.If,
            ast.IfExp,
            ast.Try,
            ast.While,
            ast.For,
            ast.AsyncFor,
            ast.Match,
        )
        current: ast.AST = containing_stmt
        while current is not main:
            self.assertIn(current, parents, "await_completed_response is not inside main")
            current = parents[current]
            self.assertFalse(
                isinstance(current, forbidden_control_flow) or _is_suppressing_with(current),
                "await_completed_response must be unconditional: no If/IfExp/Try/loop/"
                "Match/suppressing-with ancestor may sit between it and main",
            )

        success_prints = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _is_name(node.func, "print")
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "voice-live-roundtrip-ok"
        ]
        self.assertEqual(len(success_prints), 1)
        success_literals = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and node.value == "voice-live-roundtrip-ok"
        ]
        self.assertEqual(success_literals, success_prints[0].args)
        self.assertTrue(
            _position_after(success_prints[0], await_node),
            "voice-live-roundtrip-ok must be printed only after awaiting "
            "await_completed_response",
        )

    def test_fixture_python_persists_fresh_runtime_evidence_file(self) -> None:
        evidence_path = "EVIDENCE_PATH = Path('/tmp/foundry-voice-live-smoke-evidence')"
        clear_file = "EVIDENCE_PATH.write_text('', encoding='utf-8')"
        record_signature = "def record(message: str) -> None:"
        append_file = 'with EVIDENCE_PATH.open("a", encoding="utf-8") as evidence:'
        append_line = 'evidence.write(message + "\\n")'
        print_line = "print(message)"

        for token in (
            "from pathlib import Path",
            evidence_path,
            clear_file,
            record_signature,
            append_file,
            append_line,
            print_line,
            'record("VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3")',
            'record("VOICELIVE_EVENT type=session.created")',
            'record("VOICELIVE_TERMINAL type=response.done status=completed")',
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.python)

        self.assertLess(self.python.index(clear_file), self.python.index(record_signature))
        self.assertLess(self.python.index(record_signature), self.python.index("async def main() -> None:"))
        self.assertLess(self.python.index(clear_file), self.python.index("async with connect("))

        self.assertIn("/tmp/foundry-voice-live-smoke-evidence", self.fixture)
        self.assertIn("authoritative audit trail", self.fixture_flat)
        self.assertIn("workflow uploads the evidence file", self.fixture_flat)

    def test_fixture_preserves_wss_roundtrip_and_marker_contract(self) -> None:
        for token in (
            "InputTextContentPart",
            "UserMessageItem",
            'text="say hi"',
            "ServerEventType.SESSION_CREATED",
            "ServerEventType.RESPONSE_DONE",
            "ServerEventType.ERROR",
            "async def await_completed_response(conn, timeout_seconds=60.0):",
            "timeout waiting for response.done",
            "stream ended before response.done",
            "response.done status=",
            "voice-live-roundtrip-ok",
            "/tmp/foundry-voice-live-smoke-result",
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-voice-live-smoke-result",
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > /tmp/foundry-voice-live-smoke-result",
            "byte content is what CI grades",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)

        self.assertNotIn("SMOKE_RESULT", self.python)
        self.assertLess(self.fixture.index("voice-live-roundtrip-ok"), self.fixture.index("## Step 4"))
        self.assertIn(
            "On success (Step 3's script exited 0 AND its stdout contained\n"
            "`voice-live-roundtrip-ok` AND the evidence file contains exactly three\n"
            "runtime records: connect, session-created, and terminal completed):",
            self.fixture,
        )
        for forbidden in (
            "ACCEPT =",
            "saw_event",
            "saw_terminal",
            "event loop hit 60 s timeout",
            "no accepted server event received",
            "first accepted-event record",
            "At least one event of type",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.fixture)

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

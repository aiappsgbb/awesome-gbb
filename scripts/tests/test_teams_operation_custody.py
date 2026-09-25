"""Execute template handlers with fake channels/backends; no Teams/Azure calls."""

import ast
import asyncio
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[2]
BOT = ROOT / "skills/foundry-teams-bot/templates/copilot"
sys.path.insert(0, str(ROOT / "skills/foundry-hosted-agents/references/python"))
sys.path.insert(0, str(BOT))
from invocation_custody import ExistingInvocation, InvocationJournal, invocation_events


async def events(values):
    for value in values:
        yield value


@dataclass
class TextChunk:
    text: str


@dataclass
class StatusUpdate:
    text: str


@dataclass
class SessionComplete:
    session_id: str


def load_handler(filename, namespace):
    tree = ast.parse((BOT / filename).read_text())
    handler = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == "on_message")
    handler.decorator_list = []
    handler.returns = None
    for argument in handler.args.args:
        argument.annotation = None
    exec(compile(ast.Module(body=[handler], type_ignores=[]), str(BOT / filename), "exec"), namespace)
    return namespace["on_message"]


class TeamsCustodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_delivery_failure_never_reinvokes_all_three_templates(self):
        for filename in ("bot.py", "bot-invocations.py", "bot-streaming.py"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                with patch.dict(os.environ, {"BOT_OPERATION_DIR": tmp}):
                    dispatches = []
                    async def invoke(*args):
                        dispatches.append("POST")
                        return "saved"
                    async def streaming(*args):
                        dispatches.append("POST")
                        yield TextChunk("saved")
                    async def create(**kwargs):
                        dispatches.append("POST")
                        response = SimpleNamespace(id="response-one", status="completed", error=None,
                                                   agent_session_id="session-one", output=[])
                        return events([SimpleNamespace(type="response.output_text.delta", delta="saved"),
                                       SimpleNamespace(type="response.completed", response=response)])
                    client = SimpleNamespace(
                        responses=SimpleNamespace(create=create),
                        conversations=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(id="thread-one"))),
                    )
                    activity = SimpleNamespace(text="save", id="activity-one", channel_id="teams",
                                               conversation=SimpleNamespace(id="conversation-one"))
                    context = SimpleNamespace(
                        activity=activity,
                        send_activity=AsyncMock(side_effect=[OSError("delivery lost"), None, None]),
                        streaming_response=SimpleNamespace(
                            _cancelled=True, queue_informative_update=lambda *a: None,
                            set_generated_by_ai_label=lambda *a: None, end_stream=AsyncMock(),
                        ),
                    )
                    # Cancellation courtesy consumes one send before final delivery.
                    if filename == "bot-streaming.py":
                        context.send_activity.side_effect = [None, OSError("delivery lost"), None, None]
                    state = SimpleNamespace(get_value=lambda *a, **k: "thread-one", set_value=lambda *a: None)
                    namespace = {
                        "logger": logging.getLogger("test"), "InvocationJournal": InvocationJournal,
                        "ExistingInvocation": ExistingInvocation, "oai_client": client, "credential": object(),
                        "_invoke_invocations": invoke, "_stream_invocations": streaming, "_stream_responses": streaming,
                        "_send_session_files": AsyncMock(), "_friendly_error": lambda raw: "Original result unresolved",
                        "PROJECT_ENDPOINT": "https://example.test", "AGENT_NAME": "agent", "AGENT_PROTOCOL": "invocations",
                        "TextChunk": TextChunk, "StatusUpdate": StatusUpdate, "SessionComplete": SessionComplete,
                        "TurnContext": object, "TurnState": object,
                    }
                    handler = load_handler(filename, namespace)
                    await handler(context, state)
                    await handler(context, state)
                    self.assertEqual(dispatches, ["POST"])
                    records = [json.loads(line) for line in next(Path(tmp).glob("*.jsonl")).read_text().splitlines()]
                    self.assertEqual(records[0]["event"], "intent")
                    self.assertIn("unresolved", [r["event"] for r in records])
                    self.assertNotIn("delivery lost", json.dumps(records))

    async def test_sse_error_or_truncation_never_becomes_success(self):
        journal = SimpleNamespace(record=lambda *a: None)
        for lines in (
            [b'data: {"type":"assistant.message","data":{"content":"partial"}}\n', b"\n"],
            [b'data: {"type":"error","message":"private"}\n', b"\n"],
            [b"data: not-json\n", b"\n"],
        ):
            response = SimpleNamespace(status=200, headers={}, content=events(lines))
            with self.subTest(lines=lines), self.assertRaises((RuntimeError, ValueError)):
                [event async for event in invocation_events(response, journal)]

    async def test_runtime_done_id_is_not_native_retrievable_identity(self):
        records = []
        response = SimpleNamespace(status=200, headers={}, content=events([
            b"event: done\n", b'data: {"invocation_id":"runtime-one"}\n', b"\n",
        ]))
        result = [event async for event in invocation_events(
            response, SimpleNamespace(record=lambda name, fields: records.append((name, fields))))]
        self.assertEqual(result, [])
        self.assertFalse(records[-1][1]["native_retrievable_id"])
        self.assertEqual(records[-1][1]["effect"], "UNKNOWN")

    async def test_journal_rejects_missing_or_public_directory_before_dispatch(self):
        activity = SimpleNamespace(id="one", channel_id="teams", conversation=SimpleNamespace(id="one"))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"BOT_OPERATION_DIR": tmp}):
            os.chmod(tmp, 0o755)
            with self.assertRaises(ValueError):
                InvocationJournal(activity)


if __name__ == "__main__":
    unittest.main()

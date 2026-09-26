import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import wave

from azure.ai.projects import models
from azure.ai.projects.aio.operations import AsyncBetaRealtimeConnection
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "references/python"))
from definition import Consent, build_definition, check_endpoint
from lifecycle import connect, delete_conversation, delete_empty_agent, delete_version, read_audio, read_transcript
from session import TurnCollector, VoiceServiceError, error_diagnostic, exchange, read_pcm, save_pcm, send_pcm, tool_result


def event(kind, **fields):
    classes = {
        "session.created": models.RealtimeServerEventSessionCreated,
        "input_audio_buffer.speech_started": models.RealtimeServerEventInputAudioBufferSpeechStarted,
        "input_audio_buffer.speech_stopped": models.RealtimeServerEventInputAudioBufferSpeechStopped,
        "response.created": models.RealtimeServerEventResponseCreated,
        "response.done": models.RealtimeServerEventResponseDone,
        "response.output_audio.delta": models.RealtimeServerEventResponseAudioDelta,
        "response.function_call_arguments.done": models.RealtimeServerEventResponseFunctionCallArgumentsDone,
        "response.output_audio_transcript.done": models.RealtimeServerEventResponseAudioTranscriptDone,
        "error": models.RealtimeServerEventError,
    }
    return classes[kind]({"type": kind, "event_id": "event-test", **fields})


def response(kind, rid, *, status="completed", output=None):
    return event(kind, response={"id": rid, "status": status, "output": output or []})


def delta(rid, pcm=b"\x01\x00"):
    import base64
    return event(
        "response.output_audio.delta", response_id=rid, item_id="output-" + rid,
        output_index=0, content_index=0, delta=base64.b64encode(pcm).decode(),
    )


class DefinitionTests(unittest.TestCase):
    def test_real_sdk_serialization(self):
        definition = build_definition("gpt-realtime").as_dict()
        self.assertEqual(definition["kind"], "voice")
        self.assertIs(definition["store"], False)
        self.assertNotIn("parallel_tool_calls", definition)
        self.assertEqual(definition["audio"]["input"]["format"], {"type": "audio/pcm", "rate": 24000})
        self.assertEqual(definition["audio"]["input"]["transcription"],
                         {"model": "azure-speech", "language": "en-US"})
        self.assertTrue(definition["audio"]["input"]["turn_detection"]["interrupt_response"])
        self.assertEqual(definition["audio"]["input"]["turn_detection"]["type"], "azure_semantic_vad")
        self.assertEqual(definition["audio"]["input"]["turn_detection"]["languages"], ["en-US"])
        self.assertEqual(models.VoiceAgentDefinition(definition).as_dict(), definition)

    def test_model_selection_and_consent(self):
        actual = build_definition("approved-deployment", model_type="self_deployed", consent=Consent(store=True))
        self.assertEqual(actual.model_type, "self_deployed")
        self.assertTrue(actual.store)
        for model, kind in [("", "managed"), (" x ", "managed"), ("x", "invalid")]:
            with self.assertRaises(ValueError):
                build_definition(model, model_type=kind)

    def test_no_secret_urls(self):
        endpoint = "https://example.services.ai.azure.com/api/projects/example"
        self.assertEqual(check_endpoint(endpoint + "/"), endpoint)
        for url in [endpoint + "?token=secret", endpoint + "#secret", endpoint.replace("https", "http"),
                    endpoint.replace("example.services", "user:secret@example.services"),
                    endpoint + "/extra", "https://example/api/projects/"]:
            with self.assertRaises(ValueError):
                check_endpoint(url)

    def test_tool_validation(self):
        self.assertEqual(json.loads(tool_result("get_demo_hours", "{}"))["opening_hours"], "09:00 to 17:00 UTC")
        for name, args in [("delete", "{}"), ("get_demo_hours", "[]"),
                           ("get_demo_hours", '{"extra":1}'), ("get_demo_hours", "invalid")]:
            with self.assertRaises(ValueError):
                tool_result(name, args)

    def test_wav_contract_and_capture_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.wav"
            with self.assertRaises(PermissionError):
                save_pcm(path, b"\x01\x00", Consent())
            self.assertFalse(path.exists())
            save_pcm(path, b"\x01\x00" * 240, Consent(save_local_audio=True))
            self.assertEqual(read_pcm(path), b"\x01\x00" * 240)
            with self.assertRaises(FileExistsError):
                save_pcm(path, b"\x01\x00", Consent(save_local_audio=True))
            bad = Path(directory) / "bad.wav"
            with wave.open(str(bad), "wb") as target:
                target.setnchannels(2)
                target.setsampwidth(2)
                target.setframerate(24000)
                target.writeframes(b"\x00" * 40)
            with self.assertRaises(ValueError):
                read_pcm(bad)


class LifecycleTests(unittest.TestCase):
    def test_separate_read_delete_gates(self):
        client = MagicMock()
        for function in (read_audio, read_transcript, delete_conversation, delete_version):
            with self.assertRaises(PermissionError):
                function(client, "owned-agent", "owned-id", Consent(store=True))
        self.assertEqual(client.mock_calls, [])

    def test_download_not_just_reference(self):
        client = MagicMock()
        ops = client.beta.voice_agents.conversations
        ops.get_audio.return_value = models.VoiceRecording({"blob_uri": None})
        ops.download_audio.return_value = iter([b"RIFF", b"audio"])
        self.assertEqual(read_audio(client, "agent", "conversation", Consent(read_audio=True)), b"RIFFaudio")
        ops.get_audio.return_value = models.VoiceRecording({"blob_uri": "https://storage.invalid/private"})
        with self.assertRaisesRegex(RuntimeError, "BYO"):
            read_audio(client, "agent", "conversation", Consent(read_audio=True))
        self.assertEqual(ops.download_audio.call_count, 1)

    def test_delete_requires_supported_absence(self):
        client = MagicMock()
        ops = client.beta.voice_agents.conversations
        with self.assertRaisesRegex(RuntimeError, "not been verified"):
            delete_conversation(client, "agent", "conversation", Consent(delete=True))
        ops.get.side_effect = HttpResponseError(message="unauthorized", response=None)
        with self.assertRaises(HttpResponseError):
            delete_conversation(client, "agent", "conversation", Consent(delete=True))
        ops.get.side_effect = ResourceNotFoundError(message="missing")
        delete_conversation(client, "agent", "conversation", Consent(delete=True))
        client.agents.get_version.side_effect = ResourceNotFoundError(message="missing")
        delete_version(client, "agent", "2", Consent(delete=True))
        client.agents.delete_version.assert_called_once_with("agent", "2")

    def test_version_drift_and_wrong_kind(self):
        from lifecycle import require_version
        client = MagicMock()
        latest = client.agents.get.return_value.versions.latest
        latest.version = "2"
        with self.assertRaises(RuntimeError):
            require_version(client, "agent", "1")
        latest.definition = models.PromptAgentDefinition(model="example")
        with self.assertRaises(TypeError):
            require_version(client, "agent", "2")
        latest.definition = build_definition("gpt-realtime")
        self.assertIs(require_version(client, "agent", "2"), latest.definition)

    def test_connect_explicit_store_no_version_invention(self):
        client = MagicMock()
        connect(client, "agent", "session", Consent())
        client.beta.voice_agents.realtime.connect.assert_called_once_with(
            agent_name="agent", agent_session_id="session", extra_query={"store": "false"}
        )

    def test_empty_agent_cleanup_protects_other_versions(self):
        client = MagicMock()
        with self.assertRaises(PermissionError):
            delete_empty_agent(client, "owned", Consent())
        self.assertEqual(client.mock_calls, [])
        client.agents.list_versions.return_value = [object()]
        with self.assertRaisesRegex(RuntimeError, "still has versions"):
            delete_empty_agent(client, "owned", Consent(delete=True))
        client.agents.delete.assert_not_called()
        client.agents.list_versions.return_value = []
        client.agents.get.side_effect = [object(), ResourceNotFoundError(message="missing")]
        delete_empty_agent(client, "owned", Consent(delete=True))
        client.agents.delete.assert_called_once_with(agent_name="owned")

    def test_lifecycle_signatures_exist_in_pinned_sdk(self):
        import inspect
        from azure.ai.projects import AIProjectClient
        class NeverCredential:
            def get_token(self, *args, **kwargs):
                raise AssertionError("No credential acquisition in offline test")
        with AIProjectClient(endpoint="https://example.services.ai.azure.com/api/projects/example",
                             credential=NeverCredential(), allow_preview=True) as client:
            inspect.signature(client.agents.list_versions).bind(agent_name="owned")
            inspect.signature(client.agents.delete).bind(agent_name="owned")
            inspect.signature(client.agents.delete_version).bind("owned", "1")
            inspect.signature(client.beta.voice_agents.conversations.download_audio).bind("owned", "conversation")


class EventTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.conn.conversation.item.create = AsyncMock()
        self.conn.response.create = AsyncMock()
        self.conn.input_audio_buffer.append = AsyncMock()
        self.collector = TurnCollector()

    async def accept(self, *events):
        result = False
        for item in events:
            result = await self.collector.accept(item, self.conn)
        return result

    async def test_typed_greeting_and_complete_audio_turn(self):
        await self.accept(event("session.created", session={"id": "session-1"}))
        done = await self.accept(response("response.created", "greet"), delta("greet"),
                                 response("response.done", "greet"))
        self.assertTrue(done)
        self.assertEqual(self.collector.evidence.greeting_bytes, 2)
        self.assertEqual(self.collector.evidence.completed_turns, 0)
        await self.accept(event("input_audio_buffer.speech_started", audio_start_ms=0, item_id="turn1"),
                          event("input_audio_buffer.speech_stopped", audio_end_ms=100, item_id="turn1"),
                          response("response.created", "reply"), delta("reply"),
                          response("response.done", "reply"))
        self.assertEqual(self.collector.evidence.audio, b"\x01\x00")
        self.assertEqual(self.collector.evidence.completed_turns, 1)
        self.assertEqual(len(self.collector.evidence.vad_end_to_first_audio_ms), 1)
        self.assertIsNone(self.collector.evidence.conversation_id)

    async def test_tool_waits_for_done_before_followup(self):
        await self.accept(response("response.created", "r"))
        tool = event("response.function_call_arguments.done", response_id="r", item_id="tool",
                     output_index=0, call_id="call", name="get_demo_hours", arguments="{}")
        await self.accept(tool)
        self.conn.response.create.assert_not_awaited()
        self.conn.conversation.item.create.assert_not_awaited()
        await self.accept(response("response.done", "r"))
        output = self.conn.conversation.item.create.call_args.kwargs["item"]
        self.assertEqual(output.call_id, "call")
        self.assertEqual(json.loads(output.output)["opening_hours"], "09:00 to 17:00 UTC")
        self.conn.response.create.assert_awaited_once()

    async def test_barge_in_discards_stale_audio(self):
        await self.accept(event("input_audio_buffer.speech_started", item_id="one", audio_start_ms=0),
                          response("response.created", "old"), delta("old"),
                          event("input_audio_buffer.speech_started", item_id="two", audio_start_ms=500),
                          delta("old", b"\x02\x00"), response("response.done", "old", status="cancelled"))
        self.assertEqual(self.collector.evidence.interruptions, 1)
        self.assertEqual(self.collector.evidence.audio, b"")
        await self.accept(response("response.created", "new"), delta("new", b"\x03\x00"),
                          response("response.done", "new"))
        self.assertEqual(self.collector.evidence.audio, b"\x03\x00")

    async def test_failed_empty_or_unrequested_cancel_is_not_success(self):
        for status in ("failed", "cancelled", "incomplete", "completed"):
            self.collector = TurnCollector()
            await self.accept(response("response.created", "r"))
            with self.assertRaises(RuntimeError):
                await self.accept(response("response.done", "r", status=status))

    async def test_duplicate_and_unknown_tools_fail(self):
        await self.accept(response("response.created", "r"))
        item = event("response.function_call_arguments.done", response_id="r", item_id="tool",
                     output_index=0, call_id="call", name="get_demo_hours", arguments="{}")
        await self.accept(item)
        with self.assertRaises(RuntimeError):
            await self.accept(item)
        self.conn.response.create.assert_not_awaited()

    async def test_server_errors_do_not_echo_content(self):
        with self.assertRaises(VoiceServiceError) as caught:
            await self.accept(event("error", error={
                "type": "invalid_request_error", "code": "invalid_value",
                "param": "audio.input.transcription.model", "request_id": "request-test",
                "message": "sensitive-content Bearer secret https://private.invalid/?token=secret",
            }))
        self.assertNotIn("sensitive-content", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))
        self.assertEqual(caught.exception.diagnostic, {
            "event_id": "event-test", "error_type": "invalid_request_error",
            "error_code": "invalid_value", "parameter": "audio.input.transcription.model",
            "request_id": "request-test",
        })
        self.assertEqual(self.collector.evidence.errors, [caught.exception.diagnostic])

    async def test_diagnostic_rejects_free_form_identifier_fields(self):
        diagnostic = error_diagnostic(event("error", error={
            "type": "server_error", "code": "Bearer secret", "param": "https://private.invalid",
            "request_id": "x" * 129, "message": "private",
        }))
        self.assertEqual(diagnostic, {"event_id": "event-test", "error_type": "server_error"})

    async def test_send_is_pcm_with_vad_silence_no_manual_commit(self):
        with patch("session.asyncio.sleep", new=AsyncMock()):
            await send_pcm(self.conn, b"\x01\x00" * 1200)
        chunks = [call.kwargs["audio"] for call in self.conn.input_audio_buffer.append.await_args_list]
        self.assertEqual(b"".join(chunks), b"\x01\x00" * 1200 + bytes(33600))
        self.conn.input_audio_buffer.commit.assert_not_called()
        self.conn.response.create.assert_not_awaited()

    async def test_session_timeout_is_failure(self):
        self.conn.recv = AsyncMock(side_effect=lambda: None)
        async def never():
            await asyncio.sleep(10)
        self.conn.recv.side_effect = never
        with self.assertRaises(TimeoutError):
            await exchange(self.conn, b"\x01\x00", timeout=0.001)

    async def test_real_sdk_decodes_wire_audio(self):
        import aiohttp
        socket = MagicMock()
        socket.receive = AsyncMock(return_value=aiohttp.WSMessage(
            aiohttp.WSMsgType.TEXT,
            json.dumps({"type": "response.output_audio.delta", "event_id": "e",
                        "response_id": "r", "item_id": "i", "output_index": 0,
                        "content_index": 0, "delta": "AQACAA=="}),
            "",
        ))
        connection = AsyncBetaRealtimeConnection(socket, MagicMock())
        decoded = await connection.recv()
        self.assertIsInstance(decoded, models.RealtimeServerEventResponseAudioDelta)
        self.assertEqual(decoded.delta, b"\x01\x00\x02\x00")

    async def test_real_sdk_encodes_pcm_and_function_output(self):
        socket = MagicMock()
        socket.send_str = AsyncMock()
        connection = AsyncBetaRealtimeConnection(socket, MagicMock())
        await connection.input_audio_buffer.append(audio=b"\x01\x00\x02\x00")
        sent = json.loads(socket.send_str.call_args.args[0])
        self.assertEqual(sent["type"], "input_audio_buffer.append")
        self.assertEqual(sent["audio"], "AQACAA==")
        await connection.conversation.item.create(
            item=models.RealtimeConversationItemFunctionCallOutput(call_id="c", output='{"ok":true}')
        )
        sent = json.loads(socket.send_str.call_args.args[0])
        self.assertEqual(sent["item"]["type"], "function_call_output")
        self.assertEqual(sent["item"]["call_id"], "c")

    async def test_full_exchange_orders_greeting_send_and_reply(self):
        events = [
            event("session.created", session={"id": "session"}),
            response("response.created", "g"), delta("g"), response("response.done", "g"),
            event("input_audio_buffer.speech_started", item_id="input", audio_start_ms=0),
            event("input_audio_buffer.speech_stopped", item_id="input", audio_end_ms=50),
            response("response.created", "r"), delta("r"), response("response.done", "r"),
        ]
        self.conn.recv = AsyncMock(side_effect=events)
        with patch("session.asyncio.sleep", new=AsyncMock()):
            result = await exchange(self.conn, b"\x01\x00")
        self.assertEqual(result.session_id, "session")
        self.assertEqual(result.completed_turns, 1)
        self.assertGreater(self.conn.input_audio_buffer.append.await_count, 0)

    async def test_sender_failure_cancels_receiver_instead_of_hanging(self):
        self.conn.recv = AsyncMock(side_effect=[
            response("response.created", "g"), delta("g"), response("response.done", "g"),
        ])
        original = self.conn.recv
        async def receive():
            if original.await_count < 3:
                return await original()
            await asyncio.sleep(10)
        self.conn.recv = receive
        self.conn.input_audio_buffer.append.side_effect = ConnectionResetError("synthetic failure")
        with self.assertRaises(ExceptionGroup) as caught:
            await exchange(self.conn, b"\x01\x00", timeout=1)
        self.assertIsInstance(caught.exception.exceptions[0], ConnectionResetError)

    async def test_full_barge_in_exchange_finishes_new_turn(self):
        events = [
            event("session.created", session={"id": "session"}),
            response("response.created", "g"), delta("g"), response("response.done", "g"),
            event("input_audio_buffer.speech_started", item_id="one", audio_start_ms=0),
            event("input_audio_buffer.speech_stopped", item_id="one", audio_end_ms=50),
            response("response.created", "old"), delta("old"),
            event("input_audio_buffer.speech_started", item_id="two", audio_start_ms=500),
            delta("old"), response("response.done", "old", status="cancelled"),
            event("input_audio_buffer.speech_stopped", item_id="two", audio_end_ms=550),
            response("response.created", "new"), delta("new", b"\x03\x00"),
            response("response.done", "new"),
        ]
        self.conn.recv = AsyncMock(side_effect=events)
        with patch("session.asyncio.sleep", new=AsyncMock()):
            result = await exchange(self.conn, b"\x01\x00", interruption=b"\x02\x00")
        self.assertEqual(result.interruptions, 1)
        self.assertEqual(result.completed_turns, 1)
        self.assertEqual(result.audio, b"\x03\x00")
        sent = b"".join(call.kwargs["audio"] for call in self.conn.input_audio_buffer.append.await_args_list)
        self.assertEqual(sent, b"\x01\x00" + bytes(33600) + b"\x02\x00" + bytes(33600))

    async def test_second_turn_after_response_end_is_not_barge_in(self):
        events = [
            event("session.created", session={"id": "session"}),
            response("response.created", "g"), delta("g"), response("response.done", "g"),
            event("input_audio_buffer.speech_started", item_id="one", audio_start_ms=0),
            response("response.created", "old"), delta("old"), response("response.done", "old"),
            event("input_audio_buffer.speech_started", item_id="two", audio_start_ms=500),
            response("response.created", "new"), delta("new"), response("response.done", "new"),
        ]
        self.conn.recv = AsyncMock(side_effect=events)
        with patch("session.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(ExceptionGroup) as caught:
                await exchange(self.conn, b"\x01\x00", interruption=b"\x02\x00")
        self.assertIn("No barge-in", str(caught.exception.exceptions[0]))

    async def test_cancelled_tool_response_does_not_submit_output(self):
        await self.accept(response("response.created", "r"), delta("r"),
                          event("response.function_call_arguments.done", response_id="r",
                                item_id="tool", output_index=0, call_id="call",
                                name="get_demo_hours", arguments="{}"),
                          event("input_audio_buffer.speech_started", item_id="new", audio_start_ms=1),
                          response("response.done", "r", status="cancelled"))
        self.conn.conversation.item.create.assert_not_awaited()
        self.conn.response.create.assert_not_awaited()

    async def test_only_completed_latest_turn_transcript_is_final(self):
        await self.accept(
            event("input_audio_buffer.speech_started", item_id="one", audio_start_ms=0),
            response("response.created", "old"), delta("old"),
            event("response.output_audio_transcript.done", response_id="old", item_id="old",
                  output_index=0, content_index=0, transcript="stale answer"),
            event("input_audio_buffer.speech_started", item_id="two", audio_start_ms=100),
            response("response.done", "old", status="cancelled"),
            response("response.created", "new"), delta("new"),
            event("response.output_audio_transcript.done", response_id="new", item_id="new",
                  output_index=0, content_index=0, transcript="fictional nine to five"),
            response("response.done", "new"),
        )
        self.assertEqual(self.collector.evidence.reply_transcript, "fictional nine to five")


if __name__ == "__main__":
    unittest.main()

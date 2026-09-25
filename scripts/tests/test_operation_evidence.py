"""Real OpenAI transport custody tests; no remote endpoint is contacted."""

import json
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import httpx
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/foundry-hosted-agents/references/python"))
from operation_evidence import begin_operation, capture_response, response_metadata, verified_effect


class OperationEvidenceTests(unittest.TestCase):
    def test_service_id_saved_before_application_parser_failure(self):
        records = []
        effects = []
        body = {"id": "response-one", "object": "response", "status": "completed",
                "created_at": 0, "output": [], "agent_session_id": "session-one"}
        def respond(request):
            effects.append(request.method)
            return httpx.Response(200, json=body, headers={"x-request-id": "request-one"})
        record = lambda event, data: records.append((event, data))
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            client = OpenAI(api_key="offline-test", base_url="https://example.test/v1", http_client=http, max_retries=0)
            correlation = begin_operation(record, target="https://example.test/v1", intent={"task": "save"})
            raw = client.responses.with_raw_response.create(input="save")
            response = capture_response(raw, record)
            with self.assertRaises(ValueError):
                if not response.output:
                    raise ValueError("Application parser failed")
        self.assertEqual(effects, ["POST"])
        self.assertEqual(records[0][0], "operation-intent")
        self.assertEqual(records[-1][1]["response_id"], "response-one")
        self.assertNotEqual(correlation, "response-one")
        self.assertEqual(records[-1][1]["effect"], "UNKNOWN")

    def test_malformed_body_keeps_transport_and_private_bytes_without_second_dispatch(self):
        records, captures, dispatches = [], [], []
        def respond(request):
            dispatches.append(request.method)
            return httpx.Response(202, content=b'{"id":', headers={"x-request-id": "request-one"})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            client = OpenAI(api_key="offline-test", base_url="https://example.test/v1", http_client=http, max_retries=0)
            raw = client.responses.with_raw_response.create(input="save")
            with self.assertRaises(ValueError):
                capture_response(raw, lambda event, data: records.append((event, data)), raw_capture=captures.append)
        self.assertEqual(dispatches, ["POST"])
        self.assertEqual(captures, [b'{"id":'])
        self.assertEqual(records[0][1]["request_id"], "request-one")
        self.assertEqual(records[-1][1]["classification"], "UNCERTAIN_EFFECT")

    def test_failure_to_save_intent_prevents_dispatch(self):
        def failed_sink(event, data):
            raise OSError("No durable store")
        with self.assertRaises(OSError):
            begin_operation(failed_sink, target="approved", intent={"task": "save"})

    def test_pending_completed_and_effect_are_distinct(self):
        for status in ("queued", "in_progress"):
            self.assertEqual(response_metadata({"id": "response-one", "status": status})["classification"], "PENDING_OPERATION")
        completed = response_metadata({"id": "response-one", "status": "completed"})
        self.assertEqual(completed["classification"], "COMPLETED_RESPONSE")
        self.assertEqual(completed["effect"], "UNKNOWN")
        proof = verified_effect(response_id="response-one", observed_response_id="response-one",
                                reader="result-reader", consistency="read-after-write", evidence="private-readback")
        self.assertEqual(proof["classification"], "VERIFIED_EFFECT")
        with self.assertRaises(ValueError):
            verified_effect(response_id="response-one", observed_response_id="client-correlation",
                            reader="reader", consistency="eventual", evidence="readback")

    def test_missing_id_and_generic_404_cannot_verify_effect(self):
        for body in ({}, {"status": "failed", "error": {"code": "NotFound"}},
                     {"status": "failed", "error": {"code": "Forbidden"}}):
            self.assertEqual(response_metadata(body)["effect"], "UNKNOWN")

    def test_projection_drops_payload_and_signed_identifiers(self):
        body = {"id": "https://example.test?sig=secret", "status": "failed",
                "error": {"code": "Forbidden", "message": "private payload"}}
        projection = json.dumps(response_metadata(body))
        self.assertNotIn("secret", projection)
        self.assertNotIn("private payload", projection)

    def test_ghcp_parser_does_not_replay_after_remote_effect_or_partial_stream(self):
        path = Path(__file__).resolve().parents[2] / "skills/ghcp-hosted-agents/references/invoke_agent.py"
        spec = importlib.util.spec_from_file_location("ghcp_custody_invoker", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for tail in (
            ["event: done", 'data: {"invocation_id":"runtime-one"}', ""],
            ["data: malformed-json", ""],
            [],
        ):
            effects, records = [], []
            response = MagicMock(status_code=200, headers={"x-request-id": "request-one"})
            response.iter_lines.return_value = iter([
                'data: {"type":"assistant.message","data":{"content":"saved"}}', "", *tail,
            ])
            def post(*args, **kwargs):
                effects.append("saved")
                return response
            with patch.object(module.requests, "post", side_effect=post) as dispatch:
                if tail and tail[0] == "event: done":
                    self.assertEqual(module.invoke_invocations(
                        "https://example.test/", "offline", "agent", "save",
                        record=lambda event, data: records.append((event, data))), "saved")
                else:
                    with self.assertRaises((ValueError, RuntimeError)):
                        module.invoke_invocations("https://example.test/", "offline", "agent", "save",
                                                  record=lambda event, data: records.append((event, data)))
                dispatch.assert_called_once()
                self.assertNotIn("//agents", dispatch.call_args.args[0])
            self.assertEqual(effects, ["saved"])
            response.close.assert_called_once()
            self.assertEqual(records[0][0], "operation-intent")


if __name__ == "__main__":
    unittest.main()

"""Exercise the real SDK request pipeline with in-memory responses only."""

import importlib.util
import json
import unittest
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import HttpResponseError
from azure.core.pipeline.policies import SansIOHTTPPolicy
from azure.core.pipeline.transport import HttpResponse, HttpTransport


SOURCE = Path(__file__).resolve().parents[1] / "references/creator_routine.py"
SPEC = importlib.util.spec_from_file_location("creator_routine", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SAVED = {
    "name": "owned-routine",
    "enabled": False,
    "authorization": {"identity": "creator"},
}


class OfflineCredential:
    def get_token(self, *args, **kwargs):
        raise AssertionError("Offline test attempted authentication")


class Response(HttpResponse):
    def __init__(self, request, status, payload):
        super().__init__(request, None)
        self.status_code = status
        self.headers = {"Content-Type": "application/json"}
        self._body = json.dumps(payload).encode()

    def body(self):
        return self._body

    def json(self):
        return json.loads(self._body)


class Transport(HttpTransport):
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def send(self, request, **kwargs):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("Unexpected SDK request")
        status, payload = self.responses.pop(0)
        return Response(request, status, payload)


def client(transport):
    return AIProjectClient(
        endpoint="https://example.services.ai.azure.com/api/projects/example",
        credential=OfflineCredential(),
        transport=transport,
        authentication_policy=SansIOHTTPPolicy(),
        retry_total=0,
    )


class CreatorRoutineTests(unittest.TestCase):
    def test_exact_request_header_and_readback(self):
        transport = Transport([(404, {}), (200, SAVED), (200, SAVED)])
        with client(transport) as project:
            saved = MODULE.create_creator_routine(
                project, "owned-routine", "existing-agent", "Harmless check"
            )
        self.assertEqual(saved.as_dict()["authorization"]["identity"], "creator")
        self.assertEqual([r.method for r in transport.requests], ["GET", "PUT", "GET"])
        request = transport.requests[1]
        self.assertTrue(request.url.endswith("/routines/owned-routine?api-version=v1"))
        self.assertEqual(
            json.loads(request.body),
            {
                "enabled": False,
                "authorization": {"identity": "creator"},
                "triggers": {
                    "weekday-morning": {
                        "type": "schedule", "cron_expression": "0 7 * * 1-5", "time_zone": "UTC"
                    }
                },
                "action": {
                    "type": "invoke_agent_responses_api",
                    "agent_name": "existing-agent",
                    "input": "Harmless check",
                },
            },
        )
        for request in transport.requests:
            self.assertEqual(request.headers["Foundry-Features"], "Routines=V2Preview")
            self.assertNotIn("Authorization", request.headers)

    def test_existing_routine_never_upserted(self):
        transport = Transport([(200, SAVED)])
        with client(transport) as project, self.assertRaisesRegex(ValueError, "create-only"):
            MODULE.create_creator_routine(project, "owned-routine", "agent", "check")
        self.assertEqual(len(transport.requests), 1)

    def test_access_failure_not_treated_as_absence(self):
        transport = Transport([(403, {"error": {"code": "Forbidden", "message": "denied"}})])
        with client(transport) as project, self.assertRaises(HttpResponseError):
            MODULE.create_creator_routine(project, "owned-routine", "agent", "check")
        self.assertEqual(len(transport.requests), 1)

    def test_creation_failure_propagates_without_replacement(self):
        transport = Transport([(404, {}), (400, {"error": {"code": "invalid_payload"}})])
        with client(transport) as project, self.assertRaises(HttpResponseError):
            MODULE.create_creator_routine(project, "owned-routine", "agent", "check")
        self.assertEqual(len(transport.requests), 2)

    def test_readback_must_preserve_identity_and_disabled_state(self):
        for saved in (
            {**SAVED, "authorization": {"identity": "agent"}},
            {**SAVED, "authorization": None},
            {**SAVED, "authorization": "creator"},
            {**SAVED, "enabled": True},
            {**SAVED, "name": "wrong-name"},
        ):
            transport = Transport([(404, {}), (200, SAVED), (200, saved)])
            with self.subTest(saved=saved), client(transport) as project:
                with self.assertRaisesRegex(ValueError, "inspect before retrying"):
                    MODULE.create_creator_routine(project, "owned-routine", "agent", "check")
            self.assertEqual(len(transport.requests), 3)

    def test_readback_failure_does_not_retry_creation(self):
        transport = Transport([(404, {}), (200, SAVED), (404, {})])
        with client(transport) as project, self.assertRaises(HttpResponseError):
            MODULE.create_creator_routine(project, "owned-routine", "agent", "check")
        self.assertEqual(len(transport.requests), 3)

    def test_blank_input_never_calls_service(self):
        transport = Transport([])
        with client(transport) as project, self.assertRaises(ValueError):
            MODULE.create_creator_routine(project, "owned-routine", "agent", " ")
        self.assertEqual(transport.requests, [])


if __name__ == "__main__":
    unittest.main()

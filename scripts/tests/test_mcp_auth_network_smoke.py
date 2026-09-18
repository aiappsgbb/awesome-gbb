"""Offline canonical HTTP probe tests: transports are fakes, never live targets."""

from contextlib import redirect_stdout
from email.message import Message
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts.tests.test_native_ci_preflight import AUTH_ENV, ROOT


SCRIPT = ROOT / "scripts/mcp-auth-network-smoke.py"
spec = importlib.util.spec_from_file_location("mcp_auth_network_smoke", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ENDPOINT = AUTH_ENV["MCP_AUTH_SMOKE_ENDPOINT"]
METADATA = "https://mcp.example.test/.well-known/oauth-protected-resource/mcp"


def headers(challenge=None):
    result = Message()
    if challenge is not None:
        result["WWW-Authenticate"] = challenge
    return result


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "resource": ENDPOINT,
            "authorization_servers": [AUTH_ENV["MCP_AUTH_SMOKE_ISSUER"]],
            "scopes_supported": [AUTH_ENV["MCP_AUTH_SMOKE_SCOPE"]],
        }
        self.prm_status = 200
        self.initialize_status = 401
        self.challenge = f'Bearer resource_metadata="{METADATA}"'
        self.calls = []
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.marker = Path(temporary.name) / "marker"
        self.marker.write_text("SMOKE_RESULT=PASS\n")
        self.socket_guard = patch("socket.create_connection", side_effect=AssertionError("no network"))
        self.socket_guard.start()
        self.addCleanup(self.socket_guard.stop)

    def transport(self, method, url, body=None):
        self.calls.append((method, url, body))
        self.assertNotEqual(self.marker.read_text(), "SMOKE_RESULT=PASS\n")
        if method == "GET":
            return self.prm_status, headers(), json.dumps(self.document).encode()
        return self.initialize_status, headers(self.challenge), b""

    def run_probe(self, env=None, transport=None):
        output = io.StringIO()
        with redirect_stdout(output):
            status = probe.main(AUTH_ENV if env is None else env,
                                transport=transport or self.transport, marker=self.marker)
        for value in AUTH_ENV.values():
            self.assertNotIn(value, output.getvalue())
        return status, output.getvalue(), self.marker.read_text()

    def test_success_checks_exact_targets_and_writes_byte_exact_marker(self):
        self.assertEqual(self.run_probe(), (
            0, "MCP_AUTH_NETWORK_SMOKE=PASS NETWORK_AUTH_BOUNDARY_ONLY\n",
            "SMOKE_RESULT=PASS\n",
        ))
        self.assertEqual([(call[0], call[1]) for call in self.calls],
                         [("GET", METADATA), ("POST", ENDPOINT)])
        body = json.loads(self.calls[1][2])
        self.assertEqual(body["method"], "initialize")
        self.assertEqual(body["params"]["protocolVersion"], "2025-06-18")

    def test_scoped_metadata_preserves_endpoint_path(self):
        env = {**AUTH_ENV, "MCP_AUTH_SMOKE_ENDPOINT": "https://mcp.example.test/private/mcp"}
        metadata = "https://mcp.example.test/.well-known/oauth-protected-resource/private/mcp"
        self.document["resource"] = env["MCP_AUTH_SMOKE_ENDPOINT"]
        self.challenge = f'Bearer resource_metadata="{metadata}"'
        self.assertEqual(self.run_probe(env)[0], 0)
        self.assertEqual(self.calls[0][1], metadata)

    def test_missing_or_unapproved_input_never_calls_transport(self):
        for name in AUTH_ENV:
            env = AUTH_ENV.copy()
            del env[name]
            with self.subTest(name=name):
                self.assertEqual(self.run_probe(env)[0], 1)
                self.assertEqual(self.calls, [])
        self.assertEqual(self.run_probe({**AUTH_ENV, "MCP_AUTH_NETWORK_SMOKE_APPROVED": "no"})[0], 1)
        self.assertEqual(self.calls, [])

    def test_invalid_issuer_and_scope_rejected_before_network(self):
        for name, values in (
            ("MCP_AUTH_SMOKE_ISSUER", [
                "https://login.microsoftonline.com/common/v2.0",
                AUTH_ENV["MCP_AUTH_SMOKE_ISSUER"] + "/", "https://issuer.example.test/v2.0",
            ]),
            ("MCP_AUTH_SMOKE_SCOPE", ["User.Read", "api://common/access", "api://x/access\n"]),
        ):
            for value in values:
                with self.subTest(name=name, value=value):
                    self.assertEqual(self.run_probe({**AUTH_ENV, name: value})[0], 1)
                    self.assertEqual(self.calls, [])

    def test_prm_must_match_resource_and_sole_issuer_and_scope(self):
        for name, value in list(self.document.items()):
            for wrong in (None, "", ["wrong"], value + ["extra"] if isinstance(value, list) else value + "/"):
                with self.subTest(name=name, wrong=wrong):
                    self.document[name] = wrong
                    self.calls.clear()
                    result = self.run_probe()
                    self.assertEqual(result[0], 1)
                    self.assertIn("PRM_BINDING", result[2])
                    self.assertEqual(len(self.calls), 1)
            self.document[name] = value

    def test_non_200_prm_and_non_401_initialize_fail(self):
        for status in (301, 302, 307, 401, 403, 404, 500):
            self.prm_status = status
            self.assertIn("PRM_STATUS", self.run_probe()[2])
        self.prm_status = 200
        for status in (200, 202, 204, 301, 400, 403, 404, 500):
            self.initialize_status = status
            self.assertIn("INITIALIZE_STATUS", self.run_probe()[2])

    def test_malformed_or_wrong_challenge_fails(self):
        for challenge in (
            None, "", f'Basic resource_metadata="{METADATA}"',
            f'Bearer resource_metadata={METADATA}', f'Bearer resource_metadata="{METADATA}/"',
            f'Bearer resource_metadata="{METADATA}", resource_metadata="{METADATA}"',
            f'Bearer resource_metadata="{METADATA}",',
            f'Bearer resource_metadata="{METADATA}", Basic realm="other"',
            f'Bearer realm="resource_metadata={METADATA}"',
            f'Bearer resource_metadata="{METADATA}\n"',
        ):
            with self.subTest(challenge=challenge):
                self.challenge = challenge
                self.assertIn("CHALLENGE", self.run_probe()[2])
        duplicate = headers(f'Bearer resource_metadata="{METADATA}"')
        duplicate["WWW-Authenticate"] = 'Basic realm="other"'
        with self.assertRaises(probe.ProbeError):
            probe.check_challenge(duplicate, METADATA)

    def test_challenge_can_include_standard_error_parameters(self):
        self.challenge = f'bearer error="invalid_token", resource_metadata="{METADATA}"'
        self.assertEqual(self.run_probe()[0], 0)

    def test_malformed_duplicate_oversized_json_replaces_stale_pass(self):
        for raw in (b"[]", b"{", b'{"resource":1,"resource":2}', b'{"x":NaN}', b"\xff",
                    b" " * (probe.MAX_BYTES + 1)):
            with self.subTest(raw=raw[:30]):
                result = self.run_probe(transport=lambda *args: (200, headers(), raw))
                self.assertEqual(result[0], 1)
                self.assertTrue(result[2].startswith("SMOKE_RESULT=FAIL "))

    def test_network_and_deadline_errors_are_finite_codes(self):
        for code in ("NETWORK", "TIMEOUT", "REDIRECT"):
            def fail(*_args):
                raise probe.ProbeError(code)
            self.assertIn(f"FAIL {code}", self.run_probe(transport=fail)[1])

    def test_fixture_only_invokes_canonical_probe_and_no_success_printf(self):
        fixture = (ROOT / "skills/foundry-mcp-auth/test-fixture/consumer_prompt.md").read_text()
        self.assertIn("python3 -I scripts/mcp-auth-network-smoke.py", fixture)
        self.assertNotIn("printf 'SMOKE_RESULT=PASS", fixture)
        self.assertIn("not a request to inspect, review or edit", fixture)


class TransportTests(unittest.TestCase):
    def test_transport_has_no_auth_cookies_proxy_and_is_bounded(self):
        class Response(io.BytesIO):
            code = 200
            headers = Message()

        class Opener:
            def open(self, req, *, timeout):
                self.request, self.timeout = req, timeout
                return Response(b"{}")

        opener = Opener()
        with patch.object(probe, "build_opener", return_value=opener) as build:
            probe.request("POST", ENDPOINT, b"{}")
        self.assertEqual(opener.timeout, 15)
        self.assertNotIn("Authorization", opener.request.headers)
        self.assertNotIn("Cookie", opener.request.headers)
        self.assertEqual(opener.request.headers["Accept"], "application/json, text/event-stream")
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], probe.NoRedirect)

    def test_redirect_handler_never_follows_new_target(self):
        with self.assertRaisesRegex(probe.ProbeError, "REDIRECT"):
            probe.NoRedirect().redirect_request(None, None, 302, "", Message(), "https://other.test")

    def test_http_errors_remain_status_not_network_success(self):
        error = HTTPError(ENDPOINT, 401, "private response", headers("Bearer"), io.BytesIO(b""))
        with patch.object(probe, "build_opener") as build:
            build.return_value.open.side_effect = error
            self.assertEqual(probe.request("POST", ENDPOINT, b"{}")[0], 401)
            build.return_value.open.side_effect = URLError("SECRET_PRIVATE_TARGET")
            with self.assertRaisesRegex(probe.ProbeError, "^NETWORK$"):
                probe.request("GET", ENDPOINT)


if __name__ == "__main__":
    unittest.main()

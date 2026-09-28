"""Execute the canonical fixture probe with synthetic HTTP responses only."""

from contextlib import redirect_stdout
from email.message import Message
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from uuid import UUID


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills/foundry-mcp-auth/test-fixture/consumer_prompt.md"
TEXT = FIXTURE.read_text(encoding="utf-8")
CODE = re.search(r"python3 - <<'PY'\n(.*?)\nPY", TEXT, re.S).group(1)
PROBE = {"__name__": "fixture_test"}
exec(compile(CODE, str(FIXTURE), "exec"), PROBE)


class Response(io.BytesIO):
    def __init__(self, code, body=b"", headers=None):
        super().__init__(body)
        self.code = code
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value


class AuthExecutionFixtureTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "MCP_AUTH_NETWORK_SMOKE_APPROVED": "yes",
            "MCP_AUTH_SMOKE_ENDPOINT": "https://mcp.example.test/mcp",
            "AZURE_TENANT_ID": str(UUID(int=1)),
            "MCP_AUTH_SMOKE_ISSUER": f"https://login.microsoftonline.com/{UUID(int=1)}/v2.0",
            "MCP_AUTH_SMOKE_SCOPE": f"api://{UUID(int=2)}/tools.execute",
        }
        self.metadata_url = "https://mcp.example.test/.well-known/oauth-protected-resource/mcp"
        self.metadata = {
            "resource": self.env["MCP_AUTH_SMOKE_ENDPOINT"],
            "authorization_servers": [self.env["MCP_AUTH_SMOKE_ISSUER"]],
            "scopes_supported": [self.env["MCP_AUTH_SMOKE_SCOPE"]],
        }

    def responses(self, *, status=401, metadata=None, challenge=None):
        return [
            Response(200, json.dumps(self.metadata if metadata is None else metadata).encode()),
            Response(status, headers={"WWW-Authenticate":
                     challenge or f'Bearer resource_metadata="{self.metadata_url}"'}),
        ]

    def run_probe(self, responses=(), env=None):
        opener = Mock()
        opener.open.side_effect = responses
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as output:
            marker = Path(tmp) / "marker"
            marker.write_text("SMOKE_RESULT=PASS\n")
            status = PROBE["main"](self.env if env is None else env, opener, marker)
            return status, marker.read_text(), output.getvalue(), opener

    def test_real_probe_logic_requires_metadata_and_anonymous_401(self):
        status, marker, output, opener = self.run_probe(self.responses())
        self.assertEqual((status, marker), (0, "SMOKE_RESULT=PASS\n"))
        self.assertIn("NETWORK_AUTH_BOUNDARY_ONLY", output)
        self.assertEqual(opener.open.call_count, 2)
        calls = opener.open.call_args_list
        self.assertEqual(calls[0].args[0].full_url, self.metadata_url)
        self.assertEqual(calls[1].args[0].get_method(), "POST")
        self.assertEqual(json.loads(calls[1].args[0].data)["method"], "initialize")
        for call in calls:
            self.assertEqual(call.kwargs["timeout"], 20)
            self.assertFalse(any(k.lower() == "authorization" for k in call.args[0].headers))
        self.assertNotIn(self.env["MCP_AUTH_SMOKE_ENDPOINT"], output)
        self.assertNotIn(self.env["MCP_AUTH_SMOKE_ISSUER"], output)
        self.assertNotIn(self.env["MCP_AUTH_SMOKE_SCOPE"], output)

    def test_declared_scope_is_not_derived_from_jobs_or_sample_permission(self):
        env = {**self.env, "MCP_AUTH_APP_CLIENT_ID": str(UUID(int=999))}
        status, marker, _, _ = self.run_probe(self.responses(), env=env)
        self.assertEqual((status, marker), (0, "SMOKE_RESULT=PASS\n"))
        wrong = {**self.metadata, "scopes_supported": [f"api://{UUID(int=999)}/demo.read"]}
        status, marker, _, _ = self.run_probe(self.responses(metadata=wrong), env=env)
        self.assertEqual((status, marker), (1, "SMOKE_RESULT=FAIL PRM_SCOPE_MISMATCH\n"))

    def test_malformed_expected_bindings_fail_before_network_without_disclosure(self):
        for field in ("MCP_AUTH_SMOKE_ISSUER", "MCP_AUTH_SMOKE_SCOPE"):
            status, marker, output, opener = self.run_probe(
                env={**self.env, field: "SECRET_CANARY"},
            )
            self.assertEqual(status, 1)
            self.assertTrue(marker.startswith("SMOKE_RESULT=FAIL INVALID_"))
            self.assertNotIn("SECRET_CANARY", output + marker)
            opener.open.assert_not_called()

    def test_missing_inputs_or_unapproved_gate_never_call_network(self):
        for field in self.env:
            env = self.env.copy()
            del env[field]
            with self.subTest(field=field):
                status, marker, _, opener = self.run_probe(env=env)
                self.assertEqual(status, 1)
                self.assertTrue(marker.startswith("SMOKE_RESULT=FAIL "))
                opener.open.assert_not_called()
        for approval in ("no", "YES", " yes"):
            status, _, _, opener = self.run_probe(env={**self.env, "MCP_AUTH_NETWORK_SMOKE_APPROVED": approval})
            self.assertEqual(status, 1)
            opener.open.assert_not_called()

    def test_non_401_including_success_never_passes(self):
        for code in (200, 202, 301, 400, 403, 500):
            with self.subTest(code=code):
                status, marker, _, _ = self.run_probe(self.responses(status=code))
                self.assertEqual((status, marker), (1, "SMOKE_RESULT=FAIL INITIALIZE_NOT_401\n"))

    def test_urllib_401_error_is_the_expected_anonymous_response(self):
        headers = Message()
        headers["WWW-Authenticate"] = f'Bearer resource_metadata="{self.metadata_url}"'
        response = HTTPError(self.env["MCP_AUTH_SMOKE_ENDPOINT"], 401, "Unauthorized",
                             headers, io.BytesIO(b""))
        status, marker, _, _ = self.run_probe([self.responses()[0], response])
        self.assertEqual((status, marker), (0, "SMOKE_RESULT=PASS\n"))

    def test_prm_failures_stop_before_initialize(self):
        for response in (Response(302), Response(401), Response(200, b"not json"),
                         Response(200, b"\xff"), Response(200, b"x" * 65537)):
            status, marker, _, opener = self.run_probe([response])
            self.assertEqual(status, 1)
            self.assertTrue(marker.startswith("SMOKE_RESULT=FAIL "))
            self.assertEqual(opener.open.call_count, 1)

    def test_unexpected_resource_issuer_or_scope_rejects(self):
        for field, value in (
            ("resource", "https://other.example.test/mcp"),
            ("authorization_servers", ["https://login.microsoftonline.com/common/v2.0"]),
            ("scopes_supported", ["https://graph.microsoft.com/.default"]),
        ):
            with self.subTest(field=field):
                status, _, _, opener = self.run_probe(self.responses(metadata={**self.metadata, field: value}))
                self.assertEqual(status, 1)
                self.assertEqual(opener.open.call_count, 1)

    def test_missing_wrong_or_duplicate_metadata_challenge_rejects(self):
        for challenge in ("Basic realm=test", "Bearer realm=test",
                          'Bearer resource_metadata="https://other.example.test/metadata"',
                          f'Bearer resource_metadata="{self.metadata_url}", resource_metadata="{self.metadata_url}"'):
            status, marker, _, _ = self.run_probe(self.responses(challenge=challenge))
            self.assertEqual(status, 1)
            self.assertTrue(marker.startswith("SMOKE_RESULT=FAIL CHALLENGE_"))

    def test_network_errors_are_sanitized_and_no_redirect_is_followed(self):
        status, marker, output, _ = self.run_probe(URLError("SECRET_CANARY"))
        self.assertEqual((status, marker), (1, "SMOKE_RESULT=FAIL URLError\n"))
        self.assertNotIn("SECRET_CANARY", output)
        self.assertIsNone(PROBE["NoRedirect"]().redirect_request(None, None, 302, "", {}, "https://other.example"))
        self.assertIn("build_opener(NoRedirect())", CODE)


if __name__ == "__main__":
    unittest.main()

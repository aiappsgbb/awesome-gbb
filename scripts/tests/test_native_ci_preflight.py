"""Offline native-smoke prerequisite contracts; never network or delegated E2E."""

from __future__ import annotations

import ast
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/native-ci-preflight.py"
WORKFLOW = ROOT / ".github/workflows/skill-test.yml"
AUTH = "foundry-mcp-auth"
JOBS = "foundry-mcp-aca-jobs"
AUTH_ENV = {
    "MCP_AUTH_NETWORK_SMOKE_APPROVED": "yes",
    "MCP_AUTH_SMOKE_ENDPOINT": "https://mcp.example.test/mcp",
}
JOBS_ENV = {
    "MCP_AUTH_APP_CLIENT_ID": "11111111-2222-4333-8444-555555555555",
    "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.test:443/",
    "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": "https://storage.example.test",
}
CONDITION = (
    "matrix.skill == 'foundry-mcp-auth' || "
    "matrix.skill == 'foundry-mcp-aca-jobs'"
)
SUCCESS = "NATIVE_CI_PREFLIGHT=PASS CONFIG_ONLY\n"


def secret(name: str) -> str:
    return "${{ secrets." + name + " }}"


def auth_secret(name: str) -> str:
    return "${{ matrix.skill == 'foundry-mcp-auth' && secrets." + name + " || '' }}"


class NativeCiPreflightTests(unittest.TestCase):
    def invoke(self, skill: str, values: dict[str, str], *extra: str):
        self.assertTrue(SCRIPT.is_file(), "canonical runner prerequisite gate is missing")
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), skill, *extra],
            env={"PATH": os.environ["PATH"], **values},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def assert_failure(self, result, code: str, name: str = ""):
        self.assertEqual(result.returncode, 1)
        suffix = f" {name}" if name else ""
        self.assertEqual(result.stdout, f"NATIVE_CI_PREFLIGHT=FAIL {code}{suffix}\n")
        self.assertEqual(result.stderr, "")

    def test_valid_routes_need_only_their_own_inputs(self):
        for skill, values in ((AUTH, AUTH_ENV), (JOBS, JOBS_ENV)):
            with self.subTest(skill=skill):
                result = self.invoke(skill, values)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout, SUCCESS)
                self.assertEqual(result.stderr, "")

    def test_every_absent_empty_or_whitespace_input_rejects(self):
        for skill, values in ((AUTH, AUTH_ENV), (JOBS, JOBS_ENV)):
            for name in values:
                for invalid in (None, "", " ", "\t\r\n"):
                    with self.subTest(skill=skill, name=name, invalid=invalid):
                        env = values.copy()
                        if invalid is None:
                            del env[name]
                        else:
                            env[name] = invalid
                        self.assert_failure(self.invoke(skill, env), "MISSING_ENV", name)

    def test_approval_is_literal_yes_not_inferred_from_endpoint_or_app(self):
        for approval in ("no", "true", "1", "YES", " yes", "yes ", "expired"):
            with self.subTest(approval=approval):
                self.assert_failure(
                    self.invoke(AUTH, {**AUTH_ENV, **JOBS_ENV,
                                       "MCP_AUTH_NETWORK_SMOKE_APPROVED": approval}),
                    "UNAPPROVED", "MCP_AUTH_NETWORK_SMOKE_APPROVED",
                )
        self.assert_failure(
            self.invoke(AUTH, {**JOBS_ENV, "MCP_AUTH_SMOKE_ENDPOINT": AUTH_ENV["MCP_AUTH_SMOKE_ENDPOINT"]}),
            "MISSING_ENV", "MCP_AUTH_NETWORK_SMOKE_APPROVED",
        )

    def test_malformed_https_inputs_reject_without_echo(self):
        malformed = (
            "http://host.example.test", "https://", "//host.example.test",
            "https:///host.example.test", "https://user:secret@host.example.test",
            "https://@host.example.test", "https://host.example.test?sig=SECRET",
            "https://host.example.test?", "https://host.example.test#SECRET",
            "https://host.example.test#", "https://host.example.test:invalid",
            "https://host.example.test:65536", "https://host.example.test:0",
            "https://host.example.test:", "https://[broken", "https://host example.test",
            "https://host.example.test\\private", "https://host.example.test\n",
            "\thttps://host.example.test", " https://host.example.test",
            "https://host.example.test/%0a", "https://host%2eexample.test",
            "https://-host.example.test", "https://host..example.test",
        )
        for skill, values, names in (
            (AUTH, AUTH_ENV, ("MCP_AUTH_SMOKE_ENDPOINT",)),
            (JOBS, JOBS_ENV, ("MCP_ACA_JOBS_COSMOS_ENDPOINT", "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL")),
        ):
            for name in names:
                for raw in malformed:
                    value = raw + "/mcp" if skill == AUTH else raw
                    with self.subTest(skill=skill, name=name, value=value):
                        self.assert_failure(
                            self.invoke(skill, {**values, name: value}),
                            "INVALID_ENDPOINT", name,
                        )

    def test_auth_requires_mcp_path_not_arbitrary_https_target(self):
        for path in ("", "/", "/mcp/", "/not-mcp", "/%6dcp"):
            with self.subTest(path=path):
                self.assert_failure(
                    self.invoke(AUTH, {**AUTH_ENV, "MCP_AUTH_SMOKE_ENDPOINT": "https://mcp.example.test" + path}),
                    "INVALID_ENDPOINT", "MCP_AUTH_SMOKE_ENDPOINT",
                )

    def test_jobs_endpoints_are_account_origins_not_containers_or_credentials(self):
        for name in ("MCP_ACA_JOBS_COSMOS_ENDPOINT", "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL"):
            for path in ("/container", "/dbs/example", "/mcp"):
                with self.subTest(name=name, path=path):
                    self.assert_failure(
                        self.invoke(JOBS, {**JOBS_ENV, name: "https://data.example.test" + path}),
                        "INVALID_ENDPOINT", name,
                    )

    def test_valid_url_variants_are_not_normalized_or_discovered(self):
        for endpoint in ("https://mcp.internal:8443/private/mcp", "https://[::1]:443/mcp"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    self.invoke(AUTH, {**AUTH_ENV, "MCP_AUTH_SMOKE_ENDPOINT": endpoint}).stdout,
                    SUCCESS,
                )
        for endpoint in ("https://storage.example.test/", "https://cosmos.example.test:443"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    self.invoke(JOBS, {**JOBS_ENV, "MCP_ACA_JOBS_COSMOS_ENDPOINT": endpoint}).stdout,
                    SUCCESS,
                )

    def test_jobs_client_id_requires_canonical_uuid_not_consent_or_resource_id(self):
        for value in (
            "approved", "yes", "app-id", "api://11111111-2222-4333-8444-555555555555",
            "11111111222243338444555555555555",
            "{11111111-2222-4333-8444-555555555555}",
            "/subscriptions/private/resourceGroups/private", " SECRET_CANARY ",
        ):
            with self.subTest(value=value):
                self.assert_failure(
                    self.invoke(JOBS, {**JOBS_ENV, "MCP_AUTH_APP_CLIENT_ID": value}),
                    "INVALID_IDENTIFIER", "MCP_AUTH_APP_CLIENT_ID",
                )

    def test_bad_arguments_never_echo_user_controlled_values(self):
        self.assert_failure(self.invoke("SECRET_CANARY\n::error::injected", {}), "ARGUMENTS")
        self.assert_failure(self.invoke(AUTH, AUTH_ENV, "SECRET_CANARY"), "ARGUMENTS")

    def test_script_has_only_stdlib_imports_and_validation_has_no_side_effects(self):
        self.assertTrue(SCRIPT.is_file(), "canonical runner prerequisite gate is missing")
        source = SCRIPT.read_text(encoding="utf-8")
        allowed = {"__future__", "os", "sys", "re", "ipaddress", "urllib.parse", "uuid"}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                self.assertTrue({alias.name for alias in node.names} <= allowed)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module, allowed)
        spec = importlib.util.spec_from_file_location("native_ci_preflight", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for skill, values in ((AUTH, AUTH_ENV), (JOBS, JOBS_ENV), (AUTH, {}), (JOBS, {})):
            with self.subTest(skill=skill, valid=bool(values)), ExitStack() as stack:
                for target in (
                    "subprocess.Popen", "os.system", "socket.socket",
                    "socket.getaddrinfo", "builtins.open", "os.open",
                ):
                    stack.enter_context(patch(target, side_effect=AssertionError("external side effect")))
                before = values.copy()
                output = io.StringIO()
                with redirect_stdout(output):
                    status = module.main([skill], values)
                self.assertEqual(status, 0 if values else 1)
                self.assertEqual(values, before)
                self.assertNotIn("SMOKE_RESULT", output.getvalue())
                for value in values.values():
                    self.assertNotIn(value, output.getvalue())


class NativeCiPreflightWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.steps = cls.workflow["jobs"]["copilot-cli-matrix"]["steps"]

    def gate(self):
        gates = [step for step in self.steps if step.get("id") == "native-preflight"]
        self.assertEqual(len(gates), 1, "one mandatory runner prerequisite step is required")
        return gates[0]

    def test_exact_two_leg_condition_and_early_fail_closed_order(self):
        gate = self.gate()
        self.assertEqual(gate["if"], CONDITION)
        self.assertNotIn("continue-on-error", gate)
        self.assertEqual(self.steps.index(gate), 1)
        self.assertEqual(self.steps[0]["uses"], "actions/checkout@v4")
        for index, step in enumerate(self.steps):
            if step.get("uses", "").startswith("azure/login@"):
                self.assertLess(self.steps.index(gate), index)
            if step.get("id") == "run" or step.get("name") == "Retry once on classified-transient failure":
                self.assertLess(self.steps.index(gate), index)
                self.assertNotIn("always()", step.get("if", ""))
                self.assertNotIn("failure()", step.get("if", ""))

    def test_explicit_inputs_and_initial_retry_auth_wiring_match(self):
        env = self.gate()["env"]
        self.assertEqual(env, {
            "NATIVE_SMOKE_SKILL": "${{ matrix.skill }}",
            **{name: secret(name) for name in (*AUTH_ENV, *JOBS_ENV)},
        })
        consumers = [
            step for step in self.steps
            if step.get("id") == "run"
            or step.get("name") == "Retry once on classified-transient failure"
        ]
        self.assertEqual(len(consumers), 2)
        for step in consumers:
            for name in AUTH_ENV:
                self.assertEqual(step["env"].get(name), auth_secret(name))
            for name in JOBS_ENV:
                self.assertEqual(step["env"].get(name), secret(name))

    def test_unrelated_legs_do_not_select_the_gate(self):
        condition = self.gate()["if"]
        selected = {
            clause.strip().removeprefix("matrix.skill == ").strip("'")
            for clause in condition.split("||")
        }
        self.assertEqual(selected, {AUTH, JOBS})
        deps = yaml.safe_load((ROOT / ".github/skill-deps.yml").read_text())
        for skill in deps["skills"]:
            if skill not in (AUTH, JOBS):
                self.assertNotIn(skill, selected)

    def test_actual_step_shell_blocks_invalid_and_preserves_valid_continuation(self):
        gate = self.gate()
        self.assertEqual(
            gate["run"],
            'set -euo pipefail\npython3 -I scripts/native-ci-preflight.py "$NATIVE_SMOKE_SKILL"\n',
        )
        self.assertTrue(SCRIPT.is_file(), "canonical runner prerequisite gate is missing")
        for skill, valid in ((AUTH, AUTH_ENV), (JOBS, JOBS_ENV)):
            for values in ({}, valid):
                with self.subTest(skill=skill, valid=bool(values)):
                    result = subprocess.run(
                        ["bash", "-c", gate["run"] + "printf 'CONSUMER_REACHED\\n'\n"],
                        cwd=ROOT, env={"PATH": os.environ["PATH"], "NATIVE_SMOKE_SKILL": skill, **values},
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0 if values else 1)
                    self.assertEqual("CONSUMER_REACHED" in result.stdout, bool(values))
                    self.assertEqual(result.stderr, "")
                    if values:
                        self.assertEqual(result.stdout, SUCCESS + "CONSUMER_REACHED\n")


if __name__ == "__main__":
    unittest.main()

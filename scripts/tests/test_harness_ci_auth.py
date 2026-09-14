"""Offline checks for the Harness fixture's runner-owned Azure CLI login."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills/agent-framework-harness/test-fixture/consumer_prompt.md"
SMOKE = FIXTURE.with_name("live_smoke.py")
REQUIREMENTS = FIXTURE.with_name("requirements.txt")
WORKFLOW = ROOT / ".github/workflows/skill-test.yml"
OIDC_KEYS = ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")
SMOKE_COMMAND = (
    ".scratch/agent-framework-harness-venv/bin/python "
    "skills/agent-framework-harness/test-fixture/live_smoke.py"
)


class HarnessCiAuthTests(unittest.TestCase):
    def steps(self):
        return yaml.safe_load(WORKFLOW.read_text())["jobs"]["copilot-cli-matrix"]["steps"]

    def auth_step(self):
        matches = [step for step in self.steps() if step.get("id") == "harness-auth"]
        self.assertEqual(len(matches), 1, "Harness must have one runner-owned auth setup")
        return matches[0]

    def smoke_namespace(self):
        self.assertTrue(SMOKE.is_file(), "the fixture needs a canonical executable probe")
        namespace = {"__name__": "harness_ci_smoke_test", "__file__": str(SMOKE)}
        exec(compile(SMOKE.read_text(), str(SMOKE), "exec"), namespace)
        return namespace

    def test_profile_setup_is_harness_only_before_login(self):
        steps = self.steps()
        step = self.auth_step()
        self.assertEqual(step["if"], "matrix.skill == 'agent-framework-harness'")
        self.assertNotIn("continue-on-error", step)
        self.assertEqual(steps[1]["id"], "native-preflight")
        login = next(step for step in steps if step.get("uses") == "azure/login@v2")
        self.assertLess(steps.index(step), steps.index(login))
        self.assertEqual(login["with"]["tenant-id"], "${{ secrets.AZURE_TENANT_ID }}")
        self.assertEqual(login["with"]["subscription-id"], "${{ secrets.AZURE_SUBSCRIPTION_ID }}")
        self.assertNotIn("az login", step["run"])
        self.assertNotIn("curl", step["run"])

    def test_profile_setup_is_private_unique_and_leaves_user_cache_untouched(self):
        command = self.auth_step()["run"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            user_cache = root / "home/.azure"
            user_cache.mkdir(parents=True)
            sentinel = user_cache / "preserve"
            sentinel.write_text("existing user cache")
            environment_file = root / "github-env"
            created = []
            for _ in range(2):
                environment_file.write_text("")
                result = subprocess.run(
                    ["bash", "-c", command],
                    env={
                        "PATH": os.environ["PATH"],
                        "HOME": str(user_cache.parent),
                        "RUNNER_TEMP": str(root),
                        "GITHUB_ENV": str(environment_file),
                    },
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                exported = dict(line.split("=", 1) for line in environment_file.read_text().splitlines())
                self.assertEqual(set(exported), {"AZURE_CONFIG_DIR", "AZURE_TOKEN_CREDENTIALS"})
                self.assertEqual(exported["AZURE_TOKEN_CREDENTIALS"], "AzureCliCredential")
                profile = Path(exported["AZURE_CONFIG_DIR"])
                self.assertEqual(profile.parent, root)
                self.assertEqual(stat.S_IMODE(profile.stat().st_mode), 0o700)
                self.assertEqual(list(profile.iterdir()), [])
                self.assertNotIn(str(profile), result.stdout)
                created.append(profile)
            self.assertNotEqual(*created)
            self.assertEqual(sentinel.read_text(), "existing user cache")

    def test_profile_setup_rejects_missing_runner_contract(self):
        command = self.auth_step()["run"]
        for missing in ("RUNNER_TEMP", "GITHUB_ENV"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                environment = {
                    "PATH": os.environ["PATH"],
                    "RUNNER_TEMP": str(root),
                    "GITHUB_ENV": str(root / "github-env"),
                }
                del environment[missing]
                result = subprocess.run(
                    ["bash", "-c", command], env=environment,
                    capture_output=True, text=True, timeout=10,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(missing, result.stderr)
                self.assertEqual(list(root.iterdir()), [])

    def native_step(self):
        steps = [s for s in self.steps() if s.get("id") == "harness-native"]
        self.assertEqual(len(steps), 1, "one mandatory runner-controlled execution is required")
        return steps[0]

    def test_harness_has_no_copilot_process_and_native_step_cannot_be_optional(self):
        steps = self.steps()
        native = self.native_step()
        self.assertEqual(native["if"], "matrix.skill == 'agent-framework-harness'")
        self.assertNotIn("continue-on-error", native)
        self.assertNotIn("copilot ", native["run"])
        consumer = next(s for s in steps if s.get("id") == "run")
        self.assertEqual(consumer["if"], "matrix.skill != 'agent-framework-harness'")
        retry = next(s for s in steps if s.get("id") == "agentops-retry")
        self.assertIn("steps.run.outcome == 'failure'", retry["if"])
        for name in (
            "Install Copilot CLI", "Install azd (Azure Developer CLI)",
            "Install uv", "Install awesome-gbb plugin from this checkout",
            "Get Foundry bearer token", "Resolve Foundry project context",
        ):
            step = next(s for s in steps if s.get("name") == name)
            self.assertEqual(step["if"], "matrix.skill != 'agent-framework-harness'")
        self.assertLess(steps.index(native), steps.index(consumer))

    def test_fixture_has_no_manual_token_exchange(self):
        fixture = FIXTURE.read_text()
        for forbidden in (*OIDC_KEYS, "AZURE_FEDERATED_TOKEN_FILE", "oidc-token", "curl "):
            self.assertNotIn(forbidden, fixture)
        self.assertEqual(
            [block.strip() for block in re.findall(r"```bash\n(.*?)```", fixture, re.S)],
            [SMOKE_COMMAND],
        )
        self.assertNotIn("/tmp/agent-framework-harness-venv", fixture)
        self.assertNotIn("printf", fixture)
        self.assertTrue(SMOKE.is_file())
        source = SMOKE.read_text()
        self.assertIn("from azure.identity.aio import AzureCliCredential", source)
        self.assertNotIn('tenant_id=context["AZURE_TENANT_ID"]', source)
        self.assertIn('subscription=context["AZURE_SUBSCRIPTION_ID"]', source)

    def test_actual_fixture_python_uses_scoped_login_and_one_call(self):
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                namespace = self.smoke_namespace()
                namespace["RESULT_PATH"] = Path(directory) / "result"
                namespace["EVIDENCE_PATH"] = Path(directory) / "evidence"
                installed = {
                    match[1]: match[3]
                    for line in REQUIREMENTS.read_text().splitlines()
                    if (match := re.fullmatch(r"(.+?)(~=|==)(.+)", line))
                }
                namespace["validate_runtime"] = lambda: installed.copy()
                namespace["load_context"] = lambda: {
                    "AZURE_TENANT_ID": "ci-tenant",
                    "AZURE_SUBSCRIPTION_ID": "ci-sub",
                    "FOUNDRY_PROJECT_ENDPOINT": "https://example.invalid",
                    "FOUNDRY_MODEL_DEPLOYMENT": "ci-model",
                }
                events = []
                credentials = []
                calls = []
                case = self

                class Credential:
                    def __init__(self, *, subscription):
                        case.assertEqual(subscription, "ci-sub")
                        credentials.append(self)

                    async def __aenter__(self):
                        events.append("enter")
                        return self

                    async def __aexit__(self, *_):
                        events.append("exit")

                class Session:
                    pass

                class Agent:
                    default_options = {"store": False}

                    def create_session(self):
                        return Session()

                    async def run(self, prompt, *, session):
                        calls.append(prompt)
                        case.assertIsInstance(session, Session)
                        if failure:
                            raise RuntimeError("synthetic model failure")
                        return SimpleNamespace(text="HARNESS_LIVE_OK")

                class Server:
                    pass

                def build_agent(*, credential=None, project_endpoint=None, model=None):
                    case.assertTrue(credentials, "fixture must construct the scoped CLI credential")
                    case.assertIs(credential, credentials[0])
                    case.assertEqual(project_endpoint, "https://example.invalid")
                    case.assertEqual(model, "ci-model")
                    events.append("build")
                    return Agent()

                modules = {}
                for name, attributes in {
                    "agent_framework": {"Agent": Agent, "AgentSession": Session},
                    "agent_framework_foundry_hosting": {"ResponsesHostServer": Server},
                    "azure.identity.aio": {"AzureCliCredential": Credential},
                    "hosted_harness": {"build_agent": build_agent, "build_server": lambda agent: Server()},
                    "session_recovery": {"serialize_session": lambda session: session, "restore_session": lambda session: session},
                }.items():
                    module = ModuleType(name)
                    module.__dict__.update(attributes)
                    modules[name] = module
                original_path = sys.path[:]
                try:
                    with (
                        patch.dict(sys.modules, modules),
                        redirect_stdout(io.StringIO()),
                    ):
                        if failure:
                            with self.assertRaisesRegex(RuntimeError, "synthetic model failure"):
                                namespace["main"]([])
                        else:
                            self.assertEqual(namespace["main"]([]), 0)
                finally:
                    sys.path[:] = original_path
                self.assertEqual(events, ["enter", "build", "exit"])
                self.assertEqual(calls, ["Reply with exactly HARNESS_LIVE_OK."])
                marker = namespace["RESULT_PATH"].read_bytes()
                if failure:
                    self.assertTrue(marker.startswith(b"SMOKE_RESULT=FAIL"))
                    self.assertFalse(namespace["EVIDENCE_PATH"].exists())
                else:
                    self.assertEqual(marker, b"SMOKE_RESULT=PASS\n")
                    evidence = json.loads(namespace["EVIDENCE_PATH"].read_text())
                    self.assertEqual(evidence["credential_type"], "AzureCliCredential")
                    self.assertTrue(evidence["response_marker_found"])
                    self.assertNotIn("ci-tenant", namespace["EVIDENCE_PATH"].read_text())
                    def unexpected_execution(*_):
                        self.fail("host verification must not import SDKs or invoke the model")
                    namespace["validate_runtime"] = unexpected_execution
                    namespace["run_smoke"] = unexpected_execution
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(namespace["main"](["--verify-result"]), 0)
                        for field, value in (
                            ("credential_type", "StaticTokenCredential"),
                            ("schema_version", True),
                            ("agent_run_calls", True),
                            ("runtime_prefix_matched", False),
                            ("reference_sha256", "wrong"),
                        ):
                            altered = {**evidence, field: value}
                            namespace["EVIDENCE_PATH"].write_text(json.dumps(altered))
                            self.assertEqual(namespace["main"](["--verify-result"]), 1)
                        namespace["EVIDENCE_PATH"].unlink()
                        self.assertEqual(namespace["main"](["--verify-result"]), 1)
                    self.assertEqual(namespace["RESULT_PATH"].read_bytes(), marker)

    def test_runtime_is_preinstalled_in_approved_workspace_before_login(self):
        steps = self.steps()
        matches = [s for s in steps if s.get("id") == "harness-runtime"]
        self.assertEqual(len(matches), 1)
        runtime = matches[0]
        self.assertEqual(runtime["if"], "matrix.skill == 'agent-framework-harness'")
        login = next(s for s in steps if s.get("uses") == "azure/login@v2")
        self.assertLess(steps.index(runtime), steps.index(login))
        setup = next(s for s in steps if s.get("id") == "harness-python")
        self.assertEqual(setup["uses"], "actions/setup-python@v5")
        self.assertEqual(setup["if"], runtime["if"])
        self.assertEqual(setup["with"]["python-version"], "3.12")
        self.assertLess(steps.index(setup), steps.index(runtime))
        self.assertIn("python3 -m venv --clear --copies .scratch/agent-framework-harness-venv", runtime["run"])
        self.assertIn(SMOKE_COMMAND + " --check-runtime", runtime["run"])
        self.assertNotIn("/tmp/", runtime["run"])
        self.assertTrue(REQUIREMENTS.is_file())
        pin = yaml.safe_load(
            (FIXTURE.parents[1] / "references/upstream-pin.md").read_text().split("---", 2)[1]
        )
        packages = {p["name"]: p["version"] for p in pin["packages"]}
        requirements = REQUIREMENTS.read_text().splitlines()
        self.assertEqual(len(requirements), 7)
        for requirement in requirements:
            name, operator, version = re.fullmatch(r"(.+?)(~=|==)(.+)", requirement).groups()
            self.assertEqual(version, packages[name])
            self.assertEqual(operator, "==" if "b" in version else "~=")

    def test_runtime_guard_rejects_interpreter_and_dependency_substitution(self):
        namespace = self.smoke_namespace()
        versions = {
            "agent-framework-core": "1.14.0",
            "agent-framework-foundry": "1.11.0",
            "agent-framework-foundry-hosting": "1.0.0b260813",
            "azure-ai-agentserver-core": "2.1.0b1",
            "azure-ai-agentserver-responses": "2.1.0b1",
            "azure-ai-agentserver-invocations": "1.1.0b1",
            "azure-identity": "1.25.3",
        }
        namespace["version"] = versions.__getitem__
        error = namespace["SmokeFailure"]
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory) / "venv"
            executable = venv / "bin/python"
            executable.parent.mkdir(parents=True)
            executable.write_text("owned runtime")
            external = Path(directory) / "external-python"
            external.write_text("outside runtime")
            link = venv / "bin/linked-python"
            link.symlink_to(external)
            namespace["VENV_PATH"] = venv
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(sys, "prefix", str(venv)),
                patch.object(sys, "executable", str(executable)),
            ):
                self.assertEqual(namespace["validate_runtime"](), versions)
                for invalid in ("1.19.0", "1.25.2", "1.25.3b1", "1.26.0"):
                    versions["azure-identity"] = invalid
                    with self.subTest(version=invalid), self.assertRaises(error):
                        namespace["validate_runtime"]()
                versions["azure-identity"] = "1.25.4"
                self.assertEqual(namespace["validate_runtime"](), versions)
                with patch.dict(os.environ, {"PYTHONPATH": "/tmp/alternate"}):
                    with self.assertRaises(error):
                        namespace["validate_runtime"]()
                with patch.object(sys, "prefix", "/system-python"):
                    with self.assertRaises(error):
                        namespace["validate_runtime"]()
                for wrong_executable in (external, link):
                    with self.subTest(executable=wrong_executable.name), patch.object(
                        sys, "executable", str(wrong_executable)
                    ):
                        with self.assertRaises(error):
                            namespace["validate_runtime"]()
                with patch.object(Path, "read_text", return_value=""):
                    with self.assertRaises(error):
                        namespace["validate_runtime"]()

    def test_context_requires_private_runner_profile_not_ambient_cache(self):
        namespace = self.smoke_namespace()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "harness-azure-cli.test"
            profile.mkdir(mode=0o700)
            environment = {
                **dict.fromkeys(namespace["REQUIRED_ENV"], "synthetic-value"),
                "RUNNER_TEMP": str(root),
                "AZURE_CONFIG_DIR": str(profile),
            }
            with patch.dict(os.environ, environment, clear=True):
                context = namespace["load_context"]()
                self.assertEqual(context["AZURE_CONFIG_DIR"], str(profile))
                with patch.dict(os.environ, {"AZURE_CONFIG_DIR": str(root / ".azure")}):
                    with self.assertRaises(namespace["SmokeFailure"]):
                        namespace["load_context"]()
                profile.chmod(0o755)
                with self.assertRaises(namespace["SmokeFailure"]):
                    namespace["load_context"]()

    def test_fabricated_valid_files_cannot_replace_runner_execution(self):
        command = self.native_step()["run"]
        self.assertIn("set -euo pipefail", command)
        self.assertEqual(command.count(SMOKE_COMMAND), 1)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            namespace = self.smoke_namespace()
            versions = {
                match[1]: match[3]
                for line in REQUIREMENTS.read_text().splitlines()
                if (match := re.fullmatch(r"(.+?)(~=|==)(.+)", line))
            }
            prefix = root / "agent-framework-harness"
            marker = Path(str(prefix) + "-smoke-result")
            evidence = Path(str(prefix) + "-smoke-evidence")
            marker.write_text("SMOKE_RESULT=PASS\n")
            evidence.write_text(json.dumps(namespace["execution_evidence"](versions)))
            binary = root / "bin"
            binary.mkdir()
            (binary / "git").write_text("#!/bin/sh\nexit 0\n")
            (binary / "git").chmod(0o700)
            sdk = root / "sdk-probe"
            sdk.write_text('#!/bin/sh\nprintf "called" > "$CALL_RECORD"\nexit 17\n')
            sdk.chmod(0o700)
            script = command.replace(SMOKE_COMMAND, str(sdk)).replace(
                "/tmp/agent-framework-harness", str(prefix)
            )
            result = subprocess.run(
                ["bash", "-c", script],
                env={
                    "PATH": str(binary) + os.pathsep + os.environ["PATH"],
                    "GITHUB_SHA": "synthetic-sha",
                    "CALL_RECORD": str(root / "called"),
                },
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 17, result.stdout + result.stderr)
            self.assertEqual((root / "called").read_text(), "called")
            self.assertFalse(marker.exists())
            self.assertFalse(evidence.exists())
            self.assertNotIn("HARNESS_NATIVE_RESULT=PASS", result.stdout)

    def test_native_audit_uses_runner_step_outcome_not_agent_files(self):
        audit = next(s for s in self.steps() if s.get("name", "").startswith("Post-hoc audit"))
        self.assertEqual(
            audit.get("env", {}).get("HARNESS_NATIVE_OUTCOME"),
            "${{ steps.harness-native.outcome }}",
        )
        match = re.search(
            r'if \[ "\$SKILL" = "agent-framework-harness" \]; then\n.*?\nfi',
            audit["run"], re.S,
        )
        self.assertIsNotNone(match)
        for outcome in ("success", "failure", "skipped", "cancelled", ""):
            with self.subTest(outcome=outcome):
                result = subprocess.run(
                    ["bash", "-c", match[0]],
                    env={"PATH": os.environ["PATH"], "SKILL": "agent-framework-harness",
                         "HARNESS_NATIVE_OUTCOME": outcome},
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0 if outcome == "success" else 1)


if __name__ == "__main__":
    unittest.main()

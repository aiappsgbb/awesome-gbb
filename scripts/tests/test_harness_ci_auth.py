"""Offline checks for the Harness fixture's runner-owned Azure CLI login."""

from contextlib import redirect_stdout
import io
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
WORKFLOW = ROOT / ".github/workflows/skill-test.yml"
OIDC_KEYS = ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL")


class HarnessCiAuthTests(unittest.TestCase):
    def steps(self):
        return yaml.safe_load(WORKFLOW.read_text())["jobs"]["copilot-cli-matrix"]["steps"]

    def auth_step(self):
        matches = [step for step in self.steps() if step.get("id") == "harness-auth"]
        self.assertEqual(len(matches), 1, "Harness must have one runner-owned auth setup")
        return matches[0]

    def test_profile_setup_is_harness_only_before_login(self):
        steps = self.steps()
        step = self.auth_step()
        self.assertEqual(step["if"], "matrix.skill == 'agent-framework-harness'")
        self.assertNotIn("continue-on-error", step)
        self.assertEqual(steps[1]["id"], "native-preflight")
        login = next(step for step in steps if step.get("uses") == "azure/login@v2")
        self.assertLess(steps.index(step), steps.index(login))
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

    def test_only_harness_consumer_loses_manual_oidc_inputs_in_both_attempts(self):
        consumers = [
            step for step in self.steps()
            if step.get("id") in ("run", "agentops-retry")
        ]
        self.assertEqual(len(consumers), 2)
        pattern = (
            r'if \[ "\$SKILL" = "agent-framework-harness" \]; then\n'
            r'\s+unset ACTIONS_ID_TOKEN_REQUEST_TOKEN ACTIONS_ID_TOKEN_REQUEST_URL\n'
            r'\s*fi'
        )
        for step in consumers:
            with self.subTest(step=step["id"]):
                matches = list(re.finditer(pattern, step["run"]))
                self.assertEqual(len(matches), 1, "remove manual OIDC inputs only at the Harness boundary")
                match = matches[0]
                self.assertRegex(step["run"][match.end():], r"^\s*set \+e\n\s*copilot -p")
                for skill in ("agent-framework-harness", "foundry-agentops", "foundry-routines"):
                    environment = {
                        "PATH": os.environ["PATH"], "SKILL": skill,
                        "AZURE_CONFIG_DIR": "/runner/owned-profile",
                        **dict.fromkeys(OIDC_KEYS, "synthetic-canary"),
                    }
                    code = (
                        "import os; "
                        "print(','.join('set' if name in os.environ else 'missing' "
                        f"for name in {OIDC_KEYS!r})); "
                        "assert os.environ['AZURE_CONFIG_DIR']=='/runner/owned-profile'"
                    )
                    result = subprocess.run(
                        ["bash", "-c", match[0] + '\n"$1" -c "$2"', "_", sys.executable, code],
                        env=environment, capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    expected = "missing,missing" if skill == "agent-framework-harness" else "set,set"
                    self.assertEqual(result.stdout.strip(), expected)

    def test_fixture_has_no_manual_token_exchange(self):
        fixture = FIXTURE.read_text()
        for forbidden in (*OIDC_KEYS, "AZURE_FEDERATED_TOKEN_FILE", "oidc-token", "curl "):
            self.assertNotIn(forbidden, fixture)
        self.assertIn('test -n "${AZURE_CONFIG_DIR:-}"', fixture)
        self.assertIn("from azure.identity.aio import AzureCliCredential", fixture)
        self.assertIn("build_agent(credential=credential)", fixture)
        self.assertIn('tenant_id=os.environ["AZURE_TENANT_ID"]', fixture)
        self.assertIn('subscription=os.environ["AZURE_SUBSCRIPTION_ID"]', fixture)
        self.assertIn("SMOKE_RESULT=PASS\\n", fixture)

    def test_actual_fixture_python_uses_scoped_login_and_one_call(self):
        match = re.search(
            r"/tmp/agent-framework-harness-venv/bin/python - <<'PY'\n(.*?)\nPY",
            FIXTURE.read_text(), re.S,
        )
        self.assertIsNotNone(match)
        code = compile(match[1], str(FIXTURE), "exec")

        for failure in (False, True):
            with self.subTest(failure=failure):
                events = []
                credentials = []
                calls = []
                case = self

                class Credential:
                    def __init__(self, *, tenant_id, subscription):
                        case.assertEqual((tenant_id, subscription), ("ci-tenant", "ci-sub"))
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

                def build_agent(credential=None):
                    case.assertTrue(credentials, "fixture must construct the scoped CLI credential")
                    case.assertIs(credential, credentials[0])
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
                        patch.dict(os.environ, {"AZURE_TENANT_ID": "ci-tenant", "AZURE_SUBSCRIPTION_ID": "ci-sub"}),
                        redirect_stdout(io.StringIO()),
                    ):
                        if failure:
                            with self.assertRaisesRegex(RuntimeError, "synthetic model failure"):
                                exec(code, {"__name__": "__main__"})
                        else:
                            exec(code, {"__name__": "__main__"})
                finally:
                    sys.path[:] = original_path
                self.assertEqual(events, ["enter", "build", "exit"])
                self.assertEqual(calls, ["Reply with exactly HARNESS_LIVE_OK."])


if __name__ == "__main__":
    unittest.main()

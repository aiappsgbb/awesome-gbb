#!/usr/bin/env python3
"""Contract tests for the GHCP hosted-agent GA deployment migration."""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "ghcp-hosted-agents"
WORKFLOW = ROOT / ".github" / "workflows" / "skill-test.yml"


class GhcpHostedAgentsGaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.fixture = (SKILL_DIR / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        cls.container = (SKILL_DIR / "references" / "container.py").read_text(
            encoding="utf-8"
        )
        cls.pin = (SKILL_DIR / "references" / "upstream-pin.md").read_text(
            encoding="utf-8"
        )
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_obsolete_agent_yaml_is_removed(self) -> None:
        self.assertFalse((SKILL_DIR / "references" / "agent.yaml").exists())
        self.assertTrue((SKILL_DIR / "references" / "yaml" / "azure.yaml").exists())

    def test_skill_version_and_legacy_deploy_contract(self) -> None:
        frontmatter = yaml.safe_load(self.skill.split("---")[1])
        self.assertEqual(frontmatter["metadata"]["version"], "2.0.3")
        self.assertLessEqual(len(frontmatter["description"]), 1024)
        for stale in (
            "## agent.yaml",
            "references/agent.yaml",
            "azd up",
            "azd provision",
            "remoteBuild",
            "az role assignment create",
            "2025-11-15-preview",
            "Manual account-scope assignment",
            "ACA app",
            "postdeploy hook",
        ):
            with self.subTest(stale=stale):
                self.assertNotIn(stale, self.skill)

    def test_canonical_azure_yaml_uses_unified_invocations_shape(self) -> None:
        path = SKILL_DIR / "references" / "yaml" / "azure.yaml"
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        self.assertIn(
            "Source of truth for the prose example in",
            text,
        )
        self.assertIn("§ azure.yaml (unified GA deployment)", text)
        self.assertEqual(
            data["requiredVersions"]["extensions"]["azure.ai.agents"],
            ">=1.0.0-beta.4",
        )
        self.assertEqual(
            data["services"]["ai-project"]["endpoint"],
            "${FOUNDRY_PROJECT_ENDPOINT}",
        )
        agent = data["services"]["my-agent"]
        self.assertEqual(agent["host"], "azure.ai.agent")
        self.assertEqual(agent["kind"], "hosted")
        self.assertEqual(agent["language"], "docker")
        self.assertEqual(agent["uses"], ["ai-project"])
        self.assertEqual(
            agent["protocols"],
            [{"protocol": "invocations", "version": "2.0.0"}],
        )
        self.assertEqual(
            agent["environmentVariables"],
            [
                {
                    "name": "AZURE_AI_MODEL_DEPLOYMENT_NAME",
                    "value": "${AZURE_AI_MODEL_DEPLOYMENT_NAME}",
                }
            ],
        )
        self.assertEqual(data["infra"]["provider"], "microsoft.foundry")
        self.assertNotIn("env", agent)

    def test_direct_copy_env_and_permission_contract(self) -> None:
        for name in (
            "AZURE_SUBSCRIPTION_ID",
            "FOUNDRY_PROJECT_ENDPOINT",
            "AZURE_AI_PROJECT_ID",
            "AZURE_CONTAINER_REGISTRY_ENDPOINT",
            "AZURE_AI_MODEL_DEPLOYMENT_NAME",
        ):
            self.assertIn(name, self.skill)
        self.assertIn("guided", self.skill.lower())
        self.assertIn("direct-copy", self.skill.lower())
        self.assertNotIn("az role assignment create", self.skill)
        self.assertNotIn("az role assignment create", self.fixture)

    def test_fixture_is_canonical_single_attempt_smoke(self) -> None:
        required = (
            'echo "skills/ghcp-hosted-agents/SKILL.md"',
            "never invoke `copilot` recursively",
            "rm -f",
            "AZURE_AI_PROJECT_ID=${AZURE_AI_PROJECT_ID:+set}",
            "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}",
            "AZD_EXTENSION_VERSION id=microsoft.foundry",
            "AZD_EXTENSION_VERSION id=azure.ai.agents",
            'cp "$skill_refs/yaml/azure.yaml" "$work_dir/azure.yaml"',
            "expected exactly one canonical token",
            "rendered azure.yaml differs beyond agent identifiers",
            'azd env set AZURE_SUBSCRIPTION_ID "$AZURE_SUBSCRIPTION_ID"',
            'azd env set FOUNDRY_PROJECT_ENDPOINT "$FOUNDRY_PROJECT_ENDPOINT"',
            'azd env set AZURE_AI_PROJECT_ID "$AZURE_AI_PROJECT_ID"',
            'azd env set AZURE_CONTAINER_REGISTRY_ENDPOINT "$ACR_LOGIN_SERVER"',
            "azd env get-value",
            "AZD_ENV_CONTRACT_OK",
            "AZD_DEPLOY_ATTEMPT count=1",
            "AGENT_VERSION_ACTIVE",
            "protocol=invocations/2.0.0",
            "azd ai agent invoke",
            '{"input":',
            "--output raw",
            "assistant.message",
            "assistant.message_delta",
            "SMOKE_RESULT=PASS",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)

        deploys = re.findall(
            r'^\s*azd deploy "\$agent_name" --no-prompt$',
            self.fixture,
            re.MULTILINE,
        )
        self.assertEqual(deploys, ['  azd deploy "$agent_name" --no-prompt'])
        for forbidden in (
            "azd up",
            "azd provision",
            "azd down",
            "az role assignment create",
            "az containerapp",
            "az acr repository delete",
            "2025-11-15-preview",
            "curl -",
            "| tee",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.fixture)

    def test_fixture_teardown_is_bounded_and_soft_pass(self) -> None:
        self.assertIn("azd ai agent delete", self.fixture)
        self.assertRegex(self.fixture, r"timeout\s+(?:[1-9]\d?|[12]\d{2}|300)\s")
        self.assertIn("best-effort", self.fixture.lower())
        self.assertIn(
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/ghcp-hosted-agents-smoke-result",
            self.fixture,
        )

    def test_fixture_retries_only_confirmed_sse_auth_readiness(self) -> None:
        for token in (
            "model.call_failure",
            'data.get("statusCode") == 401',
            "PermissionDenied",
            "transient_auth_error",
            "INVOKE_ATTEMPT",
            "INVOKE_TRANSIENT_AUTH",
            "sleep 15",
            "INVOKE_OK name=%s attempt=%s",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)
        self.assertIn("for attempt in 1 2 3 4 5 6", self.fixture)
        self.assertNotIn("az role assignment create", self.fixture)

    def _invoke_classifier_code(self) -> str:
        start = 'python3 - "$invoke_log" <<\'PY\'\n'
        end = "\nPY\n  envelope_status=$?"
        self.assertIn(start, self.fixture)
        self.assertIn(end, self.fixture)
        return self.fixture.split(start, 1)[1].split(end, 1)[0]

    def _classify_invoke_events(self, *events: object, raw_lines: tuple[str, ...] = ()) -> int:
        lines = [f"data: {json.dumps(event)}" for event in events]
        lines.extend(raw_lines)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as stream:
            stream.write("\n\n".join(lines))
            stream.flush()
            result = subprocess.run(
                [sys.executable, "-c", self._invoke_classifier_code(), stream.name],
                check=False,
            )
        return result.returncode

    @staticmethod
    def _exact_readiness_events() -> tuple[dict, ...]:
        return (
            {
                "type": "model.call_failure",
                "data": {
                    "statusCode": 401,
                    "errorMessage": json.dumps(
                        {
                            "code": "PermissionDenied",
                            "message": (
                                "The principal lacks the required data action "
                                "Microsoft.CognitiveServices/accounts/OpenAI/responses/write "
                                "to perform POST /openai/v1/responses operation."
                            ),
                        }
                    ),
                },
            },
            {
                "type": "model.call_failure",
                "data": {
                    "statusCode": 401,
                    "errorMessage": json.dumps(
                        {
                            "code": "PermissionDenied",
                            "message": "Principal does not have access to API/Operation.",
                        }
                    ),
                },
            },
            {
                "type": "session.info",
                "data": {"message": "Request failed (transient_auth_error). Retrying..."},
            },
            {
                "type": "error",
                "message": "Authentication failed with provider at <endpoint> (HTTP 401).",
            },
        )

    def test_invoke_classifier_requires_exact_readiness_envelope(self) -> None:
        assistant = {"type": "assistant.message", "data": {"content": "hello"}}
        unrelated_error = {"type": "error", "message": "Unrelated terminal failure"}
        provider_auth_terminal = self._exact_readiness_events()[-1]
        generic_permission = {
            "type": "model.call_failure",
            "data": {
                "statusCode": 401,
                "errorMessage": json.dumps(
                    {"code": "PermissionDenied", "message": "Generic denied"}
                ),
            },
        }

        cases = (
            ("assistant only", (assistant,), (), 0),
            ("exact readiness", self._exact_readiness_events(), (), 10),
            (
                "exact readiness then assistant",
                self._exact_readiness_events() + (assistant,),
                (),
                0,
            ),
            ("assistant plus unrelated terminal", (assistant, unrelated_error), (), 20),
            (
                "assistant plus generic permission",
                (assistant, generic_permission),
                (),
                20,
            ),
            (
                "assistant plus incomplete provider auth terminal",
                (assistant, provider_auth_terminal),
                (),
                20,
            ),
            (
                "readiness plus unrelated terminal",
                self._exact_readiness_events() + (unrelated_error,),
                (),
                20,
            ),
            ("generic permission", (generic_permission,), (), 20),
            ("malformed data", (), ("data: {not-json",), 20),
            ("non-object data", (), ("data: []",), 20),
            (
                "malformed session data",
                ({"type": "session.info", "data": [{"message": "not an object"}]},),
                (),
                20,
            ),
            (
                "malformed empty session data",
                ({"type": "session.info", "data": None}, assistant),
                (),
                20,
            ),
            (
                "assistant plus no-space malformed data",
                (assistant,),
                ("data:{not-json",),
                20,
            ),
            (
                "exact readiness without generic follow-up",
                (
                    self._exact_readiness_events()[0],
                    self._exact_readiness_events()[2],
                    self._exact_readiness_events()[3],
                ),
                (),
                10,
            ),
            (
                "reordered readiness",
                (
                    self._exact_readiness_events()[2],
                    self._exact_readiness_events()[0],
                    self._exact_readiness_events()[3],
                ),
                (),
                20,
            ),
            (
                "anchored failure after generic phase",
                (
                    self._exact_readiness_events()[0],
                    self._exact_readiness_events()[1],
                    self._exact_readiness_events()[0],
                    self._exact_readiness_events()[2],
                    self._exact_readiness_events()[3],
                ),
                (),
                20,
            ),
        )
        for name, events, raw_lines, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(
                    self._classify_invoke_events(*events, raw_lines=raw_lines),
                    expected,
                )

    def test_permission_guidance_has_only_the_exact_readiness_exception(self) -> None:
        for stale in (
            "If any step returns a permission error, that is a hard FAIL",
            "A permission error at any step (`PermissionDenied`, 403) is a hard FAIL",
        ):
            self.assertNotIn(stale, self.fixture)
        self.assertIn("exact immediate-post-active readiness envelope", self.fixture)
        self.assertIn("exact immediate-post-active readiness envelope", self.skill)
        for token in (
            "Microsoft.CognitiveServices/accounts/OpenAI/responses/write",
            "POST /openai/v1/responses",
            "Authentication failed with provider",
            "in this order",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.skill)

    def test_fixture_persists_raw_invoke_forensics(self) -> None:
        required = (
            'invoke_log="/tmp/ghcp-hosted-agents-invoke.log"',
            'rm -f "$invoke_log"',
            '>"$invoke_log" 2>&1',
            "invoke_status=$?",
            'cat "$invoke_log"',
            'python3 - "$invoke_log"',
            'payload = line[5:].lstrip()',
            "event = json.loads(payload)",
            'event_type in {"assistant.message", "assistant.message_delta"}',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)

    def test_workflow_snapshots_attempt_scoped_forensics(self) -> None:
        required = (
            'INVOKE_LOG="/tmp/${SKILL}-invoke.log"',
            'PRIMARY_EVIDENCE="/tmp/${SKILL}-primary-smoke-evidence"',
            'PRIMARY_INVOKE_LOG="/tmp/${SKILL}-primary-invoke.log"',
            'RETRY_EVIDENCE="/tmp/${SKILL}-retry-smoke-evidence"',
            'RETRY_INVOKE_LOG="/tmp/${SKILL}-retry-invoke.log"',
            'cp "$EVIDENCE" "$PRIMARY_EVIDENCE"',
            'cp "$INVOKE_LOG" "$PRIMARY_INVOKE_LOG"',
            'cp "$EVIDENCE" "$RETRY_EVIDENCE"',
            'cp "$INVOKE_LOG" "$RETRY_INVOKE_LOG"',
            "/tmp/${{ matrix.skill }}-primary-smoke-evidence",
            "/tmp/${{ matrix.skill }}-retry-smoke-evidence",
            "/tmp/${{ matrix.skill }}-primary-invoke.log",
            "/tmp/${{ matrix.skill }}-retry-invoke.log",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.workflow)

        self.assertLess(
            self.workflow.index('cp "$INVOKE_LOG" "$PRIMARY_INVOKE_LOG"'),
            self.workflow.index("# === Result evaluation"),
        )
        self.assertLess(
            self.workflow.index('cp "$INVOKE_LOG" "$RETRY_INVOKE_LOG"'),
            self.workflow.index("# Same Pattern 12 eval ladder"),
        )

    def test_container_uses_pinned_public_imports(self) -> None:
        self.assertIn(
            "from copilot import CopilotClient, PermissionHandler, ProviderConfig",
            self.container,
        )
        self.assertIn(
            "from copilot.session_events import SessionEventType",
            self.container,
        )
        self.assertNotIn("copilot.generated.session_events", self.container)
        self.assertNotIn("from copilot.session import", self.container)

    def test_upstream_pin_retires_legacy_known_issues(self) -> None:
        pin_frontmatter = yaml.safe_load(self.pin.split("---")[1])
        known = {item["id"]: item for item in pin_frontmatter["known_issues"]}
        for retired in ("KI-001", "KI-002", "KI-003", "KI-004"):
            self.assertNotIn(retired, known)
        self.assertEqual(pin_frontmatter["known_issues_count"], len(known))
        self.assertIn("22b2c89c676bddb107ea370330d6341e25ff674b", self.pin)
        self.assertIn("9efebd953104414cf58eb78098729519b184bb6b", self.pin)

    def test_dependency_and_plugin_contract(self) -> None:
        deps = yaml.safe_load((ROOT / ".github" / "skill-deps.yml").read_text())
        self.assertIn(
            "foundry-hosted-agents",
            deps["skills"]["ghcp-hosted-agents"]["depends_on"],
        )
        plugin = json.loads((ROOT / "plugin.json").read_text())
        marketplace = json.loads(
            (ROOT / ".github" / "plugin" / "marketplace.json").read_text()
        )
        self.assertEqual(plugin["version"], marketplace["metadata"]["version"])
        self.assertEqual(plugin["version"], marketplace["plugins"][0]["version"])


if __name__ == "__main__":
    unittest.main()

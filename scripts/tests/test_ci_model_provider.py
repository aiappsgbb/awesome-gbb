import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/configure-ci-model-provider.py"
SPEC = importlib.util.spec_from_file_location("ci_model_provider", SCRIPT)
PROVIDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROVIDER)


class CIModelProviderTests(unittest.TestCase):
    def environment(self, **changes):
        env = {
            "FOUNDRY_PROJECT_ENDPOINT": "https://example.services.ai.azure.com/api/projects/default",
            "COPILOT_PROVIDER_BEARER_TOKEN": "test-bearer",
            "CITADEL_CI_GATEWAY_URL": "https://example.azure-api.net",
            "CITADEL_CI_API_KEY": "test-key",
        }
        return {**env, **changes}

    def test_default_foundry_retains_project_route(self):
        values = PROVIDER.configure(self.environment())
        self.assertEqual(values["CI_EFFECTIVE_MODEL_PROVIDER"], "foundry")
        self.assertEqual(values["COPILOT_PROVIDER_MODEL_ID"], "gpt-5.4-mini")
        self.assertTrue(values["COPILOT_PROVIDER_BASE_URL"].endswith("/api/projects/default"))
        self.assertEqual(values["COPILOT_PROVIDER_BEARER_TOKEN"], "test-bearer")
        self.assertEqual(values["COPILOT_PROVIDER_API_KEY"], "")
        self.assertEqual(values["COPILOT_PROVIDER_AZURE_API_VERSION"], "")

    def test_citadel_uses_verified_versioned_route_and_clears_bearer(self):
        values = PROVIDER.configure(self.environment(CI_MODEL_PROVIDER="citadel"))
        self.assertEqual(values["COPILOT_PROVIDER_BASE_URL"], "https://example.azure-api.net")
        self.assertEqual(values["COPILOT_PROVIDER_MODEL_ID"], "gpt-6-luna")
        self.assertEqual(values["COPILOT_PROVIDER_WIRE_MODEL"], "gpt-6-luna")
        self.assertEqual(values["COPILOT_PROVIDER_WIRE_API"], "responses")
        self.assertEqual(values["COPILOT_PROVIDER_AZURE_API_VERSION"], "2025-04-01-preview")
        self.assertEqual(values["COPILOT_PROVIDER_API_KEY"], "test-key")
        self.assertEqual(values["COPILOT_PROVIDER_BEARER_TOKEN"], "")
        self.assertEqual(values["COPILOT_PROVIDER_HEADERS"], "")
        self.assertEqual(values["COPILOT_PROVIDER_API_KEY_COMMAND"], "")
        self.assertNotIn("FOUNDRY_PROJECT_ENDPOINT", values)
        self.assertNotIn("FOUNDRY_MODEL_DEPLOYMENT", values)

    def test_agentops_keeps_its_separate_foundry_auth_contract(self):
        values = PROVIDER.configure(self.environment(
            CI_MODEL_PROVIDER="citadel", CI_MODEL_PROVIDER_EXEMPTION="agentops",
        ))
        self.assertEqual(values["CI_EFFECTIVE_MODEL_PROVIDER"], "foundry")
        self.assertEqual(values["COPILOT_PROVIDER_API_KEY"], "")
        self.assertEqual(values["COPILOT_PROVIDER_BEARER_TOKEN"], "test-bearer")

    def test_unknown_route_fails_instead_of_falling_back(self):
        with self.assertRaisesRegex(ValueError, "CI_MODEL_PROVIDER"):
            PROVIDER.configure(self.environment(CI_MODEL_PROVIDER="typo"))

    def test_unknown_exemption_fails(self):
        with self.assertRaisesRegex(ValueError, "exemption"):
            PROVIDER.configure(self.environment(CI_MODEL_PROVIDER_EXEMPTION="typo"))

    def test_missing_key_fails_before_fallback(self):
        with self.assertRaisesRegex(ValueError, "CITADEL_CI_API_KEY"):
            PROVIDER.configure(self.environment(CI_MODEL_PROVIDER="citadel", CITADEL_CI_API_KEY=""))

    def test_missing_bearer_fails(self):
        with self.assertRaisesRegex(ValueError, "bearer"):
            PROVIDER.configure(self.environment(COPILOT_PROVIDER_BEARER_TOKEN=""))

    def test_credential_newlines_cannot_inject_environment(self):
        with self.assertRaisesRegex(ValueError, "single-line"):
            PROVIDER.configure(self.environment(CI_MODEL_PROVIDER="citadel", CITADEL_CI_API_KEY="test\nEVIL=yes"))

    def test_gateway_urls_are_host_only_and_https(self):
        for url in (
            "http://example.azure-api.net", "https://example.azure-api.net/openai",
            "https://example.azure-api.net?api-key=x", "https://user@example.azure-api.net",
            "https://example.azure-api.net#x", "https://example.test", "",
            "https://example.azure-api.net:444", "https://example.azure-api.net:invalid",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                PROVIDER.configure(self.environment(CI_MODEL_PROVIDER="citadel", CITADEL_CI_GATEWAY_URL=url))

    def test_project_endpoint_is_not_replaced_by_gateway(self):
        with self.assertRaisesRegex(ValueError, "Foundry project"):
            PROVIDER.configure(self.environment(FOUNDRY_PROJECT_ENDPOINT="https://example.azure-api.net"))

    def test_writer_requires_actions_without_printing_credentials(self):
        env = {**os.environ, **self.environment(), "GITHUB_ACTIONS": "false"}
        result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("test-key", result.stdout + result.stderr)
        self.assertNotIn("test-bearer", result.stdout + result.stderr)

    def test_actions_writer_masks_credentials_and_clears_old_auth(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "github-env"
            env = {
                **os.environ, **self.environment(CI_MODEL_PROVIDER="citadel"),
                "GITHUB_ACTIONS": "true", "GITHUB_ENV": str(destination),
            }
            result = subprocess.run([sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("::add-mask::test-key", result.stdout)
            self.assertNotIn("test-bearer", result.stdout)
            text = destination.read_text()
            self.assertIn("COPILOT_PROVIDER_API_KEY=test-key\n", text)
            self.assertIn("COPILOT_PROVIDER_BEARER_TOKEN=\n", text)

    def test_workflows_select_provider_before_model_consumers(self):
        for filename, job in (
            ("skill-test.yml", "copilot-cli-matrix"),
            ("copilot-cli-foundry-auth-smoke.yml", "smoke"),
        ):
            with self.subTest(workflow=filename):
                workflow = yaml.load(
                    (ROOT / ".github/workflows" / filename).read_text(),
                    Loader=yaml.BaseLoader,
                )
                steps = workflow["jobs"][job]["steps"]
                token = next(i for i, s in enumerate(steps) if s.get("name") == "Get Foundry bearer token")
                selector = next(i for i, s in enumerate(steps) if s.get("name") == "Configure Copilot model provider")
                consumer = next(i for i, s in enumerate(steps) if "copilot -p" in s.get("run", "") or "copilot -s -p" in s.get("run", ""))
                self.assertLess(token, selector)
                self.assertLess(selector, consumer)
                self.assertEqual(steps[selector]["run"], "python3 scripts/configure-ci-model-provider.py")
                if job == "copilot-cli-matrix":
                    self.assertIn("agent-framework-harness", steps[selector]["if"])
                    self.assertIn("foundry-agentops", steps[selector]["env"]["CI_MODEL_PROVIDER_EXEMPTION"])

    def test_canary_checks_both_routes_without_repository_cutover(self):
        workflow = yaml.load(
            (ROOT / ".github/workflows/copilot-cli-foundry-auth-smoke.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertEqual(
            workflow["jobs"]["smoke"]["strategy"]["matrix"]["provider"],
            ["foundry", "citadel"],
        )
        selector = next(
            s for s in workflow["jobs"]["smoke"]["steps"]
            if s.get("name") == "Configure Copilot model provider"
        )
        self.assertEqual(selector["env"]["CI_MODEL_PROVIDER"], "${{ matrix.provider }}")
        self.assertIn("scripts/configure-ci-model-provider.py", workflow["on"]["pull_request"]["paths"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Contract tests for account-scoped and project-scoped Foundry endpoints."""

from __future__ import annotations

import importlib.util
import os
import pathlib
import unittest
from unittest import mock

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
AUTH_SMOKE = ROOT / ".github/workflows/copilot-cli-foundry-auth-smoke.yml"
SKILL_TEST = ROOT / ".github/workflows/skill-test.yml"
PIN_RUNNER = ROOT / "scripts/run-pin-validation.py"
ENV_TEMPLATE = ROOT / ".env.ci.example"
CI_PREAMBLE = ROOT / ".github/ci-shared-preamble.md"
WORKFLOWS = ROOT / ".github/workflows"

ACCOUNT_SECRET = "${{ secrets.AZURE_AI_ENDPOINT }}"
PROJECT_SECRET = "${{ secrets.FOUNDRY_PROJECT_ENDPOINT }}"


def load_yaml(path: pathlib.Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def load_pin_runner():
    spec = importlib.util.spec_from_file_location(
        "run_pin_validation_endpoint_contract",
        PIN_RUNNER,
    )
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {PIN_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FoundryEndpointContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auth_smoke = load_yaml(AUTH_SMOKE)
        cls.skill_test = load_yaml(SKILL_TEST)
        cls.pin_runner = load_pin_runner()

    def test_auth_smoke_routes_copilot_to_project_endpoint(self) -> None:
        steps = self.auth_smoke["jobs"]["smoke"]["steps"]
        smoke = next(step for step in steps if step.get("name", "").startswith("Smoke test"))

        self.assertEqual(smoke["env"]["COPILOT_PROVIDER_BASE_URL"], PROJECT_SECRET)

    def test_primary_and_retry_share_split_endpoint_contract(self) -> None:
        steps = self.skill_test["jobs"]["copilot-cli-matrix"]["steps"]
        primary = next(step for step in steps if step.get("id") == "run")
        retry = next(
            step
            for step in steps
            if step.get("name") == "Retry once on classified-transient failure"
        )

        self.assertEqual(primary["env"], retry["env"])
        for step in (primary, retry):
            self.assertEqual(
                step["env"]["COPILOT_PROVIDER_BASE_URL"],
                PROJECT_SECRET,
            )
            self.assertEqual(step["env"]["AZURE_AI_ENDPOINT"], ACCOUNT_SECRET)
            self.assertEqual(
                step["env"]["FOUNDRY_PROJECT_ENDPOINT"],
                PROJECT_SECRET,
            )

    def test_project_resolution_uses_project_endpoint(self) -> None:
        steps = self.skill_test["jobs"]["copilot-cli-matrix"]["steps"]
        resolver = next(
            step for step in steps if step.get("name") == "Resolve Foundry project context"
        )

        self.assertEqual(
            resolver["env"]["FOUNDRY_PROJECT_ENDPOINT"],
            PROJECT_SECRET,
        )
        self.assertIn(
            '--project-endpoint "$FOUNDRY_PROJECT_ENDPOINT"',
            resolver["run"],
        )

    def test_pin_runner_requires_project_endpoint_and_forwards_both(self) -> None:
        self.assertEqual(
            self.pin_runner.AZURE_ENV_MAP["foundry_project"],
            "FOUNDRY_PROJECT_ENDPOINT",
        )

        endpoint_env = {
            "AZURE_AI_ENDPOINT": "account-endpoint-value",
            "FOUNDRY_PROJECT_ENDPOINT": "project-endpoint-value",
        }
        with mock.patch.dict(os.environ, endpoint_env, clear=True):
            clean_env = self.pin_runner._build_clean_env(pathlib.Path("/tmp/shims"))

        for name, value in endpoint_env.items():
            self.assertEqual(clean_env[name], value)

    def test_env_template_documents_distinct_endpoint_uses(self) -> None:
        template = ENV_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn(
            "direct Cognitive Services and FDVS account-data-plane consumers",
            template,
        )
        self.assertIn(
            "Copilot CLI provider routing and Foundry-project validation",
            template,
        )
        self.assertNotIn(
            "used for both E2E skill tests and the Copilot CLI driver",
            template,
        )

    def test_ci_preamble_keeps_protections_without_endpoint_derivation_claim(self) -> None:
        preamble = CI_PREAMBLE.read_text(encoding="utf-8")

        self.assertNotIn("FOUNDRY_PROJECT_ENDPOINT` derivation", preamble)
        self.assertIn(
            "account and project endpoint secrets are maintained independently",
            preamble,
        )
        for protected_rule in (
            "Delete the resource group **`rg-awesome-gbb-ci`**",
            "Delete or recreate **`uami-awesome-gbb-ci`**",
            "Delete or recreate **`aif-awesome-gbb-ci`**",
            "Delete the project **`default`** inside `aif-awesome-gbb-ci`",
            "Remove or modify the lock **`no-delete-shared-ci`**",
            "Remove or modify the subscription-scope policy assignment",
        ):
            self.assertIn(protected_rule, preamble)

    def test_no_workflow_routes_copilot_to_account_endpoint(self) -> None:
        stale_binding = (
            "COPILOT_PROVIDER_BASE_URL: ${{ secrets.AZURE_AI_ENDPOINT }}"
        )
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in WORKFLOWS.glob("*.yml")
            if stale_binding in path.read_text(encoding="utf-8")
        ]

        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

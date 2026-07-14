"""Tests for deterministic Foundry project resolution in CI."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "resolve-foundry-project.py"
WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/skill-test.yml"


class ResolveFoundryProjectTests(unittest.TestCase):
    def test_selects_endpoint_project_when_account_has_multiple_projects(self) -> None:
        target_id = (
            "/subscriptions/sub-test/resourceGroups/rg-test/providers/"
            "Microsoft.CognitiveServices/accounts/ci-account/projects/target"
        )
        resources = [
            {
                "id": (
                    "/subscriptions/sub-test/resourceGroups/rg-test/providers/"
                    "Microsoft.CognitiveServices/accounts/ci-account/projects/default"
                )
            },
            {"id": target_id},
        ]

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project-endpoint",
                "https://ci-account.services.ai.azure.com/api/projects/target",
                "--subscription-id",
                "sub-test",
            ],
            input=json.dumps(resources),
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), target_id)

    def test_workflow_resolves_the_configured_project_endpoint(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        resolver = next(
            step for step in steps if step.get("name") == "Resolve Foundry project context"
        )

        self.assertEqual(
            resolver["env"].get("FOUNDRY_PROJECT_ENDPOINT"),
            "${{ secrets.FOUNDRY_PROJECT_ENDPOINT }}",
        )
        self.assertIn("scripts/resolve-foundry-project.py", resolver["run"])

    def test_project_resolver_change_triggers_the_workflow(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text())
        triggers = workflow.get("on", workflow.get(True))

        self.assertIn(
            "scripts/resolve-foundry-project.py",
            triggers["pull_request"]["paths"],
        )

    def test_primary_and_retry_share_configured_project_contract(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        primary = next(step for step in steps if step.get("id") == "run")
        retry = next(
            step
            for step in steps
            if step.get("name") == "Retry once on classified-transient failure"
        )

        for step in (primary, retry):
            self.assertEqual(
                step["env"].get("FOUNDRY_PROJECT_ENDPOINT"),
                "${{ secrets.FOUNDRY_PROJECT_ENDPOINT }}",
            )
            self.assertEqual(
                step["env"].get("AZURE_AI_PROJECT_ID"),
                "${{ steps.resolve-foundry-project.outputs.project_id }}",
            )


if __name__ == "__main__":
    unittest.main()

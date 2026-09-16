"""Keep freshness regression coverage independent of Azure execution."""
from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "freshness-tests.yml"


class FreshnessWorkflowTest(unittest.TestCase):
    def load_workflow(self):
        self.assertTrue(WORKFLOW.is_file(), "freshness needs PR-side regression coverage")
        return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)

    def test_workflow_runs_on_detector_and_test_changes(self):
        workflow = self.load_workflow()
        paths = workflow["on"]["pull_request"]["paths"]
        for path in (
            "scripts/check-freshness.py",
            "scripts/upstream_policy.py",
            "scripts/validate-skills.py",
            "scripts/templates/upstream-pin.template.md",
            "scripts/tests/test_check_freshness_*.py",
            "scripts/tests/test_freshness_workflow.py",
            ".github/workflows/freshness-tests.yml",
        ):
            self.assertIn(path, paths)

    def test_workflow_is_read_only_and_runs_no_live_detector(self):
        workflow = self.load_workflow()
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["jobs"]), {"freshness-tests"})
        text = WORKFLOW.read_text()
        self.assertNotIn("secrets.", text)
        self.assertNotIn("--upsert-issues", text)
        self.assertNotIn("azure/login", text)

    def test_workflow_executes_regression_modules(self):
        workflow = self.load_workflow()
        commands = "\n".join(
            step.get("run", "")
            for step in workflow["jobs"]["freshness-tests"]["steps"]
        )
        self.assertIn("python -m unittest", commands)
        for module in (
            "scripts.tests.test_check_freshness_pkg_drift",
            "scripts.tests.test_check_freshness_issue_mode",
            "scripts.tests.test_check_freshness_outcomes",
            "scripts.tests.test_build_site_preserves_manual_freshness",
            "scripts.tests.test_freshness_workflow",
        ):
            self.assertIn(module, commands)


if __name__ == "__main__":
    unittest.main()

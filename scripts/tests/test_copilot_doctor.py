"""Run SDK-independent doctor tests in the shared catalog interpreter.

The MCP 1.x protocol tests run in their own pinned environment in skill-test.yml;
the shared job uses MCP 2.x for other skills.
"""

import importlib.util
from pathlib import Path
import unittest

import yaml


class DoctorWorkflowTests(unittest.TestCase):
    def test_protocol_suite_uses_separate_pinned_environment(self):
        repo = Path(__file__).resolve().parents[2]
        workflow = yaml.safe_load((repo / ".github/workflows/skill-test.yml").read_text())
        step = next(s for s in workflow["jobs"]["unit-tests"]["steps"]
                    if s.get("name") == "Run doctor MCP 1.x protocol tests")
        self.assertNotIn("if", step)
        self.assertFalse(step.get("continue-on-error", False))
        self.assertIn('python -m venv "$RUNNER_TEMP/doctor-tests"', step["run"])
        self.assertIn("-r skills/copilot-doctor/requirements-test.txt", step["run"])
        self.assertIn('"$RUNNER_TEMP/doctor-tests/bin/python" -m unittest discover '
                      '-s skills/copilot-doctor/tests -p test_mcp.py -v', step["run"])
        requirements = (repo / "skills/copilot-doctor/requirements-test.txt").read_text()
        self.assertIn("mcp~=1.27.1", requirements.splitlines())


def load_tests(loader, tests, pattern):
    root = Path(__file__).resolve().parents[2] / "skills/copilot-doctor/tests"
    for path in [root / "test_inventory.py"]:
        spec = importlib.util.spec_from_file_location("copilot_doctor_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests

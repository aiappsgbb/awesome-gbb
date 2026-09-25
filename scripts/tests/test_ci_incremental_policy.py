"""Incremental selection and early gates, without live Azure operations."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from scripts.tests.test_build_test_matrix import (
    _git, _init_repo, _run_changed_only, _write_deps, _write_fixture, _write_quarantine,
)


ROOT = Path(__file__).resolve().parents[2]
CANARIES = ["agent-framework-harness", "foundry-prompt-agents"]


class IncrementalSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        for name in ["alpha", "beta", *CANARIES]:
            _write_fixture(self.repo, name)
        _write_quarantine(self.repo)
        _write_deps(self.repo, {"alpha": [], "beta": ["alpha"], **{n: [] for n in CANARIES}})
        self.skill = self.repo / "skills/alpha/SKILL.md"
        self.skill.write_text(
            "---\nname: alpha\ndescription: >\n  Description\nmetadata:\n  version: \"1.0.0\"\n"
            "---\n## Instructions\nRun the canonical sample.\n"
        )
        self.workflow = {
            "on": {"pull_request": None},
            "permissions": {"contents": "read"},
            "jobs": {
                "unit-tests": {"steps": [{"run": "unit-tests"}]},
                "build-matrix": {"steps": [{"run": "select"}]},
                "copilot-cli-matrix": {
                    "needs": "build-matrix", "if": "selected",
                    "steps": [{"run": "execute"}],
                },
            },
        }
        self.workflow_path = self.repo / ".github/workflows/skill-test.yml"
        self.workflow_path.parent.mkdir()
        self.workflow_path.write_text(yaml.safe_dump(self.workflow))
        _init_repo(self.repo)
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "baseline")
        self.base = _git(self.repo, "rev-parse", "HEAD")

    def select(self):
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "change")
        return _run_changed_only(self.repo, self.base)

    def test_description_and_version_only_need_no_live_run(self):
        self.skill.write_text(self.skill.read_text().replace("Description", "Better triggers")
                              .replace("1.0.0", "1.0.1"))
        self.assertEqual(self.select(), [])

    def test_operational_body_change_keeps_downstream_coverage(self):
        self.skill.write_text(self.skill.read_text().replace("canonical", "changed"))
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_name_change_is_not_editorial(self):
        self.skill.write_text(self.skill.read_text().replace("name: alpha", "name: renamed"))
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_unknown_metadata_is_not_editorial(self):
        self.skill.write_text(self.skill.read_text().replace("metadata:", "metadata:\n  mode: changed"))
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_duplicate_yaml_keys_do_not_skip_live(self):
        self.skill.write_text(self.skill.read_text().replace("name: alpha", "name: alpha\nname: alpha"))
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_removed_skill_is_not_editorial(self):
        self.skill.unlink()
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_fixture_only_executes_direct_skill(self):
        (self.repo / "skills/alpha/test-fixture/consumer_prompt.md").write_text("updated fixture")
        self.assertEqual(self.select(), ["alpha"])

    def test_fixture_plus_body_keeps_downstream(self):
        (self.repo / "skills/alpha/test-fixture/consumer_prompt.md").write_text("updated fixture")
        self.skill.write_text(self.skill.read_text() + "\nNew behavior\n")
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_local_tests_do_not_trigger_azure(self):
        tests = self.repo / "skills/alpha/tests"
        tests.mkdir()
        (tests / "test_local.py").write_text("pass\n")
        self.assertEqual(self.select(), [])

    def test_test_directory_runtime_requirements_remain_operational(self):
        tests = self.repo / "skills/alpha/tests"
        tests.mkdir()
        (tests / "requirements-management.txt").write_text("sdk~=2.0.0\n")
        self.assertEqual(self.select(), ["alpha", "beta"])

    def test_readme_is_conservative_because_it_can_be_operational(self):
        (self.repo / "skills/alpha/README.md").write_text("Change the deployment procedure")
        self.assertEqual(self.select(), ["alpha", "beta"])

    def write_workflow(self):
        self.workflow_path.write_text(yaml.safe_dump(self.workflow))

    def test_routing_changes_run_canaries(self):
        self.workflow["on"]["push"] = {"branches": ["main"]}
        self.write_workflow()
        self.assertEqual(self.select(), CANARIES)

    def test_selection_changes_run_canaries(self):
        self.workflow["jobs"]["build-matrix"]["steps"] = [{"run": "new selector"}]
        self.write_workflow()
        self.assertEqual(self.select(), CANARIES)

    def test_preflight_and_local_gate_wiring_run_canaries(self):
        self.workflow["jobs"]["driver-preflight"] = {"steps": [{"run": "probe"}]}
        self.workflow["jobs"]["copilot-cli-matrix"]["needs"] = [
            "build-matrix", "unit-tests", "driver-preflight",
        ]
        self.write_workflow()
        self.assertEqual(self.select(), CANARIES)

    def test_runtime_execution_change_still_runs_full(self):
        self.workflow["jobs"]["copilot-cli-matrix"]["steps"] = [{"run": "changed invoke"}]
        self.write_workflow()
        self.assertEqual(self.select(), sorted(["alpha", "beta", *CANARIES]))

    def test_shared_credentials_change_still_runs_full(self):
        self.workflow["permissions"] = {"id-token": "write"}
        self.write_workflow()
        self.assertEqual(self.select(), sorted(["alpha", "beta", *CANARIES]))

    def test_canaries_union_with_operational_changes(self):
        self.workflow["jobs"]["build-matrix"]["steps"] = [{"run": "new selector"}]
        self.write_workflow()
        self.skill.write_text(self.skill.read_text() + "New behavior\n")
        self.assertEqual(self.select(), sorted(["alpha", "beta", *CANARIES]))

    def test_missing_canary_does_not_silently_shrink_selection(self):
        self.workflow["jobs"]["build-matrix"]["steps"] = [{"run": "new selector"}]
        self.write_workflow()
        (self.repo / "skills/agent-framework-harness/test-fixture/consumer_prompt.md").unlink()
        self.assertEqual(self.select(), ["alpha", "beta", "foundry-prompt-agents"])


class WorkflowGateTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load((ROOT / ".github/workflows/skill-test.yml").read_text(),
                                  Loader=yaml.BaseLoader)

    def test_all_prs_report_tests_and_aggregate_without_path_deadlock(self):
        self.assertNotIsInstance(self.workflow["on"]["pull_request"], dict)

    def test_push_uses_full_event_range_not_head_parent(self):
        step = next(s for s in self.workflow["jobs"]["build-matrix"]["steps"] if s.get("id") == "build")
        self.assertEqual(step["env"]["PUSH_BEFORE"], "${{ github.event.before }}")
        self.assertIn('--base-ref "$PUSH_BEFORE"', step["run"])
        self.assertIn('git cat-file -e "$PUSH_BEFORE^{commit}"', step["run"])
        self.assertNotIn("HEAD~1", step["run"])

    def test_live_work_depends_on_local_checks_and_driver(self):
        job = self.workflow["jobs"]["copilot-cli-matrix"]
        for name in ("unit-tests", "catalog-lint", "delegated-auth-local", "driver-preflight"):
            self.assertIn(name, job["needs"])
            self.assertIn(f"needs.{name}.result", job["if"])
        self.assertIn("!cancelled()", job["if"])

    def test_all_driver_probes_and_consumer_use_same_cli_pin(self):
        jobs = self.workflow["jobs"]
        auth = yaml.safe_load((ROOT / ".github/workflows/copilot-cli-foundry-auth-smoke.yml").read_text())
        for job in (jobs["driver-preflight"], jobs["copilot-cli-matrix"], auth["jobs"]["smoke"]):
            install = next(s["run"] for s in job["steps"] if s.get("name") == "Install Copilot CLI")
            self.assertIn("@github/copilot@1.0.57-3", install)

    def test_provider_plan_handles_native_only_and_agentops_exemption(self):
        step = next(s for s in self.workflow["jobs"]["build-matrix"]["steps"] if s.get("id") == "build")
        source = step["run"].split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        for skills, provider, expected in (
            ([], "foundry", []),
            (["agent-framework-harness"], "foundry", []),
            (["foundry-prompt-agents"], "citadel", ["citadel"]),
            (["foundry-agentops", "foundry-prompt-agents"], "citadel", ["citadel", "foundry"]),
        ):
            with self.subTest(skills=skills), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "output"
                subprocess.run([sys.executable, "-c", source], check=True, env={
                    "MATRIX_JSON": json.dumps({"skill": skills}),
                    "CI_MODEL_PROVIDER": provider, "GITHUB_OUTPUT": str(output),
                })
                self.assertEqual(json.loads(output.read_text().split("=", 1)[1]),
                                 {"provider": expected})

    def test_aggregate_never_hides_failed_or_skipped_local_gates(self):
        guard = self.workflow["jobs"]["smoke-result"]
        script = guard["steps"][0]["run"]
        for job in ("build-matrix", "unit-tests", "catalog-lint", "delegated-auth-local"):
            for status in ("failure", "skipped", "cancelled"):
                with self.subTest(job=job, status=status):
                    results = {name: {"result": "success"} for name in guard["needs"]}
                    results[job] = {"result": status}
                    run = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                                         env={"MATRIX_JSON": '{"skill":[]}', "CONSUMER_RESULT": "skipped",
                                              "LOCAL_RESULTS": json.dumps(results),
                                              "PATH": os.environ["PATH"]})
                    self.assertEqual(run.returncode, 1)
                    self.assertEqual(run.stdout, "SMOKE_GUARD=FAIL LOCAL_OR_SELECTION_FAILURE\n")

    def test_aggregate_reports_driver_failure_without_claiming_skill_failure(self):
        guard = self.workflow["jobs"]["smoke-result"]
        results = {name: {"result": "success"} for name in guard["needs"]}
        results["driver-preflight"] = {"result": "failure"}
        run = subprocess.run(["bash", "-c", guard["steps"][0]["run"]],
                             capture_output=True, text=True,
                             env={"MATRIX_JSON": '{"skill":["foundry-prompt-agents"]}',
                                  "CONSUMER_RESULT": "skipped", "LOCAL_RESULTS": json.dumps(results),
                                  "PATH": os.environ["PATH"]})
        self.assertEqual(run.returncode, 1)
        self.assertEqual(run.stdout, "SMOKE_GUARD=FAIL DRIVER_UNAVAILABLE\n")


if __name__ == "__main__":
    unittest.main()

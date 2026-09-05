"""Offline delivery/privacy tests. All fixtures are synthetic; no Azure calls."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[2]
REPORTER = ROOT / "scripts/agentops-ci-report.py"
WORKFLOW = ROOT / ".github/workflows/skill-test.yml"
FIXTURE = ROOT / "skills/foundry-agentops/test-fixture/consumer_prompt.md"
CANARY = "PRIVATE_CANARY_do_not_publish_123"
LEGACY_NAMES = (
    "foundry-agentops-transcript.log", "foundry-agentops-retry.log",
    "foundry-agentops-smoke-evidence", "foundry-agentops-primary-smoke-evidence",
    "foundry-agentops-retry-smoke-evidence", "foundry-agentops-invoke.log",
    "foundry-agentops-primary-invoke.log", "foundry-agentops-retry-invoke.log",
    "foundry-agentops-smoke-result",
)
spec = importlib.util.spec_from_file_location(
    "native_contract_fixtures", ROOT / "scripts/tests/test_foundry_agentops_contract.py")
native_fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_fixtures)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.scratch = ROOT / ".artifacts" / ("ci-delivery-" + uuid.uuid4().hex)
        self.scratch.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, self.scratch)
        self.env = {
            "PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1",
            "RUNNER_TEMP": str(self.scratch), "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKSPACE": str(ROOT),
        }
        self.private = self.scratch / "agentops-ci-123-1"
        self.public = self.scratch / "agentops-ci-public-123-1"
        self.legacy = self.scratch / "legacy-compat"
        self.legacy.mkdir(mode=0o700)
        reporter_spec = importlib.util.spec_from_file_location("delivery_cleanup_test", REPORTER)
        self.reporter = importlib.util.module_from_spec(reporter_spec)
        reporter_spec.loader.exec_module(self.reporter)

    def cli(self, *args):
        if args == ("cleanup",):
            # Exercise the real entrypoint/filesystem operations, substituting
            # only the fixed legacy directory. Never inspect or mutate host /tmp.
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, self.env, clear=True), \
                    patch.object(sys, "argv", [str(REPORTER), *args]), \
                    patch.object(self.reporter, "LEGACY_DIRECTORY", self.legacy, create=True), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status = self.reporter.main()
            result = subprocess.CompletedProcess(args, status, stdout.getvalue(), stderr.getvalue())
        else:
            result = subprocess.run([sys.executable, str(REPORTER), *args],
                                    env=self.env, text=True, capture_output=True)
        self.assertNotIn(CANARY, result.stdout + result.stderr)
        return result

    def start(self):
        self.assertTrue(REPORTER.is_file(), "Missing host-side AgentOps delivery boundary")
        self.assertEqual(self.cli("init").returncode, 0)
        self.assertEqual(self.cli("prepare", "primary").returncode, 0)
        self.attempt = self.private / "attempts/primary"

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(value)
        path.chmod(0o600)

    def seed(self, *, failed_quality=False, critical=0):
        self.start()
        key = uuid.uuid4().hex
        self.workspace = self.private / "workspaces" / key
        self.workspace.mkdir(parents=True, mode=0o700)
        self.write(self.attempt / "workspace-pointer", key + "\n")
        eval_fixture = native_fixtures.FoundryAgentOpsEvalResultTests()
        eval_fixture.dataset = self.workspace / ".agentops/data/smoke.jsonl"
        result = eval_fixture.valid_result()
        result["rows"][0]["response"] = CANARY
        result["extra"] = {"secret": CANARY}
        if failed_quality:
            result["rows"][0]["metrics"][2]["value"] = 2.0
            result["aggregate_metrics"]["similarity"] = 2.0
            result["thresholds"][2].update(actual="2", passed=False)
            result["summary"].update(thresholds_passed=4, threshold_pass_rate=0.8,
                                     overall_passed=False)
        doctor_fixture = native_fixtures.FoundryAgentOpsDoctorContractTests()
        doctor_fixture.workspace = self.workspace
        doctor_fixture.agent = eval_fixture.AGENT
        doctor_fixture.version = eval_fixture.AGENT_VERSION
        doctor_fixture.start = "2026-09-05T00:00:00+00:00"
        doctor_fixture.end = "2026-09-05T00:01:00+00:00"
        doctor_fixture.sources = ["results_history", "azure_monitor", "foundry_control", "azure_resources"]
        evidence, history = doctor_fixture.evidence(critical)
        evidence["warnings"] = [CANARY]
        history["findings"][0]["summary"] = CANARY
        self.results = self.workspace / ".agentops/results/latest/results.json"
        self.evidence = self.workspace / ".agentops/release/latest/evidence.json"
        for path, value in (
            ("agent-identity.json", json.dumps({"name": eval_fixture.AGENT, "version": eval_fixture.AGENT_VERSION})),
            (".agentops/data/smoke.jsonl", json.dumps(eval_fixture.SEED)),
            (".agentops/analyze.json", '{"version":1}'),
            (".agentops/analyze-exit-code", "0"),
            (".agentops/results/latest/results.json", json.dumps(result)),
            (".agentops/results/eval-exit-code", "2" if failed_quality else "0"),
            (".agentops/release/latest/evidence.json", json.dumps(evidence)),
            (".agentops/agent/history.jsonl", json.dumps(history)),
            (".agentops/agent/doctor-exit-code", "2" if critical else "0"),
            (".agentops/agent/doctor-started-at", doctor_fixture.start),
            (".agentops/agent/doctor-finished-at", doctor_fixture.end),
        ):
            self.write(self.workspace / path, value + "\n")
        self.write(self.attempt / "marker", "SMOKE_RESULT=PASS\n")
        self.write(self.attempt / "transcript.log", "skills/foundry-agentops/SKILL.md\n" + CANARY)

    def report(self, status="0"):
        completed = self.cli("report", "primary", status)
        summary_path = self.public / "primary.json"
        self.assertTrue(summary_path.is_file(), completed.stdout + completed.stderr)
        raw = summary_path.read_text()
        self.assertNotIn(CANARY, raw)
        self.assertNotIn(str(self.workspace), raw)
        self.assertNotIn("ci-smoke-agentops-pa-offline", raw)
        return completed, json.loads(raw)

    def test_init_is_private_fresh_and_scoped(self):
        self.start()
        for relative in ("", "azure", "azd", "attempts/primary", "workspaces"):
            self.assertEqual((self.private / relative).stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.attempt / "transcript.log").stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(self.cli("init").returncode, 0)

    def test_quality_failure_and_doctor_blocked_are_not_ready(self):
        self.seed(failed_quality=True, critical=1)
        completed, summary = self.report()
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(summary["execution_checks"], {"analyze": "verified", "eval": "verified", "doctor": "verified"})
        self.assertEqual(summary["native_exit_codes"], {"eval": 2, "doctor": 2})
        self.assertEqual(summary["quality"], {"passed": False, "thresholds_passed": 4, "thresholds_total": 5})
        self.assertEqual(summary["doctor"]["readiness"], "blocked")
        self.assertEqual(summary["coverage"]["fresh_ingestion"], "unverified")
        self.assertEqual(summary["coverage"]["multi_turn"], "unverified")
        self.assertEqual(set(summary["metrics"]), {"coherence", "fluency", "similarity", "response_completeness", "avg_latency_seconds"})
        self.assertTrue(all(re.fullmatch("[0-9a-f]{64}", x) for x in summary["sha256"].values()))

    def test_marker_is_required_but_never_sufficient(self):
        for marker in ("", "SMOKE_RESULT=PASS", "SMOKE_RESULT=PASS\nextra\n",
                       "SMOKE_RESULT=FAIL " + CANARY + "\nSMOKE_RESULT=PASS\n"):
            with self.subTest(marker=marker):
                self.seed()
                self.write(self.attempt / "marker", marker)
                result, summary = self.report()
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(summary["delivery"], "failed")
                shutil.rmtree(self.private)
                shutil.rmtree(self.public)

    def test_green_marker_does_not_hide_native_execution_error(self):
        self.seed()
        result = json.loads(self.results.read_text())
        result["rows"][0]["error"] = CANARY
        self.write(self.results, json.dumps(result))
        completed, summary = self.report()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(summary["execution_checks"]["eval"], "failed")
        self.assertNotIn("metrics", summary)

    def test_orchestration_failure_retains_native_outcomes_and_prevents_replay(self):
        self.seed(failed_quality=True, critical=1)
        completed, summary = self.report("1")
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(summary["quality"]["thresholds_passed"], 4)
        self.assertEqual(summary["doctor"]["readiness"], "blocked")
        self.assertNotEqual(self.cli("retry-allowed").returncode, 0)

    def test_early_retry_does_not_overwrite_primary(self):
        self.start()
        self.assertEqual(self.cli("retry-allowed").returncode, 0)
        self.assertEqual(self.cli("prepare", "retry").returncode, 0)
        self.assertTrue((self.private / "attempts/primary/transcript.log").exists())
        self.assertTrue((self.private / "attempts/retry/transcript.log").exists())
        self.assertNotEqual(self.cli("prepare", "retry").returncode, 0)

    def test_unknown_public_enum_is_rejected(self):
        self.seed()
        evidence = json.loads(self.evidence.read_text())
        evidence["official_eval"]["status"] = CANARY
        self.write(self.evidence, json.dumps(evidence))
        completed, summary = self.report()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(summary["execution_checks"]["doctor"], "failed")

    def test_untrusted_identity_is_not_derived_from_results(self):
        self.seed()
        self.write(self.workspace / "agent-identity.json", '{"name":"different","version":"1"}')
        completed, _ = self.report()
        self.assertNotEqual(completed.returncode, 0)

    def test_missing_evidence_fails_closed(self):
        self.seed()
        self.evidence.unlink()
        completed, _ = self.report()
        self.assertNotEqual(completed.returncode, 0)

    def test_analyze_nonzero_is_not_execution_success(self):
        self.seed()
        self.write(self.workspace / ".agentops/analyze-exit-code", "1\n")
        completed, summary = self.report()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(summary["execution_checks"]["analyze"], "failed")

    def test_hardlinked_or_world_readable_artifacts_fail_closed(self):
        for kind in ("hardlink", "permissions"):
            with self.subTest(kind=kind):
                self.seed()
                if kind == "hardlink":
                    os.link(self.results, self.workspace / "other-link")
                else:
                    self.results.chmod(0o644)
                completed, _ = self.report()
                self.assertNotEqual(completed.returncode, 0)
                shutil.rmtree(self.private)
                shutil.rmtree(self.public)

    def test_duplicate_or_nonfinite_json_fails_closed(self):
        for data in ('{"version":1,"version":1}', '{"version":NaN}'):
            with self.subTest(data=data):
                self.seed()
                self.write(self.results, data)
                completed, _ = self.report()
                self.assertNotEqual(completed.returncode, 0)
                shutil.rmtree(self.private)
                shutil.rmtree(self.public)

    def test_python_optimize_and_cwd_module_cannot_disable_checkers(self):
        self.seed()
        self.write(self.workspace / "json.py", "raise RuntimeError(" + repr(CANARY) + ")\n")
        self.env["PYTHONOPTIMIZE"] = "1"
        result, summary = self.report()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(summary["execution_checks"]["eval"], "verified")

    def test_failed_doctor_execution_remains_failure(self):
        self.seed()
        self.write(self.workspace / ".agentops/agent/doctor-exit-code", "1\n")
        result, summary = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(summary["execution_checks"]["doctor"], "failed")
        self.assertEqual(summary["native_exit_codes"]["doctor"], 1)

    def test_actual_workflow_private_capture_and_gate_with_inert_copilot(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        for attempt, exit_code, preflight_status, judge_override in (
            ("primary", 0, 0, False), ("primary", 1, 0, False), ("primary", 0, 1, False),
            ("retry", 1, 0, False), ("retry", 0, 1, False),
            ("primary", 0, 0, True), ("retry", 0, 0, True),
        ):
            with self.subTest(attempt=attempt, exit_code=exit_code, preflight=preflight_status, judge=judge_override):
                self.assertEqual(self.cli("init").returncode, 0)
                if attempt == "retry":
                    self.assertEqual(self.cli("prepare", "primary").returncode, 0)
                    self.write(self.private / "attempts/primary/transcript.log", "CAPIError 429\n" + CANARY)
                bindir = self.scratch / "bin"
                bindir.mkdir(exist_ok=True)
                sentinel = self.scratch / "paid-called"
                executable = bindir / "copilot"
                self.write(executable, f"""#!{sys.executable}
import os, pathlib, sys
assert "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON" not in os.environ
assert "GITHUB_STEP_SUMMARY" not in os.environ
assert "GITHUB_OUTPUT" not in os.environ
assert "GITHUB_ENV" not in os.environ
pathlib.Path({str(sentinel)!r}).write_text("called")
print({CANARY!r})
print({CANARY!r}, file=sys.stderr)
pathlib.Path(os.environ["AGENTOPS_CI_MARKER"]).write_text("SMOKE_RESULT=FAIL {CANARY}\\n")
sys.exit({exit_code})
""")
                executable.chmod(0o700)
                step = next(s for s in steps if (s.get("id") == "run" if attempt == "primary"
                                                else s.get("name") == "Retry once on classified-transient failure"))
                branch = re.search(r"# BEGIN AgentOps private attempt\n(.*?)# END AgentOps private attempt",
                                   step["run"], re.S)
                self.assertIsNotNone(branch)
                shell = f"""
set -euo pipefail
python3() {{
  if [ "$1" = "scripts/agentops-ci-preflight.py" ]; then
    return {preflight_status}
  fi
  command "{sys.executable}" "$@"
}}
assert_tracked_checkout_clean() {{ return 0; }}
sleep() {{ return 0; }}
SKILL=foundry-agentops
PROMPT="{FIXTURE}"
{branch[1]}
"""
                env = dict(self.env, PATH=str(bindir) + os.pathsep + self.env["PATH"],
                           AGENTOPS_CI_ROOT=str(self.private),
                           AGENTOPS_CI_APPROVAL_FILE=str(self.private / "owner-approval.json"),
                           AGENTOPS_CI_TELEMETRY_APPROVAL_JSON=CANARY,
                           GITHUB_STEP_SUMMARY=str(self.scratch / "summary"),
                           GITHUB_OUTPUT=str(self.scratch / "step-output"),
                           GITHUB_ENV=str(self.scratch / "step-env"),
                           FOUNDRY_PROJECT_ENDPOINT="https://example.invalid/api/projects/example",
                           FOUNDRY_MODEL_DEPLOYMENT="example-model",
                           APPLICATIONINSIGHTS_CONNECTION_STRING=CANARY)
                if judge_override:
                    env["AZURE_OPENAI_DEPLOYMENT"] = CANARY
                result = subprocess.run(["bash", "-c", shell], cwd=ROOT, env=env, text=True, capture_output=True)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
                self.assertNotEqual(result.returncode, 0, "A marker with no native evidence cannot pass")
                self.assertEqual(sentinel.exists(), preflight_status == 0 and not judge_override)
                if sentinel.exists():
                    self.assertIn(CANARY, (self.private / f"attempts/{attempt}/transcript.log").read_text())
                    self.assertEqual((self.private / f"attempts/{attempt}/transcript.log").stat().st_mode & 0o777, 0o600)
                    sentinel.unlink()
                self.assertFalse((self.scratch / "summary").exists())
                shutil.rmtree(self.private)
                shutil.rmtree(self.public)

    def test_ci_scope_block_uses_record_not_discovery_and_rejects_overrides(self):
        self.seed()
        block = re.search(r"# BEGIN AGENTOPS CI SCOPE CHECK\n(.*?)# END AGENTOPS CI SCOPE CHECK",
                          FIXTURE.read_text(), re.S)
        self.assertIsNotNone(block)
        repository = self.scratch / "inert-repository"
        record = {
            "foundry": {"eval_judge_deployment": "judge", "doctor_judge_deployment": "judge",
                        "account_resource_id": "/subscriptions/example/resourceGroups/approved/providers/Microsoft.CognitiveServices/accounts/account"},
            "identity": {"subscription_id": "example"},
            "telemetry": {"component_resource_id": "/approved/component"},
        }
        approval = self.private / "owner-approval.json"
        self.write(approval, json.dumps(record))
        # Isolate only the already-tested Azure preflight boundary: no CLI,
        # credentials or network are touched by these config-binding cases.
        self.write(repository / "scripts/agentops-ci-preflight.py", f"""
import json
from pathlib import Path
absolute_path = Path
parse_json = json.loads
def read_file(path, root):
    return path.read_text()
def validate_paths(path, env, write):
    return Path({str(self.private)!r})
def main(args):
    return 0
""")
        endpoint = "https://example.invalid/api/projects/approved"
        env = dict(self.env, GITHUB_WORKSPACE=str(repository),
                   AGENTOPS_CI_APPROVAL_FILE=str(approval),
                   FOUNDRY_PROJECT_ENDPOINT=endpoint,
                   AZURE_AI_FOUNDRY_PROJECT_ENDPOINT=endpoint,
                   AZURE_OPENAI_DEPLOYMENT="judge", AZURE_AI_MODEL_DEPLOYMENT_NAME="judge",
                   AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING=CANARY,
                   APPLICATIONINSIGHTS_CONNECTION_STRING=CANARY,
                   LAW_WORKSPACE_ID="present-but-not-a-native-config-field")
        config = {"version": 1, "project_endpoint": endpoint,
                  "agent": "ci-smoke-agentops-pa-offline:7", "dataset": ".agentops/data/smoke.jsonl"}
        doctor = {
            "version": 1, "lookback_days": 1,
            "sources": {
                "results_history": {"enabled": True},
                "azure_monitor": {"enabled": True, "app_insights_resource_id": "/approved/component"},
                "foundry_control": {"enabled": True, "project_endpoint": endpoint,
                                    "agent_ids": ["ci-smoke-agentops-pa-offline"]},
                "azure_resources": {"enabled": True, "subscription_id": "example",
                                    "resource_group": "approved", "cognitive_services_account": "account"},
            },
        }
        for case in ("approved", "workspace-wide", "disabled", "dotenv", "judge", "key", "project"):
            with self.subTest(case=case):
                effective_env = env.copy()
                effective_doctor = json.loads(json.dumps(doctor))
                if case == "workspace-wide":
                    effective_doctor["sources"]["azure_monitor"]["log_analytics_workspace_id"] = CANARY
                elif case == "disabled":
                    effective_doctor["sources"]["results_history"]["enabled"] = False
                elif case == "dotenv":
                    self.write(self.workspace / ".agentops/.env", "OPENAI_API_KEY=" + CANARY)
                elif case == "judge":
                    effective_env["AZURE_OPENAI_DEPLOYMENT"] = CANARY
                elif case == "key":
                    effective_env["AZURE_OPENAI_API_KEY"] = CANARY
                elif case == "project":
                    effective_env["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"] = CANARY
                self.write(self.workspace / "agentops.yaml", yaml.safe_dump(config))
                self.write(self.workspace / ".agentops/agent.yaml", yaml.safe_dump(effective_doctor))
                result = subprocess.run([sys.executable, "-c", block[1]], cwd=self.workspace,
                                        env=effective_env, text=True, capture_output=True)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
                self.assertEqual(result.returncode == 0, case == "approved",
                                 "Scope reconciliation accepted an unapproved route")
                if case == "dotenv":
                    (self.workspace / ".agentops/.env").unlink()

    def test_symlink_artifact_and_pointer_escape_fail_without_reading_target(self):
        for which in ("artifact", "pointer", "directory"):
            with self.subTest(which=which):
                self.seed()
                outside = self.scratch / ("outside-" + which)
                self.write(outside, CANARY)
                if which == "artifact":
                    self.results.unlink()
                    self.results.symlink_to(outside)
                elif which == "pointer":
                    self.write(self.attempt / "workspace-pointer", str(outside))
                else:
                    shutil.rmtree(self.workspace / ".agentops/release/latest")
                    (self.workspace / ".agentops/release/latest").symlink_to(self.scratch)
                completed = self.cli("report", "primary", "0")
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(outside.read_text(), CANARY)
                shutil.rmtree(self.private)
                if self.public.exists():
                    shutil.rmtree(self.public)

    def test_cleanup_unlinks_only_owned_root_and_never_follows_symlinks(self):
        self.seed()
        self.report()
        outside = self.scratch / "outside"
        self.write(outside, CANARY)
        (self.private / "escape").symlink_to(outside)
        self.assertEqual(self.cli("cleanup").returncode, 0)
        self.assertFalse(self.private.exists())
        self.assertTrue((self.public / "primary.json").exists())
        self.assertEqual(outside.read_text(), CANARY)
        self.assertEqual(self.cli("cleanup").returncode, 0)

    def test_cleanup_rejects_symlink_root(self):
        self.start()
        shutil.rmtree(self.private)
        self.private.symlink_to(self.scratch, target_is_directory=True)
        self.assertNotEqual(self.cli("cleanup").returncode, 0)
        self.assertTrue(self.scratch.exists())

    def test_cleanup_removes_only_exact_legacy_files_even_without_private_root(self):
        for private_exists in (False, True):
            with self.subTest(private_exists=private_exists):
                if private_exists:
                    self.start()
                for name in LEGACY_NAMES:
                    self.write(self.legacy / name, CANARY)
                unrelated = self.legacy / "other-skill-transcript.log"
                unlisted = self.legacy / "foundry-agentops-not-allowlisted.log"
                for path in (unrelated, unlisted):
                    self.write(path, CANARY)
                result = self.cli("cleanup")
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertFalse(self.private.exists())
                self.assertTrue(all(not (self.legacy / name).exists() for name in LEGACY_NAMES))
                self.assertEqual(unrelated.read_text(), CANARY)
                self.assertEqual(unlisted.read_text(), CANARY)

    def test_cleanup_unlinks_owned_legacy_symlink_not_its_target(self):
        target = self.scratch / "outside-legacy"
        self.write(target, CANARY)
        link = self.legacy / LEGACY_NAMES[0]
        link.symlink_to(target)
        self.assertEqual(self.cli("cleanup").returncode, 0)
        self.assertFalse(link.is_symlink())
        self.assertEqual(target.read_text(), CANARY)

    def test_cleanup_rejects_legacy_directory_and_continues_other_targets(self):
        self.start()
        directory = self.legacy / LEGACY_NAMES[0]
        self.write(directory / "must-remain", CANARY)
        remaining = self.legacy / LEGACY_NAMES[1]
        self.write(remaining, CANARY)
        result = self.cli("cleanup")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "AGENTOPS_CI_DELIVERY=FAIL CLEANUP")
        self.assertFalse(self.private.exists())
        self.assertFalse(remaining.exists())
        self.assertEqual((directory / "must-remain").read_text(), CANARY)

    def test_cleanup_preserves_foreign_owned_legacy_file_and_reports_failure(self):
        foreign = self.legacy / LEGACY_NAMES[0]
        self.write(foreign, CANARY)
        remaining = self.legacy / LEGACY_NAMES[1]
        self.write(remaining, CANARY)
        original_stat = os.stat

        def foreign_owner(path, *args, **kwargs):
            info = original_stat(path, *args, **kwargs)
            if path == foreign.name and kwargs.get("dir_fd") is not None:
                self.assertFalse(kwargs["follow_symlinks"])
                return SimpleNamespace(st_uid=os.getuid() + 1, st_mode=info.st_mode)
            return info

        with patch.object(self.reporter.os, "stat", side_effect=foreign_owner):
            result = self.cli("cleanup")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.strip(), "AGENTOPS_CI_DELIVERY=FAIL CLEANUP")
        self.assertEqual(foreign.read_text(), CANARY)
        self.assertFalse(remaining.exists())

    def test_cleanup_attempts_legacy_unlinks_even_when_private_root_is_unsafe(self):
        self.private.symlink_to(self.scratch, target_is_directory=True)
        legacy_file = self.legacy / LEGACY_NAMES[0]
        self.write(legacy_file, CANARY)
        result = self.cli("cleanup")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.private.is_symlink())
        self.assertFalse(legacy_file.exists())

    def test_cleanup_never_follows_legacy_parent_symlink(self):
        self.start()
        outside = self.scratch / "outside-legacy-directory"
        self.write(outside / LEGACY_NAMES[0], CANARY)
        self.legacy.rmdir()
        self.legacy.symlink_to(outside, target_is_directory=True)
        result = self.cli("cleanup")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.private.exists())
        self.assertEqual((outside / LEGACY_NAMES[0]).read_text(), CANARY)

    def test_report_cannot_overwrite_primary_summary(self):
        self.seed()
        self.report()
        original = (self.public / "primary.json").read_bytes()
        self.assertEqual(self.cli("report", "primary", "1").returncode, 2)
        self.assertEqual((self.public / "primary.json").read_bytes(), original)

    def test_preexisting_public_file_never_authorizes_upload(self):
        self.seed()
        self.write(self.public / "primary.json", CANARY)
        self.assertEqual(self.cli("report", "primary", "0").returncode, 2)
        self.assertEqual((self.public / "primary.json").read_text(), CANARY)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.safe_load(WORKFLOW.read_text())
        self.steps = self.workflow["jobs"]["copilot-cli-matrix"]["steps"]
        self.primary = next(s for s in self.steps if s.get("id") == "run")
        self.retry = next(s for s in self.steps if s.get("name") == "Retry once on classified-transient failure")

    def test_secret_names_selected_without_value_fallback(self):
        for step in (self.primary, self.retry):
            for variable, dedicated in (
                ("APPLICATIONINSIGHTS_CONNECTION_STRING", "AGENTOPS_CI_APPLICATIONINSIGHTS_CONNECTION_STRING"),
                ("LAW_WORKSPACE_ID", "AGENTOPS_CI_LAW_WORKSPACE_ID"),
            ):
                self.assertEqual(step["env"][variable],
                                 "${{ secrets[matrix.skill == 'foundry-agentops' && '" + dedicated + "' || '" + variable + "'] }}")
            self.assertNotIn("AGENTOPS_CI_TELEMETRY_APPROVAL_JSON", step["env"])
        self.assertEqual(self.primary["env"], self.retry["env"])

    def test_gate_order_and_identity_root(self):
        isolate = next(s for s in self.steps if s.get("name") == "Isolate AgentOps credential sources")
        self.assertIn('$RUNNER_TEMP/agentops-ci-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT', isolate["run"])
        self.assertNotIn(".artifacts", isolate["run"])
        login = next(s for s in self.steps if s.get("uses") == "azure/login@v2")
        resolver = next(s for s in self.steps if s.get("id") == "resolve-foundry-project")
        gate = next((s for s in self.steps if s.get("id") == "agentops-preflight"), None)
        self.assertIsNotNone(gate, "Deterministic preflight is missing")
        self.assertLess(self.steps.index(isolate), self.steps.index(login))
        self.assertLess(self.steps.index(resolver), self.steps.index(gate))
        self.assertLess(self.steps.index(gate), self.steps.index(self.primary))
        self.assertIn("--write-approval", gate["run"])
        self.assertEqual(gate["env"]["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"],
                         "${{ secrets.AGENTOPS_CI_TELEMETRY_APPROVAL_JSON }}")
        for name in ("FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_PROJECT_ID", "AZURE_CLIENT_ID",
                     "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "FOUNDRY_MODEL_DEPLOYMENT"):
            self.assertEqual(gate["env"][name], self.primary["env"][name])
        self.assertNotIn("GITHUB_ENV", gate["run"])

    def test_private_branch_precedes_legacy_outputs_and_rechecks(self):
        for step in (self.primary, self.retry):
            script = step["run"]
            branch = re.search(r"# BEGIN AgentOps private attempt\n(.*?)# END AgentOps private attempt", script, re.S)
            self.assertIsNotNone(branch, "AgentOps must leave before legacy public output")
            text = branch[1]
            self.assertIn('--approval-file "$AGENTOPS_CI_APPROVAL_FILE"', text)
            self.assertLess(text.index("--approval-file"), text.index("copilot -p"))
            self.assertLess(text.index('assert_tracked_checkout_clean "after Copilot"'), text.index("report "))
            self.assertIn('> "$TRANSCRIPT" 2>&1', text)
            self.assertIn("-u AGENTOPS_CI_TELEMETRY_APPROVAL_JSON", text)
            self.assertIn("-u GITHUB_STEP_SUMMARY", text)
            self.assertNotRegex(text, r"\b(?:tee|tail)\b|cat \"\$(?:EVIDENCE|MARKER|TRANSCRIPT)")
            self.assertIn("exit", text)
            self.assertLess(branch.end(), script.index('cat "$EVIDENCE"'))
        self.assertIn("retry-allowed", self.retry["run"])

    def test_public_upload_excludes_raw_and_finalizer_is_unconditional(self):
        raw = next(s for s in self.steps if s.get("name") == "Upload transcript and evidence (forensics)")
        self.assertEqual(raw["if"], "always() && matrix.skill != 'foundry-agentops'")
        summaries = [s for s in self.steps if s.get("name", "").startswith("Upload sanitized AgentOps")]
        cleanup = next((s for s in self.steps if s.get("name") == "Remove private AgentOps runner files"), None)
        self.assertEqual(len(summaries), 2, "Upload only the individually host-validated attempt")
        self.assertIsNotNone(cleanup)
        self.assertEqual(cleanup["if"], "always() && matrix.skill == 'foundry-agentops'")
        self.assertIn("cleanup", cleanup["run"])
        self.assertIn("GIT_NO_REPLACE_OBJECTS=1", cleanup["run"])
        self.assertIn('show "$GITHUB_SHA:scripts/agentops-ci-report.py"', cleanup["run"])
        for summary, step in zip(summaries, ("run", "agentops-retry")):
            self.assertIn(f"steps.{step}.outputs.agentops_summary == 'verified'", summary["if"])
            self.assertIn("agentops-ci-public-", summary["with"]["path"])
            self.assertNotIn("*", summary["with"]["path"])
            self.assertNotIn("transcript", summary["with"]["path"])

    def test_fixture_ci_record_workspace_and_retention_contract(self):
        text = " ".join(FIXTURE.read_text().split())
        for required in (
            "AGENTOPS_CI_APPROVAL_FILE", "agentops-ci-preflight.py",
            "workspace-pointer", "agent-identity.json", "workspaces/<UUID>",
            "workflow owner's deterministic", "Do NOT set `log_analytics_workspace_id`",
            "leave the CI workspace intact", "Public Actions", "unverified",
        ):
            self.assertIn(required, text)
        self.assertIn("cached-user", text)
        self.assertIn("7-day", text)


if __name__ == "__main__":
    unittest.main()

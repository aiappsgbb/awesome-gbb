"""Single-known-run main/schedule approval; no authorization is issued here."""

import copy
from contextlib import redirect_stdout
from datetime import timedelta
import io
import json
from unittest.mock import patch
import unittest

import yaml

from scripts.tests import test_agentops_ci_preflight as preflight_fixtures
from scripts.tests.test_agentops_ci_preflight import (
    NOW, ROOT, approval_record, diagnostic_approval_record,
)


def main_approval(event_name):
    record = approval_record()
    record["schema_version"] = 3
    auth = record["authorization"]
    del auth["pull_request"], auth["head_branch"]
    auth.update(
        event_name=event_name, ref="refs/heads/main", head_sha="c" * 40,
        run_id="123456", run_attempt=2, issued_at="2030-01-01T00:00:00Z",
    )
    return record


class EventApprovalTests(unittest.TestCase):
    setUpClass = classmethod(preflight_fixtures.PreflightTests.setUpClass.__func__)
    setUp = preflight_fixtures.PreflightTests.setUp
    run_gate = preflight_fixtures.PreflightTests.run_gate
    read_json = preflight_fixtures.PreflightTests.read_json
    sync_record = preflight_fixtures.PreflightTests.sync_record

    def select(self, event_name):
        self.record = main_approval(event_name)
        self.sync_record()
        self.env.update(
            GITHUB_EVENT_NAME=event_name, GITHUB_REF="refs/heads/main", GITHUB_SHA="c" * 40,
        )
        # GitHub schedule exposes event.schedule, repository and GITHUB_SHA/REF;
        # it does not contain a pull_request object, push.after or push.ref.
        # https://docs.github.com/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
        self.event = {
            "repository": {"full_name": "example/awesome-gbb", "default_branch": "main"},
        }
        if event_name == "push":
            self.event.update(ref="refs/heads/main", after="c" * 40, deleted=False)
        else:
            self.event["schedule"] = "0 8 * * 1"
        self.write_event()

    def write_event(self):
        self.event_path.write_text(json.dumps(self.event))

    def check_offline(self, now=NOW):
        output = io.StringIO()
        with redirect_stdout(output), patch("subprocess.Popen", side_effect=AssertionError("no CLI")), \
                patch("socket.socket", side_effect=AssertionError("no network")):
            status = self.gate.main(["--check-authorization-only"], environ=self.env, now=now)
        for value in (self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"],
                      self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"]):
            self.assertNotIn(value, output.getvalue())
        return status, output.getvalue()

    def test_main_push_and_schedule_match_single_known_run_and_recheck(self):
        for event_name in ("push", "schedule"):
            with self.subTest(event=event_name):
                self.select(event_name)
                self.assertEqual(self.check_offline(), (0, "AGENTOPS_CI_AUTHORIZATION=PASS CONFIG_ONLY\n"))
                self.assertEqual(self.calls, [])
                self.assertEqual(self.run_gate(), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
                self.assertEqual(self.path.read_text(), self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"])
                self.assertEqual(self.run_gate(write=False), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
                self.path.unlink()
                self.calls.clear()

    def test_every_event_environment_binding_fails_before_metadata(self):
        for event_name in ("push", "schedule"):
            self.select(event_name)
            original = self.env.copy()
            for key, wrong in (
                ("GITHUB_REPOSITORY", "other/awesome-gbb"),
                ("GITHUB_EVENT_NAME", "workflow_dispatch"),
                ("GITHUB_EVENT_NAME", "pull_request"),
                ("GITHUB_EVENT_NAME", "schedule" if event_name == "push" else "push"),
                ("GITHUB_REF", "refs/heads/feature"),
                ("GITHUB_SHA", "d" * 40),
                ("GITHUB_RUN_ID", "654321"),
                ("GITHUB_RUN_ATTEMPT", "3"),
                ("GITHUB_RUN_ATTEMPT", "02"),
            ):
                with self.subTest(event=event_name, key=key, wrong=wrong):
                    self.env[key] = wrong
                    self.assertEqual(self.check_offline()[0], 1)
                    self.assertEqual(self.run_gate()[0], 1)
                    self.assertEqual(self.calls, [])
                    self.env = original.copy()

    def test_missing_and_mismatched_push_payload_fields_reject(self):
        self.select("push")
        original = copy.deepcopy(self.event)
        for key, wrong_values in (
            ("ref", [None, "refs/heads/feature"]),
            ("after", [None, "d" * 40]),
            ("deleted", [None, True, "false", 0, "", []]),
        ):
            for wrong in wrong_values:
                with self.subTest(key=key, wrong=wrong):
                    self.event = copy.deepcopy(original)
                    if wrong is None:
                        del self.event[key]
                    else:
                        self.event[key] = wrong
                    self.write_event()
                    self.assertEqual(self.check_offline()[0], 1)
                    self.assertEqual(self.calls, [])

    def test_schedule_no_invented_pr_fields_and_conflicting_context_rejected(self):
        self.select("schedule")
        self.assertEqual(self.check_offline()[0], 0)
        for changed in (
            {"schedule": ""}, {"pull_request": {}}, {"after": "d" * 40},
            {"ref": "refs/heads/feature"},
            {"repository": {"full_name": "example/awesome-gbb", "default_branch": "trunk"}},
            {"repository": {"full_name": "other/repo", "default_branch": "main"}},
        ):
            self.select("schedule")
            self.event.update(changed)
            self.write_event()
            self.assertEqual(self.check_offline()[0], 1)

    def test_old_records_never_convert_to_main_or_schedule(self):
        for event_name in ("push", "schedule"):
            for factory in (approval_record, diagnostic_approval_record):
                self.select(event_name)
                self.record = factory()
                self.sync_record()
                self.assertEqual(self.check_offline()[0], 1)
                self.assertEqual(self.calls, [])
                self.assertFalse(self.path.exists())

    def test_new_schema_rejects_unbounded_or_coerced_context(self):
        self.select("push")
        original = copy.deepcopy(self.record)
        cases = {
            "event_name": ("pull_request", "workflow_dispatch", "*", ["push"]),
            "ref": ("main", "refs/heads/*", "refs/heads/feature"),
            "head_sha": ("*", "", "c" * 39, "C" * 40, True),
            "run_id": ("*", "", "0123456", "123456.0", 123456, True),
            "run_attempt": (True, False, 0, -1, 2.0, "2"),
            "issued_at": ("2030-01-01T00:00:00", "2030-01-01T00:00:00+00:00",
                          "2030-01-01T00:00:00+01:00", "2030-01-01T01:00:00Z"),
            "expires_at": ("2030-01-01T00:00:00", "2030-01-02T00:00:01Z",
                           "2030-01-01T00:00:00Z"),
        }
        for key, values in cases.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    self.record = copy.deepcopy(original)
                    self.record["authorization"][key] = value
                    self.sync_record()
                    self.assertEqual(self.check_offline()[0], 1)
        for key in original["authorization"]:
            self.record = copy.deepcopy(original)
            del self.record["authorization"][key]
            self.sync_record()
            self.assertEqual(self.check_offline()[0], 1)
        for key, value in (("diagnostic", {}), ("wildcard", True)):
            self.record = copy.deepcopy(original)
            self.record[key] = value
            self.sync_record()
            self.assertEqual(self.check_offline()[0], 1)
        self.assertEqual(self.calls, [])

    def test_expiry_is_not_renewal_and_duplicate_json_fails(self):
        self.select("schedule")
        raw = self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        self.assertEqual(self.check_offline(now=NOW + timedelta(days=1)),
                         (1, "AGENTOPS_CI_AUTHORIZATION=FAIL EXPIRED\n"))
        self.assertEqual(self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"], raw)
        self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"] = raw.replace(
            '"run_attempt": 2', '"run_attempt": 2, "run_attempt": 2',
        )
        self.assertEqual(self.check_offline()[0], 1)
        self.assertEqual(self.calls, [])

    def test_new_event_does_not_relax_identity_telemetry_or_retention(self):
        self.select("push")
        for key in ("AZURE_CLIENT_ID", "FOUNDRY_PROJECT_ENDPOINT", "FOUNDRY_MODEL_DEPLOYMENT",
                    "LAW_WORKSPACE_ID", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
            with patch.dict(self.env, {key: "wrong"}):
                self.assertEqual(self.run_gate()[0], 1)
                self.assertEqual(self.calls, [])
        self.record["capture"]["retry_to_obtain_green_authorized"] = True
        self.sync_record()
        self.assertEqual(self.check_offline()[0], 1)

    def test_gate_precedes_credentials_tools_or_paid_execution(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        gate = next(step for step in steps if step.get("id") == "agentops-authorization")
        self.assertEqual(gate["if"], "matrix.skill == 'foundry-agentops'")
        self.assertNotIn("continue-on-error", gate)
        self.assertIn("--check-authorization-only", gate["run"])
        for index, step in enumerate(steps):
            if step.get("uses", "").startswith("azure/login@") or step.get("id") in ("run", "agentops-preflight"):
                self.assertLess(steps.index(gate), index)


if __name__ == "__main__":
    unittest.main()

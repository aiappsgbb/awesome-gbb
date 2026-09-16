"""Offline contracts for manual SHA policy, incomplete checks and issue safety."""

from __future__ import annotations

import datetime as dt
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CF = load_script("freshness_outcomes", ROOT / "scripts/check-freshness.py")
VS = load_script("freshness_policy_validator", ROOT / "scripts/validate-skills.py")


def pin(skill="example-skill", **upstream):
    return CF.PinFile(skill, Path("unused"), {
        "schema_version": 2,
        "freshness_tier": "B",
        "automation_tier": "auto",
        "upstream": {
            "type": "github_repo", "repo": "example/upstream",
            "ref": "main", "pinned_sha": "a" * 40, **upstream,
        },
        "last_validated": dt.date.today(),
        "validation": {"requires": ["github_only"], "runnable": True, "script": "echo ok"},
    })


def response(payload, status=200):
    result = Mock(status_code=status, text="mock response")
    result.json.return_value = payload
    if status >= 400:
        result.raise_for_status.side_effect = CF.requests.HTTPError(f"HTTP {status}")
    return result


class FreshnessOutcomesTest(unittest.TestCase):
    def setUp(self):
        for name in ("get", "post", "patch", "head"):
            guard = patch.object(CF.requests, name, side_effect=AssertionError("unexpected HTTP"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(CF.subprocess, "run", side_effect=AssertionError("unexpected subprocess"))
        guard.start()
        self.addCleanup(guard.stop)

    def issue(self, skill="example-skill"):
        return {
            "number": 1, "title": f"🔄 Refresh `{skill}`",
            "url": "https://api.github.com/repos/example/catalog/issues/1",
            "body": "previous evidence", "labels": [{"name": "freshness"}],
        }

    def close(self, verified, signals=None, dry_run=False):
        return CF.close_resolved_issues(
            skills_with_signals=signals or set(), verified_skills=verified,
            repo="example/catalog", gh_token="test-only",
            labels=["freshness"], dry_run=dry_run, execution_mode="copilot",
        )

    def upsert(self, signal, mode):
        return CF.upsert_issue(signal, "example/catalog", "test-only", mode, ["freshness"], False)

    def test_default_and_explicit_automatic_keep_sha_polling(self):
        for policy in ({}, {"sha_tracking": "automatic"}):
            with self.subTest(policy=policy), patch.object(
                CF.subprocess, "run", return_value=Mock(stdout=f"{'a' * 40}\trefs/heads/main\n")
            ) as run:
                self.assertIsNone(CF.detect_sha_drift(pin(**policy), None))
                self.assertEqual(run.call_count, 1)
                self.assertEqual(run.call_args.args[0][:2], ["git", "ls-remote"])

    def test_manual_check_never_queries_sha_and_is_not_an_issue(self):
        result = CF.detect_sha_drift(
            pin(sha_tracking="manual", sha_tracking_reason="Human reviews the vendored core."), None
        )
        self.assertEqual(result.signal_type, "manual_check")
        self.assertIn("Human reviews", result.body)
        self.assertEqual(CF.consolidate_signals([result]), [])
        CF.subprocess.run.assert_not_called()

    def test_invalid_manual_policy_is_an_error_not_a_silent_exclusion(self):
        policies = [
            {"sha_tracking": "manual"},
            {"sha_tracking": "manual", "sha_tracking_reason": " "},
            {"sha_tracking": "manual", "sha_tracking_reason": 3},
            {"sha_tracking": "disabled"},
            {"sha_tracking": False},
            {"sha_tracking": "manual", "sha_tracking_reason": "reason", "type": "pypi"},
            {"sha_tracking": "manual", "sha_tracking_reason": "reason", "ref": ""},
        ]
        for policy in policies:
            with self.subTest(policy=policy):
                result = CF.detect_sha_drift(pin(**policy), None)
                self.assertEqual(result.signal_type, "check_error")
                self.assertTrue(result.incomplete)
        CF.subprocess.run.assert_not_called()

    def test_missing_automatic_identity_is_not_success(self):
        self.assertTrue(CF.detect_sha_drift(pin(repo=""), None).incomplete)

    def test_manual_policy_keeps_all_other_detectors(self):
        manual = pin(sha_tracking="manual", sha_tracking_reason="Human vendoring.")
        with patch.object(CF, "detect_pkg_drift", return_value=[]) as packages, \
             patch.object(CF, "detect_issue_closure", return_value=[]) as issues, \
             patch.object(CF, "detect_link_rot", return_value=[]) as links, \
             patch.object(CF, "detect_stale_validation", return_value=None) as age:
            results = CF.collect_signals([manual], None)
        self.assertEqual([r.signal_type for r in results], ["manual_check"])
        for detector in (packages, issues, links, age):
            detector.assert_called_once()

    def test_lookup_failures_are_unknown_and_human_owned(self):
        failures = [
            subprocess.CalledProcessError(128, ["git", "ls-remote"]),
            subprocess.TimeoutExpired(["git"], 30),
            FileNotFoundError("git unavailable"),
        ]
        for failure in failures:
            with self.subTest(failure=failure), patch.object(CF.subprocess, "run", side_effect=failure):
                result = CF.detect_sha_drift(pin(), None)
            self.assertEqual(result.signal_type, "check_error")
            self.assertEqual(CF.classify_impact(result), "unknown")
            self.assertEqual(result.automation_tier, "issue_only")
            self.assertTrue(result.incomplete)

    def test_empty_or_malformed_sha_response_is_incomplete(self):
        for output in ("", "not-a-sha\trefs/heads/main\n"):
            with patch.object(CF.subprocess, "run", return_value=Mock(stdout=output)):
                self.assertTrue(CF.detect_sha_drift(pin(), None).incomplete)

    def test_real_sha_drift_has_no_hardcoded_assignment(self):
        with patch.object(CF.subprocess, "run", return_value=Mock(stdout=f"{'b' * 40}\tmain\n")):
            result = CF.detect_sha_drift(pin(), None)
        self.assertEqual(result.signal_type, "sha_drift")
        self.assertFalse(result.incomplete)
        self.assertNotIn("assigned to @Copilot", result.body)

    def test_pypi_failures_and_missing_version_are_incomplete(self):
        item = pin()
        item.fm["packages"] = [{"source": "pypi", "name": "azure-example", "version": "1.0.0"}]
        for payload, status in (({}, 403), ([], 200), ({"info": {}}, 200)):
            with patch.object(CF.requests, "get", return_value=response(payload, status)):
                results = CF.detect_pkg_drift(item)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].incomplete)

    def test_upstream_issue_failures_do_not_disappear(self):
        item = pin()
        item.fm["known_issues"] = [{
            "id": "KI-001", "status": "open",
            "upstream_url": "https://github.com/example/upstream/issues/1",
        }]
        for payload, status in (({}, 403), ({}, 200), ([], 200)):
            with patch.object(CF.requests, "get", return_value=response(payload, status)):
                results = CF.detect_issue_closure(item, None)
            self.assertTrue(results[0].incomplete)

    def test_documentation_access_failure_is_not_link_rot(self):
        item = pin()
        item.fm["docs_to_revalidate"] = ["https://example.test/guide"]
        for status in (401, 403, 429, 500, 503):
            with patch.object(CF.requests, "head", return_value=response({}, status)):
                results = CF.detect_link_rot(item)
            self.assertEqual(results[0].signal_type, "check_error")
        for status in (404, 410):
            with patch.object(CF.requests, "head", return_value=response({}, status)):
                self.assertEqual(CF.detect_link_rot(item)[0].signal_type, "link_rot")
        with patch.object(CF.requests, "head", side_effect=CF.requests.Timeout("timeout")):
            self.assertTrue(CF.detect_link_rot(item)[0].incomplete)

    def test_bad_validation_date_is_not_current(self):
        item = pin()
        item.fm["last_validated"] = "invalid"
        self.assertTrue(CF.detect_stale_validation(item, dt.date.today()).incomplete)

    def test_mixed_consolidation_preserves_drift_and_failed_checks(self):
        error = CF.check_error(pin(), "SHA", "unreachable")
        drift = CF.Signal(
            skill=error.skill, signal_type="pkg_drift", severity="warn",
            title="package 1.0.0 → 2.0.0", body="real drift", automation_tier="auto",
        )
        result = CF.consolidate_signals([error, drift])[0]
        self.assertEqual(result.impact, "critical")
        self.assertTrue(result.incomplete)
        self.assertEqual(result.automation_tier, "issue_only")
        self.assertIn("real drift", result.body)
        self.assertIn("Failed checks**: 1", result.body)

    def test_error_only_report_does_not_claim_verified_drift(self):
        results = CF.consolidate_signals([CF.check_error(pin(), "SHA", "unreachable")])
        text = CF.render_report(results, 1)
        self.assertIn("UNKNOWN", text)
        self.assertIn("Failed checks are not verified drift", text)
        self.assertNotIn("All 1 pinned skills are current", text)

    def test_manual_report_does_not_claim_all_current(self):
        manual = CF.detect_sha_drift(pin(sha_tracking="manual", sha_tracking_reason="Human review."), None)
        text = CF.render_report([], 1, manual_checks=[manual])
        self.assertIn("not verified automatically", text)
        self.assertIn("Human review.", text)
        self.assertNotIn("are current", text)

    def test_existing_unknown_pin_cannot_close(self):
        with patch.object(CF.requests, "get", return_value=response({"items": [self.issue()]})):
            self.assertTrue(self.close(set()))
        CF.requests.patch.assert_not_called()

    def test_remaining_signal_cannot_close_even_if_whitelisted(self):
        with patch.object(CF.requests, "get", return_value=response({"items": [self.issue()]})):
            self.assertTrue(self.close({"example-skill"}, {"example-skill"}))
        CF.requests.patch.assert_not_called()

    def test_fully_checked_issue_closes_preserving_evidence(self):
        with patch.object(CF.requests, "get", return_value=response({"items": [self.issue()]})), \
             patch.object(CF.requests, "patch", return_value=response({})) as update:
            self.assertTrue(self.close({"example-skill"}))
        body = update.call_args.kwargs["json"]["body"]
        self.assertIn("previous evidence", body)
        self.assertIn("not live skill validation", body)

    def test_autoclose_search_failure_returns_failure(self):
        cases = [
            ({}, 403), ({}, 200), ({"items": "invalid"}, 200),
            ({"items": [self.issue()], "incomplete_results": True}, 200),
        ]
        for payload, status in cases:
            with self.subTest(payload=payload, status=status), \
                 patch.object(CF.requests, "get", return_value=response(payload, status)):
                self.assertFalse(self.close({"example-skill"}))
        with patch.object(CF.requests, "get", side_effect=CF.requests.Timeout("timeout")):
            self.assertFalse(self.close({"example-skill"}))
        CF.requests.patch.assert_not_called()

    def test_upsert_search_failure_cannot_create_a_duplicate(self):
        signal = CF.Signal("example-skill", "sha_drift", "warn", "title", "body", "auto")
        cases = [
            ({}, 403), ({}, 200), ([], 200), ({"items": "invalid"}, 200),
            ({"items": [None]}, 200), ({"items": [], "incomplete_results": True}, 200),
        ]
        for payload, status in cases:
            with self.subTest(payload=payload, status=status), \
                 patch.object(CF.requests, "get", return_value=response(payload, status)):
                self.assertFalse(self.upsert(signal, "manual"))
        with patch.object(CF.requests, "get", side_effect=CF.requests.Timeout("timeout")):
            self.assertFalse(self.upsert(signal, "manual"))
        CF.requests.post.assert_not_called()
        CF.requests.patch.assert_not_called()

    def test_unknown_impact_drops_old_impact_and_requires_manual_review(self):
        signal = CF.consolidate_signals([CF.check_error(pin(), "SHA", "unreachable")])[0]
        labels = CF.labels_for_execution_mode(
            ["freshness", "automation", "impact:critical"], signal, "copilot"
        )
        self.assertEqual(labels, ["freshness", "automation", "manual-review"])

    def test_issue_only_body_never_requests_copilot(self):
        signal = CF.Signal("example-skill", "sha_drift", "warn", "title", "body", "issue_only")
        with patch.object(CF.requests, "get", return_value=response({"items": []})), \
             patch.object(CF.requests, "post", return_value=response({"number": 1})) as create, \
             patch.object(CF, "assign_copilot_to_issue") as assign:
            self.assertTrue(self.upsert(signal, "copilot"))
        self.assertIn("human action required", create.call_args.kwargs["json"]["body"])
        assign.assert_not_called()

    def test_manual_sha_does_not_suppress_real_package_drift(self):
        manual = pin(sha_tracking="manual", sha_tracking_reason="Human vendoring.")
        manual.fm["packages"] = [{"source": "pypi", "name": "azure-example", "version": "1.0.0"}]
        with patch.object(CF.requests, "get", return_value=response({"info": {"version": "2.0.0"}})):
            findings = CF.collect_signals([manual], None)
        self.assertEqual({s.signal_type for s in findings}, {"manual_check", "pkg_drift"})
        candidates = CF.consolidate_signals(findings)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].impact, "critical")
        self.assertFalse(candidates[0].incomplete)

    def test_automatic_transport_error_never_becomes_a_manual_policy(self):
        item = pin()
        with patch.object(CF.subprocess, "run", side_effect=subprocess.CalledProcessError(128, ["git"])):
            result = CF.detect_sha_drift(item, None)
        self.assertEqual(result.signal_type, "check_error")
        self.assertEqual(CF.sha_tracking_policy(item.fm), ("automatic", ""))
        self.assertNotIn("sha_tracking", item.fm["upstream"])

    def test_upsert_body_uses_execution_mode_for_consolidated_and_legacy(self):
        signal = CF.Signal("example-skill", "sha_drift", "warn", "title", "body", "auto")
        for consolidated in (False, True):
            candidate = CF.consolidate_signals([signal])[0] if consolidated else signal
            for mode in ("manual", "copilot"):
                with self.subTest(mode=mode, consolidated=consolidated), \
                     patch.object(CF.requests, "get", return_value=response({"items": []})), \
                     patch.object(CF.requests, "post", return_value=response({"number": 1})) as create, \
                     patch.object(CF, "assign_copilot_to_issue", return_value=True) as assign:
                    self.assertTrue(self.upsert(candidate, mode))
                body = create.call_args.kwargs["json"]["body"]
                self.assertNotIn("assigned to @Copilot", body)
                self.assertIn("manual review required" if mode == "manual" else "assignment requested", body)
                self.assertEqual(assign.call_count, int(mode == "copilot"))

    def test_failed_assignment_is_not_reported_as_success(self):
        signal = CF.Signal("example-skill", "sha_drift", "warn", "title", "body", "auto")
        with patch.object(CF.requests, "get", return_value=response({"items": []})), \
             patch.object(CF.requests, "post", return_value=response({"number": 1})), \
             patch.object(CF, "assign_copilot_to_issue", return_value=False):
            self.assertFalse(self.upsert(signal, "copilot"))

    def test_error_issue_is_removed_from_copilot_even_in_copilot_mode(self):
        signal = CF.consolidate_signals([CF.check_error(pin(), "SHA", "unreachable")])[0]
        with patch.object(CF.requests, "get", return_value=response({"items": [self.issue()]})), \
             patch.object(CF.requests, "patch", return_value=response({"number": 1})) as update, \
             patch.object(CF, "remove_copilot_from_issue", return_value=True) as remove, \
             patch.object(CF, "assign_copilot_to_issue") as assign:
            self.assertTrue(self.upsert(signal, "copilot"))
        self.assertIn("human action required", update.call_args.kwargs["json"]["body"])
        remove.assert_called_once()
        assign.assert_not_called()

    def test_schema_validator_and_detector_agree_on_manual_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upstream-pin.md"
            for reason, valid in (("Human re-vendoring.", True), (" ", False), (None, False)):
                item = pin(sha_tracking="manual", sha_tracking_reason=reason)
                path.write_text("---\n" + CF.yaml.safe_dump(item.fm) + "---\n", encoding="utf-8")
                self.assertEqual(VS.validate_pin_file(path) == [], valid)
                self.assertEqual(CF.detect_sha_drift(item, None).signal_type == "manual_check", valid)

    def test_malformed_pin_discovery_stops_before_issue_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "example/references/upstream-pin.md"
            target.parent.mkdir(parents=True)
            target.write_text("---\ninvalid: [\n---\n", encoding="utf-8")
            with patch.object(CF, "SKILLS_DIR", root), \
                 patch.object(sys, "argv", ["check-freshness.py", "--upsert-issues", "--dry-run"]), \
                 redirect_stderr(io.StringIO()) as output:
                self.assertEqual(CF.main(), 2)
            self.assertIn("incomplete pin discovery", output.getvalue())
        CF.requests.get.assert_not_called()

    def test_main_excludes_manual_missing_and_failed_pins_from_closure(self):
        manual = pin("manual", sha_tracking="manual", sha_tracking_reason="Human vendoring.")
        failed = pin("failed")
        current = pin("current")
        findings = [
            CF.detect_sha_drift(manual, None),
            CF.check_error(failed, "SHA", "unreachable"),
        ]
        with patch.object(CF, "discover_pin_files", return_value=[manual, failed, current]), \
             patch.object(CF, "collect_signals", return_value=findings), \
             patch.object(CF, "upsert_issue", return_value=True) as upsert, \
             patch.object(CF, "close_resolved_issues", return_value=True) as close, \
             patch.object(sys, "argv", ["check-freshness.py", "--upsert-issues", "--dry-run"]), \
             patch.dict(CF.os.environ, {"GITHUB_OUTPUT": ""}), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(CF.main(), 1)
        self.assertEqual(upsert.call_count, 1)
        self.assertEqual(close.call_args.args[1], {"current"})

    def test_manual_only_main_reports_without_issue_candidate_or_auto_resolution(self):
        manual = pin(sha_tracking="manual", sha_tracking_reason="Human vendoring.")
        finding = CF.detect_sha_drift(manual, None)
        with patch.object(CF, "discover_pin_files", return_value=[manual]), \
             patch.object(CF, "collect_signals", return_value=[finding]), \
             patch.object(CF, "upsert_issue") as upsert, \
             patch.object(CF, "close_resolved_issues", return_value=True) as close, \
             patch.object(sys, "argv", ["check-freshness.py", "--upsert-issues", "--dry-run", "--print-report"]), \
             patch.dict(CF.os.environ, {"GITHUB_OUTPUT": ""}), \
             redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            self.assertEqual(CF.main(), 0)
        upsert.assert_not_called()
        self.assertEqual(close.call_args.args[1], set())
        self.assertIn("not verified automatically", output.getvalue())

    def test_published_vendoring_policy_requires_no_sha_lookup(self):
        path = ROOT / "skills/paygo-ptu-cost-analyzer/references/upstream-pin.md"
        item = CF.parse_pin_file(path)
        self.assertEqual(CF.sha_tracking_policy(item.fm)[0], "manual")
        self.assertEqual(CF.detect_sha_drift(item, None).signal_type, "manual_check")

    def test_non_ci_cleanup_policy_requires_ownership_and_verified_cleanup(self):
        policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8").split("### 2.10 ", 1)[1].split("## 3 ", 1)[0]
        for required in (
            "Pattern 25", "per-run inventory", "pre-existing/shared",
            "failure/interruption", "Verify each deletion", "stop creating replacements",
        ):
            self.assertIn(required, policy)
        self.assertIn("no new resources or live retries", policy)


if __name__ == "__main__":
    unittest.main()

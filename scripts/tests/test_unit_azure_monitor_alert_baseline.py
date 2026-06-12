"""Unit tests for azure-monitor-alert-baseline probe.

Source contract: awesome-gbb spec §4.3.1 + §4.3.3
Locked invocation contract: threadlight-skills sibling-skills-map.md row SRE-104
Locked return shape: awesome-gbb spec §4.3.1

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

`unittest discover` cannot resolve pytest fixtures (`monkeypatch`,
`tmp_path`) and silently emits 0 tests for files that use them.
Keep this file unittest-native so CI actually runs the assertions.
See `test_build_test_matrix.py` for the canonical pattern.

Mocking strategy
----------------
The probe internally calls `_load_baseline(kind)` to resolve the alert
baseline YAML for the given `alert_baseline_kind`.  Tests patch
`alert_probe._load_baseline` via `patch.object` inside each test and
supply minimal hand-rolled baseline dicts.  This keeps test logic
independent of the baseline YAML schema.

Exception: ``test_unknown_alert_baseline_kind_errored`` does NOT
override _load_baseline, because the probe must raise ValueError
naturally for unrecognised kinds and the never-raises wrapper must
catch it.

Azure SDK surface
-----------------
We mock `azure.mgmt.monitor.MonitorManagementClient` patched onto
`alert_probe.MonitorManagementClient`, and `alert_probe.DefaultAzureCredential`.
The relevant list method is:
    client.metric_alerts.list_by_resource_group(resource_group_name=...)
returning an iterable of MetricAlertResource objects.  Each mock alert
exposes at minimum: .name, .id, .criteria, .severity.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

# Load the skill's probe.py under a UNIQUE module name to avoid
# sys.modules collision with foundry-rbac-audit's probe.py when both
# test files run in the same `unittest discover` session.  Both modules
# are named 'probe' on disk — direct `import probe` caches whichever
# loads first and breaks the second file's patch.object targets.
_PROBE_PY = (Path(__file__).resolve().parents[2]
             / "skills" / "azure-monitor-alert-baseline"
             / "references" / "python" / "probe.py")
_spec = importlib.util.spec_from_file_location("alert_probe", _PROBE_PY)
alert_probe = importlib.util.module_from_spec(_spec)
sys.modules["alert_probe"] = alert_probe
_spec.loader.exec_module(alert_probe)
probe = alert_probe.probe  # alias public function so test bodies stay stable


# ---------- shape helpers (assert spec §4.3.1 contract) ----------

REQUIRED_TOP_LEVEL = {
    "finding_id", "scope", "result", "observations",
    "remediation_hints", "confidence", "probed_at", "error",
}
ALLOWED_RESULT = {"ok", "needs_attention", "errored"}
ALLOWED_CONFIDENCE = {0.0, 0.5, 1.0}
FINDING_ID = "SRE-104"


def _assert_shape(testcase: unittest.TestCase, result: dict) -> None:
    """Every probe() return must match spec §4.3.1 exactly."""
    missing = REQUIRED_TOP_LEVEL - result.keys()
    testcase.assertFalse(missing, f"missing top-level keys: {missing}")
    testcase.assertEqual(
        result["finding_id"], FINDING_ID,
        f"finding_id must be literal 'SRE-104', got {result['finding_id']!r}")
    testcase.assertIn(
        result["result"], ALLOWED_RESULT,
        f"result must be one of {ALLOWED_RESULT}, got {result['result']!r}")
    testcase.assertIsInstance(result["scope"], dict)
    testcase.assertTrue(
        {"subscription_id", "resource_group"}.issubset(result["scope"].keys()))
    testcase.assertIsInstance(result["observations"], list)
    testcase.assertTrue(
        all(isinstance(o, dict) for o in result["observations"]),
        "observations must be a list of dicts")
    testcase.assertIsInstance(result["remediation_hints"], list)
    testcase.assertTrue(all(isinstance(h, str) for h in result["remediation_hints"]))
    testcase.assertIn(
        result["confidence"], ALLOWED_CONFIDENCE,
        f"confidence must be one of {ALLOWED_CONFIDENCE}, got {result['confidence']!r}")
    # probed_at: ISO-8601, parseable, UTC-aware
    parsed = datetime.fromisoformat(result["probed_at"].replace("Z", "+00:00"))
    testcase.assertIsNotNone(parsed.tzinfo)
    # error: "" when result != "errored"; non-empty str when errored
    if result["result"] == "errored":
        testcase.assertIsInstance(result["error"], str)
        testcase.assertTrue(
            result["error"], "result=errored requires non-empty error string")
        testcase.assertEqual(
            result["confidence"], 0.0,
            f"errored result must have confidence=0.0, got {result['confidence']}")
        testcase.assertEqual(
            result["observations"], [],
            "errored result must have empty observations")
    else:
        testcase.assertEqual(
            result["error"], "",
            f"non-errored result must have error='', got {result['error']!r}")


# ---------- helpers for building mock alert objects ----------

def _make_alert(*, name: str, severity: int = 3, threshold: float = 5.0,
                alert_id: str = None):
    """Build a minimal MetricAlertResource mock."""
    alert = MagicMock()
    alert.name = name
    alert.id = alert_id or (
        f"/subscriptions/sub-id/resourceGroups/rg/providers"
        f"/microsoft.insights/metricAlerts/{name}")
    alert.severity = severity
    # criteria: a MagicMock whose .odata_type and .all_of are inspectable
    criteria = MagicMock()
    criterion = MagicMock()
    criterion.threshold = threshold
    criteria.all_of = [criterion]
    alert.criteria = criteria
    return alert


# Minimal baseline dicts used by individual tests
FOUNDRY_PILOT_BASELINE = {
    "kind": "foundry_pilot",
    "alert_rules": [
        {"name": "HighErrorRate",  "severity": 2, "max_threshold": 5.0},
        {"name": "LowAvailability", "severity": 1, "max_threshold": 1.0},
    ],
}

SPOKE_MINIMUM_BASELINE = {
    "kind": "spoke_minimum",
    "alert_rules": [
        {"name": "BasicErrorRate", "severity": 3, "max_threshold": 10.0},
    ],
}

PRODUCTION_BASELINE = {
    "kind": "production",
    "alert_rules": [
        {"name": "HighErrorRate",     "severity": 1, "max_threshold": 2.0},
        {"name": "LowAvailability",   "severity": 1, "max_threshold": 1.0},
        {"name": "HighLatencyP99",    "severity": 2, "max_threshold": 500.0},
    ],
}


# ---------- TestCase ----------

class TestAzureMonitorAlertBaselineProbe(unittest.TestCase):
    """Unit tests for azure-monitor-alert-baseline probe.

    setUp patches MonitorManagementClient + DefaultAzureCredential onto
    the loaded `alert_probe` module and chdirs into a fresh tempdir.
    tearDown restores cwd and stops every patch.

    Tests access the patched monitor client as ``self.fake_monitor`` and
    configure ``metric_alerts.list_by_resource_group`` behaviour per-test.
    Each test that exercises the success path additionally patches
    ``alert_probe._load_baseline`` via a `with patch.object(...)` block.
    """

    def setUp(self):
        # Mock SDK client; default: no alerts
        self.fake_monitor = MagicMock(name="MonitorManagementClient")
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = []
        self._monitor_patcher = patch.object(
            alert_probe, "MonitorManagementClient",
            lambda credential, subscription_id: self.fake_monitor)
        self._monitor_patcher.start()

        # Mock DefaultAzureCredential
        self._cred_patcher = patch.object(
            alert_probe, "DefaultAzureCredential",
            lambda: MagicMock(name="cred"))
        self._cred_patcher.start()

        # Isolated tempdir CWD so probe writes out/SRE-104.json under tmpdir
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir_ctx.name)
        self._saved_cwd = os.getcwd()
        os.chdir(self.tmp_path)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        self._tmpdir_ctx.cleanup()
        self._monitor_patcher.stop()
        self._cred_patcher.stop()

    # ---------- tests ----------

    def test_empty_rg_foundry_pilot_needs_attention_low_confidence(self):
        """Empty RG, baseline=foundry_pilot → needs_attention, confidence=0.5.

        No alerts at all is ambiguous (nothing-to-check vs RBAC-masked), so
        confidence is 0.5 per the controller-locked heuristic.  remediation_hints
        must reference the baseline kind name so the operator knows what to create.
        """
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = []
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(result["confidence"], 0.5)
        self.assertEqual(result["scope"]["subscription_id"], "sub-id")
        self.assertEqual(result["scope"]["resource_group"], "rg")
        self.assertTrue(
            any("foundry_pilot" in h for h in result["remediation_hints"]),
            "remediation_hints must reference the baseline kind name")
        self.assertIsInstance(result["observations"], list)

    def test_all_foundry_pilot_alerts_present_at_safe_thresholds_ok(self):
        """All foundry_pilot baseline alerts present and within threshold → ok, confidence=1.0."""
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            _make_alert(name="HighErrorRate",   severity=2, threshold=3.0),
            _make_alert(name="LowAvailability", severity=1, threshold=0.5),
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["confidence"], 1.0)
        problem_obs = [
            o for o in result["observations"]
            if o.get("kind") in ("missing", "threshold_mismatch")
        ]
        self.assertEqual(
            problem_obs, [], f"unexpected problem observations: {problem_obs}")

    def test_one_baseline_alert_missing(self):
        """One baseline alert absent → needs_attention, observations include missing record, confidence=1.0."""
        # Only HighErrorRate is present; LowAvailability is missing
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            _make_alert(name="HighErrorRate", severity=2, threshold=3.0),
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(result["confidence"], 1.0)
        missing_obs = [
            o for o in result["observations"] if o.get("kind") == "missing"
        ]
        self.assertGreaterEqual(
            len(missing_obs), 1, "expected at least one 'missing' observation")
        missing_names = {o.get("alert_name") for o in missing_obs}
        self.assertIn(
            "LowAvailability", missing_names,
            f"'LowAvailability' must be in missing observations, got {missing_names}")

    def test_alert_present_but_threshold_mismatched(self):
        """Alert exists but threshold exceeds baseline maximum → threshold_mismatch observation.

        Baseline requires HighErrorRate max_threshold ≤ 5.0, actual is 50.0.
        """
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            _make_alert(name="HighErrorRate",   severity=2, threshold=50.0),  # too loose
            _make_alert(name="LowAvailability", severity=1, threshold=0.5),
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(result["confidence"], 1.0)
        mismatch_obs = [
            o for o in result["observations"]
            if o.get("kind") == "threshold_mismatch"
        ]
        self.assertGreaterEqual(
            len(mismatch_obs), 1,
            "expected at least one 'threshold_mismatch' observation")
        obs = mismatch_obs[0]
        self.assertEqual(obs.get("alert_name"), "HighErrorRate")
        self.assertIn("expected", obs, "threshold_mismatch must carry 'expected' key")
        self.assertIn("actual", obs, "threshold_mismatch must carry 'actual' key")
        self.assertEqual(float(obs["actual"]), 50.0)

    def test_multiple_alerts_missing_and_mismatched(self):
        """Multiple alerts missing AND one with bad threshold → observations count > 1, confidence=1.0."""
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            # HighErrorRate present but threshold too loose
            _make_alert(name="HighErrorRate", severity=2, threshold=999.0),
            # LowAvailability is missing entirely
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(result["confidence"], 1.0)
        self.assertGreater(
            len(result["observations"]), 1,
            f"expected multiple observations, got {len(result['observations'])}: {result['observations']}")

    def test_spoke_minimum_baseline_kind_dispatches(self):
        """baseline_kind=spoke_minimum exercises the kind-dispatch path.

        The baseline kind name must appear in observations or remediation_hints
        so the operator knows which baseline was evaluated.
        """
        # One alert matching the spoke_minimum baseline
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            _make_alert(name="BasicErrorRate", severity=3, threshold=5.0),
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: SPOKE_MINIMUM_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="spoke_minimum",
            )

        _assert_shape(self, result)
        self.assertIn(result["result"], ALLOWED_RESULT)
        # The baseline kind must be traceable in the output
        kind_visible = (
            any("spoke_minimum" in str(o) for o in result["observations"])
            or any("spoke_minimum" in h for h in result["remediation_hints"])
            or result["scope"].get("alert_baseline_kind") == "spoke_minimum"
        )
        self.assertTrue(
            kind_visible,
            "spoke_minimum kind must appear in observations, remediation_hints, or scope")

    def test_production_baseline_kind_dispatches(self):
        """baseline_kind=production exercises the production tier dispatch path."""
        # All three production alerts present and within threshold
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = [
            _make_alert(name="HighErrorRate",   severity=1, threshold=1.0),
            _make_alert(name="LowAvailability", severity=1, threshold=0.5),
            _make_alert(name="HighLatencyP99",  severity=2, threshold=300.0),
        ]
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: PRODUCTION_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="production",
            )

        _assert_shape(self, result)
        self.assertIn(result["result"], ALLOWED_RESULT)
        # Three rules evaluated → confidence must be 1.0
        self.assertEqual(result["confidence"], 1.0)

    def test_never_raises_on_auth_failure(self):
        """ClientAuthenticationError from list_by_resource_group → errored, confidence=0.0.

        probe() must NEVER raise; any Azure exception is caught and surfaced
        as result=errored with the exception class name in the error field.
        """
        from azure.core.exceptions import ClientAuthenticationError
        self.fake_monitor.metric_alerts.list_by_resource_group.side_effect = (
            ClientAuthenticationError("AADSTS70011: credential invalid"))

        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "errored")
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["observations"], [])
        self.assertIn(
            "ClientAuthenticationError", result["error"],
            f"error field must contain exception type name, got: {result['error']!r}")

    def test_unknown_alert_baseline_kind_errored(self):
        """An unrecognised alert_baseline_kind → result=errored, error describes the bad kind.

        This test does NOT mock _load_baseline — probe must raise ValueError
        internally and the never-raises wrapper surfaces it as result=errored.
        This defends against typos in threadlight invocations.
        """
        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            alert_baseline_kind="made_up_kind",
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "errored")
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["observations"], [])
        self.assertIn(
            "made_up_kind", result["error"],
            f"error must mention the unrecognised kind 'made_up_kind', got: {result['error']!r}")
        self.assertIn(
            "ValueError", result["error"],
            f"error must cite ValueError, got: {result['error']!r}")

    def test_manifest_file_written_as_sre104_json(self):
        """probe() writes out/SRE-104.json relative to CWD; content matches the returned dict."""
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = []
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )
        _assert_shape(self, result)

        manifest = self.tmp_path / "out" / "SRE-104.json"
        self.assertTrue(
            manifest.exists(),
            f"expected manifest at {manifest} but file is absent")
        parsed = json.loads(manifest.read_text())
        _assert_shape(self, parsed)
        self.assertEqual(parsed["finding_id"], FINDING_ID)
        self.assertEqual(parsed["scope"], result["scope"])
        self.assertEqual(parsed["result"], result["result"])
        self.assertEqual(parsed["confidence"], result["confidence"])
        self.assertEqual(parsed["probed_at"], result["probed_at"])

    def test_keyword_only_invocation_contract(self):
        """Probe must accept both positional and keyword call forms.

        Positional: probe("sub", "rg", "foundry_pilot")
        Keyword:    probe(subscription_id="sub", resource_group="rg", alert_baseline_kind="foundry_pilot")

        The `credential` parameter is keyword-only (after `*`) — passing it
        positionally MUST raise TypeError.
        """
        self.fake_monitor.metric_alerts.list_by_resource_group.return_value = []
        custom_cred = MagicMock(name="custom-credential")

        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            # Positional form must work
            r_pos = probe("sub-id", "rg", "foundry_pilot")
            _assert_shape(self, r_pos)

            # Keyword form must work
            r_kw = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )
            _assert_shape(self, r_kw)

            # credential is keyword-only; a 4th positional arg MUST raise TypeError
            with self.assertRaises(TypeError):
                probe("sub-id", "rg", "foundry_pilot", custom_cred)

            # Passing credential as a kwarg must be accepted
            r_cred = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
                credential=custom_cred,
            )
            _assert_shape(self, r_cred)

    def test_never_raises_on_generic_sdk_error(self):
        """Any unexpected exception from the monitor SDK must be caught and surfaced.

        This is the second never-raises test (complementing test_never_raises_on_auth_failure).
        Uses a generic RuntimeError to ensure the catch-all path works beyond
        Azure-specific exception classes.
        """
        self.fake_monitor.metric_alerts.list_by_resource_group.side_effect = (
            RuntimeError("unexpected SDK internal error"))
        with patch.object(alert_probe, "_load_baseline",
                          lambda kind: FOUNDRY_PILOT_BASELINE):
            result = probe(
                subscription_id="sub-id",
                resource_group="rg",
                alert_baseline_kind="foundry_pilot",
            )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "errored")
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["observations"], [])
        self.assertIn(
            "RuntimeError", result["error"],
            f"error must name the exception class, got: {result['error']!r}")
        self.assertIn(
            "unexpected SDK internal error", result["error"],
            f"error must include the exception message, got: {result['error']!r}")


if __name__ == "__main__":
    unittest.main()

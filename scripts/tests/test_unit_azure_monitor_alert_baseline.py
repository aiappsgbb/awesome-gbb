"""Unit tests for azure-monitor-alert-baseline probe.

Source contract: awesome-gbb spec §4.3.1 + §4.3.3
Locked invocation contract: threadlight-skills sibling-skills-map.md row SRE-104
Locked return shape: awesome-gbb spec §4.3.1

These tests MUST fail initially (probe.py not implemented yet — TDD red).
Task 2.3 will make them GREEN.

Mocking strategy
----------------
The probe internally calls `_load_baseline(kind)` to resolve the alert
baseline YAML for the given `alert_baseline_kind`.  Since the baseline
YAMLs (Task 2.2) and probe.py (Task 2.3) do not yet exist, tests patch
`probe._load_baseline` via `monkeypatch.setattr` and supply minimal
hand-rolled baseline dicts.  This keeps test logic independent of the
YAML schema — when Task 2.2 ships, the only thing that changes is the
real `_load_baseline` implementation, NOT the tests.

Exception: test_unknown_alert_baseline_kind does NOT mock _load_baseline,
because the probe must raise ValueError naturally for unrecognised kinds
and the never-raises wrapper must catch it.

Azure SDK surface
-----------------
We mock `azure.mgmt.monitor.MonitorManagementClient` patched onto
`probe.MonitorManagementClient`, and `probe.DefaultAzureCredential`.
The relevant list method is:
    client.metric_alerts.list_by_resource_group(resource_group_name=...)
returning an iterable of MetricAlertResource objects.  Each mock alert
exposes at minimum: .name, .id, .criteria, .severity.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make the skill's probe importable without a setup.py
SKILL_DIR = (Path(__file__).resolve().parents[2]
             / "skills" / "azure-monitor-alert-baseline" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe  # noqa: E402


# ---------- shape helpers (assert spec §4.3.1 contract) ----------

REQUIRED_TOP_LEVEL = {
    "finding_id", "scope", "result", "observations",
    "remediation_hints", "confidence", "probed_at", "error",
}
ALLOWED_RESULT = {"ok", "needs_attention", "errored"}
ALLOWED_CONFIDENCE = {0.0, 0.5, 1.0}
FINDING_ID = "SRE-104"


def _assert_shape(result: dict) -> None:
    """Every probe() return must match spec §4.3.1 exactly."""
    missing = REQUIRED_TOP_LEVEL - result.keys()
    assert not missing, f"missing top-level keys: {missing}"
    assert result["finding_id"] == FINDING_ID, \
        f"finding_id must be literal 'SRE-104', got {result['finding_id']!r}"
    assert result["result"] in ALLOWED_RESULT, \
        f"result must be one of {ALLOWED_RESULT}, got {result['result']!r}"
    assert isinstance(result["scope"], dict)
    assert {"subscription_id", "resource_group"}.issubset(result["scope"].keys())
    assert isinstance(result["observations"], list)
    assert all(isinstance(o, dict) for o in result["observations"]), \
        "observations must be a list of dicts"
    assert isinstance(result["remediation_hints"], list)
    assert all(isinstance(h, str) for h in result["remediation_hints"])
    assert result["confidence"] in ALLOWED_CONFIDENCE, \
        f"confidence must be one of {ALLOWED_CONFIDENCE}, got {result['confidence']!r}"
    # probed_at: ISO-8601, parseable, UTC-aware
    parsed = datetime.fromisoformat(result["probed_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    # error: "" when result != "errored"; non-empty str when errored
    if result["result"] == "errored":
        assert isinstance(result["error"], str) and result["error"], \
            "result=errored requires non-empty error string"
        assert result["confidence"] == 0.0, \
            f"errored result must have confidence=0.0, got {result['confidence']}"
        assert result["observations"] == [], \
            "errored result must have empty observations"
    else:
        assert result["error"] == "", \
            f"non-errored result must have error='', got {result['error']!r}"


# ---------- helpers for building mock alert objects ----------

def _make_alert(*, name: str, severity: int = 3, threshold: float = 5.0, alert_id: str = None):
    """Build a minimal MetricAlertResource mock."""
    alert = MagicMock()
    alert.name = name
    alert.id = alert_id or f"/subscriptions/sub-id/resourceGroups/rg/providers/microsoft.insights/metricAlerts/{name}"
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


# ---------- shared fixture: mock the Monitor SDK client ----------

@pytest.fixture
def fake_monitor(monkeypatch):
    """Patch MonitorManagementClient + DefaultAzureCredential.

    Returns the monitor MagicMock so individual tests can configure
    metric_alerts.list_by_resource_group behaviour.
    """
    monitor = MagicMock(name="MonitorManagementClient")
    # Default: no alerts present
    monitor.metric_alerts.list_by_resource_group.return_value = []
    monkeypatch.setattr("probe.MonitorManagementClient",
                        lambda credential, subscription_id: monitor)
    monkeypatch.setattr("probe.DefaultAzureCredential", lambda: MagicMock(name="cred"))
    return monitor


# ---------- tests ----------

def test_empty_rg_foundry_pilot_needs_attention_low_confidence(
    fake_monitor, tmp_path, monkeypatch
):
    """Empty RG, baseline=foundry_pilot → needs_attention, confidence=0.5.

    No alerts at all is ambiguous (nothing-to-check vs RBAC-masked), so
    confidence is 0.5 per the controller-locked heuristic.  remediation_hints
    must reference the baseline kind name so the operator knows what to create.
    """
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = []
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert result["confidence"] == 0.5
    assert result["scope"]["subscription_id"] == "sub-id"
    assert result["scope"]["resource_group"] == "rg"
    # At least one remediation hint must mention the baseline kind
    assert any("foundry_pilot" in h for h in result["remediation_hints"]), \
        "remediation_hints must reference the baseline kind name"
    # Observations describe the missing alerts (or are empty — both are acceptable
    # when confidence=0.5 means "no data"; probe impl decides the detail level)
    assert isinstance(result["observations"], list)


def test_all_foundry_pilot_alerts_present_at_safe_thresholds_ok(
    fake_monitor, tmp_path, monkeypatch
):
    """All foundry_pilot baseline alerts present and within threshold → ok, confidence=1.0."""
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        _make_alert(name="HighErrorRate",   severity=2, threshold=3.0),
        _make_alert(name="LowAvailability", severity=1, threshold=0.5),
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "ok"
    assert result["confidence"] == 1.0
    # No problematic observations expected when every alert is within threshold
    problem_obs = [o for o in result["observations"] if o.get("kind") in ("missing", "threshold_mismatch")]
    assert problem_obs == [], f"unexpected problem observations: {problem_obs}"


def test_one_baseline_alert_missing(fake_monitor, tmp_path, monkeypatch):
    """One baseline alert absent → needs_attention, observations include missing record, confidence=1.0.

    The probe compared at least one rule against reality (HighErrorRate found,
    LowAvailability absent) → confidence=1.0 per the controller heuristic.
    """
    monkeypatch.chdir(tmp_path)
    # Only HighErrorRate is present; LowAvailability is missing
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        _make_alert(name="HighErrorRate", severity=2, threshold=3.0),
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert result["confidence"] == 1.0
    missing_obs = [o for o in result["observations"] if o.get("kind") == "missing"]
    assert len(missing_obs) >= 1, "expected at least one 'missing' observation"
    missing_names = {o.get("alert_name") for o in missing_obs}
    assert "LowAvailability" in missing_names, \
        f"'LowAvailability' must be in missing observations, got {missing_names}"


def test_alert_present_but_threshold_mismatched(fake_monitor, tmp_path, monkeypatch):
    """Alert exists but threshold exceeds baseline maximum → threshold_mismatch observation.

    Baseline requires HighErrorRate max_threshold ≤ 5.0, actual is 50.0.
    """
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        _make_alert(name="HighErrorRate",   severity=2, threshold=50.0),  # too loose
        _make_alert(name="LowAvailability", severity=1, threshold=0.5),
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert result["confidence"] == 1.0
    mismatch_obs = [o for o in result["observations"] if o.get("kind") == "threshold_mismatch"]
    assert len(mismatch_obs) >= 1, "expected at least one 'threshold_mismatch' observation"
    obs = mismatch_obs[0]
    assert obs.get("alert_name") == "HighErrorRate"
    assert "expected" in obs, "threshold_mismatch must carry 'expected' key"
    assert "actual" in obs,   "threshold_mismatch must carry 'actual' key"
    assert float(obs["actual"]) == 50.0


def test_multiple_alerts_missing_and_mismatched(fake_monitor, tmp_path, monkeypatch):
    """Multiple alerts missing AND one with bad threshold → observations count > 1, confidence=1.0."""
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        # HighErrorRate present but threshold too loose
        _make_alert(name="HighErrorRate", severity=2, threshold=999.0),
        # LowAvailability is missing entirely
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert result["confidence"] == 1.0
    assert len(result["observations"]) > 1, \
        f"expected multiple observations, got {len(result['observations'])}: {result['observations']}"


def test_spoke_minimum_baseline_kind_dispatches(fake_monitor, tmp_path, monkeypatch):
    """baseline_kind=spoke_minimum exercises the kind-dispatch path.

    The baseline kind name must appear in observations or remediation_hints
    so the operator knows which baseline was evaluated.
    """
    monkeypatch.chdir(tmp_path)
    # One alert matching the spoke_minimum baseline
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        _make_alert(name="BasicErrorRate", severity=3, threshold=5.0),
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: SPOKE_MINIMUM_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="spoke_minimum",
    )

    _assert_shape(result)
    # Result may be ok or needs_attention depending on impl detail; shape is what matters
    assert result["result"] in ALLOWED_RESULT
    # The baseline kind must be traceable in the output
    kind_visible = (
        any("spoke_minimum" in str(o) for o in result["observations"])
        or any("spoke_minimum" in h for h in result["remediation_hints"])
        or result["scope"].get("alert_baseline_kind") == "spoke_minimum"
    )
    assert kind_visible, \
        "spoke_minimum kind must appear in observations, remediation_hints, or scope"


def test_production_baseline_kind_dispatches(fake_monitor, tmp_path, monkeypatch):
    """baseline_kind=production exercises the production tier dispatch path."""
    monkeypatch.chdir(tmp_path)
    # All three production alerts present and within threshold
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        _make_alert(name="HighErrorRate",   severity=1, threshold=1.0),
        _make_alert(name="LowAvailability", severity=1, threshold=0.5),
        _make_alert(name="HighLatencyP99",  severity=2, threshold=300.0),
    ]
    monkeypatch.setattr("probe._load_baseline", lambda kind: PRODUCTION_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="production",
    )

    _assert_shape(result)
    assert result["result"] in ALLOWED_RESULT
    # Three rules evaluated → confidence must be 1.0
    assert result["confidence"] == 1.0


def test_never_raises_on_auth_failure(fake_monitor, tmp_path, monkeypatch):
    """ClientAuthenticationError from list_by_resource_group → errored, confidence=0.0.

    probe() must NEVER raise; any Azure exception is caught and surfaced
    as result=errored with the exception class name in the error field.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    # Simulate azure.core.exceptions.ClientAuthenticationError
    from azure.core.exceptions import ClientAuthenticationError
    fake_monitor.metric_alerts.list_by_resource_group.side_effect = \
        ClientAuthenticationError("AADSTS70011: credential invalid")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "errored"
    assert result["confidence"] == 0.0
    assert result["observations"] == []
    assert "ClientAuthenticationError" in result["error"], \
        f"error field must contain exception type name, got: {result['error']!r}"


def test_unknown_alert_baseline_kind_errored(fake_monitor, tmp_path, monkeypatch):
    """An unrecognised alert_baseline_kind → result=errored, error describes the bad kind.

    This test does NOT mock _load_baseline — probe must raise ValueError
    internally and the never-raises wrapper surfaces it as error=errored.
    This defends against typos in threadlight invocations.
    """
    monkeypatch.chdir(tmp_path)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="made_up_kind",
    )

    _assert_shape(result)
    assert result["result"] == "errored"
    assert result["confidence"] == 0.0
    assert result["observations"] == []
    # error field must describe the bad kind
    assert "made_up_kind" in result["error"], \
        f"error must mention the unrecognised kind 'made_up_kind', got: {result['error']!r}"
    # A ValueError is the expected exception class for this defensive check
    assert "ValueError" in result["error"], \
        f"error must cite ValueError, got: {result['error']!r}"


def test_manifest_file_written_as_sre104_json(fake_monitor, tmp_path, monkeypatch):
    """probe() writes out/SRE-104.json relative to CWD; content matches the returned dict.

    Uses monkeypatch.chdir(tmp_path) so CWD is isolated from the repo.
    The finding-ID-literal filename means repeated calls overwrite the
    same file — intentional behaviour per spec (not tested here explicitly;
    see test_repeated_probe_overwrites_same_manifest_file).
    """
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = []
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )
    _assert_shape(result)

    manifest = tmp_path / "out" / "SRE-104.json"
    assert manifest.exists(), f"expected manifest at {manifest} but file is absent"
    parsed = json.loads(manifest.read_text())
    # Structural parity with the returned dict
    _assert_shape(parsed)
    assert parsed["finding_id"] == FINDING_ID
    assert parsed["scope"] == result["scope"]
    assert parsed["result"] == result["result"]
    assert parsed["confidence"] == result["confidence"]
    assert parsed["probed_at"] == result["probed_at"]


def test_keyword_only_invocation_contract(fake_monitor, tmp_path, monkeypatch):
    """Probe must accept both positional and keyword call forms.

    Positional: probe("sub", "rg", "foundry_pilot")
    Keyword:    probe(subscription_id="sub", resource_group="rg", alert_baseline_kind="foundry_pilot")

    The `credential` parameter is keyword-only (after `*`) — passing it
    positionally MUST raise TypeError.
    """
    monkeypatch.chdir(tmp_path)
    fake_monitor.metric_alerts.list_by_resource_group.return_value = []
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)

    # Positional form must work
    r_pos = probe("sub-id", "rg", "foundry_pilot")
    _assert_shape(r_pos)

    # Keyword form must work
    r_kw = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )
    _assert_shape(r_kw)

    # credential is keyword-only; passing a 4th positional arg MUST raise TypeError
    custom_cred = MagicMock(name="custom-credential")
    with pytest.raises(TypeError):
        probe("sub-id", "rg", "foundry_pilot", custom_cred)

    # Passing credential as a kwarg must be accepted
    r_cred = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
        credential=custom_cred,
    )
    _assert_shape(r_cred)


def test_never_raises_on_generic_sdk_error(fake_monitor, tmp_path, monkeypatch):
    """Any unexpected exception from the monitor SDK must be caught and surfaced.

    This is the second never-raises test (complementing test_never_raises_on_auth_failure).
    Uses a generic RuntimeError to ensure the catch-all path works beyond
    Azure-specific exception classes.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("probe._load_baseline", lambda kind: FOUNDRY_PILOT_BASELINE)
    fake_monitor.metric_alerts.list_by_resource_group.side_effect = RuntimeError(
        "unexpected SDK internal error"
    )

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        alert_baseline_kind="foundry_pilot",
    )

    _assert_shape(result)
    assert result["result"] == "errored"
    assert result["confidence"] == 0.0
    assert result["observations"] == []
    assert "RuntimeError" in result["error"], \
        f"error must name the exception class, got: {result['error']!r}"
    assert "unexpected SDK internal error" in result["error"], \
        f"error must include the exception message, got: {result['error']!r}"

"""Unit tests for foundry-rbac-audit probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/268
Locked invocation contract: threadlight-skills sibling-skills-map.md row IAM-101
Locked return shape: awesome-gbb spec §4.3.1

These tests MUST fail initially (probe.py not implemented yet — TDD red).
Task 1.2 will make them GREEN.
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
             / "skills" / "foundry-rbac-audit" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe  # noqa: E402


# ---------- shape helpers (assert spec §4.3.1 contract) ----------

REQUIRED_TOP_LEVEL = {
    "finding_id", "scope", "result", "observations",
    "remediation_hints", "confidence", "probed_at", "error",
}
ALLOWED_RESULT = {"ok", "needs_attention", "errored"}
ALLOWED_CONFIDENCE = {0.0, 0.5, 1.0}

# Role definition IDs we use repeatedly in fixtures
OWNER_ROLE_ID = "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
CONTRIBUTOR_ROLE_ID = "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"
READER_ROLE_ID = "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/acdd72a7-3385-48ef-bd42-f606fba81ae7"
UAA_ROLE_ID = "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"  # User Access Administrator
RBAC_ADMIN_ROLE_ID = "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/f58310d9-a9f6-439a-9e8d-f62e7b41a168"


def _assert_shape(result: dict) -> None:
    """Every probe() return must match spec §4.3.1 exactly."""
    missing = REQUIRED_TOP_LEVEL - result.keys()
    assert not missing, f"missing top-level keys: {missing}"
    assert result["finding_id"] == "IAM-101", \
        f"finding_id must be literal 'IAM-101', got {result['finding_id']!r}"
    assert result["result"] in ALLOWED_RESULT, \
        f"result must be one of {ALLOWED_RESULT}, got {result['result']!r}"
    assert isinstance(result["scope"], dict)
    assert {"subscription_id", "resource_group"}.issubset(result["scope"].keys())
    assert isinstance(result["observations"], list)
    assert isinstance(result["remediation_hints"], list)
    assert all(isinstance(h, str) for h in result["remediation_hints"])
    assert result["confidence"] in ALLOWED_CONFIDENCE, \
        f"confidence must be one of {ALLOWED_CONFIDENCE}, got {result['confidence']!r}"
    # probed_at: ISO-8601, parseable, UTC-aware
    parsed = datetime.fromisoformat(result["probed_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    # error: None when result != "errored"; str when errored
    if result["result"] == "errored":
        assert isinstance(result["error"], str) and result["error"], \
            "result=errored requires non-empty error string"
        assert result["confidence"] == 0.0
    else:
        assert result["error"] is None


def _make_assignment(*, principal_id, principal_type, role_definition_id, scope=None):
    a = MagicMock()
    a.principal_id = principal_id
    a.principal_type = principal_type
    a.role_definition_id = role_definition_id
    a.scope = scope or "/subscriptions/sub-id/resourceGroups/rg"
    return a


# ---------- shared fixture: mock the SDK clients ----------

@pytest.fixture
def fake_clients(monkeypatch):
    """Patch AuthorizationManagementClient + DefaultAzureCredential.

    Returns the authorization mock so individual tests can configure
    role_assignments.list_for_scope and role_definitions.get behaviour.
    """
    auth = MagicMock(name="AuthorizationManagementClient")
    # Default: role_definitions.get returns a stub with .role_name extractable
    auth.role_definitions.get.return_value = MagicMock(role_name="Contributor")
    monkeypatch.setattr("probe.AuthorizationManagementClient",
                        lambda credential, subscription_id: auth)
    monkeypatch.setattr("probe.DefaultAzureCredential", lambda: MagicMock(name="cred"))
    return auth


# ---------- tests ----------

def test_happy_path_only_reader_assignments(fake_clients, tmp_path, monkeypatch):
    """RG with only Reader assignments → result=ok, observations=[], confidence=1.0."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="11111111-1111-1111-1111-111111111111",
            principal_type="User",
            role_definition_id=READER_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(role_name="Reader")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user", "service_principal"],
    )

    _assert_shape(result)
    assert result["result"] == "ok"
    assert result["observations"] == []
    assert result["confidence"] == 1.0
    assert result["scope"]["subscription_id"] == "sub-id"
    assert result["scope"]["resource_group"] == "rg"


def test_owner_at_rg_flagged_as_observation(fake_clients, tmp_path, monkeypatch):
    """Owner role at RG scope on a user → flagged in observations, result=needs_attention."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="22222222-2222-2222-2222-222222222222",
            principal_type="User",
            role_definition_id=OWNER_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert len(result["observations"]) == 1
    obs = result["observations"][0]
    assert obs["principal_id"] == "22222222-2222-2222-2222-222222222222"
    assert obs["role_definition_id"] == OWNER_ROLE_ID
    assert obs.get("severity") in ("high", "critical")
    # At least one remediation hint when there are observations
    assert len(result["remediation_hints"]) >= 1


def test_user_access_admin_flagged_as_privilege_escalation(fake_clients, tmp_path, monkeypatch):
    """User Access Administrator at any scope is a privilege-escalation vector."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="33333333-3333-3333-3333-333333333333",
            principal_type="ServicePrincipal",
            role_definition_id=UAA_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(role_name="User Access Administrator")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["service_principal"],
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert any(UAA_ROLE_ID in o.get("role_definition_id", "") for o in result["observations"])


def test_rbac_administrator_flagged(fake_clients, tmp_path, monkeypatch):
    """Role Based Access Control Administrator is also a privilege-escalation vector."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="44444444-4444-4444-4444-444444444444",
            principal_type="ServicePrincipal",
            role_definition_id=RBAC_ADMIN_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(
        role_name="Role Based Access Control Administrator")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["service_principal"],
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert len(result["observations"]) >= 1


def test_target_principal_types_filter_excludes_groups(fake_clients, tmp_path, monkeypatch):
    """A Group assignment is excluded when target_principal_types=['user']."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="55555555-5555-5555-5555-555555555555",
            principal_type="Group",
            role_definition_id=OWNER_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],   # excludes Group
    )

    _assert_shape(result)
    # Group assignment filtered out → no observations from it
    assert result["observations"] == []
    # No assignments matched at all → empty-RG semantics (confidence=0.5)
    assert result["confidence"] == 0.5
    assert result["result"] == "ok"


def test_target_principal_types_filter_includes_managed_identity(fake_clients, tmp_path, monkeypatch):
    """A managed-identity Owner assignment IS flagged when MI is in the filter."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = [
        _make_assignment(
            principal_id="66666666-6666-6666-6666-666666666666",
            principal_type="ServicePrincipal",   # MIs surface as SP in the SDK
            role_definition_id=OWNER_ROLE_ID,
        ),
    ]
    fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["managed_identity", "service_principal"],
    )

    _assert_shape(result)
    assert result["result"] == "needs_attention"
    assert len(result["observations"]) == 1


def test_empty_rg_returns_ok_with_low_confidence(fake_clients, tmp_path, monkeypatch):
    """Zero assignments in scope → result=ok, observations=[], confidence=0.5 (ambiguous)."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = []

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user", "service_principal"],
    )

    _assert_shape(result)
    assert result["result"] == "ok"
    assert result["observations"] == []
    assert result["confidence"] == 0.5
    assert result["error"] is None


def test_never_raises_on_authorization_failed(fake_clients, tmp_path, monkeypatch):
    """403 from list_for_scope → result=errored, confidence=0.0, error populated, returns dict."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.side_effect = RuntimeError(
        "AuthorizationFailed: caller does not have permission to read role assignments")

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
    )

    _assert_shape(result)
    assert result["result"] == "errored"
    assert result["confidence"] == 0.0
    assert "AuthorizationFailed" in result["error"]
    assert "RuntimeError" in result["error"]
    assert result["observations"] == []
    assert result["remediation_hints"] == []


def test_manifest_file_written_with_finding_id_literal_filename(fake_clients, tmp_path, monkeypatch):
    """probe() writes out/IAM-101.json relative to CWD with the same dict."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = []

    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
    )
    _assert_shape(result)

    manifest = tmp_path / "out" / "IAM-101.json"
    assert manifest.exists(), f"expected manifest at {manifest}, got missing"
    parsed = json.loads(manifest.read_text())
    assert parsed["finding_id"] == "IAM-101"
    assert parsed["scope"] == result["scope"]
    assert parsed["result"] == result["result"]
    assert parsed["confidence"] == result["confidence"]


def test_repeated_probe_overwrites_same_manifest_file(fake_clients, tmp_path, monkeypatch):
    """Two probe() calls overwrite the SAME out/IAM-101.json — finding_id is taxonomy literal."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = []

    r1 = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
    )
    _assert_shape(r1)

    r2 = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
    )
    _assert_shape(r2)

    # Same finding_id always
    assert r1["finding_id"] == r2["finding_id"] == "IAM-101"
    # Only one manifest file exists, and it matches the second call
    manifests = list((tmp_path / "out").iterdir())
    assert [m.name for m in manifests] == ["IAM-101.json"]
    parsed = json.loads(manifests[0].read_text())
    assert parsed["probed_at"] == r2["probed_at"]


def test_credential_kwarg_is_keyword_only(fake_clients, tmp_path, monkeypatch):
    """The credential parameter MUST be keyword-only to match the locked contract."""
    monkeypatch.chdir(tmp_path)
    fake_clients.role_assignments.list_for_scope.return_value = []

    custom_cred = MagicMock(name="custom-credential")
    # This should work — credential passed as kwarg
    result = probe(
        subscription_id="sub-id",
        resource_group="rg",
        target_principal_types=["user"],
        credential=custom_cred,
    )
    _assert_shape(result)

    # This MUST raise TypeError — positional credential not allowed
    with pytest.raises(TypeError):
        probe("sub-id", "rg", ["user"], custom_cred)

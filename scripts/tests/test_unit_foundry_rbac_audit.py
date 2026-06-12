"""Unit tests for foundry-rbac-audit probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/268
Locked invocation contract: threadlight-skills sibling-skills-map.md row IAM-101
Locked return shape: awesome-gbb spec §4.3.1

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

`unittest discover` cannot resolve pytest fixtures (`monkeypatch`,
`tmp_path`) and silently emits 0 tests for files that use them.
Keep this file unittest-native so CI actually runs the assertions.
See `test_build_test_matrix.py` for the canonical pattern.
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
# sys.modules collision with azure-monitor-alert-baseline's probe.py
# when both test files run in the same `unittest discover` session.
# Both modules are named 'probe' on disk — direct `import probe` caches
# whichever loads first and breaks the second file's patch.object targets.
_PROBE_PY = (Path(__file__).resolve().parents[2]
             / "skills" / "foundry-rbac-audit"
             / "references" / "python" / "probe.py")
_spec = importlib.util.spec_from_file_location("rbac_probe", _PROBE_PY)
rbac_probe = importlib.util.module_from_spec(_spec)
sys.modules["rbac_probe"] = rbac_probe
_spec.loader.exec_module(rbac_probe)
probe = rbac_probe.probe  # alias public function so test bodies stay stable


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
FINDING_ID = "IAM-101"


def _assert_shape(testcase: unittest.TestCase, result: dict) -> None:
    """Every probe() return must match spec §4.3.1 exactly."""
    missing = REQUIRED_TOP_LEVEL - result.keys()
    testcase.assertFalse(missing, f"missing top-level keys: {missing}")
    testcase.assertEqual(
        result["finding_id"], "IAM-101",
        f"finding_id must be literal 'IAM-101', got {result['finding_id']!r}")
    testcase.assertIn(
        result["result"], ALLOWED_RESULT,
        f"result must be one of {ALLOWED_RESULT}, got {result['result']!r}")
    testcase.assertIsInstance(result["scope"], dict)
    testcase.assertTrue(
        {"subscription_id", "resource_group"}.issubset(result["scope"].keys()))
    testcase.assertIsInstance(result["observations"], list)
    testcase.assertIsInstance(result["remediation_hints"], list)
    testcase.assertTrue(all(isinstance(h, str) for h in result["remediation_hints"]))
    testcase.assertIn(
        result["confidence"], ALLOWED_CONFIDENCE,
        f"confidence must be one of {ALLOWED_CONFIDENCE}, got {result['confidence']!r}")
    # probed_at: ISO-8601, parseable, UTC-aware
    parsed = datetime.fromisoformat(result["probed_at"].replace("Z", "+00:00"))
    testcase.assertIsNotNone(parsed.tzinfo)
    # error: None when result != "errored"; str when errored
    if result["result"] == "errored":
        testcase.assertIsInstance(result["error"], str)
        testcase.assertTrue(
            result["error"], "result=errored requires non-empty error string")
        testcase.assertEqual(result["confidence"], 0.0)
    else:
        testcase.assertIsNone(result["error"])


def _make_assignment(*, principal_id, principal_type, role_definition_id, scope=None):
    a = MagicMock()
    a.principal_id = principal_id
    a.principal_type = principal_type
    a.role_definition_id = role_definition_id
    a.scope = scope or "/subscriptions/sub-id/resourceGroups/rg"
    return a


# ---------- TestCase ----------

class TestFoundryRbacAuditProbe(unittest.TestCase):
    """Unit tests for foundry-rbac-audit probe.

    setUp patches AuthorizationManagementClient + DefaultAzureCredential
    onto the loaded `rbac_probe` module and chdirs into a fresh tempdir.
    tearDown restores cwd and stops every patch.

    Tests access the patched auth client as ``self.fake_clients`` and
    configure ``role_assignments.list_for_scope`` and ``role_definitions.get``
    behaviour per-test.
    """

    def setUp(self):
        # Mock SDK client
        self.fake_clients = MagicMock(name="AuthorizationManagementClient")
        self.fake_clients.role_definitions.get.return_value = MagicMock(
            role_name="Contributor")
        self._auth_patcher = patch.object(
            rbac_probe, "AuthorizationManagementClient",
            lambda credential, subscription_id: self.fake_clients)
        self._auth_patcher.start()

        # Mock DefaultAzureCredential
        self._cred_patcher = patch.object(
            rbac_probe, "DefaultAzureCredential",
            lambda: MagicMock(name="cred"))
        self._cred_patcher.start()

        # Isolated tempdir CWD so probe writes out/IAM-101.json under tmpdir
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir_ctx.name)
        self._saved_cwd = os.getcwd()
        os.chdir(self.tmp_path)

    def tearDown(self):
        os.chdir(self._saved_cwd)
        self._tmpdir_ctx.cleanup()
        self._auth_patcher.stop()
        self._cred_patcher.stop()

    # ---------- tests ----------

    def test_happy_path_only_reader_assignments(self):
        """RG with only Reader assignments → result=ok, observations=[], confidence=1.0."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="11111111-1111-1111-1111-111111111111",
                principal_type="User",
                role_definition_id=READER_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(
            role_name="Reader")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user", "service_principal"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["scope"]["subscription_id"], "sub-id")
        self.assertEqual(result["scope"]["resource_group"], "rg")

    def test_owner_at_rg_flagged_as_observation(self):
        """Owner role at RG scope on a user → flagged in observations, result=needs_attention."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="22222222-2222-2222-2222-222222222222",
                principal_type="User",
                role_definition_id=OWNER_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(len(result["observations"]), 1)
        obs = result["observations"][0]
        self.assertEqual(
            obs["principal_id"], "22222222-2222-2222-2222-222222222222")
        self.assertEqual(obs["role_definition_id"], OWNER_ROLE_ID)
        self.assertIn(obs.get("severity"), ("high", "critical"))
        self.assertGreaterEqual(len(result["remediation_hints"]), 1)

    def test_user_access_admin_flagged_as_privilege_escalation(self):
        """User Access Administrator at any scope is a privilege-escalation vector."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="33333333-3333-3333-3333-333333333333",
                principal_type="ServicePrincipal",
                role_definition_id=UAA_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(
            role_name="User Access Administrator")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["service_principal"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertTrue(
            any(UAA_ROLE_ID in o.get("role_definition_id", "")
                for o in result["observations"]))

    def test_rbac_administrator_flagged(self):
        """Role Based Access Control Administrator is also a privilege-escalation vector."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="44444444-4444-4444-4444-444444444444",
                principal_type="ServicePrincipal",
                role_definition_id=RBAC_ADMIN_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(
            role_name="Role Based Access Control Administrator")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["service_principal"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertGreaterEqual(len(result["observations"]), 1)

    def test_target_principal_types_filter_excludes_groups(self):
        """A Group assignment is excluded when target_principal_types=['user']."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="55555555-5555-5555-5555-555555555555",
                principal_type="Group",
                role_definition_id=OWNER_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )

        _assert_shape(self, result)
        # Group assignment filtered out → no observations from it
        self.assertEqual(result["observations"], [])
        # No assignments matched at all → empty-RG semantics (confidence=0.5)
        self.assertEqual(result["confidence"], 0.5)
        self.assertEqual(result["result"], "ok")

    def test_target_principal_types_filter_includes_managed_identity(self):
        """A managed-identity Owner assignment IS flagged when MI is in the filter."""
        self.fake_clients.role_assignments.list_for_scope.return_value = [
            _make_assignment(
                principal_id="66666666-6666-6666-6666-666666666666",
                principal_type="ServicePrincipal",   # MIs surface as SP in the SDK
                role_definition_id=OWNER_ROLE_ID,
            ),
        ]
        self.fake_clients.role_definitions.get.return_value = MagicMock(role_name="Owner")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["managed_identity", "service_principal"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "needs_attention")
        self.assertEqual(len(result["observations"]), 1)

    def test_empty_rg_returns_ok_with_low_confidence(self):
        """Zero assignments in scope → result=ok, observations=[], confidence=0.5 (ambiguous)."""
        self.fake_clients.role_assignments.list_for_scope.return_value = []

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user", "service_principal"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["confidence"], 0.5)
        self.assertIsNone(result["error"])

    def test_never_raises_on_authorization_failed(self):
        """403 from list_for_scope → result=errored, confidence=0.0, error populated, returns dict."""
        self.fake_clients.role_assignments.list_for_scope.side_effect = RuntimeError(
            "AuthorizationFailed: caller does not have permission to read role assignments")

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )

        _assert_shape(self, result)
        self.assertEqual(result["result"], "errored")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("AuthorizationFailed", result["error"])
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["remediation_hints"], [])

    def test_manifest_file_written_with_finding_id_literal_filename(self):
        """probe() writes out/IAM-101.json relative to CWD with the same dict."""
        self.fake_clients.role_assignments.list_for_scope.return_value = []

        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )
        _assert_shape(self, result)

        manifest = self.tmp_path / "out" / "IAM-101.json"
        self.assertTrue(
            manifest.exists(), f"expected manifest at {manifest}, got missing")
        parsed = json.loads(manifest.read_text())
        self.assertEqual(parsed["finding_id"], FINDING_ID)
        self.assertEqual(parsed["scope"], result["scope"])
        self.assertEqual(parsed["result"], result["result"])
        self.assertEqual(parsed["confidence"], result["confidence"])

    def test_repeated_probe_overwrites_same_manifest_file(self):
        """Two probe() calls overwrite the SAME out/IAM-101.json — finding_id is taxonomy literal."""
        self.fake_clients.role_assignments.list_for_scope.return_value = []

        r1 = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )
        _assert_shape(self, r1)

        r2 = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
        )
        _assert_shape(self, r2)

        # Same finding_id always
        self.assertEqual(r1["finding_id"], FINDING_ID)
        self.assertEqual(r2["finding_id"], FINDING_ID)
        # Only one manifest file exists, and it matches the second call
        manifests = list((self.tmp_path / "out").iterdir())
        self.assertEqual([m.name for m in manifests], ["IAM-101.json"])
        parsed = json.loads(manifests[0].read_text())
        self.assertEqual(parsed["probed_at"], r2["probed_at"])

    def test_credential_kwarg_is_keyword_only(self):
        """The credential parameter MUST be keyword-only to match the locked contract."""
        self.fake_clients.role_assignments.list_for_scope.return_value = []

        custom_cred = MagicMock(name="custom-credential")
        # This should work — credential passed as kwarg
        result = probe(
            subscription_id="sub-id",
            resource_group="rg",
            target_principal_types=["user"],
            credential=custom_cred,
        )
        _assert_shape(self, result)

        # This MUST raise TypeError — positional credential not allowed
        with self.assertRaises(TypeError):
            probe("sub-id", "rg", ["user"], custom_cred)


if __name__ == "__main__":
    unittest.main()

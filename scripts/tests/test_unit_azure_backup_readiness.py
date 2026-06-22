"""Unit tests for azure-backup-readiness probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/267
Locked decision (spec §4.4 Q-D1): probe checks BOTH Recovery Services
Vaults and Backup Vaults.

Written as ``unittest.TestCase`` (NOT pytest fixtures) because
``.github/workflows/skill-test.yml::unit-tests`` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

``unittest discover`` cannot resolve pytest fixtures (``monkeypatch``,
``tmp_path``) and silently emits 0 tests for files that use them.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


_PROBE_PY = (Path(__file__).resolve().parents[2]
             / "skills" / "azure-backup-readiness"
             / "references" / "python" / "probe.py")
_spec = importlib.util.spec_from_file_location("backup_probe", _PROBE_PY)
backup_probe = importlib.util.module_from_spec(_spec)
sys.modules["backup_probe"] = backup_probe
_spec.loader.exec_module(backup_probe)
probe = backup_probe.probe


def _shape(testcase: unittest.TestCase, result: dict) -> None:
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "vaults", "findings", "summary", "manifest_path", "probed_at"}
    missing = required - result.keys()
    testcase.assertFalse(missing, f"missing: {missing}")
    testcase.assertEqual(result["skill"], "azure-backup-readiness")
    testcase.assertIsInstance(result["vaults"], list)
    testcase.assertIsInstance(result["findings"], list)


class TestAzureBackupReadinessProbe(unittest.TestCase):
    """Unit tests for the azure-backup-readiness probe."""

    def setUp(self):
        self.rsv = MagicMock(name="RecoveryServicesClient")
        self.bv = MagicMock(name="DataProtectionMgmtClient")
        self.rsvb = MagicMock(name="RecoveryServicesBackupClient")

        self._rsv_patcher = patch.object(
            backup_probe, "RecoveryServicesClient",
            lambda credential, subscription_id: self.rsv)
        self._bv_patcher = patch.object(
            backup_probe, "DataProtectionMgmtClient",
            lambda credential, subscription_id: self.bv)
        self._rsvb_patcher = patch.object(
            backup_probe, "RecoveryServicesBackupClient",
            lambda credential, subscription_id: self.rsvb)
        self._cred_patcher = patch.object(
            backup_probe, "DefaultAzureCredential",
            lambda: MagicMock(name="cred"))

        self._rsv_patcher.start()
        self._bv_patcher.start()
        self._rsvb_patcher.start()
        self._cred_patcher.start()

        # Isolate manifest output so no test leaks into the repo ``out/`` dir.
        self._outdir = tempfile.TemporaryDirectory()
        self._prev_out = os.environ.get("AZURE_BACKUP_READINESS_OUT")
        os.environ["AZURE_BACKUP_READINESS_OUT"] = self._outdir.name

    def tearDown(self):
        if self._prev_out is None:
            os.environ.pop("AZURE_BACKUP_READINESS_OUT", None)
        else:
            os.environ["AZURE_BACKUP_READINESS_OUT"] = self._prev_out
        self._outdir.cleanup()
        self._cred_patcher.stop()
        self._rsvb_patcher.stop()
        self._bv_patcher.stop()
        self._rsv_patcher.stop()

    def test_happy_path_both_vault_types_present(self):
        """Both an RSV and a Backup Vault present with active protected items."""
        self.rsv.vaults.list_by_resource_group.return_value = [
            MagicMock(name="rsv1", id="/.../vaults/rsv1"),
        ]
        self.bv.backup_vaults.get_in_resource_group.return_value = [
            MagicMock(name="bv1", id="/.../backupVaults/bv1"),
        ]
        self.rsvb.backup_protected_items.list.return_value = [
            MagicMock(name="item1", properties=MagicMock(protection_state="Protected")),
        ]
        self.bv.backup_instances.list.return_value = [
            MagicMock(name="item2"),
        ]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertGreaterEqual(len(result["vaults"]), 1)
        self.assertTrue(
            any(v["kind"] == "RecoveryServicesVault" for v in result["vaults"])
            or any(v["kind"] == "BackupVault" for v in result["vaults"]))

    def test_no_vaults_in_rg_flagged(self):
        """RG with no RSV and no Backup Vault → finding present, never raises."""
        self.rsv.vaults.list_by_resource_group.return_value = []
        self.bv.backup_vaults.get_in_resource_group.return_value = []

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["total_vaults"], 0)
        self.assertTrue(
            any(f["kind"] == "no-vaults-in-rg" for f in result["findings"]))

    def test_vault_present_but_no_protected_items(self):
        """Vault exists but no protected items → flagged as 'vault-empty'."""
        self.rsv.vaults.list_by_resource_group.return_value = [
            MagicMock(name="rsv1", id="/.../vaults/rsv1"),
        ]
        self.bv.backup_vaults.get_in_resource_group.return_value = []
        self.rsvb.backup_protected_items.list.return_value = []

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertTrue(any(f["kind"] == "vault-empty" for f in result["findings"]))

    def test_manifest_written(self):
        """Manifest is written to AZURE_BACKUP_READINESS_OUT and round-trips."""
        self.rsv.vaults.list_by_resource_group.return_value = []
        self.bv.backup_vaults.get_in_resource_group.return_value = []

        result = probe(subscription_id="sub", resource_group="rg")

        manifest = Path(result["manifest_path"])
        self.assertTrue(manifest.exists())
        self.assertEqual(manifest.parent, Path(self._outdir.name).resolve())
        self.assertEqual(
            json.loads(manifest.read_text())["finding_id"],
            result["finding_id"])

    def test_never_raises_on_partial_denial(self):
        """RSV list 403 but Backup Vault listing succeeds → probes other surface."""
        self.rsv.vaults.list_by_resource_group.side_effect = RuntimeError(
            "AuthorizationFailed: RSV list denied")
        self.bv.backup_vaults.get_in_resource_group.return_value = [
            MagicMock(name="bv1", id="/.../backupVaults/bv1"),
        ]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertGreaterEqual(result["summary"]["confidence"], 0.0)
        self.assertLess(result["summary"]["confidence"], 1.0)

    def test_protected_item_types_filters_counted_items(self):
        """protected_item_types (REL-007 contract) filters counted items by workload type."""
        self.rsv.vaults.list_by_resource_group.return_value = [
            MagicMock(name="rsv1", id="/.../vaults/rsv1"),
        ]
        self.bv.backup_vaults.get_in_resource_group.return_value = []
        self.rsvb.backup_protected_items.list.return_value = [
            MagicMock(properties=MagicMock(workload_type="VM")),
            MagicMock(properties=MagicMock(workload_type="VM")),
            MagicMock(properties=MagicMock(workload_type="SQLDataBase")),
        ]

        result = probe(subscription_id="sub", resource_group="rg",
                       protected_item_types=["VM"])

        _shape(self, result)
        # Only the two VM items count toward coverage; the SQL item is excluded.
        self.assertEqual(result["summary"]["total_protected_items"], 2)
        self.assertEqual(result["summary"]["protected_item_types_filter"], ["VM"])

    def test_protected_item_types_none_counts_all(self):
        """Omitting the filter counts every protected item (default behavior)."""
        self.rsv.vaults.list_by_resource_group.return_value = [
            MagicMock(name="rsv1", id="/.../vaults/rsv1"),
        ]
        self.bv.backup_vaults.get_in_resource_group.return_value = []
        self.rsvb.backup_protected_items.list.return_value = [
            MagicMock(properties=MagicMock(workload_type="VM")),
            MagicMock(properties=MagicMock(workload_type="SQLDataBase")),
        ]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["total_protected_items"], 2)
        self.assertIsNone(result["summary"]["protected_item_types_filter"])

    def test_never_raises_on_full_denial(self):
        """Both vault APIs 403 → probe_error populated, never raises."""
        self.rsv.vaults.list_by_resource_group.side_effect = RuntimeError(
            "AuthorizationFailed")
        self.bv.backup_vaults.get_in_resource_group.side_effect = RuntimeError(
            "AuthorizationFailed")

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertTrue(
            result["summary"].get("probe_error")
            or result["summary"]["confidence"] == 0.0)


if __name__ == "__main__":
    unittest.main()

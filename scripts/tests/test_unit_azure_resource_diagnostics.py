"""Unit tests for azure-resource-diagnostics probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/271
Locked decision (spec §4.4 Q-D2): a resource is "configured" if it has
ANY destination (LogAnalytics, EventHubs, or Storage).

Written as ``unittest.TestCase`` (NOT pytest fixtures) because
``.github/workflows/skill-test.yml::unit-tests`` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

``unittest discover`` cannot resolve pytest fixtures (``monkeypatch``,
``tmp_path``) and silently emits 0 tests for files that use them. The
module is loaded via ``spec_from_file_location`` with a UNIQUE module
name (``diag_probe``) so it never collides with the sibling
``azure-backup-readiness`` probe.py in ``sys.modules``.
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
             / "skills" / "azure-resource-diagnostics"
             / "references" / "python" / "probe.py")
_spec = importlib.util.spec_from_file_location("diag_probe", _PROBE_PY)
diag_probe = importlib.util.module_from_spec(_spec)
sys.modules["diag_probe"] = diag_probe
_spec.loader.exec_module(diag_probe)
probe = diag_probe.probe


def _shape(testcase: unittest.TestCase, result: dict) -> None:
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "resources", "findings", "summary", "manifest_path", "probed_at"}
    missing = required - result.keys()
    testcase.assertFalse(missing, f"missing: {missing}")
    testcase.assertEqual(result["skill"], "azure-resource-diagnostics")
    testcase.assertIsInstance(result["resources"], list)
    testcase.assertIsInstance(result["findings"], list)


def _make_resource(name: str, rtype: str) -> MagicMock:
    r = MagicMock()
    r.id = f"/subscriptions/x/resourceGroups/rg/providers/{rtype}/{name}"
    r.name = name
    r.type = rtype
    return r


def _make_setting(destinations: list[str]) -> MagicMock:
    setting = MagicMock(name="setting")
    setting.workspace_id = "/.../laws/law1" if "LogAnalytics" in destinations else None
    setting.event_hub_authorization_rule_id = "/.../eh-rule" if "EventHubs" in destinations else None
    setting.storage_account_id = "/.../storage-acct" if "Storage" in destinations else None
    return setting


class TestAzureResourceDiagnosticsProbe(unittest.TestCase):
    """Unit tests for the azure-resource-diagnostics probe."""

    def setUp(self):
        self.resource = MagicMock(name="ResourceManagementClient")
        self.monitor = MagicMock(name="MonitorManagementClient")

        self._res_patcher = patch.object(
            diag_probe, "ResourceManagementClient",
            lambda credential, subscription_id: self.resource)
        self._mon_patcher = patch.object(
            diag_probe, "MonitorManagementClient",
            lambda credential, subscription_id: self.monitor)
        self._cred_patcher = patch.object(
            diag_probe, "DefaultAzureCredential",
            lambda: MagicMock(name="cred"))

        self._res_patcher.start()
        self._mon_patcher.start()
        self._cred_patcher.start()

        # Isolate manifest output so no test leaks into the repo ``out/`` dir.
        self._outdir = tempfile.TemporaryDirectory()
        self._prev_out = os.environ.get("AZURE_RESOURCE_DIAGNOSTICS_OUT")
        os.environ["AZURE_RESOURCE_DIAGNOSTICS_OUT"] = self._outdir.name

    def tearDown(self):
        if self._prev_out is None:
            os.environ.pop("AZURE_RESOURCE_DIAGNOSTICS_OUT", None)
        else:
            os.environ["AZURE_RESOURCE_DIAGNOSTICS_OUT"] = self._prev_out
        self._outdir.cleanup()
        self._cred_patcher.stop()
        self._mon_patcher.stop()
        self._res_patcher.stop()

    def test_resource_with_law_destination_is_configured(self):
        """ANY destination present → counts as configured (Q-D2 decision)."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
        ]
        self.monitor.diagnostic_settings.list.return_value = [
            _make_setting(["LogAnalytics"]),
        ]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["configured_count"], 1)
        self.assertEqual(result["summary"]["unconfigured_count"], 0)

    def test_resource_with_only_storage_destination_still_configured(self):
        """Storage-only is still 'configured' per Q-D2."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
        ]
        self.monitor.diagnostic_settings.list.return_value = [
            _make_setting(["Storage"]),
        ]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["configured_count"], 1)

    def test_resource_with_no_diag_settings_unconfigured(self):
        """No diagnostic settings → unconfigured, finding emitted."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
        ]
        self.monitor.diagnostic_settings.list.return_value = []

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["unconfigured_count"], 1)
        self.assertTrue(
            any(f["kind"] == "no-diagnostic-settings" for f in result["findings"]))

    def test_resource_with_setting_but_no_destination_unconfigured(self):
        """Setting exists but with no destinations → unconfigured."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
        ]
        self.monitor.diagnostic_settings.list.return_value = [_make_setting([])]

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertEqual(result["summary"]["unconfigured_count"], 1)

    def test_target_resource_types_filters_by_arm_type(self):
        """target_resource_types (OBS-106 contract) restricts to matching ARM types."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
            _make_resource("ca1", "Microsoft.App/containerApps"),
        ]
        self.monitor.diagnostic_settings.list.return_value = [
            _make_setting(["LogAnalytics"]),
        ]

        result = probe(subscription_id="sub", resource_group="rg",
                       target_resource_types=["Microsoft.CognitiveServices/accounts"])

        _shape(self, result)
        self.assertEqual(len(result["resources"]), 1)
        self.assertEqual(result["resources"][0]["type"],
                         "Microsoft.CognitiveServices/accounts")
        self.assertEqual(result["summary"]["target_resource_types_filter"],
                         ["Microsoft.CognitiveServices/accounts"])

    def test_target_resource_types_matches_logical_kind(self):
        """Snake_case logical kinds (e.g. 'storage_account') match the ARM type."""
        self.resource.resources.list_by_resource_group.return_value = [
            _make_resource("sa1", "Microsoft.Storage/storageAccounts"),
            _make_resource("kv1", "Microsoft.KeyVault/vaults"),
        ]
        self.monitor.diagnostic_settings.list.return_value = [
            _make_setting(["LogAnalytics"]),
        ]

        result = probe(subscription_id="sub", resource_group="rg",
                       target_resource_types=["storage_account"])

        _shape(self, result)
        self.assertEqual(len(result["resources"]), 1)
        self.assertEqual(result["resources"][0]["type"],
                         "Microsoft.Storage/storageAccounts")

    def test_manifest_written(self):
        """Manifest is written to AZURE_RESOURCE_DIAGNOSTICS_OUT and round-trips."""
        self.resource.resources.list_by_resource_group.return_value = []

        result = probe(subscription_id="sub", resource_group="rg")

        manifest = Path(result["manifest_path"])
        self.assertTrue(manifest.exists())
        self.assertEqual(manifest.parent, Path(self._outdir.name).resolve())
        self.assertEqual(
            json.loads(manifest.read_text())["finding_id"],
            result["finding_id"])

    def test_never_raises_on_denial(self):
        """RG-list denial → probe_error populated / confidence 0.0, never raises."""
        self.resource.resources.list_by_resource_group.side_effect = \
            RuntimeError("AuthorizationFailed")

        result = probe(subscription_id="sub", resource_group="rg")

        _shape(self, result)
        self.assertTrue(
            result["summary"].get("probe_error")
            or result["summary"]["confidence"] == 0.0)


if __name__ == "__main__":
    unittest.main()

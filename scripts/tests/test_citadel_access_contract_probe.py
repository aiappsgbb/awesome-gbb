#!/usr/bin/env python3
"""Unit tests for citadel-spoke-onboarding hub Access Contract probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/246
Implements the threadlight NET-501/502 self-verify path.

Run:
    python -m unittest scripts.tests.test_citadel_access_contract_probe -v
    python3 -m unittest discover -s scripts/tests -p 'test_citadel_access_contract_probe.py' -v
"""
from __future__ import annotations

import os
import pathlib
import sys
import unittest
from unittest.mock import MagicMock, patch

HERE = pathlib.Path(__file__).resolve().parent
SKILL_DIR = HERE.parent.parent / "skills" / "citadel-spoke-onboarding" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

import access_contract_probe  # noqa: E402
from access_contract_probe import (  # noqa: E402
    probe_hub_contract,
    ResourceNotFoundError,
    HttpResponseError,
)


REQUIRED_KEYS = {
    "api_present", "product_assigned", "foundry_connection_status",
    "subscription_key_present", "rate_limit_policy", "last_probe_at",
    "confidence", "missing_perms",
}


class ProbeHubContractTests(unittest.TestCase):
    def setUp(self):
        self.apim = MagicMock(name="ApiManagementClient_instance")
        self.resource = MagicMock(name="ResourceManagementClient_instance")
        self._fake_cred = MagicMock(name="fake_cred")
        self.hub_rg = "hub-rg"
        self.apim_name = "hub-apim"
        self.spoke_id = "spoke-foundry-1"
        self.subscription = "fake-sub"
        # Patch SDK constructors on the module so probe_hub_contract picks them up.
        self.p_apim = patch.object(access_contract_probe, "ApiManagementClient",
                                   lambda cred, sub: self.apim)
        self.p_resource = patch.object(access_contract_probe, "ResourceManagementClient",
                                       lambda cred, sub: self.resource)
        self.p_cred = patch.object(access_contract_probe, "DefaultAzureCredential",
                                   lambda: MagicMock(name="cred"))
        self.p_apim.start()
        self.p_resource.start()
        self.p_cred.start()
        self.addCleanup(self.p_apim.stop)
        self.addCleanup(self.p_resource.stop)
        self.addCleanup(self.p_cred.stop)

    def _assertRequiredKeys(self, result):
        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()),
                        f"missing: {REQUIRED_KEYS - result.keys()}")

    def test_full_happy_path(self):
        """APIM found, product assigned, sub key present → confidence >= 0.8, missing_perms == []."""
        sub_mock = MagicMock(name="sub")
        sub_mock.state = "active"
        sub_mock.display_name = "spoke-foundry-1"
        self.apim.api.get.return_value = MagicMock(name="api")
        self.apim.product.get.return_value = MagicMock(name="product")
        self.apim.subscription.list.return_value = [sub_mock]
        self.apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertTrue(result["api_present"])
        self.assertTrue(result["product_assigned"])
        self.assertEqual(result["foundry_connection_status"], "ok")
        self.assertTrue(result["subscription_key_present"])
        self.assertGreaterEqual(result["confidence"], 0.8)
        self.assertEqual(result["missing_perms"], [])

    def test_api_missing_returns_error_path(self):
        """APIM exists but spoke API/product absent (ResourceNotFoundError/404) → missing_perms == [], foundry_connection_status == 'missing', never raises."""
        self.apim.api.get.side_effect = ResourceNotFoundError("api not found")
        self.apim.product.get.side_effect = ResourceNotFoundError("product not found")

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertFalse(result["api_present"])
        self.assertFalse(result["product_assigned"])
        self.assertEqual(result["foundry_connection_status"], "missing")
        self.assertEqual(result["missing_perms"], [])  # 404 is "not onboarded", not a permission gap
        self.assertLess(result["confidence"], 0.5)

    def test_apim_auto_discovery_when_only_one(self):
        """apim_name=None + RG with exactly 1 APIM → auto-discovers and succeeds."""
        apim_resource = MagicMock(name="apim-resource")
        apim_resource.type = "Microsoft.ApiManagement/service"
        apim_resource.name = "hub-apim-auto"
        self.resource.resources.list_by_resource_group.return_value = [apim_resource]

        sub_mock = MagicMock(name="sub")
        sub_mock.state = "active"
        sub_mock.display_name = "spoke-foundry-1"
        self.apim.api.get.return_value = MagicMock(name="api")
        self.apim.product.get.return_value = MagicMock(name="product")
        self.apim.subscription.list.return_value = [sub_mock]
        self.apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name=None,
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertTrue(result["api_present"])

    def test_apim_auto_discovery_ambiguous_returns_clear_error(self):
        """apim_name=None + RG with 2 APIMs → api_present False, confidence == 0.0, ambiguity in missing_perms."""
        apim1 = MagicMock(name="apim-1")
        apim1.type = "Microsoft.ApiManagement/service"
        apim1.name = "hub-apim-1"
        apim2 = MagicMock(name="apim-2")
        apim2.type = "Microsoft.ApiManagement/service"
        apim2.name = "hub-apim-2"
        self.resource.resources.list_by_resource_group.return_value = [apim1, apim2]

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name=None,
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertFalse(result["api_present"])
        self.assertEqual(result["confidence"], 0.0)
        ambiguity_reported = any(
            "ambiguous" in (p or "").lower() or "multiple" in (p or "").lower()
            for p in result["missing_perms"]
        )
        self.assertTrue(ambiguity_reported,
                        f"expected ambiguity message in missing_perms, got: {result['missing_perms']}")

    def test_permission_denied_populates_missing_perms(self):
        """403 on product.get → api_present=True (api DID exist), product_assigned=False, foundry_connection_status='errored', missing_perms non-empty, confidence < 0.5."""
        self.apim.api.get.return_value = MagicMock(name="api")
        self.apim.product.get.side_effect = HttpResponseError(
            "403 AuthorizationFailed: caller does not have permission"
        )

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertTrue(result["api_present"])  # api.get succeeded; api DOES exist
        self.assertFalse(result["product_assigned"])
        self.assertEqual(result["foundry_connection_status"], "errored")
        self.assertGreaterEqual(len(result["missing_perms"]), 1)
        self.assertLess(result["confidence"], 0.5)

    def test_api_get_permission_denied_returns_errored(self):
        """403 on api.get → api_present=False, product_assigned=False, foundry_connection_status='errored', missing_perms mentions api.get/403."""
        self.apim.api.get.side_effect = HttpResponseError(
            "403 AuthorizationFailed: caller does not have APIM Reader role"
        )
        # product.get returns 404 (spoke not fully onboarded) so product_assigned stays False.
        self.apim.product.get.side_effect = ResourceNotFoundError("product not found")

        result = probe_hub_contract(
            hub_rg="hub-rg",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertFalse(result["api_present"])
        self.assertFalse(result["product_assigned"])
        self.assertEqual(result["foundry_connection_status"], "errored")
        self.assertGreaterEqual(len(result["missing_perms"]), 1)
        combined = " ".join(result["missing_perms"]).lower()
        self.assertTrue(
            "api.get" in combined or "403" in combined,
            f"expected api.get or 403 in missing_perms, got: {result['missing_perms']}",
        )
        self.assertLess(result["confidence"], 0.5)

    @patch.dict(os.environ, {"TL_CITADEL_HUB_RG": "env-fallback-rg"})
    def test_env_var_fallback_when_hub_rg_empty(self):
        """Empty hub_rg + TL_CITADEL_HUB_RG env var → env var used, probe succeeds."""
        sub_mock = MagicMock(name="sub")
        sub_mock.state = "active"
        sub_mock.display_name = "spoke-foundry-1"
        self.apim.api.get.return_value = MagicMock(name="api")
        self.apim.product.get.return_value = MagicMock(name="product")
        self.apim.subscription.list.return_value = [sub_mock]
        self.apim.api_policy.get.return_value = MagicMock(value="<rate-limit calls='100' />")

        result = probe_hub_contract(
            hub_rg="",
            apim_name="hub-apim",
            spoke_id="spoke-foundry-1",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertTrue(result["api_present"])

    def test_never_raises_on_any_exception(self):
        """The probe must never raise — any deep exception is surfaced via missing_perms."""
        for fail_site in ("api_get", "product_get", "subscriptions_list"):
            with self.subTest(fail_site=fail_site):
                # Reset all side effects and set safe defaults.
                self.apim.api.get.side_effect = None
                self.apim.api.get.return_value = MagicMock(name="api")
                self.apim.product.get.side_effect = None
                self.apim.product.get.return_value = MagicMock(name="product")
                self.apim.subscription.list.side_effect = None
                self.apim.subscription.list.return_value = []
                self.apim.api_policy.get.side_effect = None
                self.apim.api_policy.get.return_value = MagicMock(value=None)

                if fail_site == "api_get":
                    self.apim.api.get.side_effect = RuntimeError("cosmic-ray")
                elif fail_site == "product_get":
                    self.apim.product.get.side_effect = RuntimeError("cosmic-ray")
                else:  # subscriptions_list
                    self.apim.subscription.list.side_effect = RuntimeError("cosmic-ray")

                result = access_contract_probe.probe_hub_contract(
                    hub_rg=self.hub_rg,
                    apim_name=self.apim_name,
                    spoke_id=self.spoke_id,
                    subscription=self.subscription,
                    credential=self._fake_cred,
                )
                self.assertIsInstance(result, dict)
                self._assertRequiredKeys(result)
                self.assertGreaterEqual(len(result["missing_perms"]), 1)
                self.assertIn("cosmic-ray", " ".join(result["missing_perms"]))

    def test_empty_spoke_id_returns_error_path(self):
        """Empty spoke_id → immediate error-path, no SDK calls, missing_perms mentions spoke_id."""
        result = probe_hub_contract(
            hub_rg="some-rg",
            apim_name="some-apim",
            spoke_id="",
            subscription="fake-sub",
        )
        self._assertRequiredKeys(result)
        self.assertFalse(result["api_present"])
        self.assertFalse(result["product_assigned"])
        self.assertFalse(result["subscription_key_present"])
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(
            any("spoke_id" in p for p in result["missing_perms"]),
            f"expected spoke_id in missing_perms, got: {result['missing_perms']}",
        )
        # Guard short-circuits before any SDK call.
        self.apim.api.get.assert_not_called()

    def test_subscription_fallback_to_env_var(self):
        """subscription=None + no env var → error; subscription=None + env var → probe proceeds."""
        # Case 1: no subscription, no env var → error-path.
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
            result = probe_hub_contract(
                hub_rg="hub-rg",
                apim_name="hub-apim",
                spoke_id="spoke-foundry-1",
                subscription=None,
            )
        self._assertRequiredKeys(result)
        self.assertTrue(
            any("subscription" in p for p in result["missing_perms"]),
            f"expected subscription in missing_perms, got: {result['missing_perms']}",
        )
        self.assertEqual(result["confidence"], 0.0)

        # Case 2: no subscription, but env var is set → probe runs to completion.
        self.apim.api.get.return_value = MagicMock(name="api")
        self.apim.product.get.return_value = MagicMock(name="product")
        self.apim.subscription.list.return_value = []
        self.apim.api_policy.get.return_value = MagicMock(value=None)
        with patch.dict(os.environ, {"AZURE_SUBSCRIPTION_ID": "env-sub-id"}):
            result2 = probe_hub_contract(
                hub_rg="hub-rg",
                apim_name="hub-apim",
                spoke_id="spoke-foundry-1",
                subscription=None,
            )
        self._assertRequiredKeys(result2)
        self.assertTrue(result2["api_present"])


if __name__ == "__main__":
    unittest.main()

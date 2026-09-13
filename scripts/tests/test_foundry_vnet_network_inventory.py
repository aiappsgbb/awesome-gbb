"""Regression contract for non-mutating Foundry network inspection."""

import importlib.util
import io
import json
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/foundry-vnet-deploy"
HELPER = SKILL / "references/python/network_inventory.py"


def resources():
    return (
        {"id": "/subscriptions/<sub>/resourceGroups/<rg>/providers/"
         "Microsoft.CognitiveServices/accounts/<account>",
         "properties": {"provisioningState": "Succeeded",
                        "publicNetworkAccess": "Disabled"}},
        [{"properties": {"privateLinkServiceConnectionState": {"status": "Approved"}}}],
        {"delegations": [{"serviceName": "Microsoft.App/environments"}],
         "serviceAssociationLinks": []},
    )


def isolated_env():
    return {"AZURE_CONFIG_DIR": "isolated-az", "AZD_CONFIG_DIR": "isolated-azd",
            "AZURE_TENANT_ID": "<tenant>", "AZURE_SUBSCRIPTION_ID": "<sub>"}


class NetworkInventoryTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HELPER.exists(), "Missing read-only network inventory helper")
        spec = importlib.util.spec_from_file_location("network_inventory", HELPER)
        self.helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.helper)

    def test_healthy_management_state_never_certifies_runtime_connectivity(self):
        report = self.helper.summarize(*resources())
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["runtime_connectivity"], "NOT_TESTED")
        self.assertEqual(report["subnet_reuse"], "OWNERSHIP_REVIEW_REQUIRED")
        self.assertNotIn("/subscriptions/", str(report))

    def _assert_access_blocked(self, value):
        account, endpoints, subnet = resources()
        account["properties"]["publicNetworkAccess"] = value
        self.assertIn("PUBLIC_ACCESS_NOT_DISABLED", self.helper.summarize(
            account, endpoints, subnet)["blockers"])

    def test_public_access_cannot_pass_private_posture(self):
        self._assert_access_blocked("Enabled")

    def test_unknown_access_cannot_pass_private_posture(self):
        self._assert_access_blocked(None)

    def _assert_endpoints_blocked(self, endpoints):
        account, _, subnet = resources()
        self.assertIn("PRIVATE_ENDPOINT_NOT_APPROVED", self.helper.summarize(
            account, endpoints, subnet)["blockers"])

    def test_missing_endpoint_is_a_blocker(self):
        self._assert_endpoints_blocked([])

    def test_pending_endpoint_is_a_blocker(self):
        self._assert_endpoints_blocked([
            {"properties": {"privateLinkServiceConnectionState": {"status": "Pending"}}},
        ])

    def test_unknown_endpoint_is_a_blocker(self):
        self._assert_endpoints_blocked([{}])

    def test_sal_is_observed_not_removed_or_treated_as_a_failed_deployment(self):
        account, endpoints, subnet = resources()
        subnet["serviceAssociationLinks"] = [{"linkedResourceType": "Microsoft.App/environments"}]
        report = self.helper.summarize(account, endpoints, subnet)
        self.assertEqual(report["service_association_link_count"], 1)
        self.assertEqual(report["blockers"], [])
        self.assertEqual(report["subnet_reuse"], "OWNERSHIP_REVIEW_REQUIRED")

    def test_wrong_delegation_and_unfinished_account_are_reported(self):
        account, endpoints, subnet = resources()
        account["properties"]["provisioningState"] = "Creating"
        subnet["delegations"] = []
        report = self.helper.summarize(account, endpoints, subnet)
        self.assertEqual(set(report["blockers"]),
                         {"ACCOUNT_NOT_SUCCEEDED", "AGENT_DELEGATION_MISSING"})

    def test_context_mismatch_stops_before_resource_reads(self):
        reader = Mock(return_value={"id": "<other-sub>", "tenantId": "<tenant>"})
        with self.assertRaisesRegex(ValueError, "Azure context mismatch"):
            self.helper.collect("<rg>", "<account>", "<vnet-rg>", "<vnet>",
                                "<subnet>", isolated_env(), reader)
        self.assertEqual(reader.call_count, 1)

    def _assert_missing_context_blocks_reads(self, missing):
        env = isolated_env()
        del env[missing]
        reader = Mock()
        with self.assertRaisesRegex(ValueError, missing):
            self.helper.collect("<rg>", "<account>", "<rg>", "<vnet>",
                                "<subnet>", env, reader)
        reader.assert_not_called()

    def test_missing_azure_config_dir_stops_before_any_azure_read(self):
        self._assert_missing_context_blocks_reads("AZURE_CONFIG_DIR")

    def test_missing_azd_config_dir_stops_before_any_azure_read(self):
        self._assert_missing_context_blocks_reads("AZD_CONFIG_DIR")

    def test_missing_tenant_stops_before_any_azure_read(self):
        self._assert_missing_context_blocks_reads("AZURE_TENANT_ID")

    def test_missing_subscription_stops_before_any_azure_read(self):
        self._assert_missing_context_blocks_reads("AZURE_SUBSCRIPTION_ID")

    def test_collector_uses_explicit_subscription_and_only_reads(self):
        account, endpoints, subnet = resources()
        reader = Mock(side_effect=[
            {"id": "<sub>", "tenantId": "<tenant>"}, account, endpoints, subnet,
        ])
        report = self.helper.collect("<rg>", "<account>", "<vnet-rg>", "<vnet>",
                                     "<subnet>", isolated_env(), reader)
        self.assertEqual(report["runtime_connectivity"], "NOT_TESTED")
        commands = [call.args[0] for call in reader.call_args_list]
        self.assertEqual([command[:3] for command in commands], [
            ["account", "show", "--query"],
            ["cognitiveservices", "account", "show"],
            ["network", "private-endpoint-connection", "list"],
            ["network", "vnet", "subnet"],
        ])
        self.assertTrue(all("--subscription" in command for command in commands[1:]))
        self.assertEqual(commands[-1][commands[-1].index("--resource-group") + 1], "<vnet-rg>")
        self.assertFalse({"create", "update", "delete", "purge", "set"} & {
            word for command in commands for word in command
        })

    def test_azure_read_errors_propagate_instead_of_becoming_empty_success(self):
        reader = Mock(side_effect=RuntimeError("read failed"))
        with self.assertRaisesRegex(RuntimeError, "read failed"):
            self.helper.collect("<rg>", "<account>", "<rg>", "<vnet>",
                                "<subnet>", isolated_env(), reader)

    def test_cli_reader_is_bounded_json_without_shell(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0, '{"value": []}', ""))
        with patch.object(self.helper.subprocess, "run", run):
            self.assertEqual(self.helper.read_az(["account", "show"]), {"value": []})
        self.assertEqual(run.call_args.args[0], [
            "az", "account", "show", "--only-show-errors", "--output", "json",
        ])
        self.assertEqual(run.call_args.kwargs["timeout"], 90)
        self.assertIs(run.call_args.kwargs["check"], True)
        self.assertFalse(run.call_args.kwargs.get("shell"))

    def test_main_reports_blockers_with_nonzero_exit(self):
        stdout = io.StringIO()
        with patch.object(self.helper, "collect", return_value={
            "blockers": ["PUBLIC_ACCESS_NOT_DISABLED"], "runtime_connectivity": "NOT_TESTED",
        }), redirect_stdout(stdout):
            self.assertEqual(self.helper.main([
                "--resource-group", "<rg>", "--account", "<account>",
                "--vnet", "<vnet>", "--subnet", "<subnet>",
            ]), 1)
        self.assertEqual(json.loads(stdout.getvalue())["runtime_connectivity"], "NOT_TESTED")

    def test_main_redacts_azure_errors_without_success_report(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(self.helper, "collect", side_effect=subprocess.CalledProcessError(
            1, ["az"], stderr="sensitive-resource-inventory",
        )), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(self.helper.main([
                "--resource-group", "<rg>", "--account", "<account>",
                "--vnet", "<vnet>", "--subnet", "<subnet>",
            ]), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("sensitive-resource-inventory", stderr.getvalue())
        self.assertIn("no changes", stderr.getvalue())

    def test_retry_diagnostics_do_not_probe_with_writes_or_delete_by_suffix(self):
        text = (SKILL / "SKILL.md").read_text()
        retry = text.split("### Step 10b:", 1)[1].split("### Step 11:", 1)[0]
        self.assertNotIn("--method PUT", retry)
        self.assertNotIn("az resource delete", retry)
        self.assertIn("network_inventory.py", retry)
        self.assertIn("same timestamp", retry.lower())
        self.assertIn("approval", retry.lower())

    def test_intake_and_postdeploy_keep_runtime_proof_separate(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertIn("### Step 9a: Read-only network inventory", text)
        self.assertIn("Managed VNet", text)
        self.assertIn("NOT_TESTED", text)
        self.assertIn("templates/standard-agent", text)
        self.assertIn("templates/basic-vnet", text)
        self.assertIn("hubReversePeeringCommand", text)


if __name__ == "__main__":
    unittest.main()

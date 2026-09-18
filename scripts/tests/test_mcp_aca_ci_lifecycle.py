"""Offline replay of the actual azd fixture boundary and exact app cleanup."""

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

import yaml

from scripts.tests import test_foundry_mcp_aca_fixture_contract as fixture_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/mcp-aca-ci-lifecycle.py"
spec = importlib.util.spec_from_file_location("mcp_aca_ci_lifecycle", SCRIPT)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
ID = "11111111-2222-4333-8444-555555555555"
GROUP = f"/subscriptions/{ID}/resourceGroups/rg-awesome-gbb-ci"
APP = "ci-smoke-mcp-abcdef12"
APP_ID = GROUP + lifecycle.APP_PROVIDER + APP
DEPLOYMENT_ID = GROUP + lifecycle.DEPLOY_PROVIDER + "/ci-smoke-mcp-abcdef12-123"
MISSING = (404, {"error": {"code": "ResourceNotFound"}}, None)


def approval():
    return {
        "schema_version": 1, "repository": "example/repo", "sha": "a" * 40,
        "run_id": "123", "run_attempt": "1", "expires_at": "2030-01-01T01:00:00Z",
        "tenant_id": ID, "client_id": ID, "resource_group_id": GROUP,
        "environment_id": GROUP + "/providers/Microsoft.App/managedEnvironments/cae-awesome-gbb-ci",
        "identity_id": GROUP + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/example",
        "acr_server": "example.azurecr.io", "age_recipient": "age1" + "q" * 58,
        "image_retain_until": "2030-01-02T00:00:00Z",
        "owner": "Example operator", "purpose": "Offline synthetic lifecycle regression",
        "delete_exact_created_app": True, "retain_images": True,
    }


class ArmFake:
    def __init__(self):
        self.calls = []
        self.created = False
        self.deleted = False
        self.status_before = MISSING
        self.approved = approval()
        self.app = {
            "id": APP_ID, "systemData": {"createdAt": "2030-01-01T00:00:01Z"},
            "identity": {"userAssignedIdentities": {self.approved["identity_id"]: {}}},
            "properties": {"environmentId": self.approved["environment_id"], "template": {
                "containers": [{"image": "example.azurecr.io/example:unique"}],
            }},
        }
        self.deployment = {
            "id": DEPLOYMENT_ID, "properties": {
                "correlationId": ID, "provisioningState": "Succeeded",
                "parameters": {"appName": {"value": APP}},
            },
        }
        self.operation = {
            "operationId": "abc123", "properties": {
                "targetResource": {"id": APP_ID}, "provisioningOperation": "Create",
                "provisioningState": "Succeeded",
            },
        }

    def __call__(self, method, resource_id, api, etag=None, *, next_link=None, before_send=None):
        if before_send is not None:
            before_send()
        if next_link is not None:
            raise AssertionError("unexpected continuation")
        self.calls.append((method, resource_id, api, etag))
        if resource_id in {
            f"/subscriptions/{ID}" + lifecycle.LOCK_PROVIDER,
            GROUP + lifecycle.LOCK_PROVIDER, APP_ID + lifecycle.LOCK_PROVIDER,
        }:
            if method != "GET" or api != lifecycle.LOCK_API:
                raise AssertionError("lock reads only, fixed API")
            return 200, {"value": []}, None
        if resource_id == APP_ID:
            if method == "DELETE":
                self.deleted = True
                return 202, {}, None
            if not self.created:
                return copy.deepcopy(self.status_before)
            return copy.deepcopy(MISSING if self.deleted else (200, self.app, '"etag"'))
        if resource_id == GROUP + lifecycle.DEPLOY_PROVIDER:
            return 200, {"value": [self.deployment] if self.created else []}, None
        if resource_id == DEPLOYMENT_ID + "/operations":
            return 200, {"value": [self.operation]}, None
        if resource_id == DEPLOYMENT_ID:
            return 200, self.deployment, None
        raise AssertionError("out-of-scope request")


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.private = self.base / "private"
        self.private.mkdir(mode=0o700)
        self.approved = approval()
        self.now = NOW
        now = patch.object(lifecycle, "utc_now", side_effect=lambda: self.now)
        now.start()
        self.addCleanup(now.stop)
        self.env = {
            "GITHUB_WORKSPACE": str(ROOT), "GITHUB_REPOSITORY": "example/repo", "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "RUNNER_TEMP": str(self.base),
            "AZURE_SUBSCRIPTION_ID": ID, "AZURE_TENANT_ID": ID, "AZURE_CLIENT_ID": ID,
            "ACR_LOGIN_SERVER": "example.azurecr.io", "APP_NAME": APP, "PROJECT_DIR": str(self.project),
            "MCP_ACA_CI_LIFECYCLE_APPROVAL_JSON": json.dumps(self.approved),
        }
        files = {
            "src/server.py": fixture_contract.EXPECTED_SERVER_PY,
            "src/requirements.txt": fixture_contract.EXPECTED_REQUIREMENTS_TXT,
            "src/Dockerfile": fixture_contract.EXPECTED_DOCKERFILE,
            "infra/main.bicep": fixture_contract.EXPECTED_MAIN_BICEP,
            "infra/main.parameters.json": fixture_contract.EXPECTED_PARAMETERS_HEREDOC + "\n",
            "azure.yaml": fixture_contract.EXPECTED_AZURE_YAML_HEREDOC + "\n",
        }
        for name, text in files.items():
            for key, value in (("APP_NAME", APP), ("UAMI_RESOURCE_ID", self.approved["identity_id"]),
                               ("ACR_SERVER", "example.azurecr.io")):
                text = text.replace("${" + key + "}", value)
            text = text.replace(r"\$schema", "$schema")
            target = self.project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        (self.project / f".azure/{APP}").mkdir(parents=True)
        (self.project / ".azure/config.json").write_text(json.dumps({"version": 1, "defaultEnvironment": APP}))
        settings = {
            "AZURE_ENV_NAME": APP, "AZURE_LOCATION": "swedencentral",
            "AZURE_SUBSCRIPTION_ID": ID, "AZURE_RESOURCE_GROUP": "rg-awesome-gbb-ci",
            "AZURE_TENANT_ID": ID, "APP_NAME": APP, "UAMI_RESOURCE_ID": self.approved["identity_id"],
            "ACR_SERVER": "example.azurecr.io", "AZURE_CONTAINER_REGISTRY_ENDPOINT": "example.azurecr.io",
        }
        (self.project / f".azure/{APP}/.env").write_text("".join(f"{key}={value}\n" for key, value in settings.items()))
        self.git = patch.object(lifecycle.subprocess, "run", return_value=subprocess.CompletedProcess(
            [], 0, fixture_contract.FIXTURE.read_bytes(), b"",
        ))
        self.git.start()
        self.addCleanup(self.git.stop)
        self.encrypted = []
        self.encryption = patch.object(lifecycle, "encrypt", side_effect=lambda path, *_:
                                      self.encrypted.append(json.loads((path / "receipt.json").read_text())))
        self.encryption.start()
        self.addCleanup(self.encryption.stop)
        self.arm = ArmFake()
        self.azd_calls = []
        self.network = patch("socket.create_connection", side_effect=AssertionError("no network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def azd(self, argv, **kwargs):
        self.azd_calls.append(argv)
        self.assertEqual(argv, ["azd", "up", "--no-prompt"])
        self.assertEqual(kwargs["cwd"], self.project)
        self.assertEqual(self.encrypted[-1]["state"], "UNKNOWN")
        self.arm.created = True
        return subprocess.CompletedProcess(argv, 0)

    def deploy(self, run=None):
        lifecycle.deploy(self.env, self.approved, self.private, self.arm, run=run or self.azd)

    def receipt(self):
        return json.loads((self.private / "receipt.json").read_text())

    def test_real_scaffold_one_azd_up_owned_receipt_and_verified_absence(self):
        self.assertEqual(lifecycle.approval(self.env, NOW), self.approved)
        self.deploy()
        self.assertEqual(self.receipt()["state"], "OWNED")
        self.assertEqual(len(self.receipt()["source_hashes"]), 6)
        self.assertEqual(self.receipt()["create_ack"]["correlation_id"], ID)
        lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertEqual(self.receipt()["state"], "APP_ABSENT_IMAGE_RETAINED")
        self.assertEqual([call[1] for call in self.arm.calls if call[0] == "DELETE"], [APP_ID])
        self.assertEqual(self.arm.calls[-1][:2], ("GET", APP_ID))
        lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertEqual(sum(call[0] == "DELETE" for call in self.arm.calls), 1)

    def test_preexisting_and_auth_network_errors_never_create(self):
        for response in ((200, {}, None), (401, {}, None), (403, {}, None),
                         (404, {}, None), (404, {"error": "404"}, None), (500, {}, None)):
            self.arm.status_before = response
            with self.subTest(response=response), self.assertRaises(lifecycle.LifecycleError):
                self.deploy()
            self.assertEqual(self.azd_calls, [])
            (self.private / "receipt.json").unlink()

    def test_frozen_inputs_forbid_hook_env_or_infra_drift_before_mutation(self):
        with patch.object(lifecycle.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, b"altered checkout fixture", b"")):
            with self.assertRaisesRegex(lifecycle.LifecycleError, "CHECKOUT"):
                self.deploy()
        for name in ("azure.yaml", "src/Dockerfile", "infra/main.bicep", f".azure/{APP}/.env"):
            path = self.project / name
            original = path.read_text()
            path.write_text(original + "\n# changed\n")
            with self.subTest(name=name), self.assertRaises(lifecycle.LifecycleError):
                self.deploy()
            path.write_text(original)
        (self.project / ".env").write_text("AZURE_RESOURCE_GROUP=shared")
        with self.assertRaises(lifecycle.LifecycleError):
            self.deploy()
        self.assertEqual(self.arm.calls, [])
        self.assertEqual(self.azd_calls, [])

    def test_lost_ack_retains_unknown_and_blocks_another_deploy(self):
        def failed(argv, **kwargs):
            self.arm.created = True
            return subprocess.CompletedProcess(argv, 1)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "DEPLOY_UNKNOWN"):
            self.deploy(failed)
        self.assertEqual(self.receipt()["state"], "UNKNOWN")
        self.assertEqual(self.encrypted[-1]["app_id"], APP_ID)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "RETRY_BLOCKED"):
            self.deploy()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY_UNKNOWN"):
            lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertFalse(self.arm.deleted)

    def test_update_failed_or_wrong_target_operation_is_not_ownership(self):
        for key, wrong in (("provisioningOperation", "Update"), ("provisioningState", "Failed"),
                           ("targetResource", {"id": APP_ID + "-other"}),
                           ("targetResource", None), ("targetResource", "invalid")):
            original = copy.deepcopy(self.arm.operation)
            self.arm.operation["properties"][key] = wrong
            with self.subTest(key=key), self.assertRaisesRegex(lifecycle.LifecycleError, "CREATE_ACK"):
                self.deploy()
            self.assertEqual(self.receipt()["state"], "UNKNOWN")
            self.assertFalse(self.arm.deleted)
            (self.private / "receipt.json").unlink()
            self.arm.created = False
            self.arm.operation = original

    def test_ambiguous_or_preexisting_deployment_cannot_ack(self):
        for before, after, operations in (
            ([self.arm.deployment], [self.arm.deployment], [self.arm.operation]),
            ([], [self.arm.deployment], [self.arm.operation, self.arm.operation]),
            ([], [], [self.arm.operation]),
        ):
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.capture_operation(before, after, lambda _: operations, APP_ID, APP)

    def test_current_resource_or_correlation_change_prevents_delete(self):
        self.deploy()
        original = copy.deepcopy(self.arm.app)
        for update in (
            {"systemData": {"createdAt": "2030-01-02T00:00:00Z"}},
            {"identity": {"userAssignedIdentities": {GROUP + "/other": {}}}},
            {"id": APP_ID + "-other"},
        ):
            self.arm.app = {**original, **update}
            with self.assertRaises(lifecycle.LifecycleError):
                lifecycle.cleanup(self.approved, self.private, self.arm)
            self.assertFalse(self.arm.deleted)
        self.arm.app = original
        self.arm.deployment["properties"]["correlationId"] = "22222222-2222-4333-8444-555555555555"
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertFalse(self.arm.deleted)

    def test_receipt_cannot_target_shared_group_lock_or_other_run(self):
        self.deploy()
        original = self.receipt()
        for key, value in (("app_id", GROUP), ("app_id", GROUP + "/providers/Microsoft.Authorization/locks/shared"),
                           ("app_id", GROUP + lifecycle.APP_PROVIDER + "standing-app"),
                           ("run_id", "999"), ("sha", "f" * 40)):
            lifecycle.write(self.private / "receipt.json", {**original, key: value})
            with self.subTest(key=key), self.assertRaises(lifecycle.LifecycleError):
                lifecycle.cleanup(self.approved, self.private, self.arm)
            self.assertFalse(self.arm.deleted)

    def test_delete_ack_without_supported_absence_stays_residual(self):
        self.deploy()
        def never_absent(method, resource_id, api, etag=None, **kwargs):
            result = self.arm(method, resource_id, api, etag, **kwargs)
            if method == "GET" and resource_id == APP_ID and self.arm.deleted:
                return 403, {"error": {"message": "404 private text"}}, None
            return result
        with self.assertRaisesRegex(lifecycle.LifecycleError, "READBACK"):
            lifecycle.cleanup(self.approved, self.private, never_absent)
        self.assertEqual(self.receipt()["state"], "DELETE_REQUESTED")

    def test_missing_or_expired_approval_fails_without_side_effects(self):
        for key, value in (("run_id", "*"), ("sha", "a" * 39), ("retain_images", False),
                           ("expires_at", "2029-12-31T23:59:59Z"), ("expires_at", "2030-01-03T00:00:00Z"),
                           ("resource_group_id", GROUP + "-other")):
            env = {**self.env, "MCP_ACA_CI_LIFECYCLE_APPROVAL_JSON": json.dumps({**self.approved, key: value})}
            with self.subTest(key=key), self.assertRaises(lifecycle.LifecycleError):
                lifecycle.approval(env, NOW)
        self.assertEqual(self.arm.calls, [])

    def test_new_process_in_same_attempt_cannot_redeploy_after_unknown(self):
        with self.assertRaises(lifecycle.LifecycleError):
            self.deploy(lambda *args, **kwargs: subprocess.CompletedProcess([], 1))
        lifecycle.write(self.private / "approval.json", self.approved)
        validate = lifecycle.approval
        with patch.object(lifecycle, "root", return_value=self.private), \
             patch.object(lifecycle, "approval", side_effect=lambda env, now, raw=None:
                          validate(env, NOW, raw)), \
             patch.object(lifecycle, "Arm", return_value=self.arm), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(lifecycle.main(["deploy"], self.env), 1)
        self.assertIn("FAIL RETRY_BLOCKED", out.getvalue())
        self.assertNotIn("PASS", out.getvalue())
        self.assertFalse(self.arm.deleted)

    def test_missing_or_malformed_inventory_cannot_report_cleanup_success(self):
        validate = lifecycle.approval
        lifecycle.write(self.private / "approval.json", self.approved)
        with patch.object(lifecycle, "root", return_value=self.private), \
             patch.object(lifecycle, "approval", side_effect=lambda env, now, raw=None:
                          validate(env, NOW, raw)), \
             patch.object(lifecycle, "Arm", return_value=self.arm):
            for record in (None, [], {"state": "UNKNOWN"}):
                if record is not None:
                    lifecycle.write(self.private / "receipt.json", record)
                with redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(lifecycle.main(["cleanup"], self.env), 1)
                self.assertIn("MCP_ACA_LIFECYCLE=FAIL", out.getvalue())
                self.assertNotIn("PASS", out.getvalue())
                self.assertNotIn("Traceback", out.getvalue())
        self.assertFalse(self.arm.deleted)

    def test_pending_delete_timeout_is_not_absence(self):
        self.deploy()
        def pending(method, resource_id, api, etag=None, **kwargs):
            result = self.arm(method, resource_id, api, etag, **kwargs)
            if method == "GET" and resource_id == APP_ID and self.arm.deleted:
                return 200, self.arm.app, None
            return result
        with self.assertRaisesRegex(lifecycle.LifecycleError, "CLEANUP_TIMEOUT"):
            lifecycle.cleanup(self.approved, self.private, pending,
                              clock=iter((0, 0, 1, 241)).__next__, sleep=lambda _: None)
        self.assertEqual(self.receipt()["state"], "DELETE_REQUESTED")

    def test_expiry_during_deploy_preflight_or_encryption_prevents_azd(self):
        for phase in ("preflight", "encryption", "insufficient-reserve"):
            with self.subTest(phase=phase):
                self.now = NOW
                def slow_read(*args, **kwargs):
                    result = self.arm(*args, **kwargs)
                    if phase == "preflight":
                        self.now = NOW + timedelta(hours=1)
                    return result
                def encrypt(_path, *_):
                    self.encrypted.append(self.receipt())
                    if phase == "encryption":
                        self.now = NOW + timedelta(hours=1)
                    elif phase == "insufficient-reserve":
                        self.now = NOW + timedelta(minutes=30, seconds=1)
                with patch.object(lifecycle, "encrypt", side_effect=encrypt), \
                     self.assertRaisesRegex(lifecycle.LifecycleError, "APPROVAL_LIFETIME"):
                    lifecycle.deploy(self.env, self.approved, self.private, slow_read, run=self.azd)
                self.assertEqual(self.azd_calls, [])
                self.assertEqual(self.receipt()["state"], "UNKNOWN")
                with self.assertRaisesRegex(lifecycle.LifecycleError, "RETRY_BLOCKED"):
                    self.deploy()
                (self.private / "receipt.json").unlink()

    def test_exact_deploy_lifetime_reserves_operation_capture_and_finalizer(self):
        self.now = NOW + timedelta(minutes=30)
        self.deploy()
        self.assertEqual(self.receipt()["state"], "OWNED")
        self.assertEqual(lifecycle.DEPLOY_SECONDS + lifecycle.CAPTURE_SECONDS +
                         lifecycle.FINALIZER_SECONDS, 1800)

    def test_delete_guard_runs_after_real_transport_token_acquisition(self):
        self.deploy()
        account = {"id": ID, "tenantId": ID,
                   "user": {"type": "servicePrincipal", "name": ID}}
        for delay in (timedelta(hours=1), timedelta(minutes=55, seconds=1)):
            with self.subTest(delay=delay):
                self.now = NOW
                def credential(argv, **_):
                    if argv[:3] == ["az", "account", "show"]:
                        return subprocess.CompletedProcess(argv, 0, json.dumps(account).encode())
                    self.assertEqual(argv[:3], ["az", "account", "get-access-token"])
                    self.now += delay
                    return subprocess.CompletedProcess(argv, 0, b"synthetic-token")
                with patch.object(lifecycle.subprocess, "run", side_effect=credential), \
                     patch.object(lifecycle, "build_opener") as opener:
                    real = lifecycle.Arm(self.env)
                    def routed(method, resource_id, api, *args, **kwargs):
                        if method == "DELETE":
                            return real(method, resource_id, api, *args, **kwargs)
                        return self.arm(method, resource_id, api, *args, **kwargs)
                    with self.assertRaisesRegex(lifecycle.LifecycleError, "APPROVAL_LIFETIME"):
                        lifecycle.cleanup(self.approved, self.private, routed)
                    opener.return_value.open.assert_not_called()
                self.assertEqual(self.receipt()["state"], "DELETE_REQUESTED")
                self.assertFalse(self.arm.deleted)

    def test_cleanup_expiry_during_readback_and_short_runtime_block_delete(self):
        self.deploy()
        def slow_read(*args, **kwargs):
            result = self.arm(*args, **kwargs)
            self.now = NOW + timedelta(hours=1)
            return result
        with self.assertRaisesRegex(lifecycle.LifecycleError, "APPROVAL_LIFETIME"):
            lifecycle.cleanup(self.approved, self.private, slow_read)
        self.assertFalse(self.arm.deleted)
        self.now = NOW
        with self.assertRaisesRegex(lifecycle.LifecycleError, "CLEANUP_TIMEOUT"):
            lifecycle.cleanup(self.approved, self.private, self.arm,
                              clock=iter((0, 181)).__next__)
        self.assertFalse(self.arm.deleted)

    def test_collection_pagination_captures_later_create_and_rechecks_operations(self):
        counts = {}
        def paginated(method, resource_id, api, *args, next_link=None, **kwargs):
            if method == "GET" and (resource_id.endswith(lifecycle.DEPLOY_PROVIDER) or
                                    resource_id.endswith("/operations")):
                link = lifecycle.ARM_ORIGIN + resource_id + "?api-version=" + api + "&$skiptoken=opaque"
                if next_link is None:
                    return 200, {"value": [], "nextLink": link}, None
                self.assertEqual(next_link, link)
                counts[resource_id] = counts.get(resource_id, 0) + 1
            return self.arm(method, resource_id, api, *args, **kwargs)
        lifecycle.deploy(self.env, self.approved, self.private, paginated, run=self.azd)
        lifecycle.cleanup(self.approved, self.private, paginated)
        self.assertEqual(counts, {
            GROUP + lifecycle.DEPLOY_PROVIDER: 2, DEPLOYMENT_ID + "/operations": 2,
        })
        self.assertEqual(self.receipt()["state"], "APP_ABSENT_IMAGE_RETAINED")

    def test_sanitized_arm_operations_bind_parent_not_optional_operation_correlation(self):
        # Shape from the coordinator's read-only ARM evidence; all values synthetic.
        operations = [
            {"operationId": "ABCDEF1234567890", "properties": {
                "correlationId": None, "serviceRequestId": None, "trackingId": ID,
                "provisioningOperation": "Create", "provisioningState": "Succeeded",
                "timestamp": "2030-01-01T00:00:01.000000+00:00",
                "targetResource": {"apiVersion": None, "extension": None, "id": APP_ID,
                                   "identifiers": None, "resourceGroup": "rg-awesome-gbb-ci",
                                   "resourceName": APP, "resourceType": "Microsoft.App/containerApps",
                                   "symbolicName": None},
            }},
            {"operationId": "01234567890123456789", "properties": {
                "correlationId": None, "serviceRequestId": None, "trackingId": ID,
                "provisioningOperation": "EvaluateDeploymentOutput", "provisioningState": "Succeeded",
                "timestamp": "2030-01-01T00:00:01.000000+00:00", "targetResource": None,
            }},
        ]
        def arm(method, resource_id, api, *args, **kwargs):
            if resource_id == DEPLOYMENT_ID + "/operations":
                return 200, {"value": operations}, None
            return self.arm(method, resource_id, api, *args, **kwargs)
        lifecycle.deploy(self.env, self.approved, self.private, arm, run=self.azd)
        self.assertEqual(self.receipt()["create_ack"], {
            "deployment_id": DEPLOYMENT_ID, "correlation_id": ID,
            "operation_id": "ABCDEF1234567890",
        })
        lifecycle.cleanup(self.approved, self.private, arm)
        self.assertEqual(self.receipt()["state"], "APP_ABSENT_IMAGE_RETAINED")

    def test_wire_arm_id_casing_and_raw_created_at_do_not_relax_approval_dates(self):
        created_at = "2030-01-01T00:00:01.5804371"
        self.arm.app["id"] = APP_ID.replace("containerApps", "containerapps")
        self.arm.app["systemData"]["createdAt"] = created_at
        self.deploy()
        self.assertEqual(self.receipt()["binding"]["created_at"], created_at)
        lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertEqual(self.receipt()["binding"]["created_at"], created_at)
        self.assertEqual(self.receipt()["state"], "APP_ABSENT_IMAGE_RETAINED")
        for key in ("expires_at", "image_retain_until"):
            for value in ("2030-01-01T01:00:00", "2030-01-01T01:00:00+01:00", created_at):
                with self.subTest(key=key, value=value), \
                     self.assertRaisesRegex(lifecycle.LifecycleError, "DATE"):
                    lifecycle.approval(self.env, NOW, json.dumps({**self.approved, key: value}))

    def test_inventory_error_before_create_cannot_launch_azd_or_retry(self):
        def denied_page(method, resource_id, api, *args, next_link=None, **kwargs):
            if resource_id == GROUP + lifecycle.DEPLOY_PROVIDER:
                if next_link:
                    raise lifecycle.LifecycleError("NETWORK")
                link = lifecycle.ARM_ORIGIN + resource_id + "?api-version=" + api + "&$skiptoken=2"
                return 200, {"value": [], "nextLink": link}, None
            return self.arm(method, resource_id, api, *args, **kwargs)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "NETWORK"):
            lifecycle.deploy(self.env, self.approved, self.private, denied_page, run=self.azd)
        self.assertEqual(self.receipt()["state"], "PREPARING")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "RETRY_BLOCKED"):
            self.deploy()
        self.assertEqual(self.azd_calls, [])

    def test_inherited_subscription_group_and_app_locks_block_before_azd(self):
        for scope in (f"/subscriptions/{ID}", GROUP, APP_ID):
            for level in ("CanNotDelete", "ReadOnly"):
                with self.subTest(scope=scope, level=level):
                    def locked(method, resource_id, api, *args, **kwargs):
                        if resource_id == scope + lifecycle.LOCK_PROVIDER:
                            return 200, {"value": [{
                                "id": scope + lifecycle.LOCK_PROVIDER + "/standing-protection",
                                "type": "Microsoft.Authorization/locks",
                                "properties": {"level": level},
                            }]}, None
                        return self.arm(method, resource_id, api, *args, **kwargs)
                    with self.assertRaisesRegex(lifecycle.LifecycleError, "CLEANUP_LOCKED"):
                        lifecycle.deploy(self.env, self.approved, self.private, locked, run=self.azd)
                    self.assertEqual(self.azd_calls, [])
                    self.assertEqual(self.receipt()["state"], "PREPARING")
                    with self.assertRaisesRegex(lifecycle.LifecycleError, "RETRY_BLOCKED"):
                        self.deploy()
                    (self.private / "receipt.json").unlink()

    def test_lock_permission_error_or_unclassifiable_response_blocks_creation(self):
        lock = {"id": GROUP + lifecycle.LOCK_PROVIDER + "/standing-protection",
                "type": "Microsoft.Authorization/locks", "properties": {"level": "CanNotDelete"}}
        responses = [
            (401, {}), (403, {}), (404, {"error": {"code": "ResourceNotFound"}}), (500, {}),
            (200, {"value": None}), (200, {"value": [None]}),
        ]
        for key, value in (("id", None), ("id", "/relative/lock"), ("type", "unexpected"),
                           ("properties", {"level": "NotSpecified"}), ("properties", {}),
                           ("properties", {"level": "CannotDelete"})):
            responses.append((200, {"value": [{**lock, key: value}]}))
        for response in responses:
            with self.subTest(response=response):
                def denied(method, resource_id, api, *args, **kwargs):
                    if resource_id.endswith(lifecycle.LOCK_PROVIDER):
                        return *response, None
                    return self.arm(method, resource_id, api, *args, **kwargs)
                with self.assertRaises(lifecycle.LifecycleError):
                    lifecycle.deploy(self.env, self.approved, self.private, denied, run=self.azd)
                self.assertEqual(self.azd_calls, [])
                (self.private / "receipt.json").unlink()

    def test_lock_on_later_page_blocks_but_standing_sibling_lock_is_not_inherited(self):
        locks_path = GROUP + lifecycle.LOCK_PROVIDER
        sibling = GROUP + "/providers/Microsoft.OperationalInsights/workspaces/standing"
        protected = GROUP
        def locks(method, resource_id, api, *args, next_link=None, **kwargs):
            if resource_id == locks_path:
                if next_link is None:
                    return 200, {"value": [], "nextLink": lifecycle.ARM_ORIGIN + locks_path +
                                 "?api-version=" + lifecycle.LOCK_API + "&$skiptoken=2"}, None
                return 200, {"value": [{
                    "id": protected + lifecycle.LOCK_PROVIDER + "/standing-protection",
                    "type": "Microsoft.Authorization/locks", "properties": {"level": "CanNotDelete"},
                }]}, None
            return self.arm(method, resource_id, api, *args, **kwargs)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "CLEANUP_LOCKED"):
            lifecycle.deploy(self.env, self.approved, self.private, locks, run=self.azd)
        self.assertEqual(self.azd_calls, [])
        (self.private / "receipt.json").unlink()
        protected = sibling
        lifecycle.deploy(self.env, self.approved, self.private, locks, run=self.azd)
        self.assertEqual(self.receipt()["state"], "OWNED")

    def test_error_page_after_create_preserves_unknown_without_redeploy(self):
        def paginated(method, resource_id, api, *args, next_link=None, **kwargs):
            if resource_id == GROUP + lifecycle.DEPLOY_PROVIDER and self.arm.created:
                if next_link:
                    return 403, {"error": {"message": "not absence"}}, None
                link = lifecycle.ARM_ORIGIN + resource_id + "?api-version=" + api + "&$skiptoken=2"
                return 200, {"value": [self.arm.deployment], "nextLink": link}, None
            return self.arm(method, resource_id, api, *args, **kwargs)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY"):
            lifecycle.deploy(self.env, self.approved, self.private, paginated, run=self.azd)
        self.assertEqual(self.receipt()["state"], "UNKNOWN")
        self.assertEqual(self.receipt()["azd_exit"], 0)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "RETRY_BLOCKED"):
            self.deploy()
        with self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY_UNKNOWN"):
            lifecycle.cleanup(self.approved, self.private, self.arm)
        self.assertEqual(len(self.azd_calls), 1)
        self.assertFalse(self.arm.deleted)

    def test_encryption_requires_pinned_binary_and_never_emits_plaintext(self):
        self.deploy()
        self.encryption.stop()
        binary = self.base / "age"
        binary.write_bytes(b"synthetic age executable")
        env = {**self.env, "AGENTOPS_CI_AGE_BIN": str(binary),
               "AGENTOPS_CI_AGE_SHA256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        def fake_age(argv, **kwargs):
            self.assertEqual(argv, [str(binary), "-r", self.approved["age_recipient"]])
            self.assertIn(APP_ID.encode(), kwargs["input"])
            return subprocess.CompletedProcess(argv, 0, b"age-encryption.org/v1\nciphertext", b"")
        with redirect_stdout(io.StringIO()) as output:
            lifecycle.encrypt(self.private, self.approved, env, run=fake_age)
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn(APP_ID.encode(), (self.private / "inventory.age").read_bytes())
        binary.write_bytes(b"changed")
        with self.assertRaisesRegex(lifecycle.LifecycleError, "CUSTODY"):
            lifecycle.encrypt(self.private, self.approved, env, run=fake_age)

    def test_no_follow_and_hardlink_checks_before_truncation(self):
        source = self.private / "source"
        lifecycle.write(source, {"preserve": True})
        alias = self.private / "alias"
        os.link(source, alias)
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.write(alias, {})
        self.assertEqual(json.loads(source.read_text()), {"preserve": True})
        alias.unlink()
        alias.symlink_to(source)
        with self.assertRaises(OSError):
            lifecycle.write(alias, {})

    def test_workflow_privately_prepares_finalizes_and_exports_only_ciphertext(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        prepare = next(step for step in steps if step.get("id") == "mcp-aca-lifecycle")
        finalizer = next(step for step in steps if step.get("name") == "Finalize exact MCP ACA app lifecycle")
        upload = next(step for step in steps if step.get("name") == "Preserve encrypted MCP ACA inventory")
        self.assertIn("mcp-aca-ci-lifecycle.py check", prepare["run"])
        self.assertLess(prepare["run"].index(" check"), prepare["run"].index("setup-agentops-age"))
        self.assertNotIn("continue-on-error", prepare)
        self.assertIn("always()", finalizer["if"])
        self.assertEqual(finalizer["timeout-minutes"], 5)
        self.assertTrue(finalizer["continue-on-error"])
        self.assertIn('git show "$GITHUB_SHA:scripts/mcp-aca-ci-lifecycle.py"', finalizer["run"])
        self.assertTrue(upload["with"]["path"].endswith("/inventory.age"))
        self.assertEqual(upload["with"]["retention-days"], 1)
        for step in steps:
            if step.get("id") == "run" or step.get("name") == "Retry once on classified-transient failure":
                self.assertNotIn("MCP_ACA_CI_LIFECYCLE_APPROVAL_JSON", step.get("env", {}))
        retry = next(step for step in steps if step.get("name") == "Retry once on classified-transient failure")
        self.assertIn("RETRY_REQUIRES_INVENTORY_RECONCILIATION", retry["run"])


class PaginationTests(unittest.TestCase):
    COLLECTION = GROUP + lifecycle.DEPLOY_PROVIDER
    URL = lifecycle.ARM_ORIGIN + COLLECTION + "?api-version=" + lifecycle.DEPLOY_API

    def test_383_standing_deployments_are_not_truncated(self):
        standing = [{"id": self.COLLECTION + f"/standing-{index}"} for index in range(383)]
        offset = 0
        def arm(*_args, **kwargs):
            nonlocal offset
            if offset:
                self.assertEqual(kwargs["next_link"], self.URL + f"&$skiptoken={offset}")
            page = {"value": standing[offset:offset + 100]}
            offset += 100
            if offset < len(standing):
                page["nextLink"] = self.URL + f"&$skiptoken={offset}"
            return 200, page, None
        self.assertEqual(lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API), standing)
        self.assertEqual(offset, 400)

    def test_multi_page_terminal_forms_and_opaque_cursor(self):
        for end in ({}, {"nextLink": None}, {"nextLink": ""}):
            with self.subTest(end=end):
                link = self.URL + "&$skiptoken=a%2Fb%2Bc%3D"
                responses = iter((
                    (200, {"value": [{"id": "first"}], "nextLink": link}, None),
                    (200, {"value": [{"id": "second"}], **end}, None),
                ))
                calls = []
                def arm(*args, **kwargs):
                    calls.append((args, kwargs))
                    return next(responses)
                self.assertEqual(lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API),
                                 [{"id": "first"}, {"id": "second"}])
                self.assertEqual(calls[1][1], {"next_link": link})

    def test_changed_url_or_api_rejected_before_following(self):
        invalid = (
            self.URL.replace("https:", "http:"), self.URL.replace("management.azure.com", "other.test"),
            self.URL.replace("management.azure.com", "management.azure.com:443"),
            self.URL.replace("management.azure.com", "user@management.azure.com"),
            self.URL.replace("rg-awesome-gbb-ci", "other-rg"), self.URL.replace(ID, "f" * 36),
            self.URL.replace("/deployments?", "/deployments/other/operations?"),
            self.URL.replace("/deployments?", "/deployments/../deployments?"),
            self.URL.replace("2022-09-01", "2025-04-01"), self.URL + "&api-version=2022-09-01",
            self.URL + "&API-VERSION=2025-04-01",
            self.URL + "#fragment", self.URL + "\n", self.URL + "\\x", self.URL + "&broken",
            self.URL + "&$skiptoken=x&$skiptoken=y", "/relative/path", True, {},
        )
        for link in invalid:
            with self.subTest(link=link):
                calls = []
                def arm(*args, **kwargs):
                    calls.append(args)
                    return 200, {"value": [], "nextLink": link}, None
                with self.assertRaisesRegex(lifecycle.LifecycleError, "CONTINUATION"):
                    lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API)
                self.assertEqual(len(calls), 1)

    def test_loop_page_item_byte_and_time_caps_never_return_partial_inventory(self):
        calls = []
        def arm(*args, **kwargs):
            calls.append(args)
            return 200, {"value": [{"id": "item"}], "nextLink": self.URL + "&$skiptoken=same"}, None
        with self.assertRaisesRegex(lifecycle.LifecycleError, "CONTINUATION_LOOP"):
            lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API)
        self.assertEqual(len(calls), 2)
        for cap, limit in (("MAX_LIST_PAGES", 1), ("MAX_LIST_ITEMS", 0), ("MAX_LIST_BYTES", 1)):
            with self.subTest(cap=cap), patch.object(lifecycle, cap, limit), \
                 self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY_LIMIT"):
                lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API)
        with self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY_LIMIT"):
            lifecycle.inventory(arm, self.COLLECTION, lifecycle.DEPLOY_API,
                                clock=iter((0, 0, lifecycle.LIST_SECONDS)).__next__)

    def test_error_or_malformed_second_page_cannot_return_first_page(self):
        for status, body in ((401, {}), (403, {}), (404, {"error": {"code": "ResourceNotFound"}}),
                             (500, {}), (200, {"value": None}), (200, {"value": [None]})):
            responses = iter(((200, {"value": [{"id": "first"}],
                                     "nextLink": self.URL + "&$skiptoken=2"}, None),
                              (status, body, None)))
            with self.subTest(status=status, body=body), \
                 self.assertRaisesRegex(lifecycle.LifecycleError, "INVENTORY"):
                lifecycle.inventory(lambda *_args, **_kwargs: next(responses),
                                    self.COLLECTION, lifecycle.DEPLOY_API)

    def test_real_transport_validates_link_before_acquiring_credentials(self):
        account = {"id": ID, "tenantId": ID,
                   "user": {"type": "servicePrincipal", "name": ID}}
        env = {"AZURE_SUBSCRIPTION_ID": ID, "AZURE_TENANT_ID": ID, "AZURE_CLIENT_ID": ID}
        class Response(io.BytesIO):
            code = 200
            headers = {}
        with patch.object(lifecycle.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(account).encode())) as cli:
            arm = lifecycle.Arm(env)
            cli.reset_mock()
            with self.assertRaisesRegex(lifecycle.LifecycleError, "CONTINUATION"):
                arm("GET", self.COLLECTION, lifecycle.DEPLOY_API,
                    next_link=self.URL.replace("management.azure.com", "other.test"))
            cli.assert_not_called()
            with self.assertRaisesRegex(lifecycle.LifecycleError, "MUTATION_GUARD"):
                arm("DELETE", APP_ID, lifecycle.API)
            cli.assert_not_called()
            cli.return_value = subprocess.CompletedProcess([], 0, b"synthetic-token")
            link = self.URL + "&$skiptoken=opaque%2Fcursor"
            with patch.object(lifecycle, "build_opener") as opener:
                opener.return_value.open.return_value = Response(b'{"value":[]}')
                self.assertEqual(arm("GET", self.COLLECTION, lifecycle.DEPLOY_API, next_link=link)[0], 200)
                self.assertEqual(opener.return_value.open.call_args.args[0].full_url, link)


if __name__ == "__main__":
    unittest.main()

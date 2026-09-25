"""Offline exact-resource lifecycle tests; no Azure credentials or calls."""

import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError, URLError
import uuid


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "skills/foundry-mcp-aca/references/python/fixture_ownership.py"
GUARD = ROOT / "skills/foundry-mcp-aca/references/bash/fixture_cleanup_guard.sh"
SPEC = importlib.util.spec_from_file_location("mcp_fixture_ownership", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def scope(**overrides):
    values = {
        "run_id": str(uuid.UUID(int=1)), "subscription": str(uuid.UUID(int=2)),
        "tenant": str(uuid.UUID(int=3)), "resource_group": "shared-test-rg",
        "app_name": "test-owned-app", "registry": "sharedregistry.azurecr.io",
    }
    return MODULE.Scope(**(values | overrides))


def app(identity):
    return {
        "id": identity.app_id, "tags": {"gbb-smoke-run": identity.run_id},
        "etag": '"owned-etag"',
        "systemData": {"createdAt": "2026-01-01T00:00:00Z"},
        "properties": {"template": {"containers": [
            {"image": "sharedregistry.azurecr.io/shared-repository:run-tag"},
        ]}},
    }


class FakeArm:
    def __init__(self, identity):
        self.scope = identity
        self.current = None
        self.calls = []
        self.fail_get = False
        self.fail_delete = False
        self.pending = False
        self.context_ok = True
        self.delete_returned = False
        self.unclassified_after_delete = 0

    def verify_context(self):
        self.calls.append(("context", self.scope.subscription))
        if not self.context_ok:
            raise MODULE.OwnershipError("Approved subscription/tenant mismatch")

    def request(self, method, resource_id, **kwargs):
        self.calls.append((method, resource_id, kwargs))
        if method == "DELETE":
            if self.fail_delete:
                raise MODULE.OwnershipError("ARM HTTP 403; absence not established")
            if not self.pending:
                self.current = None
            self.delete_returned = True
            return {}
        if self.delete_returned and self.unclassified_after_delete:
            self.unclassified_after_delete -= 1
            raise MODULE.UnclassifiedNotFound("ARM HTTP 404; absence not established")
        if self.fail_get:
            raise MODULE.OwnershipError("ARM transport failure")
        if resource_id == self.scope.group_id:
            return {"id": resource_id}
        return copy.deepcopy(self.current)

    @property
    def deletes(self):
        return [call for call in self.calls if call[0] == "DELETE"]


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ownership.json"
        self.scope = scope()
        self.arm = FakeArm(self.scope)

    def started(self):
        MODULE.prepare(self.path, self.scope, self.arm)
        MODULE.start(self.path, self.scope)
        self.arm.current = app(self.scope)

    def test_prepare_proves_absence_and_records_before_deploy(self):
        state = MODULE.prepare(self.path, self.scope, self.arm)
        self.assertIs(state["absent_before"], True)
        self.assertFalse(state["deploy_started"])
        self.assertEqual(state["app_id"], self.scope.app_id)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.arm.deletes, [])

    def test_existing_app_is_never_adopted_even_with_matching_tag(self):
        self.arm.current = app(self.scope)
        with self.assertRaisesRegex(MODULE.OwnershipError, "already exists"):
            MODULE.prepare(self.path, self.scope, self.arm)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.arm.deletes, [])

    def test_missing_inventory_never_contacts_azure(self):
        with self.assertRaises(MODULE.OwnershipError):
            MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(self.arm.calls, [])

    def test_wrong_run_subscription_tenant_and_app_rejected_before_transport(self):
        self.started()
        for change in (
            {"run_id": str(uuid.UUID(int=9))},
            {"subscription": str(uuid.UUID(int=9))},
            {"tenant": str(uuid.UUID(int=9))},
            {"resource_group": "different-shared-rg"},
            {"app_name": "another-app"},
        ):
            with self.subTest(change=change):
                self.arm.calls.clear()
                with self.assertRaises(MODULE.OwnershipError):
                    MODULE.cleanup(self.path, scope(**change), self.arm)
                self.assertEqual(self.arm.calls, [])

    def test_forged_resource_id_and_absence_proof_rejected(self):
        self.started()
        original = self.path.read_text()
        for field, value in (("app_id", self.scope.group_id), ("absent_before", "true")):
            state = json.loads(original)
            state[field] = value
            self.path.write_text(json.dumps(state))
            with self.subTest(field=field), self.assertRaises(MODULE.OwnershipError):
                MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(self.arm.deletes, [])

    def test_capture_and_success_delete_only_exact_app(self):
        self.started()
        captured = MODULE.capture(self.path, self.scope, self.arm)
        self.assertEqual(captured["app_receipts"][0]["id"], self.scope.app_id)
        state = MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(state["cleanup_state"], "app_absent_verified")
        self.assertEqual(self.arm.deletes, [
            ("DELETE", self.scope.app_id, {"etag": '"owned-etag"'}),
        ])
        self.assertTrue(state["residuals"])
        self.assertFalse(state["cleanup_complete"])
        self.assertFalse(state["residuals"][0]["retention_approved"])
        self.assertIn("custody not proven", state["residuals"][0]["reason"])
        self.assertEqual(state["residuals"][0]["registry"], self.scope.registry)

    def test_unknown_create_reconciles_matching_id_and_tag_without_replay(self):
        self.started()
        self.assertEqual(MODULE.load(self.path, self.scope)["app_receipts"], [])
        state = MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(state["app_receipts"][0]["id"], self.scope.app_id)
        self.assertEqual(len(self.arm.deletes), 1)
        with self.assertRaisesRegex(MODULE.OwnershipError, "reconcile"):
            MODULE.prepare(self.path, self.scope, self.arm)
        with self.assertRaisesRegex(MODULE.OwnershipError, "reconcile"):
            MODULE.start(self.path, self.scope)

    def test_failed_create_with_no_app_still_reports_possible_build_artifacts(self):
        MODULE.prepare(self.path, self.scope, self.arm)
        MODULE.start(self.path, self.scope)
        state = MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(self.arm.deletes, [])
        self.assertEqual(state["cleanup_state"], "app_absent_verified")
        self.assertTrue(state["residuals"])

    def test_other_run_or_missing_tag_never_deleted(self):
        self.started()
        for tags in ({}, {"gbb-smoke-run": str(uuid.UUID(int=9))}, None):
            self.arm.current = app(self.scope)
            self.arm.current["tags"] = tags
            with self.subTest(tags=tags), self.assertRaises(MODULE.OwnershipError):
                MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(self.arm.deletes, [])

    def test_auth_network_and_delete_failures_are_not_absence(self):
        self.started()
        for flag in ("fail_get", "fail_delete"):
            setattr(self.arm, flag, True)
            with self.subTest(flag=flag), self.assertRaises(MODULE.OwnershipError):
                MODULE.cleanup(self.path, self.scope, self.arm)
            self.assertEqual(MODULE.load(self.path, self.scope)["cleanup_state"], "unresolved")
            setattr(self.arm, flag, False)

    def test_wrong_actual_context_blocks_delete(self):
        self.started()
        self.arm.context_ok = False
        with self.assertRaises(MODULE.OwnershipError):
            MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(self.arm.deletes, [])

    def test_pending_delete_is_not_reissued(self):
        self.started()
        self.arm.pending = True
        ticks = iter((0, 0, 211))
        with self.assertRaisesRegex(MODULE.OwnershipError, "still pending"):
            MODULE.cleanup(self.path, self.scope, self.arm, clock=lambda: next(ticks), sleep=lambda _: None)
        self.assertEqual(len(self.arm.deletes), 1)
        self.assertEqual(MODULE.load(self.path, self.scope)["cleanup_state"], "unresolved")

    def test_unclassified_post_delete_404_waits_for_typed_absence(self):
        self.started()
        self.arm.unclassified_after_delete = 1
        state = MODULE.cleanup(self.path, self.scope, self.arm, sleep=lambda _: None)
        self.assertEqual(state["cleanup_state"], "app_absent_verified")
        self.assertEqual(len(self.arm.deletes), 1)
        self.assertEqual(state["observation_notes"], ["ARM HTTP 404; absence not established"])

    def test_unclassified_404_alone_cannot_pass_cleanup(self):
        self.started()
        self.arm.unclassified_after_delete = 2
        ticks = iter((0, 0, 181))
        with self.assertRaisesRegex(MODULE.OwnershipError, "still pending"):
            MODULE.cleanup(self.path, self.scope, self.arm, clock=lambda: next(ticks), sleep=lambda _: None)
        self.assertEqual(len(self.arm.deletes), 1)
        self.assertEqual(MODULE.load(self.path, self.scope)["cleanup_state"], "unresolved")

    def test_never_attempted_deployment_can_finish_without_residuals(self):
        MODULE.prepare(self.path, self.scope, self.arm)
        state = MODULE.cleanup(self.path, self.scope, self.arm)
        self.assertEqual(state["residuals"], [])
        self.assertTrue(state["cleanup_complete"])
        self.assertEqual(self.arm.deletes, [])

    def test_export_redacts_scope_without_altering_private_inventory(self):
        self.started()
        self.arm.current["id"] = self.scope.app_id.upper()
        state = MODULE.capture(self.path, self.scope, self.arm)
        original = self.path.read_bytes()
        destination = self.path.with_name("evidence.json")
        MODULE.report(destination, state, self.scope)
        text = destination.read_text()
        for value in (self.scope.subscription, self.scope.tenant,
                      self.scope.resource_group, self.scope.registry):
            self.assertNotIn(value, text)
            self.assertNotIn(value.upper(), text)
        self.assertEqual(self.path.read_bytes(), original)
        exported = json.loads(text)
        self.assertEqual(exported["run_id"], self.scope.run_id)
        self.assertEqual(len(exported["scope_sha256"]), 64)


class TransportTests(unittest.TestCase):
    def test_real_command_and_request_shape_only_targets_approved_app(self):
        identity = scope()
        commands, requests = [], []

        def run(args, **kwargs):
            commands.append(args)
            self.assertEqual(kwargs["timeout"], 15)
            self.assertEqual(args[-2:], ["--subscription", identity.subscription])
            stdout = json.dumps({"id": identity.subscription, "tenantId": identity.tenant})
            if "get-access-token" in args:
                stdout = "not-a-real-token\n"
            return subprocess.CompletedProcess(args, 0, stdout, "")

        def open_request(request, **kwargs):
            requests.append(request)
            self.assertEqual(kwargs["timeout"], 15)
            return io.BytesIO(b"{}")

        transport = MODULE.Arm(identity, runner=run, opener=open_request)
        transport.verify_context()
        transport.request("DELETE", identity.app_id, etag='"etag"')
        self.assertEqual([r.get_method() for r in requests], ["DELETE"])
        self.assertEqual(requests[0].full_url,
                         f"https://management.azure.com{identity.app_id}?api-version=2024-03-01")
        self.assertEqual(requests[0].get_header("If-match"), '"etag"')
        self.assertTrue(all(cmd[:2] == ["az", "account"] for cmd in commands))
        for target in (
            identity.group_id,
            identity.group_id + "/providers/Microsoft.ContainerRegistry/registries/shared",
            identity.group_id + "/providers/Microsoft.App/managedEnvironments/shared",
            identity.group_id + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/shared",
            identity.group_id + "/providers/Microsoft.Resources/deployments/shared",
            identity.group_id + "/providers/Microsoft.App/containerApps/shared-app",
        ):
            with self.assertRaises(MODULE.OwnershipError):
                transport.request("DELETE", target)
        self.assertEqual(len(requests), 1)

    def test_only_typed_arm_404_is_absence(self):
        identity = scope()
        transport = MODULE.Arm(identity)
        transport.token = "not-a-real-token"
        cases = (
            (404, "ResourceNotFound", True),
            (404, "SubscriptionNotFound", False),
            (404, None, False),
            (401, "Unauthorized", False),
            (403, "AuthorizationFailed", False),
            (500, "InternalError", False),
        )
        for status, code, absent in cases:
            def fail(request, **kwargs):
                raise HTTPError(request.full_url, status, "test", {}, io.BytesIO(
                    json.dumps({"error": {"code": code}}).encode()
                ))
            transport.opener = fail
            with self.subTest(status=status, code=code):
                if absent:
                    self.assertIsNone(transport.request("GET", identity.app_id))
                else:
                    with self.assertRaises(MODULE.OwnershipError):
                        transport.request("GET", identity.app_id)
        def unavailable(*args, **kwargs):
            raise URLError("unavailable")
        transport.opener = unavailable
        with self.assertRaises(MODULE.OwnershipError):
            transport.request("GET", identity.app_id)


class FailureGuardTests(unittest.TestCase):
    def test_actual_provision_block_success_and_failure_paths(self):
        from test_foundry_mcp_aca_fixture_contract import (
            FIXTURE, STATE_PATH, SMOKE_MARKER_PATH, _isolated_shipped_state_file,
            _isolated_shipped_smoke_marker, _provision_block, _teardown_block,
        )
        fixture = FIXTURE.read_text()
        for azd_status, capture_status, expected in ((0, 0, 0), (23, 0, 23), (0, 41, 41)):
            with (
                self.subTest(azd=azd_status, capture=capture_status),
                tempfile.TemporaryDirectory() as directory,
                _isolated_shipped_state_file(),
                _isolated_shipped_smoke_marker(),
            ):
                root = Path(directory)
                project = root / "project"
                project.mkdir()
                binaries = root / "bin"
                binaries.mkdir()
                log = root / "commands"
                for name, text in {
                    "azd": '#!/bin/sh\nprintf "azd %s\\n" "$*" >> "$COMMAND_LOG"\nexit "$AZD_STATUS"\n',
                    "python3": (
                        '#!/bin/sh\nprintf "helper %s\\n" "$2" >> "$COMMAND_LOG"\n'
                        'if [ "$2" = capture ]; then exit "$CAPTURE_STATUS"; fi\n'
                        'if [ "$2" = cleanup ]; then exit 2; fi\n'
                    ),
                }.items():
                    executable = binaries / name
                    executable.write_text(text)
                    executable.chmod(0o755)
                STATE_PATH.write_text(
                    f"APP_NAME={scope().app_name}\nPROJECT_DIR={project}\n"
                    f"SMOKE_RUN_ID={scope().run_id}\nACR_SERVER={scope().registry}\n"
                    "UAMI_RESOURCE_ID=unchanged-shared-identity\n"
                )
                env = {
                    **os.environ, "PATH": f"{binaries}:{os.defpath}",
                    "GITHUB_WORKSPACE": str(ROOT),
                    "AZURE_SUBSCRIPTION_ID": scope().subscription,
                    "AZURE_TENANT_ID": scope().tenant,
                    "COMMAND_LOG": str(log), "AZD_STATUS": str(azd_status),
                    "CAPTURE_STATUS": str(capture_status),
                }
                result = subprocess.run(
                    ["bash", "-c", _provision_block(fixture)], env=env,
                    capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                calls = log.read_text().splitlines()
                self.assertEqual(calls[:3], ["helper prepare", "helper start", "azd up --no-prompt"])
                self.assertEqual(calls.count("azd up --no-prompt"), 1)
                if expected:
                    self.assertEqual(calls[-1], "helper cleanup")
                    self.assertTrue(SMOKE_MARKER_PATH.read_text().startswith("SMOKE_RESULT=FAIL"))
                else:
                    self.assertEqual(calls[-1], "helper capture")
                    SMOKE_MARKER_PATH.write_text("SMOKE_RESULT=PASS\n")
                    result = subprocess.run(
                        ["bash", "-c", _teardown_block(fixture)], env=env,
                        capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0)
                    self.assertIn("NOTE: teardown incomplete", result.stdout)
                    self.assertEqual(SMOKE_MARKER_PATH.read_text(), "SMOKE_RESULT=PASS\n")
                    self.assertEqual(log.read_text().splitlines()[-1], "helper cleanup")
                self.assertNotIn("azd down", log.read_text())

    def test_intermediate_failure_preserves_original_status_even_if_cleanup_fails(self):
        for cleanup_status in (0, 2, 124):
            with self.subTest(cleanup_status=cleanup_status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                stub = root / "python3"
                log = root / "commands"
                stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$COMMAND_LOG"\nexit "$CLEANUP_STATUS"\n')
                stub.chmod(0o755)
                result = subprocess.run(
                    ["bash", "-c", f"source '{GUARD}'; exit 42"],
                    env={
                        **os.environ, "PATH": f"{root}:{os.defpath}",
                        "GITHUB_WORKSPACE": str(ROOT), "SMOKE_RUN_ID": scope().run_id,
                        "AZURE_SUBSCRIPTION_ID": scope().subscription,
                        "AZURE_TENANT_ID": scope().tenant,
                        "APP_NAME": scope().app_name, "ACR_SERVER": scope().registry,
                        "COMMAND_LOG": str(log), "CLEANUP_STATUS": str(cleanup_status),
                    }, capture_output=True, text=True, timeout=5,
                )
                self.assertEqual(result.returncode, 42)
                self.assertEqual(len(log.read_text().splitlines()), 1)
                self.assertIn("fixture_ownership.py cleanup", log.read_text())
                self.assertNotIn("azd down", log.read_text())
                if cleanup_status:
                    self.assertIn("NOTE: teardown incomplete", result.stdout)

    def test_successful_intermediate_step_does_not_delete_app(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stub = root / "python3"
            stub.write_text("#!/bin/sh\nexit 99\n")
            stub.chmod(0o755)
            result = subprocess.run(
                ["bash", "-c", f"source '{GUARD}'; true"],
                env={**os.environ, "PATH": f"{root}:{os.defpath}"},
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

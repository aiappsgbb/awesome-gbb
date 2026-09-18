"""Offline Jobs lifecycle adapters. Fakes are not Azure acceptance evidence."""
from copy import deepcopy
import base64
from datetime import datetime, timezone, timedelta
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("jobs_lifecycle", ROOT / "scripts/jobs-ci-lifecycle.py")
j = importlib.util.module_from_spec(spec)
spec.loader.exec_module(j)
SUB, TENANT, CLIENT, CALLER, AUTH = [str(i) * 8 + "-" + str(i) * 4 + "-" + str(i) * 4 +
                                   "-" + str(i) * 4 + "-" + str(i) * 12 for i in range(1, 6)]
GROUP = f"/subscriptions/{SUB}/resourceGroups/ci"
NOW = datetime(2026, 9, 18, 1, tzinfo=timezone.utc)


class FakeArm:
    def __init__(self, ledger):
        self.ledger, self.documents, self.writes, self.reads = ledger, {}, [], []
        self.before_token = lambda: None
        self.put_status, self.delete_status, self.lost_ack = 201, 202, False

    def __call__(self, method, rid, api, etag=None, **kwargs):
        self.reads.append((method, rid))
        if method == "DELETE":
            self.before_token()
            kwargs["before_send"]()
            self.writes.append((method, rid))
            if self.lost_ack:
                raise j.Error("NETWORK")
            self.documents.pop(rid, None)
            return self.delete_status, {}, None
        if rid.endswith(j.common.LOCK_PROVIDER):
            return 200, {"value": []}, None
        if rid in self.documents:
            return 200, deepcopy(self.documents[rid]), '"etag"'
        return 404, {"error": {"code": "ResourceNotFound"}}, None

    def put(self, rid, api, body, before_send, **kwargs):
        self.before_token()
        before_send()
        self.writes.append(("PUT", rid))
        if self.lost_ack:
            raise j.Error("NETWORK")
        value = deepcopy(body)
        value.update(id=rid, etag='"etag"')
        if "/sqlDatabases/" in rid:
            value["properties"]["resource"]["_rid"] = "immutable-container-rid"
        else:
            value["properties"]["lastModifiedTime"] = NOW.isoformat()
        self.documents[rid] = value
        return self.put_status, deepcopy(value), '"etag"'


class JobsLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name).resolve()
        native = {
            "schema_version": 1, "skill": "foundry-hosted-agents", "repository": "example/catalog",
            "sha": "a" * 40, "run_id": "100", "run_attempt": "1", "tenant_id": TENANT, "client_id": CLIENT,
            "project_id": GROUP + "/providers/Microsoft.CognitiveServices/accounts/ci/projects/test",
            "project_endpoint": "https://ci.services.ai.azure.com/api/projects/test",
            "acr_server": "testregistry.azurecr.io", "model": "gpt-5.4-mini",
            "expires_at": "2026-09-18T04:00:00Z", "retain_until": "2026-09-19T04:00:00Z",
            "age_recipient": "age1" + "q" * 58, "owner": "CI owner", "purpose": "one synthetic test",
            "delete_reconciled_native_objects": True, "retain_images_identities_and_stored_responses": True,
            "temporary_foundry_user_grants": False,
        }
        self.a = {"native": native, "resource_group_id": GROUP, "cosmos_database": "standing",
                  "caller_principal_id": CALLER, "auth_client_id": AUTH,
                  "cosmos_endpoint": "https://dedicated.documents.azure.com:443/",
                  "storage_url": "https://dedicated.blob.core.windows.net",
                  "network_perimeter_id": "",
                  "delete_run_resources": True, "standing_resources_retained": True,
                  **{key: GROUP + "/providers/" + provider + "/" + (
                      "app" if key == "app_identity_id" else "worker" if key == "worker_identity_id" else "dedicated")
                     for key, provider in j.PROVIDERS.items()}}
        self.env = {
            "RUNNER_TEMP": str(self.temp), "GITHUB_REPOSITORY": native["repository"], "GITHUB_SHA": native["sha"],
            "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1", "AZURE_SUBSCRIPTION_ID": SUB,
            "AZURE_TENANT_ID": TENANT, "AZURE_CLIENT_ID": CLIENT, "AZURE_AI_PROJECT_ID": native["project_id"],
            "FOUNDRY_PROJECT_ENDPOINT": native["project_endpoint"], "ACR_LOGIN_SERVER": native["acr_server"],
            "GITHUB_WORKSPACE": str(ROOT), **{variable: self.a[key] for key, variable in j.INPUTS.items()},
        }
        self.env["MCP_ACA_JOBS_CI_LIFECYCLE_APPROVAL_JSON"] = json.dumps(self.a)
        clock = patch.object(j.common, "utc_now", return_value=NOW)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        encrypt = patch.object(j.common, "encrypt")
        self.real_encrypt = j.common.encrypt
        self.encryption = encrypt.start()
        self.addCleanup(encrypt.stop)
        claims = base64.urlsafe_b64encode(json.dumps({
            "oid": CALLER, "tid": TENANT, "appid": CLIENT, "idtyp": "app",
        }).encode()).decode().rstrip("=")
        commands = patch.object(j.hosted, "command", return_value=("header." + claims + ".signature").encode())
        self.commands = commands.start()
        self.addCleanup(commands.stop)
        self.ledger = j.initialize(j.root(self.env), self.a, self.env)
        self.arm = FakeArm(self.ledger)
        for item in self.ledger.data["resources"].values():
            item["pre_get_404"] = True
        self.ledger.save()

    def own_app(self, kind="app"):
        item = self.ledger.data["resources"][kind]
        self.ledger.data["provision_started_at"] = "2026-09-18T00:59:59Z"
        body = {
            "id": item["id"], "systemData": {"createdAt": "2026-09-18T00:59:59.1234567"},
            "identity": {"userAssignedIdentities": {self.a["app_identity_id" if kind == "app" else "worker_identity_id"]: {}}},
            "properties": {"environmentId": self.a["environment_id"]},
        }
        self.arm.documents[item["id"]] = body
        item.update(state="OWNED", evidence={"operation_id": "op"}, binding=j.binding(kind, body, self.ledger))
        self.ledger.save()
        return body

    def test_approval_full_scope(self):
        self.assertEqual(j.approval(self.env), self.a)

    def test_approval_foreign_values_fail(self):
        for key, variable in j.INPUTS.items():
            with self.subTest(key=key), self.assertRaises(j.Error):
                j.approval({**self.env, variable: "foreign"})

    def test_same_identity_rejected(self):
        a = deepcopy(self.a)
        a["worker_identity_id"] = a["app_identity_id"]
        with self.assertRaisesRegex(j.Error, "SEPARATE_IDENTITIES"):
            j.approval({**self.env, j.INPUTS["worker_identity_id"]: a["worker_identity_id"]}, json.dumps(a))

    def test_resource_api_not_runner_client(self):
        a = deepcopy(self.a)
        a["auth_client_id"] = CLIENT
        with self.assertRaisesRegex(j.Error, "CALLER"):
            j.approval({**self.env, "MCP_AUTH_APP_CLIENT_ID": CLIENT}, json.dumps(a))

    def test_approval_dates_still_require_utc_z(self):
        a = deepcopy(self.a)
        a["native"]["expires_at"] = "2026-09-18T04:00:00"
        with self.assertRaisesRegex(j.Error, "DATE"):
            j.approval(self.env, json.dumps(a))

    def test_plaintext_approval_is_not_required_to_read_receipt_scope(self):
        (self.ledger.path / "approval.json").unlink()
        self.env.pop("MCP_ACA_JOBS_CI_LIFECYCLE_APPROVAL_JSON")
        receipt = j.common.parse(j.common.private_read(self.ledger.path / "receipt.json"))
        self.assertEqual(receipt["approval"], self.a)
        self.assertEqual(receipt["approval_sha256"], j.hosted.fingerprint(self.a))
        self.assertEqual(receipt["approval"]["native"]["owner"], "CI owner")
        self.assertTrue(self.encryption.called)

    def test_real_ciphertext_recovers_scope_without_secret_or_plaintext(self):
        age, keygen = shutil.which("age"), shutil.which("age-keygen")
        self.assertIsNotNone(age)
        self.assertIsNotNone(keygen)
        key = self.temp / "key"
        subprocess.run([keygen, "-o", str(key)], check=True, capture_output=True)
        recipient = subprocess.check_output([keygen, "-y", str(key)], text=True).strip()
        approved = deepcopy(self.a)
        approved["native"]["age_recipient"] = recipient
        binary = Path(age).resolve()
        env = {**self.env, "AGENTOPS_CI_AGE_BIN": str(binary),
               "AGENTOPS_CI_AGE_SHA256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        path = self.temp / "fresh-custody"
        with patch.object(j.common, "encrypt", side_effect=self.real_encrypt):
            j.initialize(path, approved, env)
        (path / "approval.json").unlink()
        (path / "receipt.json").unlink()
        env.pop("MCP_ACA_JOBS_CI_LIFECYCLE_APPROVAL_JSON")
        receipt = json.loads(subprocess.check_output([age, "--decrypt", "-i", str(key), str(path / "inventory.age")]))
        self.assertEqual(receipt["approval"], approved)
        self.assertEqual(receipt["approval_sha256"], j.hosted.fingerprint(approved))
        self.assertEqual(receipt["approval"]["native"]["owner"], "CI owner")
        self.assertNotIn(b"CI owner", (path / "inventory.age").read_bytes())

    def test_disabled_or_unclassified_standing_network_is_not_usable(self):
        standing = {
            "storage_account_id": {"properties": {"allowSharedKeyAccess": False,
                "allowBlobPublicAccess": False, "publicNetworkAccess": "Enabled"}},
            "cosmos_account_id": {"properties": {"disableLocalAuth": True, "publicNetworkAccess": "Enabled"}},
        }
        j.validate_standing_posture(standing)
        for kind in standing:
            for value in ("Disabled", None, "SecuredByPerimeter"):
                changed = deepcopy(standing)
                changed[kind]["properties"]["publicNetworkAccess"] = value
                with self.subTest(kind=kind, value=value), self.assertRaises(j.Error):
                    j.validate_standing_posture(changed)
        self.assertFalse(self.arm.writes)

    def test_timeout_is_not_swallowed_by_independent_cleanup(self):
        with self.assertRaisesRegex(j.Error, "DEADLINE"):
            j.error_code(j.Error("DEADLINE"))

    def perimeter_documents(self):
        perimeter = GROUP + "/providers/Microsoft.Network/networkSecurityPerimeters/dedicated"
        self.ledger.a["network_perimeter_id"] = perimeter
        profile = perimeter + "/profiles/jobs-data"
        return {
            profile + "/accessRules": [{"id": profile + "/accessRules/ci-subscription", "properties": {
                "provisioningState": "Succeeded", "direction": "Inbound",
                "subscriptions": [{"id": "/subscriptions/" + SUB}]}}],
            perimeter + "/profiles": [{"id": profile}],
            perimeter + "/resourceAssociations": [
                {"id": perimeter + "/resourceAssociations/" + name, "properties": {
                    "provisioningState": "Succeeded", "accessMode": "Enforced",
                    "profile": {"id": profile}, "privateLinkResource": {"id": self.a[key]}}}
                for name, key in (("storage", "storage_account_id"), ("cosmos", "cosmos_account_id"))],
        }

    def test_exact_enforced_perimeter_is_recorded_read_only(self):
        documents = self.perimeter_documents()
        with patch.object(j.common, "inventory", side_effect=lambda arm, rid, api: documents[rid]):
            j.verify_perimeter(self.ledger, self.arm)
        self.assertEqual(len(self.ledger.data["perimeter_binding"]["associations"]), 2)
        self.assertFalse(self.arm.writes)

    def test_extra_perimeter_members_or_rules_fail_closed(self):
        for collection in self.perimeter_documents():
            documents = self.perimeter_documents()
            documents[collection].append(deepcopy(documents[collection][0]))
            with self.subTest(collection=collection), patch.object(
                    j.common, "inventory", side_effect=lambda arm, rid, api: documents[rid]):
                with self.assertRaises(j.Error):
                    j.verify_perimeter(self.ledger, self.arm)
        self.assertFalse(self.arm.writes)

    def test_foreign_unenforced_or_wildcard_perimeter_fails(self):
        for field, value in (("accessMode", "Learning"), ("privateLinkResource", {"id": GROUP}),
                             ("profile", {"id": GROUP}), ("provisioningState", "Creating")):
            documents = self.perimeter_documents()
            next(v for k, v in documents.items() if k.endswith("resourceAssociations"))[0]["properties"][field] = value
            with self.subTest(field=field), patch.object(j.common, "inventory",
                    side_effect=lambda arm, rid, api: documents[rid]), self.assertRaises(j.Error):
                j.verify_perimeter(self.ledger, self.arm)
        for field, value in (("direction", "Outbound"), ("subscriptions", [{"id": GROUP}]),
                             ("addressPrefixes", ["0.0.0.0/0"]), ("fullyQualifiedDomainNames", ["*"])):
            documents = self.perimeter_documents()
            next(v for k, v in documents.items() if k.endswith("accessRules"))[0]["properties"][field] = value
            with self.subTest(field=field), patch.object(j.common, "inventory",
                    side_effect=lambda arm, rid, api: documents[rid]), self.assertRaises(j.Error):
                j.verify_perimeter(self.ledger, self.arm)
        self.assertFalse(self.arm.writes)

    def test_perimeter_read_failure_is_not_public_fallback(self):
        self.perimeter_documents()
        with patch.object(j.common, "inventory", side_effect=j.Error("INVENTORY")), self.assertRaises(j.Error):
            j.verify_perimeter(self.ledger, self.arm)
        self.assertNotIn("perimeter_binding", self.ledger.data)

    def test_secured_accounts_require_explicit_mode_and_cosmos_identity(self):
        standing = {
            "storage_account_id": {"properties": {"allowSharedKeyAccess": False,
                "allowBlobPublicAccess": False, "publicNetworkAccess": "SecuredByPerimeter"}},
            "cosmos_account_id": {"properties": {"disableLocalAuth": True,
                "publicNetworkAccess": "SecuredByPerimeter"},
                "identity": {"type": "SystemAssigned", "principalId": CALLER}},
        }
        with self.assertRaises(j.Error):
            j.validate_standing_posture(standing)
        j.validate_standing_posture(standing, "SecuredByPerimeter")
        standing["cosmos_account_id"]["identity"].clear()
        with self.assertRaisesRegex(j.Error, "PERIMETER_IDENTITY"):
            j.validate_standing_posture(standing, "SecuredByPerimeter")

    def test_custody_tampering_blocks_intent(self):
        self.ledger.data["approval"]["native"]["owner"] = "different"
        with self.assertRaisesRegex(j.Error, "CUSTODY"):
            self.ledger.intent("create-test")
        self.assertFalse(self.arm.writes)

    def test_incomplete_custody_prevents_producer(self):
        self.ledger.data.pop("approval")
        with self.assertRaisesRegex(j.Error, "CUSTODY"):
            self.ledger.intent("provision")
        self.assertFalse(self.arm.writes)

    def deployment(self):
        self.ledger.data["parameters"] = {"appName": "bound-app"}
        deployment = {"id": GROUP + j.common.DEPLOY_PROVIDER + "/run",
                      "properties": {"parameters": {"appName": {"value": "bound-app"}},
                                     "correlationId": AUTH, "provisioningState": "Succeeded"}}
        operations = []
        for kind, item in self.ledger.data["resources"].items():
            if kind in ("app", "job"):
                self.own_app(kind)
            elif kind == "cosmos":
                self.arm.documents[item["id"]] = {
                    "id": item["id"], "properties": {"resource": {
                        "id": item["id"].rsplit("/", 1)[1], "_rid": "native-rid",
                        "partitionKey": {"paths": ["/ownerScope"]},
                        "uniqueKeyPolicy": {"uniqueKeys": [{"paths": ["/idempotencyKeyHash"]}]},
                    }}}
            else:
                self.arm.documents[item["id"]] = {"id": item["id"], "etag": "etag", "properties": {
                    "publicAccess": "None", "lastModifiedTime": NOW.isoformat()}}
            item["state"] = "UNKNOWN"
            operations.append({"operationId": kind, "properties": {
                "provisioningOperation": "Create", "provisioningState": "Succeeded",
                "targetResource": {"id": item["id"].lower()},
            }})
        return deployment, operations

    def test_create_data_bound_to_native_deployment_operations(self):
        deployment, operations = self.deployment()
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]):
            j.capture_deployments(self.ledger, self.arm, [])
        for item in self.ledger.data["resources"].values():
            self.assertEqual(item["state"], "OWNED")
            self.assertEqual(item["evidence"]["parent_correlation_id"], AUTH)

    def test_provision_intent_does_not_retry(self):
        self.ledger.intent("provision")
        with self.assertRaisesRegex(j.Error, "RETRY_BLOCKED"):
            self.ledger.intent("provision")

    def test_update_status_does_not_prove_create(self):
        deployment, operations = self.deployment()
        operations[-1]["properties"]["provisioningOperation"] = "Update"
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "CREATE_ACK_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertEqual(self.ledger.data["resources"]["output"]["state"], "UNKNOWN")

    def test_preexisting_object_is_not_owned(self):
        item = self.ledger.data["resources"]["app"]
        self.arm.documents[item["id"]] = {"id": item["id"]}
        with self.assertRaisesRegex(j.Error, "PREEXISTING"):
            j.prepare_resources(self.ledger, self.arm)
        self.assertFalse(self.arm.writes)

    def test_expiry_during_preflight_zero_provision(self):
        def preflight(*args):
            self.clock.return_value = NOW + timedelta(hours=4)
        with patch.object(j, "prepare_resources", side_effect=preflight), \
                patch.object(j, "scaffold", return_value=self.temp), \
                patch.object(j.common, "inventory", return_value=[]), \
                patch.object(j.hosted, "command") as command, \
                self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
            j.deploy(self.ledger, self.arm)
        command.assert_not_called()

    def test_expiry_during_token_zero_auth_write(self):
        self.arm.before_token = lambda: setattr(self.clock, "return_value", NOW + timedelta(hours=4))
        with self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
            self.arm.put("auth", "api", {}, self.ledger.gate)
        self.assertFalse(self.arm.writes)

    def test_real_auth_adapter_checks_expiry_after_token_before_send(self):
        def token(*args):
            self.clock.return_value = NOW + timedelta(hours=4)
            return b"test-token"
        with patch.object(j.common.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"id": SUB, "tenantId": TENANT,
                    "user": {"type": "servicePrincipal", "name": CLIENT}}))):
            arm = j.Arm(self.ledger)
        rid = self.ledger.data["resources"]["app"]["id"] + "/authConfigs/current"
        with patch.object(j.hosted, "command", side_effect=token), patch.object(j, "build_opener") as opener:
            with self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
                arm.put(rid, "2025-01-01", {}, self.ledger.gate)
        opener.return_value.open.assert_not_called()

    def test_real_auth_adapter_binding_change_zero_send(self):
        body = self.own_app()
        def token(*args):
            body["identity"]["userAssignedIdentities"] = {}
            return b"test-token"
        with patch.object(j.common.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"id": SUB, "tenantId": TENANT,
                    "user": {"type": "servicePrincipal", "name": CLIENT}}))):
            arm = j.Arm(self.ledger)
        with patch.object(j.hosted, "command", side_effect=token), patch.object(j, "build_opener") as opener:
            with self.assertRaisesRegex(j.Error, "RESOURCE_BINDING"):
                arm.put(self.ledger.data["resources"]["app"]["id"] + "/authConfigs/current", "2025-01-01",
                        {}, lambda: j.read_owned(self.ledger, self.arm, "app"))
        opener.return_value.open.assert_not_called()

    def test_foreign_deployment_parameters_never_establish_ownership(self):
        deployment, operations = self.deployment()
        self.ledger.data["parameters"]["workerIdentityId"] = self.a["worker_identity_id"]
        deployment["properties"]["parameters"]["workerIdentityId"] = {"value": self.a["app_identity_id"]}
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "DEPLOYMENT_PARAMETERS"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertTrue(all(item["state"] == "UNKNOWN" for item in self.ledger.data["resources"].values()))

    def test_nsp_bootstrap_has_no_wildcard_and_preserves_brownfield_posture(self):
        module = (ROOT / "skills/azd-patterns/references/bicep/jobs-data-perimeter.bicep").read_text()
        data = (ROOT / "skills/azd-patterns/references/bicep/jobs-standing-data.bicep").read_text()
        standing = (ROOT / "skills/foundry-mcp-aca-jobs/templates/infra/standing.bicep").read_text()
        self.assertEqual(module.count("accessMode: 'Enforced'"), 1)
        self.assertIn("{ name: 'storage', id: storageId }", module)
        self.assertIn("{ name: 'cosmos', id: cosmosId }", module)
        self.assertIn("range(0, 2)", module)
        self.assertIn("subscriptions: [{ id: subscription().id }]", module)
        self.assertNotIn("Outbound", module)
        self.assertNotIn("0.0.0.0", module)
        self.assertIn("minimalTlsVersion: 'Tls12'", data)
        self.assertIn("enableAutomaticFailover: automaticFailover", data)
        self.assertIn("automaticFailover: cosmosAutomaticFailover", standing)
        self.assertIn("networkStage == 'associate' ? 'Disabled' : 'SecuredByPerimeter'", standing)

    def test_encryption_consumes_lifetime_zero_create(self):
        self.encryption.side_effect = lambda *args: setattr(self.clock, "return_value", NOW + timedelta(hours=4))
        with self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
            self.ledger.intent("provision")
        self.assertFalse(self.arm.writes)

    def test_unknown_global_state_blocks_replacement(self):
        self.ledger.data["blocked"] = True
        with self.assertRaisesRegex(j.Error, "UNKNOWN_BLOCKS"):
            self.ledger.intent("new-producer")

    def test_foreign_caller_blocks_all_producers(self):
        self.commands.return_value = b"a.e30.b"
        with self.assertRaisesRegex(j.Error, "CALLER"):
            j.prepare_resources(self.ledger, self.arm)
        self.assertFalse(self.arm.writes)

    def test_bounded_empty_pages(self):
        iterator = MagicMock()
        iterator.by_page.return_value = [[]] * 21
        with self.assertRaisesRegex(j.Error, "INVENTORY_LIMIT"):
            j.collect_pages(iterator, ("name",))

    def test_all_pages_including_terminal_are_captured(self):
        iterator = MagicMock()
        iterator.by_page.return_value = [[{"name": "a"}], [], [{"name": "b"}]]
        self.assertEqual(j.collect_pages(iterator, ("name",)), [{"name": "a"}, {"name": "b"}])

    def test_missing_record_binding_is_not_inventory_success(self):
        iterator = MagicMock()
        iterator.by_page.return_value = [[{"name": "a"}]]
        with self.assertRaisesRegex(j.Error, "DATA_INVENTORY"):
            j.collect_pages(iterator, ("name", "etag"))

    def test_record_cap(self):
        iterator = MagicMock()
        iterator.by_page.return_value = [[{"name": str(i)} for i in range(201)]]
        with self.assertRaisesRegex(j.Error, "INVENTORY_LIMIT"):
            j.collect_pages(iterator, ("name",))

    def test_partial_failed_deployment_preserves_proven_children(self):
        deployment, operations = self.deployment()
        deployment["properties"]["provisioningState"] = "Failed"
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations[:-1]]), \
                self.assertRaisesRegex(j.Error, "CREATE_ACK_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertEqual(self.ledger.data["resources"]["app"]["state"], "OWNED")
        self.assertEqual(self.ledger.data["resources"]["output"]["state"], "UNKNOWN")

    def test_explicit_failed_create_preserves_siblings_and_safe_app_cleanup(self):
        deployment, operations = self.deployment()
        deployment["properties"]["provisioningState"] = "Failed"
        failed = next(op for op in operations if op["operationId"] == "job")
        failed["properties"]["provisioningState"] = "Failed"
        operations.remove(failed)
        operations.insert(0, failed)
        encrypted = []
        self.encryption.side_effect = lambda path, *_: encrypted.append(
            json.loads((path / "receipt.json").read_text()))
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "CREATE_ACK_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertEqual(encrypted[-1]["capture_errors"], {"job": "CREATE_ACK_UNKNOWN"})
        for kind, item in encrypted[-1]["resources"].items():
            self.assertEqual(item["state"], "UNKNOWN" if kind == "job" else "OWNED")
            if kind != "job":
                self.assertEqual(item["evidence"]["parent_correlation_id"], AUTH)
        with patch.object(j, "verify_cascades"), patch.object(j, "data_inventory") as data, \
                patch.object(j.time, "sleep"), self.assertRaisesRegex(j.Error, "CLEANUP_RESIDUAL"):
            j.cleanup(self.ledger, self.arm)
        self.assertEqual(self.arm.writes, [("DELETE", self.ledger.data["resources"]["app"]["id"])])
        self.assertEqual(self.ledger.data["resources"]["app"]["state"], "ABSENT")
        self.assertEqual(self.ledger.data["resources"]["job"]["state"], "UNKNOWN")
        data.assert_not_called()

    def test_incomplete_child_enumeration_promotes_no_ownership(self):
        deployment, operations = self.deployment()
        operations.append({"operationId": "child", "properties": {
            "targetResource": {"id": GROUP + j.common.DEPLOY_PROVIDER + "/unreadable"},
        }})
        self.encryption.reset_mock()
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "DEPLOYMENT_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertTrue(all(item["state"] == "UNKNOWN" for item in self.ledger.data["resources"].values()))
        self.encryption.assert_not_called()

    def test_child_deployment_identity_must_match_before_any_capture(self):
        deployment, operations = self.deployment()
        child_id = GROUP + j.common.DEPLOY_PROVIDER + "/child"
        operations.append({"operationId": "child", "properties": {"targetResource": {"id": child_id}}})
        child = deepcopy(deployment)
        child["id"] = GROUP + j.common.DEPLOY_PROVIDER + "/different"
        self.arm.documents[child_id] = child
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "DEPLOYMENT_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertTrue(all(item["state"] == "UNKNOWN" for item in self.ledger.data["resources"].values()))

    def test_capture_custody_failure_stops_without_later_resource_reads(self):
        deployment, operations = self.deployment()
        self.encryption.side_effect = j.Error("CUSTODY_FAILED")
        self.arm.reads.clear()
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "CUSTODY_FAILED"):
            j.capture_deployments(self.ledger, self.arm, [])
        resource_reads = [rid for method, rid in self.arm.reads if method == "GET" and
                          rid in {item["id"] for item in self.ledger.data["resources"].values()}]
        self.assertEqual(resource_reads, [self.ledger.data["resources"]["app"]["id"]] * 2)
        self.assertFalse(self.arm.writes)

    def test_duplicate_create_evidence_never_owns_ambiguous_target(self):
        deployment, operations = self.deployment()
        duplicate = deepcopy(next(op for op in operations if op["operationId"] == "job"))
        duplicate["operationId"] = "different-job-operation"
        operations.append(duplicate)
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "CREATE_ACK_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertEqual(self.ledger.data["capture_errors"], {"job": "CREATE_ACK_UNKNOWN"})
        self.assertEqual(self.ledger.data["resources"]["job"]["state"], "UNKNOWN")
        self.assertEqual(self.ledger.data["resources"]["app"]["state"], "OWNED")

    def test_binding_failure_does_not_discard_other_resource_evidence(self):
        deployment, operations = self.deployment()
        self.arm.documents[self.ledger.data["resources"]["app"]["id"]]["id"] = GROUP + "/foreign"
        with patch.object(j.common, "inventory", side_effect=[[deployment], operations]), \
                self.assertRaisesRegex(j.Error, "CREATE_ACK_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])
        self.assertEqual(self.ledger.data["capture_errors"], {"app": "RESOURCE_BINDING"})
        self.assertEqual(self.ledger.data["resources"]["app"]["state"], "UNKNOWN")
        self.assertTrue(all(item["state"] == "OWNED" for kind, item in
                            self.ledger.data["resources"].items() if kind != "app"))

    def test_multiple_matching_deployments_are_ambiguous(self):
        deployment, operations = self.deployment()
        with patch.object(j.common, "inventory", return_value=[deployment, deepcopy(deployment)]), \
                self.assertRaisesRegex(j.Error, "DEPLOYMENT_UNKNOWN"):
            j.capture_deployments(self.ledger, self.arm, [])

    def test_unknown_job_cascade_preserves_data(self):
        self.own_app("job")
        def remove(*args):
            self.ledger.data["resources"]["job"]["state"] = "ABSENT"
        with patch.object(j, "remove_resource", side_effect=remove), patch.object(
                j, "verify_cascades", side_effect=j.Error("EXECUTION_ABSENCE_UNPROVEN")), patch.object(
                j.common, "inventory", return_value=[]), patch.object(j, "data_inventory") as inventory, \
                self.assertRaisesRegex(j.Error, "CLEANUP_RESIDUAL"):
            j.cleanup(self.ledger, self.arm)
        inventory.assert_not_called()

    def test_arm_identity_case_and_azure_time_shape(self):
        body = self.own_app()
        expected = j.binding("app", body, self.ledger)
        body["id"] = body["id"].lower()
        body["identity"]["userAssignedIdentities"] = {self.a["app_identity_id"].lower(): {}}
        self.assertEqual(j.binding("app", body, self.ledger), expected)

    def test_old_creation_time_rejected(self):
        body = self.own_app()
        body["systemData"]["createdAt"] = "2025-01-01T00:00:00Z"
        with self.assertRaisesRegex(j.Error, "CREATION_TIME"):
            j.binding("app", body, self.ledger)

    def test_foreign_identity_rejected(self):
        body = self.own_app()
        body["identity"]["userAssignedIdentities"] = {self.a["worker_identity_id"]: {}}
        with self.assertRaisesRegex(j.Error, "RESOURCE_BINDING"):
            j.binding("app", body, self.ledger)

    def test_exact_delete_two_absence_reads(self):
        self.own_app()
        j.remove_resource(self.ledger, self.arm, "app", sleep=lambda _: None)
        self.assertEqual(self.ledger.data["resources"]["app"]["state"], "ABSENT")
        self.assertEqual(len(self.arm.writes), 1)
        self.assertEqual([m for m, _ in self.arm.reads][-2:], ["GET", "GET"])

    def test_delete_auth_failure_is_not_absence(self):
        self.own_app()
        def forbidden(*args, **kwargs):
            return 403, {"error": {"code": "AuthorizationFailed"}}, None
        with self.assertRaisesRegex(j.Error, "OWNERSHIP_CHANGED"):
            j.remove_resource(self.ledger, forbidden, "app")

    def test_expiry_during_delete_token_zero_delete(self):
        self.own_app()
        self.arm.before_token = lambda: setattr(self.clock, "return_value", NOW + timedelta(hours=4))
        with self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
            j.remove_resource(self.ledger, self.arm, "app")
        self.assertFalse(self.arm.writes)

    def test_binding_change_during_delete_token_zero_delete(self):
        body = self.own_app()
        self.arm.before_token = lambda: body["identity"].update(userAssignedIdentities={})
        with self.assertRaisesRegex(j.Error, "RESOURCE_BINDING"):
            j.remove_resource(self.ledger, self.arm, "app")
        self.assertFalse(self.arm.writes)

    def test_lost_delete_ack_never_retries(self):
        self.own_app()
        self.arm.lost_ack = True
        with self.assertRaisesRegex(j.Error, "NETWORK"):
            j.remove_resource(self.ledger, self.arm, "app")
        with self.assertRaisesRegex(j.Error, "DELETE_ALREADY_ATTEMPTED"):
            j.remove_resource(self.ledger, self.arm, "app")
        self.assertEqual(len(self.arm.writes), 1)

    def test_unknown_owner_never_deleted(self):
        self.own_app()
        self.ledger.data["resources"]["app"]["state"] = "UNKNOWN"
        with self.assertRaisesRegex(j.Error, "OWNERSHIP_UNKNOWN"):
            j.remove_resource(self.ledger, self.arm, "app")
        self.assertFalse(self.arm.writes)

    def test_inherited_lock_blocks_all_create(self):
        real = self.arm
        def locked(method, rid, api, **kwargs):
            if rid.endswith(j.common.LOCK_PROVIDER):
                return 200, {"value": [{
                    "id": GROUP + j.common.LOCK_PROVIDER + "/protect",
                    "type": "Microsoft.Authorization/locks", "properties": {"level": "CanNotDelete"},
                }]}, None
            return real(method, rid, api, **kwargs)
        with self.assertRaisesRegex(j.Error, "CLEANUP_LOCKED"):
            j.prepare_resources(self.ledger, locked)
        self.assertFalse(self.arm.writes)

    def test_lock_read_denied_fails_closed(self):
        with self.assertRaisesRegex(j.Error, "INVENTORY"):
            j.prepare_resources(self.ledger, lambda *args: (403, {}, None))
        self.assertFalse(self.arm.writes)

    def test_unknown_producer_preserves_data(self):
        self.ledger.data["resources"]["app"]["state"] = "UNKNOWN"
        self.ledger.data["resources"]["output"]["state"] = "UNKNOWN"
        with self.assertRaisesRegex(j.Error, "CLEANUP_RESIDUAL"):
            j.cleanup(self.ledger, self.arm)
        self.assertIn("data:PRODUCER_ABSENCE_UNPROVEN", self.ledger.data["cleanup_errors"])
        self.assertFalse(self.arm.writes)

    def test_finalizer_reserves_full_budget(self):
        self.a["native"]["expires_at"] = "2026-09-18T01:10:00Z"
        self.ledger.a = deepcopy(self.a)
        with self.assertRaisesRegex(j.Error, "APPROVAL_LIFETIME"):
            j.cleanup(self.ledger, self.arm)
        self.assertFalse(self.arm.writes)

    def test_scaffold_freezes_canonical_files_and_ci_only_root(self):
        self.ledger.data["standing"] = {
            "environment_id": {"location": "test-region", "properties": {"defaultDomain": "example.test"}},
            "app_identity_id": {"properties": {"clientId": CLIENT}},
            "worker_identity_id": {"properties": {"clientId": AUTH, "principalId": CALLER}},
        }
        paths = [p.relative_to(ROOT).as_posix() for p in (
            ROOT / f"skills/{j.SKILL}/templates").rglob("*") if p.is_file()]
        paths.append("skills/azd-patterns/references/bicep/aca-job.bicep")
        paths.append("skills/azd-patterns/references/bicep/jobs-run-data.bicep")
        with patch.object(j.hosted, "command", return_value="\n".join(paths).encode()), patch.object(
                j, "git_file", side_effect=lambda _, p: (ROOT / p).read_bytes()):
            project = j.scaffold(self.ledger)
        config = yaml.safe_load((project / "azure.yaml").read_text())
        self.assertEqual(config["infra"]["module"], "ci")
        self.assertEqual(self.ledger.data["parameters"]["cosmosDatabaseName"], "standing")
        canonical = (project / "infra/../../../azd-patterns/references/bicep/aca-job.bicep").resolve()
        self.assertEqual(canonical.read_bytes(), (ROOT / "skills/azd-patterns/references/bicep/aca-job.bicep").read_bytes())

    def test_workflow_finalizer_and_ciphertext_only(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        finalizer = next(s for s in steps if s.get("name") == "Finalize exact Jobs run resources")
        self.assertIn("always()", finalizer["if"])
        self.assertIn('git show "$GITHUB_SHA:scripts/$SCRIPT"', finalizer["run"])
        self.assertTrue(finalizer["continue-on-error"])
        upload = next(s for s in steps if s.get("name") == "Preserve encrypted Jobs lifecycle inventory")
        self.assertTrue(upload["with"]["path"].endswith("/inventory.age"))
        self.assertEqual(upload["with"]["retention-days"], 1)

    def test_default_main_remains_subscription_scope(self):
        text = (ROOT / f"skills/{j.SKILL}/templates/infra/main.bicep").read_text()
        self.assertIn("targetScope = 'subscription'", text)
        ci = (ROOT / f"skills/{j.SKILL}/templates/infra/ci.bicep").read_text()
        for forbidden in ("roleAssignments", "roleDefinitions", "resourceGroups@", "existingAccount"):
            self.assertNotIn(forbidden, ci)
        self.assertIn("targetScope = 'resourceGroup'", ci)

    def test_standing_bootstrap_is_not_ci_entrypoint(self):
        text = (ROOT / "scripts/jobs-ci-lifecycle.py").read_text()
        self.assertNotIn('"module": "standing"', text)
        standing = (ROOT / f"skills/{j.SKILL}/templates/infra/standing.bicep").read_text()
        self.assertIn("assignableScopes: [resourceGroup().id]", standing)
        self.assertEqual(standing.count("tags: tags"), 4)
        self.assertNotIn("'Owner'", standing)
        self.assertNotIn("Contributor", standing)

    def test_hosted_project_uses_shared_exact_azd_state_validator(self):
        self.ledger.data.update(state="DEPLOYED", project=str(self.temp), parameters={
            "cosmosContainerName": "control", "outputStorageContainerName": "output",
            "appName": "ci-jobs-app", "environmentDomain": "example.invalid",
        })
        with patch.object(j, "git_file", side_effect=lambda _, p: (ROOT / p).read_bytes()):
            project, verify, variables = j.hosted_project(self.ledger)
        name = j.environment(self.ledger)["HOSTED_NAME"]
        directory = project / ".azure" / name
        values = dict(line.split("=", 1) for line in (directory / ".env").read_text().splitlines())
        self.commands.return_value = json.dumps(values).encode()
        expected = verify(self.env, self.a["native"], name, project)
        (project / ".azure/.gitignore").write_bytes(b"# .azure is not intended to be committed\n*")
        (directory / ".env.lock").touch()
        (directory / "config.json").write_text("{}")
        self.assertEqual(verify(self.env, self.a["native"], name, project), expected)
        self.assertIn("MCP_SERVER_URL", variables)
        for extra in ({"hooks": {}}, {"services": {}}, {"infra": {"provider": "foreign"}}):
            (directory / "config.json").write_text(json.dumps(extra))
            self.commands.reset_mock()
            with self.assertRaisesRegex(j.Error, "SOURCE"):
                verify(self.env, self.a["native"], name, project)
            self.commands.assert_not_called()
        (directory / "config.json").write_text("{}")
        image = "testregistry.azurecr.io/owned:tag"
        key = "SERVICE_" + name.upper().replace("-", "_") + "_IMAGE_NAME"
        with (directory / ".env").open("a") as stream:
            stream.write(f"{key}={image}\n")
        self.commands.return_value = json.dumps(values | {key: image}).encode()
        self.assertEqual(verify(self.env, self.a["native"], name, project, image), expected)
        (project / "container.py").write_text("not the frozen reference")
        with self.assertRaisesRegex(j.Error, "SOURCE"):
            verify(self.env, self.a["native"], name, project, image)

    def test_jobs_shared_native_client_reaches_sdk_without_tenant_subscription_conflict(self):
        import azure.identity._credentials.azure_cli as cli
        account = {"id": SUB, "tenantId": TENANT, "user": {"type": "servicePrincipal", "name": CLIENT}}
        def token(args, timeout):
            self.assertNotIn("--tenant", args)
            self.assertEqual(args[args.index("--subscription") + 1], SUB)
            self.assertEqual(timeout, 20)
            return '{"accessToken":"offline-synthetic","expires_on":2000000000}'
        with patch.object(j.hosted.common.subprocess, "run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(account).encode())), \
             patch.object(cli, "_run_command", side_effect=token) as cli_call, \
             patch("azure.ai.projects.AIProjectClient"):
            with j.hosted.Native(self.env, self.a["native"]).client():
                pass
            cli_call.assert_called_once()

    def test_read_helpers_are_not_live_test_evidence(self):
        self.assertFalse(j.absent(403, {"error": {"code": "ResourceNotFound"}}))
        self.assertFalse(j.absent(404, {"error": {"code": "AuthorizationFailed"}}))
        self.assertFalse(j.absent(404, {}))
        self.assertTrue(j.absent(404, {"error": {"code": "JobNotFound"}}))


class JobsProbeTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "jobs_probes", ROOT / "skills/foundry-mcp-aca-jobs/test-fixture/probes.py")
        self.probes = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.probes)
        self.response = SimpleNamespace(output=[
            SimpleNamespace(type="mcp_call", name="start_aca_job", error=None,
                arguments=json.dumps({"jobType": "short-job", "idempotencyKey": "key",
                                      "inputRef": "https://example.test/input", "callbackAlias": "ops"}),
                output=json.dumps({"taskId": "actual-task", "status": "Running"})),
            SimpleNamespace(type="mcp_call", name="get_aca_job_status", error=None,
                arguments='{"taskId":"actual-task"}',
                output=json.dumps({"taskId": "actual-task", "errorCode": None})),
        ])

    def check(self):
        return self.probes.agent_calls(self.response, "https://example.test/input", "key")

    def test_actual_calls_are_correlated_without_echo_marker(self):
        self.assertEqual(self.check(), "actual-task")

    def test_assistant_text_is_not_mcp_evidence(self):
        self.response.output[0].type = "message"
        with self.assertRaises(AssertionError):
            self.check()

    def test_wrong_input_fails(self):
        self.response.output[0].arguments = "{}"
        with self.assertRaises(AssertionError):
            self.check()

    def test_wrong_task_fails(self):
        self.response.output[1].output = '{"taskId":"foreign","errorCode":null}'
        with self.assertRaises(AssertionError):
            self.check()

    def test_tool_errors_fail(self):
        self.response.output[0].error = "permission denied"
        with self.assertRaises(AssertionError):
            self.check()

    def test_extra_model_tool_call_fails(self):
        self.response.output.append(deepcopy(self.response.output[0]))
        with self.assertRaises(AssertionError):
            self.check()

    def test_native_mcp_result_envelope(self):
        for item in self.response.output:
            item.output = json.dumps({"content": [{"type": "text", "text": item.output}]})
        self.assertEqual(self.check(), "actual-task")

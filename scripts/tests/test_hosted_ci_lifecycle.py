"""Offline reconciliation/custody tests; no Azure or native azd process."""

from copy import deepcopy
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import io
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_lifecycle", ROOT / "scripts/hosted-ci-lifecycle.py")
h = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h)
NOW = datetime(2026, 9, 17, 10, tzinfo=timezone.utc)
SUB = "11111111-1111-1111-1111-111111111111"
TENANT = "22222222-2222-2222-2222-222222222222"
CLIENT = "33333333-3333-3333-3333-333333333333"
PRINCIPAL = "44444444-4444-4444-4444-444444444444"
INSTANCE_CLIENT = "55555555-5555-5555-5555-555555555555"
PROJECT = f"/subscriptions/{SUB}/resourceGroups/ci/providers/Microsoft.CognitiveServices/accounts/ci/projects/test"
NAME = "ci-smoke-ha-" + "a" * 32


class Model(dict):
    def as_dict(self):
        return dict(self)

    def __getattr__(self, key):
        return self[key]


class FakeNative:
    def __init__(self, ledger):
        self.ledger = ledger
        self.present = False
        self.deleted = set()
        self.calls = []
        self.sessions = []
        self.extra_versions = False
        self.changed = False
        self.delete_error = False
        self.cascade_parent = False

    def version(self):
        definition = deepcopy(self.ledger.data["definition"])
        if self.changed:
            definition["extra_field"] = True
        return SimpleNamespace(
            name=self.ledger.data["agent"], version="1", id="version-id", created_at=NOW,
            definition=Model(definition),
            instance_identity=Model(principal_id=PRINCIPAL, client_id=INSTANCE_CLIENT),
            metadata={"enableVnextExperience": "true"},
        )

    def absent(self, method, **kwargs):
        self.calls.append((method, kwargs))
        return not self.present or (method, tuple(sorted(kwargs.items()))) in self.deleted

    def call(self, method, *, before_send=None, **kwargs):
        if before_send:
            before_send()
        self.calls.append((method, kwargs))
        if method == "update_details":
            return None
        if method == "get":
            return SimpleNamespace(id="agent-id", name=self.ledger.data["agent"],
                                   instance_identity=Model(principal_id=PRINCIPAL, client_id=INSTANCE_CLIENT),
                                   blueprint=None)
        if method == "get_version":
            return self.version()
        if method == "get_session":
            return SimpleNamespace(
                agent_session_id=kwargs["session_id"],
                version_indicator=Model(type="version_ref", agent_version="1"),
            )
        if method.startswith("delete"):
            if self.delete_error:
                raise h.Error("NATIVE_REQUEST")
            args = {key: value for key, value in kwargs.items() if key != "force"}
            self.deleted.add((method.replace("delete", "get", 1), tuple(sorted(args.items()))))
            if method == "delete_session":
                self.sessions = [s for s in self.sessions if s.agent_session_id != args["session_id"]]
            if method == "delete" or method == "delete_version" and self.cascade_parent:
                self.present = False
            return None
        raise AssertionError(method)

    def inventory(self, kind, name):
        self.calls.append(("list_" + kind, {"agent_name": name}))
        if self.cascade_parent and not self.present:
            raise h.Error("INVENTORY_UNKNOWN")
        if kind == "sessions":
            return self.sessions
        key = ("get_version", tuple(sorted({"agent_name": name, "agent_version": "1"}.items())))
        if not self.present or key in self.deleted:
            return []
        return [self.version()] * (2 if self.extra_versions else 1)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.env = {
            "RUNNER_TEMP": str(self.root), "HOSTED_CI_SKILL": "foundry-hosted-agents",
            "GITHUB_REPOSITORY": "example/catalog", "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1",
            "AZURE_SUBSCRIPTION_ID": SUB, "AZURE_TENANT_ID": TENANT, "AZURE_CLIENT_ID": CLIENT,
            "AZURE_AI_PROJECT_ID": PROJECT,
            "FOUNDRY_PROJECT_ENDPOINT": "https://ci.services.ai.azure.com/api/projects/test",
            "ACR_LOGIN_SERVER": "testregistry.azurecr.io", "GITHUB_WORKSPACE": str(ROOT),
        }
        self.a = {
            "schema_version": 1, "skill": self.env["HOSTED_CI_SKILL"],
            "repository": self.env["GITHUB_REPOSITORY"], "sha": self.env["GITHUB_SHA"],
            "run_id": "100", "run_attempt": "1", "tenant_id": TENANT, "client_id": CLIENT,
            "project_id": PROJECT, "project_endpoint": self.env["FOUNDRY_PROJECT_ENDPOINT"],
            "acr_server": self.env["ACR_LOGIN_SERVER"], "model": "gpt-5.4-mini",
            "expires_at": "2026-09-17T12:00:00Z", "retain_until": "2026-09-18T12:00:00Z",
            "age_recipient": "age1" + "q" * 58, "owner": "CI owner", "purpose": "one test",
            "delete_reconciled_native_objects": True, "retain_images_identities_and_stored_responses": True,
            "temporary_foundry_user_grants": False,
        }
        self.env["HOSTED_CI_LIFECYCLE_APPROVAL_JSON"] = json.dumps(self.a)
        self.clock = patch.object(h.common, "utc_now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.real_encrypt = h.common.encrypt
        self.encryption = patch.object(h.common, "encrypt")
        self.encrypt = self.encryption.start()
        self.addCleanup(self.encryption.stop)
        self.path = h.root(self.env)
        self.path.mkdir(mode=0o700)
        h.common.write(self.path / "approval.json", self.a)
        h.common.write(self.path / "receipt.json", {
            "context": {k: self.a[k] for k in ("skill", "sha", "run_id", "run_attempt")},
            "approval": deepcopy(self.a), "approval_sha256": h.fingerprint(self.a),
            "state": "PREPARED",
        })
        self.ledger = h.Ledger(self.path, self.a, self.env)
        self.native = FakeNative(self.ledger)
        real_record = h.record_native_absence
        absence = patch.object(h, "record_native_absence",
                               side_effect=lambda *args: real_record(*args, sleep=lambda _: None))
        absence.start()
        self.addCleanup(absence.stop)

    def owned(self):
        self.ledger.data.update(
            agent=NAME, image="testregistry.azurecr.io/owned@" + "sha256:" + "a" * 64,
            definition={"kind": "hosted", "container_configuration": {
                "image": "testregistry.azurecr.io/owned@" + "sha256:" + "a" * 64}},
            pre_get_404=True, deploy_intent=True, deploy_started_at="2026-09-17T10:00:00Z",
        )
        self.native.present = True
        h.reconcile(self.ledger, self.native)

    def test_exact_approval_and_negative_bindings(self):
        self.assertEqual(h.approval(self.env), self.a)
        for key, value in (
            ("schema_version", True), ("run_attempt", True), ("run_id", "0100"),
            ("sha", "b" * 40), ("temporary_foundry_user_grants", True),
            ("project_id", PROJECT.rsplit("/projects/", 1)[0]),
            ("delete_reconciled_native_objects", False), ("retain_images_identities_and_stored_responses", False),
            ("expires_at", "2026-09-17T12:00:00"), ("expires_at", "2026-09-17T12:00:00+01:00"),
            ("expires_at", "2026-09-17T09:59:59Z"), ("expires_at", "2026-09-19T12:00:00Z"),
            ("retain_until", "2026-09-17T11:00:00Z"), ("age_recipient", "invalid"),
        ):
            with self.subTest(key=key, value=value):
                a = dict(self.a, **{key: value})
                with self.assertRaises(h.Error):
                    h.approval(self.env, json.dumps(a))
        with self.assertRaises(h.Error):
            h.approval(self.env, json.dumps(self.a)[:-1] + ',"run_id":"100"}')

    def test_duplicate_process_and_receipt_context_are_rejected(self):
        with h.exclusive(self.path):
            with self.assertRaisesRegex(h.Error, "CONCURRENT_PROCESS"):
                with h.exclusive(self.path):
                    self.fail("second process admitted")
        self.ledger.data["context"]["run_attempt"] = "2"
        h.common.write(self.path / "receipt.json", self.ledger.data)
        with self.assertRaisesRegex(h.Error, "CONTEXT"):
            h.Ledger(self.path, self.a, self.env)

    def test_complete_definition_and_unique_inventory_required(self):
        self.owned()
        self.assertEqual(self.ledger.data["state"], "RECONCILED_OWNERSHIP")
        self.assertNotIn("create_ack", self.ledger.data)
        self.native.changed = True
        with self.assertRaisesRegex(h.Error, "DEFINITION_CHANGED"):
            h.reconcile(self.ledger, self.native)
        self.native.changed = False
        self.native.extra_versions = True
        with self.assertRaisesRegex(h.Error, "OWNERSHIP_UNKNOWN"):
            h.reconcile(self.ledger, self.native)
        self.native.extra_versions = False
        self.ledger.data["binding"]["identity"]["principal_id"] = CLIENT
        with self.assertRaisesRegex(h.Error, "OWNERSHIP_CHANGED"):
            h.reconcile(self.ledger, self.native)

    def test_unknown_preabsence_or_intent_never_becomes_owned(self):
        self.owned()
        for key in ("pre_get_404", "deploy_intent"):
            self.ledger.data[key] = False
            with self.assertRaisesRegex(h.Error, "OWNERSHIP_UNKNOWN"):
                h.reconcile(self.ledger, self.native)
            self.ledger.data[key] = True

    def test_empty_legacy_protocol_default_preserves_complete_frozen_binding(self):
        from azure.ai.projects.models import HostedAgentDefinition
        self.owned()
        self.ledger.data["definition"] = HostedAgentDefinition(
            kind="hosted", cpu="1", memory="2Gi",
            container_configuration={"image": self.ledger.data["image"]},
            protocol_versions=[{"protocol": "responses", "version": "2.0.0"}],
        ).as_dict()
        version = self.native.version()
        expected = h.version_binding(version, self.ledger)
        frozen = deepcopy(self.ledger.data)
        actual = version.definition.as_dict() | {"container_protocol_versions": []}
        version.definition = HostedAgentDefinition(actual)
        self.assertEqual(h.version_binding(version, self.ledger), expected)
        self.assertEqual(version.definition.as_dict(), actual)
        self.assertEqual(self.ledger.data, frozen)

    def test_protocol_default_does_not_hide_protocol_or_other_definition_drift(self):
        self.owned()
        self.ledger.data["definition"]["protocol_versions"] = [{"protocol": "responses", "version": "2.0.0"}]
        for extra in (
            {"container_protocol_versions": None}, {"container_protocol_versions": {}},
            {"container_protocol_versions": [{"protocol": "invocations", "version": "2.0.0"}]},
            {"container_protocol_versions": [], "protocol_versions": []},
            {"container_protocol_versions": [], "protocol_versions": [{"protocol": "responses", "version": "1.0.0"}]},
            {"container_protocol_versions": [], "cpu": "2"},
            {"container_protocol_versions": [], "unknown_default": []},
        ):
            with self.subTest(extra=extra):
                version = self.native.version()
                version.definition.update(extra)
                with self.assertRaisesRegex(h.Error, "DEFINITION_CHANGED"):
                    h.version_binding(version, self.ledger)
        version = self.native.version()
        del version.definition["protocol_versions"]
        version.definition["container_protocol_versions"] = []
        with self.assertRaisesRegex(h.Error, "DEFINITION_CHANGED"):
            h.version_binding(version, self.ledger)

    def test_failed_definition_reconciliation_never_enables_cleanup(self):
        self.owned()
        self.ledger.data.pop("binding")
        self.ledger.data.pop("agent_binding")
        self.ledger.data["state"] = "UNKNOWN"
        self.native.changed = True
        with self.assertRaisesRegex(h.Error, "DEFINITION_CHANGED"):
            h.reconcile(self.ledger, self.native)
        self.native.changed = False
        with self.assertRaisesRegex(h.Error, "OWNERSHIP_UNKNOWN"):
            h.cleanup_native(self.ledger, self.native)
        self.assertNotIn("binding", self.ledger.data)
        self.assertFalse(any(method.startswith("delete") for method, _ in self.native.calls))

    def test_invoke_budget_persists_across_processes(self):
        self.owned()
        h.configure_routing(self.ledger, self.native)
        h.before_invoke(self.ledger, self.native)
        another = h.Ledger(self.path, self.a, self.env)
        with self.assertRaisesRegex(h.Error, "INVOKE_BUDGET"):
            h.before_invoke(another, self.native)

    def test_routing_uses_bound_version_once_without_consuming_invoke_budget(self):
        self.owned()
        with self.assertRaisesRegex(h.Error, "ROUTING_UNKNOWN"):
            h.before_invoke(self.ledger, self.native)
        h.configure_routing(self.ledger, self.native)
        routing = [(method, args) for method, args in self.native.calls if method == "update_details"]
        self.assertEqual(len(routing), 1)
        self.assertEqual(routing[0][1]["agent_name"], NAME)
        config = routing[0][1]["agent_endpoint"].as_dict()
        rule = config["version_selector"]["version_selection_rules"][0]
        self.assertEqual(rule["agent_version"], "1")
        self.assertEqual(rule["traffic_percentage"], 100)
        self.assertIn("responses", config["protocol_configuration"])
        self.assertNotIn("invoke_intents", self.ledger.data)
        self.assertTrue(self.ledger.data["routing_ack"])
        another = h.Ledger(self.path, self.a, self.env)
        with self.assertRaisesRegex(h.Error, "ROUTING_ALREADY_ATTEMPTED"):
            h.configure_routing(another, self.native)
        h.before_invoke(another, self.native)
        self.assertEqual(another.data["invoke_intents"], 1)

    def test_routing_lost_ack_blocks_new_process_and_invocation(self):
        self.owned()
        real_call = self.native.call
        def call(method, **kwargs):
            result = real_call(method, **kwargs)
            if method == "update_details":
                raise h.Error("NATIVE_REQUEST")
            return result
        with patch.object(self.native, "call", side_effect=call), self.assertRaisesRegex(h.Error, "NATIVE_REQUEST"):
            h.configure_routing(self.ledger, self.native)
        another = h.Ledger(self.path, self.a, self.env)
        with self.assertRaisesRegex(h.Error, "ROUTING_ALREADY_ATTEMPTED"):
            h.configure_routing(another, self.native)
        with self.assertRaisesRegex(h.Error, "ROUTING_UNKNOWN"):
            h.before_invoke(another, self.native)
        self.assertEqual(len([c for c in self.native.calls if c[0] == "update_details"]), 1)
        self.assertNotIn("invoke_intents", another.data)

    def test_routing_expiry_after_poll_or_encryption_sends_no_write_or_invoke(self):
        self.owned()
        for stage in ("poll", "encryption"):
            with self.subTest(stage=stage):
                h.common.utc_now.return_value = NOW
                self.ledger.data.pop("routing_intent", None)
                if stage == "poll":
                    h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
                def encrypt(*_):
                    h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
                with patch.object(h.common, "encrypt", side_effect=encrypt), self.assertRaisesRegex(
                        h.Error, "APPROVAL_LIFETIME"):
                    h.configure_routing(self.ledger, self.native)
                with self.assertRaisesRegex(h.Error, "ROUTING_UNKNOWN"):
                    h.before_invoke(self.ledger, self.native)
                self.assertFalse(any(c[0] == "update_details" for c in self.native.calls))
                self.assertNotIn("invoke_intents", self.ledger.data)

    def test_routing_rechecks_after_token_and_binding_reads_before_sdk_send(self):
        self.owned()
        original_binding = deepcopy(self.ledger.data["binding"])
        for stage in ("token_expiry", "read_expiry", "foreign_agent", "version", "definition", "identity", "extra_version"):
            with self.subTest(stage=stage):
                h.common.utc_now.return_value = NOW
                self.ledger.data.pop("routing_intent", None)
                self.ledger.data["binding"] = deepcopy(original_binding)
                version = self.native.version()
                agent = self.native.call("get", agent_name=NAME)
                events = []
                def token(*_):
                    events.append("token")
                    if stage == "token_expiry":
                        h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
                    elif stage == "foreign_agent":
                        version.name = "ci-smoke-ha-" + "b" * 32
                    elif stage == "version":
                        version.version = "2"
                    elif stage == "definition":
                        version.definition["extra"] = "foreign"
                    elif stage == "identity":
                        agent.instance_identity["principal_id"] = CLIENT
                    return SimpleNamespace(token="never-public", expires_on=2000000000)
                def get_version(**_):
                    events.append("binding-read")
                    if stage == "read_expiry":
                        h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
                    return version
                agents = MagicMock()
                agents.get_version.side_effect = get_version
                agents.get.return_value = agent
                versions = [version] * (2 if stage == "extra_version" else 1)
                agents.list_versions.side_effect = lambda **_: SimpleNamespace(by_page=lambda: iter([versions]))
                credential = MagicMock()
                credential.__enter__.return_value.get_token.side_effect = token
                with patch.object(h.common, "Arm"), \
                     patch("azure.identity.AzureCliCredential", return_value=credential), \
                     patch("azure.ai.projects.AIProjectClient") as client:
                    client.return_value.__enter__.return_value.agents = agents
                    with self.assertRaises(h.Error):
                        h.configure_routing(self.ledger, h.Native(self.env, self.a))
                    agents.update_details.assert_not_called()
                self.assertEqual(events[0], "token")
                with self.assertRaisesRegex(h.Error, "ROUTING_UNKNOWN"):
                    h.before_invoke(self.ledger, self.native)
                self.assertNotIn("invoke_intents", self.ledger.data)

    def test_native_routing_without_guard_or_foreign_frozen_version_is_rejected(self):
        with patch.object(h.Native, "client") as client, self.assertRaisesRegex(h.Error, "ROUTING_GUARD"):
            h.Native(self.env, self.a).call("update_details", agent_name=NAME)
        client.assert_not_called()
        self.owned()
        self.ledger.data["binding"]["version"] = "2"
        with self.assertRaisesRegex(h.Error, "VERSION"):
            h.configure_routing(self.ledger, self.native)
        self.assertFalse(any(c[0] == "update_details" for c in self.native.calls))
        self.assertNotIn("invoke_intents", self.ledger.data)

    def test_receipt_custody_survives_real_encryption_without_plaintext_or_secret(self):
        age = shutil.which("age")
        keygen = shutil.which("age-keygen")
        self.assertIsNotNone(age, "age is required, as installed by the unit-test workflow")
        self.assertIsNotNone(keygen, "age-keygen is required, as installed by the unit-test workflow")
        key = self.root / "owner-key"
        subprocess.run([keygen, "-o", str(key)], check=True, capture_output=True)
        recipient = subprocess.check_output([keygen, "-y", str(key)], text=True).strip()
        binary = Path(age).resolve()
        approved = dict(self.a, age_recipient=recipient)
        runner = self.root / "fresh-runner"
        runner.mkdir()
        env = {**self.env, "RUNNER_TEMP": str(runner),
               "HOSTED_CI_LIFECYCLE_APPROVAL_JSON": json.dumps(approved),
               "AGENTOPS_CI_AGE_BIN": str(binary),
               "AGENTOPS_CI_AGE_SHA256": hashlib.sha256(binary.read_bytes()).hexdigest()}
        stdout = io.StringIO()
        with patch.object(h.common, "encrypt", side_effect=self.real_encrypt), patch("sys.stdout", stdout):
            self.assertEqual(h.main(["init"], env), 0)
        path = h.root(env)
        (path / "approval.json").unlink()
        (path / "receipt.json").unlink()
        del env["HOSTED_CI_LIFECYCLE_APPROVAL_JSON"]
        raw = subprocess.check_output([age, "--decrypt", "-i", str(key), str(path / "inventory.age")])
        receipt = json.loads(raw)
        self.assertEqual(receipt["approval"], approved)
        self.assertEqual(receipt["approval_sha256"], h.fingerprint(receipt["approval"]))
        self.assertEqual(receipt["context"], {k: approved[k] for k in ("skill", "sha", "run_id", "run_attempt")})
        for field in ("owner", "purpose", "tenant_id", "project_id", "project_endpoint", "expires_at", "retain_until"):
            self.assertNotIn(approved[field], stdout.getvalue())
            self.assertNotIn(approved[field].encode(), (path / "inventory.age").read_bytes())
        self.assertEqual(receipt["state"], "PREPARED")

    def test_incomplete_or_changed_receipt_custody_blocks_every_entrypoint(self):
        original = deepcopy(self.ledger.data)
        for field in ("approval", "approval_sha256", "owner", "purpose", "tenant_id", "project_id",
                      "project_endpoint", "expires_at", "retain_until"):
            bad = deepcopy(original)
            if field in ("approval", "approval_sha256"):
                bad.pop(field)
            else:
                bad["approval"].pop(field)
                bad["approval_sha256"] = h.fingerprint(bad["approval"])
            h.common.write(self.path / "receipt.json", bad)
            for args in (["deploy", str(self.root), NAME], ["configure-routing"], ["before-invoke"], ["grants"]):
                with self.subTest(field=field, args=args), patch.object(h, "command") as command, \
                     patch.object(h, "Native") as native, patch.object(h.common, "Arm") as arm, \
                     patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    self.assertEqual(h.main(args, self.env), 1)
                    self.assertEqual(stdout.getvalue(), "HOSTED_CI_LIFECYCLE=FAIL CUSTODY\n")
                    command.assert_not_called()
                    native.assert_not_called()
                    arm.assert_not_called()
        h.common.write(self.path / "receipt.json", original)

    def test_encryption_failure_blocks_producer_and_frozen_approval_changes(self):
        with patch.object(h.common, "encrypt", side_effect=h.Error("CUSTODY")), \
             patch.object(h, "command") as command, self.assertRaisesRegex(h.Error, "CUSTODY"):
            h.deploy(self.ledger, self.native, None, self.root, NAME)
        command.assert_not_called()
        self.a["owner"] = "replacement owner"
        self.assertEqual(self.ledger.a["owner"], "CI owner")
        with self.assertRaisesRegex(h.Error, "CUSTODY"):
            h.Ledger(self.path, self.a, self.env)

    def test_unknown_and_unaccounted_sessions_prevent_native_deletes(self):
        with self.assertRaisesRegex(h.Error, "OWNERSHIP_UNKNOWN"):
            h.cleanup_native(self.ledger, self.native)
        self.owned()
        self.native.sessions = [SimpleNamespace(agent_session_id="session")]
        with self.assertRaisesRegex(h.Error, "SESSION_UNKNOWN"):
            h.cleanup_native(self.ledger, self.native)
        self.assertFalse(any(method.startswith("delete") for method, _ in self.native.calls))

    def test_native_cleanup_rechecks_bindings_and_never_forces(self):
        self.owned()
        self.ledger.data["invoke_intents"] = 1
        self.native.sessions = [SimpleNamespace(agent_session_id="session")]
        real_remove = h.remove_once
        with patch.object(h, "remove_once", side_effect=lambda *a, **kw: real_remove(*a, **kw, sleep=lambda _: None)):
            h.cleanup_native(self.ledger, self.native)
        deletes = [(method, args) for method, args in self.native.calls if method.startswith("delete")]
        self.assertEqual([method for method, _ in deletes], ["delete_session", "delete_version", "delete"])
        for method, args in deletes:
            if method != "delete_session":
                self.assertIs(args["force"], False)
        self.assertTrue(self.ledger.data["native_absent"])
        h.cleanup_native(h.Ledger(self.path, self.a, self.env), self.native)
        self.assertEqual(len([x for x in self.native.calls if x[0].startswith("delete")]), 3)

    def cascade_receipt(self):
        self.owned()
        self.native.cascade_parent = True
        h.remove_once(self.ledger, self.native, "version",
                      {"agent_name": NAME, "agent_version": "1"}, sleep=lambda _: None)
        self.native.calls.clear()

    def test_final_version_cascade_proves_parent_absence_without_inventory_or_delete(self):
        self.owned()
        self.native.cascade_parent = True
        real_remove = h.remove_once
        with patch.object(h, "remove_once", side_effect=lambda *args: real_remove(*args, sleep=lambda _: None)):
            h.cleanup_native(self.ledger, self.native)
        deletes = [(method, args) for method, args in self.native.calls if method.startswith("delete")]
        self.assertEqual(deletes, [("delete_version", {
            "agent_name": NAME, "agent_version": "1", "force": False,
        })])
        after_delete = self.native.calls[self.native.calls.index(deletes[0]) + 1:]
        self.assertFalse(any(method.startswith("list_") for method, _ in after_delete))
        self.assertGreaterEqual(sum(method == "get" for method, _ in after_delete), 2)
        self.assertTrue(self.ledger.data["native_absent"])
        self.assertTrue(self.ledger.data["parent_cascade_observed"])
        self.assertEqual(self.ledger.data["state"], "NATIVE_ABSENT_IMAGES_IDENTITIES_RETAINED")
        self.assertEqual(len(self.ledger.data["delete_intents"]), 1)
        self.assertEqual(self.ledger.data["delete_intents"], self.ledger.data["absent"])
        self.native.calls.clear()
        h.cleanup_native(h.Ledger(self.path, self.a, self.env), self.native)
        self.assertEqual([method for method, _ in self.native.calls], ["get", "get_version", "get"])

    def test_cascade_resume_after_interruption_never_reissues_version_delete(self):
        self.owned()
        self.native.cascade_parent = True
        real_remove = h.remove_once
        real_record = h.record_native_absence
        def interrupt(*args):
            if not self.native.present:
                raise h.Error("INTERRUPTED")
            return real_record(*args)
        with patch.object(h, "remove_once", side_effect=lambda *args: real_remove(*args, sleep=lambda _: None)), \
             patch.object(h, "record_native_absence", side_effect=interrupt):
            with self.assertRaisesRegex(h.Error, "INTERRUPTED"):
                h.cleanup_native(self.ledger, self.native)
        resumed = h.Ledger(self.path, self.a, self.env)
        self.assertNotIn("native_absent", resumed.data)
        self.assertEqual(resumed.data["delete_intents"], resumed.data["absent"])
        self.native.calls.clear()
        h.cleanup_native(resumed, self.native)
        self.assertTrue(resumed.data["native_absent"])
        self.assertEqual([method for method, _ in self.native.calls], ["get", "get_version", "get"])

    def test_cascade_requires_exact_intent_absence_and_prior_reconciled_bindings(self):
        self.cascade_receipt()
        original = deepcopy(self.ledger.data)
        for marker in (False, True):
            for field, value in (
                ("binding", None), ("agent_binding", None), ("pre_get_404", False),
                ("deploy_intent", False), ("delete_intents", []), ("absent", []),
                ("delete_intents", ["version:foreign"]), ("absent", ["version:foreign"]),
                ("agent_binding", dict(original["agent_binding"], identity={"principal_id": CLIENT})),
            ):
                with self.subTest(native_absent=marker, field=field, value=value):
                    self.ledger.data = deepcopy(original)
                    self.ledger.data.update({field: value, "native_absent": marker})
                    with self.assertRaisesRegex(h.Error, "OWNERSHIP_UNKNOWN"):
                        h.cleanup_native(self.ledger, self.native)
        self.assertFalse(any(method.startswith(("delete", "list_")) for method, _ in self.native.calls))

    def test_cascade_parent_reappearance_or_read_errors_fail_closed_on_resume(self):
        self.cascade_receipt()
        original = deepcopy(self.ledger.data)
        real_absent = self.native.absent
        for completed in (False, True):
            for observations in (
                [True, False], [h.Error("NATIVE_REQUEST")],
                [True, h.Error("NATIVE_REQUEST")], [True, h.Error("ABSENCE_UNPROVEN")],
            ):
                with self.subTest(completed=completed, observations=observations):
                    self.ledger.data = deepcopy(original)
                    self.ledger.data["native_absent"] = completed
                    values = iter(observations)
                    def observe(method, **kwargs):
                        if method != "get":
                            return real_absent(method, **kwargs)
                        value = next(values)
                        if isinstance(value, h.Error):
                            raise value
                        return value
                    with patch.object(self.native, "absent", side_effect=observe), self.assertRaises(h.Error):
                        h.cleanup_native(self.ledger, self.native)
                    expected = original | {"native_absent": completed}
                    if observations[0] is True:
                        expected["parent_cascade_observed"] = True
                    self.assertEqual(self.ledger.data, expected)
        self.assertFalse(any(method.startswith(("delete", "list_")) for method, _ in self.native.calls))

    def test_interrupted_parent_absence_proof_cannot_delete_a_reappearing_parent(self):
        self.cascade_receipt()
        real_absent = self.native.absent
        reads = iter([True, h.Error("NATIVE_REQUEST")])
        def observe(method, **kwargs):
            if method != "get":
                return real_absent(method, **kwargs)
            value = next(reads)
            if isinstance(value, h.Error):
                raise value
            return value
        with patch.object(self.native, "absent", side_effect=observe), \
             self.assertRaisesRegex(h.Error, "NATIVE_REQUEST"):
            h.cleanup_native(self.ledger, self.native)
        resumed = h.Ledger(self.path, self.a, self.env)
        self.assertTrue(resumed.data["parent_cascade_observed"])
        self.assertNotIn("native_absent", resumed.data)
        self.native.present = True
        self.native.calls.clear()
        with self.assertRaisesRegex(h.Error, "OWNERSHIP_CHANGED"):
            h.cleanup_native(resumed, self.native)
        self.assertFalse(any(method.startswith(("delete", "list_")) for method, _ in self.native.calls))
        self.assertNotIn("native_absent", resumed.data)

    def test_cascade_requires_fresh_version_absence_even_after_completion(self):
        self.cascade_receipt()
        original = deepcopy(self.ledger.data)
        real_absent = self.native.absent
        for completed in (False, True):
            for result in (False, h.Error("NATIVE_REQUEST"), h.Error("ABSENCE_UNPROVEN")):
                with self.subTest(completed=completed, result=result):
                    self.ledger.data = deepcopy(original)
                    self.ledger.data["native_absent"] = completed
                    def observe(method, **kwargs):
                        if method != "get_version":
                            return real_absent(method, **kwargs)
                        if isinstance(result, h.Error):
                            raise result
                        return result
                    with patch.object(self.native, "absent", side_effect=observe), self.assertRaises(h.Error):
                        h.cleanup_native(self.ledger, self.native)
                    self.assertEqual(self.ledger.data, original | {
                        "native_absent": completed, "parent_cascade_observed": True,
                    })
        self.assertFalse(any(method.startswith(("delete", "list_")) for method, _ in self.native.calls))

    def test_cascade_appearing_between_resume_parent_and_version_reads_uses_same_proof(self):
        self.cascade_receipt()
        real_absent = self.native.absent
        def observe(method, **kwargs):
            if observe.first and method == "get":
                observe.first = False
                return False
            return real_absent(method, **kwargs)
        observe.first = True
        with patch.object(self.native, "absent", side_effect=observe):
            h.cleanup_native(h.Ledger(self.path, self.a, self.env), self.native)
        self.assertFalse(any(method.startswith(("delete", "list_")) for method, _ in self.native.calls))
        self.assertTrue(h.Ledger(self.path, self.a, self.env).data["native_absent"])

    def test_inventory_failure_is_not_reclassified_as_parent_cascade(self):
        self.owned()
        real_inventory = self.native.inventory
        def inventory(kind, name):
            if kind == "sessions":
                raise h.Error("INVENTORY_UNKNOWN")
            return real_inventory(kind, name)
        with patch.object(self.native, "inventory", side_effect=inventory), \
             self.assertRaisesRegex(h.Error, "INVENTORY_UNKNOWN"):
            h.cleanup_native(self.ledger, self.native)
        self.assertNotIn("native_absent", self.ledger.data)
        self.assertFalse(any(method.startswith("delete") for method, _ in self.native.calls))

    def test_failed_delete_is_not_reissued_by_another_process(self):
        self.owned()
        self.native.delete_error = True
        with self.assertRaises(h.Error):
            h.cleanup_native(self.ledger, self.native)
        self.native.delete_error = False
        with self.assertRaisesRegex(h.Error, "DELETE_ALREADY_ATTEMPTED"):
            h.cleanup_native(h.Ledger(self.path, self.a, self.env), self.native)
        self.assertEqual(len([x for x in self.native.calls if x[0].startswith("delete")]), 1)

    def test_expiry_before_native_delete_prevents_mutation(self):
        self.owned()
        with patch.object(h.common, "utc_now", return_value=datetime(2026, 9, 17, 11, 59, tzinfo=timezone.utc)):
            with self.assertRaisesRegex(h.Error, "APPROVAL_LIFETIME"):
                h.cleanup_native(self.ledger, self.native)
        self.assertFalse(any(method.startswith("delete") for method, _ in self.native.calls))

    def test_package_receipt_does_not_accept_foreign_or_ambiguous_artifacts(self):
        location = f"my-agent-project/{NAME}-{NAME}:tag"
        artifact = {"kind": "container", "locationKind": "local", "location": location,
                    "metadata": {"targetImage": location, "sourceImage": "", "imageHash": "sha256:" + "a" * 64}}
        data = {"services": {NAME: {"artifacts": [artifact]}}}
        self.assertEqual(h.package_receipt(json.dumps(data).encode(), NAME)["local_image"], location)
        for bad in (
            {"services": {"other": data["services"][NAME]}},
            {"services": {NAME: {"artifacts": [artifact, artifact]}}},
            {"services": {NAME: {"artifacts": [dict(artifact, locationKind="remote")]}}},
        ):
            with self.assertRaises(h.Error):
                h.package_receipt(json.dumps(bad).encode(), NAME)

    def test_deploy_journal_blocks_new_process_after_lost_ack(self):
        self.ledger.data["state"] = "UNKNOWN"
        self.ledger.save()
        with patch.object(h, "command") as run:
            with self.assertRaisesRegex(h.Error, "RETRY_BLOCKED"):
                h.deploy(h.Ledger(self.path, self.a, self.env), self.native, None, self.root, NAME)
            run.assert_not_called()

    def test_preexisting_name_or_lock_blocks_package_before_creation(self):
        for existing in (True, False):
            self.native.present = existing
            with self.subTest(existing=existing), patch.object(h, "source", return_value={}), \
                 patch.object(h.common, "require_cleanup_unlocked", side_effect=h.Error("CLEANUP_LOCKED")):
                def run(args, *_):
                    if args[1] == "version":
                        return b'{"azd":{"version":"1.34.1"}}'
                    if args[1] == "ext":
                        return b'[{"id":"azure.ai.agents","installedVersion":"1.0.0-beta.14"}]'
                    self.fail("unexpected mutation")
                with patch.object(h, "command", side_effect=run), self.assertRaises(h.Error):
                    h.deploy(self.ledger, self.native, None, self.root, NAME)
            self.assertNotIn("package_intent", self.ledger.data)

    def run_deploy(self, fail=None):
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "azure.yaml").write_text(yaml.safe_dump({"services": {NAME: {"name": NAME}}}))
        local = f"my-agent-project/{NAME}-{NAME}:tag"
        raw_manifest = json.dumps({"config": {"digest": "sha256:" + "b" * 64}}).encode()
        digest = "sha256:" + hashlib.sha256(raw_manifest).hexdigest()
        self.commands = []
        def run(args, *_):
            self.commands.append(args)
            if args[1] == fail:
                raise h.Error("LOST_ACK")
            if args[1] == "version":
                return b'{"azd":{"version":"1.34.1"}}'
            if args[1] == "ext":
                return b'[{"id":"azure.ai.agents","installedVersion":"1.0.0-beta.14"}]'
            if args[1] == "package":
                return json.dumps({"services": {NAME: {"artifacts": [{
                    "kind": "container", "locationKind": "local", "location": local,
                    "metadata": {"targetImage": local, "sourceImage": "", "imageHash": "sha256:" + "b" * 64}
                }]}}}).encode()
            if args[1] == "publish":
                return b""
            if args[1] == "acr":
                return b"[]" if args[2] == "repository" else json.dumps({"digest": digest}).encode()
            if args[1] == "buildx":
                return raw_manifest
            if args[1] == "deploy":
                self.native.present = True
                return b""
            raise AssertionError(args)
        with patch.object(h, "source", return_value={"canonical": "hash"}), \
             patch.object(h.common, "require_cleanup_unlocked"), patch.object(h, "command", side_effect=run):
            h.deploy(self.ledger, self.native, None, self.project, NAME)

    def test_native_package_publish_prebuilt_deploy_and_reconciliation(self):
        self.run_deploy()
        mutations = [args for args in self.commands if args[1] in ("package", "publish", "deploy")]
        self.assertEqual([args[1] for args in mutations], ["package", "publish", "deploy"])
        self.assertIn("--from-package", mutations[-1])
        self.assertIn("@sha256:", mutations[-1][-2])
        data = h.Ledger(self.path, self.a, self.env).data
        self.assertEqual(data["state"], "RECONCILED_OWNERSHIP")
        self.assertEqual(data["package"]["config_digest"], "sha256:" + "b" * 64)
        self.assertTrue(data["publish_ack"])
        self.assertEqual(data["stored_responses_disposition"], "RETAINED_OWNER_APPROVED")
        config = yaml.safe_load((self.project / "azure.yaml").read_text())
        self.assertEqual(config["services"][NAME]["docker"], {"remoteBuild": False, "imagePassthrough": True})
        self.assertGreater(self.encrypt.call_count, 5)

    def test_lost_publish_ack_preserves_fragment_and_blocks_replacement(self):
        with self.assertRaisesRegex(h.Error, "LOST_ACK"):
            self.run_deploy(fail="publish")
        other = h.Ledger(self.path, self.a, self.env)
        self.assertEqual(other.data["state"], "UNKNOWN")
        self.assertTrue(other.data["publish_intent"])
        self.assertIn("remote_tag", other.data)
        self.assertNotIn("deploy_intent", other.data)
        with self.assertRaisesRegex(h.Error, "RETRY_BLOCKED"):
            h.deploy(other, FakeNative(other), None, self.project, NAME)

    def test_expiry_during_encryption_blocks_package(self):
        def encrypt(*_):
            if self.ledger.data.get("package_intent"):
                h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
        with patch.object(h.common, "encrypt", side_effect=encrypt), self.assertRaisesRegex(h.Error, "APPROVAL_LIFETIME"):
            self.run_deploy()
        self.assertFalse(any(args[1] == "package" for args in self.commands))

    def test_source_rejects_hooks_extra_files_and_env_overrides(self):
        project = self.root / "source"
        project.mkdir()
        mapping = {"Dockerfile": "docker/Dockerfile", "container.py": "python/container.py",
                   "pyproject.toml": "python/pyproject.toml", "azure.yaml": "yaml/azure.yaml"}
        originals = {}
        for local, remote in mapping.items():
            raw = (ROOT / "skills/foundry-hosted-agents/references" / remote).read_bytes()
            originals[remote] = raw
            if local == "azure.yaml":
                raw = raw.replace(b"  my-agent:\n", f"  {NAME}:\n".encode(), 1).replace(
                    b"    name: my-agent\n", f"    name: {NAME}\n".encode(), 1)
            (project / local).write_bytes(raw)
        (project / "copilot-instructions.md").write_text("You are a customer-support triage assistant.\n")
        (project / ".azure").mkdir()
        (project / ".azure/config.json").write_text(json.dumps({"version": 1, "defaultEnvironment": NAME}))
        values = {"AZURE_ENV_NAME": NAME, "AZURE_SUBSCRIPTION_ID": SUB, "AZURE_AI_PROJECT_ID": PROJECT,
                  "FOUNDRY_PROJECT_ENDPOINT": self.a["project_endpoint"],
                  "AZURE_CONTAINER_REGISTRY_ENDPOINT": self.a["acr_server"],
                  "AZURE_AI_MODEL_DEPLOYMENT_NAME": self.a["model"]}
        (project / ".azure" / NAME).mkdir()
        (project / ".azure" / NAME / ".env").write_text("\n".join(f'{key}="{value}"' for key, value in values.items()))
        (project / ".azure/.gitignore").write_bytes(b"# .azure is not intended to be committed\n*")
        (project / ".azure" / NAME / "config.json").write_text("{}")
        (project / ".azure" / NAME / ".env.lock").touch()
        def run(args, *_):
            return (originals[args[-1].split("/references/")[1]] if args[0] == "git"
                    else json.dumps(values).encode())
        with patch.object(h, "command", side_effect=run):
            self.assertEqual(len(h.source(self.env, self.a, NAME, project)), 5)
            values["AZURE_RESOURCE_GROUP"] = "foreign"
            with self.assertRaisesRegex(h.Error, "AZD_ENV"):
                h.source(self.env, self.a, NAME, project)
            del values["AZURE_RESOURCE_GROUP"]
            with (project / "azure.yaml").open("a") as stream:
                stream.write("\nhooks:\n  predeploy: dangerous\n")
            with self.assertRaisesRegex(h.Error, "SOURCE"):
                h.source(self.env, self.a, NAME, project)

    def azd_state(self):
        project = self.root / "azd-state"
        name = NAME
        directory = project / ".azure" / name
        directory.mkdir(parents=True)
        (project / ".azure/config.json").write_text(json.dumps({"version": 1, "defaultEnvironment": name}))
        values = {"AZURE_ENV_NAME": name, "AZURE_SUBSCRIPTION_ID": SUB}
        (directory / ".env").write_text("\n".join(f'{k}="{v}"' for k, v in values.items()))
        return project, name, values

    def test_azd_generated_metadata_is_exact_and_optional_before_and_after_publish(self):
        project, name, values = self.azd_state()
        with patch.object(h, "command", return_value=json.dumps(values).encode()):
            h.azd_environment(self.env, project, name, values)
            (project / ".azure/.gitignore").write_bytes(b"# .azure is not intended to be committed\n*")
            (project / ".azure" / name / "config.json").write_text(" { }\n")
            (project / ".azure" / name / ".env.lock").touch()
            h.azd_environment(self.env, project, name, values)
        image = "testregistry.azurecr.io/exact:tag"
        key = "SERVICE_" + name.upper().replace("-", "_") + "_IMAGE_NAME"
        with (project / ".azure" / name / ".env").open("a") as stream:
            stream.write(f'\n{key}="{image}"\n')
        with patch.object(h, "command", return_value=json.dumps(values | {key: image}).encode()):
            h.azd_environment(self.env, project, name, values, image)
            with self.assertRaisesRegex(h.Error, "AZD_ENV"):
                h.azd_environment(self.env, project, name, values, "testregistry.azurecr.io/foreign:tag")

    def test_azd_rejects_overrides_extra_paths_and_nonregular_metadata_before_cli(self):
        project, name, values = self.azd_state()
        variants = (
            (".azure/.gitignore", b"*"), (f".azure/{name}/config.json", b'{"hooks": {}}'),
            (f".azure/{name}/config.json", b'{"services": {}}'),
            (f".azure/{name}/config.json", b'null'),
            (f".azure/{name}/.env.lock", b"not an empty lock"),
            (f".azure/{name}/.env.tmp-foreign", b""), (".azure/foreign", None),
        )
        for relative, content in variants:
            path = project / relative
            with self.subTest(relative=relative, content=content), patch.object(h, "command") as command:
                path.mkdir() if content is None else path.write_bytes(content)
                with self.assertRaises(h.Error):
                    h.azd_environment(self.env, project, name, values)
                command.assert_not_called()
                path.rmdir() if content is None else path.unlink()
        target = project / ".azure" / name / "config.json"
        other = self.root / "outside-config"
        other.write_text("{}")
        for kind in ("symlink", "hardlink", "fifo", "directory"):
            with self.subTest(kind=kind), patch.object(h, "command") as command:
                if kind == "symlink":
                    target.symlink_to(other)
                elif kind == "hardlink":
                    os.link(other, target)
                elif kind == "fifo":
                    os.mkfifo(target)
                else:
                    target.mkdir()
                with self.assertRaises(h.Error):
                    h.azd_environment(self.env, project, name, values)
                command.assert_not_called()
                target.rmdir() if kind == "directory" else target.unlink()
        original = project / ".azure"
        relocated = self.root / "outside-azure"
        original.rename(relocated)
        original.symlink_to(relocated, target_is_directory=True)
        with patch.object(h, "command") as command, self.assertRaisesRegex(h.Error, "SOURCE"):
            h.azd_environment(self.env, project, name, values)
        command.assert_not_called()

    def test_real_cli_credential_uses_verified_subscription_without_conflicting_tenant(self):
        import azure.identity._credentials.azure_cli as cli
        from azure.core.exceptions import ClientAuthenticationError
        from azure.identity import AzureCliCredential
        account = {"id": SUB, "tenantId": TENANT, "user": {"type": "servicePrincipal", "name": CLIENT}}
        def token(args, timeout):
            self.assertEqual(timeout, 20)
            if "--subscription" in args and "--tenant" in args:
                raise ClientAuthenticationError("Please specify only one of subscription and tenant, not both")
            self.assertEqual(args[args.index("--subscription") + 1], SUB)
            self.assertEqual(args[args.index("--resource") + 1], "https://ai.azure.com")
            return '{"accessToken":"offline-synthetic","expires_on":2000000000}'
        with patch.object(cli, "_run_command", side_effect=token) as run:
            with AzureCliCredential(tenant_id=TENANT, subscription=SUB, process_timeout=20) as broken:
                with self.assertRaises(ClientAuthenticationError):
                    broken.get_token("https://ai.azure.com/.default")
            run.reset_mock()
            with patch.object(h.common.subprocess, "run", return_value=SimpleNamespace(
                    returncode=0, stdout=json.dumps(account).encode())), \
                 patch("azure.ai.projects.AIProjectClient") as project:
                for skill in h.SKILLS:
                    with h.Native(self.env, self.a | {"skill": skill}).client():
                        pass
                self.assertEqual(run.call_count, 2)
                kwargs = project.call_args.kwargs
                self.assertEqual(kwargs["endpoint"], self.a["project_endpoint"])
                self.assertEqual(kwargs["retry_total"], 0)
                self.assertEqual(kwargs["redirect_max"], 0)
                self.assertEqual(kwargs["credential"].get_token("https://ai.azure.com/.default").token,
                                 "offline-synthetic")
                with self.assertRaisesRegex(h.Error, "CREDENTIAL_SCOPE"):
                    kwargs["credential"].get_token("https://other.invalid/.default")
            for bad in (
                account | {"id": CLIENT}, account | {"tenantId": SUB},
                account | {"user": {"type": "user", "name": CLIENT}},
                account | {"user": {"type": "servicePrincipal", "name": TENANT}},
            ):
                run.reset_mock()
                with patch.object(h.common.subprocess, "run", return_value=SimpleNamespace(
                        returncode=0, stdout=json.dumps(bad).encode())), \
                     patch("azure.ai.projects.AIProjectClient") as project:
                    with self.assertRaisesRegex(h.Error, "CREDENTIAL"):
                        with h.Native(self.env, self.a).client():
                            self.fail("unapproved CLI identity")
                    run.assert_not_called()
                    project.assert_not_called()

    def test_native_pages_require_terminal_page_with_bounded_total(self):
        native = h.Native(self.env, self.a)
        for pages, success in (([[1], [2], []], True), ([[1]] * 4, False), ([list(range(7))], False)):
            agents = SimpleNamespace(list_versions=lambda **_: SimpleNamespace(by_page=lambda: iter(pages)))
            with self.subTest(pages=pages), patch.object(native, "client", return_value=nullcontext(agents)):
                if success:
                    self.assertEqual(native.inventory("versions", NAME), [1, 2])
                else:
                    with self.assertRaisesRegex(h.Error, "INVENTORY_LIMIT"):
                        native.inventory("versions", NAME)

    def test_native_page_error_never_returns_partial_inventory(self):
        from azure.core.exceptions import HttpResponseError
        def pages():
            yield [1]
            raise HttpResponseError("private diagnostic")
        native = h.Native(self.env, self.a)
        agents = SimpleNamespace(list_versions=lambda **_: SimpleNamespace(by_page=pages))
        with patch.object(native, "client", return_value=nullcontext(agents)):
            with self.assertRaisesRegex(h.Error, "^INVENTORY_UNKNOWN$"):
                native.inventory("versions", NAME)

    def test_token_acquisition_expiry_prevents_native_delete(self):
        native = h.Native(self.env, self.a)
        credential = MagicMock()
        def token(*_):
            h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
            return SimpleNamespace(token="never-public", expires_on=100)
        credential.__enter__.return_value.get_token.side_effect = token
        with patch.object(h.common, "Arm"), patch("azure.identity.AzureCliCredential", return_value=credential), \
             patch("azure.ai.projects.AIProjectClient") as client:
            with self.assertRaisesRegex(h.Error, "APPROVAL_LIFETIME"):
                native.call("delete", agent_name=NAME, force=False)
            client.assert_not_called()

    def test_supported_404_only_is_absence_and_errors_are_sanitized(self):
        from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
        native = h.Native(self.env, self.a)
        for error, expected in ((ResourceNotFoundError("secret"), False), (HttpResponseError("secret 404"), False)):
            with patch.object(native, "client", side_effect=error):
                with self.assertRaises(h.Error) as caught:
                    native.absent("get", agent_name=NAME)
                self.assertNotIn("secret", str(caught.exception))
        error = ResourceNotFoundError("secret")
        error.status_code = 404
        with patch.object(native, "client", side_effect=error):
            self.assertTrue(native.absent("get", agent_name=NAME))

    def ghcp(self):
        self.a.update(skill="ghcp-hosted-agents", temporary_foundry_user_grants=True)
        self.env["HOSTED_CI_SKILL"] = "ghcp-hosted-agents"
        self.ledger.data["context"]["skill"] = "ghcp-hosted-agents"
        self.ledger.data.update(approval=deepcopy(self.a), approval_sha256=h.fingerprint(self.a))
        h.common.write(self.path / "receipt.json", self.ledger.data)
        self.ledger = h.Ledger(self.path, self.a, self.env)
        self.native = FakeNative(self.ledger)
        self.owned()
        self.ledger.data["agent"] = "ci-smoke-ghcp-" + "a" * 32
        self.ledger.save()

    def test_exact_role_create_ack_reget_and_standing_grants(self):
        self.ghcp()
        documents, mutations = {}, []
        def arm(method, resource_id, api, etag=None, **kwargs):
            if method == "GET":
                return (200, deepcopy(documents[resource_id]), None) if resource_id in documents else (
                    404, {"error": {"code": "RoleAssignmentDoesNotExist"}}, None)
            mutations.append((method, resource_id))
            kwargs["before_send"]()
            if method == "PUT":
                documents[resource_id] = {
                    "id": resource_id, "properties": {"scope": resource_id.rsplit("/providers/", 1)[0],
                    "principalId": PRINCIPAL, "principalType": "ServicePrincipal",
                    "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/{h.ROLE}"}}
                return 201, deepcopy(documents[resource_id]), None
            del documents[resource_id]
            return 204, {}, None
        with patch.object(h.common, "inventory", return_value=[]), patch.object(h.common, "require_cleanup_unlocked"):
            h.grant_roles(self.ledger, self.native, arm)
        self.assertEqual([item["state"] for item in self.ledger.data["roles"]], ["OWNED", "OWNED"])
        self.ledger.data["roles"][0]["state"] = "STANDING"
        h.cleanup_roles(self.ledger, arm, sleep=lambda _: None)
        self.assertEqual([method for method, _ in mutations], ["PUT", "PUT", "DELETE"])
        self.assertEqual(len(documents), 1)

    def test_unknown_role_ack_forbids_retry_and_delete(self):
        self.ghcp()
        def arm(method, resource_id, api, **kwargs):
            if method == "GET":
                return 404, {"error": {"code": "ResourceNotFound"}}, None
            kwargs["before_send"]()
            raise h.Error("NETWORK")
        with patch.object(h.common, "inventory", return_value=[]), patch.object(h.common, "require_cleanup_unlocked"):
            with self.assertRaises(h.Error):
                h.grant_roles(self.ledger, self.native, arm)
        self.assertEqual(self.ledger.data["roles"][0]["state"], "UNKNOWN")
        with self.assertRaisesRegex(h.Error, "RETRY_BLOCKED"):
            h.grant_roles(self.ledger, self.native, arm)
        with self.assertRaisesRegex(h.Error, "ROLE_OWNERSHIP_UNKNOWN"):
            h.cleanup_roles(self.ledger, arm)
        with self.assertRaisesRegex(h.Error, "ROLE_OWNERSHIP_UNKNOWN"):
            h.before_invoke(self.ledger, self.native)

    def test_partial_grant_failure_revokes_only_acknowledged_assignment(self):
        self.ghcp()
        documents, deleted = {}, []
        def arm(method, resource_id, api, *args, **kwargs):
            if method == "GET":
                return ((200, deepcopy(documents[resource_id]), None) if resource_id in documents else
                        (404, {"error": {"code": "ResourceNotFound"}}, None))
            kwargs["before_send"]()
            if method == "PUT":
                if "/projects/" in resource_id:
                    raise h.Error("ROLE_CREATE_UNKNOWN")
                documents[resource_id] = {"id": resource_id, "properties": {
                    "scope": resource_id.rsplit("/providers/", 1)[0], "principalId": PRINCIPAL,
                    "principalType": "ServicePrincipal",
                    "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/{h.ROLE}"}}
                return 201, deepcopy(documents[resource_id]), None
            deleted.append(resource_id)
            del documents[resource_id]
            return 204, {}, None
        with patch.object(h.common, "inventory", return_value=[]), patch.object(h.common, "require_cleanup_unlocked"):
            with self.assertRaisesRegex(h.Error, "ROLE_CREATE_UNKNOWN"):
                h.grant_roles(self.ledger, self.native, arm)
        with self.assertRaisesRegex(h.Error, "ROLE_OWNERSHIP_UNKNOWN"):
            h.cleanup_roles(self.ledger, arm, sleep=lambda _: None)
        self.assertEqual(len(deleted), 1)
        self.assertNotIn("/projects/", deleted[0])
        self.assertEqual([item["state"] for item in self.ledger.data["roles"]], ["ABSENT", "UNKNOWN"])

    def test_role_404_auth_and_changed_principal_are_not_ownership(self):
        self.assertFalse(h.role_absent(403, {"error": {"code": "ResourceNotFound"}}))
        self.assertFalse(h.role_absent(404, {"error": {"code": "AuthenticationFailed"}}))
        with self.assertRaises(h.Error):
            h.role_binding({"id": PROJECT, "properties": {}}, PROJECT, PRINCIPAL, SUB)

    def test_role_transport_is_fixed_to_approved_scope_role_and_principal_type(self):
        account = {"id": SUB, "tenantId": TENANT, "user": {"type": "servicePrincipal", "name": CLIENT}}
        class Response(io.BytesIO):
            code = 201
            headers = {}
        with patch.object(h.common.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(account).encode())) as cli:
            arm = h.common.Arm(self.env)
            cli.reset_mock()
            cli.return_value = subprocess.CompletedProcess([], 0, b"synthetic-token")
            resource = PROJECT + "/providers/Microsoft.Authorization/roleAssignments/" + CLIENT
            for bad_id, api, principal in (
                (resource.replace("/accounts/ci/", "/accounts/foreign/"), h.ROLE_API, PRINCIPAL),
                (resource, "2024-01-01", PRINCIPAL), (resource, h.ROLE_API, "not-an-id"),
                (resource.replace(SUB, TENANT), h.ROLE_API, PRINCIPAL),
            ):
                with self.subTest(resource=bad_id, api=api), self.assertRaises(h.Error):
                    arm("PUT", bad_id, api, role_principal=principal, before_send=lambda: None)
            cli.assert_not_called()
            with patch.object(h.common, "build_opener") as opener:
                opener.return_value.open.return_value = Response(b"{}")
                arm("PUT", resource, h.ROLE_API, role_principal=PRINCIPAL, before_send=lambda: None)
                request = opener.return_value.open.call_args.args[0]
                self.assertEqual(json.loads(request.data), {"properties": {
                    "principalId": PRINCIPAL, "principalType": "ServicePrincipal",
                    "roleDefinitionId": f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleDefinitions/{h.ROLE}"}})

    def test_role_transport_does_not_send_after_token_expires_approval(self):
        account = {"id": SUB, "tenantId": TENANT, "user": {"type": "servicePrincipal", "name": CLIENT}}
        with patch.object(h.common.subprocess, "run", return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(account).encode())) as cli:
            arm = h.common.Arm(self.env)
            def token(*_, **__):
                h.common.utc_now.return_value = datetime(2026, 9, 17, 12, 1, tzinfo=timezone.utc)
                return subprocess.CompletedProcess([], 0, b"synthetic-token")
            cli.side_effect = token
            with patch.object(h.common, "build_opener") as opener, self.assertRaisesRegex(h.Error, "APPROVAL_LIFETIME"):
                arm("PUT", PROJECT + "/providers/Microsoft.Authorization/roleAssignments/" + CLIENT,
                    h.ROLE_API, role_principal=PRINCIPAL, before_send=lambda: h.common.require_lifetime(self.a, 600))
            opener.return_value.open.assert_not_called()


class WorkflowTests(unittest.TestCase):
    def test_fixture_deploy_failure_preserves_status_and_stops_before_next_action(self):
        for skill in h.SKILLS:
            text = (ROOT / f"skills/{skill}/test-fixture/consumer_prompt.md").read_text()
            block = next(block for block in re.findall(r"```bash\n(.*?)\n```", text, re.S)
                         if block.startswith(f"bash /tmp/{skill}-ga-smoke.sh"))
            self.assertIn("Immutable test, not a repair session.", text)
            self.assertIn("tool denial, means write FAIL and STOP", text)
            self.assertIn("bypass the helper", text)
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)
                script = path / f"{skill}-ga-smoke.sh"
                script.write_text("exit 37\n")
                block = block.replace("/tmp/", str(path) + "/")
                result = subprocess.run(["bash", "-c", block + "\nprintf 'BYPASS_ATTEMPTED\\n'\n"],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 37)
                self.assertEqual((path / f"{skill}-smoke-result").read_text(),
                                 "SMOKE_RESULT=FAIL lifecycle deploy gate\n")
                self.assertNotIn("BYPASS_ATTEMPTED", result.stdout)

    def test_runner_finalizer_and_retry_gate_are_wired(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        triggers = workflow[True]
        self.assertIn("scripts/hosted-ci-lifecycle.py", triggers["pull_request"]["paths"])
        self.assertIn("scripts/**", triggers["push"]["paths"])
        steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        runtime = next(step for step in steps if step.get("id") == "hosted-lifecycle")
        self.assertIn("'openai~=2.45.0'", runtime["run"])
        finalizer = next(
            step for step in steps if step.get("name", "").startswith("Finalize Hosted"))
        self.assertIn("always()", finalizer["if"])
        self.assertTrue(finalizer["continue-on-error"])
        self.assertEqual(finalizer["timeout-minutes"], 5)
        self.assertIn('git show "$GITHUB_SHA:scripts/$SCRIPT"', finalizer["run"])
        self.assertIn("mcp-aca-ci-lifecycle.py", finalizer["run"])
        retry = next(step for step in steps if step.get("id") == "agentops-retry")
        self.assertLess(retry["run"].index("HOSTED_CI_LIFECYCLE=FAIL RETRY"),
                        retry["run"].index("copilot"))
        upload = next(step for step in steps if step.get("name") == "Preserve encrypted Hosted lifecycle inventory")
        self.assertEqual(upload["with"]["retention-days"], 1)
        self.assertTrue(upload["with"]["path"].endswith("/inventory.age"))

    def test_fixtures_call_owned_executor_and_never_delete_from_agent(self):
        for skill in h.SKILLS:
            text = (ROOT / f"skills/{skill}/test-fixture/consumer_prompt.md").read_text()
            with self.subTest(skill=skill):
                self.assertIn('hosted-ci-lifecycle.py" deploy "$work_dir" "$agent_name"', text)
                self.assertIn('"openai~=2.45.0"', text)
                self.assertIn('"before-invoke"' if skill == "foundry-hosted-agents" else '" before-invoke', text)
                self.assertNotIn("force=True", text)
                self.assertNotIn("azd ai agent delete", text)
                self.assertNotIn('"acr", "repository", "delete"', text)
                self.assertNotIn("az role assignment delete", text)
                self.assertIn("RECONCILED_OWNERSHIP", text)
                if skill == "foundry-hosted-agents":
                    self.assertNotIn("project.agents.update_details(", text)
                    self.assertLess(text.index('"configure-routing"'), text.index('"before-invoke"'))
                    self.assertLess(text.index('"before-invoke"'), text.index("response = openai_client.responses.create("))


if __name__ == "__main__":
    unittest.main()

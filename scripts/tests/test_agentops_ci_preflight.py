"""Offline owner-approval gate tests. No credentials, network, or native AgentOps."""

from __future__ import annotations

import contextlib
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "agentops-ci-preflight.py"
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
DIAGNOSTIC_RECIPIENT = "age1" + ("q" * 58)
DIAGNOSTIC_HEAD_SHA = "a" * 40


def fake_id(label):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.invalid/" + label))


def approval_record():
    subscription = fake_id("subscription")
    base = f"/subscriptions/{subscription}/resourceGroups/example-ci/providers/"
    return {
        "schema_version": 1,
        "authorization": {
            "status": "approved", "basis": "Synthetic operator test approval",
            "repository": "example/awesome-gbb", "pull_request": 17,
            "head_branch": "example-ci", "event_name": "pull_request",
            "expires_at": "2030-01-02T00:00:00Z", "purpose": "Offline synthetic validation",
            "merge_release_authorized": False,
        },
        "identity": {
            "credential_route": "ci-cli", "tenant_id": fake_id("tenant"),
            "subscription_id": subscription, "client_id": fake_id("client"),
            "principal_id": fake_id("principal"),
            "resource_id": base + "Microsoft.ManagedIdentity/userAssignedIdentities/example-identity",
        },
        "foundry": {
            "account_resource_id": base + "Microsoft.CognitiveServices/accounts/example-account",
            "allowed_project_endpoints": [
                "https://example-account.services.ai.azure.com/api/projects/example-project",
                "https://example-account.services.ai.azure.com/api/projects/other-approved-project",
            ],
            "project_selection": "Use the existing CI project endpoint only after exact membership validation; do not change projects or infer a default",
            "agent_model_deployment": "example-model", "eval_judge_deployment": "example-model",
            "doctor_judge_deployment": "example-model",
            "existing_workloads_must_remain_unchanged": True,
        },
        "telemetry": {
            "component_resource_id": base + "microsoft.insights/components/example-component",
            "application_id": fake_id("application"),
            "workspace_resource_id": base + "Microsoft.OperationalInsights/workspaces/example-workspace",
            "workspace_customer_id": fake_id("workspace"), "location": "example-region",
            "ingestion_endpoint": "https://example-region-0.in.applicationinsights.azure.com/",
            "live_endpoint": "https://example-region.livediagnostics.monitor.azure.com/",
            "retention_in_days": 30, "total_retention_in_days": 30,
            "immediate_purge_data_on_30_days": True, "daily_quota_gb": 0.1,
            "quota_is_not_a_hard_cost_or_ingestion_guarantee": True,
            "retention_tables": [
                "AppAvailabilityResults", "AppBrowserTimings", "AppDependencies",
                "AppEvents", "AppExceptions", "AppMetrics", "AppPageViews",
                "AppPerformanceCounters", "AppRequests", "AppSystemEvents",
                "AppTraces", "AppGenAIContent",
            ],
            "retention_authority": "Linked workspace and explicit table analytical/total retention; the legacy component RetentionInDays field is not authoritative",
            "export_scope": "Only these dedicated telemetry destinations and private runner-local native artifacts are approved; no shared telemetry secret fallback",
            "public_network_access": "Required for the existing GitHub-hosted runner; no private-network or Citadel changes",
            "ingestion_auth": "Native connection-string routing on the dedicated component; not permission to add an ingestion/write role or use inference API keys",
            "access": "Existing subscription/resource-group inherited Azure RBAC, including CI UAMI Contributor on example-ci; this is not exclusive access for the CI principal. Parent retained a private readback of 3 inherited assignments. No new roles were added; any additional roles require separate verification and are restricted to read access on these two new resources",
            "shared_secret_replacement_authorized": False,
        },
        "source_scope": {
            "enabled": ["results_history", "azure_monitor", "foundry_control", "azure_resources"],
            "azure_monitor_lookback_days": 1, "azure_monitor_query_count": 4,
            "azure_monitor_aggregate_only": True, "azure_monitor_has_no_run_filter": True,
            "historical_aggregates_are_not_current_run_ingestion_proof": True,
            "shared_resource_repairs_authorized": False,
        },
        "capture": {
            "synthetic_only": True, "synthetic_dataset_rows": 1,
            "existing_user_conversations_authorized": False,
            "native_prompt_response_tool_content_and_findings": "Approved only for the synthetic fixture; includes evaluation/Doctor judge inputs, native logs, evidence and any native Azure Monitor export",
            "full_doctor_required": True, "quality_failure_must_remain_failure": True,
            "unverified_coverage_must_remain_unverified": True,
            "retry_to_obtain_green_authorized": False,
            "other_telemetry_or_judge_destinations_authorized": False,
        },
        "storage_and_cleanup": {
            "responses_service_storage": "Operator accepts applicable native Foundry Responses service retention for the single synthetic fixture response; this is separate from Azure Monitor retention",
            "individual_response_purge_proven": False, "native_response_id_loss_limitation_accepted": True,
            "agent_deletion_does_not_prove_response_purge": True,
            "delete_only_fixture_owned_agents_and_versions": True,
            "preserve_existing_model_deployments": True,
            "runner_credentials_and_approval_file": "Private directories and approval file mode0600; remove in unconditional cleanup; never print or upload",
            "raw_artifact_access": "Restricted workflow/operator access only; raw native artifacts may contain the synthetic content and resource metadata",
            "raw_artifact_purge_by": "2030-01-05T00:00:00Z",
            "public_artifacts": "Only sanitized summaries and source/artifact hashes; never approval record, connection string or credentials",
            "azure_monitor_retention_is_not_an_exact_physical_purge_deadline": True,
        },
    }


def diagnostic_approval_record():
    record = approval_record()
    record["schema_version"] = 2
    record["diagnostic"] = {
        "enabled": True,
        "mode": "doctor-encrypted",
        "label": "agentops-diagnostic",
        "recipient": DIAGNOSTIC_RECIPIENT,
        "fingerprint": "sha256:" + hashlib.sha256(
            DIAGNOSTIC_RECIPIENT.encode("ascii")
        ).hexdigest(),
        "retention_days": 1,
        "head_sha": DIAGNOSTIC_HEAD_SHA,
        "run_attempt": 1,
    }
    record["storage_and_cleanup"]["public_artifacts"] = (
        "Sanitized summaries and source/artifact hashes; additionally, only the "
        "redacted Doctor log encrypted to the bound age recipient in a publicly "
        "downloadable artifact retained for 1 day; never plaintext native logs, "
        "approval record, connection strings or credentials"
    )
    record["storage_and_cleanup"]["raw_artifact_access"] = (
        "Plaintext native artifacts remain private to the runner/operator; only "
        "the redacted Doctor log may leave the runner as age ciphertext for the "
        "bound operator recipient"
    )
    return record


def connection_string(record, key=None):
    telemetry = record["telemetry"]
    return ";".join([
        "InstrumentationKey=" + (key or fake_id("routing-key")),
        "IngestionEndpoint=" + telemetry["ingestion_endpoint"],
        "LiveEndpoint=" + telemetry["live_endpoint"],
        "ApplicationId=" + telemetry["application_id"],
    ])


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.exists():
            cls.gate = None
            return
        spec = importlib.util.spec_from_file_location("agentops_ci_preflight", SCRIPT)
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def setUp(self):
        self.assertIsNotNone(self.gate, "The CI approval preflight implementation is missing")
        self.root = ROOT / (".agentops-ci-test-" + uuid.uuid4().hex)
        self.root.mkdir(mode=0o700)
        self.addCleanup(shutil.rmtree, self.root)
        self.private = self.root / "agentops-ci-123456-2"
        self.private.mkdir(mode=0o700)
        self.azure = self.private / "azure"
        self.azd = self.private / "azd"
        self.azure.mkdir(mode=0o700)
        self.azd.mkdir(mode=0o700)
        self.path = self.private / "owner-approval.json"
        self.record = approval_record()
        auth = self.record["authorization"]
        self.event = {
            "number": auth["pull_request"], "repository": {"full_name": auth["repository"]},
            "pull_request": {
                "number": auth["pull_request"],
                "head": {
                    "ref": auth["head_branch"],
                    "sha": "b" * 40,
                    "repo": {"full_name": auth["repository"]},
                },
                "base": {"repo": {"full_name": auth["repository"]}},
                "labels": [],
            },
        }
        self.event_path = self.root / "event.json"
        self.event_path.write_text(json.dumps(self.event))
        identity, foundry, telemetry = (
            self.record["identity"], self.record["foundry"], self.record["telemetry"]
        )
        self.env = {
            "RUNNER_TEMP": str(self.root), "AZURE_CONFIG_DIR": str(self.azure),
            "AZD_CONFIG_DIR": str(self.azd), "AZURE_TOKEN_CREDENTIALS": "AzureCliCredential",
            "AZURE_TENANT_ID": identity["tenant_id"], "AZURE_SUBSCRIPTION_ID": identity["subscription_id"],
            "AZURE_CLIENT_ID": identity["client_id"], "GITHUB_REPOSITORY": auth["repository"],
            "GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(self.event_path),
            "GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "2",
            "FOUNDRY_PROJECT_ENDPOINT": foundry["allowed_project_endpoints"][0],
            "AZURE_AI_PROJECT_ID": foundry["account_resource_id"] + "/projects/example-project",
            "FOUNDRY_MODEL_DEPLOYMENT": "example-model", "LAW_WORKSPACE_ID": telemetry["workspace_customer_id"],
            "APPLICATIONINSIGHTS_CONNECTION_STRING": connection_string(self.record),
            "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON": json.dumps(self.record, indent=2) + "\n",
        }
        self.account = {
            "id": identity["subscription_id"], "tenantId": identity["tenant_id"],
            "user": {"type": "servicePrincipal", "name": identity["client_id"]},
        }
        self.metadata = {
            identity["resource_id"]: {
                "id": identity["resource_id"],
                "properties": {key: identity[value] for key, value in (
                    ("tenantId", "tenant_id"), ("clientId", "client_id"), ("principalId", "principal_id")
                )},
            },
            telemetry["component_resource_id"]: {
                "id": telemetry["component_resource_id"], "location": telemetry["location"],
                "properties": {
                    "AppId": telemetry["application_id"], "WorkspaceResourceId": telemetry["workspace_resource_id"],
                    "InstrumentationKey": fake_id("routing-key"), "ConnectionString": connection_string(self.record),
                    "RetentionInDays": 90,
                },
            },
            telemetry["workspace_resource_id"]: {
                "id": telemetry["workspace_resource_id"], "location": telemetry["location"],
                "properties": {
                    "customerId": telemetry["workspace_customer_id"], "retentionInDays": 30,
                    "workspaceCapping": {"dailyQuotaGb": 0.1},
                    "features": {"immediatePurgeDataOn30Days": True},
                },
            },
        }
        for table in telemetry["retention_tables"]:
            resource_id = telemetry["workspace_resource_id"] + "/tables/" + table
            self.metadata[resource_id] = {
                "id": resource_id, "name": table,
                "properties": {"retentionInDays": 30, "totalRetentionInDays": 30},
            }
        self.calls = []

    def read_json(self, argv):
        self.calls.append(argv)
        if argv == ["az", "account", "show", "-o", "json"]:
            return copy.deepcopy(self.account)
        self.assertEqual(argv[:4], ["az", "resource", "show", "--ids"])
        self.assertEqual(argv[5], "--api-version")
        self.assertEqual(argv[7:], ["-o", "json"])
        self.assertIn(argv[4], self.metadata, "Discovery or non-approved resource requested")
        return copy.deepcopy(self.metadata[argv[4]])

    def run_gate(self, write=True, callback=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = self.gate.main(
                ["--write-approval" if write else "--approval-file", str(self.path)],
                environ=self.env, read_json=callback or self.read_json, now=NOW,
            )
        return result, out.getvalue(), err.getvalue()

    def sync_record(self):
        self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"] = json.dumps(self.record)

    def assert_denied(self, result=None):
        status, out, err = result or self.run_gate()
        self.assertEqual(status, 1)
        self.assertRegex(out, r"\AAGENTOPS_CI_PREFLIGHT=FAIL [A-Z_]+\n\Z")
        self.assertEqual(err, "")
        secret = self.env.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        if secret:
            self.assertNotIn(secret, out)

    def test_initial_write_and_secretless_fresh_recheck(self):
        raw = self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        self.assertEqual(self.run_gate(), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
        self.assertEqual(self.path.read_text(), raw)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(len(self.calls), 16)
        del self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        self.assertEqual(self.run_gate(write=False), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
        self.assertEqual(len(self.calls), 32)
        self.account["user"]["name"] = fake_id("changed-client")
        self.assert_denied(self.run_gate(write=False))

    def test_uami_readback_accepts_service_resourcegroups_casing(self):
        approved = self.record["identity"]["resource_id"]
        self.metadata[approved]["id"] = approved.replace("/resourceGroups/", "/resourcegroups/")
        raw = self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        self.assertEqual(self.run_gate(), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
        self.assertEqual(self.path.read_bytes(), raw.encode("utf-8"))
        self.assertEqual(self.calls[1][4], approved)

    def arm_id_boundaries(self):
        component = self.metadata[self.record["telemetry"]["component_resource_id"]]
        return [
            (resource_id, metadata, "id", "RESOURCE_BINDING")
            for resource_id, metadata in self.metadata.items()
        ] + [
            ("linked-workspace", component["properties"], "WorkspaceResourceId", "COMPONENT_BINDING"),
            ("selected-project", self.env, "AZURE_AI_PROJECT_ID", "PROJECT_BINDING"),
        ]

    def test_arm_id_casing_preserves_approval_bytes_and_exact_read_requests(self):
        raw = self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        original = copy.deepcopy(self.record)
        for boundary, target, key, _ in self.arm_id_boundaries():
            approved = target[key]
            for variant in (approved.lower(), approved.upper(), approved.swapcase()):
                with self.subTest(boundary=boundary, variant=variant):
                    target[key] = variant
                    self.calls.clear()
                    try:
                        self.assertEqual(self.run_gate(), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
                        self.assertEqual(self.path.read_bytes(), raw.encode("utf-8"))
                        with patch.dict(self.env):
                            del self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
                            self.assertEqual(self.run_gate(write=False),
                                             (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))
                        self.assertEqual(self.path.read_bytes(), raw.encode("utf-8"))
                        self.assertEqual(self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"], raw)
                        self.assertEqual(self.record, original)
                        self.assertEqual(target[key], variant)
                        self.assertEqual(len(self.calls), 32)
                        requests = [argv[4] for argv in self.calls if argv[1:3] == ["resource", "show"]]
                        self.assertEqual(requests, list(self.metadata) * 2)
                    finally:
                        target[key] = approved
                        self.path.unlink(missing_ok=True)

    def test_arm_ids_reject_every_non_case_difference_at_all_boundaries(self):
        for boundary, target, key, code in self.arm_id_boundaries():
            approved = target[key]
            parts = approved.split("/")
            variants = [
                "/tenants/" + fake_id("other-tenant") + approved,
                approved.replace(fake_id("subscription"), fake_id("other-subscription")),
                approved.replace("/resourceGroups/example-ci/", "/resourceGroups/other-ci/"),
                approved.replace("/providers/" + parts[6], "/providers/Microsoft.Other"),
                approved.replace("/" + parts[7] + "/", "/otherType/"),
                approved.replace("/" + parts[8], "/other-resource"),
                approved + "-other", approved + "/other-child", approved + "/",
                approved.replace("/providers/", "//providers/"),
                approved + "?api-version=2023-01-31", approved + "#fragment",
                " " + approved, approved + " ", approved + "\n",
                approved.replace("/subscriptions/", "/%73ubscriptions/"),
                approved.replace("/providers/", "%2Fproviders/"),
                approved.replace("/subscriptions/", "/\u017fubscriptions/"),
                approved.replace("/providers/", "/prov\u0130ders/"),
                approved.replace("/providers/", "/prov\u0131ders/"),
                approved.replace("example", "\u0435xample"),
                approved.replace("example", "\uff45xample"),
                approved.replace("/providers/", "\uff0fproviders/"),
                None, True, 1, [], {}, approved.encode("ascii"),
            ]
            if "workspace" in approved:
                variants.append(approved.replace("workspace", "wor\u212aspace"))
            if "/tables/" in approved:
                variants.append(approved.rsplit("/", 1)[0] + "/OtherTable")
            if "/projects/" in approved:
                variants.append(approved.rsplit("/", 1)[0] + "/other-approved-project")
            for variant in variants:
                with self.subTest(boundary=boundary, variant=variant):
                    target[key] = variant
                    expected_code = "MISSING_ENV" if target is self.env and not isinstance(variant, str) else code
                    try:
                        self.assertEqual(self.run_gate(),
                                         (1, f"AGENTOPS_CI_PREFLIGHT=FAIL {expected_code}\n", ""))
                        self.assertFalse(self.path.exists())
                    finally:
                        target[key] = approved

    def test_non_arm_identifiers_and_routing_values_remain_case_sensitive(self):
        identity, telemetry = self.record["identity"], self.record["telemetry"]
        uami = self.metadata[identity["resource_id"]]["properties"]
        component = self.metadata[telemetry["component_resource_id"]]
        workspace = self.metadata[telemetry["workspace_resource_id"]]
        cases = [
            (self.env, key, "IDENTITY_BINDING")
            for key in ("AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_CLIENT_ID")
        ] + [
            (self.env, "FOUNDRY_PROJECT_ENDPOINT", "PROJECT_BINDING"),
            (self.env, "FOUNDRY_MODEL_DEPLOYMENT", "MODEL_BINDING"),
            (self.env, "LAW_WORKSPACE_ID", "WORKSPACE_BINDING"),
            (self.env, "AZURE_TOKEN_CREDENTIALS", "CREDENTIAL_ROUTE"),
            (self.account, "id", "CLI_IDENTITY"), (self.account, "tenantId", "CLI_IDENTITY"),
            (self.account["user"], "name", "CLI_IDENTITY"),
            (self.account["user"], "type", "CLI_IDENTITY"),
            (component, "location", "COMPONENT_BINDING"),
            (component["properties"], "AppId", "COMPONENT_BINDING"),
            (component["properties"], "InstrumentationKey", "ROUTING_KEY"),
            (workspace, "location", "WORKSPACE_BINDING"),
            (workspace["properties"], "customerId", "WORKSPACE_BINDING"),
        ] + [
            (uami, key, "UAMI_BINDING") for key in ("tenantId", "clientId", "principalId")
        ] + [
            (metadata, "name", "TABLE_BINDING")
            for resource_id, metadata in self.metadata.items() if "/tables/" in resource_id
        ]
        for target, key, code in cases:
            with self.subTest(key=key, code=code):
                original = target[key]
                target[key] = original.swapcase()
                try:
                    self.assertEqual(self.run_gate(), (1, f"AGENTOPS_CI_PREFLIGHT=FAIL {code}\n", ""))
                    self.assertFalse(self.path.exists())
                finally:
                    target[key] = original
        for target, key in [
            (self.env, "APPLICATIONINSIGHTS_CONNECTION_STRING"),
            (component["properties"], "ConnectionString"),
        ]:
            original = target[key]
            for field in original.split(";"):
                name, value = field.split("=", 1)
                with self.subTest(connection=key, field=name):
                    target[key] = original.replace(value, value.swapcase())
                    code = "ROUTING_KEY" if name == "InstrumentationKey" else "TELEMETRY_BINDING"
                    try:
                        self.assertEqual(self.run_gate(),
                                         (1, f"AGENTOPS_CI_PREFLIGHT=FAIL {code}\n", ""))
                        self.assertFalse(self.path.exists())
                    finally:
                        target[key] = original

    def test_every_schema_field_required_and_no_unknown_keys(self):
        original = copy.deepcopy(self.record)
        for group, values in original.items():
            with self.subTest(missing=group):
                self.record = copy.deepcopy(original)
                del self.record[group]
                self.sync_record()
                self.assert_denied()
            if isinstance(values, dict):
                for key in values:
                    with self.subTest(group=group, missing=key):
                        self.record = copy.deepcopy(original)
                        del self.record[group][key]
                        self.sync_record()
                        self.assert_denied()
                self.record = copy.deepcopy(original)
                self.record[group]["unknown"] = True
                self.sync_record()
                self.assert_denied()
        self.record = copy.deepcopy(original)
        self.record["unknown"] = True
        self.sync_record()
        self.assert_denied()
        self.assertFalse(self.calls)

    def test_all_normative_policy_values_are_enforced(self):
        original = copy.deepcopy(self.record)
        mutable = {
            "authorization": {"basis", "purpose", "repository", "pull_request", "head_branch", "expires_at"},
            "identity": {"tenant_id", "subscription_id", "client_id", "principal_id", "resource_id"},
            "foundry": {"account_resource_id", "allowed_project_endpoints", "agent_model_deployment",
                        "eval_judge_deployment", "doctor_judge_deployment"},
            "telemetry": {"component_resource_id", "application_id", "workspace_resource_id",
                          "workspace_customer_id", "location", "ingestion_endpoint", "live_endpoint"},
            "storage_and_cleanup": {"raw_artifact_purge_by"},
        }
        for group, values in original.items():
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                if key in mutable.get(group, set()):
                    continue
                with self.subTest(group=group, field=key):
                    self.record = copy.deepcopy(original)
                    replacement = (
                        not value if isinstance(value, bool) else
                        value + 1 if isinstance(value, (int, float)) else
                        value[:-1] if isinstance(value, list) else "unapproved policy"
                    )
                    self.record[group][key] = replacement
                    self.sync_record()
                    self.assert_denied()
        self.assertFalse(self.calls)

    def test_context_expiry_and_scalar_types(self):
        for group, key, value in [
            ("authorization", "expires_at", "2029-12-31T23:59:59Z"),
            ("authorization", "expires_at", "2030-01-01T00:00:00Z"),
            ("authorization", "expires_at", "2030-01-02T00:00:00"),
            ("authorization", "expires_at", "2030-01-02T01:00:00+01:00"),
            ("authorization", "basis", " "), ("authorization", "purpose", ""),
            ("authorization", "pull_request", True), ("authorization", "pull_request", "17"),
            ("storage_and_cleanup", "raw_artifact_purge_by", "2029-12-31T00:00:00Z"),
            ("storage_and_cleanup", "raw_artifact_purge_by", "2030-01-01T12:00:00Z"),
            ("capture", "synthetic_dataset_rows", True), ("telemetry", "retention_in_days", 30.0),
            ("capture", "full_doctor_required", 1),
        ]:
            with self.subTest(group=group, key=key, value=value):
                self.record = approval_record()
                self.record[group][key] = value
                self.sync_record()
                self.assert_denied()
        for version in [3, True, "1", None]:
            self.record = approval_record()
            self.record["schema_version"] = version
            self.sync_record()
            self.assert_denied()

    def test_v2_exact_diagnostic_shape_hash_types_and_storage_policy(self):
        self.record = diagnostic_approval_record()
        self.event["action"] = "synchronize"
        self.event["pull_request"]["head"]["sha"] = DIAGNOSTIC_HEAD_SHA
        self.event["pull_request"]["labels"] = [{"name": "agentops-diagnostic"}]
        self.event_path.write_text(json.dumps(self.event))
        self.env["GITHUB_RUN_ATTEMPT"] = "1"
        self.private = self.root / "agentops-ci-123456-1"
        self.private.mkdir(mode=0o700)
        self.azure = self.private / "azure"
        self.azd = self.private / "azd"
        self.azure.mkdir(mode=0o700)
        self.azd.mkdir(mode=0o700)
        self.path = self.private / "owner-approval.json"
        self.env["AZURE_CONFIG_DIR"] = str(self.azure)
        self.env["AZD_CONFIG_DIR"] = str(self.azd)
        self.sync_record()
        self.assertEqual(self.run_gate(), (0, "AGENTOPS_CI_PREFLIGHT=PASS\n", ""))

        original = diagnostic_approval_record()
        cases = [
            ("missing-diagnostic", lambda r: r.pop("diagnostic")),
            ("missing", lambda r: r["diagnostic"].pop("label")),
            ("extra", lambda r: r["diagnostic"].update({"extra": True})),
            ("enabled-int", lambda r: r["diagnostic"].update({"enabled": 1})),
            ("mode", lambda r: r["diagnostic"].update({"mode": "doctor-plaintext"})),
            ("label", lambda r: r["diagnostic"].update({"label": "other"})),
            ("recipient-uppercase", lambda r: r["diagnostic"].update(
                {"recipient": r["diagnostic"]["recipient"].upper()})),
            ("recipient-shape", lambda r: r["diagnostic"].update({"recipient": "age1invalid"})),
            ("recipient-charset", lambda r: r["diagnostic"].update(
                {"recipient": "age1" + ("b" * 58)})),
            ("fingerprint", lambda r: r["diagnostic"].update(
                {"fingerprint": "sha256:" + ("0" * 64)})),
            ("fingerprint-newline", lambda r: r["diagnostic"].update({
                "fingerprint": "sha256:" + hashlib.sha256(
                    (r["diagnostic"]["recipient"] + "\n").encode("ascii")
                ).hexdigest()
            })),
            ("retention-bool", lambda r: r["diagnostic"].update({"retention_days": True})),
            ("head-sha", lambda r: r["diagnostic"].update({"head_sha": "A" * 40})),
            ("attempt-bool", lambda r: r["diagnostic"].update({"run_attempt": True})),
            ("v1-diagnostic", lambda r: r.update({"schema_version": 1})),
            ("v2-v1-public-policy", lambda r: r["storage_and_cleanup"].update(
                {"public_artifacts": approval_record()["storage_and_cleanup"]["public_artifacts"]})),
            ("v2-v1-raw-policy", lambda r: r["storage_and_cleanup"].update(
                {"raw_artifact_access": approval_record()["storage_and_cleanup"]["raw_artifact_access"]})),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                self.path.unlink(missing_ok=True)
                self.record = copy.deepcopy(original)
                mutate(self.record)
                self.sync_record()
                self.assert_denied()

        self.record = approval_record()
        self.record["diagnostic"] = copy.deepcopy(original["diagnostic"])
        self.sync_record()
        self.assert_denied()

    def test_v2_github_context_binds_label_head_attempt_and_nonfork_membership(self):
        self.record = diagnostic_approval_record()
        self.event["action"] = "synchronize"
        self.event["pull_request"]["head"]["sha"] = DIAGNOSTIC_HEAD_SHA
        self.event["pull_request"]["labels"] = [
            {"name": "unrelated"},
            {"name": "agentops-diagnostic"},
        ]
        self.event_path.write_text(json.dumps(self.event))
        self.env["GITHUB_RUN_ATTEMPT"] = "1"
        self.env["GITHUB_SHA"] = "d" * 40
        self.gate.validate_record(self.record, NOW)
        self.gate.validate_github_context(self.record, self.env)

        original_event = copy.deepcopy(self.event)
        cases = [
            ("missing-label", lambda e: e["pull_request"].update({"labels": []})),
            ("wrong-label-case", lambda e: e["pull_request"].update(
                {"labels": [{"name": "AgentOps-Diagnostic"}]})),
            ("wrong-head", lambda e: e["pull_request"]["head"].update({"sha": "c" * 40})),
            ("malformed-head", lambda e: e["pull_request"]["head"].update({"sha": "not-a-sha"})),
            ("fork", lambda e: e["pull_request"]["head"]["repo"].update(
                {"full_name": "fork/awesome-gbb"})),
            ("wrong-repository", lambda e: e["repository"].update(
                {"full_name": "other/awesome-gbb"})),
            ("wrong-pull-request", lambda e: e.update({"number": 99})),
            ("wrong-branch", lambda e: e["pull_request"]["head"].update({"ref": "other"})),
            ("missing-action", lambda e: e.pop("action")),
            ("opened-action", lambda e: e.update({"action": "opened"})),
            ("reopened-action", lambda e: e.update({"action": "reopened"})),
            ("closed-action", lambda e: e.update({"action": "closed"})),
            ("labeled-action", lambda e: e.update({"action": "labeled"})),
            ("other-action", lambda e: e.update({"action": "edited"})),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                event = copy.deepcopy(original_event)
                mutate(event)
                self.event_path.write_text(json.dumps(event))
                with self.assertRaisesRegex(self.gate.PreflightError, r"^CI_CONTEXT$"):
                    self.gate.validate_github_context(self.record, self.env)
        self.event_path.write_text(json.dumps(original_event))
        for attempt in ("2", "01", 1):
            with self.subTest(attempt=attempt):
                self.env["GITHUB_RUN_ATTEMPT"] = attempt
                with self.assertRaisesRegex(self.gate.PreflightError, r"^CI_CONTEXT$"):
                    self.gate.validate_github_context(self.record, self.env)
        self.env["GITHUB_RUN_ATTEMPT"] = "1"
        self.env["GITHUB_EVENT_NAME"] = "push"
        with self.assertRaisesRegex(self.gate.PreflightError, r"^CI_CONTEXT$"):
            self.gate.validate_github_context(self.record, self.env)

        expired = diagnostic_approval_record()
        expired["authorization"]["expires_at"] = "2030-01-01T00:00:00Z"
        with self.assertRaisesRegex(self.gate.PreflightError, r"^EXPIRED$"):
            self.gate.validate_record(expired, NOW)

    def test_v1_github_context_keeps_original_membership_semantics(self):
        self.env["GITHUB_RUN_ATTEMPT"] = "9"
        self.event["pull_request"]["head"]["sha"] = "not-used-by-v1"
        self.event["pull_request"]["labels"] = []
        self.event_path.write_text(json.dumps(self.event))
        self.gate.validate_record(self.record, NOW)
        self.gate.validate_github_context(self.record, self.env)

    def test_each_environment_binding_is_mandatory_and_exact(self):
        original = self.env.copy()
        for key in (
            "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_CLIENT_ID",
            "AZURE_TOKEN_CREDENTIALS", "FOUNDRY_PROJECT_ENDPOINT", "AZURE_AI_PROJECT_ID",
            "FOUNDRY_MODEL_DEPLOYMENT", "LAW_WORKSPACE_ID", "GITHUB_REPOSITORY",
            "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
            "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "RUNNER_TEMP", "AZURE_CONFIG_DIR",
            "AZD_CONFIG_DIR", "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON",
        ):
            for value in (None, "", "wrong"):
                with self.subTest(key=key, value=value):
                    self.env = original.copy()
                    if value is None:
                        del self.env[key]
                    else:
                        self.env[key] = value
                    self.assert_denied()
        self.assertFalse(self.path.exists())

    def test_event_binding_uses_event_head_not_environment(self):
        original = copy.deepcopy(self.event)
        for path, value in [
            (("number",), 99), (("repository", "full_name"), "other/awesome-gbb"),
            (("pull_request", "number"), 99),
            (("pull_request", "head", "ref"), "other-branch"),
            (("pull_request", "head", "repo", "full_name"), "unapproved/awesome-gbb"),
            (("pull_request", "base", "repo", "full_name"), "other/awesome-gbb"),
        ]:
            with self.subTest(path=path):
                self.event = copy.deepcopy(original)
                target = self.event
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.event_path.write_text(json.dumps(self.event))
                self.env["GITHUB_HEAD_REF"] = self.record["authorization"]["head_branch"]
                self.assert_denied()
        self.assertFalse(self.calls)

    def test_identity_and_resource_metadata_bindings(self):
        identity = self.record["identity"]
        telemetry = self.record["telemetry"]
        cases = [
            ("account", ("id",), fake_id("other-subscription")),
            ("account", ("tenantId",), fake_id("other-tenant")),
            ("account", ("user", "type"), "user"),
            ("account", ("user", "name"), fake_id("other-client")),
            (identity["resource_id"], ("id",), identity["resource_id"] + "-wrong"),
            (identity["resource_id"], ("properties", "tenantId"), fake_id("other-tenant")),
            (identity["resource_id"], ("properties", "clientId"), fake_id("other-client")),
            (identity["resource_id"], ("properties", "principalId"), fake_id("other-principal")),
        ]
        for resource, fields in [
            (telemetry["component_resource_id"], [
                ("id",), ("location",), ("properties", "AppId"),
                ("properties", "WorkspaceResourceId"), ("properties", "InstrumentationKey"),
                ("properties", "ConnectionString"),
            ]),
            (telemetry["workspace_resource_id"], [
                ("id",), ("location",), ("properties", "customerId"),
                ("properties", "retentionInDays"), ("properties", "workspaceCapping", "dailyQuotaGb"),
                ("properties", "features", "immediatePurgeDataOn30Days"),
            ]),
        ]:
            cases.extend((resource, path, "wrong") for path in fields)
        for resource, path, value in cases:
            with self.subTest(resource=resource, path=path):
                target = self.account if resource == "account" else self.metadata[resource]
                for field in path[:-1]:
                    target = target[field]
                old = target[path[-1]]
                target[path[-1]] = value
                self.assert_denied()
                target[path[-1]] = old

    def test_each_table_requires_both_30_day_retentions(self):
        telemetry = self.record["telemetry"]
        for table in telemetry["retention_tables"]:
            resource_id = telemetry["workspace_resource_id"] + "/tables/" + table
            for field in ("retentionInDays", "totalRetentionInDays"):
                for value in (None, 90, -1, 30.0, True):
                    with self.subTest(table=table, field=field, value=value):
                        props = self.metadata[resource_id]["properties"]
                        if value is None:
                            del props[field]
                        else:
                            props[field] = value
                        self.assert_denied()
                        props[field] = 30
            saved = self.metadata[resource_id]
            self.metadata[resource_id] = None
            self.assert_denied()
            self.metadata[resource_id] = saved

    def test_routing_key_not_just_application_id_and_no_export_overrides(self):
        self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string(
            self.record, fake_id("wrong-routing-key")
        )
        self.assert_denied()
        self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string(self.record)
        for name, value in [
            ("AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING", connection_string(self.record, fake_id("other"))),
            ("AGENTOPS_OTLP_ENDPOINT", "https://export.example.invalid"),
            ("OTEL_EXPORTER_OTLP_ENDPOINT", "https://export.example.invalid"),
            ("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://export.example.invalid"),
            ("OTEL_TRACES_EXPORTER", "console"), ("APPINSIGHTS_INSTRUMENTATIONKEY", fake_id("other")),
            ("APPLICATIONINSIGHTS_INSTRUMENTATIONKEY", fake_id("other")),
            ("AZURE_MONITOR_CONNECTION_STRING", connection_string(self.record)),
            ("OTEL_CONFIG_FILE", "/example/unapproved-exporter.yaml"),
            ("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", self.record["foundry"]["allowed_project_endpoints"][1]),
            ("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true"),
        ]:
            with self.subTest(name=name):
                self.env[name] = value
                self.assert_denied()
                del self.env[name]

    def test_connection_string_requires_unambiguous_explicit_fields(self):
        valid = connection_string(self.record)
        for bad in [
            valid + ";InstrumentationKey=" + fake_id("other"),
            valid + ";instrumentationkey=" + fake_id("other"),
            valid + ";EndpointSuffix=example.invalid", valid + ";broken",
            valid.replace("https://", "http://"),
            ";".join(valid.split(";")[:-1]),
        ]:
            self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"] = bad
            self.assert_denied()

    def test_approval_json_unknown_duplicates_and_malformed_fail_closed(self):
        for raw in ("{}", "[]", "null", "{", '{"schema_version":1,"schema_version":1}',
                    json.dumps(self.record).replace('"daily_quota_gb": 0.1', '"daily_quota_gb": NaN')):
            self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"] = raw
            self.assert_denied()
        self.assertFalse(self.calls)

    def test_path_boundary_permissions_symlinks_and_no_cleanup_of_other_assets(self):
        sentinel = self.root / "keep"
        sentinel.write_text("not fixture owned")
        original = self.path
        for destination in (self.root / "approval.json", self.root / "agentops-ci-private-other" / "approval.json",
                            self.private / ".." / "approval.json"):
            self.path = destination
            self.assert_denied()
        self.path = original
        self.path.symlink_to(sentinel)
        self.assert_denied()
        self.path.unlink()
        self.path.write_text("{}")
        self.path.chmod(0o644)
        self.assert_denied(self.run_gate(write=False))
        self.assert_denied()
        self.path.unlink()
        self.private.chmod(0o755)
        self.assert_denied()
        self.private.chmod(0o700)
        nested = self.private / "symlink"
        nested.symlink_to(self.private, target_is_directory=True)
        self.path = nested / "approval.json"
        self.assert_denied()
        self.assertEqual(sentinel.read_text(), "not fixture owned")
        self.assertFalse(self.calls)

    def test_config_is_private_stable_and_azd_empty(self):
        self.azure.chmod(0o755)
        self.assert_denied()
        self.azure.chmod(0o700)
        (self.azd / "credential.json").write_text("synthetic")
        self.assert_denied()
        (self.azd / "credential.json").unlink()
        self.env["AZD_CONFIG_DIR"] = str(self.azure)
        self.assert_denied()
        self.env["AZD_CONFIG_DIR"] = str(self.private)
        self.assert_denied()
        self.env["AZD_CONFIG_DIR"] = str(self.azd)
        self.azure.rmdir()
        self.azure.symlink_to(self.azd, target_is_directory=True)
        self.assert_denied()
        self.assertFalse(self.calls)

    def test_azure_profile_symlink_outside_private_root_fails_before_metadata(self):
        outside = self.root / "outside-profile.json"
        outside.write_text("SYNTHETIC_PRIVATE_CACHE")
        (self.azure / "azureProfile.json").symlink_to(outside)
        result = self.run_gate()
        self.assert_denied(result)
        self.assertFalse(self.calls)
        self.assertFalse(self.path.exists())
        self.assertEqual(outside.read_text(), "SYNTHETIC_PRIVATE_CACHE")
        self.assertNotIn("SYNTHETIC_PRIVATE_CACHE", "".join(result[1:]))

    def test_azure_cache_rejects_nested_file_and_directory_symlinks(self):
        nested = self.azure / "nested"
        nested.mkdir(mode=0o700)
        outside_dir = self.root / "outside-cache"
        outside_dir.mkdir(mode=0o700)
        outside_file = outside_dir / "token.json"
        outside_file.write_text("SYNTHETIC_PRIVATE_CACHE")
        for target in (outside_dir, outside_file, self.azure / "nonexistent"):
            with self.subTest(directory=target == outside_dir):
                link = nested / "linked-cache"
                link.symlink_to(target, target_is_directory=target == outside_dir)
                try:
                    self.assert_denied()
                    self.assertFalse(self.calls)
                finally:
                    link.unlink()
                    self.path.unlink(missing_ok=True)

    def test_final_validation_rejects_cache_symlink_created_during_metadata(self):
        outside = self.root / "outside-profile.json"
        outside.write_text("SYNTHETIC_PRIVATE_CACHE")
        def replace_cache(argv):
            if argv[1:3] == ["account", "show"]:
                (self.azure / "azureProfile.json").symlink_to(outside)
            return self.read_json(argv)
        result = self.run_gate(callback=replace_cache)
        self.assert_denied(result)
        self.assertEqual(len(self.calls), 16)
        self.assertFalse(self.path.exists())
        self.assertEqual(outside.read_text(), "SYNTHETIC_PRIVATE_CACHE")

    def test_regular_nested_azure_cache_is_allowed_and_not_modified(self):
        nested = self.azure / "nested"
        nested.mkdir(mode=0o700)
        profile = self.azure / "azureProfile.json"
        token = nested / "token.json"
        profile.write_text("SYNTHETIC_PROFILE")
        token.write_text("SYNTHETIC_TOKEN")
        self.assertEqual(self.run_gate()[0], 0)
        self.assertEqual(profile.read_text(), "SYNTHETIC_PROFILE")
        self.assertEqual(token.read_text(), "SYNTHETIC_TOKEN")

    def test_run_specific_private_root_cannot_use_another_run_or_attempt(self):
        for name, values in (
            ("GITHUB_RUN_ID", ("123457", "0", "-1", "../123456", "123456/extra")),
            ("GITHUB_RUN_ATTEMPT", ("3", "0", "-1", "../2", "2/extra")),
        ):
            original = self.env[name]
            for value in values:
                with self.subTest(name=name, value=value):
                    self.env[name] = value
                    self.assert_denied()
            self.env[name] = original
        self.assertFalse(self.calls)

    def test_component_metadata_uses_explicit_arm_properties_not_sdk_aliases(self):
        props = self.metadata[self.record["telemetry"]["component_resource_id"]]["properties"]
        for name in ("AppId", "WorkspaceResourceId", "InstrumentationKey", "ConnectionString"):
            with self.subTest(name=name):
                value = props.pop(name)
                alias = name[0].lower() + name[1:]
                props[alias] = value
                self.assert_denied()
                props[name] = props.pop(alias)

    def test_missing_parent_created_privately_only_after_validation(self):
        self.path = self.private / "approval" / "owner.json"
        self.assertEqual(self.run_gate()[0], 0)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_errors_do_not_leak_cli_arguments_stdout_stderr_or_tracebacks(self):
        secret = "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"
        for error in [
            subprocess.CalledProcessError(1, ["az", secret], output=secret, stderr=secret),
            subprocess.TimeoutExpired(["az", secret], 20, output=secret, stderr=secret),
            FileNotFoundError(secret), ValueError(secret), RuntimeError(secret),
        ]:
            with self.subTest(error=type(error)):
                def fail(argv):
                    raise error
                result = self.run_gate(callback=fail)
                self.assert_denied(result)
                self.assertNotIn(secret, "".join(result[1:]))
                self.assertFalse(self.path.exists())

    def test_real_cli_adapter_captures_bounds_and_never_mutates_environment(self):
        completed = subprocess.CompletedProcess([], 0, json.dumps(self.account), "")
        with patch.object(self.gate.subprocess, "run", return_value=completed) as run:
            result = self.gate.cli_read_json(["az", "account", "show", "-o", "json"], self.env)
        self.assertEqual(result, self.account)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["az", "account", "show", "-o", "json"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertGreater(kwargs["timeout"], 0)
        self.assertLessEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["env"], self.env)
        self.assertNotIn("shell", kwargs)

    def test_models_and_all_approved_endpoint_mappings_must_agree(self):
        original = copy.deepcopy(self.record)
        for key in ("agent_model_deployment", "eval_judge_deployment", "doctor_judge_deployment"):
            self.record = copy.deepcopy(original)
            self.record["foundry"][key] = "other-model"
            self.sync_record()
            self.assert_denied()
        for endpoint in [
            "https://another-account.services.ai.azure.com/api/projects/example-project",
            "https://example-account.services.ai.azure.com/api/projects/example-project?route=other",
            "https://example-account.services.ai.azure.com/api/projects/example-project/",
            "https://example-account.services.ai.azure.com/api/projects/../other-project",
        ]:
            self.record = copy.deepcopy(original)
            self.record["foundry"]["allowed_project_endpoints"] = [endpoint]
            self.env["FOUNDRY_PROJECT_ENDPOINT"] = endpoint
            self.sync_record()
            self.assert_denied()
        self.assertFalse(self.calls)

    def test_alternate_approved_project_never_adds_a_new_metadata_destination(self):
        foundry = self.record["foundry"]
        self.env["FOUNDRY_PROJECT_ENDPOINT"] = foundry["allowed_project_endpoints"][1]
        self.env["AZURE_AI_PROJECT_ID"] = foundry["account_resource_id"] + "/projects/other-approved-project"
        self.env["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"] = self.env["FOUNDRY_PROJECT_ENDPOINT"]
        self.env["AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string(self.record)
        self.assertEqual(self.run_gate()[0], 0)
        self.assertEqual(len(self.calls), 16)

    def test_no_shared_secret_fallback_even_if_agentops_alias_is_valid(self):
        del self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"]
        self.env["AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING"] = connection_string(self.record)
        self.assert_denied()
        self.assertFalse(self.calls)

    def test_record_resource_ids_cannot_expand_subscription_scope(self):
        original = copy.deepcopy(self.record)
        for group, key in [
            ("identity", "resource_id"), ("foundry", "account_resource_id"),
            ("telemetry", "component_resource_id"), ("telemetry", "workspace_resource_id"),
        ]:
            self.record = copy.deepcopy(original)
            self.record[group][key] = self.record[group][key].replace(
                fake_id("subscription"), fake_id("other-subscription")
            )
            self.sync_record()
            self.assert_denied()
        self.assertFalse(self.calls)

    def test_exact_source_and_table_sets_reject_duplicates_and_substitutions(self):
        original = copy.deepcopy(self.record)
        for group, key in [("source_scope", "enabled"), ("telemetry", "retention_tables")]:
            for operation in ("duplicate", "substitute", "extra"):
                self.record = copy.deepcopy(original)
                items = self.record[group][key]
                if operation == "duplicate":
                    items[-1] = items[0]
                elif operation == "substitute":
                    items[-1] = "Unapproved"
                else:
                    items.append("Unapproved")
                self.sync_record()
                self.assert_denied()
        self.assertFalse(self.calls)

    def test_missing_metadata_is_never_a_success_default(self):
        original = copy.deepcopy(self.metadata)
        telemetry = self.record["telemetry"]
        for resource_id, keys in [
            (self.record["identity"]["resource_id"], ("properties", "principalId")),
            (telemetry["component_resource_id"], ("properties", "ConnectionString")),
            (telemetry["component_resource_id"], ("properties", "InstrumentationKey")),
            (telemetry["workspace_resource_id"], ("properties", "features", "immediatePurgeDataOn30Days")),
        ]:
            self.metadata = copy.deepcopy(original)
            target = self.metadata[resource_id]
            for key in keys[:-1]:
                target = target[key]
            del target[keys[-1]]
            self.assert_denied()

    def test_retry_rejects_file_permission_hardlink_and_expiry_changes(self):
        self.assertEqual(self.run_gate()[0], 0)
        del self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        self.path.chmod(0o640)
        self.assert_denied(self.run_gate(write=False))
        self.path.chmod(0o600)
        link = self.private / "hardlink.json"
        os.link(self.path, link)
        self.assert_denied(self.run_gate(write=False))
        link.unlink()
        self.record["authorization"]["expires_at"] = "2029-01-01T00:00:00Z"
        self.path.write_text(json.dumps(self.record))
        self.assert_denied(self.run_gate(write=False))

    def test_recheck_detects_approval_replacement_during_metadata_reads(self):
        self.assertEqual(self.run_gate()[0], 0)
        del self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"]
        def replace_approval(argv):
            if argv[1:3] == ["account", "show"]:
                replaced = copy.deepcopy(self.record)
                replaced["capture"]["retry_to_obtain_green_authorized"] = True
                self.path.write_text(json.dumps(replaced))
            return self.read_json(argv)
        self.assert_denied(self.run_gate(write=False, callback=replace_approval))

    def test_preflight_exception_cannot_smuggle_a_secret_as_a_code(self):
        secret = "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"
        def fail(argv):
            raise self.gate.PreflightError(secret)
        status, out, err = self.run_gate(callback=fail)
        self.assertEqual(status, 1)
        self.assertNotIn(secret, out + err)
        self.assertEqual(out, "AGENTOPS_CI_PREFLIGHT=FAIL INTERNAL_ERROR\n")

    def test_real_cli_adapter_failure_output_remains_private(self):
        secret = "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"
        for failure in [
            subprocess.CalledProcessError(1, ["az", secret], output=secret, stderr=secret),
            subprocess.TimeoutExpired(["az", secret], 20, output=secret, stderr=secret),
            FileNotFoundError(secret),
        ]:
            with patch.object(self.gate.subprocess, "run", side_effect=failure):
                result = self.run_gate(
                    callback=lambda argv: self.gate.cli_read_json(argv, self.env)
                )
            self.assert_denied(result)
            self.assertNotIn(secret, "".join(result[1:]))

    def test_partial_write_failure_cleans_only_the_new_approval_inode(self):
        sentinel = self.private / "keep"
        sentinel.write_text("keep")
        with patch.object(self.gate.os, "fsync", side_effect=OSError("SYNTHETIC_SECRET")):
            result = self.run_gate()
        self.assert_denied(result)
        self.assertNotIn("SYNTHETIC_SECRET", "".join(result[1:]))
        self.assertFalse(self.path.exists())
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertTrue(self.azure.is_dir())
        self.assertTrue(self.azd.is_dir())

    def test_cli_entrypoint_sanitizes_argument_and_missing_secret_failures(self):
        for args in [[], ["--unknown-SYNTHETIC_SECRET"], ["--write-approval", str(self.path)]]:
            env = {"PATH": os.environ["PATH"], "PYTHONDONTWRITEBYTECODE": "1"}
            completed = subprocess.run(
                [os.sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertRegex(completed.stdout, r"\AAGENTOPS_CI_PREFLIGHT=FAIL [A-Z_]+\n\Z")
            self.assertEqual(completed.stderr, "")
            self.assertNotIn("SYNTHETIC_SECRET", completed.stdout)


if __name__ == "__main__":
    unittest.main()

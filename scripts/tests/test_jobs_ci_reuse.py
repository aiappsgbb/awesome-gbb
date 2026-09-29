"""Synthetic CI reuse contract: no Azure I/O, no shared provisioning or cleanup."""

import copy
from contextlib import chdir
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID
import sys

import httpx
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "skills/foundry-mcp-aca-jobs/templates"
SPEC = importlib.util.spec_from_file_location("ci_reuse", TEMPLATE / "infra/scripts/ci_reuse.py")
reuse = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reuse)
sys.path.insert(0, str(ROOT / "skills/foundry-hosted-agents/references/python"))


def environment():
    guid = lambda n: str(UUID(int=n))
    group = f"/subscriptions/{guid(1)}/resourceGroups/ci-example"
    values = {
        "group": group, "database": "standing-db", "tenant": guid(2), "subscription": guid(1),
        "executor": guid(3), "executor_client": guid(4), "audience": guid(5),
        "cosmos_endpoint": "https://ci-cosmos.documents.azure.com:443/",
        "storage_endpoint": "https://cistorage.blob.core.windows.net/",
        "registry_host": "ciregistry.azurecr.io",
    }
    for key, kind in reuse.TYPES.items():
        name = {"cosmos": "ci-cosmos", "storage": "cistorage", "registry": "ciregistry"}.get(key, key.replace("_", "-"))
        values[key] = group + "/providers/" + kind + "/" + name
    return {"MCP_ACA_JOBS_CI_REUSE": "existing", **{env: values[key] for key, env in reuse.INPUTS.items()}}


def observed(config):
    data = {key: {"id": config[key], "location": "Sweden Central",
                  "properties": {"provisioningState": "Succeeded"}} for key in reuse.VERSIONS}
    data["database"] = {"id": config["cosmos"] + "/sqlDatabases/" + config["database"]}
    data["account"] = {"id": config["subscription"], "tenantId": config["tenant"],
                       "user": {"type": "servicePrincipal", "name": config["executor_client"]}}
    data["executor_identity"] = {"principalId": config["executor"], "clientId": config["executor_client"]}
    for index, key in enumerate(("app_identity", "worker_identity"), 6):
        data[key]["properties"].update(principalId=str(UUID(int=index)), clientId=str(UUID(int=index + 2)), tenantId=config["tenant"])
    data["registry"]["properties"].update(loginServer=config["registry_host"],
                                         roleAssignmentMode="LegacyRegistryPermissions", adminUserEnabled=False)
    data["cosmos"]["properties"].update(documentEndpoint=config["cosmos_endpoint"], disableLocalAuth=True)
    data["storage"]["properties"].update(primaryEndpoints={"blob": config["storage_endpoint"]}, allowSharedKeyAccess=False)
    data["role_definitions"] = {}
    data["grants"] = {}
    for actor in ("executor", "app", "worker"):
        data["grants"][actor] = {}
        for scope in ("group", "registry", "storage"):
            role = {"group": "Contributor" if actor == "executor" else "CI job operator",
                    "registry": "AcrPush" if actor == "executor" else "AcrPull",
                    "storage": "Storage Blob Data Contributor"}[scope]
            role_id = "/roles/" + reuse.BUILTIN_ROLES.get(role, role.replace(" ", "-"))
            data["grants"][actor][scope] = [{"roleDefinitionName": role, "roleDefinitionId": role_id, "scope": config[scope]}]
            data["role_definitions"][role_id] = {"properties": {"permissions": [{"actions": sorted(reuse.JOB_ACTIONS)}]}}
    db_scope = config["cosmos"] + "/dbs/" + config["database"]
    data["cosmos_roles"], data["cosmos_definitions"] = [], []
    for actor, principal in (("executor", config["executor"]), ("app", str(UUID(int=6))), ("worker", str(UUID(int=7)))):
        role_id = config["cosmos"] + "/sqlRoleDefinitions/" + actor
        actions = ["Microsoft.DocumentDB/databaseAccounts/readMetadata",
                   "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read",
                   "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/executeQuery"]
        if actor != "executor":
            actions.append("Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/*")
        data["cosmos_roles"].append({"principalId": principal, "scope": db_scope, "roleDefinitionId": role_id})
        data["cosmos_definitions"].append({"id": role_id, "permissions": [{"dataActions": actions}]})
    return data


class JobsReuseTests(unittest.TestCase):
    def setUp(self):
        self.config = reuse.settings(environment(), "abcdef12")
        self.data = observed(self.config)

    def test_valid_standing_scope_distinguishes_executor_reader_from_runtime_writers(self):
        self.assertEqual(reuse.validate(self.config, self.data)["location"], "swedencentral")
        self.assertNotIn("items/*", str(self.data["cosmos_definitions"][0]))
        with patch.object(reuse.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="{}")) as run:
            reuse.cli(self.config, ["account", "show"])
            self.assertNotIn("--subscription", run.call_args.args[0], "Must read actual active context, not select the expected account")

    def test_every_missing_input_fails_without_any_azure_call(self):
        for field in reuse.INPUTS.values():
            env = environment()
            del env[field]
            with self.subTest(field=field), patch.object(reuse, "cli") as cli, self.assertRaises(reuse.ReuseError):
                reuse.settings(env, "abcdef12")
            cli.assert_not_called()
        with self.assertRaises(reuse.ReuseError):
            reuse.settings({**environment(), "MCP_ACA_JOBS_CI_REUSE": ""}, "abcdef12")

    def test_cross_scope_identity_or_database_input_never_falls_back(self):
        for key in ("app_identity", "worker_identity", "cosmos", "storage", "environment", "registry"):
            env = environment()
            env[reuse.INPUTS[key]] = env[reuse.INPUTS[key]].replace("ci-example", "another-group")
            with self.subTest(key=key), self.assertRaises(reuse.ReuseError):
                reuse.settings(env, "abcdef12")
        for database in ("../standing", "standing/other", "", "a\nb"):
            with self.assertRaises(reuse.ReuseError):
                reuse.settings({**environment(), "MCP_ACA_JOBS_COSMOS_DATABASE": database}, "abcdef12")

    def test_wrong_actual_binding_or_missing_writer_grant_fails_closed(self):
        for mutate in (
            lambda d: d["database"].update(id=self.config["cosmos"] + "/sqlDatabases/another"),
            lambda d: d["cosmos"]["properties"].update(documentEndpoint="https://wrong.documents.azure.com"),
            lambda d: d["registry"]["properties"].update(roleAssignmentMode="AbacRepositoryPermissions"),
            lambda d: d["grants"]["worker"].update(storage=[]),
            lambda d: d["cosmos_roles"][2].update(scope=self.config["cosmos"] + "/dbs/another"),
            lambda d: d["account"]["user"].update(type="user"),
            lambda d: d["executor_identity"].update(principalId=str(UUID(int=999))),
            lambda d: d["grants"]["worker"]["storage"][0].update(scope=""),
            lambda d: d["grants"]["executor"]["group"][0].update(roleDefinitionId="/roles/custom-named-Contributor"),
            lambda d: d.update(storage=None),
        ):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(reuse.ReuseError):
                reuse.validate(self.config, data)

    def test_preexisting_temp_resource_is_not_adopted(self):
        with patch.object(reuse, "observations", return_value=self.data), patch.object(reuse, "get", return_value={"id": "existing"}):
            with self.assertRaisesRegex(reuse.ReuseError, "RUN_TARGET_ALREADY_EXISTS"):
                reuse.check(self.config, absent=True)

    def manifest(self):
        return {"config_sha256": hashlib.sha256(json.dumps(self.config, sort_keys=True).encode()).hexdigest(),
                "absent_before": {key: rid for key, (rid, _) in reuse.owned(self.config).items()},
                "image_repositories_absent_before": [reuse.image_repository(self.config), reuse.image_repository(self.config, True)],
                "observed_at": "2026-01-01T00:00:00+00:00"}

    def test_cleanup_plan_contains_only_exact_run_objects_never_shared_database_or_identities(self):
        plan = reuse.cleanup_plan(self.config, self.manifest())
        self.assertEqual(len(plan), 5)
        for _, resource_id, _ in plan:
            self.assertIn("abcdef12", resource_id)
            self.assertNotIn("roleAssignments", resource_id)
            self.assertNotIn("userAssignedIdentities", resource_id)
            self.assertNotEqual(resource_id, self.config["group"])
            self.assertNotEqual(resource_id, self.config["cosmos"] + "/sqlDatabases/" + self.config["database"])
        for key in ("group", "cosmos", "app_identity", "worker_identity", "storage"):
            bad = self.manifest()
            bad["absent_before"]["app"] = self.config[key]
            with self.assertRaises(reuse.ReuseError):
                reuse.cleanup_plan(self.config, bad)

    def test_cleanup_rejects_unrecorded_or_replaced_objects_before_delete(self):
        with patch.object(reuse, "get", return_value={"id": "not-recorded"}), patch.object(reuse, "cli") as cli:
            with self.assertRaises(reuse.ReuseError):
                reuse.cleanup(self.config, self.manifest(), {})
            cli.assert_not_called()
        target = reuse.owned(self.config)["job"][0]
        created = {"job": {"id": target, "created_at": "2026-01-01T01:00:00Z"}}
        with patch.object(reuse, "get", return_value={"id": target, "systemData": {"createdAt": "2026-01-02T00:00:00Z"}}), patch.object(reuse, "cli") as cli:
            with self.assertRaisesRegex(reuse.ReuseError, "CLEANUP_RESOURCE_REPLACED"):
                reuse.cleanup(self.config, self.manifest(), created)
            cli.assert_not_called()

    def test_stage_selects_ci_entrypoint_without_modifying_normal_template(self):
        original = (TEMPLATE / "infra/main.bicep").read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            shutil.copytree(TEMPLATE, project)
            with patch.object(reuse, "check", return_value=reuse.validate(self.config, self.data)):
                params = reuse.prepare(project, self.config)
            self.assertEqual(params["cosmosDatabaseName"], "standing-db")
            self.assertEqual((project / "infra/main.bicep").read_bytes(), (TEMPLATE / "infra/ci-reuse.bicep").read_bytes())
            self.assertEqual(reuse.load(project / "ci-reuse.json"), self.config)
            yaml = (project / "azure.yaml").read_text()
            self.assertIn("registry: ciregistry.azurecr.io", yaml)
            self.assertIn("image: ci-smoke-mcp-jobs-abcdef12", yaml)
            self.assertIn("tag: run", yaml)
            for name in (".dockerignore", ".azdignore"):
                exclusion = (project / name).read_text()
                self.assertTrue(exclusion.startswith("**\n"))
                self.assertNotIn("ci-reuse.json", exclusion)
                self.assertNotIn(".azure", exclusion)
                self.assertNotIn("ci-preflight", exclusion)
            azd = {"AZURE_SUBSCRIPTION_ID": self.config["subscription"], "AZURE_TENANT_ID": self.config["tenant"],
                   "AZURE_RESOURCE_GROUP": "ci-example", "ACR_LOGIN_SERVER": self.config["registry_host"],
                   "MCP_ACA_JOBS_COSMOS_DATABASE": self.config["database"],
                   "MCP_ACA_JOBS_COSMOS_ENDPOINT": self.config["cosmos_endpoint"],
                   "MCP_ACA_JOBS_STORAGE_ACCOUNT_URL": self.config["storage_endpoint"]}
            with patch.object(reuse.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(azd))):
                reuse.check_staged_target(project, self.config)
            azd["AZURE_RESOURCE_GROUP"] = "wrong-group"
            with patch.object(reuse.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(azd))):
                with self.assertRaisesRegex(reuse.ReuseError, "AZD_TARGET_DRIFT"):
                    reuse.check_staged_target(project, self.config)
            with self.assertRaises(FileExistsError), patch.object(reuse, "check", return_value=reuse.validate(self.config, self.data)):
                reuse.prepare(project, self.config)
        self.assertEqual((TEMPLATE / "infra/main.bicep").read_bytes(), original)

    def test_ci_graph_composes_canonical_modules_without_shared_writes(self):
        text = (TEMPLATE / "infra/ci-reuse.bicep").read_text()
        self.assertIn("targetScope = 'resourceGroup'", text)
        self.assertIn("module app 'app.bicep'", text)
        self.assertIn("module control 'cosmos.bicep'", text)
        self.assertIn("module job '../../../azd-patterns/references/bicep/aca-job.bicep'", text)
        self.assertIn("useExistingDatabase: true", text)
        for forbidden in ("Microsoft.Authorization/", "Microsoft.ManagedIdentity/", "Microsoft.Resources/resourceGroups"):
            self.assertNotIn(forbidden, text)
        self.assertIn("param useExistingDatabase bool = false", (TEMPLATE / "infra/cosmos.bicep").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "compiled.json"
            result = subprocess.run(["az", "bicep", "build", "--file", str(TEMPLATE / "infra/ci-reuse.bicep"),
                                     "--outfile", str(output)], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            compiled = json.loads(output.read_text())
            resources = compiled["resources"]
            resources = list(resources.values()) if isinstance(resources, dict) else resources
            self.assertFalse(any(r["type"] in ("Microsoft.Authorization/roleAssignments",
                "Microsoft.Authorization/roleDefinitions", "Microsoft.ManagedIdentity/userAssignedIdentities",
                "Microsoft.Resources/resourceGroups") for r in resources))
            control = next(r for r in resources if r["type"] == "Microsoft.Resources/deployments"
                           and "ci-control-" in r["name"])
            self.assertIs(control["properties"]["parameters"]["useExistingDatabase"]["value"], True)
            inner = control["properties"]["template"]["resources"]
            inner = list(inner.values()) if isinstance(inner, dict) else inner
            database = next(r for r in inner if r["type"].endswith("/sqlDatabases")
                            and "useExistingDatabase" in r.get("condition", ""))
            self.assertIn("not(parameters('useExistingDatabase'))", database["condition"])
            container = next(r for r in inner if r["type"].endswith("/containers") and "useExistingAccount" in r.get("condition", ""))
            self.assertNotIn("dependsOn", container["properties"]["resource"])

    def test_cleanup_only_deletes_registered_objects_and_verifies_absence(self):
        state = {}
        created = {}
        for key, (rid, _) in reuse.owned(self.config).items():
            created[key] = {"id": rid, "created_at": "2026-01-01T01:00:00Z"}
            state[rid] = {"id": rid, "systemData": {"createdAt": created[key]["created_at"]}}
            if key in ("app", "job"):
                identity = self.config["app_identity" if key == "app" else "worker_identity"]
                state[rid].update(identity={"userAssignedIdentities": {identity: {}}},
                                  properties={"environmentId": self.config["environment"]})
        calls = []
        def get(config, resource_id, version, **kwargs):
            return state.get(resource_id)
        def cli(config, args, **kwargs):
            calls.append(args)
            url = args[args.index("--url") + 1]
            resource_id = url.removeprefix("https://management.azure.com").split("?")[0]
            del state[resource_id]
        with patch.object(reuse, "get", side_effect=get), patch.object(reuse, "cli", side_effect=cli):
            reuse.cleanup(self.config, self.manifest(), created)
        self.assertEqual(len(calls), 5)
        self.assertFalse(state)
        self.assertTrue(all(args[:3] == ["rest", "--method", "delete"] for args in calls))

    def test_image_cleanup_rejects_shared_repo_or_changed_manifest(self):
        with patch.object(reuse, "cli") as cli:
            with self.assertRaises(reuse.ReuseError):
                reuse.cleanup_image(self.config, {"repository": "shared", "digest": "sha256:" + "a" * 64})
            cli.assert_not_called()
        receipt = {"repository": reuse.image_repository(self.config), "digest": "sha256:" + "a" * 64}
        with patch.object(reuse, "image_metadata", return_value={"digest": receipt["digest"], "tags": ["run", "retained"]}), patch.object(reuse, "cli") as cli:
            with self.assertRaises(reuse.ReuseError):
                reuse.cleanup_image(self.config, receipt)
            cli.assert_not_called()

    def test_fixture_invoke_does_not_replay_after_malformed_accepted_response(self):
        calls = []
        def respond(request):
            calls.append(request.method)
            return httpx.Response(200, content=b'{"id":', headers={"x-request-id": "request-one"})
        with tempfile.TemporaryDirectory() as tmp, chdir(tmp):
            with httpx.Client(transport=httpx.MockTransport(respond)) as http:
                client = OpenAI(api_key="offline-only", base_url="https://example.test/v1", http_client=http)
                with self.assertRaisesRegex(reuse.ReuseError, "INVOKE_OUTCOME_UNKNOWN_NO_REPLAY"):
                    reuse.invoke_once(client, "hosted", {"input": "save"})
                with self.assertRaises(FileExistsError):
                    reuse.invoke_once(client, "hosted", {"input": "save"})
            self.assertEqual(calls, ["POST"])
            records = [json.loads(line) for line in Path("ci-hosted-operation.jsonl").read_text().splitlines()]
            self.assertEqual(records[-1]["classification"], "UNCERTAIN_EFFECT")
            self.assertTrue(any(r.get("request_id") == "request-one" for r in records))

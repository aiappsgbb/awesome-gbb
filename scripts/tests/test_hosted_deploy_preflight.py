"""Offline regressions for the hosted prerequisite and execution evidence gates."""

from __future__ import annotations

import copy
import ast
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/foundry-hosted-agents"
HELPER = SKILL / "references/python/deploy_preflight.py"
NOW = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)
ACCOUNT = "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>"
PROJECT = ACCOUNT + "/projects/<project>"
MODEL = ACCOUNT + "/deployments/<model>"
REGISTRY = "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.ContainerRegistry/registries/<registry>"
IMAGE = "registry.azurecr.io/agent@sha256:" + "a" * 64
CONNECTIONS = ("threadStorageConnections", "vectorStoreConnections", "storageConnections", "aiServicesConnections")


def resource(resource_id, **properties):
    return {"id": resource_id, "properties": {"provisioningState": "Succeeded", **properties}}


def receipt(**values):
    return {"result": "pass", "evidence": "private-observation.log", **values}


def evidence():
    return {
        "schema_version": 1,
        "observed_at": NOW.isoformat(),
        "target": {
            "mode": "basic-private", "account_id": ACCOUNT, "project_id": PROJECT,
            "model_id": MODEL, "registry_id": REGISTRY, "image": IMAGE,
            "subnet_id": "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<agents>",
            "project_endpoint": "https://account.services.ai.azure.com/api/projects/project",
            "operator_route": "approved-operator-proxy", "runtime_route": "approved-injected-route",
            "tool_endpoints": ["https://tool.internal/mcp"], "connections": {},
            "registry_network": "private", "model_env": "MODEL_DEPLOYMENT_NAME",
        },
        "account": {
            **resource(ACCOUNT, publicNetworkAccess="Disabled", networkInjections=[{
                "scenario": "agent",
                "subnetArmId": "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<agents>",
                "useMicrosoftManagedNetwork": False,
            }]),
            "kind": "AIServices",
        },
        "project": {
            **resource(PROJECT, endpoints={"AI Foundry API": "https://account.services.ai.azure.com/api/projects/project"}),
            "identity": {"principalId": "<project-mi>"},
            "systemData": {"createdAt": "2026-09-10T00:00:00Z"},
        },
        "model": resource(MODEL),
        "account_hosts": {"value": []},
        "project_hosts": {"value": [resource(PROJECT + "/capabilityHosts/basic", capabilityHostKind="Agents")]},
        "registry": resource(
            REGISTRY, loginServer="registry.azurecr.io", publicNetworkAccess="Disabled",
            roleAssignmentMode="AbacRepositoryPermissions",
            policies={"azureADAuthenticationAsArmPolicy": {"status": "enabled"}},
        ),
        "pull": receipt(
            principal_id="<project-mi>", scope=REGISTRY, role="Container Registry Repository Reader",
            repository="agent", condition_allows_repository=True,
        ),
        "probes": [
            receipt(purpose="operator-project", target="https://account.services.ai.azure.com/api/projects/project",
                    route="approved-operator-proxy", authenticated=True, tls_verified=True),
            receipt(purpose="runtime-model", target=MODEL, route="approved-injected-route",
                    authenticated=True, tls_verified=True),
            receipt(purpose="runtime-tool", target="https://tool.internal/mcp", route="approved-injected-route",
                    authenticated=True, tls_verified=True),
            receipt(purpose="registry-network", target=IMAGE, route="approved-injected-route",
                    network_reachable=True, tls_verified=True),
        ],
        "runtime": receipt(
            image=IMAGE, platform="linux/amd64", container_user="", session_home="/home/session",
            session_home_writable=True, protocol="responses", protocol_version="2.0.0",
            cohort_reference="references/python/pyproject.toml",
            cohort_verified=True, management_environment_separate=True,
            session_home_check="local-candidate",
        ),
        "registration": {
            "path": "sdk", "metadata": {"enableVnextExperience": "true"},
            "evidence": "frozen-create-request.json",
        },
        "environment_variables": {"MODEL_DEPLOYMENT_NAME": "<model>"},
    }


class HostedPreflightTests(unittest.TestCase):
    def load_helper(self):
        self.assertTrue(HELPER.is_file(), "missing executable hosted deployment preflight")
        spec = importlib.util.spec_from_file_location("hosted_deploy_preflight", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def check(self, data):
        return self.load_helper().check_setup(data, now=NOW)

    def blocked(self, data, code):
        result = self.check(data)
        self.assertEqual(result["status"], "BLOCKED", result)
        self.assertIn(code, [item["code"] for item in result["issues"]], result)
        self.assertTrue(all(item["scope"] and item["action"] for item in result["issues"]))
        return result

    def test_valid_basic_needs_only_project_host_and_is_not_live_proof(self):
        data = evidence()
        original = copy.deepcopy(data)
        result = self.check(data)
        self.assertEqual(result["status"], "READY_FOR_REGISTRATION", result)
        self.assertEqual(result["live_execution"], "NOT_TESTED")
        self.assertIn("native-session-home", result["pending_live_checks"])
        self.assertIn("project-mi-platform-pull", result["pending_live_checks"])
        self.assertEqual(data, original)

    def test_missing_basic_project_host_fails_despite_account_success(self):
        data = evidence()
        data["project_hosts"]["value"] = []
        result = self.blocked(data, "PROJECT_HOST_MISSING")
        issue = next(i for i in result["issues"] if i["code"] == "PROJECT_HOST_MISSING")
        self.assertEqual(issue["scope"], PROJECT + "/capabilityHosts")
        self.assertIn("add-project-capability-host.bicep", issue["action"])
        self.assertIn("authorization", issue["action"])

    def test_failed_wrong_scope_kind_or_duplicate_host_is_not_repaired(self):
        for change in ("failed", "scope", "kind", "duplicate"):
            with self.subTest(change=change):
                data = evidence()
                host = data["project_hosts"]["value"][0]
                if change == "failed":
                    host["properties"]["provisioningState"] = "Failed"
                elif change == "scope":
                    host["id"] = ACCOUNT + "/capabilityHosts/basic"
                elif change == "kind":
                    host["properties"]["capabilityHostKind"] = "Unknown"
                else:
                    data["project_hosts"]["value"].append(copy.deepcopy(host))
                before = copy.deepcopy(data)
                self.blocked(data, "PROJECT_HOST_INVALID")
                self.assertEqual(data, before)

    def test_basic_does_not_silently_reuse_byo_host(self):
        for key in CONNECTIONS:
            with self.subTest(key=key):
                data = evidence()
                data["project_hosts"]["value"][0]["properties"][key] = ["existing-store"]
                self.blocked(data, "HOST_CONNECTIONS")

    def test_standard_checks_account_host_and_exact_byo_connections(self):
        data = evidence()
        data["target"]["mode"] = "standard-private"
        connections = {key: ["existing-" + key] for key in CONNECTIONS}
        data["target"]["connections"] = connections
        data["project_hosts"]["value"][0]["properties"].update(connections)
        self.blocked(data, "ACCOUNT_HOST_MISSING")
        data["account_hosts"]["value"] = [resource(
            ACCOUNT + "/capabilityHosts/account", capabilityHostKind="Agents",
            customerSubnet=data["target"]["subnet_id"],
        )]
        self.assertEqual(self.check(data)["status"], "READY_FOR_REGISTRATION")
        data["project_hosts"]["value"][0]["properties"]["storageConnections"] = ["different"]
        self.blocked(data, "HOST_CONNECTIONS")

    def test_public_managed_mode_does_not_require_manual_hosts(self):
        data = evidence()
        data["target"]["mode"] = "managed-public"
        data["account"]["properties"]["publicNetworkAccess"] = "Enabled"
        data["account"]["properties"]["networkInjections"] = []
        data["registry"]["properties"]["publicNetworkAccess"] = "Enabled"
        data["target"]["registry_network"] = "public"
        data["project_hosts"]["value"] = []
        self.assertEqual(self.check(data)["status"], "READY_FOR_REGISTRATION")
        data["account"]["properties"]["publicNetworkAccess"] = "Disabled"
        self.blocked(data, "NETWORK_MODE")

    def test_read_error_or_partial_list_is_not_missing_host(self):
        for body in ({}, {"error": {"code": "Forbidden"}}, {"value": [], "nextLink": "next"}):
            data = evidence()
            data["project_hosts"] = body
            self.blocked(data, "HOST_INVENTORY")

    def test_project_and_model_must_match_target_and_be_ready(self):
        for key in ("project", "model"):
            with self.subTest(key=key):
                data = evidence()
                data[key]["properties"]["provisioningState"] = "Accepted"
                self.blocked(data, "RESOURCE_STATE")
                data = evidence()
                data[key]["id"] += "-wrong"
                self.blocked(data, "RESOURCE_SCOPE")

    def test_project_endpoint_must_come_from_selected_project(self):
        data = evidence()
        data["target"]["project_endpoint"] = "https://other.services.ai.azure.com/api/projects/other"
        data["probes"][0]["target"] = data["target"]["project_endpoint"]
        self.blocked(data, "PROJECT_ENDPOINT")

    def test_private_registry_creation_date_boundary_fails_closed(self):
        for date in ("2026-06-24T23:59:59Z", "2026-06-25T12:00:00Z", None, "bad"):
            with self.subTest(date=date):
                data = evidence()
                data["project"]["systemData"]["createdAt"] = date
                self.blocked(data, "PRIVATE_ACR_GENERATION")
        data = evidence()
        data["project"]["systemData"]["createdAt"] = "2026-06-26T00:00:00Z"
        self.assertEqual(self.check(data)["status"], "READY_FOR_REGISTRATION")

    def test_pull_role_must_match_registry_mode_identity_scope_repository(self):
        for field, value in (
            ("principal_id", "<agent-mi>"), ("scope", ACCOUNT), ("repository", "other"),
            ("role", "AcrPull"), ("condition_allows_repository", False),
        ):
            with self.subTest(field=field):
                data = evidence()
                data["pull"][field] = value
                self.blocked(data, "ACR_PULL")
        data = evidence()
        data["registry"]["properties"]["roleAssignmentMode"] = "LegacyRegistryPermissions"
        data["pull"]["role"] = "AcrPull"
        self.assertEqual(self.check(data)["status"], "READY_FOR_REGISTRATION")

    def test_registry_policy_must_be_enabled(self):
        data = evidence()
        data["registry"]["properties"]["policies"]["azureADAuthenticationAsArmPolicy"]["status"] = "disabled"
        self.blocked(data, "ACR_POLICY")

    def test_private_registry_cannot_be_exposed_to_pass_preflight(self):
        data = evidence()
        data["registry"]["properties"]["publicNetworkAccess"] = "Enabled"
        self.blocked(data, "ACR_NETWORK")

    def test_runtime_model_name_must_match_selected_deployment(self):
        data = evidence()
        data["environment_variables"]["MODEL_DEPLOYMENT_NAME"] = "wrong-model"
        self.blocked(data, "MODEL_BINDING")

    def test_operator_probe_does_not_certify_runtime_route(self):
        for change in ("missing", "route", "auth", "tls", "target"):
            with self.subTest(change=change):
                data = evidence()
                probe = data["probes"][2]
                if change == "missing":
                    data["probes"].pop(2)
                elif change == "route":
                    probe["route"] = "laptop"
                elif change == "auth":
                    probe["authenticated"] = False
                elif change == "tls":
                    probe["tls_verified"] = False
                else:
                    probe["target"] = "https://wrong.internal/mcp"
                self.blocked(data, "PATH_UNVERIFIED")

    def test_runtime_rejects_wrong_image_uid_home_protocol_or_cohort(self):
        for field, value in (
            ("image", IMAGE + "bad"), ("platform", "linux/arm64"), ("container_user", "65532"),
            ("session_home_writable", False), ("protocol_version", "1.0.0"),
            ("cohort_verified", False), ("management_environment_separate", False),
        ):
            with self.subTest(field=field):
                data = evidence()
                data["runtime"][field] = value
                self.blocked(data, "RUNTIME")

    def test_reserved_env_values_are_not_echoed(self):
        for key in ("FOUNDRY_PROJECT_ENDPOINT", "AGENT_NAME", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
            data = evidence()
            data["environment_variables"][key] = "secret-value-never-print"
            result = self.blocked(data, "RESERVED_ENV")
            self.assertNotIn("secret-value-never-print", json.dumps(result))

    def test_stale_future_missing_or_malformed_evidence_is_blocked(self):
        for timestamp in ("2026-09-11T20:00:00Z", "2026-09-13T20:00:00Z", "bad", None):
            data = evidence()
            data["observed_at"] = timestamp
            self.blocked(data, "EVIDENCE_AGE")
        for data in (None, [], {}, {"schema_version": 1}):
            self.assertEqual(self.check(data)["status"], "BLOCKED")

    def test_image_must_be_immutable(self):
        data = evidence()
        data["target"]["image"] = "registry.azurecr.io/agent:latest"
        self.blocked(data, "IMAGE")

    def test_direct_sdk_creation_metadata_must_match_native_path(self):
        for value in ({}, {"enableVnextExperience": True}, {"enableVnextExperience": "false"}):
            data = evidence()
            data["registration"]["metadata"] = value
            self.blocked(data, "REGISTRATION")

    def test_invalid_nested_types_fail_closed_without_traceback(self):
        for path, value in (
            (("target", "mode"), []),
            (("registry", "properties", "roleAssignmentMode"), {}),
            (("target", "connections", "storageConnections"), ""),
            (("account", "properties", "networkInjections"), {}),
        ):
            with self.subTest(path=path):
                data = evidence()
                parent = data
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                self.assertEqual(self.check(data)["status"], "BLOCKED")

    def test_cli_returns_structured_failure_not_traceback(self):
        self.load_helper()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            run = subprocess.run([sys.executable, str(HELPER), str(path)],
                                 capture_output=True, text=True, check=False)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)["status"], "BLOCKED")
        self.assertNotIn("Traceback", run.stderr)

    def test_authoritative_execution_requires_direct_gets_and_real_receipt(self):
        helper = self.load_helper()
        observation = {
            "source": "direct-version-get", "version": "3", "status": "active",
            "image": IMAGE, "identity": "<actual-agent>", "observed_at": "2026-09-12T19:59:00Z",
        }
        deployment = {
            "observed_at": NOW.isoformat(),
            "version": "3", "image": IMAGE, "identity": "<actual-agent>",
            "observations": [observation, {**observation, "observed_at": "2026-09-12T20:00:00Z"}],
            "endpoint": receipt(version="3", image=IMAGE, identity="<actual-agent>"),
            "invocation": receipt(version="3", image=IMAGE, identity="<actual-agent>",
                                  response_id="<response>", session_id="<session>"),
            "business": receipt(response_id="<response>", tool_call_id="<call>",
                                audit_id="<audit>", requested_result_verified=True),
            "hosted_runtime": receipt(version="3", image=IMAGE, identity="<actual-agent>",
                                      session_id="<session>", native_session_home_writable=True),
        }
        result = helper.check_execution(deployment, now=NOW)
        self.assertEqual(result["status"], "BUSINESS_PROOF_RECORDED", result)
        for change in ("list", "failed", "single", "stale", "image", "receipt", "empty", "home", "age", "mutable"):
            with self.subTest(change=change):
                data = copy.deepcopy(deployment)
                if change == "list":
                    data["observations"][-1]["source"] = "list-versions"
                elif change == "failed":
                    data["observations"][-1]["status"] = "failed"
                elif change == "single":
                    data["observations"].pop()
                elif change == "stale":
                    data["observations"][-1]["observed_at"] = "2026-09-10T20:00:00Z"
                elif change == "image":
                    data["endpoint"]["image"] = "other"
                elif change == "receipt":
                    data["business"]["response_id"] = "other"
                elif change == "home":
                    data["hosted_runtime"]["native_session_home_writable"] = False
                elif change == "age":
                    data["observed_at"] = "2026-09-10T20:00:00Z"
                elif change == "mutable":
                    data["image"] = "registry.azurecr.io/agent:latest"
                    for item in [*data["observations"], data["endpoint"], data["invocation"], data["hosted_runtime"]]:
                        item["image"] = data["image"]
                else:
                    data["business"] = {}
                self.assertEqual(helper.check_execution(data, now=NOW)["status"], "BLOCKED")

    def test_rollout_emits_required_native_creation_metadata(self):
        source = (SKILL / "references/python/version_rollout.py").read_text()
        tree = ast.parse(source)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create_new_version")
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function],
                            type_ignores=[])
        ast.fix_missing_locations(module)

        class Clock:
            @staticmethod
            def time():
                return 123

        class Protocol:
            RESPONSES = "responses"

        class Version(dict):
            version = "3"

        class Project:
            def __init__(self):
                self.agents = self
                self.kwargs = None

            def create_version(self, **kwargs):
                self.kwargs = kwargs
                return Version(status="creating")

        namespace = {
            "time": Clock, "_env": lambda name: "<model>", "RESPONSES_PROTOCOL_VERSION": "2.0.0",
            "AgentEndpointProtocol": Protocol, "HostedAgentDefinition": lambda **kw: kw,
            "ContainerConfiguration": lambda **kw: kw, "ProtocolVersionRecord": lambda **kw: kw,
        }
        exec(compile(module, "<creation-function>", "exec"), namespace)
        project = Project()
        namespace["create_new_version"](project, "agent", IMAGE)
        self.assertEqual(project.kwargs.get("metadata"), {"enableVnextExperience": "true"})

    def test_rollout_wait_uses_two_direct_gets_and_failure_wins(self):
        # Isolate the polling function without importing Azure or running main.
        source = (SKILL / "references/python/version_rollout.py").read_text()
        tree = ast.parse(source)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "wait_for_active")
        module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function],
                            type_ignores=[])
        ast.fix_missing_locations(module)

        class Clock:
            @staticmethod
            def sleep(seconds):
                pass

        namespace = {"time": Clock}
        exec(compile(module, "<polling-function>", "exec"), namespace)

        class Project:
            def __init__(self, values):
                self.values = iter(values)
                self.agents = self
                self.calls = 0

            def get_version(self, **kwargs):
                self.calls += 1
                return next(self.values)

        active = {"status": "active"}
        project = Project([active, active])
        namespace["wait_for_active"](project, "agent", "3", sleep_seconds=0)
        self.assertEqual(project.calls, 2)
        for bad in ({"status": "failed"}, {"status": "active", "error": {"code": "ProvisioningError"}}):
            project = Project([active, bad])
            with self.assertRaises(RuntimeError):
                namespace["wait_for_active"](project, "agent", "3", max_attempts=2, sleep_seconds=0)


class HostedGuidanceContractTests(unittest.TestCase):
    def test_no_unscoped_capability_host_prohibition(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertNotIn("Do NOT create CapabilityHosts — platform manages infrastructure automatically", text)
        self.assertNotIn("ENABLE_CAPABILITY_HOST=false` — NO CapabilityHost creation", text)
        self.assertIn("Deployment preflight", text)

    def test_private_acr_rule_is_dated_not_blanket_public(self):
        text = (ROOT / "skills/foundry-vnet-deploy/references/agent-tools-network-isolation.md").read_text()
        self.assertNotIn("Hosted agents need a *public* Azure Container Registry", text)
        self.assertIn("June 25, 2026", text)
        self.assertIn("2026-09-12", text)

    def test_verification_is_read_only_and_selects_real_host_name(self):
        text = (ROOT / "skills/foundry-vnet-deploy/SKILL.md").read_text()
        section = text.split("### 11.4 — Capability Hosts", 1)[1].split("### 11.5", 1)[0]
        self.assertNotIn("--method PUT", section)
        self.assertNotIn("/capabilityHosts/caphost?", section)
        self.assertIn("basic-vnet", section)

    def test_all_owners_link_one_preflight_contract(self):
        for name in ("foundry-hosted-agents", "foundry-vnet-deploy", "foundry-caphost-lifecycle"):
            with self.subTest(name=name):
                text = (ROOT / "skills" / name / "SKILL.md").read_text()
                self.assertIn("deployment-preflight.md", text)

    def test_brownfield_fixture_has_private_preflight_gate(self):
        text = (SKILL / "test-fixture/consumer_prompt.md").read_text()
        self.assertIn("deploy_preflight.py", text)
        self.assertIn("two consecutive", text)


if __name__ == "__main__":
    unittest.main()

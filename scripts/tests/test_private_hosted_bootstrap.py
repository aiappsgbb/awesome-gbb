"""Offline #499 regressions. Native SDK models are required, never substituted."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx
import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import AgentSessionResource
from azure.core.credentials import AccessToken
from azure.core.pipeline.transport import HttpResponse, HttpTransport
from openai import PermissionDeniedError
from openai.types.responses import Response
from scripts.tests.test_hosted_deploy_preflight import evidence as setup_evidence

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills/foundry-hosted-agents/references"
sys.path.insert(0, str(REFS / "python"))
IMAGE = "registry.azurecr.io/basic@sha256:" + "a" * 64


def response_body():
    return {
        "id": "response-one", "object": "response", "created_at": 1,
        "status": "completed", "error": None, "incomplete_details": None,
        "model": "", "usage": None, "parallel_tool_calls": False,
        "tool_choice": "auto", "tools": [], "temperature": 1, "top_p": 1,
        "agent_session_id": "session-one",
        "agent_reference": {"name": "basic-agent", "version": "7"},
        "output": [{"id": "message-one", "type": "message", "role": "assistant",
                    "status": "completed", "content": [
                        {"type": "output_text", "text": "Billing Issue", "annotations": []}]}],
    }


def session_body():
    return {"agent_session_id": "session-one", "status": "active",
            "version_indicator": {"type": "version_ref", "agent_version": "7"},
            "created_at": 1, "last_accessed_at": 2, "expires_at": 9999999999}


class PrivateBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tuple(int(n) for n in version("azure-ai-projects").split(".")[:2]) < (2, 3):
            raise AssertionError("native SDK >=2.3 required; no substitute wire models")

    def helper(self):
        return importlib.import_module("private_bootstrap")

    def test_no_tools_runtime_and_explicit_container_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "consumer"
            self.helper().prepare(root, "basic-agent", "local")
            config = yaml.safe_load((root / "azure.yaml").read_text())
            agent = config["services"]["basic-agent"]
            self.assertEqual(agent["language"], "docker")
            self.assertNotIn("codeConfiguration", agent)
            self.assertFalse(agent["docker"]["remoteBuild"])
            self.assertEqual(agent["project"], "app")
            source = (root / "app/main.py").read_text()
            self.assertNotIn("tools=", source)
            self.assertNotIn("SkillsProvider", source)
            self.assertNotIn("load_dotenv", source)
            self.assertIn('default_options={"store": False}', source)
            dockerfile = (root / "app/Dockerfile").read_text()
            self.assertIn("--locked", dockerfile)
            self.assertNotIn("USER ", dockerfile)

    def test_prebuilt_uses_service_level_digest_without_publisher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "consumer"
            self.helper().prepare(root, "basic-agent", "prebuilt", IMAGE)
            agent = yaml.safe_load((root / "azure.yaml").read_text())["services"]["basic-agent"]
            self.assertEqual(agent["image"], IMAGE)
            self.assertTrue(agent["docker"]["imagePassthrough"])
            self.assertFalse(agent["docker"]["remoteBuild"])
            self.assertNotIn("image", {k: v for k, v in agent["docker"].items() if k != "imagePassthrough"})

    def test_private_prebuilt_procedure_explicitly_skips_package_and_publish(self):
        procedure = (REFS / "private-basic.md").read_text()
        command = 'azd deploy "$AGENT" --from-package "$IMAGE" --no-prompt'
        self.assertIn(command, procedure)
        self.assertNotIn('azd deploy "$AGENT" --no-prompt', procedure)
        self.assertNotIn("Do not use `--from-package` with a digest", procedure)
        self.assertIn("not rely on YAML passthrough alone", procedure)
        self.assertIn("azd 1.27.0 is not", procedure)
        self.assertIn("flag availability alone is **not** a zero-publish guarantee", procedure)
        self.assertIn("azd 1.34.1 +", procedure)
        self.assertIn("azure.ai.agents 1.0.0-beta.14", procedure)
        self.assertIn("not a minimum-version claim", procedure)
        self.assertIn("`requiredAzdVersion` = `>=1.32.0`", procedure)
        self.assertIn("imagePassthroughPackageOverride", procedure)
        self.assertIn("not live deployment or", procedure)
        template = (REFS / "yaml/azure.yaml").read_text()
        self.assertNotIn("never feed a digest to --from-package", template)
        self.assertIn("version-gated deploy --from-package", template)
        self.assertIn("distinct from publish --from-package", template)
        self.assertIn("functional success and cleanup/custody reported separately", procedure)

    def test_reject_mutable_prebuilt_or_conflicting_build_choices(self):
        for build, image in (("prebuilt", None), ("prebuilt", "registry.azurecr.io/basic:latest"),
                             ("local", IMAGE), ("code", None)):
            with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
                self.helper().prepare(Path(tmp) / "consumer", "basic-agent", build, image)

    def test_existing_workdir_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileExistsError):
            self.helper().prepare(Path(tmp), "basic-agent", "local")

    def test_upload_context_is_allowlisted_and_lock_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "consumer"
            self.helper().prepare(root, "basic-agent", "local")
            for filename in (".dockerignore", ".azdignore"):
                lines = (root / "app" / filename).read_text().splitlines()
                self.assertEqual(lines[0], "**")
                self.assertEqual(set(lines[1:]), {"!main.py", "!pyproject.toml", "!uv.lock", "!Dockerfile"})
            with self.assertRaisesRegex(ValueError, "uv.lock"):
                self.helper().source_inventory(root)
            (root / "app/uv.lock").write_text("version = 1\n")
            (root / "app/.env").write_text("DO_NOT_UPLOAD=secret")
            inventory = self.helper().source_inventory(root)
            self.assertNotIn(".env", inventory)
            self.assertEqual(len(inventory["main.py"]), 64)
            (root / "app/.dockerignore").write_text("!**\n")
            with self.assertRaisesRegex(ValueError, "exclusions"):
                self.helper().source_inventory(root)

    def test_manifest_digest_and_full_descriptors_not_format_assumptions(self):
        for media_type in ("application/vnd.oci.image.manifest.v1+json",
                           "application/vnd.docker.distribution.manifest.v2+json"):
            body = {"schemaVersion": 2, "mediaType": media_type,
                    "config": {"digest": "sha256:" + "c" * 64, "size": 123, "mediaType": "config"},
                    "layers": [{"digest": "sha256:" + "d" * 64, "size": 456, "mediaType": "layer"}]}
            raw = json.dumps(body).encode()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            result = self.helper().manifest_inventory(raw, digest)
            self.assertEqual(result["config"], body["config"])
            self.assertEqual(result["layers"], body["layers"])
            with self.assertRaises(ValueError):
                self.helper().manifest_inventory(raw + b"\n", digest)

    def test_effective_build_plan_rejects_mutable_bases_and_code_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "consumer"
            self.helper().prepare(root, "basic-agent", "local")
            (root / "app/uv.lock").write_text("version = 1\n")
            with patch.dict(os.environ, {"PYTHON_IMAGE": IMAGE, "UV_IMAGE": IMAGE}):
                result = self.helper().validate_build(root, "basic-agent")
                self.assertEqual(result["path"], "local")
                self.assertEqual(result["base_images"]["PYTHON_IMAGE"], IMAGE)
            with patch.dict(os.environ, {"PYTHON_IMAGE": "python:3.12-slim", "UV_IMAGE": IMAGE}):
                with self.assertRaisesRegex(ValueError, "immutable"):
                    self.helper().validate_build(root, "basic-agent")
            config = yaml.safe_load((root / "azure.yaml").read_text())
            config["services"]["basic-agent"]["codeConfiguration"] = {"runtime": "python_3_13"}
            (root / "azure.yaml").write_text(yaml.safe_dump(config))
            with self.assertRaisesRegex(ValueError, "container"):
                self.helper().validate_build(root, "basic-agent")


class NativeModelOracleTests(unittest.TestCase):
    def helper(self):
        return importlib.import_module("hosted_smoke")

    def check(self, first=None, second=None, session=None):
        first = response_body() if first is None else first
        second = copy.deepcopy(first) if second is None else second
        return self.helper().verify_model_readback(
            Response.model_validate(first), Response.model_validate(second),
            AgentSessionResource(session_body() if session is None else session),
            agent_name="basic-agent", agent_version="7",
        )

    def test_completed_model_readback_ignores_optional_phase_not_identity(self):
        first = response_body()
        second = copy.deepcopy(first)
        second["output"][0]["phase"] = None
        self.assertEqual(self.check(first, second)["response_id"], "response-one")

    def test_response_wording_is_not_a_health_oracle(self):
        for text in ("billing", "Billing Issue", "Hello. Here is a short answer."):
            body = response_body()
            body["output"][0]["content"][0]["text"] = text
            self.check(body)

    def test_empty_error_incomplete_and_tool_results_are_not_basic_model_proof(self):
        for key, value in (("status", "failed"), ("error", {"code": "server_error", "message": "failed"}),
                           ("output", []), ("output", [{"type": "function_call", "id": "fc",
                                                        "call_id": "call", "name": "noop", "arguments": "{}"}])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                body = response_body()
                body[key] = value
                self.check(body)

    def test_stable_readback_mismatches_block(self):
        for key, value in (("id", "other"), ("agent_session_id", "other"),
                           ("agent_reference", {"name": "other", "version": "7"}),
                           ("agent_reference", {"name": "basic-agent", "version": "8"})):
            second = response_body()
            second[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(second=second)
        second = response_body()
        second["output"][0]["content"][0]["text"] = "Different persisted result"
        with self.assertRaises(ValueError):
            self.check(second=second)

    def test_session_mismatch_or_failure_blocks(self):
        for key, value in (("agent_session_id", "other"), ("status", "failed"),
                           ("expires_at", 1),
                           ("version_indicator", {"type": "version_ref", "agent_version": "8"})):
            body = session_body()
            body[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check(session=body)


class JsonHttpResponse(HttpResponse):
    def __init__(self, request, body):
        super().__init__(request, None)
        self.status_code = 200
        self.headers = {"Content-Type": "application/json"}
        self._body = json.dumps(body).encode()
        self.content_type = "application/json"

    def body(self):
        return self._body

    def json(self):
        return json.loads(self._body)


class NativeTransport(HttpTransport):
    def __init__(self, agent_version, pending_first=False):
        self.agent_version = agent_version
        self.calls = []
        self.pending_first = pending_first

    def open(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def send(self, request, **kwargs):
        self.calls.append((request.method, request.url))
        if "/sessions/session-one" in request.url:
            return JsonHttpResponse(request, session_body())
        if "/versions/7" in request.url:
            if self.pending_first:
                self.pending_first = False
                return JsonHttpResponse(request, {
                    **self.agent_version, "status": "creating",
                    "instance_identity": None, "definition": None,
                })
            return JsonHttpResponse(request, self.agent_version)
        raise AssertionError("Unexpected native management request: " + request.url)


class OfflineCredential:
    def get_token(self, *args, **kwargs):
        return AccessToken("offline-test-token", 9999999999)


class NativeExecutionTests(unittest.TestCase):
    def setup(self):
        data = setup_evidence()
        data["observed_at"] = datetime.now(timezone.utc).isoformat()
        data["target"]["tool_endpoints"] = []
        data["account"]["properties"]["disableLocalAuth"] = True
        data["registry"]["properties"]["adminUserEnabled"] = False
        return data

    def run_native(self, *, denied=False, mutate=None, require_affinity=False, pending_first=False):
        helper = importlib.import_module("hosted_smoke")
        data = self.setup()
        native = {
            "id": "basic-agent:7", "name": "basic-agent", "version": "7",
            "object": "agent.version", "created_at": 1, "status": "active",
            "metadata": {"enableVnextExperience": "true"},
            "instance_identity": {"principal_id": "agent-principal", "client_id": "agent-client"},
            "definition": {"kind": "hosted", "cpu": "1", "memory": "2Gi",
                           "container_configuration": {"image": data["target"]["image"]},
                           "protocol_versions": [{"protocol": "responses", "version": "2.0.0"}],
                           "environment_variables": {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "<model>"}},
        }
        if mutate:
            mutate(native)
        transport = NativeTransport(native, pending_first=pending_first)
        calls = []

        def handle(request):
            calls.append((request.method, request.url.path, request.headers.get("x-agent-session-id")))
            if denied:
                return httpx.Response(403, json={"error": {"code": "Forbidden", "message": "Denied"}})
            body = response_body()
            if request.method == "GET":
                if require_affinity and request.headers.get("x-agent-session-id") != body["agent_session_id"]:
                    return httpx.Response(404, json={"error": {"code": "NotFound", "message": "Session affinity required"}})
                body["output"][0]["phase"] = None
            return httpx.Response(200, json=body)

        records = []
        with AIProjectClient(endpoint=data["target"]["project_endpoint"],
                             credential=OfflineCredential(), transport=transport,
                             retry_total=0) as project:
            native_openai = project.get_openai_client
            with httpx.Client(transport=httpx.MockTransport(handle)) as http_client:
                def openai(**kwargs):
                    return native_openai(http_client=http_client, **kwargs)
                with patch.object(project, "get_openai_client", side_effect=openai):
                    result = helper.execute(project, data, "basic-agent", "7",
                                            lambda stage, value: records.append((stage, value)),
                                            attempts=3 if pending_first else 2, sleep=lambda seconds: None)
        return result, transport.calls, calls, records

    def test_real_sdk_transport_executes_gets_one_invoke_and_independent_readbacks(self):
        result, management, responses, records = self.run_native()
        self.assertEqual(result["status"], "PRIVATE_BASIC_MODEL_PASS")
        self.assertEqual(result["business_execution"], "NOT_TESTED")
        self.assertEqual(len(management), 4)
        self.assertTrue(all(method == "GET" for method, _ in management))
        self.assertEqual([method for method, _, _ in responses], ["POST", "GET"])
        self.assertIn("/agents/basic-agent/endpoint/protocols/openai/responses", responses[0][1])
        self.assertTrue(responses[1][1].endswith("/responses/response-one"))
        self.assertEqual(sum(stage == "direct-version-get" for stage, _ in records), 2)

    def test_creating_without_future_identity_is_pending_not_terminal(self):
        result, management, responses, records = self.run_native(pending_first=True)
        self.assertEqual(result["status"], "PRIVATE_BASIC_MODEL_PASS")
        self.assertEqual([method for method, _, _ in responses], ["POST", "GET"])
        observed = [data for stage, data in records if stage == "direct-version-get"]
        self.assertEqual(observed[0]["classification"], "PENDING_OPERATION")
        self.assertEqual([data["status"] for data in observed], ["creating", "active", "active"])

    def test_native_retrieve_requires_observed_session_affinity_without_extra_post(self):
        result, _, responses, _ = self.run_native(require_affinity=True)
        self.assertEqual(result["status"], "PRIVATE_BASIC_MODEL_PASS")
        self.assertEqual([method for method, _, _ in responses], ["POST", "GET"])
        self.assertIsNone(responses[0][2], "Initial POST must not reuse a historical session")
        self.assertEqual(responses[1][2], "session-one")
        self.assertTrue(responses[1][1].endswith("/responses/response-one"))
        self.assertEqual(result["response_id"], "response-one")
        self.assertEqual(result["session_id"], "session-one")

    def test_permission_failure_is_not_retried_or_faked_as_pass(self):
        with self.assertRaises(PermissionDeniedError):
            self.run_native(denied=True)

    def test_native_version_mismatch_failure_and_missing_metadata_fail(self):
        mutations = [
            lambda v: v.update(status="failed"),
            lambda v: v.update(name="wrong-agent"),
            lambda v: v.update(metadata={}),
            lambda v: v["definition"]["container_configuration"].update(image=IMAGE),
            lambda v: v.update(instance_identity=None),
            lambda v: v.update(metadata=None),
            lambda v: v.update(definition=None),
            lambda v: v["definition"].update(container_configuration=None),
            lambda v: v["definition"].update(environment_variables=None),
            lambda v: v["definition"].update(protocol_versions=None),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.run_native(mutate=mutation)

    def test_private_freshness_keyless_and_no_tools_are_not_optional(self):
        helper = importlib.import_module("hosted_smoke")
        for mutate in (
            lambda d: d.update(observed_at="2000-01-01T00:00:00Z"),
            lambda d: d["registry"]["properties"].update(adminUserEnabled=True),
            lambda d: d["account"]["properties"].update(disableLocalAuth=False),
            lambda d: d["target"].update(tool_endpoints=["https://tool.internal/mcp"]),
            lambda d: d["account"]["properties"].update(publicNetworkAccess="Enabled"),
        ):
            data = self.setup()
            mutate(data)
            with self.assertRaises(ValueError):
                helper.private_setup(data)

    def test_context_checks_pair_and_each_exact_azd_value(self):
        helper = importlib.import_module("hosted_smoke")
        data = self.setup()
        data["target"]["tenant_id"] = "<tenant>"
        target = data["target"]
        with tempfile.TemporaryDirectory() as tmp:
            az = Path(tmp) / "az"
            azd = Path(tmp) / "azd"
            az.mkdir()
            azd.mkdir()
            env = {
                "AZURE_CONFIG_DIR": str(az), "AZD_CONFIG_DIR": str(azd),
                "AZURE_TENANT_ID": "<tenant>", "AZURE_SUBSCRIPTION_ID": "<sub>",
                "AZURE_AI_PROJECT_ID": target["project_id"],
                "FOUNDRY_PROJECT_ENDPOINT": target["project_endpoint"],
                "AZURE_CONTAINER_REGISTRY_ENDPOINT": "registry.azurecr.io",
                "AZURE_CONTAINER_REGISTRY_RESOURCE_ID": target["registry_id"],
                "AZURE_AI_MODEL_DEPLOYMENT_NAME": "<model>",
            }
            def run(argv, **kwargs):
                return type("CommandOutput", (), {"stdout": (
                    json.dumps({"id": "<sub>", "tenantId": "<tenant>"}) if argv[0] == "az"
                    else env[argv[-1]])})()
            with patch.dict(os.environ, env, clear=True), patch.object(helper.subprocess, "run", side_effect=run):
                helper.check_context(data)
                for key in ("AZURE_AI_PROJECT_ID", "AZURE_TENANT_ID", "FOUNDRY_PROJECT_ENDPOINT",
                            "AZURE_CONTAINER_REGISTRY_ENDPOINT", "AZURE_CONTAINER_REGISTRY_RESOURCE_ID"):
                    with patch.dict(os.environ, {key: "wrong"}), self.assertRaises(ValueError):
                        helper.check_context(data)
                with patch.dict(os.environ, {"AZD_CONFIG_DIR": str(az)}), self.assertRaises(ValueError):
                    helper.check_context(data)

    def test_live_entrypoint_requires_explicit_opt_in_without_azure_calls(self):
        helper = importlib.import_module("hosted_smoke")
        with tempfile.TemporaryDirectory() as tmp, patch.object(helper.subprocess, "run") as calls:
            with patch.object(sys, "argv", ["hosted_smoke.py", "--setup", "not-read.json",
                                          "--agent", "basic-agent", "--version", "7",
                                          "--evidence", str(Path(tmp) / "evidence")]):
                self.assertEqual(helper.main(), 1)
                calls.assert_not_called()

    def test_public_fixture_uses_shared_semantic_oracle_not_exact_labels(self):
        fixture = (REFS.parent / "test-fixture/consumer_prompt.md").read_text()
        self.assertIn("verify_model_readback(", fixture)
        self.assertIn('r"MODEL_COMPLETION_READBACK_OK"', fixture)
        self.assertNotIn("INVOKE_LABEL", fixture)
        self.assertNotIn("except Exception as exc:  # noqa: BLE001 - bounded cold-start retry", fixture)

    def test_public_fixture_retrieve_pins_observed_session_header(self):
        fixture = (REFS.parent / "test-fixture/consumer_prompt.md").read_text()
        self.assertIn('extra_headers={"x-agent-session-id": result["session_id"]}', fixture)


if __name__ == "__main__":
    unittest.main()

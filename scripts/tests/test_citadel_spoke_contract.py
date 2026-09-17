"""Offline native APIM transport and published spoke-contract regressions."""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from azure.core.credentials import AccessToken
from azure.core.pipeline.transport import HttpResponse, HttpTransport
from azure.mgmt.apimanagement import ApiManagementClient
import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/citadel-spoke-onboarding"
SPEC = importlib.util.spec_from_file_location(
    "citadel_probe_contract", SKILL / "references/python/access_contract_probe.py"
)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)
SERVICE = "/subscriptions/example-sub/resourceGroups/hub-rg/providers/Microsoft.ApiManagement/service/hub-apim"
API = SERVICE + "/apis/example-api"
PRODUCT = SERVICE + "/products/example-product"


class OfflineCredential:
    def get_token(self, *scopes, **kwargs):
        return AccessToken("offline-test-token", 4102444800)


class Response(HttpResponse):
    def __init__(self, request, status, body):
        super().__init__(request, None)
        self.status_code = status
        self.headers = {"content-type": "application/json"}
        self.reason = str(status)
        self.content_type = "application/json"
        self.payload = json.dumps(body).encode()

    def body(self):
        return self.payload


class Transport(HttpTransport):
    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def open(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def send(self, request, **kwargs):
        route = (request.method, urlsplit(request.url).path)
        self.requests.append(route)
        if route not in self.routes:
            raise AssertionError(f"Unexpected network request: {route}")
        status, body = self.routes[route]
        return Response(request, status, body)


class NativeProbeTests(unittest.TestCase):
    def setUp(self):
        self.subscription = {
            "id": SERVICE + "/subscriptions/example-subscription",
            "name": "example-subscription",
            "properties": {"scope": PRODUCT, "state": "active", "displayName": "example"},
        }
        self.routes = {
            ("GET", API): (200, {"id": API, "name": "example-api", "properties": {"path": "example"}}),
            ("GET", PRODUCT): (200, {"id": PRODUCT, "name": "example-product", "properties": {"displayName": "Example"}}),
            ("HEAD", PRODUCT + "/apis/example-api"): (204, {}),
            ("GET", SERVICE + "/subscriptions"): (200, {"value": [self.subscription]}),
            ("GET", API + "/policies/policy"): (200, {"properties": {"value": "<policies />"}}),
        }

    def invoke(self, **kwargs):
        transport = Transport(self.routes)
        with ApiManagementClient(OfflineCredential(), "example-sub", transport=transport, retry_total=0) as client:
            with patch.object(PROBE, "ApiManagementClient", return_value=client):
                result = PROBE.probe_hub_contract(
                    "hub-rg", "hub-apim", spoke_id="example",
                    subscription="example-sub", credential=OfflineCredential(), **kwargs,
                )
        self.assertTrue(all(method in {"GET", "HEAD"} for method, _ in transport.requests))
        self.assertFalse(any("listSecrets" in path for _, path in transport.requests))
        return result, transport.requests

    def test_native_positive_is_hub_inventory_not_foundry_acceptance(self):
        result, requests = self.invoke()
        self.assertTrue(result["api_present"])
        self.assertTrue(result["product_assigned"])
        self.assertTrue(result["subscription_key_present"])
        self.assertEqual(result["hub_contract_status"], "ok")
        self.assertEqual(result["foundry_connection_status"], "unverified")
        self.assertEqual(result["missing_perms"], [])
        self.assertIn(("HEAD", PRODUCT + "/apis/example-api"), requests)

    def test_unbound_api_is_not_assigned(self):
        self.routes[("HEAD", PRODUCT + "/apis/example-api")] = (404, {})
        result, _ = self.invoke()
        self.assertFalse(result["product_assigned"])
        self.assertEqual(result["hub_contract_status"], "missing")

    def test_product_readback_from_another_scope_is_rejected(self):
        self.routes[("GET", PRODUCT)][1]["id"] = PRODUCT.replace("/hub-apim/", "/other-apim/")
        result, _ = self.invoke()
        self.assertFalse(result["product_assigned"])
        self.assertTrue(result["missing_perms"])
        self.assertIn("Product readback scope mismatch", " ".join(result["missing_perms"]))

    def test_api_readback_from_another_scope_is_rejected(self):
        self.routes[("GET", API)][1]["id"] = API.replace("/hub-apim/", "/other-apim/")
        result, _ = self.invoke()
        self.assertFalse(result["api_present"])
        self.assertTrue(result["missing_perms"])
        self.assertIn("API readback scope mismatch", " ".join(result["missing_perms"]))

    def test_display_name_cannot_authorize_unrelated_subscription(self):
        self.subscription["properties"]["scope"] = PRODUCT + "-other"
        result, _ = self.invoke()
        self.assertFalse(result["subscription_key_present"])

    def test_all_apis_subscription_is_not_product_scoped(self):
        self.subscription["properties"]["scope"] = "/apis"
        result, _ = self.invoke()
        self.assertFalse(result["subscription_key_present"])

    def test_exact_relative_scope_and_arbitrary_display_name(self):
        self.subscription["properties"].update(scope="/products/example-product", displayName="Unrelated name")
        result, _ = self.invoke()
        self.assertTrue(result["subscription_key_present"])

    def test_subscription_from_wrong_service_is_rejected(self):
        self.subscription["id"] = self.subscription["id"].replace("/hub-apim/", "/other-apim/")
        result, _ = self.invoke()
        self.assertFalse(result["subscription_key_present"])
        self.assertTrue(result["missing_perms"])

    def test_failed_inventory_cannot_leave_a_partial_pass(self):
        self.routes[("GET", SERVICE + "/subscriptions")][1]["nextLink"] = (
            "https://management.azure.com" + SERVICE + "/subscriptions/page2"
        )
        self.routes[("GET", SERVICE + "/subscriptions/page2")] = (
            403, {"error": {"code": "AuthorizationFailed", "message": "private diagnostic"}},
        )
        result, _ = self.invoke()
        self.assertFalse(result["subscription_key_present"])
        self.assertEqual(result["hub_contract_status"], "errored")
        self.assertTrue(result["missing_perms"])
        self.assertNotIn("private diagnostic", json.dumps(result))

    def test_binding_forbidden_is_not_missing(self):
        self.routes[("HEAD", PRODUCT + "/apis/example-api")] = (403, {"error": {"code": "AuthorizationFailed"}})
        result, _ = self.invoke()
        self.assertFalse(result["product_assigned"])
        self.assertEqual(result["hub_contract_status"], "errored")

    def test_no_foundry_observation_never_reports_ok_or_missing(self):
        self.routes[("GET", API)] = (404, {"error": {"code": "ResourceNotFound"}})
        result, _ = self.invoke()
        self.assertEqual(result["foundry_connection_status"], "unverified")

    def test_explicit_native_contract_ids(self):
        api_id, product_id = "azure-openai-api", "LLM-Example-App-DEV"
        replacements = {API: SERVICE + "/apis/" + api_id, PRODUCT: SERVICE + "/products/" + product_id}
        original = json.dumps(self.routes[("GET", SERVICE + "/subscriptions")][1])
        self.routes = {
            ("GET", replacements[API]): (200, {"id": replacements[API]}),
            ("GET", replacements[PRODUCT]): (200, {"id": replacements[PRODUCT]}),
            ("HEAD", replacements[PRODUCT] + "/apis/" + api_id): (204, {}),
            ("GET", SERVICE + "/subscriptions"): (200, json.loads(original.replace(PRODUCT, replacements[PRODUCT]))),
            ("GET", replacements[API] + "/policies/policy"): (200, {"properties": {"value": "<policies />"}}),
        }
        result, _ = self.invoke(api_id=api_id, product_id=product_id)
        self.assertEqual(result["hub_contract_status"], "ok")

    def test_policy_read_error_is_visible_not_certified(self):
        self.routes[("GET", API + "/policies/policy")] = (403, {"error": {"code": "AuthorizationFailed"}})
        result, _ = self.invoke()
        self.assertIsNone(result["rate_limit_policy"])
        self.assertTrue(result["missing_perms"])
        self.assertEqual(result["hub_contract_status"], "errored")


class PublishedContractTests(unittest.TestCase):
    def test_hosted_wiring_uses_canonical_environment_fragment(self):
        text = (SKILL / "SKILL.md").read_text()
        section = text.split("**Hosted Agents (FoundryChatClient):**", 1)[1].split("**Prompt Agents", 1)[0]
        self.assertIn("environmentVariables:", section)
        self.assertIn("AZURE_AI_MODEL_DEPLOYMENT_NAME", section)
        self.assertNotIn("environment_variables:", section)
        self.assertNotIn("`agent.yaml`", section)
        self.assertIn("../foundry-hosted-agents/references/yaml/azure.yaml", section)
        self.assertIn("../foundry-hosted-agents/references/python/main.py", section)

    def test_connection_custody_does_not_claim_downstream_jwt(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertIn("not end-to-end keyless", text)
        self.assertIn("authType: ApiKey", text)
        self.assertNotIn("APIM enforces JWT\n> validation on the project's MI token", text)
        self.assertNotIn("APIM enforces JWT validation on\nthe project's MI token", text)

    def test_spoke_materialization_and_pin_match_hub_source(self):
        pin = (SKILL / "references/upstream-pin.md").read_text()
        data = yaml.safe_load(pin.split("---", 2)[1])
        hub = yaml.safe_load((ROOT / "skills/citadel-hub-deploy/references/upstream-pin.md").read_text().split("---", 2)[1])
        sha = hub["upstream"]["pinned_sha"]
        self.assertEqual(data["upstream"]["pinned_sha"], sha)
        self.assertIn(f'PINNED_SHA="${{PINNED_SHA:-{sha}}}"', data["validation"]["script"])
        self.assertIn('git checkout --detach "$PINNED_SHA"', data["validation"]["script"])
        skill = (SKILL / "SKILL.md").read_text()
        self.assertIn(sha, skill)
        self.assertNotIn("git clone -b citadel-v1", skill)

    def test_current_agentops_status_retains_negative_acceptance(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Merged source, not production readiness", readme)
        self.assertIn("34001218180", readme)
        self.assertIn("quality FAIL (4/5 thresholds)", readme)
        self.assertIn("Doctor readiness BLOCKED", readme)
        self.assertNotIn("The published plugin does not include this unmerged addition.", readme)

    def test_reference_separates_live_inventory_from_unexecuted_routes(self):
        pin = (SKILL / "references/upstream-pin.md").read_text()
        status = pin.split("### Adoption status — 2026-09-17", 1)[1]
        for fact in (
            "09:35:14.539855", "09:35:19.515289", "HUB_INVENTORY",
            "unassociated", "HOSTED_GATEWAY_ROUTE", "DOWNSTREAM_JWT", "NOT TESTED",
            "5.0.0", "23.1.1", "1.25.3", "CLEANUP", "zero",
            "c6de8d1dbdfa7a9edfd5e6facf8eb75ff5ade7a623a8565a02b4721757d9dcfe",
            "3191f175305b463068035b0910995eb0b0330404fdab25c1412ce72756f625e0",
        ):
            self.assertIn(fact, status)
        self.assertIn("source-only", status)
        self.assertNotIn("corrected probe and unified Hosted wiring need", pin)
        skill = (SKILL / "SKILL.md").read_text()
        self.assertIn("references/upstream-pin.md", skill)
        self.assertIn("Version 2 migration", skill)
        self.assertIn("`foundry_connection_status=\"ok\"`", skill)
        self.assertIn("`hub_contract_status`", skill)


if __name__ == "__main__":
    unittest.main()

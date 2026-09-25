"""Offline profile, manifest and adoption regression tests for #518."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills/foundry-hosted-agents/references"
sys.path.insert(0, str(REFS / "python"))
import hosted_contract as contract
from deploy_preflight import check_capabilities
from datetime import datetime, timezone


class HostedContractTests(unittest.TestCase):
    def setUp(self):
        self.consumer = {"azd": "1.34.1", "azure.ai.agents": "1.0.0-beta.14"}
        self.profile = contract.select_profile("maf-container-beta14", self.consumer)
        self.service = yaml.safe_load((REFS / "yaml/azure.yaml").read_text())["services"]["my-agent"]

    def test_exact_consumer_and_canonical_service(self):
        contract.validate_service(self.service, self.profile)

    def test_unknown_legacy_and_other_runtime_require_review(self):
        for name in ("missing", "legacy-two-file", "ghcp-invocations"):
            with self.subTest(name=name), self.assertRaises(contract.ContractError):
                contract.select_profile(name, self.consumer)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hosted-contract.json"
            changed = contract.load_contract()
            changed["contract_version"] = "2.0.0"
            path.write_text(json.dumps(changed))
            with patch.object(contract, "CONTRACT", path), self.assertRaises(contract.ContractError):
                contract.select_profile("maf-container-beta14", self.consumer)

    def test_newer_or_older_versions_are_not_implicitly_supported(self):
        for version in ("1.27.0", "1.35.0", ""):
            with self.subTest(version=version), self.assertRaises(contract.ContractError):
                contract.select_profile("maf-container-beta14", {**self.consumer, "azd": version})
        with self.assertRaises(contract.ContractError):
            contract.select_profile("maf-container-beta14", {"azd": "1.34.1"})

    def test_mixed_env_and_reserved_names_fail_without_echoing_values(self):
        for key in ("env", "environment_variables"):
            with self.subTest(key=key), self.assertRaises(contract.ContractError):
                contract.validate_service({**self.service, key: {}}, self.profile)
        for name in ("FOUNDRY_PROJECT_ENDPOINT", "AGENT_TEST", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
            service = copy.deepcopy(self.service)
            service["environmentVariables"].append({"name": name, "value": "private-value"})
            with self.assertRaises(contract.ContractError) as error:
                contract.validate_service(service, self.profile)
            self.assertNotIn("private-value", str(error.exception))

    def test_duplicate_env_wrong_protocol_and_code_deploy_rejected(self):
        for mutate in (
            lambda s: s["environmentVariables"].append(s["environmentVariables"][0]),
            lambda s: s.update(protocols=[{"protocol": "responses", "version": "1.0.0"}]),
            lambda s: s.update(codeConfiguration={"runtime": "python_3_13"}),
        ):
            service = copy.deepcopy(self.service)
            mutate(service)
            with self.assertRaises(contract.ContractError):
                contract.validate_service(service, self.profile)

    def test_adoption_compares_bytes_not_contract_label(self):
        reviewed = contract.provenance()
        contract.require_adoption(reviewed, contract.provenance())
        adopted = copy.deepcopy(reviewed)
        adopted["sha256"]["python/hosted_smoke.py"] = "0" * 64
        with self.assertRaises(contract.ContractError):
            contract.require_adoption(reviewed, adopted)

    def test_provenance_rejects_symlinked_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "references"
            shutil.copytree(REFS, target)
            helper = target / "python/hosted_smoke.py"
            helper.unlink()
            helper.symlink_to(REFS / "python/hosted_smoke.py")
            with self.assertRaises(contract.ContractError):
                contract.provenance(target)


def capabilities():
    permissions = [{"operation": operation, "principal_id": f"{operation}-principal",
                    "scope": "/approved/scope", "actions": [f"synthetic/{operation}"],
                    "api_contract": "reviewed-operation-reference"}
                   for operation in ("image-pull", "invoke", "version-read", "response-read", "session-read")]
    return {
        "schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
        "target": {"profile": "maf-container-beta14", "environment_id": "/approved/environment",
                   "mode": "basic-private", "registry_network": "private",
                   "required_features": ["hosted-container", "private-agent-network", "private-registry-pull"],
                   "registry_id": "/approved/registry",
                   "repository": "approved", "pull_requirement": "repository-only",
                   "source_access_required": False, "required_permissions": permissions},
        "consumer": {"azd": "1.34.1", "azure.ai.agents": "1.0.0-beta.14"},
        "environment": {"resource_id": "/approved/environment",
                        "project_created_at": "2026-09-01T00:00:00Z",
                        "supported_features": ["hosted-container", "private-agent-network", "private-registry-pull"],
                        "result": "pass", "evidence": "private-environment-read"},
        "registry": {"id": "/approved/registry", "role_assignment_mode": "AbacRepositoryPermissions",
                     "repository_condition_verified": True, "broader_pull_grants_excluded": True,
                     "result": "pass", "evidence": "private-registry-read"},
        "permissions": [{**p, "effective_conditions_verified": True, "result": "pass",
                         "evidence": "private-role-and-condition-read"} for p in permissions],
        "ingress": {"authentication_enforced": True, "direct_backend_bypass_blocked": True,
                    "forwarded_headers": "ignored", "result": "pass", "evidence": "private-route-proof"},
    }


class CapabilityTests(unittest.TestCase):
    def test_preflight_does_not_require_image_or_future_session(self):
        self.assertEqual(check_capabilities(capabilities())["status"], "READY_FOR_ARTIFACTS")

    def test_legacy_cannot_satisfy_repository_only(self):
        data = capabilities()
        data["registry"]["role_assignment_mode"] = "LegacyRegistryPermissions"
        self.assertEqual(check_capabilities(data)["issues"][0]["code"], "UNSUPPORTED_CAPABILITY")
        data["target"]["pull_requirement"] = "registry-wide"
        self.assertEqual(check_capabilities(data)["status"], "BLOCKED")
        data["target"]["registry_wide_approved"] = True
        self.assertEqual(check_capabilities(data)["status"], "READY_FOR_ARTIFACTS")

    def test_unsupported_environment_and_unverified_auth_stop_before_build(self):
        mutations = (
            lambda d: d["environment"].update(supported_features=[]),
            lambda d: d["registry"].update(broader_pull_grants_excluded=False),
            lambda d: d["ingress"].update(forwarded_headers="trust-all"),
            lambda d: d["ingress"].update(direct_backend_bypass_blocked=False),
            lambda d: d["permissions"][2].update(principal_id="invoker-not-reader"),
            lambda d: d["permissions"][3].update(result="forbidden"),
            lambda d: d["target"].update(source_access_required=True),
            lambda d: d["environment"].update(project_created_at="2026-06-25T12:00:00Z"),
            lambda d: d["target"].update(required_features=["hosted-container"]),
        )
        for mutate in mutations:
            data = capabilities()
            mutate(data)
            with self.subTest(mutate=mutate):
                self.assertEqual(check_capabilities(data)["status"], "BLOCKED")

    def test_duplicate_permission_receipt_does_not_hide_a_denial(self):
        data = capabilities()
        data["permissions"].append({**data["permissions"][0], "result": "fail"})
        self.assertEqual(check_capabilities(data)["status"], "BLOCKED")

    def test_missing_decision_or_stale_observation_is_not_ready(self):
        for key in ("pull_requirement", "source_access_required", "required_permissions"):
            data = capabilities()
            del data["target"][key]
            self.assertEqual(check_capabilities(data)["status"], "BLOCKED")
        data = capabilities()
        data["observed_at"] = "2000-01-01T00:00:00Z"
        self.assertEqual(check_capabilities(data)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()

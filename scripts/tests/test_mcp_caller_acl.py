"""App-only audience/caller separation; no Azure calls."""

import importlib.util
from pathlib import Path
import unittest
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("producer_auth", ROOT / "skills/foundry-mcp-aca/references/python/auth_config.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class CallerAclTests(unittest.TestCase):
    def test_exact_client_acl_is_distinct_from_api_audience(self):
        tenant, api, executor, worker = (str(UUID(int=i)) for i in range(1, 5))
        allow = module.build(tenant, api, [executor])
        deny = module.build(tenant, api, [worker])
        for config in (allow, deny):
            self.assertEqual(config["properties"]["globalValidation"]["unauthenticatedClientAction"], "Return401")
            provider = config["properties"]["identityProviders"]["azureActiveDirectory"]
            self.assertNotIn("clientSecretSettingName", provider["registration"])
            self.assertEqual(provider["validation"]["allowedAudiences"], [f"api://{api}", api])
        self.assertEqual(allow["properties"]["identityProviders"]["azureActiveDirectory"]["validation"]["defaultAuthorizationPolicy"],
                         {"allowedApplications": [executor]})
        self.assertNotIn(executor, deny["properties"]["identityProviders"]["azureActiveDirectory"]["validation"]["defaultAuthorizationPolicy"]["allowedApplications"])

    def test_missing_duplicate_audience_or_invalid_caller_rejected(self):
        tenant, api, caller = (str(UUID(int=i)) for i in range(1, 4))
        for callers in ([], None, [api], [caller, caller], ["*"], ["not-a-guid"]):
            with self.subTest(callers=callers), self.assertRaises((ValueError, TypeError)):
                module.build(tenant, api, callers)

    def test_fixture_restores_positive_acl_after_negative_probe(self):
        text = (ROOT / "skills/foundry-mcp-aca/test-fixture/consumer_prompt.md").read_text()
        self.assertIn("--caller \"$AZURE_CLIENT_ID\"", text)
        self.assertIn("trap restore_ci_policy EXIT", text)
        self.assertIn('test "$NEGATIVE_CALLER" != "$AZURE_CLIENT_ID"', text)
        self.assertIn('[ "$DENIED_CODE" = 403 ]', text)
        self.assertIn('[ "$RESTORED_CODE" = 200 ]', text)
        self.assertIn("CALLER_ACL_RESTORED_200", text)
        self.assertIn("properties: loadJsonContent('mcp-authconfig.json').properties", text)
        provision = text.split("### Deterministic provision Bash block (MANDATORY)", 1)[1]
        self.assertLess(provision.index("--caller \"$AZURE_CLIENT_ID\""), provision.index("if ! azd up"))
        self.assertNotIn("until azd up", text)
        bicep = (ROOT / "skills/foundry-mcp-aca/references/bicep/mcp-aca-auth.bicep").read_text()
        self.assertIn("@minLength(1)\nparam allowedCallerClientIds array", bicep)
        self.assertNotIn("param allowedCallerClientIds array =", bicep)

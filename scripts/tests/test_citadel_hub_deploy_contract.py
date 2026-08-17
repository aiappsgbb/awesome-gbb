#!/usr/bin/env python3
"""Contract tests for the citadel-hub-deploy upstream pin and profiles."""

from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "citadel-hub-deploy"
PROFILES_DIR = SKILL_DIR / "references" / "profiles"
TARGET_SHA = "63f0f812474e713916dc909494d655246783a1d9"
LIVE_VALIDATED_SHA = "f2702b49f80d0ad40e227ae2ee9d8b6dd9137da4"

UPSTREAM_PROFILE_ENV_VARS = {
    "AI_FOUNDRY_EXTERNAL_NETWORK_ACCESS",
    "APIC_LOCATION",
    "APIC_SKU",
    "APIM_NETWORK_TYPE",
    "APIM_SKU",
    "APIM_SKU_UNITS",
    "APIM_V2_PUBLIC_NETWORK_ACCESS",
    "APIM_V2_USE_PRIVATE_ENDPOINT",
    "AZURE_ENTRA_AUTH",
    "AZURE_LOCATION",
    "COSMOS_DB_PUBLIC_ACCESS",
    "COSMOS_DB_RUS",
    "CREATE_DASHBOARDS",
    "ENABLE_AI_MODEL_INFERENCE",
    "ENABLE_API_CENTER",
    "ENABLE_AZURE_AI_SEARCH",
    "ENABLE_DOCUMENT_INTELLIGENCE",
    "ENABLE_MANAGED_REDIS",
    "ENABLE_OPENAI_REALTIME",
    "ENABLE_PII_REDACTION",
    "ENABLE_UNIFIED_AI_API",
    "EVENTHUB_CAPACITY",
    "EVENTHUB_NETWORK_ACCESS",
    "KEY_VAULT_EXTERNAL_NETWORK_ACCESS",
    "KEY_VAULT_SKU_NAME",
    "LOGIC_APPS_SKU_CAPACITY_UNITS",
    "REDIS_HIGH_AVAILABILITY",
    "REDIS_PUBLIC_NETWORK_ACCESS",
    "REDIS_SKU_CAPACITY",
    "REDIS_SKU_NAME",
    "USE_EXISTING_LOG_ANALYTICS",
    "USE_EXISTING_VNET",
    "VNET_ADDRESS_PREFIX",
}


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_profile(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in read(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


class CitadelHubDeployContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = read(SKILL_DIR / "SKILL.md")
        self.pin = read(SKILL_DIR / "references" / "upstream-pin.md")
        self.audit = read(SKILL_DIR / "references" / "live-audit-notes.md")
        self.checklist = read(SKILL_DIR / "references" / "customer-checklist.md")
        self.profiles = {
            path.name: parse_profile(path)
            for path in sorted(PROFILES_DIR.glob("*.env"))
        }

    def assert_profile_values(
        self,
        profile_name: str,
        expected: dict[str, str],
    ) -> None:
        profile = self.profiles[profile_name]
        for key, value in expected.items():
            with self.subTest(profile=profile_name, key=key):
                self.assertEqual(profile.get(key), value)

    def test_pin_and_quickstart_materialize_the_exact_target_sha(self) -> None:
        self.assertIn(f"pinned_sha: {TARGET_SHA}", self.pin)
        self.assertRegex(
            self.skill,
            rf'PINNED_SHA=["\']{TARGET_SHA}["\']',
        )
        self.assertIn('git checkout --detach "$PINNED_SHA"', self.skill)
        self.assertIn('git rev-parse HEAD', self.skill)
        self.assertNotIn("--branch citadel-v1", self.skill)

    def test_manual_build_validator_is_persistent_and_overrideable(self) -> None:
        self.assertIn("automation_tier: issue_only", self.pin)
        self.assertIn("runnable: false", self.pin)
        self.assertIn(
            f'PINNED_SHA="${{PINNED_SHA:-{TARGET_SHA}}}"',
            self.pin,
        )
        self.assertIn("az bicep build", self.pin)
        self.assertIn("az bicep build-params", self.pin)

    def test_secondary_foundry_region_is_not_misrepresented_as_env_driven(self) -> None:
        self.assertIn("hardcoded `eastus2`", self.checklist)
        self.assertIn("There is no `AZURE_LOCATION_2`", self.checklist)

    def test_profiles_only_use_env_vars_consumed_by_target_bicepparam(self) -> None:
        for name, profile in self.profiles.items():
            with self.subTest(profile=name):
                self.assertEqual(
                    set(profile) - UPSTREAM_PROFILE_ENV_VARS,
                    set(),
                    "profile contains env vars not consumed at the pinned SHA",
                )

    def test_pilot_quickstart_is_lean_and_secure(self) -> None:
        expected = {
            "APIM_SKU": "Developer",
            "USE_EXISTING_VNET": "false",
            "USE_EXISTING_LOG_ANALYTICS": "false",
            "COSMOS_DB_PUBLIC_ACCESS": "Disabled",
            "AI_FOUNDRY_EXTERNAL_NETWORK_ACCESS": "Disabled",
            "KEY_VAULT_EXTERNAL_NETWORK_ACCESS": "Disabled",
            "EVENTHUB_NETWORK_ACCESS": "Disabled",
            "ENABLE_MANAGED_REDIS": "false",
            "REDIS_HIGH_AVAILABILITY": "Disabled",
            "ENABLE_API_CENTER": "false",
            "ENABLE_AZURE_AI_SEARCH": "false",
            "ENABLE_DOCUMENT_INTELLIGENCE": "false",
            "CREATE_DASHBOARDS": "false",
            "AZURE_ENTRA_AUTH": "true",
        }
        self.assert_profile_values("pilot-quickstart.env", expected)

    def test_apim_v2_profiles_keep_event_hub_public_during_provisioning(self) -> None:
        for profile_name in (
            "enterprise-baseline.env",
            "vnet-isolated-spoke-aware.env",
        ):
            with self.subTest(profile=profile_name):
                self.assertEqual(
                    self.profiles[profile_name].get("EVENTHUB_NETWORK_ACCESS"),
                    "Enabled",
                )
        self.assertRegex(
            self.skill + self.checklist,
            re.compile(
                r"Event Hub.{0,180}Enabled.{0,180}APIM v2",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_entra_setup_documents_permissions_private_kv_and_verification(self) -> None:
        docs = self.skill + self.checklist
        for required_text in (
            "Application.ReadWrite.All",
            "Application Developer",
            "Key Vault Secrets Officer",
            "API Management Service Contributor",
            "ENTRA-APP-CLIENT-SECRET",
            "az keyvault secret show",
            "az apim nv show",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, docs)
        self.assertRegex(
            docs,
            re.compile(
                r"Key Vault.{0,300}(?:private endpoint|private network|VPN|peered)",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            docs,
            re.compile(
                r"setup\.ps1.{0,500}continues.{0,300}Key Vault",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_entra_setup_verifies_current_values_not_only_resource_existence(self) -> None:
        for required_text in (
            "azd env get-value ENTRA_CLIENT_SECRET",
            "azd env get-value AZURE_CLIENT_ID",
            "--query value -o tsv",
            "https://login.microsoftonline.com/$EXPECTED_TENANT_ID/v2.0",
            (
                "https://login.microsoftonline.com/"
                "$EXPECTED_TENANT_ID/v2.0/.well-known/openid-configuration"
            ),
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, self.skill)
        self.assertRegex(
            self.skill,
            re.compile(
                r'keyvault secret show.{0,240}--query value -o tsv.{0,240}'
                r'ENTRA_CLIENT_SECRET',
                re.DOTALL,
            ),
        )
        self.assertRegex(
            self.skill,
            re.compile(
                r'apim nv show.{0,240}--query value -o tsv.{0,300}'
                r'expected_value',
                re.DOTALL,
            ),
        )
        verification_docs = self.skill + self.checklist
        self.assertNotIn("declare -A", verification_docs)
        for named_value in (
            "JWT-TenantId",
            "JWT-AppRegistrationId",
            "JWT-Issuer",
            "JWT-OpenIdConfigUrl",
        ):
            with self.subTest(named_value=named_value):
                self.assertRegex(
                    self.skill,
                    re.compile(
                        rf"verify_apim_named_value\s+{named_value}\s+",
                    ),
                )

    def test_quickstarts_assert_exact_guids_before_mutating_azure(self) -> None:
        self.assertIn('EXPECTED_TENANT_ID="<tenant-guid>"', self.skill)
        self.assertIn(
            'EXPECTED_SUBSCRIPTION_ID="<subscription-guid>"',
            self.skill,
        )
        self.assertIn("az account show --query tenantId", self.skill)
        self.assertIn("az account show --query id", self.skill)
        self.assertNotIn("az account show --query name", self.skill)
        for required_text in (
            "azd env get-value AZURE_TENANT_ID --no-prompt",
            "azd env get-value AZURE_SUBSCRIPTION_ID --no-prompt",
            'azd env set AZURE_TENANT_ID "$EXPECTED_TENANT_ID"',
            'azd env set AZURE_SUBSCRIPTION_ID "$EXPECTED_SUBSCRIPTION_ID"',
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, self.skill)
        self.assertGreaterEqual(
            len(re.findall(r"assert_azure_target\s*\n\s*azd up", self.skill)),
            3,
        )
        self.assertRegex(
            self.skill,
            re.compile(
                r"assert_azure_target.{0,240}pwsh (?:\./)?setup\.ps1",
                re.DOTALL,
            ),
        )
        self.assertIn("$expectedTenantId = \"<tenant-guid>\"", self.skill)
        self.assertIn(
            "$expectedSubscriptionId = \"<subscription-guid>\"",
            self.skill,
        )
        self.assertRegex(
            self.skill,
            re.compile(r"Assert-AzureTarget\s*\n\s*azd up"),
        )
        self.assertRegex(
            self.skill,
            re.compile(r"Assert-AzureTarget\s*\n\s*pwsh \.\\setup\.ps1"),
        )

    def test_checklist_asserts_exact_cli_and_active_azd_environment_guids(self) -> None:
        for required_text in (
            'EXPECTED_TENANT_ID="<tenant-guid>"',
            'EXPECTED_SUBSCRIPTION_ID="<subscription-guid>"',
            'az account set --subscription "$EXPECTED_SUBSCRIPTION_ID"',
            "az account show --query tenantId -o tsv",
            "az account show --query id -o tsv",
            "azd env get-value AZURE_TENANT_ID --no-prompt",
            "azd env get-value AZURE_SUBSCRIPTION_ID --no-prompt",
            "assert_azure_target || exit 1",
            "immediately before `azd up`",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, self.checklist)
        self.assertNotIn("az account show --query name", self.checklist)
        self.assertNotIn("az account set --subscription <name>", self.checklist)
        self.assertNotRegex(
            self.checklist,
            re.compile(
                r"azd env get-values.{0,120}(?:grep|cut|sed|eval)",
                re.DOTALL,
            ),
        )
        self.assertRegex(
            self.checklist,
            re.compile(
                r'actual_tenant.{0,500}EXPECTED_TENANT_ID.{0,500}'
                r'actual_subscription.{0,500}EXPECTED_SUBSCRIPTION_ID.{0,500}'
                r'azd_tenant.{0,500}EXPECTED_TENANT_ID.{0,500}'
                r'azd_subscription.{0,500}EXPECTED_SUBSCRIPTION_ID',
                re.DOTALL,
            ),
        )

    def test_quick_smoke_requires_entra_and_subscription_auth_and_http_success(
        self,
    ) -> None:
        smoke = self.skill.split("### Quick smoke (no Jupyter)", 1)[1].split(
            "\n---",
            1,
        )[0]
        for required_text in (
            "azd env get-value AZURE_TENANT_ID --no-prompt",
            "azd env get-value AZURE_SUBSCRIPTION_ID --no-prompt",
            "azd env get-value AZURE_CLIENT_ID --no-prompt",
            "azd env get-value AZURE_AUDIENCE --no-prompt",
            "azd env get-value ENTRA_CLIENT_SECRET --no-prompt",
            "https://login.microsoftonline.com/$TENANT_ID/oauth2/v2.0/token",
            "grant_type=client_credentials",
            "scope=$AUDIENCE/.default",
            "jq -er '.access_token'",
            "set +x",
            "unset CLIENT_SECRET",
            "unset TOKEN KEY",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, smoke)
        self.assertGreaterEqual(smoke.count("--fail-with-body"), 3)
        self.assertGreaterEqual(smoke.count('-H "api-key: $KEY"'), 2)
        self.assertGreaterEqual(
            smoke.count('-H "Authorization: Bearer $TOKEN"'),
            2,
        )
        self.assertNotRegex(smoke, re.compile(r"curl -s(?:\s|$)"))
        self.assertNotIn('echo "$TOKEN"', smoke)
        self.assertNotIn('echo "$CLIENT_SECRET"', smoke)
        self.assertNotIn("set -x", smoke)

    def test_powershell_quickstart_fails_on_native_command_errors(self) -> None:
        self.assertIn('$ErrorActionPreference = "Stop"', self.skill)
        self.assertIn("function Assert-NativeSuccess", self.skill)
        for operation in (
            "az login",
            "azd auth login",
            "az account set",
            "git clone",
            "git fetch",
            "git checkout",
            "azd env new",
            "azd up",
            "Entra setup",
        ):
            with self.subTest(operation=operation):
                self.assertIn(
                    f'Assert-NativeSuccess "{operation}"',
                    self.skill,
                )
        self.assertRegex(
            self.skill,
            re.compile(
                r"azd env set \$k \$v\s*\n\s*"
                r'Assert-NativeSuccess "profile value \$k"',
            ),
        )
        self.assertIn("Test-Path -LiteralPath $profilePath -PathType Leaf", self.skill)
        self.assertIn(
            "Get-Content -LiteralPath $profilePath -ErrorAction Stop",
            self.skill,
        )

    def test_separate_host_entra_setup_exits_on_target_mismatch(self) -> None:
        self.assertGreaterEqual(self.skill.count("set -euo pipefail"), 2)
        self.assertRegex(
            self.skill,
            re.compile(
                r"assert_azure_target \|\| exit 1\s*\n\s*pwsh \./setup\.ps1",
            ),
        )

    def test_apim_private_ingress_is_not_described_as_fully_private_hub(self) -> None:
        for profile_name in (
            "enterprise-baseline.env",
            "vnet-isolated-spoke-aware.env",
        ):
            profile_text = (
                PROFILES_DIR / profile_name
            ).read_text(encoding="utf-8")
            with self.subTest(profile=profile_name):
                self.assertNotIn("fully private", profile_text.lower())
        self.assertNotIn("To go fully private", self.skill)

    def test_enterprise_and_vnet_profiles_preserve_critical_guardrails(self) -> None:
        shared = {
            "APIM_SKU": "StandardV2",
            "COSMOS_DB_PUBLIC_ACCESS": "Disabled",
            "AI_FOUNDRY_EXTERNAL_NETWORK_ACCESS": "Disabled",
            "KEY_VAULT_EXTERNAL_NETWORK_ACCESS": "Disabled",
            "REDIS_PUBLIC_NETWORK_ACCESS": "Disabled",
            "EVENTHUB_NETWORK_ACCESS": "Enabled",
            "ENABLE_MANAGED_REDIS": "true",
            "REDIS_HIGH_AVAILABILITY": "Enabled",
            "ENABLE_API_CENTER": "true",
            "ENABLE_AZURE_AI_SEARCH": "false",
            "ENABLE_DOCUMENT_INTELLIGENCE": "false",
            "CREATE_DASHBOARDS": "true",
            "AZURE_ENTRA_AUTH": "true",
        }
        self.assert_profile_values(
            "enterprise-baseline.env",
            shared
            | {
                "USE_EXISTING_VNET": "false",
                "USE_EXISTING_LOG_ANALYTICS": "true",
                "APIM_V2_USE_PRIVATE_ENDPOINT": "true",
                "APIM_V2_PUBLIC_NETWORK_ACCESS": "true",
            },
        )
        self.assert_profile_values(
            "vnet-isolated-spoke-aware.env",
            shared
            | {
                "USE_EXISTING_VNET": "true",
                "USE_EXISTING_LOG_ANALYTICS": "false",
                "APIM_V2_USE_PRIVATE_ENDPOINT": "true",
                "APIM_V2_PUBLIC_NETWORK_ACCESS": "false",
            },
        )
        for profile_name in (
            "enterprise-baseline.env",
            "vnet-isolated-spoke-aware.env",
        ):
            with self.subTest(profile=profile_name):
                self.assertNotIn(
                    "FOUNDRY_NETWORK_INJECTION_ENABLED",
                    self.profiles[profile_name],
                )

    def test_profiles_do_not_enable_incompatible_network_injection(self) -> None:
        for name, profile in self.profiles.items():
            with self.subTest(profile=name):
                self.assertNotIn("FOUNDRY_NETWORK_INJECTION_ENABLED", profile)
        self.assertRegex(
            self.skill,
            re.compile(
                r"network injection.{0,240}not (?:consumed|exposed).{0,240}"
                r"main\.bicepparam",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_redis_profiles_declare_current_high_availability_setting(self) -> None:
        for name, profile in self.profiles.items():
            if profile.get("ENABLE_MANAGED_REDIS") == "true":
                with self.subTest(profile=name):
                    self.assertIn(
                        profile.get("REDIS_HIGH_AVAILABILITY"),
                        {"Enabled", "Disabled"},
                    )

    def test_audit_separates_new_build_validation_from_old_live_evidence(self) -> None:
        self.assertIn(TARGET_SHA, self.audit)
        self.assertIn(LIVE_VALIDATED_SHA, self.audit)
        self.assertRegex(
            self.audit,
            re.compile(
                rf"{TARGET_SHA}.{{0,500}}build",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            self.audit,
            re.compile(
                rf"{LIVE_VALIDATED_SHA}.{{0,500}}live",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            self.audit,
            re.compile(
                r"no (?:Azure )?(?:deployment|live validation).{0,160}"
                rf"{TARGET_SHA}",
                re.IGNORECASE | re.DOTALL,
            ),
        )


if __name__ == "__main__":
    unittest.main()

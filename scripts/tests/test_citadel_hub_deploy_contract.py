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
        pilot = self.profiles["pilot-quickstart.env"]
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
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(pilot.get(key), value)

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

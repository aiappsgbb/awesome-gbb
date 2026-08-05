#!/usr/bin/env python3
"""Focused regression tests for the foundry-hosted-agents refresh contract."""

from __future__ import annotations

import pathlib
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-hosted-agents"
FIXTURE = SKILL_DIR / "test-fixture" / "consumer_prompt.md"
PIN = SKILL_DIR / "references" / "upstream-pin.md"
TIMEOUT = SKILL_DIR / "references" / "python" / "foundry_agent_timeout.py"


class FoundryHostedAgentsRefreshContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.pin = PIN.read_text(encoding="utf-8")
        cls.timeout = TIMEOUT.read_text(encoding="utf-8")
        cls.pin_frontmatter = yaml.safe_load(cls.pin.split("---", 2)[1])

    def test_timeout_reference_requires_current_versions(self) -> None:
        self.assertIn("- agent-framework-core ~= 1.13.0", self.timeout)
        self.assertIn("- agent-framework-foundry ~= 1.10.4", self.timeout)
        self.assertNotIn("- agent-framework-core ~= 1.11.0", self.timeout)
        self.assertNotIn("- agent-framework-foundry ~= 1.10.1", self.timeout)

    def test_fixture_records_canonical_pyproject_parity_with_marker_safe_failure(self) -> None:
        required = (
            'grep -Fq',
            "CANONICAL_PYPROJECT_OK",
            "SMOKE_RESULT=FAIL canonical pyproject dependency drift:",
            'r"CANONICAL_PYPROJECT_OK"',
            "printf 'SMOKE_RESULT=FAIL canonical pyproject dependency drift: <dependency>\\n' > /tmp/foundry-hosted-agents-smoke-result",
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.fixture)

    def test_pin_validation_imports_canonical_container_and_otel_bundle(self) -> None:
        required = (
            "PIN_VALIDATION_REPO_ROOT",
            "references/python/container.py",
            "importlib.util.spec_from_file_location",
            "from microsoft.opentelemetry import use_microsoft_opentelemetry",
            "from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor",
            'print("ok canonical container import")',
            'print("ok otel bundle")',
            "assert callable(client.agents.update_details)",
            'print("ok hosted coherent stack")',
            'print("ok update_details")',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, self.pin)
        self.assertEqual(
            self.pin_frontmatter["validation"]["expected_output"],
            [
                "ok canonical container import",
                "ok hosted coherent stack",
                "ok update_details",
                "ok otel bundle",
            ],
        )


if __name__ == "__main__":
    unittest.main()

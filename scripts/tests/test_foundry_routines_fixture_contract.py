"""Contract tests for the live Foundry Routines fixture."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-routines" / "SKILL.md"
FIXTURE = ROOT / "skills" / "foundry-routines" / "test-fixture" / "consumer_prompt.md"
PIN = ROOT / "skills" / "foundry-routines" / "references" / "upstream-pin.md"


class FoundryRoutinesFixtureContractTests(unittest.TestCase):
    def test_skill_version_includes_live_fixture_repair(self) -> None:
        raw = SKILL.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        version = tuple(
            int(part)
            for part in yaml.safe_load(frontmatter)["metadata"]["version"].split(".")
        )

        self.assertGreaterEqual(version, (1, 0, 3))

    def test_install_contract_uses_current_bounded_dependencies(self) -> None:
        expected = (
            '"azure-ai-projects~=2.4.0" '
            '"azure-identity~=1.25.3" '
            '"httpx~=0.28.1"'
        )
        self.assertIn(expected, SKILL.read_text(encoding="utf-8"))
        self.assertIn(expected, FIXTURE.read_text(encoding="utf-8"))

        pin = PIN.read_text(encoding="utf-8")
        self.assertIn('"azure-ai-projects~=${PINNED_VERSION:-2.4.0}"', pin)
        self.assertIn('"azure-identity~=1.25.3"', pin)
        self.assertIn('"httpx~=0.28.1"', pin)

    def test_pin_audit_trail_matches_current_frontmatter(self) -> None:
        pin = PIN.read_text(encoding="utf-8")

        self.assertIn("| **Pinned version** | **2.4.0**", pin)
        self.assertIn("`~=2.4.0` ≡ `>=2.4.0, <2.5.0`", pin)
        self.assertIn("| `azure-ai-projects` | PyPI | **2.4.0**", pin)
        self.assertIn("| `httpx` | PyPI | **0.28.1**", pin)
        self.assertNotIn("aif-awesome-gbb-ci", pin)

    def test_fixture_uses_live_proven_monthly_schedule(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn('"monthly-anchor"', fixture)
        self.assertIn('"cron_expression": "0 0 1 * *"', fixture)
        self.assertNotIn('"annual-anchor"', fixture)
        self.assertNotIn('"cron_expression": "0 0 1 1 *"', fixture)
        self.assertNotIn("January 1", fixture)

    def test_fixture_forbids_self_modification(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn("Do NOT edit any repository file", fixture)
        self.assertRegex(
            fixture,
            re.compile(r"service\s+rejects.{0,200}write the FAIL marker", re.DOTALL),
        )
        self.assertNotIn("rg-awesome-gbb-ci", fixture)

    def test_generated_docs_show_the_current_version_everywhere(self) -> None:
        raw = SKILL.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        expected = f"v{yaml.safe_load(frontmatter)['metadata']['version']}"
        detail = (
            ROOT / "docs" / "skills" / "foundry-routines" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(f'<span class="badge ver">{expected}</span>', detail)

        card_pattern = re.compile(
            r'href="/awesome-gbb/skills/foundry-routines/">'
            r"foundry-routines</a>.{0,1600}"
            rf'<span class="badge ver">{re.escape(expected)}</span>',
            re.DOTALL,
        )
        listing_pages = (
            ROOT / "docs" / "skills" / "index.html",
            ROOT / "docs" / "plugins" / "awesome-gbb" / "index.html",
        )
        for page in listing_pages:
            with self.subTest(page=page.relative_to(ROOT)):
                self.assertRegex(page.read_text(encoding="utf-8"), card_pattern)


if __name__ == "__main__":
    unittest.main()

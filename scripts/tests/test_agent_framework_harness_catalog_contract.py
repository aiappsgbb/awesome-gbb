#!/usr/bin/env python3
"""Catalog integration contract for the Agent Framework Harness skill."""

from __future__ import annotations

import json
import pathlib
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def frontmatter(path: pathlib.Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


class AgentFrameworkHarnessCatalogContractTests(unittest.TestCase):
    def test_catalog_versions_include_the_new_skill(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads(
            (ROOT / ".github" / "plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(plugin["version"], "4.30.0")
        self.assertIn("36 reusable building blocks", plugin["description"])
        self.assertEqual(marketplace["metadata"]["version"], "4.30.0")
        self.assertEqual(marketplace["plugins"][0]["version"], "4.30.0")

    def test_adjacent_skills_route_to_harness_ownership(self) -> None:
        expected_versions = {
            "foundry-hosted-agents": "2.1.4",
        }
        for skill, expected_version in expected_versions.items():
            with self.subTest(skill=skill):
                metadata = frontmatter(SKILLS / skill / "SKILL.md")
                description = str(metadata["description"])
                self.assertIn("agent-framework-harness", description)
                self.assertEqual(
                    metadata["metadata"]["version"],  # type: ignore[index]
                    expected_version,
                )

    def test_fixture_is_compatible_with_checkout_integrity_guard(self) -> None:
        fixture = (
            SKILLS
            / "agent-framework-harness"
            / "test-fixture"
            / "consumer_prompt.md"
        ).read_text(encoding="utf-8")

        self.assertIn('echo "skills/agent-framework-harness/SKILL.md"', fixture)
        self.assertIn("never invoke `copilot` recursively", fixture)
        self.assertIn(
            "printf 'SMOKE_RESULT=PASS\\n' > "
            "/tmp/agent-framework-harness-smoke-result",
            fixture,
        )
        self.assertNotIn("git checkout", fixture)
        self.assertNotIn("git commit", fixture)
        self.assertNotIn("git add", fixture)


if __name__ == "__main__":
    unittest.main()

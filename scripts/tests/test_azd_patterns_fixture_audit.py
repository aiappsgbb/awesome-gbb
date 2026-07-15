#!/usr/bin/env python3
"""Regression test for deterministic azd-patterns fixture audit evidence."""

from __future__ import annotations

import pathlib
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "azd-patterns"


class AzdPatternsFixtureAuditTests(unittest.TestCase):
    def test_fixture_starts_with_skill_path_acknowledgement(self) -> None:
        fixture = (SKILL_DIR / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        audit = 'echo "skills/azd-patterns/SKILL.md"'
        self.assertIn("## Step -1", fixture)
        self.assertIn(audit, fixture)
        self.assertLess(fixture.index(audit), fixture.index("## Environment available"))

    def test_fixture_asset_change_bumps_patch_version(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = yaml.safe_load(skill.split("---")[1])
        self.assertEqual(frontmatter["metadata"]["version"], "1.4.9")


if __name__ == "__main__":
    unittest.main()

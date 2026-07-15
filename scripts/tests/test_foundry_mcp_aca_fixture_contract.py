#!/usr/bin/env python3
"""Contract tests for the foundry-mcp-aca live fixture."""

from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT / "skills" / "foundry-mcp-aca" / "test-fixture" / "consumer_prompt.md"
)


class FoundryMcpAcaFixtureContractTests(unittest.TestCase):
    def test_fixture_acknowledges_skill_before_step_zero(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        acknowledgement = 'echo "skills/foundry-mcp-aca/SKILL.md"'

        self.assertIn("## Step -1", fixture)
        self.assertIn("Your first Bash action must be:", fixture)
        self.assertIn(acknowledgement, fixture)
        self.assertLess(fixture.index(acknowledgement), fixture.index("## Step 0"))


if __name__ == "__main__":
    unittest.main()

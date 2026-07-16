#!/usr/bin/env python3
"""Contract tests for the foundry-cost-monitoring live fixture."""

from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "skills"
    / "foundry-cost-monitoring"
    / "test-fixture"
    / "consumer_prompt.md"
)
SKILL_MD = ROOT / "skills" / "foundry-cost-monitoring" / "SKILL.md"
MARKER_PATH = "/tmp/foundry-cost-monitoring-smoke-result"
SKILL_PATH = "skills/foundry-cost-monitoring/SKILL.md"


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)


class FoundryCostMonitoringFixtureContractTests(unittest.TestCase):
    def test_success_marker_action_also_emits_skill_audit_evidence(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        marker_blocks = [
            block
            for block in _bash_blocks(fixture)
            if f"> {MARKER_PATH}" in block and "SMOKE_RESULT=PASS" in block
        ]

        self.assertEqual(len(marker_blocks), 1)
        marker_block = marker_blocks[0]
        self.assertIn(SKILL_PATH, marker_block)
        self.assertLess(
            marker_block.index(SKILL_PATH),
            marker_block.index("SMOKE_RESULT=PASS"),
        )

    def test_fixture_patch_version_is_bumped(self) -> None:
        frontmatter = SKILL_MD.read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn('version: "1.0.5"', frontmatter)


if __name__ == "__main__":
    unittest.main()

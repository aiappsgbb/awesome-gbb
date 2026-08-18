"""Contract tests for the foundry-rbac-audit live fixture."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "skills"
    / "foundry-rbac-audit"
    / "test-fixture"
    / "consumer_prompt.md"
)


class FoundryRbacAuditFixtureContractTests(unittest.TestCase):
    def test_first_action_is_completed_standalone_skill_breadcrumb(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)
        prose_before_first_block = fixture.split("```bash", 1)[0]

        self.assertTrue(bash_blocks)
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "skills/foundry-rbac-audit/SKILL.md"',
        )
        self.assertRegex(
            prose_before_first_block,
            r"separate\s+Bash\s+tool\s+call\s+containing\s+only",
        )
        self.assertRegex(
            prose_before_first_block,
            r"[Dd]o\s+not\s+combine",
        )
        self.assertRegex(
            prose_before_first_block,
            r"[Ww]ait\s+for\s+(?:that|the)\s+Bash\s+tool\s+call\s+to\s+complete"
            r"\s+before",
        )


if __name__ == "__main__":
    unittest.main()

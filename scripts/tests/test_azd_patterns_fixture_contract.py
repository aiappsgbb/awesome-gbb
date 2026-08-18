"""Contract tests for the azd-patterns live fixture."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills" / "azd-patterns" / "test-fixture" / "consumer_prompt.md"


class AzdPatternsFixtureContractTests(unittest.TestCase):
    def test_first_action_is_standalone_skill_breadcrumb(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        self.assertTrue(bash_blocks)
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "skills/azd-patterns/SKILL.md"',
        )
        self.assertIn(
            "Your first action must be a separate Bash tool call containing only",
            fixture,
        )


if __name__ == "__main__":
    unittest.main()

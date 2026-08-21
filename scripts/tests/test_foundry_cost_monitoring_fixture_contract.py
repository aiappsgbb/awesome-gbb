"""Regression contract for the foundry-cost-monitoring live fixture.

PR #464's force-full run 32174352090 exposed a contradictory prompt: it
required the agent to read SKILL.md first while also forbidding that read.
The agent tried to reconcile the conflict by editing the fixture in the CI
checkout, and the checkout-integrity guard correctly failed the leg.
"""

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


class FoundryCostMonitoringFixtureContractTests(unittest.TestCase):
    def test_fixture_is_self_contained_execution_only_and_read_only(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        for required in (
            "This is a self-contained EXECUTION smoke, not a catalog inspection.",
            "Run each applicable Bash code block only when its surrounding "
            "instructions apply.",
            "Execute Steps 0-4 in order, then run exactly one Step 5 marker block.",
            "Do NOT inspect repository files",
            "Do NOT create or modify tracked repository files.",
            "Do NOT open, read, view, or `cat` SKILL.md",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

        self.assertTrue(bash_blocks, "fixture must contain executable Bash blocks")
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "Executing consumer smoke for '
            'skills/foundry-cost-monitoring/SKILL.md"',
        )

        for forbidden in (
            "Do whatever the skill tells you to do.",
            "read the skill's `SKILL.md` first",
            "run every Bash code block below in order",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_flat)

    def test_fixture_contains_only_self_contained_bash_blocks(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fenced_languages = re.findall(r"^```([A-Za-z0-9_-]+)\s*$", fixture, re.MULTILINE)

        self.assertTrue(fenced_languages, "fixture must contain executable blocks")
        self.assertEqual(
            set(fenced_languages),
            {"bash"},
            "all executable fixture content must be self-contained Bash; "
            "Python belongs inside Bash heredocs",
        )


if __name__ == "__main__":
    unittest.main()

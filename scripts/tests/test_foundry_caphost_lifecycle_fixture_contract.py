"""Regression contract for the capability-host lifecycle live fixture."""

from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "skills"
    / "foundry-caphost-lifecycle"
    / "test-fixture"
    / "consumer_prompt.md"
)


class FoundryCaphostLifecycleFixtureContractTests(unittest.TestCase):
    def test_fixture_requires_execution_instead_of_catalog_review(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        for required in (
            "This is an EXECUTION smoke, not a catalog inspection.",
            "You MUST run every Bash code block below in order",
            "Do NOT inspect repo files",
            "do NOT run `validate-skills.py`",
            "Your only acceptable terminal state is a Bash tool call that writes",
            "/tmp/foundry-caphost-lifecycle-smoke-result",
            "never invoke `copilot` recursively",
            "Do NOT create or modify tracked repository files.",
            "The workflow has pre-provisioned shared CI infrastructure.",
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-caphost-lifecycle-smoke-result",
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > /tmp/foundry-caphost-lifecycle-smoke-result",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

        self.assertTrue(bash_blocks, "fixture must contain executable Bash blocks")
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "Executing consumer smoke for '
            'skills/foundry-caphost-lifecycle/SKILL.md"',
        )

        for forbidden in (
            "Do whatever the skill tells you to do.",
            "read the skill's `SKILL.md`",
            "ran catalog validation",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_flat)

    def test_dependent_bash_blocks_restore_lifecycle_state(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)
        state_source = "source /tmp/foundry-caphost-lifecycle-state.env"
        dependent_commands = (
            "az cognitiveservices account create",
            "STATE=$(az cognitiveservices account show",
            "python3 caphost_put.py",
            "az rest --method get",
            "python3 caphost_delete.py",
            "az cognitiveservices account delete",
            "FOUND=$(az cognitiveservices account list-deleted",
            "az cognitiveservices account purge",
            "STILL=$(az cognitiveservices account list-deleted",
        )

        self.assertIn(
            'STATE_FILE="/tmp/foundry-caphost-lifecycle-state.env"',
            fixture,
        )
        for block in bash_blocks:
            if any(command in block for command in dependent_commands):
                first_command = next(
                    line.strip()
                    for line in block.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                with self.subTest(first_command=first_command):
                    self.assertEqual(first_command, state_source)


if __name__ == "__main__":
    unittest.main()

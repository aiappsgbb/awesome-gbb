"""Guard the live fixture against being misread as repository-maintenance work."""

import unittest
from pathlib import Path


class ConsumerExecutionContractTests(unittest.TestCase):
    def test_live_execution_and_no_maintenance_are_explicit(self):
        fixture = (
            Path(__file__).resolve().parents[1] / "test-fixture/consumer_prompt.md"
        ).read_text()
        self.assertIn("authorized LIVE EXECUTION smoke", fixture)
        self.assertNotIn("execution fixture candidate", fixture)
        for boundary in (
            "not a catalog inspection",
            "real Skills API create/download/promote/delete calls",
            "run unrelated unittest/pytest",
            "Missing workflow inputs or API failures are a FAIL",
            "Your FIRST action must be this separate Bash tool call",
            "canonical program performs the final byte-exact result write",
        ):
            self.assertIn(boundary, fixture)
        first_bash = fixture.split("```bash\n", 1)[1].split("```", 1)[0].strip()
        self.assertEqual(
            first_bash, 'echo "skills/foundry-skill-catalog/SKILL.md"'
        )
        self.assertIn("python skills/foundry-skill-catalog/test-fixture/native_smoke.py", fixture)
        self.assertIn("Do not\nwrite a second program, override its marker", fixture)


if __name__ == "__main__":
    unittest.main()

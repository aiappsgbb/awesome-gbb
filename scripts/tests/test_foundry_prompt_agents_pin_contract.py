"""Contract tests for the prompt-agent validation environment."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "skills" / "foundry-prompt-agents" / "references" / "upstream-pin.md"
SKILL = ROOT / "skills" / "foundry-prompt-agents" / "SKILL.md"


class FoundryPromptAgentsPinContractTests(unittest.TestCase):
    def test_validation_installs_bounded_httpx_dependency(self) -> None:
        raw = PIN.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        script = yaml.safe_load(frontmatter)["validation"]["script"]

        self.assertIn('"httpx~=0.28.1"', script)

    def test_consumer_install_commands_match_validated_dependency_set(self) -> None:
        lines = [
            line
            for line in SKILL.read_text(encoding="utf-8").splitlines()
            if "pip install" in line and "azure-ai-projects" in line
        ]

        self.assertEqual(2, len(lines))
        for line in lines:
            with self.subTest(line=line):
                self.assertIn('"azure-ai-projects~=2.4.0"', line)
                self.assertIn('"azure-identity~=1.25.3"', line)
                self.assertIn('"httpx~=0.28.1"', line)


if __name__ == "__main__":
    unittest.main()

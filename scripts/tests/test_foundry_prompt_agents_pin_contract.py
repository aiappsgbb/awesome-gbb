"""Contract tests for the prompt-agent validation environment."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "skills" / "foundry-prompt-agents" / "references" / "upstream-pin.md"


class FoundryPromptAgentsPinContractTests(unittest.TestCase):
    def test_validation_installs_bounded_httpx_dependency(self) -> None:
        raw = PIN.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        script = yaml.safe_load(frontmatter)["validation"]["script"]

        self.assertIn('"httpx~=0.28.1"', script)


if __name__ == "__main__":
    unittest.main()

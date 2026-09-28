"""Memory retirement preserves navigation without advertising a callable skill."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_MEMORY = (
    "https://github.com/microsoft/azure-skills/blob/main/"
    ".github/plugins/azure-skills/skills/microsoft-foundry/foundry-agent/"
    "create/references/tools/prompt-agent/tool-memory.md"
)


class MemoryRetirementTests(unittest.TestCase):
    def test_retired_skill_is_not_registered_or_bundled(self) -> None:
        self.assertFalse((ROOT / "skills/foundry-memory").exists())
        dependencies = yaml.safe_load((ROOT / ".github/skill-deps.yml").read_text())
        self.assertNotIn("foundry-memory", dependencies["skills"])
        for entry in dependencies["skills"].values():
            self.assertNotIn("foundry-memory", entry["depends_on"])
        plugin = json.loads((ROOT / "plugin.json").read_text())
        self.assertGreaterEqual(int(plugin["version"].split(".")[0]), 5)
        self.assertEqual(plugin["skills"], "skills/")

    def test_existing_consumers_link_the_official_workflow(self) -> None:
        for skill in ("foundry-prompt-agents", "foundry-hosted-agents"):
            with self.subTest(skill=skill):
                text = (ROOT / "skills" / skill / "SKILL.md").read_text()
                self.assertIn(OFFICIAL_MEMORY, text)
                self.assertNotIn("| Memory across sessions | `foundry-memory` |", text)
                self.assertNotIn("(`foundry-memory`)", text)

    def test_site_preserves_retired_url_but_excludes_active_entry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build-site.py"),
                 "--out", str(output), "--validate"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            notice = (output / "skills/foundry-memory/index.html").read_text()
            self.assertIn("foundry-memory has been retired", notice)
            self.assertIn(OFFICIAL_MEMORY, notice)
            for page in ("index.html", "skills/index.html", "llms.txt",
                         "plugins/awesome-gbb/index.html"):
                with self.subTest(page=page):
                    self.assertNotIn("foundry-memory", (output / page).read_text())


if __name__ == "__main__":
    unittest.main()

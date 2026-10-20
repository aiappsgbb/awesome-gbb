"""Offline packaging contract for the html-deck-to-pptx skill.

The conversion itself needs Playwright and a browser, so CI checks the parts
that can regress silently: frontmatter, bundled files, a public-registry
lockfile, JavaScript syntax and the self-contained synthetic fixture.
"""

from pathlib import Path
import json
import re
import shutil
import subprocess
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "html-deck-to-pptx"
SCRIPTS = SKILL / "scripts"


class HtmlDeckToPptxContractTests(unittest.TestCase):
    def test_frontmatter_shape(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: html-deck-to-pptx\ndescription: >\n"))
        data = yaml.safe_load(text.split("---")[1])
        self.assertEqual(set(data), {"name", "description", "metadata"})
        self.assertRegex(data["metadata"]["version"], r"^[1-9]\d*\.\d+\.\d+$")
        description = data["description"]
        self.assertLessEqual(len(description), 1024)
        for phrase in ("USE FOR:", "DO NOT USE FOR:", "html to pptx", "gbb-pptx", "html-presentation"):
            self.assertIn(phrase, description)

    def test_bundled_files_and_no_dependencies_committed(self):
        for rel in (
            "references/fidelity.md",
            "references/last_validated.yaml",
            "scripts/html2pptx.mjs",
            "scripts/qa.mjs",
            "scripts/package.json",
            "scripts/package-lock.json",
            "tests/fixture/deck.html",
        ):
            self.assertTrue((SKILL / rel).is_file(), rel)
        tracked = subprocess.run(
            ["git", "ls-files", str(SKILL.relative_to(ROOT))],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
        self.assertNotIn("node_modules/", tracked)
        self.assertNotIn(".work/", tracked)

    def test_lockfile_resolves_from_public_registry(self):
        lock = json.loads((SCRIPTS / "package-lock.json").read_text(encoding="utf-8"))
        pkg = json.loads((SCRIPTS / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["packages"][""]["dependencies"], pkg["dependencies"])
        for name, entry in lock["packages"].items():
            if name:
                self.assertTrue(
                    entry["resolved"].startswith("https://registry.npmjs.org/"), name
                )
                self.assertTrue(entry["integrity"].startswith("sha512-"), name)

    def test_fixture_is_self_contained(self):
        html = (SKILL / "tests" / "fixture" / "deck.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'<section class="slide"', html)), 4)
        self.assertNotRegex(html, r'(src|href)="(https?:)?//(?!example\.com/)')
        for feature in ("linear-gradient", "<table>", "<ul>", "<ol", "<svg", 'class="notes"', 'href="#s4"'):
            self.assertIn(feature, html)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_scripts_parse(self):
        for path in sorted(SCRIPTS.rglob("*.mjs")):
            if "node_modules" in path.parts:
                continue
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{path}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()

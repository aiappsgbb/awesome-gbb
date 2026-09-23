"""Run the bundled persistence suite in the existing catalog unit-test job."""

import importlib.util
import json
import re
import runpy
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "progress-guard"


class ProgressGuardPackagingTests(unittest.TestCase):
    def test_frontmatter_and_reference_links(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: progress-guard\ndescription: >\n"))
        metadata = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(set(metadata), {"name", "description", "metadata"})
        self.assertEqual(metadata["metadata"]["version"], "1.1.0")
        self.assertTrue(200 <= len(metadata["description"]) <= 1024)
        self.assertIn("USE FOR:", metadata["description"])
        self.assertIn("DO NOT USE FOR:", metadata["description"])
        self.assertIn("(references/compaction.md)", text)
        for path in SKILL.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in link:
                    with self.subTest(path=path, link=link):
                        target = (path.parent / link.split("#")[0]).resolve()
                        self.assertTrue(target.is_file())
                        self.assertTrue(target.is_relative_to(SKILL))

    def test_catalog_keeps_compaction_acceptance_pending(self):
        site = runpy.run_path(str(ROOT / "scripts" / "build-site.py"))
        entry = next(s for s in site["load_skills"](ROOT) if s["name"] == SKILL.name)
        self.assertEqual(entry["draft"]["source_status"], "candidate")
        self.assertEqual(entry["draft"]["release_status"], "pending")
        record = entry["draft"]["record"]
        self.assertIn(record, site["PUBLISHED_DOCS"])
        text = (ROOT / "docs" / record).read_text(encoding="utf-8")
        self.assertIn("not been executed as observed agent trials", text)
        self.assertIn("1.1.0", text)
        plugin = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn(f'## {plugin["version"]}', (ROOT / "CHANGELOG.md").read_text())


def load_tests(loader, tests, pattern):
    path = (Path(__file__).resolve().parents[2] / "skills" / "progress-guard"
            / "tests" / "test_ledger.py")
    spec = importlib.util.spec_from_file_location("progress_guard_ledger_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests.addTests(loader.loadTestsFromModule(module))
    return tests

"""Execute the fixture's exact reader wiring with canonical synchronous helpers."""

import importlib.util
import inspect
import io
import re
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fixture_skill_packages", ROOT / "references/skill_packages.py"
)
READER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = READER
SPEC.loader.exec_module(READER)


class ConsumerReaderWiringTests(unittest.TestCase):
    def test_fixture_calls_sync_reader_and_unpacks_package_content(self):
        self.assertFalse(inspect.iscoroutinefunction(READER.download_catalog))
        self.assertFalse(inspect.iscoroutinefunction(READER.skill_archive))
        blocks = re.findall(
            r"```python\n(.*?)```",
            (ROOT / "test-fixture/consumer_prompt.md").read_text(),
            re.DOTALL,
        )
        self.assertEqual(len(blocks), 1)
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("SKILL.md", "# Fixture\nversion-one\n")
            package.writestr("assets/note.txt", b"synthetic asset")
        content = archive.getvalue()

        for selected_version in ("1", None):
            with self.subTest(selected_version=selected_version):
                operations = SimpleNamespace(
                    get=Mock(return_value=SimpleNamespace(name="fixture", default_version="1")),
                    get_version=Mock(
                        return_value=SimpleNamespace(name="fixture", version="1", description="fixture")
                    ),
                    download_version=Mock(return_value=iter([content[:20], content[20:]])),
                )
                namespace = {
                    "project": SimpleNamespace(beta=SimpleNamespace(skills=operations)),
                    "name": "fixture",
                    "selected_version": selected_version,
                    "expected_version": "1",
                    "download_catalog": READER.download_catalog,
                    "skill_archive": READER.skill_archive,
                }
                exec(compile(blocks[0], "consumer_prompt.md", "exec"), namespace)
                self.assertIsInstance(namespace["packages"], list)
                self.assertIsInstance(namespace["package"], READER.SkillPackage)
                self.assertIn("version-one", namespace["skill_md"])
                self.assertEqual(namespace["files"]["assets/note.txt"], b"synthetic asset")
                operations.get.assert_called_once_with("fixture")
                operations.get_version.assert_called_once_with("fixture", "1")
                operations.download_version.assert_called_once_with("fixture", "1")


if __name__ == "__main__":
    unittest.main()

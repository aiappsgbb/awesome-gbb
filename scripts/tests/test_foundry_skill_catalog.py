"""Behavior tests for the canonical Foundry Skills versioned consumer."""

from __future__ import annotations

import asyncio
import importlib.util
import io
import shutil
import subprocess
import sys
import types
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/foundry-skill-catalog/references"


class LegacyInlineSkill:
    def __init__(self, *, name, description, instructions):
        self.name = name
        self.description = description
        self.instructions = instructions


def archive(body="Version one", *, path="SKILL.md", extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as package:
        package.writestr(path, f"---\nname: greeting\ndescription: Greeting\n---\n{body}")
        for name, content in (extra or {}).items():
            package.writestr(name, content)
    return stream.getvalue()


def load_source():
    framework = types.ModuleType("agent_framework")
    framework.InlineSkill = LegacyInlineSkill
    framework.Skill = LegacyInlineSkill
    framework.SkillsSource = object
    framework.SkillFrontmatter = lambda **kwargs: types.SimpleNamespace(**kwargs)
    projects = types.ModuleType("azure.ai.projects")
    projects.AIProjectClient = MagicMock()
    name = "foundry_skills_source"
    spec = importlib.util.spec_from_file_location(name, REFERENCES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    with (
        patch.object(sys, "path", [str(REFERENCES), *sys.path]),
        patch.dict(sys.modules, {"agent_framework": framework, "azure.ai.projects": projects}),
    ):
        spec.loader.exec_module(module)
    return module


class FoundrySkillCatalogTests(unittest.TestCase):
    def setUp(self):
        self.module = load_source()
        self.parent = types.SimpleNamespace(
            name="greeting", description="Latest description", default_version="1", latest_version="2"
        )
        self.operations = Mock(spec=["list", "get", "get_version", "download_version", "download"])
        self.operations.list.return_value = [self.parent]
        self.operations.get.return_value = self.parent
        self.operations.get_version.side_effect = lambda name, version: types.SimpleNamespace(
            name=name, version=version, description=f"Description {version}"
        )
        self.operations.download_version.side_effect = lambda name, version: iter(
            [archive(f"Version {version}")]
        )
        self.project = types.SimpleNamespace(beta=types.SimpleNamespace(skills=self.operations))
        self.module.AIProjectClient.return_value.__enter__.return_value = self.project

    def collect(self, **kwargs):
        source = self.module.FoundrySkillsSource("https://example.invalid/project", object(), **kwargs)
        return asyncio.run(source.get_skills())

    def test_existing_constructor_follows_default_not_latest(self):
        result = self.collect()
        self.assertEqual(result[0].instructions, "Version 1")
        self.assertEqual(result[0].description, "Description 1")
        self.operations.download_version.assert_called_once_with("greeting", "1")
        self.operations.download.assert_not_called()

    def test_explicit_pin_reads_only_requested_skill_and_version(self):
        result = self.collect(skill_versions={"greeting": "2"})
        self.assertEqual(result[0].instructions, "Version 2")
        self.operations.list.assert_not_called()
        self.operations.get.assert_called_once_with("greeting")

    def test_empty_selection_does_not_read_the_project_catalog(self):
        self.assertEqual(self.collect(skill_versions={}), [])
        self.operations.list.assert_not_called()
        self.operations.get.assert_not_called()

    def test_new_load_observes_promotion_and_rollback(self):
        source = self.module.FoundrySkillsSource("https://example.invalid/project", object())
        for version in ("1", "2", "1"):
            self.parent.default_version = version
            self.assertEqual(asyncio.run(source.get_skills())[0].instructions, f"Version {version}")

    def test_native_inline_content_is_downloaded_without_has_blob(self):
        self.assertFalse(hasattr(self.parent, "has_blob"))
        self.assertEqual(self.collect()[0].instructions, "Version 1")

    def test_native_errors_do_not_fall_back_to_legacy_download(self):
        failure = RuntimeError("provider version download failed")
        self.operations.download_version.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            self.collect()
        self.assertIs(caught.exception, failure)
        self.operations.download.assert_not_called()

    def test_empty_default_is_not_replaced_by_latest(self):
        self.parent.default_version = ""
        with self.assertRaisesRegex(ValueError, "default_version"):
            self.collect()
        self.operations.download_version.assert_not_called()

    def test_invalid_pin_is_rejected_before_network(self):
        for value in ("", "latest", "1/../../2", 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.collect(skill_versions={"greeting": value})
        self.operations.get.assert_not_called()

    def test_missing_native_sdk_method_is_not_legacy_compatibility(self):
        self.operations.download_version = None
        with self.assertRaisesRegex(ValueError, "download_version"):
            self.collect()
        self.operations.download.assert_not_called()

    def test_mutating_callers_pin_mapping_does_not_change_existing_source(self):
        pins = {"greeting": "1"}
        source = self.module.FoundrySkillsSource("https://example.invalid/project", object(), skill_versions=pins)
        pins["greeting"] = "2"
        self.assertEqual(asyncio.run(source.get_skills())[0].instructions, "Version 1")

    def test_metadata_for_wrong_version_fails_closed(self):
        self.operations.get_version.side_effect = None
        self.operations.get_version.return_value = types.SimpleNamespace(
            name="greeting", version="99", description="Wrong"
        )
        with self.assertRaisesRegex(ValueError, "version"):
            self.collect()

    def test_legacy_zip_still_works_without_native_versions(self):
        self.operations.list.return_value = [
            types.SimpleNamespace(name="greeting", description="Legacy", has_blob=True)
        ]
        self.operations.download.return_value = iter([archive("Legacy body")])
        result = self.collect()
        self.assertEqual(result[0].instructions, "Legacy body")

    def test_legacy_json_placeholder_is_explicit_and_warns(self):
        self.operations.list.return_value = [
            types.SimpleNamespace(name="greeting", description="Legacy description", has_blob=False)
        ]
        with self.assertWarnsRegex(RuntimeWarning, "legacy"):
            result = self.collect()
        self.assertEqual(result[0].instructions, "Legacy description")
        self.operations.download.assert_not_called()

    def test_native_pin_cannot_silently_downgrade_to_legacy(self):
        self.operations.get.return_value = types.SimpleNamespace(
            name="greeting", description="Legacy", has_blob=True
        )
        with self.assertRaisesRegex(ValueError, "legacy"):
            self.collect(skill_versions={"greeting": "1"})

    def test_unrecognized_metadata_does_not_become_placeholder(self):
        self.operations.list.return_value = [types.SimpleNamespace(name="greeting", description="Unknown")]
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.collect()

    def test_download_failure_does_not_leave_partial_success(self):
        def interrupted():
            yield b"PK"
            raise RuntimeError("stream interrupted")
        self.operations.download_version.side_effect = lambda *args: interrupted()
        with self.assertRaisesRegex(RuntimeError, "stream interrupted"):
            self.collect()

    def test_only_exact_skill_filename_is_accepted(self):
        self.operations.download_version.side_effect = lambda *args: iter(
            [archive(path="not-SKILL.md")]
        )
        with self.assertRaisesRegex(ValueError, "SKILL.md"):
            self.collect()

    def test_ambiguous_archive_is_rejected(self):
        self.operations.download_version.side_effect = lambda *args: iter(
            [archive(extra={"other/SKILL.md": "Another body"})]
        )
        with self.assertRaisesRegex(ValueError, "SKILL.md"):
            self.collect()

    def test_zip_paths_cannot_escape_bundle_directory(self):
        self.operations.download_version.side_effect = lambda *args: iter(
            [archive(extra={"../escape.txt": "unsafe"})]
        )
        with self.assertRaisesRegex(ValueError, "path"):
            self.collect()

    def test_archive_symlinks_and_duplicate_files_fail_closed(self):
        for special in ("symlink", "duplicate"):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as package:
                package.writestr("SKILL.md", "Valid instructions")
                if special == "symlink":
                    entry = zipfile.ZipInfo("link")
                    entry.external_attr = 0o120777 << 16
                    package.writestr(entry, "../elsewhere")
                else:
                    with self.assertWarns(UserWarning):
                        package.writestr("SKILL.md", "Ambiguous instructions")
            self.operations.download_version.side_effect = lambda *args: iter([stream.getvalue()])
            with self.subTest(special=special), self.assertRaisesRegex(ValueError, "path"):
                self.collect()

    def test_current_maf_frontmatter_constructor_is_supported(self):
        class CurrentInlineSkill:
            def __init__(self, *, frontmatter, instructions):
                self.frontmatter = frontmatter
                self.instructions = instructions
        self.module.InlineSkill = CurrentInlineSkill
        result = self.collect()[0]
        self.assertEqual(result.frontmatter.name, "greeting")
        self.assertEqual(result.frontmatter.description, "Description 1")
        self.assertEqual(result.instructions, "Version 1")

    def load_bundler(self):
        spec = importlib.util.spec_from_file_location("sync_skills", REFERENCES / "sync_skills.py")
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "path", [str(REFERENCES), *sys.path]):
            spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, "bundle_skills", None)), "version-aware bundler missing")
        return module

    def test_native_bundle_uses_same_pinned_package_and_preserves_assets(self):
        module = self.load_bundler()
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        self.operations.download_version.side_effect = lambda *args: iter(
            [archive("Pinned bundle", path="greeting/SKILL.md", extra={"greeting/assets/example.txt": "asset"})]
        )
        try:
            result = module.bundle_skills(self.project, target, {"greeting": "1"})
            self.assertEqual(result, {"bundled": 1, "skipped_legacy": 0})
            self.assertIn("Pinned bundle", (target / "greeting/SKILL.md").read_text())
            self.assertEqual((target / "greeting/assets/example.txt").read_text(), "asset")
            self.operations.download_version.assert_called_once_with("greeting", "1")
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_bundle_download_failure_does_not_erase_existing_files(self):
        module = self.load_bundler()
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        (target / "greeting").mkdir(parents=True)
        (target / "greeting/SKILL.md").write_text("Keep original")
        self.operations.download_version.side_effect = RuntimeError("download failed")
        try:
            with self.assertRaisesRegex(RuntimeError, "download failed"):
                module.bundle_skills(self.project, target)
            self.assertEqual((target / "greeting/SKILL.md").read_text(), "Keep original")
        finally:
            shutil.rmtree(target)

    def test_bundler_preserves_explicit_legacy_skip_with_warning(self):
        module = self.load_bundler()
        self.operations.list.return_value = [
            types.SimpleNamespace(name="greeting", description="Legacy", has_blob=False)
        ]
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        try:
            with self.assertWarnsRegex(RuntimeWarning, "legacy"):
                result = module.bundle_skills(self.project, target)
            self.assertEqual(result, {"bundled": 0, "skipped_legacy": 1})
            self.assertFalse((target / "greeting").exists())
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_bundle_env_requires_json_object_not_null(self):
        module = self.load_bundler()
        self.assertTrue(callable(getattr(module, "selection_from_env", None)))
        self.assertIsNone(module.selection_from_env(None))
        self.assertEqual(module.selection_from_env("{}"), {})
        self.assertEqual(module.selection_from_env('{"greeting":null}'), {"greeting": None})
        for value in ("null", "[]", "false", '"greeting"'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.selection_from_env(value)

    def test_build_only_bundler_works_with_agent_framework_unavailable(self):
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        script = f"""
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, {str(REFERENCES)!r})
sys.modules["agent_framework"] = None
from sync_skills import bundle_skills
parent = SimpleNamespace(name="greeting", default_version="1")
ops = SimpleNamespace(
    get=lambda name: parent,
    get_version=lambda name, version: SimpleNamespace(
        name=name, version=version, description="Greeting"),
    download_version=lambda name, version: iter([{archive("Without MAF")!r}]),
)
result = bundle_skills(SimpleNamespace(beta=SimpleNamespace(skills=ops)),
                      Path({str(target)!r}), {{"greeting": "1"}})
assert result == {{"bundled": 1, "skipped_legacy": 0}}
assert "Without MAF" in (Path({str(target)!r}) / "greeting/SKILL.md").read_text()
assert "agent_framework" not in [name for name, value in sys.modules.items() if value is not None]
"""
        try:
            result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            shutil.rmtree(target, ignore_errors=True)

    def test_explicit_selection_rejects_stale_directories_without_writes(self):
        module = self.load_bundler()
        for selection in ({"greeting": "1"}, {}):
            target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
            for name in ("greeting", "old-skill"):
                (target / name).mkdir(parents=True)
                (target / name / "SKILL.md").write_text(f"Preserve {name}")
            (target / "notes.txt").write_text("User notes")
            before = {
                str(path.relative_to(target)): path.read_bytes()
                for path in target.rglob("*") if path.is_file()
            }
            try:
                with self.subTest(selection=selection):
                    with (
                        patch.object(Path, "write_bytes") as write_bytes,
                        patch.object(shutil, "rmtree") as remove_tree,
                        self.assertRaisesRegex(ValueError, "clean target"),
                    ):
                        module.bundle_skills(self.project, target, selection)
                    write_bytes.assert_not_called()
                    remove_tree.assert_not_called()
                    after = {
                        str(path.relative_to(target)): path.read_bytes()
                        for path in target.rglob("*") if path.is_file()
                    }
                    self.assertEqual(before, after)
            finally:
                shutil.rmtree(target)

    def test_explicit_empty_selection_accepts_clean_target_without_writes(self):
        module = self.load_bundler()
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        with patch.object(Path, "write_bytes") as write_bytes, patch.object(shutil, "rmtree") as remove_tree:
            self.assertEqual(module.bundle_skills(self.project, target, {}), {"bundled": 0, "skipped_legacy": 0})
        write_bytes.assert_not_called()
        remove_tree.assert_not_called()
        self.assertFalse(target.exists())

    def test_explicit_selection_rejects_root_skill_without_deleting_it(self):
        module = self.load_bundler()
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("Unselected root skill")
        try:
            with self.assertRaisesRegex(ValueError, "clean target"):
                module.bundle_skills(self.project, target, {})
            self.assertEqual((target / "SKILL.md").read_text(), "Unselected root skill")
        finally:
            shutil.rmtree(target)

    def test_legacy_skip_cannot_leave_preexisting_selected_skill_active(self):
        module = self.load_bundler()
        self.operations.get.return_value = types.SimpleNamespace(
            name="greeting", description="Legacy", has_blob=False
        )
        target = ROOT / ".scratch" / f"skill-catalog-test-{uuid.uuid4().hex}"
        (target / "greeting").mkdir(parents=True)
        (target / "greeting/SKILL.md").write_text("Old instructions")
        try:
            with self.assertWarns(RuntimeWarning), self.assertRaisesRegex(ValueError, "clean target"):
                module.bundle_skills(self.project, target, {"greeting": None})
            self.assertEqual((target / "greeting/SKILL.md").read_text(), "Old instructions")
        finally:
            shutil.rmtree(target)

    def test_documented_native_contract_replaces_blanket_legacy_claims(self):
        text = (REFERENCES.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("download_version", text)
        self.assertIn("default_version", text)
        self.assertIn("resources/read", text)
        self.assertIn("skill_versions=", text)
        self.assertNotIn("there is **no\nnative `version` field**", text)
        self.assertNotIn("## ⚠️ Hosted agents only (Prompt agents not supported)", text)


if __name__ == "__main__":
    unittest.main()

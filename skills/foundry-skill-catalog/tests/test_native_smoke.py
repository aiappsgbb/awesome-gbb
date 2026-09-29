"""Offline lifecycle/marker tests for the canonical Skills consumer program."""

import importlib.util
import base64
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from azure.core.exceptions import ResourceNotFoundError


ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "skills/foundry-skill-catalog/test-fixture/native_smoke.py"
SPEC = importlib.util.spec_from_file_location("native_skills_smoke", PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class NativeSkillsSmokeTests(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        self.skills = self.project.beta.skills
        self.skills.get.side_effect = [
            ResourceNotFoundError(), SimpleNamespace(default_version="1"),
            SimpleNamespace(default_version="2"), SimpleNamespace(default_version="1"),
            ResourceNotFoundError(),
        ]
        self.skills.create.side_effect = [SimpleNamespace(version="1"), SimpleNamespace(version="2")]
        self.skills.list_versions.return_value = [SimpleNamespace(version="1"), SimpleNamespace(version="2")]
        self.skills.create_from_files.return_value = SimpleNamespace(version="3")
        self.skills.delete_version.return_value = SimpleNamespace(deleted=True)
        self.skills.get_version.side_effect = ResourceNotFoundError()
        self.skills.delete.return_value = SimpleNamespace(deleted=True)

    def test_success_preserves_history_staging_and_canonical_reader_calls(self):
        with patch.object(smoke, "check_package") as check:
            smoke.smoke(self.project, "ci-smoke-skill-test")
        self.assertEqual([c.kwargs["default"] for c in self.skills.create.call_args_list], [True, False])
        self.assertEqual(check.call_count, 5)
        self.assertEqual(self.skills.delete_version.call_args.args, ("ci-smoke-skill-test", "2"))
        self.skills.delete.assert_called_once_with("ci-smoke-skill-test")
        archive = self.skills.create_from_files.call_args.kwargs["content"]
        self.assertIs(archive.default, False)
        body, files = smoke.skill_archive(base64.b64decode(archive.files[0][1]))
        self.assertIn("name: ci-smoke-skill-test", body)
        self.assertEqual(files["assets/note.txt"], b"synthetic asset\n")

    def test_existing_name_is_never_adopted_or_deleted(self):
        self.skills.get.side_effect = None
        with self.assertRaisesRegex(RuntimeError, "remains present"):
            smoke.smoke(self.project, "existing")
        self.skills.create.assert_not_called()
        self.skills.delete.assert_not_called()

    def test_original_failure_survives_cleanup_failure(self):
        self.skills.create.side_effect = [SimpleNamespace(version="1"), ValueError("primary")]
        self.skills.delete.side_effect = RuntimeError("cleanup")
        with self.assertRaisesRegex(ValueError, "primary"):
            smoke.smoke(self.project, "owned")
        self.skills.delete.assert_called_once_with("owned")

    def test_cleanup_failure_cannot_pass(self):
        self.skills.delete.return_value.deleted = False
        with patch.object(smoke, "check_package"), self.assertRaisesRegex(RuntimeError, "not acknowledged"):
            smoke.smoke(self.project, "owned")

    def test_failed_first_create_is_not_replayed_or_unconditionally_deleted(self):
        self.skills.create.side_effect = RuntimeError("unknown outcome")
        with self.assertRaisesRegex(RuntimeError, "unknown outcome"):
            smoke.smoke(self.project, "owned")
        self.skills.create.assert_called_once()
        self.skills.delete.assert_not_called()

    def test_main_marks_failure_without_leaking_exception_or_stale_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "marker"
            marker.write_text("SMOKE_RESULT=PASS\n")
            with patch.object(smoke, "Path", return_value=marker), \
                 patch.object(smoke, "DefaultAzureCredential", side_effect=ValueError("SECRET_CANARY")), \
                 patch("builtins.print") as output:
                self.assertEqual(smoke.main(), 1)
            self.assertEqual(marker.read_text(), "SMOKE_RESULT=FAIL native lifecycle ValueError\n")
            self.assertNotIn("SECRET_CANARY", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()

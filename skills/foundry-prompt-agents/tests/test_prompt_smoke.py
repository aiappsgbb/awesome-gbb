"""Exercise canonical classifier cleanup and failure paths without Azure calls."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import tempfile

from azure.core.exceptions import ResourceNotFoundError
import httpx
from openai import NotFoundError


PATH = Path(__file__).resolve().parents[1] / "test-fixture/prompt_smoke.py"
SPEC = importlib.util.spec_from_file_location("prompt_smoke", PATH)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class PromptSmokeTests(unittest.TestCase):
    def setUp(self):
        self.project = Mock()
        self.openai = Mock()
        self.project.agents.create_version.return_value = SimpleNamespace(name="ci-smoke-pa-test", version="1")
        self.project.agents.get_version.side_effect = ResourceNotFoundError()
        self.openai.conversations.create.return_value = SimpleNamespace(id="conversation-test")
        self.openai.conversations.retrieve.side_effect = NotFoundError(
            "gone", response=httpx.Response(404, request=httpx.Request("GET", "https://example.test")), body=None,
        )
        self.openai.responses.create.return_value = SimpleNamespace(output_text="billing")

    def test_success_invokes_exact_candidate_and_verifies_both_deletions(self):
        smoke.smoke(self.project, self.openai)
        self.assertEqual(
            self.openai.responses.create.call_args.kwargs["extra_body"]["agent_reference"]["version"], "1"
        )
        self.project.agents.delete_version.assert_called_once_with("ci-smoke-pa-test", "1")
        self.project.agents.get_version.assert_called_once_with("ci-smoke-pa-test", "1")
        self.openai.conversations.delete.assert_called_once_with("conversation-test")
        self.openai.conversations.retrieve.assert_called_once_with("conversation-test")

    def test_invalid_label_still_cleans_both_owned_resources(self):
        self.openai.responses.create.return_value.output_text = "unrecognized"
        with self.assertRaisesRegex(ValueError, "Invalid classifier"):
            smoke.smoke(self.project, self.openai)
        self.project.agents.delete_version.assert_called_once()
        self.openai.conversations.delete.assert_called_once()

    def test_invoke_failure_is_not_replayed_and_cleanup_runs(self):
        self.openai.responses.create.side_effect = RuntimeError("invoke failed")
        with self.assertRaisesRegex(RuntimeError, "invoke failed"):
            smoke.smoke(self.project, self.openai)
        self.openai.responses.create.assert_called_once()
        self.project.agents.delete_version.assert_called_once()
        self.openai.conversations.delete.assert_called_once()

    def test_conversation_failure_cleans_only_created_agent_version(self):
        self.openai.conversations.create.side_effect = RuntimeError("create failed")
        with self.assertRaisesRegex(RuntimeError, "create failed"):
            smoke.smoke(self.project, self.openai)
        self.project.agents.delete_version.assert_called_once()
        self.openai.conversations.delete.assert_not_called()

    def test_cleanup_error_does_not_prevent_other_cleanup_or_pass(self):
        self.openai.conversations.delete.side_effect = RuntimeError("cleanup failed")
        with self.assertRaisesRegex(RuntimeError, "cleanup failed"):
            smoke.smoke(self.project, self.openai)
        self.project.agents.delete_version.assert_called_once()

    def test_existing_resource_after_delete_is_failure(self):
        for resource in ("agent", "conversation"):
            with self.subTest(resource=resource):
                self.setUp()
                if resource == "agent":
                    self.project.agents.get_version.side_effect = None
                else:
                    self.openai.conversations.retrieve.side_effect = None
                with self.assertRaisesRegex(RuntimeError, "deletion not verified"):
                    smoke.smoke(self.project, self.openai)

    def test_main_failure_overwrites_stale_pass_without_exception_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / "result"
            marker.write_text("SMOKE_RESULT=PASS\n")
            with patch.object(smoke, "Path", return_value=marker), \
                 patch.object(smoke, "DefaultAzureCredential", side_effect=ValueError("SECRET_CANARY")), \
                 patch("builtins.print") as output:
                self.assertEqual(smoke.main(), 1)
            self.assertEqual(marker.read_text(), "SMOKE_RESULT=FAIL ValueError\n")
            self.assertNotIn("SECRET_CANARY", str(output.call_args_list))


if __name__ == "__main__":
    unittest.main()

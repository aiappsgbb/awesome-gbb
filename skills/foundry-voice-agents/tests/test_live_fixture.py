import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "test-fixture"))
sys.path.insert(0, str(ROOT / "references/python"))
import live_acceptance
from definition import Consent
from main import verify_context
from session import SessionEvidence, save_pcm
from synthetic_audio import synthesize


class LiveFixtureTests(unittest.TestCase):
    def test_context_guard_rejects_missing_or_mismatched_scope(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                verify_context()
        environment = {
            "AZURE_CONFIG_DIR": "/approved/azure", "AZD_CONFIG_DIR": "/approved/azd",
            "AZURE_TENANT_ID": "tenant", "AZURE_SUBSCRIPTION_ID": "subscription",
        }
        with patch.dict("os.environ", environment, clear=True), \
             patch("main.subprocess.check_output", return_value='{"tenantId":"other","id":"subscription"}'):
            with self.assertRaises(RuntimeError):
                verify_context()
        with patch.dict("os.environ", environment, clear=True), \
             patch("main.subprocess.check_output", return_value='{"tenantId":"tenant","id":"subscription"}'):
            verify_context()

    def test_synthetic_http_failure_does_not_save_response_body(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch("synthetic_audio.requests.post") as request:
            request.return_value.status_code = 403
            request.return_value.content = b"not audio, sensitive error body"
            credential = MagicMock()
            credential.get_token.return_value.token = "synthetic-token"
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                synthesize(Path(temporary), "https://example.cognitiveservices.azure.com",
                           "/subscriptions/example/providers/Microsoft.CognitiveServices/accounts/example",
                           credential)
            self.assertEqual(list(Path(temporary).iterdir()), [])
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
            self.assertEqual(request.call_args.kwargs["timeout"], (10, 45))

    def test_live_runner_has_explicit_approval_gate(self):
        args = argparse.Namespace(approve_live_synthetic=False)
        with patch.object(live_acceptance, "verify_context") as verify:
            with self.assertRaises(PermissionError):
                live_acceptance.run(args)
            verify.assert_not_called()

    def test_partial_synthesis_failure_closes_local_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "evidence"
            args = argparse.Namespace(
                approve_live_synthetic=True,
                endpoint="https://example.services.ai.azure.com/api/projects/example",
                evidence_dir=directory, speech_endpoint="https://example.cognitiveservices.azure.com",
                account_id="/subscriptions/example/providers/Microsoft.CognitiveServices/accounts/example",
                model="gpt-realtime",
            )
            def fail_after_file(*_, **__):
                save_pcm(directory / "hours.wav", b"\x01\x00", Consent(save_local_audio=True))
                raise RuntimeError("synthetic request failed")
            with patch.object(live_acceptance, "verify_context"), \
                 patch.object(live_acceptance, "require_no_telemetry"), \
                 patch.object(live_acceptance, "AzureCliCredential"), \
                 patch.object(live_acceptance, "AIProjectClient") as client, \
                 patch.object(live_acceptance, "synthesize", side_effect=fail_after_file):
                with self.assertRaisesRegex(RuntimeError, "Voice acceptance failed"):
                    live_acceptance.run(args)
                client.return_value.__enter__.return_value.agents.create_version.assert_not_called()
            inventory = json.loads((directory / "inventory.json").read_text())
            self.assertEqual(inventory["functional"], "fail")
            self.assertEqual(inventory["cleanup"], "verified_absent")
            self.assertEqual(inventory["agents"], [])
            self.assertTrue(inventory["source_sha256"])
            self.assertFalse((directory / "hours.wav").exists())

    def test_privacy_preflight_refuses_account_or_project_binding(self):
        account = "/subscriptions/example/resourceGroups/example/providers/Microsoft.CognitiveServices/accounts/example"
        endpoint = "https://example.services.ai.azure.com/api/projects/example"
        speech = "https://example.cognitiveservices.azure.com"
        absent = MagicMock(status_code=200)
        absent.json.return_value = {"value": []}
        bound = MagicMock(status_code=200)
        bound.json.return_value = {"value": [{"properties": {"category": "AppInsights"}}]}
        with patch.dict("os.environ", {"AZURE_SUBSCRIPTION_ID": "example"}):
            for responses in ([bound], [absent, bound]):
                with patch("live_acceptance.requests.get", side_effect=responses):
                    with self.assertRaises(PermissionError):
                        live_acceptance.require_no_telemetry(MagicMock(), account, endpoint, speech)
            with patch("live_acceptance.requests.get", side_effect=[absent, absent]) as request:
                live_acceptance.require_no_telemetry(MagicMock(), account, endpoint, speech)
                self.assertEqual(request.call_count, 2)
            with self.assertRaises(ValueError):
                live_acceptance.require_no_telemetry(MagicMock(), account, endpoint, "https://other.cognitiveservices.azure.com")

    def test_metadata_excludes_audio_and_transcript(self):
        collector = MagicMock()
        collector.evidence = SessionEvidence(
            audio=b"private", output_transcripts=["synthetic speech"], reply_transcript="final speech"
        )
        result = live_acceptance.evidence_metadata(collector)
        self.assertNotIn("audio", result)
        self.assertNotIn("reply_transcript", result)
        self.assertNotIn("output_transcripts", result)
        self.assertEqual(len(result["transcript_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()

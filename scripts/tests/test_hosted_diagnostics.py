"""Replay the diagnostic shell with inert CLI/HTTP executables."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/foundry-hosted-agents/references/bash/diagnose_server_error.sh"


class HostedDiagnosticTests(unittest.TestCase):
    def run_script(self, *, authorize=False, evidence_exists=True):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            evidence = root / "evidence"
            if evidence_exists:
                evidence.mkdir(mode=0o700)
            log = root / "calls.jsonl"
            stub = (
                f"#!{sys.executable}\n"
                "import json,os,pathlib,sys\n"
                "args=sys.argv[1:]\n"
                "with open(os.environ['STUB_CALLS'],'a') as f: f.write(json.dumps([pathlib.Path(sys.argv[0]).name,args])+'\\n')\n"
                "if pathlib.Path(sys.argv[0]).name=='az':\n"
                " if 'get-access-token' in args: print('unit-test-token')\n"
                " elif 'show' in args: print('https://example.cognitiveservices.azure.com')\n"
                " else: print('metadata')\n"
                "else:\n"
                " assert '--connect-timeout' in args and '--max-time' in args\n"
                " pathlib.Path(args[args.index('-o')+1]).write_text('private-test-payload')\n"
                " pathlib.Path(args[args.index('-D')+1]).write_text('x-request-id: test-request')\n"
                " print('429',end='')\n"
            )
            for name in ("az", "curl"):
                executable = bin_dir / name
                executable.write_text(stub)
                executable.chmod(0o700)
            env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                   "AZURE_RESOURCE_GROUP": "example", "FOUNDRY_ACCOUNT": "example",
                   "MODEL_DEPLOYMENT_NAME": "example", "STUB_CALLS": str(log),
                   "DIAGNOSTIC_EVIDENCE_DIR": str(evidence)}
            env.pop("APPINSIGHTS_RESOURCE_ID", None)
            env["ALLOW_NEW_MODEL_PROBE"] = "yes" if authorize else "no"
            result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=10)
            calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
            captures = [(p.name, p.stat().st_mode & 0o777) for p in evidence.glob("*")] if evidence.exists() else []
            return result, calls, captures

    def test_default_metadata_does_not_dispatch_new_inference(self):
        result, calls, captures = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([name for name, _ in calls], ["az"])
        self.assertEqual(captures, [])
        self.assertIn("No new inference authorized", result.stdout)

    def test_authorized_new_probe_has_deadlines_and_private_raw_capture(self):
        result, calls, captures = self.run_script(authorize=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sum(name == "curl" for name, _ in calls), 1)
        self.assertEqual(len(captures), 2)
        self.assertTrue(all(mode == 0o600 for _, mode in captures))
        self.assertNotIn("private-test-payload", result.stdout)
        self.assertIn("original failure cause is not established", result.stdout)

    def test_missing_evidence_directory_blocks_before_cli(self):
        result, calls, captures = self.run_script(evidence_exists=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [])
        self.assertEqual(captures, [])

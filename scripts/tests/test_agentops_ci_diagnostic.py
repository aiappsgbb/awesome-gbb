"""Offline tests for the encrypted AgentOps Doctor diagnostic transport."""

from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "agentops-ci-diagnostic.py"
AGE = Path(os.environ.get("AGENTOPS_TEST_AGE_BIN") or shutil.which("age") or "/opt/homebrew/bin/age")
AGE_KEYGEN = Path(
    os.environ.get("AGENTOPS_TEST_AGE_KEYGEN_BIN")
    or shutil.which("age-keygen")
    or "/opt/homebrew/bin/age-keygen"
)
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
PLAINTEXT_CANARY = "PLAINTEXT_DIAGNOSTIC_CANARY"
STDERR_CANARY = "SUBPROCESS_STDERR_CANARY"

preflight_spec = importlib.util.spec_from_file_location(
    "diagnostic_preflight_fixtures", ROOT / "scripts/tests/test_agentops_ci_preflight.py"
)
preflight_fixtures = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_fixtures)


@unittest.skipUnless(sys.platform == "linux", "age execution requires Linux sealed memfd support")
@unittest.skipUnless(
    AGE.is_file() and AGE_KEYGEN.is_file(),
    "age v1.3.2 and age-keygen are required for diagnostic transport tests",
)
class AgentOpsCiDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diag = None
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location("agentops_ci_diagnostic", SCRIPT)
            cls.diag = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.diag)

    def setUp(self):
        self.assertIsNotNone(self.diag, "The AgentOps CI diagnostic transport is missing")
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.scratch = ROOT / ".artifacts" / ("agentops-diagnostic-" + uuid.uuid4().hex)
        self.scratch.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, self.scratch)
        self.private = self.scratch / "agentops-ci-98765-1"
        self.public = self.scratch / "agentops-ci-public-98765-1"
        self.private.mkdir(mode=0o700)
        self.public.mkdir(mode=0o700)
        self.tools = self.private / "tools"
        self.tools.mkdir(mode=0o700)
        self.age = self.tools / "age"
        shutil.copyfile(AGE, self.age)
        self.age.chmod(0o700)

        self.identity = self.scratch / "offline-identity.txt"
        generated = subprocess.run(
            [str(AGE_KEYGEN), "-o", str(self.identity)],
            check=True,
            capture_output=True,
            text=True,
            env={"PATH": os.defpath},
        )
        self.identity.chmod(0o600)
        self.recipient = next(
            line.split(":", 1)[1].strip()
            for line in generated.stderr.splitlines()
            if line.startswith("Public key:")
        )

        self.record = preflight_fixtures.diagnostic_approval_record()
        self.record["diagnostic"]["recipient"] = self.recipient
        self.record["diagnostic"]["fingerprint"] = "sha256:" + hashlib.sha256(
            self.recipient.encode("ascii")
        ).hexdigest()
        self.record["diagnostic"]["head_sha"] = "d" * 40
        self.approval_raw = (json.dumps(self.record, indent=2) + "\n").encode()
        self.approval = self.private / "owner-approval.json"
        self.approval.write_bytes(self.approval_raw)
        self.approval.chmod(0o600)

        auth = self.record["authorization"]
        self.event = {
            "action": "synchronize",
            "number": auth["pull_request"],
            "repository": {"full_name": auth["repository"]},
            "pull_request": {
                "number": auth["pull_request"],
                "head": {
                    "ref": auth["head_branch"],
                    "sha": self.record["diagnostic"]["head_sha"],
                    "repo": {"full_name": auth["repository"]},
                },
                "base": {"repo": {"full_name": auth["repository"]}},
                "labels": [{"name": "agentops-diagnostic"}],
            },
        }
        self.event_path = self.scratch / "event.json"
        self.event_path.write_text(json.dumps(self.event))
        self.event_path.chmod(0o600)
        self.env = {
            "PATH": "/definitely/not/the/age/path",
            "RUNNER_TEMP": str(self.scratch),
            "GITHUB_RUN_ID": "98765",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_REPOSITORY": auth["repository"],
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_EVENT_PATH": str(self.event_path),
            "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON": self.approval_raw.decode(),
            "AGENTOPS_CI_AGE_BIN": str(self.age),
            "AGENTOPS_CI_AGE_SHA256": hashlib.sha256(self.age.read_bytes()).hexdigest(),
            "APPLICATIONINSIGHTS_CONNECTION_STRING": (
                "InstrumentationKey=11111111-2222-3333-4444-555555555555;"
                "IngestionEndpoint=https://example.invalid/;"
                "SharedAccessKey=service-bus-component-secret;"
                "SharedAccessSignature=connstring-secret"
            ),
            "COPILOT_PROVIDER_BEARER_TOKEN": "provider-secret-token",
            "AZURE_CLIENT_SECRET": "azure-client-secret",
            "AZURE_CLIENT_CERTIFICATE_PASSWORD": "certificate-password",
            "AZURE_OPENAI_API_KEY": "azure-openai-key",
            "OPENAI_API_KEY": "openai-key",
            "GH_TOKEN": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
            "GITHUB_TOKEN": "github-token-value",
        }
        self.workspace_key = uuid.uuid4().hex
        self.workspace = self.private / "workspaces" / self.workspace_key
        self.attempt = self.private / "attempts" / "primary"
        self.workspace.mkdir(parents=True, mode=0o700)
        self.attempt.mkdir(parents=True, mode=0o700)
        self.write(self.attempt / "workspace-pointer", self.workspace_key + "\n")
        self.log = self.workspace / ".agentops/agent/doctor-command.log"

    @staticmethod
    def write(path, value, *, binary=False):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if binary:
            path.write_bytes(value)
        else:
            path.write_text(value)
        path.chmod(0o600)

    def cli(self, action, *, runner=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        kwargs = {"environ": self.env, "now": NOW}
        if runner is not None:
            kwargs["run"] = runner
        with patch.dict(os.environ, self.env, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = self.diag.main([action], **kwargs)
        output = stdout.getvalue() + stderr.getvalue()
        for canary in (PLAINTEXT_CANARY, STDERR_CANARY, "provider-secret-token"):
            self.assertNotIn(canary, output)
        return subprocess.CompletedProcess([action], status, stdout.getvalue(), stderr.getvalue())

    def export(self, text, *, runner=None):
        self.write(self.log, text)
        return self.cli("export", runner=runner)

    def decrypt(self):
        result = subprocess.run(
            [str(AGE), "--decrypt", "-i", str(self.identity), str(self.public / "doctor-log.age")],
            check=True,
            capture_output=True,
            text=True,
            env={"PATH": os.defpath},
        )
        return result.stdout

    def assert_finite_failure(self, result, action, code):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, f"AGENTOPS_CI_DIAGNOSTIC=FAIL {action.upper()} {code}\n")
        self.assertEqual(result.stderr, "")
        self.assertFalse((self.public / "doctor-log.age").exists())
        self.assertFalse((self.public / "diagnostic.json").exists())

    def rewrite_record(self):
        self.approval_raw = (json.dumps(self.record, indent=2) + "\n").encode()
        self.approval.write_bytes(self.approval_raw)
        self.approval.chmod(0o600)
        self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"] = self.approval_raw.decode()
        self.event_path.write_text(json.dumps(self.event))
        self.event_path.chmod(0o600)

    def test_check_validates_without_publishing_or_creating_keys(self):
        before = sorted(str(path.relative_to(self.private)) for path in self.private.rglob("*"))
        result = self.cli("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "AGENTOPS_CI_DIAGNOSTIC=PASS CHECK\n")
        self.assertEqual(list(self.public.iterdir()), [])
        self.assertEqual(
            before, sorted(str(path.relative_to(self.private)) for path in self.private.rglob("*"))
        )

    def test_export_real_age_roundtrip_redacts_secrets_and_preserves_useful_error(self):
        approval_escaped = json.dumps(self.approval_raw.decode())[1:-1]
        approval_encoded = __import__("urllib.parse", fromlist=["quote"]).quote(
            self.approval_raw.decode(), safe=""
        )
        toxic = "\n".join(
            (
                "Doctor failed while checking vector index: useful synthetic exception",
                "Authorization: Bearer bearer-value",
                'Authorization: Basic dXNlcjpwYXNz',
                "2026-09-05T12:34:56Z DEBUG Basic prefixed-basic-secret useful debug credential detail",
                "2026-09-05T12:34:57Z DEBUG Bearer prefixed-bearer-secret useful debug credential detail",
                "2026-09-05T12:34:58Z DEBUG basic dXNlcjpwYXNz useful lowercase credential detail",
                "Error: Basic error-prefixed-basic-secret useful error credential detail",
                "Error: Bearer error-prefixed-bearer-secret useful error credential detail",
                "Error: bEaReR opaque-secret useful mixed-case credential detail",
                "Basic standalone-basic-secret useful standalone credential detail",
                "Bearer standalone-bearer-secret useful standalone credential detail",
                "notBearer delimiter-canary useful delimiter exception",
                '{"authorization":"Bearer json-bearer","api-key":"json-api-key"}',
                "token=generic-token-secret; useful token exception",
                "github_token=github-field-secret, useful github exception",
                "SAS=sas-field-secret} useful SAS exception",
                "access_token=access-value refresh_token: refresh-value",
                'client_secret="field-client-secret" password=field-password',
                '{"clientSecret":"camel secret","accessToken":"camel-access"}',
                "AccountKey=account-key;InstrumentationKey=standalone-ikey",
                "SharedAccessKey=service-bus-secret",
                "SharedAccessSignature=standalone-sas",
                "service-bus-component-secret connstring-secret",
                "https://service.invalid/resource?sv=1&sig=sas-signature-secret&se=tomorrow",
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature",
                "github_pat_11AA22BB33CC44DD55EE66FF77GG88HH99II",
                "AGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ",
                "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----",
                self.env["APPLICATIONINSIGHTS_CONNECTION_STRING"],
                "InstrumentationKey=11111111-2222-3333-4444-555555555555",
                "provider-secret-token azure-client-secret certificate-password",
                "azure-openai-key openai-key ghp_abcdefghijklmnopqrstuvwxyz1234567890",
                "github-token-value",
                '{"password":"pw\\\\\\"password-suffix-canary\\\\\\\\tail","token":"tok\\\\\\"token-suffix-canary\\\\\\\\tail","api_key":"api\\\\\\"api-key-suffix-canary\\\\\\\\tail"} useful escaped quote detail',
                self.approval_raw.decode(),
                approval_escaped,
                approval_encoded,
            )
        )
        result = self.export(toxic + "\n")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, "AGENTOPS_CI_DIAGNOSTIC=PASS EXPORT\n")
        cipher = (self.public / "doctor-log.age").read_bytes()
        self.assertTrue(cipher.startswith(b"age-encryption.org/v1\n"))
        plaintext = self.decrypt()
        self.assertIn(
            "Doctor failed while checking vector index: useful synthetic exception", plaintext
        )
        self.assertIn("[REDACTED]", plaintext)
        for secret in (
            "bearer-value",
            "dXNlcjpwYXNz",
            "standalone-basic-secret",
            "standalone-bearer-secret",
            "prefixed-basic-secret",
            "prefixed-bearer-secret",
            "error-prefixed-basic-secret",
            "error-prefixed-bearer-secret",
            "opaque-secret",
            "json-bearer",
            "json-api-key",
            "generic-token-secret",
            "github-field-secret",
            "sas-field-secret",
            "access-value",
            "refresh-value",
            "field-client-secret",
            "field-password",
            "camel secret",
            "camel-access",
            "account-key",
            "standalone-ikey",
            "service-bus-secret",
            "service-bus-component-secret",
            "connstring-secret",
            "standalone-sas",
            "sas-signature-secret",
            "eyJhbGci",
            "github_pat_",
            "AGE-SECRET-KEY",
            "private-material",
            "11111111-2222-3333-4444-555555555555",
            "provider-secret-token",
            "azure-client-secret",
            "certificate-password",
            "azure-openai-key",
            "openai-key",
            "ghp_",
            "github-token-value",
            "password-suffix-canary",
            "token-suffix-canary",
            "api-key-suffix-canary",
            '"schema_version"',
            "%7B",
        ):
            self.assertNotIn(secret, plaintext)
        for useful in (
            "2026-09-05T12:34:56Z DEBUG Basic [REDACTED] useful debug credential detail",
            "2026-09-05T12:34:57Z DEBUG Bearer [REDACTED] useful debug credential detail",
            "2026-09-05T12:34:58Z DEBUG basic [REDACTED] useful lowercase credential detail",
            "Error: Basic [REDACTED] useful error credential detail",
            "Error: Bearer [REDACTED] useful error credential detail",
            "Error: bEaReR [REDACTED] useful mixed-case credential detail",
            "useful standalone credential detail",
            "notBearer delimiter-canary useful delimiter exception",
            "useful token exception",
            "useful github exception",
            "useful SAS exception",
            "useful escaped quote detail",
        ):
            self.assertIn(useful, plaintext)
        metadata = json.loads((self.public / "diagnostic.json").read_text())
        self.assertEqual(
            set(metadata),
            {
                "schema_version",
                "artifact",
                "ciphertext_sha256",
                "ciphertext_size",
                "redaction_count",
                "redaction_occurred",
                "native_prefix",
            },
        )
        self.assertEqual(metadata["schema_version"], 1)
        self.assertEqual(metadata["artifact"], "doctor-log.age")
        self.assertEqual(metadata["ciphertext_sha256"], hashlib.sha256(cipher).hexdigest())
        self.assertEqual(metadata["ciphertext_size"], len(cipher))
        self.assertGreater(metadata["redaction_count"], 15)
        self.assertIs(metadata["redaction_occurred"], True)
        self.assertIn(metadata["native_prefix"], self.diag.NATIVE_PREFIXES)
        serialized = json.dumps(metadata)
        self.assertNotIn("useful synthetic", serialized)
        self.assertNotIn(str(self.private), serialized)

    def test_export_reads_only_primary_fixed_doctor_log(self):
        retry = self.private / "attempts/retry"
        retry.mkdir(mode=0o700)
        other_key = uuid.uuid4().hex
        other_workspace = self.private / "workspaces" / other_key
        other_workspace.mkdir(mode=0o700)
        self.write(retry / "workspace-pointer", other_key + "\n")
        self.write(other_workspace / ".agentops/agent/doctor-command.log", PLAINTEXT_CANARY)
        result = self.export("primary useful diagnostic\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.decrypt(), "primary useful diagnostic\n")

    def test_subprocess_receives_only_minimal_noncredential_environment(self):
        seen = []

        def recording_run(*args, **kwargs):
            seen.append(dict(kwargs.get("env", {})))
            return subprocess.run(*args, **kwargs)

        result = self.export("safe diagnostic\n", runner=recording_run)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertGreaterEqual(len(seen), 3)
        for child_env in seen:
            self.assertEqual(set(child_env), {"PATH", "LANG", "LC_ALL"})
            self.assertFalse(set(child_env) & self.diag.SECRET_ENV_NAMES)

    def test_rejects_v1_approval(self):
        self.record = preflight_fixtures.approval_record()
        self.rewrite_record()
        self.assert_finite_failure(self.cli("check"), "check", "APPROVAL")

    def test_rejects_approval_byte_mismatch(self):
        self.env["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"] = self.approval_raw.decode() + " "
        self.assert_finite_failure(self.cli("check"), "check", "APPROVAL_MISMATCH")

    def test_rejects_context_head_attempt_and_label_mismatch(self):
        cases = (
            ("head", lambda: self.event["pull_request"]["head"].update({"sha": "e" * 40})),
            ("attempt", lambda: self.env.update({"GITHUB_RUN_ATTEMPT": "2"})),
            ("label", lambda: self.event["pull_request"].update({"labels": [{"name": "other"}]})),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                saved_event, saved_attempt = json.loads(json.dumps(self.event)), self.env["GITHUB_RUN_ATTEMPT"]
                mutate()
                self.event_path.write_text(json.dumps(self.event))
                self.assert_finite_failure(self.cli("check"), "check", "CI_CONTEXT")
                self.event, self.env["GITHUB_RUN_ATTEMPT"] = saved_event, saved_attempt
                self.event_path.write_text(json.dumps(self.event))

    def test_rejects_noncanonical_diagnostic_policy(self):
        for field, value in (("enabled", False), ("mode", "plaintext"), ("run_attempt", 2)):
            with self.subTest(field=field):
                original = self.record["diagnostic"][field]
                self.record["diagnostic"][field] = value
                self.rewrite_record()
                self.assert_finite_failure(self.cli("check"), "check", "APPROVAL")
                self.record["diagnostic"][field] = original
                self.rewrite_record()

    def test_missing_binary_never_falls_back_to_path(self):
        self.age.unlink()
        self.assert_finite_failure(self.cli("check"), "check", "AGE_BINARY")

    def test_rejects_binary_path_outside_fixed_tools_location(self):
        self.env["AGENTOPS_CI_AGE_BIN"] = str(AGE)
        self.assert_finite_failure(self.cli("check"), "check", "AGE_PATH")

    def test_rejects_binary_symlink_hardlink_and_wrong_mode(self):
        original = self.age.read_bytes()
        for kind in ("symlink", "hardlink", "mode"):
            with self.subTest(kind=kind):
                self.age.unlink()
                if kind == "symlink":
                    self.age.symlink_to(AGE)
                elif kind == "hardlink":
                    hardlink_target = self.scratch / "age-hardlink-target"
                    hardlink_target.write_bytes(original)
                    hardlink_target.chmod(0o700)
                    os.link(hardlink_target, self.age)
                else:
                    self.age.write_bytes(original)
                    self.age.chmod(0o755)
                self.assert_finite_failure(self.cli("check"), "check", "AGE_BINARY")
                if self.age.exists() or self.age.is_symlink():
                    self.age.unlink()
                self.age.write_bytes(original)
                self.age.chmod(0o700)

    def test_rejects_binary_over_size_bound_before_invocation(self):
        self.age.write_bytes(b"x" * (self.diag.MAX_AGE_BYTES + 1))
        self.age.chmod(0o700)
        self.env["AGENTOPS_CI_AGE_SHA256"] = hashlib.sha256(self.age.read_bytes()).hexdigest()
        self.assert_finite_failure(self.cli("check"), "check", "AGE_BINARY")

    def test_rejects_binary_hash_and_version_mismatch(self):
        self.env["AGENTOPS_CI_AGE_SHA256"] = "0" * 64
        self.assert_finite_failure(self.cli("check"), "check", "AGE_HASH")
        self.env["AGENTOPS_CI_AGE_SHA256"] = hashlib.sha256(self.age.read_bytes()).hexdigest()

        real_run = subprocess.run

        def wrong_version(argv, **kwargs):
            if argv[1:] == ["--version"]:
                return subprocess.CompletedProcess(argv, 0, b"v1.3.1\n", b"")
            return real_run(argv, **kwargs)

        self.assert_finite_failure(self.cli("check", runner=wrong_version), "check", "AGE_VERSION")

    def test_executes_sealed_verified_bytes_when_age_path_is_replaced(self):
        capture = self.scratch / "replacement-capture"
        replacement = self.scratch / "replacement-age"
        replacement.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> '{capture}'\n"
            "if [ \"$1\" = \"--version\" ]; then\n"
            "  printf 'v1.3.2\\n'\n"
            "else\n"
            f"  cat >> '{capture}'\n"
            "  printf 'age-encryption.org/v1\\nreplacement\\n'\n"
            "fi\n"
        )
        replacement.chmod(0o700)
        observations = []

        def swapping_run(argv, **kwargs):
            if not observations:
                os.replace(replacement, self.age)
            passed = tuple(kwargs.get("pass_fds", ()))
            observations.append(
                (
                    tuple(argv),
                    passed,
                    fcntl.fcntl(passed[0], fcntl.F_GET_SEALS) if passed else None,
                    stat.S_IMODE(os.fstat(passed[0]).st_mode) if passed else None,
                )
            )
            return subprocess.run(argv, **kwargs)

        result = self.export("Doctor retained verified executable bytes\n", runner=swapping_run)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.decrypt(), "Doctor retained verified executable bytes\n")
        self.assertFalse(capture.exists(), "replacement executable received diagnostic input")
        self.assertEqual(len(observations), 3)
        required_seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        for argv, passed, seals, mode in observations:
            self.assertEqual(len(passed), 1)
            self.assertEqual(argv[0], f"/proc/self/fd/{passed[0]}")
            self.assertEqual(seals, required_seals)
            self.assertEqual(mode, 0o700)

    def test_executes_sealed_verified_bytes_when_age_inode_is_overwritten(self):
        capture = self.scratch / "overwrite-capture"
        replacement = (
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> '{capture}'\n"
            "if [ \"$1\" = \"--version\" ]; then\n"
            "  printf 'v1.3.2\\n'\n"
            "else\n"
            f"  cat >> '{capture}'\n"
            "  printf 'age-encryption.org/v1\\noverwrite\\n'\n"
            "fi\n"
        )
        calls = 0

        def overwriting_run(argv, **kwargs):
            nonlocal calls
            if calls == 0:
                self.age.write_text(replacement)
                self.age.chmod(0o700)
            calls += 1
            return subprocess.run(argv, **kwargs)

        result = self.export("Doctor retained immutable verified bytes\n", runner=overwriting_run)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.decrypt(), "Doctor retained immutable verified bytes\n")
        self.assertFalse(capture.exists(), "overwritten executable received diagnostic input")
        self.assertEqual(calls, 3)

    def test_closes_sealed_age_descriptor_when_probe_errors(self):
        passed_fds = []

        def timeout_run(argv, **kwargs):
            passed_fds.extend(kwargs.get("pass_fds", ()))
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        result = self.cli("check", runner=timeout_run)
        self.assert_finite_failure(result, "check", "AGE_TIMEOUT")
        self.assertEqual(len(passed_fds), 1)
        with self.assertRaises(OSError):
            os.fstat(passed_fds[0])

    def test_memfd_failure_stops_before_any_age_process_or_plaintext(self):
        calls = []

        def recording_run(argv, **kwargs):
            calls.append((argv, kwargs.get("input")))
            return subprocess.run(argv, **kwargs)

        with patch.object(
            self.diag.os,
            "memfd_create",
            side_effect=OSError("synthetic unsupported memfd"),
            create=True,
        ):
            result = self.export(PLAINTEXT_CANARY + "\n", runner=recording_run)
        self.assert_finite_failure(result, "export", "AGE_BINARY")
        self.assertEqual(calls, [])

    def test_rejects_recipient_that_matches_shape_but_fails_age_checksum(self):
        recipient = self.record["diagnostic"]["recipient"]
        self.record["diagnostic"]["recipient"] = recipient[:-1] + (
            "q" if recipient[-1] != "q" else "p"
        )
        self.record["diagnostic"]["fingerprint"] = "sha256:" + hashlib.sha256(
            self.record["diagnostic"]["recipient"].encode()
        ).hexdigest()
        self.rewrite_record()
        self.assert_finite_failure(self.cli("check"), "check", "AGE_RECIPIENT")

    def test_encryption_nonzero_and_stderr_are_finite_and_never_publish(self):
        calls = 0

        def failing_run(argv, **kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                return subprocess.run(argv, **kwargs)
            return subprocess.CompletedProcess(argv, 9, b"plaintext-on-stdout", STDERR_CANARY.encode())

        result = self.export(PLAINTEXT_CANARY + "\n", runner=failing_run)
        self.assert_finite_failure(result, "export", "ENCRYPTION_FAILED")

    def test_encryption_timeout_is_finite_and_never_publish(self):
        calls = 0

        def timeout_run(argv, **kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                return subprocess.run(argv, **kwargs)
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"], output=b"plaintext", stderr=b"secret")

        result = self.export(PLAINTEXT_CANARY + "\n", runner=timeout_run)
        self.assert_finite_failure(result, "export", "ENCRYPTION_TIMEOUT")

    def test_rejects_missing_unsafe_oversize_and_non_utf8_source(self):
        cases = ("missing", "symlink", "hardlink", "fifo", "oversize", "nonutf8", "nul")
        for kind in cases:
            with self.subTest(kind=kind):
                if self.log.exists() or self.log.is_symlink():
                    self.log.unlink()
                self.log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                if kind == "symlink":
                    target = self.scratch / "outside.log"
                    self.write(target, PLAINTEXT_CANARY)
                    self.log.symlink_to(target)
                elif kind == "hardlink":
                    target = self.scratch / "outside.log"
                    self.write(target, PLAINTEXT_CANARY)
                    os.link(target, self.log)
                elif kind == "fifo":
                    os.mkfifo(self.log, 0o600)
                elif kind == "oversize":
                    self.write(self.log, b"x" * (self.diag.MAX_LOG_BYTES + 1), binary=True)
                elif kind == "nonutf8":
                    self.write(self.log, b"\xff\xfe", binary=True)
                elif kind == "nul":
                    self.write(self.log, b"error\x00secret", binary=True)
                result = self.cli("export")
                expected = "SOURCE_ABSENT" if kind == "missing" else (
                    "SOURCE_INVALID" if kind in ("nonutf8", "nul") else "SOURCE_UNSAFE"
                )
                self.assert_finite_failure(result, "export", expected)
                if self.log.exists() or self.log.is_symlink():
                    self.log.unlink()

    def test_rejects_unsafe_source_ancestor(self):
        self.write(self.log, PLAINTEXT_CANARY)
        self.log.parent.chmod(0o755)
        self.addCleanup(self.log.parent.chmod, 0o700)
        self.assert_finite_failure(self.cli("export"), "export", "SOURCE_UNSAFE")

    def test_rejects_existing_destination_types_before_reading_source(self):
        destinations = ("doctor-log.age", "diagnostic.json")
        kinds = ("regular", "symlink", "hardlink", "fifo")
        for destination in destinations:
            for kind in kinds:
                with self.subTest(destination=destination, kind=kind):
                    target = self.public / destination
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    outside = self.scratch / ("outside-" + uuid.uuid4().hex)
                    self.write(outside, PLAINTEXT_CANARY)
                    if kind == "regular":
                        self.write(target, PLAINTEXT_CANARY)
                    elif kind == "symlink":
                        target.symlink_to(outside)
                    elif kind == "hardlink":
                        os.link(outside, target)
                    else:
                        os.mkfifo(target, 0o600)
                    if self.log.exists():
                        self.log.unlink()
                    result = self.cli("export")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(
                        result.stdout,
                        "AGENTOPS_CI_DIAGNOSTIC=FAIL EXPORT OUTPUT_EXISTS\n",
                    )
                    self.assertEqual(result.stderr, "")
                    self.assertTrue(target.exists() or target.is_symlink())
                    if target.exists() or target.is_symlink():
                        target.unlink()

    def test_rejects_unsafe_public_ancestor(self):
        self.write(self.log, "safe\n")
        self.public.chmod(0o755)
        self.addCleanup(self.public.chmod, 0o700)
        self.assert_finite_failure(self.cli("export"), "export", "OUTPUT_UNSAFE")

    def test_publication_failure_removes_partial_ciphertext(self):
        self.write(self.log, PLAINTEXT_CANARY)
        original = self.diag.report.new_file
        calls = 0

        @contextlib.contextmanager
        def fail_second(path, private):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("synthetic publication failure")
            with original(path, private) as stream:
                yield stream

        with patch.object(self.diag.report, "new_file", fail_second):
            result = self.cli("export")
        self.assert_finite_failure(result, "export", "PUBLICATION_FAILED")

    def test_malformed_ciphertext_and_oversize_ciphertext_never_publish(self):
        for label, stdout in (
            ("malformed", b"not-age"),
            ("oversize", b"age-encryption.org/v1\n" + b"x" * self.diag.MAX_CIPHERTEXT_BYTES),
        ):
            with self.subTest(label=label):
                self.write(self.log, PLAINTEXT_CANARY)
                calls = 0

                def corrupt_run(argv, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls < 3:
                        return subprocess.run(argv, **kwargs)
                    return subprocess.CompletedProcess(argv, 0, stdout, b"")

                self.assert_finite_failure(
                    self.cli("export", runner=corrupt_run), "export", "CIPHERTEXT_INVALID"
                )

    def test_no_redactions_reports_zero_without_claiming_root_cause(self):
        result = self.export("Doctor completed ordinary diagnostic collection\n")
        self.assertEqual(result.returncode, 0)
        metadata = json.loads((self.public / "diagnostic.json").read_text())
        self.assertEqual(metadata["redaction_count"], 0)
        self.assertIs(metadata["redaction_occurred"], False)
        self.assertNotIn("root", json.dumps(metadata).lower())
        self.assertNotIn("exception", json.dumps(metadata).lower())

    def test_unknown_arguments_fail_closed(self):
        result = self.cli("decrypt")
        self.assert_finite_failure(result, "arguments", "ARGUMENTS")

    def test_non_allowlisted_internal_error_code_is_collapsed(self):
        with patch.object(
            self.diag, "check_contract", side_effect=self.diag.DiagnosticError(PLAINTEXT_CANARY)
        ):
            result = self.cli("check")
        self.assert_finite_failure(result, "check", "INTERNAL_ERROR")


class AgentOpsCiDiagnosticPortableRedactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("agentops_ci_diagnostic_redaction", SCRIPT)
        cls.diag = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.diag)

    def test_redact_removes_actions_oidc_request_token_canary(self):
        token = "actions-oidc-request-token-canary"
        redacted, count = self.diag.redact(
            f"Doctor context included {token}\n",
            {"ACTIONS_ID_TOKEN_REQUEST_TOKEN": token},
        )
        self.assertNotIn(token, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertEqual(count, 1)
        regression_cases = (
            (
                "password-json-escaped",
                '{"password":"pw\\\\\\"password-suffix-canary\\\\\\\\tail","note":"safe"}',
                '{"password":[REDACTED],"note":"safe"}',
                ('pw\\\\\\"password-suffix-canary\\\\\\\\tail', "password-suffix-canary"),
            ),
            (
                "token-json-escaped",
                '{"token":"tok\\\\\\"token-suffix-canary\\\\\\\\tail","note":"safe"}',
                '{"token":[REDACTED],"note":"safe"}',
                ('tok\\\\\\"token-suffix-canary\\\\\\\\tail', "token-suffix-canary"),
            ),
            (
                "api-key-json-escaped",
                '{"api_key":"api\\\\\\"api-key-suffix-canary\\\\\\\\tail","note":"safe"}',
                '{"api_key":[REDACTED],"note":"safe"}',
                ('api\\\\\\"api-key-suffix-canary\\\\\\\\tail', "api-key-suffix-canary"),
            ),
            (
                "single-quoted-password",
                "password='" + r"pw\'single-suffix-canary\tail" + "' safe",
                "password=[REDACTED] safe",
                (r"pw\'single-suffix-canary\tail", "single-suffix-canary"),
            ),
        )
        for label, source, expected, forbidden in regression_cases:
            with self.subTest(label=label):
                redacted, count = self.diag.redact(source, {})
                self.assertEqual(redacted, expected)
                self.assertEqual(count, 1)
                for fragment in forbidden:
                    self.assertNotIn(fragment, redacted)

    def test_redact_removes_all_agentops_connection_string_aliases(self):
        aliases = (
            "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_CI_APPLICATIONINSIGHTS_CONNECTION_STRING",
        )
        for index, alias in enumerate(aliases):
            with self.subTest(alias=alias):
                secret = f"InstrumentationKey=alias-secret-{index}"
                redacted, count = self.diag.redact(
                    f"Doctor context included {secret}\n",
                    {alias: secret},
                )
                self.assertNotIn(secret, redacted)
                self.assertIn("[REDACTED]", redacted)
                self.assertGreaterEqual(count, 1)

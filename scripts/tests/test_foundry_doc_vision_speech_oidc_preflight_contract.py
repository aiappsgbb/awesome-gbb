#!/usr/bin/env python3
"""Static contract for the temporary FDVS OIDC preflight workflow."""

from __future__ import annotations

import pathlib
import re
import textwrap
import unittest
from urllib.parse import urlparse

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "foundry-doc-vision-speech-oidc-preflight.yml"
)

EXPECTED_STATUS_KEYS = (
    "FDVS_OIDC_PREFLIGHT_AUTH",
    "FDVS_OIDC_PREFLIGHT_ACCOUNT",
    "FDVS_OIDC_PREFLIGHT_RBAC_COGNITIVE_SERVICES_USER",
    "FDVS_OIDC_PREFLIGHT_RBAC_COGNITIVE_SERVICES_SPEECH_USER",
    "FDVS_OIDC_PREFLIGHT_DOCINTEL_PREBUILT_READ",
    "FDVS_OIDC_PREFLIGHT_SPEECH_TTS",
    "FDVS_OIDC_PREFLIGHT_SPEECH_STT",
    "FDVS_OIDC_PREFLIGHT_RESULT",
)
EXPECTED_SECRET_NAMES = {
    "AZURE_AI_ENDPOINT",
    "AZURE_CLIENT_ID",
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_TENANT_ID",
}
EXPECTED_ACCOUNT_DIAGNOSTICS = (
    "ENDPOINT_PARSE",
    "ENDPOINT_SCHEME",
    "ENDPOINT_CREDENTIALS",
    "ENDPOINT_HOSTNAME",
    "ENDPOINT_HOST_PROJECT",
    "ENDPOINT_HOST_OPENAI",
    "ENDPOINT_HOST_SUFFIX",
    "ENDPOINT_QUERY",
    "ENDPOINT_FRAGMENT",
    "ENDPOINT_PATH",
    "ACCOUNT_HOST_DERIVATION",
    "ACCOUNT_LIST_QUERY",
    "ACCOUNT_RESOLUTION_CARDINALITY",
    "ACCOUNT_KIND",
    "ACCOUNT_ENDPOINT_PRESENCE",
    "ACCOUNT_ENDPOINT_MATCH",
    "IDENTITY_LIST_QUERY",
    "IDENTITY_RESOLUTION_CARDINALITY",
    "UNKNOWN",
)
EXPECTED_STT_DIAGNOSTIC_COMPONENTS = {
    "WAV_SPECIAL_CODES": ("WAV_INVALID", "WAV_UNKNOWN"),
    "WAV_CHANNEL_CODES": ("MONO", "STEREO", "UNKNOWN"),
    "WAV_SAMPLE_WIDTH_CODES": (
        "BITS_8",
        "BITS_16",
        "BITS_24",
        "BITS_32",
        "UNKNOWN",
    ),
    "WAV_SAMPLE_RATE_CODES": (
        "HZ_8000",
        "HZ_16000",
        "HZ_22050",
        "HZ_24000",
        "HZ_44100",
        "HZ_48000",
        "UNKNOWN",
    ),
    "WAV_COMPRESSION_CODES": ("PCM", "UNKNOWN"),
    "WAV_FRAME_CODES": ("PRESENT", "EMPTY", "UNKNOWN"),
    "STT_CANCELLATION_REASON_CODES": (
        "ERROR",
        "END_OF_STREAM",
        "BY_USER",
        "UNKNOWN",
    ),
    "STT_CANCELLATION_ERROR_CODES": (
        "NO_ERROR",
        "AUTHENTICATION_FAILURE",
        "BAD_REQUEST",
        "TOO_MANY_REQUESTS",
        "FORBIDDEN",
        "CONNECTION_FAILURE",
        "SERVICE_TIMEOUT",
        "SERVICE_ERROR",
        "SERVICE_UNAVAILABLE",
        "RUNTIME_ERROR",
        "EMBEDDED_MODEL_ERROR",
        "SERVICE_REDIRECT_PERMANENT",
        "SERVICE_REDIRECT_TEMPORARY",
        "UNKNOWN",
    ),
    "STT_SDK_EXCEPTION_CODES": (
        "SDK_EXCEPTION_RUNTIME_ERROR",
        "SDK_EXCEPTION_VALUE_ERROR",
        "SDK_EXCEPTION_TYPE_ERROR",
        "SDK_EXCEPTION_OS_ERROR",
        "UNKNOWN",
    ),
    "STT_BASE_OUTCOME_CODES": (
        "RECOGNIZED_TRANSCRIPT_MISMATCH",
        "NO_MATCH",
        "UNEXPECTED_RESULT_REASON",
        "UNKNOWN",
    ),
}
ENDPOINT_DIAGNOSTIC_CHECKS = (
    ("ENDPOINT_PARSE", "parsed = urlparse(endpoint)"),
    ("ENDPOINT_SCHEME", 'if parsed.scheme != "https":'),
    (
        "ENDPOINT_CREDENTIALS",
        "if parsed.username is not None or parsed.password is not None:",
    ),
    ("ENDPOINT_HOSTNAME", "if not parsed.hostname:"),
    (
        "ENDPOINT_HOST_PROJECT",
        'if parsed.hostname.endswith(".services.ai.azure.com"):',
    ),
    (
        "ENDPOINT_HOST_OPENAI",
        'if parsed.hostname.endswith(".openai.azure.com"):',
    ),
    ("ENDPOINT_HOST_SUFFIX", "if not parsed.hostname.endswith(suffix):"),
    ("ENDPOINT_QUERY", "if parsed.query:"),
    ("ENDPOINT_FRAGMENT", "if parsed.fragment:"),
    ("ENDPOINT_PATH", 'if parsed.path not in {"", "/"}:'),
)
FORBIDDEN_MUTATIONS = (
    r"\baz\s+role\s+assignment\s+(?:create|update|delete)\b",
    r"\baz\s+deployment\b",
    r"\baz\s+stack\b",
    r"\baz\s+resource\s+(?:create|update|delete)\b",
    r"(?m)^[ \t]*(?:run:[ \t]*)?azd\b",
    r"\baz\s+cognitiveservices\s+account\s+keys\s+list\b",
    r"\b(?:PUT|PATCH|DELETE)\s+https?://",
    r"(?m)^[ \t]*(?:run:[ \t]*)?terraform\b",
    r"(?m)^[ \t]*(?:run:[ \t]*)?bicep\b",
)


class FoundryDocVisionSpeechOidcPreflightContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not WORKFLOW.is_file():
            raise AssertionError(f"missing workflow: {WORKFLOW}")
        cls.raw = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.raw, Loader=yaml.BaseLoader)
        cls.job = cls.workflow["jobs"]["preflight"]

    def test_trigger_is_workflow_dispatch_only(self) -> None:
        self.assertEqual(
            set(self.workflow["on"]),
            {"workflow_dispatch"},
        )

    def test_main_guard_precedes_azure_login(self) -> None:
        self.assertIn(
            'GITHUB_REF" != "refs/heads/main"',
            self.raw,
            "expected the main-branch guard before Azure login",
        )
        self.assertIn(
            "uses: azure/login@v2",
            self.raw,
            "expected azure/login@v2 to be present after the main-branch guard",
        )
        guard = self.raw.index('GITHUB_REF" != "refs/heads/main"')
        login = self.raw.index("uses: azure/login@v2")
        self.assertLess(guard, login)
        self.assertIn("if: steps.ref-guard.outcome == 'success'", self.raw)

    def test_job_permissions_are_exact(self) -> None:
        self.assertNotIn("permissions", self.workflow)
        self.assertEqual(
            self.job["permissions"],
            {"id-token": "write", "contents": "read"},
        )

    def test_login_reuses_only_existing_identity_secrets(self) -> None:
        self.assertIn("uses: azure/login@v2", self.raw)
        secret_names = set(
            re.findall(r"secrets\.([A-Z][A-Z0-9_]*)", self.raw)
        )
        self.assertEqual(secret_names, EXPECTED_SECRET_NAMES)
        for name in EXPECTED_SECRET_NAMES:
            self.assertIn(f"${{{{ secrets.{name} }}}}", self.raw)

    def test_account_is_derived_from_endpoint_and_is_aiservices(self) -> None:
        self.assertIn('required_env("AZURE_AI_ENDPOINT")', self.raw)
        self.assertIn('suffix = ".cognitiveservices.azure.com"', self.raw)
        self.assertIn('account["kind"] != "AIServices"', self.raw)
        self.assertRegex(
            self.raw,
            r'"cognitiveservices",\s*"account",\s*"list"',
        )

    def test_account_diagnostic_allowlist_and_boundaries_are_explicit(self) -> None:
        allowlist_blocks = re.findall(
            r"ACCOUNT_DIAGNOSTIC_CODES = \(\n(?P<body>.*?)\n\s*\)",
            self.raw,
            flags=re.DOTALL,
        )
        self.assertEqual(
            len(allowlist_blocks),
            2,
            "probe and finalizer must independently use the explicit allowlist",
        )
        for block in allowlist_blocks:
            codes = tuple(
                re.findall(
                    r'^\s*"([A-Z][A-Z0-9_]*)",$',
                    block,
                    flags=re.MULTILINE,
                )
            )
            self.assertEqual(codes, EXPECTED_ACCOUNT_DIAGNOSTICS)
            self.assertTrue(
                all(re.fullmatch(r"[A-Z][A-Z0-9_]*", code) for code in codes)
            )

        boundaries = (
            ("ACCOUNT_HOST_DERIVATION", "account_name = parsed.hostname"),
            ("ACCOUNT_LIST_QUERY", "accounts = az_json("),
            ("ACCOUNT_RESOLUTION_CARDINALITY", "if len(matches) != 1:"),
            ("ACCOUNT_KIND", 'if account["kind"] != "AIServices":'),
            ("ACCOUNT_ENDPOINT_PRESENCE", "account_endpoint = ("),
            (
                "ACCOUNT_ENDPOINT_MATCH",
                "if urlparse(account_endpoint).hostname != parsed.hostname:",
            ),
            ("IDENTITY_LIST_QUERY", "identities = az_json("),
            (
                "IDENTITY_RESOLUTION_CARDINALITY",
                "if len(identity_matches) != 1:",
            ),
        )
        for code, boundary in boundaries:
            with self.subTest(code=code):
                assignment = self.raw.index(f'account_diagnostic = "{code}"')
                assertion = self.raw.index(boundary)
                self.assertLess(assignment, assertion)

    def test_endpoint_diagnostics_are_sequential_and_guard_own_checks(self) -> None:
        account_block = re.search(
            r'account_diagnostic = "UNKNOWN"\n'
            r"\s*try:\n"
            r"(?P<body>.*?)"
            r'\n\s*account_diagnostic = "ACCOUNT_LIST_QUERY"',
            self.raw,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(account_block)
        assert account_block is not None
        body = account_block.group("body")

        assignments = tuple(
            re.findall(r'account_diagnostic = "([A-Z][A-Z0-9_]*)"', body)
        )
        expected_assignments = tuple(
            code for code, _ in ENDPOINT_DIAGNOSTIC_CHECKS
        ) + ("ACCOUNT_HOST_DERIVATION",)
        self.assertEqual(assignments, expected_assignments)

        assignment_offsets = [
            body.index(f'account_diagnostic = "{code}"')
            for code in expected_assignments
        ]
        self.assertEqual(assignment_offsets, sorted(assignment_offsets))

        for index, (code, check) in enumerate(ENDPOINT_DIAGNOSTIC_CHECKS):
            with self.subTest(code=code):
                start = assignment_offsets[index]
                end = assignment_offsets[index + 1]
                interval = body[start:end]
                self.assertIn(check, interval)
                self.assertEqual(
                    body.count(check),
                    1,
                    f"{code} check must occur once in its own interval",
                )

        parse_start = assignment_offsets[0]
        parse_end = assignment_offsets[1]
        parse_interval = body[parse_start:parse_end]
        self.assertRegex(
            parse_interval,
            r"try:\n\s+parsed = urlparse\(endpoint\)\n"
            r"\s+except Exception:\n\s+raise RuntimeError",
        )
        host_derivation_interval = body[assignment_offsets[-1] :]
        self.assertIn(
            "account_name = parsed.hostname[: -len(suffix)]",
            host_derivation_interval,
        )
        self.assertNotIn("ENDPOINT_SHAPE", self.raw)

    def test_endpoint_diagnostic_runtime_mapping_is_exact(self) -> None:
        probe_run = next(
            step["run"]
            for step in self.job["steps"]
            if step.get("id") == "live-probes"
        )
        python_body = probe_run.split(
            "python - <<'PY' >/dev/null 2>/dev/null\n",
            1,
        )[1].rsplit("\nPY", 1)[0]
        validation = re.search(
            r'account_diagnostic = "UNKNOWN"\n'
            r"try:\n"
            r"(?P<body>.*?)"
            r'\n    account_diagnostic = "ACCOUNT_LIST_QUERY"',
            python_body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(validation)
        assert validation is not None

        function_source = (
            "def diagnose(endpoint):\n"
            '    account_diagnostic = "UNKNOWN"\n'
            "    try:\n"
            f"{textwrap.indent(textwrap.dedent(validation.group('body')), '        ')}\n"
            "    except Exception:\n"
            "        return account_diagnostic\n"
            "    return account_diagnostic\n"
        )
        namespace = {"urlparse": urlparse}
        exec(compile(function_source, "<endpoint-diagnostic>", "exec"), namespace)
        diagnose = namespace["diagnose"]

        cases = (
            ("https://[invalid", "ENDPOINT_PARSE"),
            (
                "http://account.cognitiveservices.azure.com",
                "ENDPOINT_SCHEME",
            ),
            (
                "https://user@account.cognitiveservices.azure.com",
                "ENDPOINT_CREDENTIALS",
            ),
            (
                "https://user:secret@account.cognitiveservices.azure.com",
                "ENDPOINT_CREDENTIALS",
            ),
            (
                "https://resource.services.ai.azure.com/api/projects/project",
                "ENDPOINT_HOST_PROJECT",
            ),
            (
                "https://resource.openai.azure.com/",
                "ENDPOINT_HOST_OPENAI",
            ),
            ("https://example.com/models", "ENDPOINT_HOST_SUFFIX"),
            (
                "https://account.cognitiveservices.azure.com/models",
                "ENDPOINT_PATH",
            ),
            (
                "https://account.cognitiveservices.azure.com?api-version=test",
                "ENDPOINT_QUERY",
            ),
            (
                "https://account.cognitiveservices.azure.com#fragment",
                "ENDPOINT_FRAGMENT",
            ),
            ("https:///", "ENDPOINT_HOSTNAME"),
            (
                "https://account.cognitiveservices.azure.com/",
                "ACCOUNT_HOST_DERIVATION",
            ),
        )
        for endpoint, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(diagnose(endpoint), expected)

    def test_account_diagnostic_is_private_validated_and_not_uploaded(self) -> None:
        self.assertIn("FDVS_ACCOUNT_DIAGNOSTIC_FILE", self.job["env"])
        diagnostic_path = self.job["env"]["FDVS_ACCOUNT_DIAGNOSTIC_FILE"]
        status_path = self.job["env"]["FDVS_STATUS_FILE"]
        self.assertEqual(diagnostic_path, "/tmp/fdvs-account-diagnostic.txt")
        self.assertNotEqual(diagnostic_path, status_path)

        upload_steps = [
            step
            for step in self.job["steps"]
            if step.get("uses") == "actions/upload-artifact@v4"
        ]
        self.assertEqual(len(upload_steps), 1)
        self.assertEqual(upload_steps[0]["with"]["path"], status_path)
        self.assertNotIn(diagnostic_path, upload_steps[0]["with"]["path"])

        self.assertIn("python - <<'PY' >/dev/null 2>/dev/null", self.raw)
        account_handler = re.search(
            r"except Exception:\n"
            r"\s*if account_diagnostic not in ACCOUNT_DIAGNOSTIC_CODES:\n"
            r"(?P<body>.*?)\n"
            r'\s*fail_stage\("FDVS_OIDC_PREFLIGHT_ACCOUNT"\)',
            self.raw,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(account_handler)
        assert account_handler is not None
        handler_body = account_handler.group("body")
        self.assertRegex(
            handler_body,
            r"ACCOUNT_DIAGNOSTIC_FILE\.write_bytes\(\s*"
            r'f"\{account_diagnostic\}\\n"\.encode\("ascii"\)\s*\)',
        )
        self.assertNotRegex(
            handler_body,
            r"(?i)(endpoint|account_name|client_id|subscription_id|"
            r"principal_id|stdout|stderr|exception|traceback)",
        )

        self.assertIn("raw_diagnostic = diagnostic_file.read_bytes()", self.raw)
        self.assertIn(
            'raw_diagnostic == f"{code}\\n".encode("ascii")',
            self.raw,
        )
        self.assertIn(
            'print(f"::error::FDVS_ACCOUNT_DIAGNOSTIC={diagnostic}")',
            self.raw,
        )
        self.assertEqual(self.raw.count("FDVS_ACCOUNT_DIAGNOSTIC="), 1)

    def test_stt_diagnostic_is_separate_allowlisted_and_not_uploaded(self) -> None:
        self.assertIn("FDVS_SPEECH_STT_DIAGNOSTIC_FILE", self.job["env"])
        diagnostic_path = self.job["env"]["FDVS_SPEECH_STT_DIAGNOSTIC_FILE"]
        status_path = self.job["env"]["FDVS_STATUS_FILE"]
        self.assertEqual(
            diagnostic_path,
            "/tmp/fdvs-speech-stt-diagnostic.txt",
        )
        self.assertNotEqual(diagnostic_path, status_path)

        upload_steps = [
            step
            for step in self.job["steps"]
            if step.get("uses") == "actions/upload-artifact@v4"
        ]
        self.assertEqual(len(upload_steps), 1)
        self.assertEqual(upload_steps[0]["with"]["path"], status_path)
        self.assertNotIn(diagnostic_path, upload_steps[0]["with"]["path"])

        for name, expected_codes in EXPECTED_STT_DIAGNOSTIC_COMPONENTS.items():
            with self.subTest(name=name):
                allowlist_blocks = re.findall(
                    rf"{name} = \(\n(?P<body>.*?)\n\s*\)",
                    self.raw,
                    flags=re.DOTALL,
                )
                self.assertEqual(
                    len(allowlist_blocks),
                    2,
                    "probe and finalizer must independently allowlist diagnostics",
                )
                for block in allowlist_blocks:
                    actual_codes = tuple(
                        re.findall(
                            r'^\s*"([A-Z][A-Z0-9_]*)",$',
                            block,
                            flags=re.MULTILINE,
                        )
                    )
                    self.assertEqual(actual_codes, expected_codes)

        self.assertIn("validated_stt_diagnostic(raw_diagnostic)", self.raw)
        self.assertIn(
            'print(f"::error::FDVS_SPEECH_STT_DIAGNOSTIC={diagnostic}")',
            self.raw,
        )
        self.assertEqual(self.raw.count("FDVS_SPEECH_STT_DIAGNOSTIC="), 1)

    def test_stt_failures_are_classified_without_raw_payloads(self) -> None:
        stt_block = re.search(
            r"wav_diagnostic = classify_wav\(wav_path\)\n"
            r"(?P<body>.*?)"
            r'\n\s*pass_stage\("FDVS_OIDC_PREFLIGHT_SPEECH_STT"\)',
            self.raw,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            stt_block,
            "STT must classify the WAV and recognition outcome before PASS",
        )
        assert stt_block is not None
        body = stt_block.group("body")
        for required in (
            "speechsdk.ResultReason.RecognizedSpeech",
            "RECOGNIZED_TRANSCRIPT_MISMATCH",
            "speechsdk.ResultReason.NoMatch",
            '"NO_MATCH"',
            "speechsdk.ResultReason.Canceled",
            "speechsdk.CancellationDetails(recognition)",
            "classify_stt_cancellation(cancellation)",
            '"UNEXPECTED_RESULT_REASON"',
            "write_stt_diagnostic(wav_diagnostic, outcome)",
        ):
            with self.subTest(required=required):
                self.assertIn(required, body)

        exception_handler = re.search(
            r"except Exception as error:\n"
            r"(?P<body>.*?)\n"
            r'\s*fail_stage\("FDVS_OIDC_PREFLIGHT_SPEECH_STT"\)',
            self.raw,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(
            exception_handler,
            "the broad STT catch must classify its exception safely",
        )
        assert exception_handler is not None
        handler_body = exception_handler.group("body")
        self.assertIn("classify_stt_exception(error)", handler_body)
        self.assertIn("write_stt_diagnostic(", handler_body)
        self.assertEqual(handler_body.count("classify_stt_exception(error)"), 1)
        self.assertEqual(
            len(re.findall(r"\berror\b", handler_body)),
            1,
            "the caught exception may only flow into the allowlist classifier",
        )

        self.assertNotIn(".error_details", self.raw)
        self.assertEqual(
            body.count("recognition.text"),
            1,
            "transcript text may only be compared, never emitted",
        )
        self.assertNotRegex(
            self.raw,
            r"(?i)(?:print|write_text|write_bytes)\([^)]*recognition\.text",
        )
        self.assertNotRegex(
            handler_body,
            r"(?i)(?:str|repr)\(error\)|traceback|error\.args|"
            r"error_details|recognition\.text|wav_path",
        )
        self.assertNotRegex(
            self.raw,
            r"FDVS_SPEECH_STT_DIAGNOSTIC=\{(?:endpoint|token|client_id|"
            r"subscription_id|recognition\.text|wav_path|error)",
        )

    def test_stt_finalizer_rejects_unallowlisted_payloads(self) -> None:
        finalize_run = next(
            step["run"]
            for step in self.job["steps"]
            if step.get("name") == "Finalize sanitized evidence"
        )
        python_body = finalize_run.split("python - <<'PY'\n", 1)[1].rsplit(
            "\nPY",
            1,
        )[0]
        validator_source = re.search(
            r"(?P<body>WAV_SPECIAL_CODES = \(.*?"
            r"\ndef validated_stt_diagnostic\(raw: bytes\) -> str:\n.*?)"
            r"(?=\n\ndiagnostic_file =)",
            python_body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(validator_source)
        assert validator_source is not None

        namespace = {"re": re}
        exec(
            compile(
                textwrap.dedent(validator_source.group("body")),
                "<stt-diagnostic-validator>",
                "exec",
            ),
            namespace,
        )
        validate = namespace["validated_stt_diagnostic"]

        valid = (
            b"WAV_MONO_BITS_16_HZ_24000_PCM_PRESENT"
            b"__CANCELED_ERROR_AUTHENTICATION_FAILURE\n"
        )
        self.assertEqual(validate(valid), valid.decode("ascii").strip())
        unsafe_values = (
            b"WAV_MONO_BITS_16_HZ_24000_PCM_PRESENT"
            b"__RuntimeError: endpoint=https://private.example\n",
            b"WAV_MONO_BITS_16_HZ_24000_PCM_PRESENT"
            b"__recognized private transcript\n",
            b"WAV_MONO_BITS_16_HZ_24000_PCM_PRESENT"
            b"__/tmp/private.wav\n",
            b"WAV_MONO_BITS_16_HZ_24000_PCM_PRESENT__NO_MATCH\nextra\n",
            b"\xff\n",
        )
        for raw in unsafe_values:
            with self.subTest(raw=raw):
                self.assertEqual(validate(raw), "UNKNOWN")

    def test_stt_cancellation_classifier_uses_python_sdk_contract(self) -> None:
        probe_run = next(
            step["run"]
            for step in self.job["steps"]
            if step.get("id") == "live-probes"
        )
        python_body = probe_run.split(
            "python - <<'PY' >/dev/null 2>/dev/null\n",
            1,
        )[1].rsplit("\nPY", 1)[0]
        maps = re.search(
            r"(?P<body>STT_CANCELLATION_REASON_NAME_CODES = \{.*?"
            r"\nSTT_CANCELLATION_ERROR_NAME_CODES = \{.*?\n\})",
            python_body,
            flags=re.DOTALL,
        )
        functions = re.search(
            r"(?P<body>def safe_named_enum_code\(.*?"
            r"\ndef classify_stt_cancellation\(.*?"
            r"return f\"CANCELED_\{reason_code\}_\{error_code\}\")",
            python_body,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(maps)
        self.assertIsNotNone(functions)
        assert maps is not None
        assert functions is not None

        namespace: dict[str, object] = {}
        source = "\n\n".join(
            (
                textwrap.dedent(maps.group("body")),
                textwrap.dedent(functions.group("body")),
            )
        )
        exec(compile(source, "<stt-cancellation-classifier>", "exec"), namespace)
        classify = namespace["classify_stt_cancellation"]

        class NamedEnum:
            def __init__(self, name: str) -> None:
                self.name = name

        class Cancellation:
            reason = NamedEnum("Error")
            code = NamedEnum("BadRequest")

        try:
            actual = classify(Cancellation())
        except AttributeError:
            actual = "ATTRIBUTE_ERROR"
        self.assertEqual(actual, "CANCELED_ERROR_BAD_REQUEST")

    def test_embedded_python_blocks_compile(self) -> None:
        blocks = re.findall(
            r"python - <<'PY'(?: >/dev/null 2>/dev/null)?\n"
            r"(?P<body>.*?)\n\s+PY",
            self.raw,
            flags=re.DOTALL,
        )
        self.assertEqual(len(blocks), 2)
        for index, body in enumerate(blocks):
            with self.subTest(index=index):
                compile(textwrap.dedent(body), f"<workflow-python-{index}>", "exec")

    def test_exact_effective_roles_are_required(self) -> None:
        self.assertIn('"--include-inherited"', self.raw)
        self.assertIn('"Cognitive Services User"', self.raw)
        self.assertIn('"Cognitive Services Speech User"', self.raw)
        self.assertIn('"--assignee-object-id"', self.raw)

    def test_live_default_credential_probes_are_present(self) -> None:
        self.assertIn("DefaultAzureCredential()", self.raw)
        self.assertIn('"prebuilt-read"', self.raw)
        self.assertIn("SpeechSynthesizer(", self.raw)
        self.assertIn("SpeechRecognizer(", self.raw)
        self.assertIn("recognize_once_async().get()", self.raw)
        self.assertNotIn("AzureCliCredential", self.raw)
        self.assertNotIn("subscription_key", self.raw)

    def test_azure_commands_are_read_only(self) -> None:
        for pattern in FORBIDDEN_MUTATIONS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    re.search(pattern, self.raw, flags=re.IGNORECASE)
                )

    def test_status_keys_and_upload_contract_are_exact(self) -> None:
        status_tuple = re.search(
            r"STATUS_KEYS = \(\n(?P<body>.*?)\n\s*\)",
            self.raw,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(status_tuple)
        assert status_tuple is not None
        keys = tuple(
            re.findall(r'^\s*"([A-Z0-9_]+)",$', status_tuple.group("body"), re.MULTILINE)
        )
        self.assertEqual(keys, EXPECTED_STATUS_KEYS)
        self.assertIn("name: fdvs-oidc-preflight", self.raw)
        self.assertIn("path: /tmp/fdvs-oidc-preflight.txt", self.raw)
        self.assertIn("retention-days: 7", self.raw)
        self.assertEqual(self.raw.count("uses: actions/upload-artifact@v4"), 1)
        self.assertIn("if: always()", self.raw)

    def test_finalizer_is_fail_closed(self) -> None:
        self.assertIn("STATUS_VALUES = {\"PASS\", \"FAIL\", \"NOT_RUN\"}", self.raw)
        self.assertIn('status["FDVS_OIDC_PREFLIGHT_RESULT"] = "FAIL"', self.raw)
        self.assertIn('status["FDVS_OIDC_PREFLIGHT_RESULT"] = "PASS"', self.raw)
        self.assertIn('cmp -s "$STATUS_FILE" "$EXPECTED_FILE"', self.raw)
        self.assertIn('exit 1', self.raw)
        self.assertNotRegex(
            self.raw,
            r"(?i)(?:soft[-_ ]?skip|allow[-_ ]?failure|success[-_ ]?fallback)",
        )

    def test_success_bytes_are_literal_and_private(self) -> None:
        expected = "\n".join(
            f"{key}=PASS" for key in EXPECTED_STATUS_KEYS
        ) + "\n"
        block = re.search(
            r"cat > \"\$EXPECTED_FILE\" <<'EOF'\n"
            r"(?P<body>(?:\s+FDVS_[A-Z0-9_]+=PASS\n)+)"
            r"\s+EOF",
            self.raw,
        )
        self.assertIsNotNone(block)
        assert block is not None
        actual = "\n".join(
            line.strip() for line in block.group("body").splitlines()
        ) + "\n"
        self.assertEqual(actual, expected)
        self.assertNotRegex(
            expected,
            r"(?i)(https?://|[0-9a-f]{8}-[0-9a-f-]{27,}|token|endpoint|client_id)",
        )


if __name__ == "__main__":
    unittest.main()

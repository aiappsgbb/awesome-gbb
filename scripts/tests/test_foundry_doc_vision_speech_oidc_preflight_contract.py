#!/usr/bin/env python3
"""Static contract for the temporary FDVS OIDC preflight workflow."""

from __future__ import annotations

import pathlib
import re
import unittest

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
    "ENDPOINT_SHAPE",
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
            ("ENDPOINT_SHAPE", "parsed = urlparse(endpoint)"),
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
        self.assertNotRegex(self.raw, r"except Exception as \w+")
        account_handler = re.search(
            r'account_diagnostic = "UNKNOWN".*?'
            r'except Exception:\n(?P<body>.*?)\n'
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

"""Run the fixture's final validator against synthetic five-record archives."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills/foundry-toolbox/test-fixture/consumer_prompt.md"
TEXT = FIXTURE.read_text(encoding="utf-8")
FINAL = TEXT.split("## Step 2 - write the deterministic result marker", 1)[1]
CODE = re.search(r"python3 - <<'PY'\n(.*?)\nPY", FINAL, re.S).group(1)
VALID = [
    "AZD_SERVICE_CREATED name=ci-smoke-azdsvc-12345678",
    "AZD_CLI_CREATED name=ci-smoke-azdcli-12345678",
    "TOOL_SEARCH_CREATED name=ci-smoke-tbx-87654321 version=1",
    "TOOLBOX_RETRIEVED name=ci-smoke-tbx-87654321 version=1",
    "TOOL_SEARCH_FUNCTIONS names=call_tool,tool_search",
]


class ToolboxArchiveEvidenceTests(unittest.TestCase):
    def validate(self, records):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, marker = root / "evidence", root / "marker"
            if records is not None:
                evidence.write_text("\n".join(records) + "\n")
            marker.write_text("SMOKE_RESULT=PASS\n")
            paths = {
                "/tmp/foundry-toolbox-smoke-evidence": evidence,
                "/tmp/foundry-toolbox-smoke-result": marker,
            }
            failure = None
            with patch("pathlib.Path", side_effect=paths.__getitem__), redirect_stdout(io.StringIO()) as output:
                try:
                    exec(compile(CODE, str(FIXTURE), "exec"), {})
                except (AssertionError, FileNotFoundError) as error:
                    failure = type(error)
            return marker.read_text(), output.getvalue(), failure

    def test_exact_five_records_pass_with_archive_hash(self):
        marker, output, error = self.validate(VALID)
        self.assertEqual(marker, "SMOKE_RESULT=PASS\n")
        self.assertIsNone(error)
        self.assertRegex(output, r"TOOLBOX_ARCHIVE_EVIDENCE_VERIFIED records=5 sha256=[0-9a-f]{64}")

    def test_missing_partial_extra_or_duplicate_archive_cannot_pass(self):
        for records in (None, [], VALID[:2], VALID + [VALID[0]], VALID[:4] + [VALID[3]]):
            with self.subTest(records=records):
                marker, output, error = self.validate(records)
                self.assertEqual(marker, "SMOKE_RESULT=FAIL evidence incomplete\n")
                self.assertIsNotNone(error)
                self.assertNotIn("VERIFIED", output)

    def test_different_sdk_identity_version_or_meta_tools_cannot_pass(self):
        for replacement in (
            "TOOLBOX_RETRIEVED name=ci-smoke-tbx-11111111 version=1",
            "TOOLBOX_RETRIEVED name=ci-smoke-tbx-87654321 version=2",
            "TOOL_SEARCH_FUNCTIONS names=tool_search",
        ):
            records = VALID.copy()
            records[4 if "FUNCTIONS" in replacement else 3] = replacement
            marker, _, error = self.validate(records)
            self.assertEqual(marker, "SMOKE_RESULT=FAIL evidence incomplete\n")
            self.assertIs(error, AssertionError)

    def test_all_producers_and_validator_share_the_archive_path(self):
        self.assertIn('evidence="/tmp/foundry-toolbox-smoke-evidence"', TEXT)
        self.assertIn('evidence_path = "/tmp/foundry-toolbox-smoke-evidence"', TEXT)
        self.assertIn('Path("/tmp/foundry-toolbox-smoke-evidence")', CODE)
        self.assertNotIn("printf 'SMOKE_RESULT=PASS", TEXT)
        self.assertIn("do not replay the azd smoke", TEXT)
        self.assertIn("five TOTAL records (two azd plus three SDK)", TEXT)


if __name__ == "__main__":
    unittest.main()

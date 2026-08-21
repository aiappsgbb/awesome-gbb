"""Contract tests for the foundry-doc-vision-speech Copilot-CLI fixture.

Regression guard for the audit-step failure observed on PR #457, run
31812164018 job 94805195252: the smoke itself PASSED (marker file wrote
``SMOKE_RESULT=PASS``, all four live-Azure probes green in 50s) but the
workflow's post-hoc audit step failed with

    No evidence in transcript that agent loaded the
    'foundry-doc-vision-speech' skill

Root cause: the Copilot CLI transcript renders each tool-call body
collapsed — roughly the first five lines, then ``└ N lines...``. The
agent had batched every fixture step into a single 188-line Bash block,
so the Step -1 breadcrumb was swallowed inside the truncated region and
never reached the transcript text the audit greps.

The proven fix (``foundry-iq``, green on six consecutive main runs) is to
require the breadcrumb be its OWN Bash tool call containing ONLY that
command, so its full body always renders inside the untruncated head.

These tests assert the fixture keeps that instruction and keeps a
breadcrumb string the audit grep can actually match.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO = pathlib.Path(__file__).resolve().parents[2]
SKILL = "foundry-doc-vision-speech"
FIXTURE = REPO / "skills" / SKILL / "test-fixture" / "consumer_prompt.md"

# The audit step in .github/workflows/skill-test.yml greps the transcript
# with this pattern (SKILL expanded). Mirrored here so the test fails if
# the fixture ever stops producing matchable output.
AUDIT_PATTERN = re.compile(rf'skill[(]"?{re.escape(SKILL)}"?|SKILL\.md|skills/{re.escape(SKILL)}/')


def _bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, re.S)


class FixtureAuditBreadcrumbContract(unittest.TestCase):
    """The fixture must survive the transcript's tool-call truncation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = FIXTURE.read_text(encoding="utf-8")
        cls.blocks = _bash_blocks(cls.text)

    def test_fixture_exists_and_has_bash_blocks(self) -> None:
        self.assertTrue(FIXTURE.is_file(), f"missing fixture: {FIXTURE}")
        self.assertGreater(len(self.blocks), 1, "fixture has no executable steps")

    def test_first_bash_block_is_a_standalone_audit_breadcrumb(self) -> None:
        """Block 1 must be one single command, so it renders untruncated.

        A multi-command first block risks the agent folding later work
        into it; a long one risks the ``└ N lines...`` collapse that
        hid the breadcrumb on run 31812164018.
        """
        first = self.blocks[0].strip()
        lines = [ln for ln in first.splitlines() if ln.strip()]
        self.assertEqual(
            len(lines), 1,
            "the audit breadcrumb block must contain exactly one command so "
            f"the transcript renders it in full; got {len(lines)} lines:\n{first}",
        )
        self.assertTrue(
            lines[0].lstrip().startswith("echo "),
            f"breadcrumb must be a bare echo, got: {lines[0]!r}",
        )

    def test_breadcrumb_output_matches_the_workflow_audit_grep(self) -> None:
        """What the echo prints must satisfy the audit regex."""
        first = self.blocks[0].strip()
        self.assertRegex(
            first, AUDIT_PATTERN,
            "the breadcrumb does not contain a string the workflow audit "
            "step can grep — the leg will fail even when the smoke passes",
        )

    def test_fixture_requires_the_breadcrumb_be_its_own_tool_call(self) -> None:
        """The prose must forbid batching it with later steps.

        This is the instruction that was MISSING on run 31812164018 and
        is present in the green ``foundry-iq`` fixture.
        """
        prose = self.text.split("```bash")[0]
        self.assertRegex(
            prose, r"separate\s+Bash\s+tool\s+call",
            "fixture must require the breadcrumb be a separate Bash tool call",
        )
        self.assertRegex(
            prose, r"only\s+this\s+command|containing\s+only",
            "fixture must require the breadcrumb block contain only that command",
        )
        self.assertRegex(
            prose, r"[Dd]o\s+not\s+combine|[Dd]o\s+NOT\s+combine",
            "fixture must explicitly forbid combining the breadcrumb with later steps",
        )

    def test_fixture_still_forbids_reading_the_oversized_skill_md(self) -> None:
        """The token-bomb guard (Pattern 19 addendum v2) must survive."""
        self.assertRegex(
            self.text, r"[Dd]o NOT `?view`?|[Dd]o not `?view`?|do NOT view",
            "fixture must forbid viewing SKILL.md (~47 KB token bomb)",
        )

    def test_fixture_carries_the_anti_recursive_copilot_block(self) -> None:
        """Pattern 27 — not in the shared preamble, must be per-fixture."""
        self.assertIn("never invoke `copilot` recursively", self.text)


if __name__ == "__main__":
    unittest.main()

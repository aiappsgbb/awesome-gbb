"""Contract tests for the live Foundry Routines fixture."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-routines" / "SKILL.md"
FIXTURE = ROOT / "skills" / "foundry-routines" / "test-fixture" / "consumer_prompt.md"
PIN = ROOT / "skills" / "foundry-routines" / "references" / "upstream-pin.md"


class FoundryRoutinesFixtureContractTests(unittest.TestCase):
    def test_fixture_requires_execution_instead_of_catalog_inspection(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())

        for required in (
            "This is an EXECUTION smoke, not a catalog inspection.",
            "You MUST run every Bash code block below in order",
            "Do NOT inspect repo files",
            "do NOT run `validate-skills.py`",
            "do NOT rebuild docs",
            "do NOT run `git status`",
            "Do NOT read, view, grep, or glob `SKILL.md`",
            "Your only acceptable terminal state is a Bash tool call that writes",
            "/tmp/foundry-routines-smoke-result",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

        for forbidden in (
            "Do whatever the skill tells you to do.",
            "read the skill's `SKILL.md` first",
            "Read `skills/foundry-routines/SKILL.md`",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_flat)

    def test_fixture_starts_with_standalone_audit_breadcrumb(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        self.assertTrue(bash_blocks, "fixture must contain executable Bash blocks")
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "Executing consumer smoke for skills/foundry-routines/SKILL.md"',
        )
        self.assertIn(
            "mandatory FIRST action",
            fixture.split("```bash", maxsplit=1)[0],
        )
        self.assertIn(
            "Do not combine it with Step 0 or any later work.",
            fixture,
        )

    def test_fixture_requires_ordered_bash_blocks_without_ad_hoc_harness(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())
        python_fences = re.findall(r"```python\n(.*?)```", fixture, re.DOTALL)
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        self.assertEqual(
            python_fences,
            [],
            "lifecycle Python must execute inside ordered Bash heredocs",
        )
        self.assertGreaterEqual(
            len(bash_blocks),
            8,
            "breadcrumb, auth, install, lifecycle, and marker need explicit Bash calls",
        )
        for required in (
            "Execute each fenced Bash block as its own Bash tool call.",
            "Do not combine multiple numbered steps into one command",
            "Do NOT create an ad-hoc combined smoke harness",
            "Do NOT use shell process substitution",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

    def test_fixture_forbids_repo_edits_and_session_plans(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())

        for required in (
            "Do NOT create or modify tracked repository files.",
            "Do NOT write a session plan",
            "Do NOT create scratch scripts",
            "Do NOT edit the fixture or skill",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

    def test_fixture_forbids_recursive_copilot(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        for required in (
            "never invoke `copilot` recursively",
            "Do NOT run `copilot -p ...`",
            "Do NOT run `copilot --version`",
            "The workflow already captures your output through its outer `tee`",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture)

    def test_final_bash_block_is_exact_pattern_12_marker_write(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        self.assertEqual(
            bash_blocks[-1].strip(),
            "if [[ -f /tmp/foundry-routines-smoke-success ]]; then\n"
            "  printf 'SMOKE_RESULT=PASS\\n' > "
            "/tmp/foundry-routines-smoke-result\n"
            "else\n"
            "  printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > "
            "/tmp/foundry-routines-smoke-result\n"
            "  exit 1\n"
            "fi",
        )
        self.assertIn(
            "The file's literal byte content is what CI grades",
            fixture,
        )
        self.assertIn(
            "anything else is graded FAIL by `cmp -s`",
            fixture,
        )

    def test_cleanup_failure_cannot_create_success_sentinel(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        cleanup = fixture.split(
            "## Step 7 - Delete the routine, clean the prompt agent, and seal success",
            maxsplit=1,
        )[1].split(
            "## Step 8 - Write the result marker",
            maxsplit=1,
        )[0]
        bash_block = re.findall(r"```bash\n(.*?)```", cleanup, re.DOTALL)

        self.assertEqual(len(bash_block), 1)
        commands = bash_block[0]
        self.assertIn("set -euo pipefail", commands)
        self.assertLess(
            commands.index("set -euo pipefail"),
            commands.index("python3 - <<'PY'"),
        )
        self.assertLess(
            commands.index("raise routine_delete_error"),
            commands.index(': > "$SUCCESS_FILE"'),
        )

    def test_success_sentinel_requires_all_ordered_lifecycle_evidence(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        cleanup = fixture.split(
            "## Step 7 - Delete the routine, clean the prompt agent, and seal success",
            maxsplit=1,
        )[1].split(
            "## Step 8 - Write the result marker",
            maxsplit=1,
        )[0]
        expected_evidence = (
            "AGENT_CREATED",
            "ROUTINE_CREATED",
            "ROUTINE_DISPATCHED",
            "ROUTINE_LISTED",
            "ROUTINE_DELETED",
        )

        self.assertIn(
            'EVIDENCE_FILE="/tmp/foundry-routines-smoke-evidence"',
            fixture,
        )
        for item in expected_evidence:
            with self.subTest(item=item):
                self.assertIn(f"{item}\\n", fixture)

        self.assertIn("EXPECTED_EVIDENCE=$(printf", cleanup)
        self.assertIn('ACTUAL_EVIDENCE=$(cat "$EVIDENCE_FILE")', cleanup)
        self.assertIn(
            'if [[ "$ACTUAL_EVIDENCE" == "$EXPECTED_EVIDENCE" ]]; then',
            cleanup,
        )
        self.assertLess(
            cleanup.index('[[ "$ACTUAL_EVIDENCE" == "$EXPECTED_EVIDENCE" ]]'),
            cleanup.index(': > "$SUCCESS_FILE"'),
        )

    def test_skill_version_includes_live_fixture_repair(self) -> None:
        raw = SKILL.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        version = tuple(
            int(part)
            for part in yaml.safe_load(frontmatter)["metadata"]["version"].split(".")
        )

        self.assertGreaterEqual(version, (1, 0, 3))

    def test_install_contract_uses_current_bounded_dependencies(self) -> None:
        expected = (
            '"azure-ai-projects~=2.4.0" '
            '"azure-identity~=1.25.3" '
            '"httpx~=0.28.1"'
        )
        self.assertIn(expected, SKILL.read_text(encoding="utf-8"))
        self.assertIn(expected, FIXTURE.read_text(encoding="utf-8"))

        pin = PIN.read_text(encoding="utf-8")
        self.assertIn('"azure-ai-projects~=${PINNED_VERSION:-2.4.0}"', pin)
        self.assertIn('"azure-identity~=1.25.3"', pin)
        self.assertIn('"httpx~=0.28.1"', pin)

    def test_pin_audit_trail_matches_current_frontmatter(self) -> None:
        pin = PIN.read_text(encoding="utf-8")

        self.assertIn("| **Pinned version** | **2.4.0**", pin)
        self.assertIn("`~=2.4.0` ≡ `>=2.4.0, <2.5.0`", pin)
        self.assertIn("| `azure-ai-projects` | PyPI | **2.4.0**", pin)
        self.assertIn("| `httpx` | PyPI | **0.28.1**", pin)
        self.assertNotIn("aif-awesome-gbb-ci", pin)

    def test_fixture_uses_live_proven_monthly_schedule(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn('"monthly-anchor"', fixture)
        self.assertIn('"cron_expression": "0 0 1 * *"', fixture)
        self.assertNotIn('"annual-anchor"', fixture)
        self.assertNotIn('"cron_expression": "0 0 1 1 *"', fixture)
        self.assertNotIn("January 1", fixture)

    def test_fixture_forbids_self_modification(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn("Do NOT edit any repository file", fixture)
        self.assertRegex(
            fixture,
            re.compile(r"service\s+rejects.{0,200}write the FAIL marker", re.DOTALL),
        )
        self.assertNotIn("rg-awesome-gbb-ci", fixture)

    def test_enabled_routine_deletion_is_a_hard_pass_condition(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn("Routine deletion is a hard PASS condition", fixture)
        self.assertIn("routine-disable-note:", fixture)
        self.assertIn("routine-delete-fail:", fixture)
        self.assertIn("routine_delete_error", fixture)
        self.assertLess(
            fixture.index("project.beta.routines.delete"),
            fixture.index(': > "$SUCCESS_FILE"'),
        )
        self.assertNotIn("janitor sweeps `ci-smoke-routine-*`", fixture)
        self.assertNotIn("1f and 1g are best-effort", fixture)

    def test_generated_docs_show_the_current_version_everywhere(self) -> None:
        raw = SKILL.read_text(encoding="utf-8")
        _, frontmatter, _ = raw.split("---", 2)
        expected = f"v{yaml.safe_load(frontmatter)['metadata']['version']}"
        detail = (
            ROOT / "docs" / "skills" / "foundry-routines" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(f'<span class="badge ver">{expected}</span>', detail)

        card_pattern = re.compile(
            r'href="/awesome-gbb/skills/foundry-routines/">'
            r"foundry-routines</a>.{0,1600}"
            rf'<span class="badge ver">{re.escape(expected)}</span>',
            re.DOTALL,
        )
        listing_pages = (
            ROOT / "docs" / "skills" / "index.html",
            ROOT / "docs" / "plugins" / "awesome-gbb" / "index.html",
        )
        for page in listing_pages:
            with self.subTest(page=page.relative_to(ROOT)):
                self.assertRegex(page.read_text(encoding="utf-8"), card_pattern)


if __name__ == "__main__":
    unittest.main()

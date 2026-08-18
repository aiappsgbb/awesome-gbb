"""Regression contract for the capability-host lifecycle live fixture."""

from __future__ import annotations

import pathlib
import re
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "skills"
    / "foundry-caphost-lifecycle"
    / "test-fixture"
    / "consumer_prompt.md"
)
SKILL = ROOT / "skills" / "foundry-caphost-lifecycle" / "SKILL.md"
PIN = ROOT / "skills" / "foundry-caphost-lifecycle" / "references" / "upstream-pin.md"


class FoundryCaphostLifecycleFixtureContractTests(unittest.TestCase):
    def test_fixture_requires_execution_instead_of_catalog_review(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        for required in (
            "This is an EXECUTION smoke, not a catalog inspection.",
            "You MUST run every Bash code block below in order",
            "Do NOT inspect repo files",
            "do NOT run `validate-skills.py`",
            "Your only acceptable terminal state is a Bash tool call that writes",
            "/tmp/foundry-caphost-lifecycle-smoke-result",
            "never invoke `copilot` recursively",
            "Do NOT create or modify tracked repository files.",
            "The workflow has pre-provisioned shared CI infrastructure.",
            "printf 'SMOKE_RESULT=PASS\\n' > /tmp/foundry-caphost-lifecycle-smoke-result",
            "printf 'SMOKE_RESULT=FAIL <one-line reason>\\n' > /tmp/foundry-caphost-lifecycle-smoke-result",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

        self.assertTrue(bash_blocks, "fixture must contain executable Bash blocks")
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "Executing consumer smoke for '
            'skills/foundry-caphost-lifecycle/SKILL.md"',
        )

        for forbidden in (
            "Do whatever the skill tells you to do.",
            "read the skill's `SKILL.md`",
            "ran catalog validation",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_flat)

    def test_dependent_bash_blocks_restore_lifecycle_state(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)
        state_source = "source /tmp/foundry-caphost-lifecycle-state.env"
        dependent_commands = (
            "az cognitiveservices account create",
            "STATE=$(az cognitiveservices account show",
            "python3 - <<'PY'",
            "az rest --method get",
            "az cognitiveservices account delete",
            "FOUND=$(az cognitiveservices account list-deleted",
            "az cognitiveservices account purge",
            "STILL=$(az cognitiveservices account list-deleted",
        )

        self.assertIn(
            'STATE_FILE="/tmp/foundry-caphost-lifecycle-state.env"',
            fixture,
        )
        for block in bash_blocks:
            if any(command in block for command in dependent_commands):
                first_command = next(
                    line.strip()
                    for line in block.splitlines()
                    if line.strip() and not line.lstrip().startswith("#")
                )
                with self.subTest(first_command=first_command):
                    self.assertEqual(first_command, state_source)

    def test_python_helpers_execute_inline_without_checkout_writes(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)
        python_fences = re.findall(r"```python\n(.*?)```", fixture, re.DOTALL)
        heredoc_blocks = [
            block for block in bash_blocks if "python3 - <<'PY'" in block
        ]

        self.assertEqual(
            python_fences,
            [],
            "Python helper bodies must execute inside Bash heredocs",
        )
        self.assertEqual(
            len(heredoc_blocks),
            3,
            "create, idempotent replay, and delete each need an inline heredoc",
        )
        for block in heredoc_blocks:
            commands = [
                line.strip()
                for line in block.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            with self.subTest(first_command=commands[0]):
                self.assertEqual(
                    commands[0],
                    "source /tmp/foundry-caphost-lifecycle-state.env",
                )
                self.assertEqual(commands[-1], "PY")

        for forbidden in (
            "caphost_put.py",
            "caphost_delete.py",
            "python3 caphost_put.py",
            "python3 caphost_delete.py",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture)

    def test_fixture_uses_disposable_unlocked_resource_group(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn('RG="rg-awesome-gbb-caphost-ci"', fixture)
        self.assertIn(
            "dedicated unlocked disposable CI resource group",
            fixture,
        )
        self.assertNotIn('RG="rg-awesome-gbb-ci"', fixture)
        self.assertNotIn(
            "janitor sweeps `caphost-smoke-*`",
            fixture,
        )

    def test_full_account_lifecycle_is_hard_gated(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        fixture_flat = " ".join(fixture.split())

        for required in (
            '[[ "$SHAPE_OK" == "true" ]] || exit 1',
            "caphost_replay_status=",
            "caphost_absent_after_delete",
            '[[ "$FOUND" == "$ACCT" ]] || exit 1',
            '[[ -z "$STILL" ]] || exit 1',
            "Account entered the soft-delete index",
            "Account purge succeeded and the account left the soft-delete index",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture_flat)

        for forbidden in (
            "Pattern 25",
            "best-effort soft-PASS",
            "list-deleted -l",
            "true **even if Steps 7-9",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, fixture_flat)

    def test_pass_marker_requires_ordered_lifecycle_evidence(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        required_evidence = (
            "ACCOUNT_CREATED",
            "CAPHOST_CREATED",
            "CAPHOST_GET_OK",
            "CAPHOST_REPLAY_OK",
            "CAPHOST_DELETED",
            "ACCOUNT_SOFT_DELETED",
            "ACCOUNT_PURGED",
        )
        self.assertIn(
            'EVIDENCE_FILE="/tmp/foundry-caphost-lifecycle-smoke-evidence"',
            fixture,
        )
        for item in required_evidence:
            with self.subTest(item=item):
                self.assertIn(item, fixture)

        self.assertIn("EXPECTED_EVIDENCE=$(printf", fixture)
        self.assertIn('ACTUAL_EVIDENCE=$(cat "$EVIDENCE_FILE")', fixture)
        self.assertIn(
            '[[ "$ACTUAL_EVIDENCE" == "$EXPECTED_EVIDENCE" ]]',
            fixture,
        )

    def test_cli_failures_cannot_masquerade_as_absence(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")

        self.assertNotIn("list-deleted -l", fixture)
        self.assertNotIn("list-deleted -l", skill)
        self.assertNotIn('list-deleted \\\n            --query', fixture)
        self.assertIn("if ! FOUND=$(az cognitiveservices account list-deleted", fixture)
        self.assertIn("if ! STILL=$(az cognitiveservices account list-deleted", fixture)

    def test_incomplete_evidence_triggers_failure_cleanup(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        final_step = fixture.split(
            "## Step 10 — Marker contract (deterministic, MANDATORY)",
            maxsplit=1,
        )[1]

        for required in (
            "cleanup_failed_account()",
            'if ! active=$(az cognitiveservices account list -g "$RG"',
            'az cognitiveservices account delete -n "$ACCT" -g "$RG"',
            'az cognitiveservices account purge -l "$LOC" -n "$ACCT" -g "$RG"',
            'grep -qx \'ACCOUNT_CREATED\' "$EVIDENCE_FILE"',
            "active_after=",
            "if ! cleanup_failed_account; then",
            "NOTE: failure cleanup incomplete",
        ):
            with self.subTest(required=required):
                self.assertIn(required, final_step)
        self.assertNotIn(
            "az cognitiveservices account show",
            final_step,
        )

    def test_capability_host_management_is_rest_only(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")
        pin = PIN.read_text(encoding="utf-8")

        for content in (fixture, skill):
            self.assertNotIn("client.capability_hosts", content)
            self.assertNotIn("CognitiveServicesManagementClient", content)
        self.assertNotIn("azure-mgmt-cognitiveservices", fixture)
        self.assertNotIn("azure-mgmt-cognitiveservices", pin)
        self.assertIn("SDK support for capability host management isn't available", skill)
        self.assertIn("status not in (200, 201)", fixture)
        self.assertIn("CAPHOST_REPLAY_OK", fixture)

        _, frontmatter, _ = skill.split("---", 2)
        version = tuple(
            int(part)
            for part in yaml.safe_load(frontmatter)["metadata"]["version"].split(".")
        )
        self.assertGreaterEqual(version, (2, 0, 0))

    def test_rest_long_running_operations_reach_terminal_success(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        skill = SKILL.read_text(encoding="utf-8")

        self.assertGreaterEqual(
            fixture.count("time.monotonic() + 900"),
            2,
        )
        for required in (
            'location = response.headers.get("Location")',
            'retry_after = int(response.headers.get("Retry-After", "10"))',
            "caphost_delete_FAIL missing_location",
            "caphost_delete_FAIL initial_status=404",
            "caphost_delete_FAIL lro_status=404",
            'if lro_status == "Succeeded":',
            "caphost_delete_lro_succeeded",
        ):
            with self.subTest(required=required):
                self.assertIn(required, fixture)
        self.assertGreaterEqual(
            fixture.count('if state in ("Failed", "Canceled"):'),
            2,
        )
        self.assertIn(
            "PUT 201 uses `Azure-AsyncOperation`",
            skill,
        )
        self.assertIn(
            "DELETE 202 uses `Location` and `Retry-After`",
            skill,
        )

    def test_replay_identity_comes_from_terminal_get(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        replay = fixture.split(
            "## Step 5 — Idempotent replay",
            maxsplit=1,
        )[1].split("## Step 6 — DELETE", maxsplit=1)[0]

        self.assertIn(
            'current.get("id", "").lower().endswith(expected_suffix)',
            fixture,
        )
        self.assertNotIn(
            'payload.get("id", "").lower().endswith(expected_suffix)',
            fixture,
        )
        self.assertLess(
            replay.index('current.get("id", "").lower().endswith(expected_suffix)'),
            replay.index("break"),
        )

    def test_account_delete_and_purge_use_documented_budgets(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")

        self.assertIn("deadline=$((SECONDS + 300))", fixture)
        self.assertIn("deadline=$((SECONDS + 600))", fixture)


if __name__ == "__main__":
    unittest.main()

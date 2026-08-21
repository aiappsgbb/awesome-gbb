"""Regression contract for the foundry-network-runbook live fixture.

PR #464's second force-full run 32186896596 exposed two contradictory
assumptions: the fixture treated an unset LAW workspace secret as a broken
auth contract even though LAW is optional, and it carried the soft-skip state
only in a shell variable that cannot survive separate Bash tool calls.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT
    / "skills"
    / "foundry-network-runbook"
    / "test-fixture"
    / "consumer_prompt.md"
)
LAW_STATE_FILE = "/tmp/foundry-network-runbook-law-absent"


def _section(fixture: str, start: str, end: str) -> str:
    return fixture.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]


class FoundryNetworkRunbookFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE.read_text(encoding="utf-8")

    def test_only_core_azure_identity_is_mandatory_auth_context(self) -> None:
        auth = _section(self.fixture, "## Step 0", "## Step 1")
        auth_flat = " ".join(auth.split())

        self.assertIn(
            "Only `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and "
            "`AZURE_SUBSCRIPTION_ID` are mandatory.",
            auth_flat,
        )
        self.assertIn(
            "`LAW_WORKSPACE_ID` is optional",
            auth_flat,
        )
        self.assertIn(
            'echo "LAW_WORKSPACE_ID=${LAW_WORKSPACE_ID:+set}"',
            auth,
        )
        self.assertNotRegex(
            auth_flat,
            re.compile(
                r"If .*LAW_WORKSPACE_ID.* prints empty.*"
                r"Write the FAIL marker",
            ),
        )
        self.assertIn(
            "Gate execution only on those three core Azure identity variables.",
            auth_flat,
        )
        self.assertNotIn(
            "Do NOT gate flow on any of these checks",
            auth_flat,
        )

    def test_law_soft_skip_state_survives_separate_bash_tool_calls(self) -> None:
        auth = _section(self.fixture, "## Step 0", "## Step 1")
        law_probe = _section(
            self.fixture,
            "**a) Log Analytics workspace probe",
            "**b) Private DNS zone enumeration",
        )
        kusto_probe = _section(self.fixture, "## Step 3", "## Step 4")

        self.assertIn(f"rm -f {LAW_STATE_FILE}", auth)
        self.assertIn(f"rm -f {LAW_STATE_FILE}", law_probe)
        self.assertIn(f": > {LAW_STATE_FILE}", law_probe)
        self.assertIn(f"if [ ! -f {LAW_STATE_FILE} ]; then", kusto_probe)
        self.assertNotIn('if [ -z "${LAW_ABSENT}" ]; then', kusto_probe)

    def test_law_probe_soft_skips_only_confirmed_not_found(self) -> None:
        law_probe = _section(
            self.fixture,
            "**a) Log Analytics workspace probe",
            "**b) Private DNS zone enumeration",
        )
        bash_blocks = re.findall(r"```bash\n(.*?)```", law_probe, re.DOTALL)
        self.assertEqual(len(bash_blocks), 1)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_file = tmp_path / "law-absent"
            fake_az = tmp_path / "az"
            fake_az.write_text(
                "#!/usr/bin/env bash\n"
                'case "$FAKE_AZ_MODE" in\n'
                '  present) echo "law-awesome-gbb-ci"; exit 0 ;;\n'
                '  not_found) echo "(ResourceNotFound) workspace was not found" '
                ">&2; exit 3 ;;\n"
                '  auth_error) echo "(AuthorizationFailed) denied" >&2; exit 3 ;;\n'
                "esac\n",
                encoding="utf-8",
            )
            fake_az.chmod(0o755)
            command = bash_blocks[0].replace(LAW_STATE_FILE, str(state_file))
            env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}

            for mode, expected_returncode, expected_absent in (
                ("present", 0, False),
                ("not_found", 0, True),
                ("auth_error", 1, False),
            ):
                with self.subTest(mode=mode):
                    state_file.unlink(missing_ok=True)
                    result = subprocess.run(
                        ["bash", "-c", command],
                        env={**env, "FAKE_AZ_MODE": mode},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, expected_returncode)
                    self.assertEqual(state_file.exists(), expected_absent)


if __name__ == "__main__":
    unittest.main()

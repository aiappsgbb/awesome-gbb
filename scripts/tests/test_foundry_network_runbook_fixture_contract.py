"""Regression contract for the foundry-network-runbook live fixture.

PR #464's second force-full run 32186896596 exposed two contradictory
assumptions: the fixture treated an unset LAW workspace secret as a broken
auth contract even though LAW is optional, and it carried the soft-skip state
only in a shell variable that cannot survive separate Bash tool calls.
"""

from __future__ import annotations

import re
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


if __name__ == "__main__":
    unittest.main()

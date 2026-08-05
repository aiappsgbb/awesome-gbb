#!/usr/bin/env python3
"""Contract tests for the foundry-mcp-aca live fixture.

These tests enforce structural and behavioral contracts on consumer_prompt.md
that CI cannot catch through grep alone. They verify:
- Port lifecycle coherence (no placeholder/probe mismatch)
- Shell correctness (session header must use Bash arrays, not scalar quoting)
- MCP protocol conformance (initialized must be status-gated, not || true)
- Named tool invocation (echo with exact payload assertion, no first-tool fallback)
- Prose/hard-gate consistency (all three protocol steps listed)
- SKILL.md version is PATCH (1.2.4)
- Pin script validates mcp explicitly
"""

from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = (
    ROOT / "skills" / "foundry-mcp-aca" / "test-fixture" / "consumer_prompt.md"
)
SKILL_MD = ROOT / "skills" / "foundry-mcp-aca" / "SKILL.md"
PIN_FILE = (
    ROOT / "skills" / "foundry-mcp-aca" / "references" / "upstream-pin.md"
)


class FoundryMcpAcaFixtureContractTests(unittest.TestCase):
    """Structural contract tests for consumer_prompt.md."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE.read_text(encoding="utf-8")
        cls.skill = SKILL_MD.read_text(encoding="utf-8")
        cls.pin = PIN_FILE.read_text(encoding="utf-8")

    # --- Issue #1: Port lifecycle coherence ---

    def test_no_probe_port_mismatch_with_placeholder(self) -> None:
        """If probes target port 8080, no placeholder image serving port 80."""
        has_probe_8080 = "port: 8080" in self.fixture and "probes:" in self.fixture
        has_placeholder_80 = "containerapps-helloworld" in self.fixture
        # Both cannot coexist — probes on 8080 will never pass against a port-80 image
        self.assertFalse(
            has_probe_8080 and has_placeholder_80,
            "Fixture has probes targeting port 8080 with a placeholder image "
            "that serves on port 80 — the startup probe can never become healthy "
            "during the placeholder window, potentially blocking azd provision.",
        )

    # --- Issue #2: Session header shell correctness ---

    def test_session_header_uses_bash_array(self) -> None:
        """Session header must use Bash array, not scalar with embedded quotes."""
        # Anti-pattern: SESSION_HEADER="-H \"mcp-session-id: $SESSION_ID\""
        self.assertNotIn(
            'SESSION_HEADER="-H',
            self.fixture,
            "Session header uses scalar with embedded quotes — shell does not "
            "re-parse quotes in variable expansions. Use a Bash array instead.",
        )
        # Must use array pattern
        self.assertIn("SESSION_ARGS", self.fixture)

    # --- Issue #3: notifications/initialized must be status-gated ---

    def test_initialized_notification_captures_status(self) -> None:
        """notifications/initialized must NOT be silently swallowed with || true."""
        # Find the notifications/initialized section
        init_section_match = re.search(
            r'notifications/initialized.*?\n```', self.fixture, re.DOTALL
        )
        self.assertIsNotNone(init_section_match, "notifications/initialized section not found")
        init_section = init_section_match.group(0)
        # Must NOT use bare || true that swallows HTTP errors
        self.assertNotIn(
            "|| true",
            init_section,
            "notifications/initialized uses `|| true` which swallows failures — "
            "must capture and assert HTTP status.",
        )

    # --- Issue #4: Named tool invocation with exact payload ---

    def test_tools_call_uses_named_tool_not_first_fallback(self) -> None:
        """tools/call must invoke a named tool with known args, not fallback to first."""
        # Anti-pattern: FIRST_TOOL=$(... .result.tools[0].name ...) then call with {}
        self.assertNotIn(
            "FIRST_TOOL",
            self.fixture,
            "Fixture uses dynamic first-tool fallback — must invoke a named tool "
            "(echo) with known arguments and assert exact payload.",
        )

    def test_tools_call_asserts_exact_echo_payload(self) -> None:
        """tools/call on echo must assert 'echoed: <probe>' in response."""
        self.assertIn(
            "echoed:",
            self.fixture,
            "Fixture does not assert exact echo payload — must verify "
            "'echoed: <probe>' in tools/call response.",
        )

    def test_tools_call_asserts_no_error(self) -> None:
        """tools/call must verify isError is not true."""
        self.assertIn(
            "isError",
            self.fixture,
            "Fixture does not check isError — must verify tools/call "
            "did not return an error response.",
        )

    # --- Issue #5: Prose/hard-gate consistency ---

    def test_intro_mentions_tools_call(self) -> None:
        """Fixture intro must mention tools/call as part of the acceptance criteria."""
        # First 20 lines = intro section
        intro = "\n".join(self.fixture.split("\n")[:20])
        self.assertIn(
            "tools/call",
            intro,
            "Fixture intro does not mention tools/call — hard gates must include "
            "all three protocol steps (initialize + tools/list + tools/call).",
        )

    def test_hard_gates_list_includes_tools_call(self) -> None:
        """Pattern 25 hard gate list must include tools/call."""
        # Find the hard gates section
        gates_match = re.search(
            r"hard gates.*?(?=\n---|\nDo NOT chain)",
            self.fixture,
            re.DOTALL | re.IGNORECASE,
        )
        self.assertIsNotNone(gates_match)
        gates_section = gates_match.group(0)
        self.assertIn("tools/call", gates_section)

    # --- Issue #6: Correct dates (2026, not 2025) ---

    def test_spec_has_correct_year(self) -> None:
        """Design spec must use 2026, not 2025."""
        spec_path = ROOT / "docs" / "superpowers" / "specs" / "foundry-mcp-aca-refresh-1.2.4.md"
        if spec_path.exists():
            spec = spec_path.read_text(encoding="utf-8")
            self.assertNotIn("2025-08-05", spec, "Spec has wrong year — should be 2026")

    # --- Issue #7: PATCH version ---

    def test_skill_version_is_patch(self) -> None:
        """SKILL.md version must be 1.2.4 (PATCH)."""
        self.assertIn('version: "1.2.4"', self.skill)

    # --- Pin validation contracts ---

    def test_pin_script_installs_mcp_explicitly(self) -> None:
        """Pin validation script must explicitly install mcp with bounded specifier."""
        self.assertRegex(
            self.pin,
            r"mcp[~>=<]",
            "Pin script does not install mcp explicitly — must use bounded specifier.",
        )

    def test_pin_script_asserts_mcp_version(self) -> None:
        """Pin script must assert mcp version via importlib.metadata."""
        self.assertIn("importlib.metadata", self.pin)
        self.assertIn("mcp", self.pin)

    def test_pin_script_asserts_jobs_operations(self) -> None:
        """Pin script must assert JobsOperations.get and begin_create_or_update."""
        self.assertIn("JobsOperations", self.pin)
        self.assertIn("get", self.pin)
        self.assertIn("begin_create_or_update", self.pin)

    def test_ki001_does_not_claim_fastmcp3_requires_mcp2(self) -> None:
        """KI-001 must not claim FastMCP 3 requires MCP 2 — it still pins mcp<2."""
        self.assertNotIn("requires mcp>=2.0", self.pin)
        self.assertNotIn("requires mcp>=2", self.pin.split("KI-001")[1].split("KI-002")[0] if "KI-002" in self.pin else self.pin.split("KI-001")[1])

    # --- Skill acknowledgment (preserved from original) ---

    def test_fixture_acknowledges_skill_before_step_zero(self) -> None:
        acknowledgement = 'echo "skills/foundry-mcp-aca/SKILL.md"'
        self.assertIn("## Step -1", self.fixture)
        self.assertIn(acknowledgement, self.fixture)
        self.assertLess(
            self.fixture.index(acknowledgement), self.fixture.index("## Step 0")
        )


if __name__ == "__main__":
    unittest.main()

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

import json
import pathlib
import re
import subprocess
import tempfile
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

    # --- Issue #8: Registry must not derive server from placeholder image ---

    def test_registry_uses_explicit_acr_param_not_image_split(self) -> None:
        """Registries must use an explicit ACR server param, not split(image, '/')[0].

        When the default image is mcr.microsoft.com/..., split(image, '/')[0]
        resolves to 'mcr.microsoft.com' — registering MCR as a managed-identity
        registry, which fails because MCR is public and doesn't accept MI tokens.
        """
        self.assertNotIn(
            "split(image, '/')[0]",
            self.fixture,
            "Bicep uses split(image, '/')[0] for registry server — this resolves "
            "to mcr.microsoft.com when image is the MCR placeholder, causing "
            "managed-identity pull failure. Use an explicit acrServer param.",
        )

    def test_registry_server_references_acr_param(self) -> None:
        """Registries block must reference an explicit ACR server parameter."""
        # Must have an acrServer or acrLoginServer param in the Bicep
        self.assertRegex(
            self.fixture,
            r"param\s+acr(Server|LoginServer)\s+string",
            "Bicep must declare an explicit ACR server parameter for registries.",
        )

    # --- Issue #9: Unique service identity per run ---

    def test_service_tag_uses_app_name_variable(self) -> None:
        """azd-service-name must use $APP_NAME, not static 'mcp'."""
        # Find the Bicep tags block; static 'mcp' causes collision in shared RG
        bicep_match = re.search(
            r"tags:\s*\{[^}]*azd-service-name[^}]*\}",
            self.fixture, re.DOTALL
        )
        self.assertIsNotNone(bicep_match, "azd-service-name tag not found in Bicep")
        tag_block = bicep_match.group(0)
        # Must NOT be hardcoded 'mcp' — must reference appName param
        self.assertNotIn(
            "'mcp'",
            tag_block,
            "azd-service-name uses static 'mcp' — causes collision in shared CI RG. "
            "Must use appName parameter for per-run uniqueness.",
        )

    def test_azure_yaml_service_key_matches_bicep_tag(self) -> None:
        """azure.yaml service key must not be static 'mcp' if Bicep uses variable tag."""
        # The azure.yaml is now generated via heredoc with ${APP_NAME} as service key
        # Verify the fixture uses $APP_NAME (or ${APP_NAME}) in the services block
        self.assertRegex(
            self.fixture,
            r"\$\{?APP_NAME\}?:\s*\n\s+project:",
            "azure.yaml service key must use $APP_NAME (dynamic) not a static string. "
            "Must match dynamic Bicep azd-service-name for per-run uniqueness.",
        )

    # --- Issue #10: Session ID must be required, not optional ---

    def test_session_id_empty_is_fail(self) -> None:
        """Fixture must FAIL if Mcp-Session-Id is empty after initialize."""
        # Must contain an explicit empty-session-ID check that writes FAIL
        session_section = self.fixture[self.fixture.index("SESSION_ID="):]
        session_section = session_section[:session_section.index("```", 100)]
        self.assertRegex(
            session_section,
            r'-z.*SESSION_ID|SESSION_ID.*empty|FAIL.*session',
            "Fixture does not FAIL on empty session ID — FastMCP always assigns one, "
            "so empty means the protocol handshake is broken.",
        )

    # --- Issue #11: MCP 2025-06-18 protocol conformance ---

    def test_initialized_requires_http_202(self) -> None:
        """notifications/initialized must require HTTP 202, not any 2xx."""
        init_section = self.fixture[self.fixture.index("notifications/initialized"):]
        init_section = init_section[:init_section.index("```", 200)]
        # Must check for exactly 202, not a range
        self.assertIn(
            "202",
            init_section,
            "notifications/initialized must require HTTP 202 per MCP spec — "
            "notifications return 202 Accepted, not 200 OK.",
        )

    def test_protocol_version_captured_from_initialize(self) -> None:
        """Initialize response must capture result.protocolVersion."""
        # Must extract protocolVersion into a variable (between initialize and Step 5b)
        init_section = self.fixture[self.fixture.index("## Step 5"):]
        init_section = init_section[:init_section.index("## Step 5b")]
        self.assertIn(
            "protocolVersion",
            init_section,
            "protocolVersion not captured from initialize response.",
        )
        # Must extract it into a variable for subsequent headers
        self.assertRegex(
            self.fixture,
            r"PROTOCOL_VERSION.*protocolVersion|protocolVersion.*PROTOCOL_VERSION",
            "protocolVersion not extracted into PROTOCOL_VERSION variable.",
        )

    def test_protocol_version_header_on_subsequent_requests(self) -> None:
        """MCP-Protocol-Version header required on tools/list and tools/call."""
        after_init = self.fixture[self.fixture.index("tools/list"):]
        self.assertIn(
            "MCP-Protocol-Version",
            after_init,
            "MCP-Protocol-Version header missing from subsequent requests — "
            "required by MCP 2025-06-18 spec for HTTP transport.",
        )

    # --- Issue #12: Stale probe prose ---

    def test_no_stale_probe_prose(self) -> None:
        """No references to probe configuration that was removed."""
        # Step 2 area should not claim probes are configured
        step2_match = re.search(r"## Step 2.*?## Step", self.fixture, re.DOTALL)
        if step2_match:
            step2 = step2_match.group(0)
            self.assertNotIn(
                "startup probes against",
                step2,
                "Step 2 still references startup probes — probes were removed.",
            )

    # --- Issue #13: Failure list synchronized ---

    def test_failure_list_includes_session_id(self) -> None:
        """Failure summary must include missing session ID."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertRegex(
            fail_section,
            r"[Ss]ession|Mcp-Session-Id",
            "Failure list does not mention missing session ID.",
        )

    def test_failure_list_includes_tools_call(self) -> None:
        """Failure summary must include tools/call failures."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertIn(
            "tools/call",
            fail_section,
            "Failure list does not mention tools/call failures.",
        )

    def test_failure_list_includes_initialized_status(self) -> None:
        """Failure summary must include initialized notification status."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        self.assertRegex(
            fail_section,
            r"initialized.*202|notifications/initialized",
            "Failure list does not mention initialized notification status.",
        )

    # --- Issue #14: No search_orders_filtered fallback ---

    def test_no_search_orders_filtered_fallback(self) -> None:
        """Fixture must not reference search_orders_filtered (server only has echo)."""
        self.assertNotIn(
            "search_orders_filtered",
            self.fixture,
            "Fixture references search_orders_filtered but the deployed server "
            "only exposes 'echo'. Remove unreachable fallback.",
        )

    # --- Issue #15: Pin regex must not match fastmcp suffix ---

    def test_pin_mcp_regex_excludes_fastmcp(self) -> None:
        """Pin regex for mcp must not match the 'mcp' suffix of 'fastmcp~='."""
        # Find lines with 'mcp' pin specifiers — must be word-boundary safe
        # Extract the pip install line for standalone mcp
        pin_lines = [
            l for l in self.pin.splitlines()
            if "mcp" in l and ("~=" in l or ">=" in l or "==" in l)
        ]
        # There must be a line that starts with 'mcp' (not 'fastmcp')
        standalone_mcp = [l for l in pin_lines if re.search(r'(?<![a-z])mcp[~>=<]', l)]
        self.assertTrue(
            standalone_mcp,
            "Pin script has no standalone 'mcp' specifier — the regex "
            "'mcp[~>=<]' would match the suffix of 'fastmcp~='. "
            "Must have an explicit 'mcp~=X.Y.Z' or '\"mcp~=X.Y.Z\"' line.",
        )

    # --- Issue #16: SKILL protocol claims correctness ---

    def test_skill_notifications_return_202_not_200(self) -> None:
        """SKILL.md must state notifications/initialized returns HTTP 202, not 200."""
        protocol_section = self.skill[self.skill.index("## MCP Protocol Requirements"):]
        protocol_section = protocol_section[:protocol_section.index("## ", 5)]
        # Must NOT claim ALL methods return HTTP 200 — notifications return 202
        self.assertNotIn(
            "ALL 6 JSON-RPC methods must return HTTP 200",
            protocol_section,
            "SKILL.md falsely claims ALL 6 methods return HTTP 200 — "
            "notifications/initialized returns HTTP 202 per MCP 2025-06-18 spec.",
        )

    def test_skill_initialized_not_can_return_empty(self) -> None:
        """SKILL.md must not say notifications/initialized 'Can return {}'."""
        # Find the protocol table
        protocol_section = self.skill[self.skill.index("## MCP Protocol Requirements"):]
        protocol_section = protocol_section[:protocol_section.index("## ", 5)]
        # initialized is a notification — 202 with no body, not 200 with {}
        self.assertNotIn(
            "Can return `{}`",
            protocol_section,
            "SKILL.md says initialized 'Can return {}' — per MCP 2025-06-18, "
            "accepted notifications return HTTP 202 with no body.",
        )

    def test_skill_gotchas_notifications_not_200(self) -> None:
        """Gotchas table must not claim all methods return HTTP 200."""
        gotchas_section = self.skill[self.skill.index("## Gotchas"):]
        # The gotchas fix column says "All 6 ... must return HTTP 200"
        self.assertNotIn(
            "All 6 JSON-RPC methods must return HTTP 200",
            gotchas_section,
            "Gotchas table repeats the wrong claim — notifications return 202.",
        )

    # --- Issue #17: Initialized body assertion ---

    def test_initialized_asserts_empty_body_or_no_body(self) -> None:
        """notifications/initialized must verify body is empty (202 = no body)."""
        # Find the bash block that actually sends notifications/initialized
        init_curl_idx = self.fixture.index('"method": "notifications/initialized"')
        block_start = self.fixture.rfind("```bash", 0, init_curl_idx)
        block_end = self.fixture.index("```", init_curl_idx)
        block_content = self.fixture[block_start:block_end]
        has_body_check = (
            "body" in block_content.lower()
            or "INIT_NOTIFY_BODY" in block_content
            or "empty" in block_content.lower()
        )
        self.assertTrue(
            has_body_check,
            "notifications/initialized must verify response body is empty "
            "(HTTP 202 = accepted notification, no body per MCP spec).",
        )

    # --- Issue #18: Failure contract completeness ---

    def test_failure_list_includes_protocol_version(self) -> None:
        """Failure summary must mention protocol version negotiation failure."""
        fail_section = self.fixture[self.fixture.rindex("## Summary of FAIL"):]
        has_protocol = (
            "protocolVersion" in fail_section
            or "protocol version" in fail_section.lower()
            or "MCP-Protocol-Version" in fail_section
        )
        self.assertTrue(
            has_protocol,
            "Failure list does not mention protocol version negotiation — "
            "missing negotiated version or MCP-Protocol-Version replay is a FAIL.",
        )

    # --- Issue #19: Scoped echo assertion ---

    def test_echo_assertion_in_tools_call_block(self) -> None:
        """'echoed:' assertion must be in the same bash block as tools/call."""
        call_idx = self.fixture.rindex('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_idx)
        block_end = self.fixture.index("```", call_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "echoed:",
            block_content,
            "'echoed:' assertion must appear in the bash block containing tools/call.",
        )

    def test_isError_assertion_in_tools_call_block(self) -> None:
        """isError check must be in the same bash block as tools/call."""
        call_idx = self.fixture.rindex('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_idx)
        block_end = self.fixture.index("```", call_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "isError",
            block_content,
            "isError check must appear in the bash block containing tools/call.",
        )

    # --- Issue #20: Spec date must not silently skip ---

    def test_spec_file_exists(self) -> None:
        """Design spec file must exist — test should not silently skip."""
        spec_path = ROOT / "docs" / "superpowers" / "specs" / "foundry-mcp-aca-refresh-1.2.4.md"
        self.assertTrue(
            spec_path.exists(),
            f"Design spec file does not exist: {spec_path}",
        )

    # --- Issue #21: SESSION_ARGS replayed on all three requests ---

    def test_session_args_on_initialized(self) -> None:
        """SESSION_ARGS must be used on notifications/initialized curl request."""
        # Find the actual curl command for initialized (the bash block containing it)
        init_curl_idx = self.fixture.index('notifications/initialized", "params"')
        block_start = self.fixture.rfind("```bash", 0, init_curl_idx)
        block_end = self.fixture.index("```", init_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on notifications/initialized curl.",
        )

    def test_session_args_on_tools_list(self) -> None:
        """SESSION_ARGS must be used on tools/list curl request."""
        list_curl_idx = self.fixture.index('"method": "tools/list"')
        block_start = self.fixture.rfind("```bash", 0, list_curl_idx)
        block_end = self.fixture.index("```", list_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on tools/list curl.",
        )

    def test_session_args_on_tools_call(self) -> None:
        """SESSION_ARGS must be used on tools/call curl request."""
        call_curl_idx = self.fixture.index('"method": "tools/call"')
        block_start = self.fixture.rfind("```bash", 0, call_curl_idx)
        block_end = self.fixture.index("```", call_curl_idx)
        block_content = self.fixture[block_start:block_end]
        self.assertIn(
            "SESSION_ARGS[@]",
            block_content,
            "SESSION_ARGS must be replayed on tools/call curl.",
        )

    # --- Skill acknowledgment (preserved from original) ---

    def test_fixture_acknowledges_skill_before_step_zero(self) -> None:
        acknowledgement = 'echo "skills/foundry-mcp-aca/SKILL.md"'
        self.assertIn("## Step -1", self.fixture)
        self.assertIn(acknowledgement, self.fixture)
        self.assertLess(
            self.fixture.index(acknowledgement), self.fixture.index("## Step 0")
        )


class TestStatePersistence(unittest.TestCase):
    """Bash tool calls run in fresh processes; env vars don't persist."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = FIXTURE.read_text(encoding="utf-8")

    def test_state_file_written_after_naming(self):
        """All cross-shell deployment values must be persisted after naming."""
        self.assertIn('STATE_FILE="/tmp/foundry-mcp-aca-state.env"', self.fixture)
        for variable in ("APP_NAME", "PROJECT_DIR", "UAMI_RESOURCE_ID", "ACR_SERVER"):
            self.assertRegex(
                self.fixture,
                rf'echo "{variable}=.*" >{{1,2}} "\$STATE_FILE"',
                f"{variable} must be persisted to the fixture state file.",
            )

    def test_scaffolding_block_uses_restored_state_without_reassignment(self):
        """The fresh-shell scaffold must trust every persisted Step 1 value."""
        state_path = pathlib.Path("/tmp/foundry-mcp-aca-state.env")

        def bash_block_containing(marker: str) -> str:
            marker_index = self.fixture.index(marker)
            block_start = self.fixture.rfind("```bash\n", 0, marker_index)
            block_end = self.fixture.index("```", marker_index)
            return self.fixture[block_start + len("```bash\n"):block_end]

        state_block = bash_block_containing(
            'STATE_FILE="/tmp/foundry-mcp-aca-state.env"'
        )
        scaffolding_block = bash_block_containing(
            'mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"'
        )
        source_index = scaffolding_block.index(
            "source /tmp/foundry-mcp-aca-state.env"
        )
        restored_body = scaffolding_block[source_index:]
        persisted_variables = (
            "APP_NAME",
            "PROJECT_DIR",
            "UAMI_RESOURCE_ID",
            "ACR_SERVER",
        )
        reassigned = re.findall(
            rf"^\s*(?:export\s+)?({'|'.join(persisted_variables)})=",
            restored_body,
            re.MULTILINE,
        )
        self.assertEqual(
            [],
            reassigned,
            "the scaffolding block must not reassign persisted variables after "
            f"sourcing Step 1 state; found {reassigned}",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = pathlib.Path(temp_dir)
            restored_project_dir = workspace / "restored-from-state"
            state_path.unlink(missing_ok=True)
            self.addCleanup(state_path.unlink, missing_ok=True)
            workflow_env = {
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(workspace),
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }
            create_state = subprocess.run(
                ["bash", "-c", state_block],
                env=workflow_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                0,
                create_state.returncode,
                f"shipped Step 1 state creation failed: {create_state.stderr!r}",
            )
            state_lines = state_path.read_text(encoding="utf-8").splitlines()
            state_path.write_text(
                "\n".join(
                    (
                        f"PROJECT_DIR={restored_project_dir}"
                        if line.startswith("PROJECT_DIR=")
                        else line
                    )
                    for line in state_lines
                )
                + "\n",
                encoding="utf-8",
            )

            scaffold = subprocess.run(
                ["bash", "-c", scaffolding_block],
                env=workflow_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                0,
                scaffold.returncode,
                "shipped scaffolding block failed after sourcing Step 1 state: "
                f"{scaffold.stderr!r}",
            )
            self.assertTrue(
                (restored_project_dir / "src").is_dir()
                and (restored_project_dir / "infra").is_dir(),
                "the scaffolding block must create directories under the "
                "PROJECT_DIR restored from persisted state",
            )

    def test_azure_yaml_block_sources_state(self):
        """The azure.yaml heredoc block must source state first."""
        # Find the azure.yaml heredoc
        azdyaml_idx = self.fixture.index("<<AZDYAML")
        # Find the bash block start before it
        block_start = self.fixture.rfind("```bash", 0, azdyaml_idx)
        block_content = self.fixture[block_start:azdyaml_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "azure.yaml heredoc bash block must source state file"
        )

    def test_azd_up_block_sources_state(self):
        """The azd up retry block must source state first."""
        azdup_idx = self.fixture.index("until azd up --no-prompt")
        block_start = self.fixture.rfind("```bash", 0, azdup_idx)
        block_content = self.fixture[block_start:azdup_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "azd up block must source state file"
        )

    def test_mcp_probe_block_sources_state(self):
        """The MCP probe block must source state for APP_NAME fallback."""
        fqdn_idx = self.fixture.index("FQDN=$(azd env get-values")
        block_start = self.fixture.rfind("```bash", 0, fqdn_idx)
        block_content = self.fixture[block_start:fqdn_idx]
        self.assertIn(
            "source /tmp/foundry-mcp-aca-state.env", block_content,
            "MCP probe block must source state file"
        )

    def test_azure_tenant_id_in_azd_env(self):
        """azd env .env must include AZURE_TENANT_ID for federated-credential CI."""
        self.assertIn(
            'AZURE_TENANT_ID=${AZURE_TENANT_ID}',
            self.fixture,
            "AZURE_TENANT_ID must be written to the azd .env file"
        )

    def test_no_azd_env_new_or_set(self):
        """Fixture bash blocks must NOT use 'azd env new' or 'azd env set'."""
        import re
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        self.assertNotIn(
            'azd env new',
            combined,
            "azd env new requires interactive prompts; use direct file creation"
        )
        self.assertNotIn(
            'azd env set ',
            combined,
            "azd env set requires interactive prompts; write .env directly"
        )

    def test_state_persistence_documentation(self):
        """Fixture must document the state-persistence requirement."""
        self.assertIn(
            "State persistence between Bash tool calls", self.fixture,
            "Fixture must have a section explaining state persistence"
        )

    # --- Round 7: Heredoc, state, protocol, anchoring ---

    def test_parameters_json_escapes_schema_in_expanding_heredoc(self):
        """The heredoc must preserve $schema while expanding deployment values."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        self.assertRegex(
            combined,
            r"cat\s*>\s*.*parameters\.json.*<<\s*PARAMS",
            "main.parameters.json must use an expanding heredoc so deployment "
            "values are rendered instead of preserved as literal placeholders.",
        )
        self.assertIn(
            r'"\$schema"',
            combined,
            "main.parameters.json must escape only the $schema key.",
        )

    def test_parameters_json_heredoc_preserves_schema_and_expands_values(self):
        """Replay Step 1 state in a fresh shell before executing Step 3."""
        state_path = "/tmp/foundry-mcp-aca-state.env"

        def bash_block_containing(marker: str) -> str:
            marker_index = self.fixture.index(marker)
            block_start = self.fixture.rfind("```bash\n", 0, marker_index)
            block_end = self.fixture.index("```", marker_index)
            return self.fixture[block_start + len("```bash\n"):block_end]

        state_block = bash_block_containing(f'STATE_FILE="{state_path}"')
        parameters_block = bash_block_containing(
            'cat > "${PROJECT_DIR}/infra/main.parameters.json"'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = pathlib.Path(temp_dir)
            persisted_state = pathlib.Path(state_path)
            persisted_state.unlink(missing_ok=True)
            self.addCleanup(persisted_state.unlink, missing_ok=True)
            workflow_env = {
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "GITHUB_WORKSPACE": str(workspace),
                "AZURE_SUBSCRIPTION_ID": "test-subscription",
                "ACR_LOGIN_SERVER": "test.azurecr.io",
            }
            create_state = subprocess.run(
                [
                    "bash",
                    "-c",
                    state_block,
                ],
                env=workflow_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                create_state.returncode,
                0,
                f"shipped Step 1 state creation failed: stderr={create_state.stderr!r}",
            )
            state_values = dict(
                line.split("=", 1)
                for line in persisted_state.read_text().splitlines()
                if "=" in line
            )
            project_dir = pathlib.Path(state_values["PROJECT_DIR"])
            (project_dir / "infra").mkdir(parents=True)

            render_parameters = subprocess.run(
                [
                    "bash",
                    "-c",
                    parameters_block,
                ],
                env=workflow_env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                render_parameters.returncode,
                0,
                "shipped Step 3 parameters block failed after sourcing Step 1 state: "
                f"stderr={render_parameters.stderr!r}",
            )
            rendered = json.loads(
                (project_dir / "infra" / "main.parameters.json").read_text()
            )

        expected_uami = (
            "/subscriptions/test-subscription/resourceGroups/rg-awesome-gbb-ci/"
            "providers/Microsoft.ManagedIdentity/userAssignedIdentities/"
            "uami-awesome-gbb-ci"
        )
        self.assertRegex(
            state_values["APP_NAME"],
            r"^ci-smoke-mcp-[0-9a-f]{8}$",
            "the exact Step 1 state block must generate and persist APP_NAME",
        )
        self.assertIn("$schema", rendered)
        self.assertEqual(
            rendered["parameters"]["appName"]["value"], state_values["APP_NAME"]
        )
        self.assertEqual(state_values.get("UAMI_RESOURCE_ID"), expected_uami)
        self.assertEqual(state_values.get("ACR_SERVER"), "test.azurecr.io")
        self.assertEqual(
            rendered["parameters"]["uamiResourceId"]["value"], expected_uami
        )
        self.assertEqual(
            rendered["parameters"]["acrServer"]["value"], "test.azurecr.io"
        )

    def test_protocol_version_fails_if_empty(self):
        """Fixture must FAIL if negotiated protocolVersion is empty."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        # Must have an explicit fail gate on empty PROTOCOL_VERSION
        self.assertRegex(
            combined,
            r'(if\s+\[\s+-z\s+"\$PROTOCOL_VERSION"\s*\]|'
            r'\[\s+-z\s+"\$PROTOCOL_VERSION"\s*\]\s*&&)',
            "Fixture must FAIL deterministically when protocolVersion is empty — "
            "the MCP spec requires a negotiated version.",
        )

    def test_protocol_version_header_unconditional(self):
        """MCP-Protocol-Version header must be added unconditionally (not gated on -n)."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        # The conditional pattern `[ -n "$PROTOCOL_VERSION" ] && SESSION_ARGS+=` is wrong
        self.assertNotRegex(
            combined,
            r'\[\s+-n\s+"\$PROTOCOL_VERSION"\s*\]\s*&&\s*SESSION_ARGS',
            "MCP-Protocol-Version header must be unconditional — protocol version "
            "is mandatory per MCP 2025-06-18; conditional add defeats the FAIL gate.",
        )

    def test_mcp_exchange_state_persisted_to_file(self):
        """FQDN, SESSION_ID, PROTOCOL_VERSION must be persisted to STATE_FILE."""
        blocks = re.findall(r'```bash\n(.*?)```', self.fixture, re.DOTALL)
        combined = '\n'.join(blocks)
        for var in ("FQDN", "SESSION_ID", "PROTOCOL_VERSION"):
            self.assertRegex(
                combined,
                rf'echo\s+"?{var}=',
                f"{var} must be appended/written to STATE_FILE for cross-fence persistence",
            )

    def test_initialized_notification_captures_status_scoped(self):
        """notifications/initialized status gate must be in the actual enforcement block."""
        # Find the bash block containing the actual curl for notifications/initialized
        method_marker = '"method": "notifications/initialized"'
        idx = self.fixture.find(method_marker)
        self.assertGreater(idx, 100, "enforcement block for notifications/initialized not found")
        # Find the containing bash block
        block_start = self.fixture.rfind("```bash", 0, idx)
        block_end = self.fixture.find("```", idx)
        enforcement_block = self.fixture[block_start:block_end]
        # Must contain the 202 status check
        self.assertIn("!= \"202\"", enforcement_block,
                      "The enforcement block must assert HTTP 202 for notifications/initialized")
        # Must NOT contain || true
        self.assertNotIn("|| true", enforcement_block,
                         "notifications/initialized must not swallow failures with || true")

    def test_initialized_requires_http_202_scoped(self):
        """HTTP 202 gate must be in the enforcement block, not just mentioned in prose."""
        method_marker = '"method": "notifications/initialized"'
        idx = self.fixture.find(method_marker)
        self.assertGreater(idx, 100)
        block_start = self.fixture.rfind("```bash", 0, idx)
        block_end = self.fixture.find("```", idx)
        enforcement_block = self.fixture[block_start:block_end]
        # Must have FAIL on non-202
        self.assertIn("SMOKE_RESULT=FAIL", enforcement_block,
                      "notifications/initialized must write FAIL marker on non-202")

    def test_skill_consumer_config_no_trailing_slash(self):
        """SKILL.md consumer config must use /mcp (no trailing slash) for FastMCP 2.x."""
        skill = SKILL_MD.read_text(encoding="utf-8")
        # Find the consumer config JSON block with url field
        config_match = re.search(r'"url":\s*"https://[^"]+/mcp/"', skill)
        self.assertIsNone(
            config_match,
            "SKILL.md consumer config uses /mcp/ (trailing slash) but pinned FastMCP 2.x "
            "returns 307 for trailing slash. Use /mcp (no slash).",
        )


    def test_anti_catalog_inspection_guard(self):
        """Fixture must explicitly forbid reading catalog source files."""
        # The guard must name specific forbidden paths
        self.assertIn("Do NOT read, view, grep, glob, or open ANY repository file",
                      self.fixture)
        for forbidden in ["SKILL.md", "scripts/tests/", ".github/workflows/",
                          "skill-deps.yml"]:
            self.assertIn(forbidden, self.fixture[:2000],
                          f"Anti-catalog-inspection guard must mention '{forbidden}' "
                          "in the preamble (first 2000 chars)")


    # --- Blocker 1: auth curl targets must use /mcp not /mcp/ ---
    def test_auth_curl_targets_use_canonical_mcp_path(self):
        """Step 5b auth curl targets must use /mcp (no trailing slash).
        FastMCP 2.14.7 returns 307 for /mcp/ which breaks non-redirect curls."""
        # Extract Step 5b auth section (after MCP_AUTH_APP_CLIENT_ID check)
        auth_section = ""
        in_auth = False
        for line in self.fixture.split("\n"):
            if "MCP_AUTH_APP_CLIENT_ID" in line:
                in_auth = True
            if in_auth:
                auth_section += line + "\n"
        # All curl URLs in auth section must use /mcp" not /mcp/"
        import re
        curl_urls = re.findall(r'https://\$\{FQDN\}/mcp/?["\']?\)', auth_section)
        for url in curl_urls:
            self.assertNotIn("/mcp/", url,
                             "Auth curl target must use /mcp (no trailing slash); "
                             "FastMCP 2.14.7 returns 307 for /mcp/")

    # --- Blocker 2: malformed JSON must not bypass tools/list gate ---
    def test_tools_list_gate_handles_malformed_json(self):
        """TOOL_COUNT assignment must use jq -e or explicit parse guard so
        malformed JSON cannot silently bypass the >=1 check."""
        # Find the TOOL_COUNT assignment block
        import re
        # The gate must either use jq -e, or have an explicit empty/error guard
        tool_count_match = re.search(
            r'TOOL_COUNT=\$\(.*?\)', self.fixture, re.DOTALL)
        self.assertIsNotNone(tool_count_match, "TOOL_COUNT assignment not found")
        tc_line = tool_count_match.group(0)
        # Must have explicit malformed-JSON protection:
        # Either jq -e (exits non-zero on null/false), or a subsequent
        # empty-string guard before the arithmetic comparison
        has_jq_e = "jq -e" in tc_line
        # Check for explicit empty guard after assignment
        tc_pos = tool_count_match.end()
        next_100 = self.fixture[tc_pos:tc_pos + 200]
        has_empty_guard = ('[ -z "$TOOL_COUNT" ]' in next_100 or
                           '[ -z "${TOOL_COUNT' in next_100 or
                           'TOOL_COUNT:-' in next_100 or
                           '|| {' in tc_line or
                           '|| printf' in tc_line or
                           '|| exit' in tc_line)
        self.assertTrue(has_jq_e or has_empty_guard,
                        "TOOL_COUNT gate must protect against malformed JSON: "
                        "use 'jq -e' or guard empty TOOL_COUNT before arithmetic test. "
                        f"Found: {tc_line}")

    def test_tools_list_gate_enforces_jsonrpc_tools_array_contract(self):
        """Execute the shipped gate against valid and invalid tools/list bodies."""
        gate_match = re.search(
            r'^TOOL_COUNT=\$\(echo "\$TOOLS_JSON".*?'
            r'^echo "tools/list returned \$TOOL_COUNT tool\(s\)"$',
            self.fixture,
            re.DOTALL | re.MULTILINE,
        )
        self.assertIsNotNone(gate_match, "Executable tools/list gate not found")

        invalid_payloads = {
            "malformed syntax": '{"jsonrpc":"2.0","result":',
            "missing result.tools": '{"jsonrpc":"2.0","result":{}}',
            "JSON-RPC error": (
                '{"jsonrpc":"2.0","error":{"code":-32603,"message":"failure"},"id":2}'
            ),
            "null tools": '{"jsonrpc":"2.0","result":{"tools":null},"id":2}',
            "string tools": '{"jsonrpc":"2.0","result":{"tools":"echo"},"id":2}',
            "object tools": (
                '{"jsonrpc":"2.0","result":{"tools":{"name":"echo"}},"id":2}'
            ),
            "empty tools array": '{"jsonrpc":"2.0","result":{"tools":[]},"id":2}',
        }
        valid_payload = (
            '{"jsonrpc":"2.0","result":{"tools":[{"name":"echo"}]},"id":2}'
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            marker = pathlib.Path(temp_dir) / "smoke-result"
            gate = gate_match.group(0).replace(
                "/tmp/foundry-mcp-aca-smoke-result", str(marker)
            )

            for name, payload in invalid_payloads.items():
                with self.subTest(payload=name):
                    result = subprocess.run(
                        ["bash", "-c", gate],
                        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "TOOLS_JSON": payload},
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertNotEqual(
                        result.returncode,
                        0,
                        f"{name} incorrectly passed the shipped tools/list gate: "
                        f"stdout={result.stdout!r} stderr={result.stderr!r}",
                    )

            result = subprocess.run(
                ["bash", "-c", gate],
                env={"PATH": "/usr/bin:/bin:/usr/local/bin", "TOOLS_JSON": valid_payload},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                "valid JSON-RPC tools/list response failed the shipped gate: "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()

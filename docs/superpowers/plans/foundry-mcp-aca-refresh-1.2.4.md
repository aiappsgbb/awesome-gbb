# Plan: foundry-mcp-aca refresh 1.2.4

**Design:** [specs/foundry-mcp-aca-refresh-1.2.4.md](../specs/foundry-mcp-aca-refresh-1.2.4.md)
**Status:** Complete (correction round 2 applied)

## Corrections applied (TDD — RED before GREEN)

### RED (7 failures on head `44cebd32`):
- `test_no_probe_port_mismatch_with_placeholder`: FAIL — probes on port 8080 with placeholder serving port 80
- `test_session_header_uses_bash_array`: FAIL — scalar SESSION_HEADER with embedded quotes
- `test_tools_call_uses_named_tool_not_first_fallback`: FAIL — FIRST_TOOL dynamic fallback
- `test_tools_call_asserts_no_error`: FAIL — no isError check
- `test_intro_mentions_tools_call`: FAIL — intro omits tools/call
- `test_hard_gates_list_includes_tools_call`: FAIL — hard gates omit tools/call
- `test_spec_has_correct_year`: FAIL — spec uses 2025 instead of 2026

### GREEN (corrections implemented):
1. Removed probes from fixture Bicep — eliminates port mismatch
2. Replaced scalar SESSION_HEADER with Bash array SESSION_ARGS
3. Added notifications/initialized HTTP status capture + assertion (no || true)
4. Replaced search_orders_filtered fallback with named `echo` call + exact `"echoed: ci-probe"` assertion + isError check
5. Updated intro + hard gates to include tools/call
6. Fixed spec date to 2026-08-05
7. Updated spec success criteria with precise protocol gates

## Steps

1. **Pin script validation** — explicit `mcp~=1.29.0` install, importlib.metadata version assertion, JobsOperations method assertions
2. **KI-001 expansion** — coordinated fastmcp 3.x + mcp 2.0 migration hold
3. **SKILL.md agnostic rewrites** — remove engagement-specific phrases
4. **SemVer** — 1.2.3 → 1.2.4 (PATCH per AGENTS.md §5)
5. **Fixture: azd up** — single-command deployment with placeholder lifecycle
6. **Fixture: port lifecycle** — probes removed to avoid placeholder/port conflict
7. **Fixture: MCP session conformance** — Bash array for session-id, status-gated notifications/initialized
8. **Fixture: named tools/call** — `echo` with `ci-probe`, assert exact `"echoed: ci-probe"` + isError!=true
9. **Local validation** — contract tests GREEN, validate-skills.py, build-plugins.py --check, pin validation, build-site.py
10. **Push + CI** — exact-head copilot-cli-matrix green

## Files changed

- `skills/foundry-mcp-aca/SKILL.md` — version bump + agnostic rewrites
- `skills/foundry-mcp-aca/references/upstream-pin.md` — pin script + KI-001 expansion
- `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` — azd up + session array + named tools/call
- `scripts/tests/test_foundry_mcp_aca_fixture_contract.py` — contract tests (14 assertions)
- `docs/superpowers/specs/foundry-mcp-aca-refresh-1.2.4.md` — design spec
- `docs/superpowers/plans/foundry-mcp-aca-refresh-1.2.4.md` — this plan
- `docs/` — rebuilt static site

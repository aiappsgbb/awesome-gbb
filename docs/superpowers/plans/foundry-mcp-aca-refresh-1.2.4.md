# Plan: foundry-mcp-aca refresh 1.2.4

**Design:** [specs/foundry-mcp-aca-refresh-1.2.4.md](../specs/foundry-mcp-aca-refresh-1.2.4.md)
**Status:** Correction round 3 applied

## Correction rounds

### Round 1 (head `5b406557` → `44cebd32`):
SemVer 1.2.4, agnostic rewrites, pin script, fixture rewrite.
Rejected: agent improvised ACR seeding + direct deploy recovery.

### Round 2 (head `44cebd32` → `dc884459`):
14 contract tests, SESSION_ARGS array, status-gated initialized, named echo.
Rejected: agent patched azd env files, imported MCR placeholder, edited Bicep.

### Round 3 (head `34b91a23` → current):
Registry fix (explicit `param acrServer`), KI-001 factual correction.
Then: 12 new contract tests, unique per-run service identity, MCP 2025-06-18
protocol conformance (202 for initialized, protocolVersion capture,
MCP-Protocol-Version header), session ID FAIL gate, synchronized gates.

### RED (10 failures on head `34b91a23`):
- `test_service_tag_uses_app_name_variable`: FAIL — static 'mcp' tag
- `test_azure_yaml_service_key_matches_bicep_tag`: FAIL — static service key
- `test_protocol_version_captured_from_initialize`: FAIL — no protocolVersion capture
- `test_protocol_version_header_on_subsequent_requests`: FAIL — no MCP-Protocol-Version header
- `test_session_id_empty_is_fail`: FAIL — no FAIL gate on empty session ID
- `test_initialized_requires_http_202`: FAIL — checked 2xx range, not 202
- `test_failure_list_includes_session_id`: FAIL — no session ID in failure list
- `test_failure_list_includes_tools_call`: FAIL — no tools/call in failure list
- `test_failure_list_includes_initialized_status`: FAIL — no initialized status in failure list
- `test_no_stale_probe_prose`: FAIL — stale probe reference remained

### GREEN (28/28 after corrections):
1. Bicep `azd-service-name` → `appName` param (per-run unique)
2. azure.yaml via heredoc with `${APP_NAME}` service key
3. `protocolVersion` captured from initialize `.result.protocolVersion`
4. `MCP-Protocol-Version` header added to SESSION_ARGS
5. Empty session ID → immediate FAIL
6. `notifications/initialized` requires exactly HTTP 202
7. Failure list updated with session ID, 202, tools/call
8. Stale probe prose removed

## Files changed

- `skills/foundry-mcp-aca/SKILL.md` — version bump + agnostic rewrites
- `skills/foundry-mcp-aca/references/upstream-pin.md` — pin script + KI-001
- `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` — full protocol conformance
- `scripts/tests/test_foundry_mcp_aca_fixture_contract.py` — 28 contract tests
- `docs/superpowers/specs/foundry-mcp-aca-refresh-1.2.4.md` — design spec
- `docs/superpowers/plans/foundry-mcp-aca-refresh-1.2.4.md` — this plan
- `docs/` — rebuilt static site

## Round-4: State persistence (2026-08-05)

### RED (pre-fix)
Run 30996359268 transcript showed agent fixing azure.yaml placeholders
(unresolved `${APP_NAME}`) and manually adding AZURE_TENANT_ID. Root cause:
Copilot CLI Bash tool process isolation — env vars don't persist.

### Fix
- STATE_FILE (`/tmp/foundry-mcp-aca-state.env`) written after naming
- `source` at top of azure.yaml, azd up, and MCP probe blocks
- `azd env set AZURE_TENANT_ID "$AZURE_TENANT_ID"` added to Step 4
- 6 contract tests added (TestStatePersistence class)

### GREEN
- 34/34 tests pass
- validate-skills.py ✅
- build-plugins.py --check ✅
- T3 run 30998053808 GREEN — zero improvisation, full MCP roundtrip

## Round-6: MCP protocol conformance (2026-08-05)

### Genuine RED (pre-fix)
- `test_initialized_asserts_empty_body_or_no_body` — FAILED (fixture checks HTTP 202 but not body emptiness)
- `test_failure_list_includes_protocol_version` — FAILED (failure list omits protocol version)

### Corrections applied
1. SKILL.md: requests→200, notifications→202 (3 locations)
2. Fixture initialized: capture body, assert empty
3. Fixture failure list: add protocol version and non-empty body entries
4. Test fix: `test_initialized_asserts_empty_body_or_no_body` search from `"method": "notifications/initialized"` not first prose mention

### GREEN
All 47 tests pass.

## Round-7 corrections (2026-08-05)

### RED (5 failures on 6f7c7dc0)
- `test_parameters_json_uses_quoted_heredoc` — no `<<'` heredoc found
- `test_protocol_version_fails_if_empty` — no FAIL gate on empty version
- `test_protocol_version_header_unconditional` — found `[ -n "$PROTOCOL_VERSION" ] &&`
- `test_mcp_exchange_state_persisted_to_file` — FQDN/SESSION_ID/PROTOCOL_VERSION not in STATE_FILE writes
- `test_skill_consumer_config_no_trailing_slash` — found `/mcp/` in consumer config

### Corrections applied
1. main.parameters.json: `<<'PARAMS'` quoted heredoc (preserves `$schema`)
2. PROTOCOL_VERSION empty → FAIL marker immediately
3. MCP-Protocol-Version header unconditional (removed conditional)
4. STATE_FILE persists FQDN, SESSION_ID, PROTOCOL_VERSION
5. tools/list and tools/call source STATE_FILE and rebuild SESSION_ARGS
6. SKILL.md L719: `/mcp/` → `/mcp`

### GREEN
All 54 tests pass.

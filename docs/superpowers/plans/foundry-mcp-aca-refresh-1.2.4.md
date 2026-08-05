# Plan: foundry-mcp-aca refresh 1.2.4

**Design:** [specs/foundry-mcp-aca-refresh-1.2.4.md](../specs/foundry-mcp-aca-refresh-1.2.4.md)
**Status:** Correction round 10 applied

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
- `scripts/tests/test_foundry_mcp_aca_fixture_contract.py` — 59 contract tests
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
- 57 fixture + 377 full suite pass
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
All 57 fixture tests pass, 377 full suite.

## Round-8 corrections (2026-08-05)

### Genuine RED on `58a3cd66`

The new behavioral test extracts and executes the fixture's shipped
`TOOL_COUNT` Bash gate rather than matching jq syntax. Its required payload
matrix produced 2 failing subtests:

- `string tools` — incorrectly returned success with count `4`
- `object tools` — incorrectly returned success with count `1`

Malformed syntax, missing `.result.tools`, JSON-RPC error, null tools, and an
empty tools array already returned failure. A JSON-RPC 2.0 success response
with a non-empty tools array returned success.

### Minimal correction

The jq predicate now accepts only a response where:

1. `.jsonrpc == "2.0"`
2. `.error == null`
3. `.result.tools` has type `array`
4. `.result.tools | length >= 1`

Failure at parsing, schema validation, or count validation writes
`SMOKE_RESULT=FAIL` and exits before the fixture can invoke `tools/call`.

### GREEN

- Targeted semantic contract: 1 test, 8 payload cases, PASS
- Fixture contracts: 58 tests, PASS
- Full catalog suite: 378 tests, PASS

## Round-9 corrections (2026-08-05)

### T3 rejection and genuine RED

Exact-head run `31009977441` / job `92319391511` passed CI but is not valid
final evidence. Artifact `8932166611` shows the agent first wrote the
prescribed quoted parameter heredoc, then announced “Fixing the parameter-file
write” and rewrote it. The quoted heredoc had preserved all deployment
placeholders literally.

An execution-level regression test extracted the shipped heredoc and rendered
it with known environment values. On head `6853b61e` it failed:

```text
AssertionError: '${APP_NAME}' != 'ci-smoke-mcp-test1234'
```

### Minimal correction

1. Change `<<'PARAMS'` to expanding `<<PARAMS`.
2. Escape only the schema key as `"\$schema"`.
3. Keep `${APP_NAME}`, `${UAMI_RESOURCE_ID}`, and `${ACR_SERVER}` expandable.
4. Replace the obsolete quoted-heredoc substring test with a structural escape
   test; retain the new execution-level JSON rendering test.

### GREEN

- Coupled heredoc + semantic gate contracts: 3 tests, PASS
- Fixture contracts: 59 tests, PASS
- Full catalog suite: 379 tests, PASS

## Round-10 corrections (2026-08-05)

### Genuine RED on `8b27ec6a`

The round-9 heredoc test injected `UAMI_RESOURCE_ID` and `ACR_SERVER`
directly, even though literal fixture execution starts Step 3 in a fresh shell
with only Step 1 state. The revised test now:

1. extracts and executes the Step 1 naming and state blocks with only
   `GITHUB_WORKSPACE`, `AZURE_SUBSCRIPTION_ID`, and `ACR_LOGIN_SERVER`;
2. starts a fresh Bash process;
3. executes the extracted Step 3 parameters block, which sources that state;
4. parses and validates the rendered JSON.

RED failed with:

```text
AssertionError: None != '/subscriptions/test-subscription/.../uami-awesome-gbb-ci'
```

### Minimal correction

1. Derive `UAMI_RESOURCE_ID` and `ACR_SERVER` in Step 1 from workflow env.
2. Persist them beside `APP_NAME` and `PROJECT_DIR`.
3. Document the complete four-value state contract.
4. Reuse the sourced pair in Step 4's `.azure/.env` instead of deriving them
   in that later process.
5. Correct the spec rationale: MCP `<2` is held for a future MCP 2.0 protocol
   break, not because MCP 1.x is incompatible with FastMCP 2.x.

### GREEN

- Fresh-shell state + parameter replay and semantic gate contracts: 3 tests,
  PASS
- Fixture contracts: 59 tests, PASS
- Full catalog suite: 379 tests, PASS

## Round-11 corrections (2026-08-05)

### T3 rejection and genuine RED

Exact-head run `31011829922` / job `92325758381` passed CI but is not valid
final evidence. Artifact `8932995008` shows the agent combined the separate
naming and state instructions and added an unprescribed
`PROJECT_DIR="${GITHUB_WORKSPACE}/.scratch/${APP_NAME}"` assignment. Literal
fresh-shell execution of the state fence therefore remained unproven.

The behavioral test stopped concatenating the naming and state fences and
executed the exact state fence with only workflow environment variables. On
head `8d537c06`, it failed:

```text
Regex didn't match: '^ci-smoke-mcp-[0-9a-f]{8}$' not found in ''
```

### Minimal correction

1. Generate `SUFFIX` and `APP_NAME` inside the state-persistence fence.
2. Persist all four cross-shell values in that same invocation.
3. Explicitly forbid running naming as a separate Bash tool invocation.
4. Keep Step 3 as a separate fresh process that sources only persisted state.

### GREEN

- Exact Step 1 state + fresh-shell Step 3 replay: PASS
- Fixture contract count remains 59 tests

## Round-12 corrections (2026-08-05)

### T3 rejection and genuine RED

Exact-head run `31013776210` / job `92332489833` passed CI but is not valid
final evidence. Artifact `8933777390` line 35 followed the shipped scaffolding
block and reassigned
`PROJECT_DIR="${GITHUB_WORKSPACE}/.scratch/${APP_NAME}"` immediately after
sourcing Step 1 state. That bypassed proof that the persisted `PROJECT_DIR`
controlled the fresh-shell scaffold.

The focused contract extracts the shipped Step 1 and scaffolding blocks. It
also forbids assignments to `APP_NAME`, `PROJECT_DIR`, `UAMI_RESOURCE_ID`, or
`ACR_SERVER` after the scaffold sources state. On head `9b56147c`, it failed:

```text
the scaffolding block must not reassign persisted variables after sourcing
Step 1 state; found ['PROJECT_DIR']
```

### Minimal correction

Remove only the redundant `PROJECT_DIR` assignment. Preserve the state source,
`mkdir`, and `cd "$PROJECT_DIR"`.

### GREEN

- Exact Step 1 + fresh-shell scaffolding replay: PASS
- Fixture contracts: 60 tests, PASS
- Full catalog suite: 380 tests, PASS

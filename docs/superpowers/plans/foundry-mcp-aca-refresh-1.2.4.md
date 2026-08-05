# Plan: foundry-mcp-aca refresh 1.2.4

**Design:** [specs/foundry-mcp-aca-refresh-1.2.4.md](../specs/foundry-mcp-aca-refresh-1.2.4.md)
**Status:** Round 14 implemented; exact-head T3 pending

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

## Round-13 corrections (2026-08-05)

### Architectural threshold and T3 rejection

After rounds 9–12, another narrow prose/state patch is rejected. The root
cause is tool-choice ambiguity, not another missing state sentence.

Exact-head run `31015993206` / job `92340108760`, head
`7f49057998777e4eee917f482cdf05e74a073d21`, artifact `8934773029`, transcript
SHA-256
`baf01d79ab3fd0b9696c5980b9c7dfb21aeeb57453717d3f95839f1fbf966e13`
was green but is false-green and explicitly rejected. Transcript lines 15–21
show one Edit/Create action authored all six files; lines 33–34 and 42–43 show
two Edit repairs to `main.parameters.json`.

### Architectural correction

The old Step 2/3 supplied bare content fences plus prose “write this file,”
allowing stochastic Edit/Create versus Bash heredocs. Replace them with:

1. a first-page mandatory guard forbidding Edit/Create/Write and generated-file
   inspection or repair; and
2. one exact executable Bash scaffold block, with no second write path, that
   sources Step 1 state, fail-marks source, missing-state, `mkdir`, and `cat`
   failures, creates directories, and writes exactly six files with quoted
   static and unquoted dynamic heredocs.

The scaffold performs no Azure or external calls. Step 4+ deployment,
protocol, marker, and cleanup remain unchanged.

### Execution-level contract

Extract the exact Step 1 state block and exact combined scaffold block and run
them in separate fresh shells with only workflow environment. Validate all six
exact file contracts, literal `$schema`, exact expanded persisted values,
parsed `azure.yaml` app/service key, no reassignment, alternate path, or
external calls, and failure boundaries for the missing state file, each
missing persisted value, `mkdir`, and first `cat`.

### RED and GREEN

- Architectural RED on parent `7f490579`: 3 failed, 60 passed, 29 subtests
  (missing block/guard).
- Fail-fast RED: 4 failures, 60 passed (masked early error, missing marker,
  stale guard).
- Missing-state gate RED: 5 failing cases (allowlist plus `APP_NAME`,
  `PROJECT_DIR`, `UAMI_RESOURCE_ID`, and `ACR_SERVER`).
- Final GREEN: 67 passed, 46 subtests.

### Acceptance pending

No live-Azure acceptance claim exists yet. Exact-head T3 must still prove no
Edit/Create/Write, one state Bash (the Step 1 state-writing invocation), one
combined scaffold Bash sourced from state, no repair or inspection, one `azd`
path, one MCP roundtrip, deterministic marker, and audit echo only (the
required `SKILL.md` audit-path echo, with no catalog reads beyond it).

## Round-14 corrections (2026-08-05)

### Exact-head rejection and root cause

Run `31026453627`, job `92376101138`, head
`d250c8feb0f8721c10a2f7513fe5164361eaca1d`, artifact `8939043595`,
transcript SHA-256
`4c73d6a94805fb40e443932bfd558b351147d64c712aa83725c373df1fd085b9`
is explicitly rejected. The transcript shows:

1. lines 1–2: Edit/Create writes a session `plan.md`;
2. lines 6–12: audit and state run without Step 0 auth;
3. lines 26–32: the first provision path runs unauthenticated; and
4. lines 34–42: auth is repaired and provision is rerun.

The Step 2 deterministic scaffold correction worked, but the fixture still
encoded audit, auth, and state as independent prose fragments. State could
therefore exist without successful auth, and the scaffold/provision dependency
could not enforce ordering. The file-tool guard covered only scaffold files,
not session planning.

### Architectural correction

1. Replace Step -1, the separate Step 0 command fragments, and the Step 1
   state fragment with one exact first-action bootstrap Bash block.
2. The block performs audit echo, required-env validation, optional-auth
   inventory, show-don't-assert `az account show`, and the sole
   `azd auth login`.
3. Remove stale state before validation; on failure write deterministic FAIL
   and leave no state; after auth, write a temporary four-line state file and
   atomically publish it with `mv`.
4. Keep the exact six-file Step 2 scaffold block unchanged. Its state source
   is now an executable dependency on successful bootstrap auth.
5. Keep provision separate but make it one exact block that sources the
   authenticated bootstrap state before creating the azd env or running
   `azd up`.
6. Apply the file-tool prohibition globally: no Edit/Create/Write or other
   file-editing tools for any purpose, no session-state `plan.md`, and only
   prescribed Bash actions.

### RED and GREEN

- RED on `d250c8`: 4 new tests, 7 assertion failures (missing bootstrap and
  four missing global guard sentences).
- GREEN: 73 fixture contract tests.
- Execution proof: stubbed `az`/`azd` call log verifies audit and auth order;
  auth failure leaves no state and writes FAIL; every required-env omission
  fails before Azure calls; successful auth publishes exact state.
- Fresh-shell scaffold proof: exact bootstrap followed by the unchanged exact
  scaffold creates and validates all six files.
- Provision structure proof: exactly one prescribed provision fence contains
  the sole executable `azd up` and begins by requiring bootstrap state. The
  scanner covers alternate fences, compound/subshell/continued and
  path-qualified commands, while ignoring actual heredoc bodies.
- Review RED: 3 focused tests produced 6 failures. Compound duplicate auth and
  provision commands counted as one path, and four fresh MCP/Easy Auth Bash
  blocks consumed persisted state without sourcing it.
- Review GREEN: all four blocks source state first and every matching command
  occurrence counts toward the single-path invariant.
- Full `scripts/tests`: 393 tests.

### Acceptance pending

Exact-head T3 must prove zero Edit/Create/Write actions; exact bootstrap first;
one unchanged scaffold Bash action; one authenticated provision path after
bootstrap; one MCP roundtrip; no repair or generated-file/catalog inspection
beyond the audit echo; and deterministic marker output.

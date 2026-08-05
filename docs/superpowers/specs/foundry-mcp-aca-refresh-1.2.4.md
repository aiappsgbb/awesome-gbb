# Design Spec: foundry-mcp-aca refresh 1.2.4

**Status:** Implemented (correction-phase artifact)
**Date:** 2026-08-05
**Base version:** 1.2.3
**Target version:** 1.2.4 (PATCH — pin refresh + wording + deployment corrections)

## Scope

PATCH refresh of `foundry-mcp-aca` covering:

1. Pin bumps: azure-mgmt-appcontainers 4.0→5.0 (MAJOR, API preserved),
   azure-cosmos 4.15→4.16.3, aiohttp 3.13.5→3.14.3, explicit mcp 1.29.0 pin
2. Agnostic prose rewrites (remove engagement-specific phrases per AGENTS.md §2.1)
3. Deployment model coherence: fixture aligned to `azd up` with unique per-run
   service identity (`$APP_NAME` as both Bicep `azd-service-name` tag and
   azure.yaml service key)
4. MCP 2025-06-18 protocol conformance: session-id required (FAIL on empty),
   `protocolVersion` captured, `MCP-Protocol-Version` header on subsequent
   requests, `notifications/initialized` requires HTTP 202, named `echo`
   tools/call with exact payload assertion
5. KI-001: independent FastMCP <3 (mount/server API) and MCP <2 (protocol) holds

## Compatibility matrix

| Package | Previous | Current | Hold | Rationale |
|---------|----------|---------|------|-----------|
| fastmcp | 2.14.7 | 2.14.7 | <3.0 | KI-001 — mount-path break |
| mcp | (transitive) | 1.29.0 | <2.0 | KI-001 — incompatible with fastmcp 2.x |
| azure-mgmt-appcontainers | 4.0.0 | 5.0.0 | — | MAJOR but JobsOperations.get/begin_create_or_update preserved |
| azure-cosmos | 4.15.0 | 4.16.3 | — | MINOR; async query_items signature unchanged |
| azure-identity | 1.25.3 | 1.25.3 | — | unchanged |
| azure-keyvault-secrets | 4.11.0 | 4.11.0 | — | unchanged |
| aiohttp | 3.13.5 | 3.14.3 | — | MINOR |

## SSOT boundaries

- SKILL.md links to `references/` code; does not duplicate
- `pilotPosture` Bicep param name is canonical from azd-patterns — NOT renamed
- Generic archetype tool names (get_customer_profile, search_orders_filtered) preserved
- Reference data files unchanged

## Deployment model

`azd up` is the single documented deployment path (AGENTS.md §2.6):
- Bicep uses placeholder image; `azd deploy` swaps via `azd-service-name` tag
- `azure.yaml` service binding handles image build + push
- Probes are omitted during first provision to avoid port mismatch with the
  placeholder image (serves port 80 vs real server port 8080). Production
  deployments add probes after the first successful `azd deploy`.

## Live Azure success criteria (T3)

- `azd up` completes successfully against `rg-awesome-gbb-ci`
- MCP `initialize` returns 200 with `serverInfo.name` and `protocolVersion`
- `Mcp-Session-Id` header captured; FAIL if empty (required by MCP spec)
- `MCP-Protocol-Version` header sent on all subsequent HTTP requests
- `notifications/initialized` returns HTTP 202 exactly (MCP 2025-06-18)
- `tools/list` returns ≥1 tool
- `tools/call` on `echo` with `"ci-probe"` returns exact `"echoed: ci-probe"` payload
- `isError` is not `true` on the tools/call response
- Deterministic marker file written (Pattern 12)
- `azd-service-name` tag and azure.yaml service key both use `$APP_NAME`
  (per-run unique, avoiding shared-RG collision)

## Round-4 correction (2026-08-05): Bash tool process isolation

**Root cause:** Copilot CLI runs each Bash tool invocation in a FRESH
process. Environment variables set in one call (e.g. `APP_NAME`) are lost
in subsequent calls. The fixture's azure.yaml heredoc and azd up blocks
referenced `${APP_NAME}` in a shell where it was unset.

**Fix:** Write `/tmp/foundry-mcp-aca-state.env` after Step 1 naming and
`source` it at the top of every subsequent bash block (azure.yaml, azd up,
MCP probe). Additionally added `azd env set AZURE_TENANT_ID` which was
missing for OIDC-based azd auth.

**Evidence:** Run 30998053808 / job 92279922520 — agent sources state file
at line 172 (`source /tmp/foundry-mcp-aca-state.env`), `azd up` succeeds
without intervention, full MCP roundtrip passes. Zero improvisation signals
in transcript grep.

## Round-5 correction (2026-08-05): azd env headless CI fix

**Root cause:** `azd env new` / `azd env set` trigger interactive prompts
that block the CLI with "Permission denied". Fixed by writing `.azure/`
config and env files directly instead of using `azd env` commands.

**Evidence:** Run 30999760430 — clean T3, zero improvisation.

## Round-6 correction (2026-08-05): MCP protocol conformance in SKILL/fixture

**Changes:**
1. SKILL.md L70: "All JSON-RPC requests must return HTTP 200; notifications
   must return HTTP 202" (was "ALL 6 … HTTP 200")
2. SKILL.md L76: initialized → "HTTP 202 Accepted (no body)" (was "Can return `{}`")
3. SKILL.md L747 gotchas: same request/notification distinction
4. Fixture: initialized now captures body and asserts empty (per MCP 2025-06-18)
5. Fixture failure list: added protocol version negotiation and non-empty
   initialized body as FAIL conditions

**TDD evidence:**
- RED (2 failures): `test_initialized_asserts_empty_body_or_no_body`,
  `test_failure_list_includes_protocol_version` — ran before fixture fix
- GREEN: all 47 tests pass after minimal source corrections

## Round-7 correction (2026-08-05): state persistence, protocol gates, SKILL trailing slash

**Root cause:** Coordinator rejected head 6f7c7dc0 citing 5 genuine remaining gaps
from run 30999760430 (head 6ceda5bc, one prior commit):
1. `$schema` in main.parameters.json expanded under unquoted heredoc
2. PROTOCOL_VERSION gate was optional (`[ -n ... ] &&` conditional)
3. MCP state (FQDN/SESSION_ID/PROTOCOL_VERSION) not persisted across bash fences
4. SKILL.md L719 consumer config used `/mcp/` (trailing slash → 307 under FastMCP 2.x)
5. Scoped initialized tests needed to anchor on enforcement block, not intro prose

**Fixes:**
1. Parameters.json creation uses `<<'PARAMS'` quoted heredoc (preserves `$schema` literal)
2. Empty PROTOCOL_VERSION now writes FAIL marker immediately; header is unconditional
3. STATE_FILE persists FQDN + SESSION_ID + PROTOCOL_VERSION; tools/list and tools/call
   source it and rebuild SESSION_ARGS from persisted values
4. SKILL.md consumer config example corrected to `/mcp` (no trailing slash)
5. Two scoped tests anchored on `'"method": "notifications/initialized"'` (already correct at 6f7c7dc0)

**TDD evidence:**
- RED: 5 of 7 new tests failed at round-6 head (2 scoped tests already passed)
- GREEN: all 57 tests pass after fixes

## Round-8 correction (2026-08-05): semantic `tools/list` schema gate

**Root cause:** The fixture used
`jq -e -r '.result.tools | length // 0'`. Although malformed JSON and
zero-length values failed later, jq's `length` also accepts strings and
objects. A non-empty string or object therefore produced a positive count and
incorrectly allowed the smoke to continue to `tools/call`. The existing test
only searched for the substring `jq -e`, so it did not execute or prove the
shipped gate's semantics.

**Fix:** The jq predicate now requires JSON-RPC `"2.0"`, no JSON-RPC error,
an array-valued `.result.tools`, and at least one array entry. Any parse,
schema, or count failure writes the deterministic FAIL marker and exits before
`tools/call`.

**TDD evidence:**
- RED on head `58a3cd66`: the execution-level contract test extracted and ran
  the shipped Bash gate; `string tools` and `object tools` incorrectly passed
  (2 failing subtests). Malformed syntax, missing tools, JSON-RPC error, null,
  and an empty array already failed.
- GREEN: the same payload matrix passes after the minimal predicate change:
  all 7 invalid payloads fail the gate and a JSON-RPC 2.0 response containing
  a non-empty tools array passes.
- Current counts: 58 fixture contract tests; 378 full catalog tests.

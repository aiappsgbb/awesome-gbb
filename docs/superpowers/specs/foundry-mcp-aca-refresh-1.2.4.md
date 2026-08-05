# Design Spec: foundry-mcp-aca refresh 1.2.4

**Status:** Round 16 implemented; exact-head T3 pending
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
| mcp | (transitive) | 1.29.0 | <2.0 | KI-001 — future MCP 2.0 protocol break |
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
- Round-8 counts: 58 fixture contract tests; 378 full catalog tests.

## Round-9 correction (2026-08-05): parameter heredoc must render values

**Root cause:** Round 7 changed `main.parameters.json` to a quoted heredoc to
preserve `$schema`, but quoted heredocs also preserve `${APP_NAME}`,
`${UAMI_RESOURCE_ID}`, and `${ACR_SERVER}`. The first round-8 T3 run exposed
the defect: the agent wrote the prescribed literal placeholders, then repaired
the parameter file in a second shell call. The green marker therefore did not
qualify as literal prescribed execution.

**Fix:** Use an expanding heredoc and escape only `\$schema`. A behavioral
test extracts and executes the shipped heredoc, parses the rendered JSON, and
asserts both the literal `$schema` key and all three expanded deployment
values.

**TDD and T3 evidence:**
- RED on head `6853b61e`: the rendered `appName` was literal
  `"${APP_NAME}"` instead of `"ci-smoke-mcp-test1234"`.
- GREEN: the behavioral heredoc test, structural escape test, and semantic
  `tools/list` matrix all pass.
- Run `31009977441`, job `92319391511`, artifact `8932166611` is explicitly
  rejected as final T3 evidence because transcript lines 44-52 show the
  parameter-file repair.
- Current local counts after correction: 59 fixture contract tests; 379 full
  catalog tests.

## Round-10 correction (2026-08-05): persist Step-3 deployment values

**Root cause:** Step 3 sources the Step 1 state file before expanding
`UAMI_RESOURCE_ID` and `ACR_SERVER`, but Step 1 persisted only `APP_NAME` and
`PROJECT_DIR`. Those two values were first defined in Step 4's `.azure/.env`,
which runs in a later fresh Bash process. The round-9 behavioral test masked
the defect by injecting both missing values directly into its subprocess
environment.

**Fix:** Step 1 now derives `UAMI_RESOURCE_ID` from
`AZURE_SUBSCRIPTION_ID`, copies `ACR_SERVER` from `ACR_LOGIN_SERVER`, and
persists both beside `APP_NAME` and `PROJECT_DIR`. Step 4 reuses the sourced
values rather than deriving them again.

**TDD evidence:**
- RED on head `8b27ec6a`: the revised test executed extracted Step 1 state
  creation using only workflow inputs, sourced that state in a fresh shell,
  then ran the extracted Step 3 parameters block. The state assertion failed
  with `None` for `UAMI_RESOURCE_ID`.
- GREEN: Step 1 persists all four values; the same fresh-shell replay renders
  the literal `$schema` key plus non-empty, expected app, identity, and ACR
  values.
- Counts remain 59 fixture contract tests and 379 full catalog tests because
  this correction strengthens the existing behavioral test.

## Round-11 correction (2026-08-05): naming and persistence must share one process

**Root cause:** The naming and state-persistence instructions were separate
Bash fences even though the fixture states every Bash tool call starts a fresh
process. The round-10 test masked this by concatenating both fences. Literal
execution of the state fence persisted an empty `APP_NAME`, and exact-head T3
run `31011829922` compensated by adding a `PROJECT_DIR` assignment while
combining the instructions.

**Fix:** The state-persistence fence now generates `SUFFIX` and `APP_NAME`
before deriving and persisting all four cross-shell values. Naming prose
explicitly forbids a separate Bash invocation. The behavioral test executes
that exact fence alone with only workflow inputs, then executes Step 3 in a
new Bash process.

**TDD evidence:**
- RED on head `8d537c06`: exact state-fence replay persisted an empty app name
  (`'^ci-smoke-mcp-[0-9a-f]{8}$' not found in ''`).
- GREEN: the exact state fence persists a non-empty unique app name, and the
  fresh Step 3 process renders literal `$schema`, the same app name, the exact
  UAMI resource ID, and the exact ACR server.
- Counts remain 59 fixture contract tests and 379 full catalog tests.

## Round-12 correction (2026-08-05): scaffolding must trust restored state

**Root cause:** The scaffolding block sourced Step 1 state and then reassigned
`PROJECT_DIR` from `GITHUB_WORKSPACE` and `APP_NAME`. Although the recomputed
value matched the persisted value, that prescribed reassignment bypassed proof
that the fresh shell actually restored and used `PROJECT_DIR`.

**Fix:** Remove only the redundant `PROJECT_DIR` assignment. The block still
sources `/tmp/foundry-mcp-aca-state.env`, creates `src/` and `infra/` beneath
the restored directory, and changes into it.

**TDD evidence:**
- RED on head `9b56147c`: the new extracted-block contract found
  `['PROJECT_DIR']` assigned after the state source.
- GREEN: the contract executes the exact Step 1 block, replaces the persisted
  `PROJECT_DIR` with a distinct test path, then runs the exact scaffolding block
  in a fresh shell and observes both directories under that restored path.
- Counts are 60 fixture contract tests and 380 full catalog tests.

## Round-13 correction (2026-08-05): deterministic scaffold execution

**Architectural threshold:** After rounds 9–12, another narrow prose/state
patch is rejected. The root cause is tool-choice ambiguity, not another missing
state sentence.

**Rejected exact-head T3:** Run `31015993206`, job `92340108760`, head
`7f49057998777e4eee917f482cdf05e74a073d21`, artifact `8934773029`, transcript
SHA-256
`baf01d79ab3fd0b9696c5980b9c7dfb21aeeb57453717d3f95839f1fbf966e13`.
Transcript lines 15–21 show one Edit/Create action authored all six files;
lines 33–34 and 42–43 show two Edit repairs to `main.parameters.json`. The
run/job was green but is false-green and explicitly rejected.

**Design:** Replace the old Step 2/3 bare content fences and prose “write this
file,” which allowed stochastic Edit/Create versus Bash heredocs, with a
first-page mandatory guard and one exact executable Bash scaffold block. The
block sources Step 1 state; fail-marks source, missing-state, `mkdir`, and `cat`
failures; creates directories; and writes exactly six files using quoted
static and unquoted dynamic heredocs. It performs no Azure or external calls,
forbids Edit/Create/Write and generated-file inspection or repair, and exposes
no second write path. Step 4+ deployment, protocol, marker, and cleanup remain
unchanged.

**Execution-level contract:** Extract the exact Step 1 state block and exact
combined scaffold block, then execute them in separate fresh shells with only
workflow environment. Validate all six exact file contracts, literal
`$schema`, exact expanded persisted values, the parsed `azure.yaml`
app/service key, no reassignment, alternate path, or external calls, and
failure boundaries for a missing state file, each missing persisted value,
`mkdir`, and the first `cat`.

**TDD evidence:**
- Architectural RED on parent `7f490579`: 3 failed, 60 passed, 29 subtests
  (missing block/guard).
- Fail-fast RED: 4 failures, 60 passed (masked early error, missing marker,
  stale guard).
- Missing-state gate RED: 5 failing cases (allowlist plus `APP_NAME`,
  `PROJECT_DIR`, `UAMI_RESOURCE_ID`, and `ACR_SERVER`).
- Final GREEN: 67 passed, 46 subtests.

**Acceptance remains open:** There is no live-Azure acceptance claim yet.
Exact-head T3 must still prove no Edit/Create/Write, one state Bash (the Step 1
state-writing invocation), one combined scaffold Bash sourced from state, no
repair or inspection, one `azd` path, one MCP roundtrip, deterministic marker,
and audit echo only (the required `SKILL.md` audit-path echo, with no catalog
reads beyond it).

## Round-14 correction (2026-08-05): auth-ordered atomic bootstrap

**Rejected exact-head T3:** Run `31026453627`, job `92376101138`, head
`d250c8feb0f8721c10a2f7513fe5164361eaca1d`, artifact `8939043595`,
transcript SHA-256
`4c73d6a94805fb40e443932bfd558b351147d64c712aa83725c373df1fd085b9`.
Transcript lines 1–2 use Edit/Create for
`~/.copilot/session-state/90ffa132-ffd8-4fbb-b149-a9c76da90f88/plan.md`.
Lines 6–12 merge audit and state while skipping Step 0 auth. Lines 26–32
then enter the provision path unauthenticated; lines 34–42 repair auth and
reprovision. The deterministic scaffold itself succeeded with one prescribed
Bash call and no generated-file repair, but the two provision paths make the
green run false evidence.

**Root cause:** Authentication, audit acknowledgement, and state publication
were three independent prose-directed fragments. The scaffold required state,
but state did not require successful authentication. The file-tool prohibition
also applied only to scaffold authoring, leaving session plan files outside its
scope. "Step 0 first" prose could not enforce either dependency.

**Architecture:** The fixture's first Bash action is now one exact bootstrap
block. It uses `set -Eeuo pipefail`, a deterministic `FAIL` helper, the audit
echo, required-env existence checks, optional-auth inventory, show-don't-assert
`az account show`, and the sole explicit `azd auth login`. It removes stale
state before validation, writes new state to a process-unique temporary file
only after login succeeds, and atomically publishes it with `mv`. The unchanged
Step 2 scaffold fails immediately if that state is absent. Provision remains
one separate prescribed Bash block whose first operation sources the
bootstrap-created state. The first-page guard now forbids Edit/Create/Write
and every other file-editing tool globally, including session-state plan files.

**TDD evidence:**
- RED on parent `d250c8`: 4 new tests produced 7 assertion failures. The
  bootstrap heading/block was absent, auth and state were split, and all four
  global file-tool/plan guard sentences were missing.
- GREEN: 73 fixture contract tests pass. Execution-level tests stub `az`,
  `azd`, and `uuidgen`, assert audit and call order, prove auth failure writes
  FAIL and leaves no state, prove all required env omissions fail before Azure
  calls, and prove successful auth publishes the exact four-line state.
- The existing fresh-shell execution contract then runs the exact unchanged
  scaffold block and validates all six generated files.
- A provision-structure oracle requires one prescribed provision fence, the
  sole executable `azd up`, and bootstrap state as its first dependency. It
  recognizes alternate shell fences, compound/subshell/continued and
  path-qualified commands, while excluding actual heredoc bodies.
- Review RED: 3 focused tests produced 6 failures: compound duplicate auth and
  provision commands were undercounted, and four fresh MCP/Easy Auth Bash
  blocks consumed persisted deployment state without sourcing it.
- Review GREEN: every state-consuming MCP/Easy Auth block now sources the state
  file first, and the oracle counts every executable command occurrence.
- Full `scripts/tests`: 393 tests pass.

**Acceptance remains open:** The next exact-head T3 must show zero
Edit/Create/Write actions, the exact bootstrap as the first action, one
unchanged scaffold Bash action, exactly one authenticated provision path, one
MCP roundtrip, no repair or generated-file/catalog inspection beyond the audit
echo, and the deterministic marker.

## Round-15 correction (2026-08-05): transcript-visible bootstrap audit

**Rejected exact-head T3:** Run `31031280923`, job `92392368732`, head
`351a44934b58f5e4ba9ba59f83ec4540f47aa571`, artifact `8940859005`,
transcript SHA-256
`ee6d6db8ccf751d349bb74c41a28de6ddba86b1212335aa61c6df84f3476bc8f`.
The 65-line transcript proves zero file-tool actions, the exact bootstrap as
the first Bash action, one unchanged scaffold call, one provision call, one
MCP roundtrip, immediate deterministic PASS, and best-effort teardown.
Nevertheless, the post-hoc audit failed because Copilot collapsed the
52-line bootstrap after displaying its first four lines; the audit echo was
inside the hidden portion and therefore absent from the transcript artifact.

**Architecture:** Keep the same single bootstrap action and dependency order,
but move the required audit echo to line 2, immediately after
`set -Eeuo pipefail`. The CLI transcript always displays this prefix before
collapsing the remainder, making the existing audit grep deterministic without
adding a second audit action or a prose-only acknowledgement.

**TDD evidence:** The strengthened bootstrap contract was RED on `351a449`
because line 2 declared `STATE_FILE`; after promoting the audit echo, the same
test and all 73 fixture contract tests are GREEN. Full `scripts/tests` remains
393 tests.

## Round-16 correction (2026-08-05): teardown restores state and exposes failure

**Rejected previously accepted T3:** Run `31031888829`, job `92394412664`,
head `4d53b5fc419c05e12502dee119d0e6276dbfd22d`, artifact `8941088170`,
transcript SHA-256
`92c1de96cab8b353e081b5503c4ca0501f6d08167e39c638fd28aa8c18539a7a`.
Transcript lines 41-47 show Step 7 beginning with `cd "$PROJECT_DIR"` without
sourcing `/tmp/foundry-mcp-aca-state.env`; line 51 reports that `azd down`
found no project in the current directory. Because every Copilot Bash action
is a fresh process, the unset variable made cleanup run from the repository
root. The pipeline also omitted `pipefail`, so `tail -20` returned zero and
suppressed the Pattern-25 NOTE when `azd down` failed.

**Focused correction:** Step 7 now sources the persisted state first, soft-NOTEs
and returns success when state or the restored project directory is unavailable,
changes to that directory, enables pipeline failure propagation, and runs the
same bounded `azd down --purge --force --no-prompt`. A nonzero or timed-out
teardown emits the existing shared-RG janitor NOTE. The previously written PASS
marker remains byte-for-byte unchanged on every cleanup path.

**Execution-level contract and TDD evidence:**

- RED on `4d53b5fc`: 6 failed, 2 passed, 72 deselected, 4 subtests passed.
  The exact extracted Step 7 block failed the structural source check, ran the
  successful stub from the fresh-shell cwd instead of the restored project, and
  emitted no NOTE for missing state, invalid cwd, nonzero `azd`, or timeout.
- GREEN: 3 targeted tests passed with 9 subtests. The success stub records the
  restored cwd and exact `down --purge --force --no-prompt` arguments; the four
  failure paths return zero, emit a NOTE, and preserve the PASS marker.
- Final local counts: 75 fixture contract tests and 395 full `scripts/tests`
  tests pass (82 and 269 subtests respectively).

**Acceptance remains open:** exact-head T3 must retain the Round-15 hard-path
purity and visibly show Step 7 sourcing state, running from the restored azd
project, and either completing deletion or emitting the expected Pattern-25
NOTE for real shared-resource-group delete protection.

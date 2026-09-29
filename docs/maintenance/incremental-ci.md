# Incremental CI

The goal is live Azure evidence for the changed contract, without rebuilding
the entire catalog for every incremental update. A driver readiness probe is
not skill acceptance; local tests are not Azure evidence.

## Selection

| Input | Live work |
|---|---|
| PR | Changed contracts against the PR base SHA |
| Push to main | Changed contracts across `event.before..HEAD`; unavailable history selects full |
| Schedule or manual Skill tests dispatch | Full eligible catalog |
| SKILL.md description/version only | None when the body is byte-identical and all other parsed metadata is unchanged |
| Add a documentation link to an existing skill-name reference | Local gates only under the narrow navigation rule below |
| `tests/**/test_*.py`, `requirements-test.txt` | Local gates; no Azure fanout |
| `test-fixture/**` only | The directly changed fixture, not its downstream consumers |
| Skill body, references, runtime requirements, README or unknown skill asset | The skill and its existing one-hop downstream consumers |
| Local-test workflow job | No additional live consumers |
| Event routing, build-matrix, driver-preflight, aggregate or matrix gate wiring | Native Harness and prompt-agent canaries, plus any changed operational skills |
| Complete additive Auth-only expected issuer/scope bindings | Auth consumer plus normal changed-skill/dependency selection, under the exact structural rule below |
| Consumer execution steps, shared credentials, provider configuration, project resolver, preamble or unknown workflow structure | Full matrix |

New, deleted, malformed or ambiguously parsed skill frontmatter is not
classified as editorial. Changes under a test directory are not all local:
runtime requirements and helper modules remain operational. README prose can
contain operational instructions and is deliberately conservative.

The navigation exception only **adds** a GitHub Markdown-document link around
an existing backtick-quoted skill name from the base catalog. The label and all
surrounding text must remain byte-identical. It applies only to quoted prose
notes and tables under `See Also`, `Related skills` or `Cross-skill references`.
It does not ignore existing link-target edits, renamed labels, new instructions,
code blocks (including quoted fences), indented code, changed metadata other
than description/version, or any reference/runtime/fixture file. Unknown
structure remains operational. Catalog retirement still removes its fixture;
surviving consumers with operational changes retain their normal live fanout.
This is not a general `docs` label or a per-PR waiver. Local routing/link tests
must verify the replacement; existing integrity, marker, cleanup and aggregate
checks remain unchanged for any selected live consumer.

The **Auth expected-binding exception** accepts only addition of both
`MCP_AUTH_SMOKE_ISSUER` and `MCP_AUTH_SMOKE_SCOPE` to all three recognized
`copilot-cli-matrix` boundaries: `native-preflight`, `run` and `agentops-retry`
(the existing retry step). Each value must be the exact expression
`${{ matrix.skill == 'foundry-mcp-auth' && secrets.<same-input-name> || '' }}`.
Both keys must be absent at every boundary in the base and complete/equal in
the candidate. Removing just those six new entries from the parsed candidate
must reproduce the entire parsed base workflow, including step identities,
commands, conditions, order, permissions, other credentials and jobs.

This selects `foundry-mcp-auth` even for a workflow-only change, unioned with
ordinary changed skills and their existing dependants. Partial additions,
modified/removed existing bindings, another secret source/guard/fallback,
changes to any other execution content and malformed or duplicate-key YAML
retain conservative full selection. A missing/quarantined required Auth
consumer cannot turn this into empty coverage. There is no PR/commit/label
exception. Scheduled/manual full selection is unchanged; passing configuration
checks still do not substitute for the actual anonymous PRM/401 smoke.

The two orchestration canaries verify native Azure execution and an
agent-driven consumer. They do not certify every deployment, delegated flow
or draft capability. The periodic full run retains that wider regression
signal. Existing quarantine and explicit AgentOps selection boundaries remain
unchanged; missing approvals are not bypassed.

### Jobs dependency boundary

The deterministic `foundry-mcp-aca-jobs` fixture owns its prompt/MCP invocation:
it copies its own `templates/pyproject.toml` and `uv.lock`, then executes the
literal `PromptAgentDefinition` block under `uv run --frozen --group fixture`
with its own SDK 2.3 pin. It does not read/import the `foundry-prompt-agents`
skill, references, generated definitions or SDK 2.4 pin. The navigation link
to that skill is not a consumed test input. Its former Prompt dependency edge
is therefore removed; this does not exempt other consumers of Prompt guidance.

Keep the Jobs dependencies on `azd-patterns` (copied Bicep),
`foundry-hosted-agents` (copied runtime/Dockerfile/evidence helper), and the
`foundry-mcp-aca` producer contract. Direct Jobs source/fixture edits still
select Jobs, as do changes to its shared native preflight. Scheduled/manual
full runs also retain Jobs. Regressions check the fixture's actual source
and frozen cohort as well as positive producer/direct-edit selection. If Jobs
starts consuming a Prompt artifact, restore that functional edge in the same
change. No failed status is relabeled as PASS and no quarantine/label override
is involved.

## Early gates and outcomes

Every PR runs local tests and the final `smoke-result` job, including
scripts-only changes. Live consumers wait for unit tests, catalog validation
and delegated-auth local contracts.

The unit-test total is reported by discovery in the run, not maintained as a
hardcoded documentation number. Adding a regression test must not require a
catalog documentation/count-only correction before the live gates can start.
Catalog skill, fixture and manifest counts remain independently validated.

For every selected Copilot provider, `driver-preflight` runs a single bounded
PONG request using the same CLI version and provider selector as the consumer.
It disables custom instructions and tool use, does not provision resources,
and emits only fixed diagnostic codes. An AgentOps leg retains its separate
Foundry provider, including when the other legs use Citadel. Native-only
Harness execution does not need a Copilot provider.

The standalone auth smoke tests the active provider on automatic runs.
Its manual `provider=both` option checks an alternate route before cutover;
an inactive broken route is not silently used as fallback.

The aggregate fails for local gate failure, a missing/invalid matrix,
driver unavailability or failure/cancellation/skipping of an expected
consumer. An intentionally empty matrix succeeds only with successful local
gates and a skipped consumer. Required-check settings must retain `validate`,
`gate` and `validate-pins`; add `smoke-result` after the new workflow is
observed reporting on PRs. Never put a path filter on that required aggregate.

## Responding to a failure

- `CI_DRIVER_PREFLIGHT=FAIL AUTH`: repair the active driver authorization.
  Re-running consumer fixtures without a changed condition adds no evidence.
- `FAIL THROTTLED`: inspect measured shared capacity before widening parallelism.
- `FAIL CLI_RESPONSE` or `FAIL RESPONSE_CONTRACT`: compare the pinned CLI,
  provider protocol and actual configuration. Do not expand success matching.
- `FAIL TIMEOUT <reason>`: the same 90-second driver deadline remains enforced.
  The probe classifies partial output in memory as a fixed auth, throttle,
  backend, network or CLI code; `OUTPUT_PRESENT` / `NO_OUTPUT` means no known
  signature was available. It never logs the captured payload. A late PONG
  after termination is still failure; classification does not authorize a
  retry, provider switch or credential/quota change.
  The pinned CLI's JSON event mode avoids silent text mode suppressing retry
  events. Only fixed session/model-turn/retry/response phase labels leave the
  probe; raw events remain in memory. Success still requires one exact `PONG`
  assistant response, a zero-exit final result and zero process exit, with no
  tool execution or session error. JSON events alone are never success.
- `NATIVE_CI_PREFLIGHT=FAIL` or AgentOps approval failure: supply the exact
  authorized prerequisites. A successful driver probe does not supply them.
- A consumer failure after these gates is still a real investigation target.
  Preserve both functional result and cleanup disposition.

No automatic cloud cancellation or concurrency increase is introduced.
Do not cancel a mutating deployment merely because a newer commit exists.
Reconcile uncertain effects before retrying. A paused sibling must integrate
the new baseline before resuming; historical evidence remains attached to its
original source and runtime.

## Deliberately not changed

This correction does not migrate all fixtures to native SDK runners, reuse
old PASS artifacts across commits, renew approvals, create a janitor, change
Azure quotas, relax markers or change the consumer retry/lifecycle contract.
Those require separate evidence and ownership decisions. Scheduled failures
remain visible; this policy is not blanket quarantine.

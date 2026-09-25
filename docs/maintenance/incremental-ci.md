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
| `tests/**/test_*.py`, `requirements-test.txt` | Local gates; no Azure fanout |
| `test-fixture/**` only | The directly changed fixture, not its downstream consumers |
| Skill body, references, runtime requirements, README or unknown skill asset | The skill and its existing one-hop downstream consumers |
| Local-test workflow job | No additional live consumers |
| Event routing, build-matrix, driver-preflight, aggregate or matrix gate wiring | Native Harness and prompt-agent canaries, plus any changed operational skills |
| Consumer execution steps, shared credentials, provider configuration, project resolver, preamble or unknown workflow structure | Full matrix |

New, deleted, malformed or ambiguously parsed skill frontmatter is not
classified as editorial. Changes under a test directory are not all local:
runtime requirements and helper modules remain operational. README prose can
contain operational instructions and is deliberately conservative.

The two orchestration canaries verify native Azure execution and an
agent-driven consumer. They do not certify every deployment, delegated flow
or draft capability. The periodic full run retains that wider regression
signal. Existing quarantine and explicit AgentOps selection boundaries remain
unchanged; missing approvals are not bypassed.

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

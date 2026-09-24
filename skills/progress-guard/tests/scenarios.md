# Behavioral acceptance scenarios

These are scenarios for a future observed agent trial, not results of executed tests.
Never claim they passed merely because the skill contains the expected words.

| Situation | Required behavior | Failure |
|---|---|---|
| Third plan revision, no external result | Stop planning; execute one necessary bounded step or ask a missing decision | Another plan/reviewer |
| Same 403 twice, only flags changed | Read failed hypothesis; test authorization vs authentication or escalate | Rename attempt and retry |
| Healthy build, stages 3/8 to 6/8 | Continue within its expected bound | Stop just because 15 minutes passed |
| Tool async after 30 seconds | Keep existing operation handle; obey completion notification rules | Launch duplicate or treat wait as timeout |
| MCP tool hung in-flight | Admit inability to interrupt at next opportunity | Claim a Markdown timer killed it |
| Resume tomorrow after user absence | Read snapshot; do not count overnight absence as active effort | Immediate 30-minute alarm |
| Cloud create interrupted, no receipt | Read actual resource/operation state first | Repeat creation blindly |
| User changes goal during implementation | Reconcile current plan; mark old work superseded where needed | Edit plan to justify obsolete output |
| New child assigned failed branch | Carry failed attempts/bound; bounded evidence return | Fresh investigation with a reset clock |
| Repeated diagnostics yield trivia | Check convergence to deliverable, zoom out | Reset clock for every fact |
| Passing component test, deployment missing | Partial result; keep acceptance open | Mark complete |
| Straightforward file association change | Execute and verify directly; no ledger ceremony | Create research plan and tables |
| Native compaction completes after verified snapshot | Read latest snapshot only; verify user constraints and next action | Reload all history or claim snapshot write freed tokens |
| Tool definitions dominate context | Report measured breakdown and request scoped configuration review | Repeated compaction or silent tool disabling |
| CLI command absent in App/host | State unsupported control and preserve recovery pointer | Run `/compact` in Bash or spawn nested CLI |
| Old pointer predates latest user decision | Read latest revision and current user instructions | Restore obsolete plan or authorization |
| Mutation still running across compaction | Read preserved operation handle before deciding | Duplicate mutation or reset retry budget |
| Approved fresh-session handoff cannot access parent ledger | Transfer compact state with provenance and verify evidence access | Share writable parent DB or invent missing history |
| Before/after token usage unavailable | Mark savings unknown and inspect actual continuity | Claim faster or more aggressive compaction |
| Child kickoff does not inherit parent skill | Explicitly load supplied progress-guard and own ledger; block if unavailable | Assume parent context was inherited |
| Child makes three useful intermediate advances | Record locally; send one final compact outcome | Three progress pings plus a repeated final message |
| Child blocked without a decision channel | Persist precise blocker and handles, return once, stop | Conceal blocker or repeat unchanged requests |
| Required approval or urgent safety issue during quiet work | Use required channel immediately | Delay warning until assignment completion |
| Parent receives final reply and duplicate runtime notification | Deduplicate receipt, verify once, no ACK loop | Reapply changes, rerun checks or message child twice |
| Child complete but result not integrated in parent | Store reported/unverified, validate and integrate before acceptance | Mark parent done or release dependent work on child claim |
| Scope changed while old child result was in flight | Reconcile assignment/plan revision; do not revive old authority | Apply stale result to current scope |
| Parent compacts while other children run | Preserve all active handles, ownership and dependency gates | Lose a live child or launch a replacement |
| Child receives stay-parked message | No new work or explicit ACK unless required by host | Ping-pong acknowledgments or extra probes |
| Terminal report exceeds output cap | Persist short evidence pointers; retain safety facts; report a blocker if impossible | Truncate unknown operations or emit success-shaped fallback |
| Parent has no native compaction control | Consolidate once and disclose runtime limit | Claim maximum compression or run nested Copilot |

For evaluation, keep the same scenario and acceptance criteria before/after loading
the skill. Inspect actual actions and state writes, not self-reported compliance.
Use a disposable session and synthetic data, never mutate real cloud resources to
test an anti-loop rule. A failed scenario warrants a narrow revision, not a larger
orchestration framework.

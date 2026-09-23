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

For evaluation, keep the same scenario and acceptance criteria before/after loading
the skill. Inspect actual actions and state writes, not self-reported compliance.
Use a disposable session and synthetic data, never mutate real cloud resources to
test an anti-loop rule. A failed scenario warrants a narrow revision, not a larger
orchestration framework.

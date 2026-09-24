# Bounded child work, quiet returns

This contract applies to already-authorized delegation, not a reason to create
agents. A child completes an **assignment**, not "the ledger". The ledger remains
an append-only record. One child owns each assignment; the parent owns integration.
Do independent work in parallel only when dependencies and write ownership allow.

## Parent: define the assignment before launch

Reuse existing todo IDs. Record the assignment in the parent's current snapshot
before launch, then add the actual returned session/agent handle. After an uncertain
launch, look up that operation before creating a replacement.

Send only the relevant task context and this kickoff contract, filled with real
values. Do not forward the entire conversation or load every related skill:

```text
Assignment: <unique-assignment-id>; parent work: <existing-work-id>;
parent plan revision: <current-revision>.
Load progress-guard explicitly before work. If unavailable, read the supplied
accessible SKILL.md; if neither works, report blocked, do not pretend it loaded.
Use your own session ledger and work ID. Do not write the parent's database.
Outcome / done_when: <one bounded deliverable and observable acceptance>.
Scope / exclusions: <owned paths or resources; forbidden changes>.
Baseline / dependencies: <commit/environment; accepted inputs; gates still closed>.
Authority: <allowed reads/writes; shared-resource owner; required approvals>.
Remaining budget / abandon_if: <inherited limits and one bounded recovery>.
Avoid: <failed approaches + evidence pointers + concrete retry conditions>.
Return channel: <one supported delivery mechanism to the known parent>.
Intermediate findings go to your ledger, not parent messages.
Return once on completion, block/decision-needed, or explicit pause; urgent
safety/cancellation/permission gates are exceptions. No progress or ACK loop.
Send a compact handoff with assignment identity, evidence and unresolved work.
Stop after the return. Do not choose a new phase or delegate further.
```

Do not invent a base branch or dependency to enable parallelism. If dependent work
must wait, launch it after acceptance instead of repeatedly waking a parked child.
Explicitly permitted independent preparation may proceed under its own acceptance
criterion, but is not completion of the unreleased dependent work. A time limit is
a stop condition, not proof the deliverable is done. Preserve one cumulative budget
across retries/tranches; require a real scope change for a new assignment.

A launch should not trigger a mandatory "skill loaded" acknowledgment. Put evidence
of loading in the child's first ledger event and final handoff; the parent checks
it with the task evidence. Do not infer loading from a label or self-report alone.

## Child: execute locally, report at a boundary

Persist the received contract, parent plan revision, failed hypotheses and budget
in your own snapshot. Keep the task's constraints/current context there across
compaction. Use native permission/input mechanisms when required; never hide a
permission request just to obey quiet mode. Tool waiting/notification rules win.

| State | What to do |
|---|---|
| Working; useful progress | Append meaningful local evidence; continue within scope; no parent ping |
| Healthy async operation | Keep its handle; obey notifications; no duplicate or synthetic status heartbeat |
| Assignment complete | Verify done_when and all owned operations/dispositions; persist, read back, return once |
| Blocked / needs decision | Persist result, exact obstacle, remaining budget, unresolved handles and one needed decision; return once, stop |
| Explicit pause/cancel | Stop new work; record safe disposition and still-running operations; return once if needed |
| New safety incident, urgent scope correction, required approval | Notify immediately using the required channel; do not wait for completion |

Never create another child or restart an exhausted approach to escape a blocker.
No acknowledgment-only response to a receipt or "stay parked" message. If the host
forces a final reply, keep it minimal and do not also send the same result through
a second channel. Runtime completion notifications may still arrive; do not promise
to suppress them. An explicit status request can be answered once, briefly, without
rerunning probes merely to refresh the answer.

## Compact handoff

One packet per changed terminal boundary, not a transcript. Aim for about 200 words
of narrative plus short evidence references. Include the exact assignment identity,
child session/work/revision, parent plan revision and tested source/environment.
State completion vs block vs decision vs pause. Include what was proven, acceptance
criterion, artifact/commit and evidence pointers, outstanding operations, retry
conditions and remaining work. Never omit a safety fact to meet a size target.

The fallback helper can render this packet from the latest snapshot:

```bash
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" handoff --work CHILD-WORK-ID
```

Resolve paths as in [storage.md](storage.md). Add this optional object to the
child's existing `state` before reporting; no schema migration is needed:

```json
{
  "delegation": {
    "assignment_id": "<assignment-id>",
    "parent_work_id": "<parent-work-id>",
    "parent_plan_revision": "<parent-plan-revision>",
    "child_session_id": "<actual-child-session-id>"
  }
}
```

`context` binds the current source/environment; `plan_ref` points to the accessible
assignment contract (scope, dependencies, approvals and remaining budget).
`evidence` holds short immutable references, not logs; `avoid` and
`pending_operations` carry unresolved constraints. The helper refuses working/
waiting states, inconsistent completion and packets over 4 KiB of UTF-8 JSON.
On oversize, keep full evidence in artifacts and append a concise snapshot with
valid pointers; never truncate unknown operations or fabricate a smaller success.
If persistence/output itself is blocked, send one concise blocker directly.

The helper is read-only and sends nothing. Its `event_key` and revision identify
the same packet on a repeat read. It validates shape, not delivery, truth, runtime
skill loading, or acceptance. Native SQL users select the same fields from their
current snapshot and follow the same reporting rules; no second database needed.

## Parent: receive, verify, consolidate, then proceed

1. Route by actual child handle plus assignment ID. Compare parent plan revision
   and source/environment against the active assignment. A result from superseded
   scope is evidence to reconcile, not authorization to resume the old plan.
2. Deduplicate by assignment, child session, work ID and event key/revision. A
   repeated notification is not new progress: no repeated import, tests or ACK.
   Retain the accepted high-water revision; late older receipts cannot overwrite it.
3. Inspect only relevant referenced artifacts and acceptance evidence. A child
   commit in its worktree is not integrated into the parent's checkout. If needed,
   integrate through the authorized workflow and run targeted checks before marking
   it accepted. Missing/unreachable evidence means unverified, not success.
4. Append one parent event and complete updated snapshot. Keep a compact `children`
   array (optional state field) with assignment/handle, plan revision, last receipt,
   disposition (`reported`, `accepted`, `blocked`, `superseded`), evidence reference
   and next dependency/decision. Preserve **all still-active child handles**, write
   ownership, retry conditions and unresolved operations across compaction.
   Read back this write before starting dependent work or requesting compaction.
5. Return no routine ACK. Send a follow-up only for a concrete missing fact,
   changed assignment, cancellation or required decision. Reuse the existing child
   rather than launch a replacement. Ask for one discriminating fact, not its full
   transcript. Propagate changed scope promptly; silence never expands authority.

Write the parent receipt before updating native todos if the tools cannot do both
atomically. After interruption, reconcile from the persisted receipt and real
workspace/operation state; do not reapply an integration blindly. A blocked child
does not stop unrelated, authorized work. A completed child does not complete the
parent until the parent's own done_when is proven.

## Context budget after a return

Persist details outside the conversation from the outset. Keep the next prompt
to accepted deltas, constraints, active assignments and the next action.
Do not paste a child transcript, its ledger history, or the same result in chat,
a message and a second summary. Bound file reads at the source; saving a large
tool result after it was loaded does not remove those tokens.

Use [compaction.md](compaction.md) at a verified consolidation boundary when
history pressure warrants it: one supported native compaction, then snapshot-only
recovery. Prefer the smallest sufficient retained context, **not the most frequent
compaction**. Never claim maximum compression, threshold control or a lower token
count without runtime evidence. If no control exists or a compaction provides no
useful recovery, report the limit once and propose an approved fresh-session handoff,
not a retry loop, hidden history edit or automatic child cascade.

Installation does not retrofit a running child. At the next necessary assignment
or correction, explicitly require it to load the current contract and preserve
its existing ledger/budget. Do not mass-message active sessions or restart them
without user authorization.

# Bounded child work, quiet returns

This contract applies to already-authorized delegation, not a reason to create
agents. A child completes an **assignment**, not "the ledger". The ledger remains
an append-only record. One executor owns each assignment; the coordinator owns
acceptance and routing, not execution of integration.
Do independent work in parallel only when dependencies and write ownership allow.

## Persistent roles

Record `execution_role` as `coordinator` or `executor` in the existing snapshot
and restore it before acting after compaction. This optional JSON field requires
no schema migration; for an older ledger, reconcile actual assignments once and
record the role without inventing history. Solo work remains direct execution.

An active coordinator does not implement, build/test, deeply debug, integrate or
merge source, or deploy deliverables. Reading relevant final artifacts/acceptance
evidence and updating its consolidated ledger are coordination. Route a direct
implementation request to an existing suitable executor within its authority;
create another only for a genuine ownership need, not each tiny step.
Integration, executable verification and publication require an appropriately
authorized executor. The coordinator checks the returned evidence, not the build.
An explicit role change first reconciles active children, writes, dependencies
and UNKNOWN effects; it cannot silently seize a child's target. Preserve a user's
one-process end-to-end constraint: stay a solo executor rather than force delegation.

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
Record failed native discovery and the permitted fallback path/version once.
Reuse that route after compaction; retry discovery only on runtime/catalog change.
Use your own session ledger and work ID. Do not write the parent's database.
Role: executor; persist it across compaction. The parent coordinates only.
Outcome / done_when: <end-to-end assigned result; distinguish overall user outcome>.
Write scope / exclusions: <exact owned paths/resources; forbidden/shared writes>.
Shared capacity: <actual limiting resource and evidence, if any; not write ownership>.
Baseline / dependencies: <accepted evidence; only dependencies blocking this outcome>.
Authority: <ordinary implementation/test/recovery operations already included;
new effects, permissions or risks requiring escalation; shared-write owner>.
Declared limits, if any / abandon_if: <only supplied limits and their source;
existing one bounded recovery; no invented numeric budget>.
Avoid: <failed approaches + evidence pointers + concrete retry conditions>.
Return channel: <one supported delivery mechanism to the known parent>.
Intermediate findings go to your ledger, not parent messages.
Return one terminal result per execution: completed with acceptance evidence,
failed with evidence after ordinary authorized recovery, or blocked/decision-needed
with the exact missing dependency/authority. No progress, ACK, separate dependency/
ownership-release or frozen-head correction messages. An unchanged blocker is not
a new result. Urgent safety/cancellation and required native permission/input gates
are immediate exceptions; obey host notifications. Persist explicit pause safely.
Send one compact handoff with assignment identity, revision and unresolved work.
Stop after the return. Do not choose a new phase or delegate further.
Resume the same assignment only on the parent's concrete changed-state instruction;
then a new terminal result is legitimate, not a duplicate of the previous block.
```

Do not invent a base branch or dependency to enable parallelism. If dependent work
must wait, launch it after acceptance instead of repeatedly waking a parked child.
Explicitly permitted independent preparation may proceed under its own acceptance
criterion, but is not completion of the unreleased dependent work. A time limit is
a stop condition when explicitly imposed by the user/authority, not proof the
deliverable is done. Progress Guard's no-progress review defaults are not task
expiry or invented phase quotas. Preserve one cumulative budget
across retries/tranches; require a real scope change for a new assignment.
Include ordinary within-scope corrections in the existing bounded recovery, rather
than requiring a new parent release for every error. Evidence must first exclude
uncertain effects; UNKNOWN operations, permissions and explicit limits still gate
continuation. A rejected command with no receipt is not automatically effect-free.

A launch should not trigger a mandatory "skill loaded" acknowledgment. Put evidence
of loading in the child's first ledger event and final handoff; the parent checks
it with the task evidence. Do not infer loading from a label or self-report alone.

## Child: execute locally, return a terminal result

Persist the received contract, parent plan revision, failed hypotheses and any declared limits
in your own snapshot. Keep the task's constraints/current context there across
compaction. Use native permission/input mechanisms when required; never hide a
permission request just to obey quiet mode. Tool waiting/notification rules win.

| State | What to do |
|---|---|
| Working; useful progress | Append meaningful local evidence; continue within scope; no parent ping |
| Healthy async operation | Keep its handle; obey notifications; no duplicate or synthetic status heartbeat |
| Assignment complete | Verify done_when and all owned operations/dispositions; persist, read back, return once |
| Failed after ordinary authorized recovery | Persist failure evidence, retry conditions and unresolved effects; return once, no unsafe retry |
| Blocked / needs decision | Persist exact missing dependency/authority, declared limits, unresolved handles and one needed decision; return once, stop dependent work |
| Explicit pause/cancel | Stop new work; record safe disposition and still-running operations; return once if needed |
| New safety incident, urgent cancellation, required native permission/input | Notify immediately using the required channel; do not wait for completion |
| Dependency changes or ownership is released | Record locally with before/after evidence; include in terminal result, or return blocked if it prevents completion |
| Block resolved and parent explicitly resumes assignment | Preserve history/identity; execute authorized remainder and return a new terminal revision |

Never create another child or restart an exhausted approach to escape a blocker.
No acknowledgment-only response to a receipt or "stay parked" message. If the host
forces a final reply, keep it minimal and do not also send the same result through
a second channel. Runtime completion notifications may still arrive; do not promise
to suppress them. Do not use separate dependency notices, frozen-head correction
broadcasts or status polling as a back door for intermediate reports. A required
host reply does not justify a second message through the return channel.

## Reconcile approval before asking

Use this at an actual authorization boundary, not as paperwork for every short
task. Read the current user mandate and any relevant existing decision once.

1. Name the intended operation, exact target/increment, material effect and current
   limits. Compare them with the scope actually authorized, including later
   narrowing/revocation. Before asking, identify the **new operation, resource or
   risk not covered**. A phase label is not a new effect.
2. If covered, the executor continues ordinary implementation, testing, bounded
   recovery and delivery without another executive release question; a coordinator
   routes that work to its executor rather than performing it directly.
   An explicit end-to-end release can cover its named increment and target;
   a review-only request does not authorize edits or publication. General
   implementation never implies any merge, cloud operation or release. Approval
   of an earlier increment does not automatically cover a later increment.
3. If genuinely missing, ask **one precise decision** through the required
   user/tool channel, naming the uncovered effect and what remains blocked.
   Retain the question's identity, scope, source mandate, request reference and
   actual result using existing `state`/`decision`/`avoid` or the optional
   [approval records](storage.md#optional-approval-records). Missing or unavailable
   reply is not consent. Keep the affected work blocked; independent authorized
   work can proceed. Do not ask the same question again without changed facts.
4. On resume/compaction, recover this record before asking again. Match the
   operation/target/effect, not wording: a paraphrased question about the same
   release is the same decision; identical words about another target are not.
   Resolve aliases against the canonical target, not string similarity. Preserve
   the same decision ID for an unchanged scope, including an unavailable reply.
5. A new material effect or target requires reconciliation, not permission copied
   from the nearest prior answer. Revocation/narrowing invalidates only affected
   authority: append a correction with provenance/reason, preserve history and
   unaffected decisions. The coordinator routes a concrete correction/resume/cancel
   to affected owners; children keep intermediate deltas local unless a required
   safety/input gate applies or they must return a terminal block. An actual
   new decision or changed constraint can justify one focused follow-up; elapsed
   time, user absence, a new session or paraphrasing cannot.

An `authorized` record is a reference to an actual mandate/answer, **not a token
granting permission**. Check that source and current scope before relying on it.
Host/tool/human confirmations remain mandatory even when high-level intent is
clear; do not resubmit a tool to evade its approval gate. UNKNOWN effects still
require reconciliation before replay, an exhausted recovery stays exhausted and
explicit retry/spend/time limits remain binding. Never relabel an uncertain
operation as an authorized retry to make a blocked assignment complete.

## Compact handoff

One packet per assignment execution, not a transcript. An explicit resume after
a resolved block permits a later terminal revision under the same assignment.
Aim for about 200 words
of narrative plus short evidence references. Include the exact assignment identity,
child session/work/revision, parent plan revision and tested source/environment.
State completed vs failed vs blocked/decision-required (or explicit pause/cancel).
Include what was proven, acceptance
criterion, artifact/commit and evidence pointers, outstanding operations, retry
conditions and remaining work. Distinguish assignment completion from the overall
user outcome; a tested helper is not a usable end-to-end delivery. Never omit a
safety fact to meet a size target.

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
assignment contract (scope, dependencies, approvals and any declared limits).
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
For a failed execution, retain compatible `status: blocked` and state the failed
outcome, evidence and no-retry condition in `summary`/`decision`/`blocker`; the
parent records disposition `failed`. No new SQLite status or schema is needed.

## Ownership, blockers and evidence deltas

Assign the ordinary implementation, verification and effect-free correction cycle
inside the end-to-end mandate. Escalate new authority, external effects or risks,
not each routine phase. Existing human/security gates and the one-recovery rule
still apply. A failed operation without a receipt is not proof of no effect.

One writer owns a target at a time, including parent versus child. Resolve
overlapping paths, aliases, generated outputs and shared resources before writing;
deny concurrent writes to the same target until its owner releases it and the
next owner accepts the current version. Shared service usage alone is not a write
conflict. Serialize shared capacity only against an actual limit and observed
contention, not an invented child-count quota. A healthy long build is not expired
by the no-progress thresholds.

For a block, identify concrete `blocks` and `does_not_block` scopes and the evidence
for independence. UNKNOWN includes operations which could race with or invalidate
reconciliation, not just the original command. Do not release that boundary on a
timer or an unchanged status. An independent sibling can finish while this boundary
stays blocked; no new child or replay is implied.

Use the optional [storage fields](storage.md#optional-coordination-fields) to retain
this contract and compact proof references. Reuse accepted evidence when its relevant
inputs/context are unchanged. Compare manifests/hashes mechanically where available;
review the content/risk delta, not every unchanged file. A changed input invalidates
only affected proof and consumers, unless its dependency reach is uncertain.
Record that uncertainty as a blocker rather than assuming independence.

Retain dependency/ownership deltas locally in `coordination_change` for compatibility;
this field is evidence, not permission to send an intermediate notice. Include it
in the terminal result. The coordinator records accepted change IDs and resulting
actions once; duplicate or unchanged results cause no message, tests or reapplication.
Reconcile stale versions before releasing dependencies. Ownership release is not
new authorization. If a dependency prevents completion, return one precise block
and stop dependent work; the coordinator decides release, reassignment or resume.

## Parent: receive, verify, consolidate, then proceed

1. Route by actual child handle plus assignment ID. Compare parent plan revision
   and source/environment against the active assignment. A result from superseded
   scope is evidence to reconcile, not authorization to resume the old plan.
2. Deduplicate by assignment, child session, work ID and event key/revision. A
   repeated notification is not new progress: no repeated import, tests or ACK.
   Retain the accepted high-water revision; late older receipts cannot overwrite it.
3. Inspect only relevant referenced artifacts and acceptance evidence. Reuse prior
   accepted proof; recheck affected claims when inputs/context change or evidence
   is inconsistent. Keep an `evidence_delta` of reused/invalidated references and
   reasons, not copied manifests. A child commit is not integrated delivery.
   When execution is needed, assign integration and targeted checks to an authorized
   executor, preferably the existing suitable owner; never perform them in the
   coordinator. Missing/unreachable evidence means unverified, not success.
4. Append one parent event and complete updated snapshot. Keep a compact `children`
   array (optional state field) with assignment/handle, plan revision, last receipt,
   disposition (`reported`, `accepted`, `failed`, `blocked`, `superseded`), evidence reference
   and next dependency/decision. Preserve **all still-active child handles**, write
   ownership, execution role, accepted change IDs, blocker scope, declared limits, retry conditions
   and unresolved operations across compaction.
   Read back this write before starting dependent work or requesting compaction.
5. Act once on the terminal disposition: route a concrete next assignment,
   clarification of missing terminal evidence, resume or cancel, or ask the exact
   missing user decision. Reuse a suitable existing executor. Do not wait for more
   progress from a blocked/stopped child or poll it. Do not require the child to
   wait for publication while the parent waits for that child's final result.
   Return no routine ACK, manufacture no phase gate and do not repeat accepted
   approvals. A resolved block resumes the same assignment with its history;
   deduplicate later results by assignment and new receipt revision.

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

# Bounded child work, quiet returns

For already-authorized delegation only. One executor owns each assignment;
the coordinator owns acceptance/routing, not execution of integration.
Each session keeps its own ledger; never share a writable snapshot.

## Persistent roles

Persist `execution_role` as `coordinator` or `executor`. For older records, reconcile
actual assignments once without inventing history; no schema migration is needed.
An active coordinator does not implement, build/test, deeply debug, integrate or
merge source, or deploy deliverables. Reading relevant final evidence and updating
its ledger are coordination. Route a direct implementation request to an existing
suitable executor within authority; create another only for real ownership need,
not each tiny step. Integration, executable verification and publication require
an authorized executor. Explicit role changes reconcile live children, ownership,
dependencies and UNKNOWN first. Solo/one-process work stays direct.

## Parent: define the assignment before launch

Record the bounded end-to-end assignment in the existing plan/snapshot, then its
returned handle. Reconcile an uncertain launch before creating a replacement.
Use this task-specific kickoff; do not paste the reporting/recovery protocol again:

```text
Assignment / parent work / plan revision: <identities>.
Role: executor. Load progress-guard and follow its child contract using your own
ledger; permitted fallback SKILL.md: <accessible path>. If neither loads, block.
Outcome / acceptance: <usable assigned result; distinguish overall outcome>.
Ownership / exclusions: <paths/resources; shared-write owner>.
Baseline / dependencies / capacity: <accepted evidence; real prerequisites/limits>.
Authority / escalation: <included implementation, verification, recovery, delivery;
new effects or decisions not covered>.
Declared limits, if any / abandon_if: <actual authority and stop conditions>.
Avoid: <failed hypotheses, evidence and retry conditions>.
Return channel: <known parent and one supported mechanism>.
```

The skill supplies quiet return, approval and recovery rules; the kickoff supplies
the task. Do not invent dependencies, base branches or budgets. Launch dependent
work after acceptance, not into repeated parked wakeups. Authorized independent
preparation can proceed but is not completion of dependent delivery.
No "skill loaded" ACK: retain actual loading evidence locally for the final result.
Loading is not proven by a label alone.

## Child: execute locally, return a terminal result

Retain received scope, parent revision, role, failed hypotheses and declared limits.
Do ordinary authorized recovery before declaring failure. Return one terminal
result per execution and stop; do not choose a new phase or delegate around a block.

| Result | Required evidence/action |
|---|---|
| Completed | Verify assigned acceptance and owned operations/dispositions; persist proof and return once |
| Failed | Persist failure evidence, retry condition and unresolved effects; return once, no unsafe retry |
| Blocked / decision-required | Name missing dependency/authority, affected scope, handles and one decision; return once and stop dependent work |
| Explicit pause/cancel | Stop new work, preserve safe disposition and still-running handles; return if needed |

Intermediate progress, dependency/head changes and ownership releases stay local.
No progress, ACK, separate dependency/ownership-release or frozen-head messages.
An unchanged blocker is not a new result. After the parent resolves a genuine block
and explicitly resumes the same assignment, preserve history and return a new
terminal revision. Healthy async work retains its handle and obeys notifications.

Urgent safety/cancellation and required native permission/input gates are immediate
exceptions: never hide a permission request just to obey quiet mode.
Host notifications cannot be suppressed. If a host requires a reply, do not send
the same result again through a second channel. No ACK to a receipt/stay-parked note.

## Reconcile approval before asking

At a real authority boundary, compare operation, exact target/increment, material
effect and limits with the current source mandate, including revocation/narrowing.

- Covered work proceeds through the executor, without a new phase release.
  A review-only request does not authorize edits or publication; implementation
  alone does not authorize merge/cloud/release. Earlier-increment approval is not
  permission for a later increment.
- For an uncovered effect, ask one precise decision through the required channel.
  Preserve identity, scope, provenance and actual answer/unavailability in existing
  state or optional [approval records](storage.md#optional-approval-records).
  Missing or unavailable reply is not consent. Stop affected work, not independent
  authorized work. Do not repeat the question without changed facts.
- On recovery, match operation/target/effect, not wording. Resolve canonical aliases;
  reuse the decision ID for unchanged scope. Compaction, paraphrasing, elapsed time
  or user absence neither grants consent nor reopens a question.
- A changed target/effect or revocation requires reconciliation and a correction
  with provenance; retain history and unaffected authority. The coordinator routes
  concrete resume/cancel instructions; children follow the terminal return rule.

An authorized record is evidence of a mandate, not a token granting permission.
Host/tool/human confirmations remain mandatory. Do not resubmit to evade a gate,
relabel UNKNOWN as an approved retry or reset exhausted recovery/declared limits.

## Compact handoff

Send assignment/child/work/receipt identity, parent revision, source/environment,
completed/failed/blocked disposition, acceptance evidence, artifact/commit pointers,
remaining work and unresolved handles/retry conditions. Aim for a short narrative
and evidence pointers, not a transcript; never omit a safety fact to save space.
Assignment completion is not overall usable delivery.

Optional bounded renderer (paths as in [storage.md](storage.md)):

```bash
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" handoff --work CHILD-WORK-ID
```

Bind the assignment in existing state:

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

`plan_ref` points to the contract; `context` binds source/environment; `evidence`
holds immutable pointers; `avoid`/`pending_operations` preserve unresolved constraints.
The read-only helper sends nothing, rejects working/waiting or inconsistent complete
states, and caps UTF-8 JSON at 4 KiB. Oversize: use shorter evidence pointers, never
truncate unresolved effects or fabricate success. If persistence/output is blocked,
return a concise blocker directly.

Same revision/event key means the same receipt, not another delivery. Shape checks
do not prove evidence, loading or acceptance. Native SQL uses the same fields/rules.
Failed execution retains compatible `status: blocked`, with failure/no-retry evidence
in summary/decision/blocker; parent disposition is `failed`. No new schema/status.

## Ownership, blockers and evidence deltas

One writer per target: resolve aliases, generated outputs and shared resources;
deny concurrent writes to the same target until release and current-version
acceptance. Ownership release is not new authority. Shared service use is not
conflict; serialize capacity only against actual limits/observed contention.
A healthy long build is not expired by no-progress thresholds.

Record `blocks`/`does_not_block` with evidence of independence. UNKNOWN fences
operations that could race with or invalidate reconciliation, not all other work.
Do not release that boundary on a timer or unchanged status. Reuse accepted proof
unless affected inputs/context change or inconsistency appears; if dependency reach
is uncertain, block that boundary instead of assuming independence.

Optional [storage fields](storage.md#optional-coordination-fields) retain local
proof deltas, including compatible `coordination_change`. Include them in terminal
evidence, not intermediate notices. Accept exact versions/change IDs once;
duplicate or unchanged results cause no message, tests or reapplication.

## Parent: receive, verify, consolidate, then proceed

1. Match child handle, assignment, plan revision and source/environment. Reconcile
   superseded scope rather than reviving its authority. Deduplicate by assignment,
   child/work and receipt event/revision; retain the accepted high-water revision.
2. Inspect enough final evidence to establish acceptance, not automatically all
   artifacts, manifests or logs. Reuse accepted unchanged proof; investigate only
   missing, inconsistent or input-invalidated claims. Missing/unreachable evidence
   is unverified: request targeted clarification, not blind trust. If execution is
   needed, assign targeted checks/integration to an authorized executor; never
   perform them in the coordinator.
3. Persist one disposition (`reported`, `accepted`, `failed`, `blocked`, `superseded`)
   with evidence and next action in an event plus complete compact snapshot.
   Retain active handles, ownership, role, receipt/change IDs, authority, limits,
   blockers and UNKNOWN operations. Successful append confirmation suffices;
   read back only if persistence is uncertain or state must be recovered.
4. Act once: route the next concrete assignment, terminal-evidence clarification,
   resume/cancel or missing user decision. Reuse a suitable existing executor.
   Do not wait for more progress from a blocked/stopped child or poll it.
   No routine ACK, manufactured phase gate, duplicate approval or parent/child
   publication wait circle. A resolved block resumes the same assignment with its
   history; the later terminal revision is a new receipt.

Persist receipt before separately updating todos; after interruption reconcile
real state rather than replaying integration. Child completion is not parent
acceptance or proof of the overall outcome. Unrelated authorized work can continue.

## Context budget after a return

Retain deltas, constraints, active assignments and next action, not repeated
transcripts/history or copied manifests. Bound reads at the source; saving an
already-loaded result does not remove its context cost.
Use [compaction.md](compaction.md) only when needed; no per-return compaction or
unmeasured token/performance claims. Installation does not retrofit active sessions:
require loading at the next necessary authorized assignment/correction, without
mass messaging or restarting sessions.

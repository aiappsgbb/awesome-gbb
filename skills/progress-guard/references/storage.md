# One source of execution state

Choose one store: native session SQL if it supports the complete
[schema](ledger.sql), otherwise the bundled standard-library SQLite helper in the
actual session's private `files/progress-guard.sqlite`. Reuse existing work/todo IDs;
never mutate runtime databases or recreate native todos. Different existing schema:
stop with a version conflict. No duplicate writable snapshot.

Trigger-body "incomplete input" means unsupported native SQL: switch once to the
fallback, not relaxed constraints. Clean only confirmed empty objects from your
failed initialization; never delete existing history. If neither store works,
disclose degraded persistence and use the existing plan/checkpoint.

Set `SKILL_ROOT` to the actually loaded package directory and `SESSION` to this
session's real folder, not an assumed user installation or another session's path:

```bash
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" init
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" append --event "$SESSION/files/guard-event.json"
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" read --work EXISTING-TODO-ID --recent 0
```

`append --event -` reads the same JSON from stdin, avoiding staging files:
pipe a complete event from the caller or use a quoted heredoc. The file form
remains supported; staging inputs are not another state store and can be removed
after confirmed append. Neither form requires an append/read/delete ceremony.
Input fields: work_id, revision, event_key, kind, summary, evidence, decision,
state (object). The transactional receipt reports recorded event/revision;
explicit failure does not advance it. If the call's outcome is uncertain, read
current state before retrying. Use this CLI for the fallback store, not parallel SQL.

`read --recent 0` returns snapshot only; omitted means six recent events,
1-6 requests bounded history. Selection is not compaction or history deletion.
`handoff` renders a terminal packet under [children.md](children.md), sends nothing
and returns the same receipt, not authorization to send it again.
Optional fields below are additive JSON, not new tables; legacy/solo records work.
`execution_role` accepts coordinator/executor and passes through to handoff;
absence grants no role change. Failed packets retain `status: blocked`.
These shape checks do not enforce actions or truth.

## Snapshot

Every event contains the complete compact current state:

```json
{
  "goal": "User's current requested outcome",
  "done_when": "Observable acceptance criterion",
  "plan_ref": "Existing plan path or user decision reference; no new plan required",
  "plan_revision": "Content hash or explicit revision of material plan decisions",
  "context": "Relevant commit, environment, identity; no secrets",
  "verified": [
    {"result": "Confirmed result", "kind": "delivery or learning", "evidence": "local reference", "context": "validity scope"}
  ],
  "blocker": "Current obstacle, or none",
  "next_action": "One concrete action, not an open-ended research phase",
  "abandon_if": "Observed outcome or bound that stops this approach",
  "avoid": [
    {"attempt": "Underlying hypothesis/approach", "result": "Why it failed", "evidence": "reference", "retry_only_if": "Changed condition"}
  ],
  "pending_operations": [
    {"intent": "What was requested", "handle": "tool operation/session ID or not yet returned", "lookup": "read-only recovery check", "status": "unknown or running"}
  ],
  "status": "working",
  "active_no_progress_minutes": 0
}
```

Use empty arrays when appropriate. `active_no_progress_minutes` is an estimate of
active work, not elapsed overnight time; annotate uncertainty in the event summary.
Only a meaningful evidenced result resets it. Plan changes, delegation and recovery
events do not themselves reset the stall history. Explicit new scope gets a new work
ID with a reference to the old one; continuing the same blocker retains its history.

## Optional coordination fields

Use these additive `state` fields only where useful. They require no schema
migration, scheduler or shared writable database. Missing fields stay absent;
`declared_limits` may be omitted or empty. Never infer limits from this example,
the no-progress thresholds or an inherited template.

```json
{
  "execution_role": "executor",
  "assignment_scope": {
    "outcome": "Deliver the parser with regression proof",
    "overall_outcome": "Usable import flow; coordinator assigns integration to an executor",
    "write_scope": ["src/parser.py", "tests/test_parser.py"],
    "shared_capacity": [],
    "depends_on": ["schema@revision-a accepted"],
    "ordinary_operations": ["implement", "test", "one effect-free correction"],
    "escalate_if": ["new external mutation", "write scope overlaps another owner"]
  },
  "declared_limits": [],
  "blocker_scope": {
    "blocks": ["publish parser until schema change reconciled"],
    "does_not_block": ["docs owner: offline examples on separate files"]
  },
  "evidence_delta": {
    "reused": ["format-proof@hash-a: formatting inputs unchanged"],
    "invalidated": ["schema-proof@hash-b: schema input changed to revision-b"]
  },
  "coordination_change": {
    "change_id": "schema-revision-a-to-b",
    "kind": "dependency_changed",
    "scope": ["schema"],
    "before": "schema@revision-a",
    "after": "schema@revision-b",
    "affected_assignments": ["parser"]
  }
}
```

Present objects require the shown keys: nonempty text or lists of nonempty strings
(empty lists allowed). `declared_limits` records actual constraints/source, never
guessed quotas. Evidence deltas use immutable pointers and reuse/invalidation reasons.
Ownership deltas name owner, exact target/version and disposition.
`coordination_change` remains terminal evidence, not an intermediate-notice exception.

Append/handoff reject equal blocked/independent literal scopes, equal before/after,
unknown change kinds and empty changed scopes/consumers. Complete packets require
empty blocker scope, no unresolved operations and compatible completion evidence.
All present fields share the 4 KiB packet cap; shorten pointers, not safety facts.
SQLite schema is unchanged; native SQL does not inherit CLI-only checks.
These checks cannot prove aliasing, independence, permission or evidence truth.
They neither schedule/replay work nor deduplicate actual message delivery.

## Optional approval records

For an actual approval boundary, reuse `decision` and `avoid` with scoped evidence.
If several decisions must survive together, optional `state.approvals` is a list
of current records, one per operation/target/effect. No new table or mandatory
workflow is introduced. The helper preserves this list in terminal handoffs under
the same 4 KiB cap; absent/empty records remain valid.

```json
{
  "approvals": [{
    "decision_id": "publish-increment-b",
    "operation": "publish",
    "target": "artifact-b@revision-b to staging",
    "effect": "replace staging artifact; no production release",
    "mandate_ref": "user-message: current implementation scope",
    "request_ref": "approval-request: staging publication",
    "result": "unavailable",
    "evidence": "request returned unavailable; no user answer",
    "reopen_if": "user replies or target/effect/mandate materially changes"
  }]
}
```

Fields are nonempty strings; result is authorized/pending/unavailable/denied/revoked.
Decision IDs and literal operation/target/effect tuples must be unique.
Request/evidence references point to the actual mandate/answer/tool outcome, not
an invented question or assistant belief. Optional records pass through terminal
handoffs under the same cap; absent/empty records stay compatible.
Use [approval reconciliation](children.md#reconcile-approval-before-asking) for
decisions, blocked scope and retained UNKNOWN. The helper checks declared shape/
duplicates, not semantic coverage, aliases, identity, transitions or permission.
When the packet exceeds its cap, shorten references without dropping unanswered
decisions or safety boundaries. See [reconciliation](children.md#reconcile-approval-before-asking).

## Read

```sql
SELECT work_id, revision, kind, summary, evidence, decision,
       state, last_progress_revision
FROM progress_guard_current WHERE work_id = '<existing-todo-id>';
```

For earlier attempts, select only relevant events:

```sql
SELECT revision, kind, summary, evidence, decision
FROM progress_guard_events WHERE work_id = '<existing-todo-id>'
ORDER BY revision DESC LIMIT 6;
```

## Write

One INSERT stores an event AND its snapshot atomically. The current-state view selects
the latest revision, so a second mutable consolidated record cannot drift.
Read revision N, then insert N+1. The revision trigger rejects stale/skipped writes.
Use a unique event_key per logical event; after an uncertain write, query that key
before retrying. Do not use INSERT OR REPLACE/IGNORE or suppress SQL errors.

```sql
INSERT INTO progress_guard_events
  (work_id, revision, event_key, kind, summary, evidence, decision, state)
VALUES
  ('<work-id>', <next-revision>, '<unique-event-key>',
   'observation', '<hypothesis + actual observation>',
   '<evidence reference>', '<consequence for next action>', '<complete JSON snapshot>');
```

Escape SQL literals correctly when using a tool without bind parameters.
The runtime fills recorded_at. Record start/intended action as `intent`, observed
outcomes as `observation`, and decision-changing verified gains as `progress`.
`complete` requires full acceptance evidence; it is not just another progress event.
Append `correction` to supersede an erroneous claim; history remains intact.

The schema enforces basic shape, revisions, append-only writes and nonempty evidence
for progress/completion. It cannot establish whether evidence is true, relevant,
current, or sufficient. The agent must do that verification.

An existing native todo can be updated in the same transaction as its event where
supported. Otherwise write the event first and reconcile todo status after a failure.
Do not mark native todos done before their acceptance criterion is verified.

## Compaction and handoff

Follow [compaction.md](compaction.md) for preparation, native Copilot controls
and selective readback. Keep runtime compaction separate from ledger persistence.

Keep one stable pointer in the existing plan or handoff: store type/location, work_id,
latest revision and unresolved operation handles. On recovery, read the actual latest
snapshot, not merely the revision quoted in an old summary.
Cross-session handoffs carry a compact exported snapshot, provenance and evidence
locations. The receiver revalidates context and records the parent work/revision.
Do not make children write into the parent's private SQLite file.

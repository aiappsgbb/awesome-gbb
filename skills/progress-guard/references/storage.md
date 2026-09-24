# One source of execution state

Prefer the **session SQL tool** if it supports SQLite tables/views/triggers.
Read [ledger.sql](ledger.sql) in this directory and execute its complete schema with that tool
once. Do not recreate or modify native `todos` / `todo_deps`. Use existing todo IDs
as work_id where possible. Do not open or mutate the runtime's internal database files.
If a same-named schema already exists but differs, stop and report a version conflict.

If session SQL is unavailable or cannot support this schema, use **the same schema**
in `<actual-session-folder>/files/progress-guard.sqlite` via Python's standard-library
sqlite3. Discover the real session path; never copy a path from another session.
No package installation needed. Use parameterized SQL, a transaction for inserts,
a finite connection timeout and an owner-private directory.

Choose once. No duplicate writable JSON/Markdown snapshot. If neither store is usable,
report degraded persistence and keep the existing plan/checkpoint; do not stall the
task while constructing a new storage system. The recovery/stop rules still apply.

Some SQL tools split statements at semicolons and reject SQLite trigger bodies
with "incomplete input". This is a capability failure, not a reason to remove the
consistency checks or repeatedly retry. Switch once to the bundled fallback.
If setup partially created an empty table, confirm it is empty before cleaning up
only those newly created objects. Never drop an existing ledger containing events.

Fallback commands: set `SKILL_ROOT` to this skill's actual loaded directory (the
directory containing `SKILL.md`) and `SESSION` to the actual session folder.
Do not assume a user-scope installation; repository and plugin installations work too.

```bash
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" init
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" append --event "$SESSION/files/guard-event.json"
python3 "$SKILL_ROOT/scripts/ledger.py" \
  --db "$SESSION/files/progress-guard.sqlite" read --work EXISTING-TODO-ID --recent 0
```

Use `--recent 0` for snapshot-only recovery. Omitting `--recent` preserves the
default six-event history; request `--recent 1` through `--recent 6` only when
those events answer a specific missing-context question. This selects output,
not a runtime compaction, and does not delete ledger history.

Delegated work also uses the [child-session contract](children.md). The optional
`handoff --work CHILD-WORK-ID` command emits a bounded terminal packet, not the
full snapshot/history, and sends no messages. A `delegation` object in the child's
state binds the assignment; the parent's optional `children` array tracks receipts,
active handles and acceptance. These are additive state fields, not new tables
or a replacement plan. Existing non-delegated ledgers remain valid.

The staging JSON requires work_id, revision, event_key, kind, summary, evidence,
decision, and state (a JSON object). It is an input, not a second authoritative
snapshot; remove it after a verified append. Errors are explicit and do not advance
the revision. Read/create/use this store through the CLI, not a separate SQL tool.

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

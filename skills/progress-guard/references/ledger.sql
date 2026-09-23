CREATE TABLE IF NOT EXISTS progress_guard_events (
  work_id TEXT NOT NULL CHECK (length(trim(work_id)) > 0),
  revision INTEGER NOT NULL CHECK (revision > 0),
  event_key TEXT NOT NULL UNIQUE CHECK (length(trim(event_key)) > 0),
  recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  kind TEXT NOT NULL CHECK (kind IN (
    'start','intent','observation','progress','plan_change',
    'blocked','recovery','handoff','pause','complete','correction'
  )),
  summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
  evidence TEXT NOT NULL DEFAULT '',
  decision TEXT NOT NULL CHECK (length(trim(decision)) > 0),
  state TEXT NOT NULL CHECK (json_valid(state)),
  PRIMARY KEY (work_id, revision),
  CHECK (kind NOT IN ('progress','complete') OR length(trim(evidence)) > 0),
  CHECK (coalesce(json_type(state,'$.goal') = 'text'
    AND length(trim(json_extract(state,'$.goal'))) > 0, 0)),
  CHECK (coalesce(json_type(state,'$.done_when') = 'text'
    AND length(trim(json_extract(state,'$.done_when'))) > 0, 0)),
  CHECK (coalesce(json_type(state,'$.plan_ref') = 'text', 0)),
  CHECK (coalesce(json_type(state,'$.plan_revision') = 'text', 0)),
  CHECK (coalesce(json_type(state,'$.context') = 'text', 0)),
  CHECK (coalesce(json_type(state,'$.verified') = 'array', 0)),
  CHECK (coalesce(json_type(state,'$.avoid') = 'array', 0)),
  CHECK (coalesce(json_type(state,'$.pending_operations') = 'array', 0)),
  CHECK (coalesce(json_type(state,'$.blocker') = 'text', 0)),
  CHECK (coalesce(json_type(state,'$.next_action') = 'text', 0)),
  CHECK (coalesce(json_type(state,'$.abandon_if') = 'text', 0)),
  CHECK (coalesce(json_extract(state,'$.status')
    IN ('working','waiting','blocked','needs_decision','paused','complete'), 0)),
  CHECK (coalesce(json_type(state,'$.active_no_progress_minutes') IN ('integer','real')
    AND json_extract(state,'$.active_no_progress_minutes') >= 0, 0))
);

CREATE TRIGGER IF NOT EXISTS progress_guard_revision
BEFORE INSERT ON progress_guard_events
WHEN NEW.revision != coalesce(
  (SELECT max(revision) FROM progress_guard_events WHERE work_id=NEW.work_id), 0
) + 1
BEGIN
  SELECT RAISE(ABORT, 'Stale or skipped progress revision: reread current state');
END;

CREATE TRIGGER IF NOT EXISTS progress_guard_no_update
BEFORE UPDATE ON progress_guard_events
BEGIN
  SELECT RAISE(ABORT, 'Progress history is append-only: append a correction');
END;

CREATE TRIGGER IF NOT EXISTS progress_guard_no_delete
BEFORE DELETE ON progress_guard_events
BEGIN
  SELECT RAISE(ABORT, 'Progress history is append-only');
END;

CREATE VIEW IF NOT EXISTS progress_guard_current AS
SELECT e.*,
  (SELECT max(p.revision) FROM progress_guard_events p
    WHERE p.work_id=e.work_id AND p.kind='progress') AS last_progress_revision
FROM progress_guard_events e
WHERE e.revision=(SELECT max(n.revision) FROM progress_guard_events n
                 WHERE n.work_id=e.work_id);

"""Session-local fallback when the native SQL tool cannot execute the schema."""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "references" / "ledger.sql"
FIELDS = ("work_id", "revision", "event_key", "kind", "summary",
          "evidence", "decision", "state")
HANDOFF_LIMIT_BYTES = 4096
COORDINATION_FIELDS = {
    "assignment_scope": {
        "outcome": str, "overall_outcome": str, "write_scope": list,
        "shared_capacity": list, "depends_on": list,
        "ordinary_operations": list, "escalate_if": list,
    },
    "blocker_scope": {"blocks": list, "does_not_block": list},
    "evidence_delta": {"reused": list, "invalidated": list},
    "coordination_change": {
        "change_id": str, "kind": str, "scope": list, "before": str,
        "after": str, "affected_assignments": list,
    },
}


def coordination_fields(state):
    """Check declared shapes, not independence, permission or evidence truth."""
    def valid(value, expected):
        if expected is str:
            return isinstance(value, str) and bool(value.strip())
        return isinstance(value, list) and all(valid(item, str) for item in value)

    result = {}
    for name, fields in COORDINATION_FIELDS.items():
        if name not in state:
            continue
        value = state[name]
        if not isinstance(value, dict) or any(
                not valid(value.get(key), expected) for key, expected in fields.items()):
            raise ValueError(f"{name} requires nonempty text or text-list fields: "
                             + ", ".join(fields))
        result[name] = value
    if "declared_limits" in state:
        if not valid(state["declared_limits"], list):
            raise ValueError("declared_limits requires a text list of supplied limits and sources")
        result["declared_limits"] = state["declared_limits"]
    if "blocker_scope" in result:
        scope = result["blocker_scope"]
        if set(scope["blocks"]) & set(scope["does_not_block"]):
            raise ValueError("blocker_scope cannot declare the same scope blocked and independent")
    if "coordination_change" in result:
        change = result["coordination_change"]
        if (change["kind"] not in ("dependency_changed", "ownership_released")
                or change["before"] == change["after"]
                or not change["scope"] or not change["affected_assignments"]):
            raise ValueError("coordination_change requires a changed dependency/ownership boundary and affected consumers")
    return result


def handoff(row, state):
    """Render a terminal report without history or a second mutable snapshot."""
    status = state["status"]
    if status not in ("complete", "blocked", "needs_decision", "paused"):
        raise ValueError("Handoff requires complete, blocked, needs_decision or paused state")
    delegation = state.get("delegation")
    identifiers = ("assignment_id", "parent_work_id", "parent_plan_revision",
                   "child_session_id")
    if not isinstance(delegation, dict) or any(
            not isinstance(delegation.get(key), str) or not delegation[key].strip()
            for key in identifiers):
        raise ValueError("Handoff requires delegation: " + ", ".join(identifiers))
    if not state["plan_ref"].strip() or not state["context"].strip():
        raise ValueError("Handoff requires assignment plan_ref and source/environment context")
    coordination = coordination_fields(state)
    if status == "complete" and (
            row["kind"] != "complete" or not row["evidence"].strip()
            or state["pending_operations"]
            or state["blocker"].strip().casefold() not in ("", "none")
            or coordination.get("blocker_scope", {}).get("blocks")):
        raise ValueError("Complete handoff requires a complete event, evidence and no unresolved operations/blocker")
    if status in ("blocked", "needs_decision") and (
            state["blocker"].strip().casefold() in ("", "none")):
        raise ValueError("Blocked handoff requires a precise blocker")
    packet = {
        "delegation": {key: delegation[key] for key in identifiers},
        **{key: row[key] for key in
           ("work_id", "revision", "event_key", "summary", "evidence", "decision")},
        **{key: state[key] for key in
           ("status", "goal", "plan_ref", "plan_revision", "context", "done_when", "blocker",
            "next_action", "abandon_if", "avoid", "pending_operations",
            "active_no_progress_minutes")},
        **coordination,
    }
    output = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    if len((output + "\n").encode("utf-8")) > HANDOFF_LIMIT_BYTES:
        raise ValueError("Handoff exceeds 4096 UTF-8 bytes; persist concise evidence references, never truncate safety facts")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("action", choices=("init", "read", "append", "handoff"))
    parser.add_argument("--work")
    parser.add_argument("--event", type=Path, help="JSON file with all event fields")
    parser.add_argument("--recent", type=int, default=None,
                        help="read: include 0-6 recent events (default 6; 0 for snapshot only)")
    args = parser.parse_args()
    if not args.db.is_absolute():
        parser.error("--db must be an absolute path in the actual session files folder")
    if args.action in ("read", "handoff") and not args.work:
        parser.error(f"{args.action} requires --work")
    if args.action == "append" and not args.event:
        parser.error("append requires --event")
    if args.recent is not None and (
            args.action != "read" or not 0 <= args.recent <= 6):
        parser.error("--recent requires read and a value from 0 to 6")
    if args.action != "init" and not args.db.is_file():
        parser.error("Database missing; initialize explicitly first")
    os.umask(0o077)
    if args.action == "init":
        args.db.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.db, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        if args.action == "init":
            if db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                raise ValueError("Database already initialized; read it, do not overwrite")
            db.executescript("BEGIN;\n" + SCHEMA.read_text() +
                             "\nPRAGMA user_version=1;\nCOMMIT;")
            print(json.dumps({"initialized": str(args.db), "schema": 1}))
        elif args.action in ("read", "handoff"):
            row = db.execute(
                "SELECT * FROM progress_guard_current WHERE work_id=?", (args.work,)
            ).fetchone()
            if row is None:
                raise ValueError("No snapshot for work ID: " + args.work)
            result = dict(row)
            result["state"] = json.loads(result["state"])
            if args.action == "handoff":
                print(handoff(row, result["state"]))
                return
            recent = 6 if args.recent is None else args.recent
            if recent:
                result["recent_events"] = [dict(r) for r in db.execute(
                    "SELECT revision,kind,summary,evidence,decision "
                    "FROM progress_guard_events WHERE work_id=? "
                    "ORDER BY revision DESC LIMIT ?", (args.work, recent)
                )]
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            event = json.loads(args.event.read_text())
            if not isinstance(event, dict) or set(event) != set(FIELDS):
                raise ValueError("Event requires exactly: " + ", ".join(FIELDS))
            if not isinstance(event["state"], dict):
                raise ValueError("state must be a JSON object")
            coordination_fields(event["state"])
            event["state"] = json.dumps(event["state"], ensure_ascii=False)
            with db:
                db.execute(
                    f"INSERT INTO progress_guard_events ({','.join(FIELDS)}) "
                    f"VALUES ({','.join('?' for _ in FIELDS)})",
                    [event[f] for f in FIELDS],
                )
            print(json.dumps({"recorded": event["event_key"],
                              "revision": event["revision"]}))
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"progress-guard: {error}", file=sys.stderr)
        sys.exit(1)

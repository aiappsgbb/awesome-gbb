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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("action", choices=("init", "read", "append"))
    parser.add_argument("--work")
    parser.add_argument("--event", type=Path, help="JSON file with all event fields")
    parser.add_argument("--recent", type=int, default=None,
                        help="read: include 0-6 recent events (default 6; 0 for snapshot only)")
    args = parser.parse_args()
    if not args.db.is_absolute():
        parser.error("--db must be an absolute path in the actual session files folder")
    if args.action == "read" and not args.work:
        parser.error("read requires --work")
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
        elif args.action == "read":
            row = db.execute(
                "SELECT * FROM progress_guard_current WHERE work_id=?", (args.work,)
            ).fetchone()
            if row is None:
                raise ValueError("No snapshot for work ID: " + args.work)
            result = dict(row)
            result["state"] = json.loads(result["state"])
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

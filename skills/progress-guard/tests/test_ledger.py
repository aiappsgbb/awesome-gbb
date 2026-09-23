"""Persistence tests, not proof that an LLM obeys the skill."""
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "references" / "ledger.sql"


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(SCHEMA.read_text())

    def tearDown(self):
        self.db.close()

    def append(self, revision=1, kind="start", work="task-a", **changes):
        event = dict(
            work_id=work, revision=revision, event_key=f"{work}-{revision}",
            kind=kind, summary="Bounded work started", evidence="",
            decision="Run one discriminating test", state=json.dumps({
                "goal": "Fix the failing request", "done_when": "Targeted test passes",
                "plan_ref": "existing plan", "plan_revision": "1",
                "context": "commit-a; dev environment",
                "verified": [], "blocker": "403",
                "next_action": "Check authorization identity",
                "abandon_if": "Identity mismatch disproves the hypothesis",
                "avoid": [], "pending_operations": [], "status": "working",
                "active_no_progress_minutes": 0,
            }),
        )
        event.update(changes)
        columns = ",".join(event)
        self.db.execute(
            f"INSERT INTO progress_guard_events ({columns}) VALUES "
            f"({','.join('?' for _ in event)})", list(event.values())
        )
        return event

    def test_current_snapshot_and_history(self):
        self.append()
        self.append(2, "observation")
        self.assertEqual(self.db.execute(
            "SELECT revision FROM progress_guard_current").fetchone()[0], 2)
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM progress_guard_events").fetchone()[0], 2)

    def test_revision_rejects_stale_writer(self):
        self.append()
        with self.assertRaises(sqlite3.IntegrityError):
            self.append(1, event_key="different-writer")
        with self.assertRaises(sqlite3.IntegrityError):
            self.append(3)

    def test_event_key_prevents_duplicate_retry(self):
        self.append()
        with self.assertRaises(sqlite3.IntegrityError):
            self.append(2, event_key="task-a-1")

    def test_history_is_append_only(self):
        self.append()
        for statement in ("DELETE FROM progress_guard_events",
                          "UPDATE progress_guard_events SET summary='changed'"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(statement)

    def test_progress_requires_evidence(self):
        self.append()
        with self.assertRaises(sqlite3.IntegrityError):
            self.append(2, "progress")
        self.append(2, "progress", evidence="test-output.txt: test passes")
        self.assertEqual(self.db.execute(
            "SELECT last_progress_revision FROM progress_guard_current"
        ).fetchone()[0], 2)
        self.append(3, "plan_change")
        self.assertEqual(self.db.execute(
            "SELECT last_progress_revision FROM progress_guard_current"
        ).fetchone()[0], 2)

    def test_invalid_state_fails(self):
        for state in ("bad json", "{}", "[]"):
            with self.assertRaises((sqlite3.IntegrityError, sqlite3.OperationalError)):
                self.append(state=state)

    def test_work_items_are_independent(self):
        self.append()
        self.append(work="task-b")
        self.assertEqual(self.db.execute(
            "SELECT count(*) FROM progress_guard_current").fetchone()[0], 2)

    def test_fallback_roundtrip_and_stale_write(self):
        event = self.append()
        event["state"] = json.loads(event["state"])
        script = SCHEMA.parents[1] / "scripts" / "ledger.py"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = [sys.executable, str(script), "--db", str(root / "ledger.sqlite")]
            def run(*args):
                return subprocess.run(base + list(args), capture_output=True, text=True)
            self.assertEqual(run("init").returncode, 0)
            payload = root / "event.json"
            payload.write_text(json.dumps(event))
            self.assertEqual(run("append", "--event", str(payload)).returncode, 0)
            result = run("read", "--work", "task-a")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["state"]["goal"],
                             event["state"]["goal"])
            self.assertNotEqual(run("append", "--event", str(payload)).returncode, 0)
            self.assertEqual(json.loads(run("read", "--work", "task-a").stdout)["revision"], 1)
            self.assertNotEqual(run("init").returncode, 0)

    def test_fallback_missing_database_is_not_created_on_read(self):
        script = SCHEMA.parents[1] / "scripts" / "ledger.py"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.sqlite"
            result = subprocess.run(
                [sys.executable, str(script), "--db", str(path),
                 "read", "--work", "task-a"], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(path.exists())

    def test_snapshot_only_preserves_latest_state_without_old_events(self):
        event = self.append()
        state = json.loads(event["state"])
        state["avoid"] = [{"attempt": "same request", "retry_only_if": "role changes"}]
        state["pending_operations"] = [{"handle": "operation-a", "status": "unknown"}]
        state["context"] = "commit-b; user constraint: no new resources"
        event["state"] = state
        script = SCHEMA.parents[1] / "scripts" / "ledger.py"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = [sys.executable, str(script), "--db", str(root / "ledger.sqlite")]
            def run(*args):
                return subprocess.run(base + list(args), capture_output=True, text=True,
                                      timeout=10)
            self.assertEqual(run("init").returncode, 0)
            payload = root / "event.json"
            event["summary"] = "OLD_DETAIL_" * 1000
            payload.write_text(json.dumps(event))
            self.assertEqual(run("append", "--event", str(payload)).returncode, 0)
            event.update(revision=2, event_key="task-a-2", summary="Latest verified state")
            payload.write_text(json.dumps(event))
            self.assertEqual(run("append", "--event", str(payload)).returncode, 0)
            result = run("read", "--work", "task-a", "--recent", "0")
            self.assertEqual(result.returncode, 0, result.stderr)
            snapshot = json.loads(result.stdout)
            self.assertEqual(snapshot["revision"], 2)
            self.assertEqual(snapshot["state"], state)
            self.assertNotIn("recent_events", snapshot)
            self.assertNotIn("OLD_DETAIL_", result.stdout)
            full = run("read", "--work", "task-a")
            self.assertEqual(full.returncode, 0, full.stderr)
            self.assertEqual(len(json.loads(full.stdout)["recent_events"]), 2)
            self.assertLess(len(result.stdout), len(full.stdout) // 2)

    def test_recent_history_is_bounded_ordered_and_work_scoped(self):
        event = self.append()
        event["state"] = json.loads(event["state"])
        script = SCHEMA.parents[1] / "scripts" / "ledger.py"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = [sys.executable, str(script), "--db", str(root / "ledger.sqlite")]
            def run(*args):
                return subprocess.run(base + list(args), capture_output=True, text=True,
                                      timeout=10)
            self.assertEqual(run("init").returncode, 0)
            payload = root / "event.json"
            for revision in range(1, 9):
                event.update(revision=revision, event_key=f"task-a-{revision}")
                payload.write_text(json.dumps(event))
                self.assertEqual(run("append", "--event", str(payload)).returncode, 0)
            event.update(work_id="task-b", revision=1, event_key="task-b-1",
                         summary="Unrelated work")
            payload.write_text(json.dumps(event))
            self.assertEqual(run("append", "--event", str(payload)).returncode, 0)
            for flags, revisions in (([], [8, 7, 6, 5, 4, 3]),
                                     (["--recent", "2"], [8, 7])):
                result = run("read", "--work", "task-a", *flags)
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = json.loads(result.stdout)["recent_events"]
                self.assertEqual([row["revision"] for row in rows], revisions)
                self.assertNotIn("Unrelated work", result.stdout)

    def test_invalid_recent_arguments_do_not_create_database(self):
        script = SCHEMA.parents[1] / "scripts" / "ledger.py"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.sqlite"
            base = [sys.executable, str(script), "--db", str(path)]
            for args in (["init", "--recent", "0"],
                         ["append", "--event", "unused.json", "--recent", "0"],
                         ["read", "--work", "task-a", "--recent", "-1"],
                         ["read", "--work", "task-a", "--recent", "7"],
                         ["read", "--work", "task-a", "--recent", "bad"]):
                with self.subTest(args=args):
                    result = subprocess.run(base + args, capture_output=True, text=True,
                                            timeout=10)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("--recent", result.stderr)
                    self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

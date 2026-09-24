"""Mechanical reporting boundaries, not observed multi-agent behavior."""

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ledger.py"


class HandoffTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.db = self.root / "child.sqlite"
        self.assertEqual(self.run_cli("init").returncode, 0)
        self.state = {
            "goal": "Implement only the assigned parser",
            "done_when": "Parser regression passes on the delivered commit",
            "plan_ref": "assignment.txt: owned parser.py; no cloud or extra children",
            "plan_revision": "child-plan-1",
            "context": "commit-a; local environment",
            "verified": [{"result": "Parser passes", "evidence": "test-output.txt"}],
            "blocker": "none",
            "next_action": "Parent verifies and integrates commit-a",
            "abandon_if": "Do not retry without changed failing input",
            "avoid": [{"attempt": "retry unchanged input", "retry_only_if": "input changes"}],
            "pending_operations": [],
            "status": "complete",
            "active_no_progress_minutes": 7,
            "delegation": {
                "assignment_id": "parse-task-1",
                "parent_work_id": "parent-task",
                "parent_plan_revision": "parent-plan-2",
                "child_session_id": "child-session",
            },
        }

    def run_cli(self, *args, db=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(db or self.db), *args],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )

    def append(self, revision=1, kind="complete", summary="Parser completed"):
        event = {
            "work_id": "child-task", "revision": revision,
            "event_key": f"child-event-{revision}", "kind": kind,
            "summary": summary, "evidence": "commit-a:test-output.txt",
            "decision": "Stop after reporting; parent owns acceptance",
            "state": self.state,
        }
        path = self.root / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        result = self.run_cli("append", "--event", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)

    def report(self):
        return self.run_cli("handoff", "--work", "child-task")

    def test_complete_packet_is_stable_compact_and_read_only(self):
        self.append(summary="old history " * 2000)
        self.append(2)
        before = self.db.read_bytes()
        result = self.report()
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["revision"], 2)
        self.assertEqual(packet["event_key"], "child-event-2")
        self.assertEqual(packet["delegation"], self.state["delegation"])
        self.assertEqual(packet["goal"], self.state["goal"])
        self.assertEqual(packet["done_when"], self.state["done_when"])
        self.assertEqual(packet["avoid"], self.state["avoid"])
        self.assertEqual(packet["active_no_progress_minutes"], 7)
        self.assertNotIn("old history", result.stdout)
        self.assertNotIn("state", packet)
        self.assertNotIn("recent_events", packet)
        self.assertNotIn("verified", packet)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), 4096)
        self.assertEqual(self.report().stdout, result.stdout)
        self.assertEqual(before, self.db.read_bytes())

    def test_working_or_waiting_cannot_emit_progress_ping(self):
        self.append()
        for revision, status in enumerate(("working", "waiting"), start=2):
            self.state["status"] = status
            self.append(revision, kind="observation")
            result = self.report()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("Handoff requires", result.stderr)

    def test_blocked_decision_and_pause_preserve_unknown_operations(self):
        self.state["pending_operations"] = [
            {"handle": "operation-1", "status": "unknown", "lookup": "read operation-1"}
        ]
        self.state["blocker"] = "Need current operation disposition before retry"
        for revision, status in enumerate(("blocked", "needs_decision", "paused"), start=1):
            self.state["status"] = status
            self.append(revision, kind="handoff")
            result = self.report()
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)
            self.assertEqual(packet["status"], status)
            self.assertEqual(packet["blocker"], self.state["blocker"])
            self.assertEqual(packet["pending_operations"], self.state["pending_operations"])
            self.assertEqual(packet["abandon_if"], self.state["abandon_if"])

    def test_completion_cannot_hide_blocker_pending_operation_or_wrong_kind(self):
        for revision, (blocker, operations, kind) in enumerate((
            ("awaiting integration proof", [], "complete"),
            ("none", [{"handle": "job-1", "status": "running"}], "complete"),
            ("none", [], "observation"),
        ), start=1):
            self.state.update(blocker=blocker, pending_operations=operations)
            self.append(revision, kind=kind)
            result = self.report()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("Complete handoff requires", result.stderr)

    def test_blocked_state_requires_specific_blocker(self):
        self.state["status"] = "blocked"
        self.append(kind="blocked")
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("precise blocker", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_assignment_binding_fails_without_changing_ledger(self):
        binding = dict(self.state["delegation"])
        for revision, key in enumerate(binding, start=1):
            self.state["delegation"] = {k: v for k, v in binding.items() if k != key}
            self.append(revision)
            before = self.db.read_bytes()
            result = self.report()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Handoff requires delegation", result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(before, self.db.read_bytes())

    def test_byte_limit_is_exact_and_never_silently_truncates(self):
        self.append()
        baseline = self.report()
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        summary = "Parser completed"
        # Both revisions/event keys below have one digit, preserving packet overhead.
        remaining = 4096 - len(baseline.stdout.encode("utf-8"))
        self.append(2, summary=summary + "x" * remaining)
        exact = self.report()
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertEqual(len(exact.stdout.encode("utf-8")), 4096)
        self.append(3, summary=summary + "x" * (remaining - 1) + "\u00e9")
        before = self.db.read_bytes()
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("4096 UTF-8 bytes", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(before, self.db.read_bytes())
        stored = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertTrue(json.loads(stored.stdout)["summary"].endswith("\u00e9"))

    def test_invalid_cli_usage_and_missing_work_fail_without_creation(self):
        missing = self.root / "missing.sqlite"
        for args in (("handoff",), ("handoff", "--work", "x", "--recent", "0"),
                     ("handoff", "--work", "x")):
            result = self.run_cli(*args, db=missing)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertFalse(missing.exists())
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No snapshot", result.stderr)

    def test_parent_receipt_survives_readback_and_duplicate_delivery(self):
        self.append()
        packet = json.loads(self.report().stdout)
        parent_db = self.root / "parent.sqlite"
        self.assertEqual(self.run_cli("init", db=parent_db).returncode, 0)
        receipt = {
            "assignment_id": packet["delegation"]["assignment_id"],
            "handle": packet["delegation"]["child_session_id"],
            "parent_plan_revision": packet["delegation"]["parent_plan_revision"],
            "last_receipt": packet["event_key"],
            "revision": packet["revision"],
            "disposition": "reported",
            "evidence": packet["evidence"],
            "next_action": "Verify evidence before dependent work",
        }
        state = dict(self.state, status="working", children=[receipt],
                     plan_revision="parent-plan-2", goal="Integrate the parser",
                     next_action="Verify and integrate child result")
        state.pop("delegation")
        event = {
            "work_id": "parent-task", "revision": 1,
            "event_key": "receipt:parse-task-1:child-session:child-task:child-event-1",
            "kind": "observation", "summary": "Received result; not accepted",
            "evidence": packet["evidence"], "decision": "Verify before integration",
            "state": state,
        }
        path = self.root / "parent-event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        result = self.run_cli("append", "--event", str(path), db=parent_db)
        self.assertEqual(result.returncode, 0, result.stderr)
        event["revision"] = 2
        path.write_text(json.dumps(event), encoding="utf-8")
        duplicate = self.run_cli("append", "--event", str(path), db=parent_db)
        self.assertNotEqual(duplicate.returncode, 0)
        latest = self.run_cli("read", "--work", "parent-task", "--recent", "0", db=parent_db)
        snapshot = json.loads(latest.stdout)
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(snapshot["state"]["children"], [receipt])
        self.assertEqual(snapshot["state"]["status"], "working")
        with closing(sqlite3.connect(self.db)) as child:
            self.assertEqual(child.execute(
                "SELECT count(*) FROM progress_guard_events").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()

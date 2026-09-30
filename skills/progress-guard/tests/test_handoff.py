"""Mechanical reporting boundaries, not observed multi-agent behavior."""

import json
import copy
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
            "next_action": "Coordinator accepts evidence and assigns integration",
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

    def append(self, revision=1, kind="complete", summary="Parser completed",
               work="child-task", succeeds=True):
        event = {
            "work_id": work, "revision": revision,
            "event_key": f"{work}-event-{revision}", "kind": kind,
            "summary": summary, "evidence": "commit-a:test-output.txt",
            "decision": "Stop after reporting; parent owns acceptance",
            "state": self.state,
        }
        path = self.root / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        result = self.run_cli("append", "--event", str(path))
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
        return result

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
        self.assertEqual(packet["event_key"], "child-task-event-2")
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
        self.state["coordination_change"] = {
            "change_id": "schema-a-to-b", "kind": "dependency_changed",
            "scope": ["schema"], "before": "version-a", "after": "version-b",
            "affected_assignments": ["parser"],
        }
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
                     next_action="Review evidence and assign integration to executor")
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

    def test_optional_scope_preserves_outcomes_without_invented_limits(self):
        self.append()
        legacy = json.loads(self.report().stdout)
        self.assertNotIn("declared_limits", legacy)
        self.assertNotIn("assignment_scope", legacy)
        self.state["assignment_scope"] = {
            "outcome": "Parser passes",
            "overall_outcome": "Import flow usable; executor integration pending",
            "write_scope": ["parser.py"], "shared_capacity": ["shared build runner"],
            "depends_on": [], "ordinary_operations": ["edit", "test"],
            "escalate_if": ["new permission or external effect"],
        }
        self.state["declared_limits"] = ["user: no cloud writes"]
        self.append(2)
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["assignment_scope"], self.state["assignment_scope"])
        self.assertEqual(packet["declared_limits"], ["user: no cloud writes"])
        self.assertNotEqual(packet["assignment_scope"]["outcome"],
                            packet["assignment_scope"]["overall_outcome"])

    def test_recorded_blocked_sibling_does_not_gate_independent_work_items(self):
        ready = copy.deepcopy(self.state)
        self.state.update(status="blocked", blocker="Writer owns parser.py",
                          blocker_scope={"blocks": ["parser.py"],
                                         "does_not_block": ["docs.md", "ui.py"]})
        self.append(kind="blocked")
        blocked = json.loads(self.report().stdout)
        self.assertEqual(blocked["blocker_scope"]["blocks"], ["parser.py"])
        for work, target in (("docs", "docs.md"), ("ui", "ui.py")):
            self.state = copy.deepcopy(ready)
            self.state["delegation"].update(assignment_id=work, child_session_id=work)
            self.state["context"] = f"Independent owner; {target}"
            self.append(work=work)
            result = self.run_cli("handoff", "--work", work)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "complete")
        self.assertEqual(json.loads(self.report().stdout)["status"], "blocked")

    def test_recorded_same_target_conflict_cannot_be_reported_complete(self):
        self.state.update(
            status="blocked", blocker="Owner-a still writes parser.py; owner-b denied",
            blocker_scope={"blocks": ["parser.py"], "does_not_block": ["docs.md"]},
            pending_operations=[{"handle": "owner-a", "status": "running",
                                 "lookup": "verify release and target version"}],
        )
        self.append(kind="blocked")
        self.assertEqual(json.loads(self.report().stdout)["status"], "blocked")
        self.state.update(status="complete", blocker="none", pending_operations=[])
        self.append(2)
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Complete handoff requires", result.stderr)

    def test_terminal_change_evidence_roundtrip_duplicate_and_unchanged_rejected(self):
        change = {
            "change_id": "parser-owner-a-released-v2", "kind": "ownership_released",
            "scope": ["parser.py"], "before": "owner-a writing v1",
            "after": "owner-a released v2", "affected_assignments": ["owner-b"],
        }
        self.state["coordination_change"] = change
        self.append()
        before = self.db.read_bytes()
        packet = self.report()
        self.assertEqual(packet.stdout, self.report().stdout)
        self.assertEqual(json.loads(packet.stdout)["coordination_change"], change)
        self.assertEqual(self.db.read_bytes(), before)
        event = json.loads((self.root / "event.json").read_text())
        event["revision"] = 2
        (self.root / "event.json").write_text(json.dumps(event))
        duplicate = self.run_cli("append", "--event", str(self.root / "event.json"))
        self.assertNotEqual(duplicate.returncode, 0)
        self.state["coordination_change"]["after"] = change["before"]
        unchanged = self.append(2, succeeds=False)
        self.assertIn("coordination_change", unchanged.stderr)
        latest = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertEqual(json.loads(latest.stdout)["revision"], 1)

    def test_changed_input_preserves_only_affected_proof_delta(self):
        self.state["evidence_delta"] = {
            "reused": ["layout-proof@a: inputs unchanged"],
            "invalidated": ["parser-proof@b: schema changed to c"],
        }
        self.state["coordination_change"] = {
            "change_id": "schema-b-to-c", "kind": "dependency_changed",
            "scope": ["schema"], "before": "hash-b", "after": "hash-c",
            "affected_assignments": ["parser"],
        }
        self.append()
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["evidence_delta"], self.state["evidence_delta"])
        self.assertEqual(packet["coordination_change"]["affected_assignments"], ["parser"])
        self.assertNotIn("layout", packet["coordination_change"]["affected_assignments"])

    def test_recorded_effect_free_correction_retains_same_assignment(self):
        binding = copy.deepcopy(self.state["delegation"])
        self.state.update(status="working",
                          next_action="Correct local test path within same authority",
                          avoid=[{"attempt": "wrong local path",
                                  "evidence": "local pre-dispatch rejection; no effects",
                                  "retry_only_if": "one authorized corrected path"}])
        self.append(kind="recovery", summary="Effect-free local path defect")
        self.state.update(status="complete", next_action="Parent checks passing test")
        self.append(2)
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["delegation"], binding)
        self.assertEqual(packet["avoid"], self.state["avoid"])

    def test_unknown_handle_survives_reads_without_replay_or_boundary_loss(self):
        self.state.update(
            status="blocked", blocker="Mutation outcome unknown",
            pending_operations=[{"handle": "mutation-1", "status": "unknown",
                                 "lookup": "supported read of target"}],
            blocker_scope={"blocks": ["target and reconciliation inputs"],
                           "does_not_block": ["offline docs with separate owner"]},
        )
        self.append(kind="blocked")
        before = self.db.read_bytes()
        for _ in range(2):
            result = self.report()
            self.assertEqual(result.returncode, 0, result.stderr)
            packet = json.loads(result.stdout)
            self.assertEqual(packet["pending_operations"], self.state["pending_operations"])
            self.assertEqual(packet["blocker_scope"], self.state["blocker_scope"])
        self.assertEqual(before, self.db.read_bytes())

    def test_healthy_long_build_record_is_not_expired_by_helper(self):
        self.state.update(status="waiting", active_no_progress_minutes=0,
                          pending_operations=[{"handle": "build-1", "status": "running",
                                               "elapsed_minutes": 60,
                                               "evidence": "new compiled targets"}])
        self.append(kind="progress", summary="Healthy build still advancing")
        result = self.run_cli("read", "--work", "child-task", "--recent", "0")
        state = json.loads(result.stdout)["state"]
        self.assertEqual(state["status"], "waiting")
        self.assertEqual(state["pending_operations"], self.state["pending_operations"])
        self.assertNotIn("declared_limits", state)
        self.assertNotEqual(self.report().returncode, 0)
        after = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertEqual(result.stdout, after.stdout)

    def test_optional_field_errors_are_explicit_and_do_not_append(self):
        baseline = copy.deepcopy(self.state)
        bad_fields = (
            ("declared_limits", 30),
            ("declared_limits", [""]),
            ("assignment_scope", {"outcome": "incomplete shape"}),
            ("blocker_scope", {"blocks": ["same"], "does_not_block": ["same"]}),
            ("evidence_delta", {"reused": "not a list", "invalidated": []}),
            ("coordination_change", {"change_id": "c", "kind": "heartbeat",
                                     "scope": ["s"], "before": "a", "after": "b",
                                     "affected_assignments": ["x"]}),
        )
        for name, value in bad_fields:
            with self.subTest(field=name, value=value):
                self.state = dict(baseline, **{name: value})
                result = self.append(succeeds=False)
                self.assertIn(name, result.stderr)
                self.assertNotEqual(self.report().returncode, 0)
        self.state = dict(baseline, declared_limits=[])
        self.append()
        self.assertEqual(json.loads(self.report().stdout)["declared_limits"], [])

    def test_optional_fields_count_toward_output_cap_without_truncation(self):
        self.state.update(status="blocked", blocker="Unknown outcome", execution_role="executor",
                          blocker_scope={"blocks": ["target"],
                                         "does_not_block": ["docs"]},
                          evidence_delta={"reused": ["x" * 4096], "invalidated": []})
        self.append(kind="blocked")
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("4096 UTF-8 bytes", result.stderr)
        stored = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertEqual(json.loads(stored.stdout)["state"], self.state)

    def approval(self, **updates):
        return {
            "decision_id": "release-a", "operation": "publish",
            "target": "artifact-a@v1 to staging", "effect": "replace staging artifact",
            "mandate_ref": "user: publish artifact-a v1 end-to-end to staging",
            "request_ref": "same explicit user mandate; no extra question",
            "result": "authorized", "evidence": "user-message-a: explicit staging release",
            "reopen_if": "target, effect or current mandate materially changes",
            **updates,
        }

    def test_explicit_release_record_retains_source_without_new_question(self):
        self.state["approvals"] = [self.approval()]
        self.append()
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["approvals"], self.state["approvals"])
        self.assertEqual(packet["approvals"][0]["request_ref"],
                         "same explicit user mandate; no extra question")
        self.assertNotIn("permission_granted", packet)

    def test_review_only_and_new_permission_remain_scoped_blocks(self):
        for revision, reason in enumerate(("review-only mandate", "new production effect"), 1):
            self.state.update(
                status="needs_decision", blocker=reason,
                blocker_scope={"blocks": ["publish"], "does_not_block": ["review"]},
                approvals=[self.approval(result="pending", mandate_ref=reason,
                                         request_ref="request: permit named publication?",
                                         evidence="request outstanding; no answer")],
            )
            self.append(revision, kind="observation")
            packet = json.loads(self.report().stdout)
            self.assertEqual(packet["status"], "needs_decision")
            self.assertEqual(packet["approvals"][0]["result"], "pending")
            self.assertEqual(packet["blocker_scope"]["does_not_block"], ["review"])

    def test_unavailable_reply_survives_snapshot_recovery_without_reasking(self):
        self.state.update(
            status="needs_decision", blocker="No reply to staging publication request",
            approvals=[self.approval(result="unavailable",
                                     request_ref="request-a", evidence="request-a unavailable")],
        )
        self.append(kind="observation")
        before = self.db.read_bytes()
        for _ in range(2):
            recovered = self.run_cli("read", "--work", "child-task", "--recent", "0")
            state = json.loads(recovered.stdout)["state"]
            self.assertEqual(state["approvals"], self.state["approvals"])
            self.assertEqual(json.loads(self.report().stdout)["approvals"], state["approvals"])
        self.assertEqual(before, self.db.read_bytes())
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM progress_guard_events").fetchone()[0], 1)

    def test_paraphrase_is_duplicate_scope_but_identical_words_can_target_another_release(self):
        first = self.approval()
        self.state["approvals"] = [first, self.approval(
            decision_id="another-id", request_ref="paraphrased request, same scope")]
        self.assertIn("unique", self.append(succeeds=False).stderr)
        self.state["approvals"] = [first, self.approval(
            decision_id="release-b", target="artifact-b@v2 to staging",
            result="pending", evidence="no authorization for increment-b")]
        self.append()
        packet = json.loads(self.report().stdout)
        self.assertEqual(len(packet["approvals"]), 2)
        self.assertEqual(packet["approvals"][1]["result"], "pending")

    def test_revocation_narrowing_and_new_effect_preserve_unaffected_authority_and_history(self):
        first = self.approval()
        independent = self.approval(decision_id="review-b", operation="review",
                                    target="artifact-b@v2", effect="read-only",
                                    mandate_ref="user: review b", evidence="user-message-b")
        self.state["approvals"] = [first, independent]
        self.append()
        self.state.update(
            status="blocked", blocker="User narrowed release scope",
            blocker_scope={"blocks": ["publish-a"], "does_not_block": ["review-b"]},
            approvals=[self.approval(result="revoked", evidence="user-message-c: review only now"),
                       independent,
                       self.approval(decision_id="new-effect", effect="publish to production",
                                     result="pending", evidence="new effect not in mandate")],
        )
        self.append(2, kind="correction")
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["approvals"][1], independent)
        self.assertEqual(packet["approvals"][0]["result"], "revoked")
        with closing(sqlite3.connect(self.db)) as db:
            old = json.loads(db.execute(
                "SELECT state FROM progress_guard_events WHERE revision=1").fetchone()[0])
            self.assertEqual(old["approvals"][0], first)

    def test_authorized_record_cannot_clear_unknown_operation(self):
        self.state.update(approvals=[self.approval()],
                          pending_operations=[{"handle": "publish-a", "status": "unknown",
                                               "lookup": "read target before any replay"}])
        self.append()
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("Complete handoff requires", result.stderr)
        recovered = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertEqual(json.loads(recovered.stdout)["state"]["pending_operations"],
                         self.state["pending_operations"])

    def test_approval_shapes_results_and_ids_fail_explicitly(self):
        baseline = copy.deepcopy(self.state)
        bad = [
            "authorized",
            [self.approval(result="assumed")],
            [self.approval(evidence="")],
            [self.approval(), self.approval(target="different-target")],
        ]
        for value in bad:
            self.state = dict(baseline, approvals=value)
            self.assertIn("approvals", self.append(succeeds=False).stderr)
        self.state = dict(baseline, approvals=[])
        self.append()
        self.assertEqual(json.loads(self.report().stdout)["approvals"], [])
        self.state = baseline
        self.append(2)
        self.assertNotIn("approvals", json.loads(self.report().stdout))

    def test_approval_records_cannot_evade_terminal_byte_cap(self):
        self.state["approvals"] = [self.approval(evidence="x" * 4096)]
        self.append()
        result = self.report()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("4096 UTF-8 bytes", result.stderr)
        recovered = self.run_cli("read", "--work", "child-task", "--recent", "0")
        self.assertEqual(json.loads(recovered.stdout)["state"]["approvals"],
                         self.state["approvals"])

    def test_role_survives_snapshot_recovery_and_terminal_output_without_schema_change(self):
        self.append()
        self.assertNotIn("execution_role", json.loads(self.report().stdout))
        for revision, role in enumerate(("executor", "coordinator"), 2):
            self.state["execution_role"] = role
            self.append(revision)
            recovered = self.run_cli("read", "--work", "child-task", "--recent", "0")
            self.assertEqual(json.loads(recovered.stdout)["state"]["execution_role"], role)
            self.assertEqual(json.loads(self.report().stdout)["execution_role"], role)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
            original = json.loads(db.execute(
                "SELECT state FROM progress_guard_events WHERE revision=1").fetchone()[0])
            self.assertNotIn("execution_role", original)

    def test_invalid_role_fails_without_changing_existing_snapshot(self):
        self.append()
        before = self.db.read_bytes()
        for role in ("both", "", None, [], {"role": "executor"}):
            self.state["execution_role"] = role
            self.assertIn("execution_role", self.append(2, succeeds=False).stderr)
            self.assertEqual(self.db.read_bytes(), before)

    def test_scripted_block_resolution_resume_and_new_terminal_revision(self):
        self.state.update(
            execution_role="executor", status="blocked",
            blocker="Schema owner has not released version-b",
            next_action="Coordinator obtains schema release then explicitly resumes",
        )
        self.append(kind="blocked")
        first = json.loads(self.report().stdout)
        before = self.db.read_bytes()
        self.assertEqual(first, json.loads(self.report().stdout))
        self.assertEqual(self.db.read_bytes(), before)
        parent_db = self.root / "parent.sqlite"
        self.assertEqual(self.run_cli("init", db=parent_db).returncode, 0)
        parent_state = dict(self.state, execution_role="coordinator", status="working",
                            blocker="none", next_action="Resume same parser executor on version-b",
                            children=[{"assignment_id": first["delegation"]["assignment_id"],
                                       "last_receipt": first["event_key"], "revision": 1,
                                       "disposition": "blocked",
                                       "evidence": "schema-owner terminal release version-b"}])
        parent_state.pop("delegation")
        event = {
            "work_id": "parent-task", "revision": 1, "event_key": "accept-block-and-resume",
            "kind": "observation", "summary": "Block reconciled; resume assigned executor",
            "evidence": "schema-owner release version-b",
            "decision": "Resume parse-task-1; no new phase approval", "state": parent_state,
        }
        path = self.root / "parent-event.json"
        path.write_text(json.dumps(event))
        result = self.run_cli("append", "--event", str(path), db=parent_db)
        self.assertEqual(result.returncode, 0, result.stderr)
        recovered = self.run_cli("read", "--work", "parent-task", "--recent", "0", db=parent_db)
        self.assertEqual(json.loads(recovered.stdout)["state"], parent_state)
        self.state.update(status="working", blocker="none",
                          next_action="Execute remainder on released version-b")
        self.append(2, kind="recovery", summary="Parent explicitly resumed after schema release")
        self.assertNotEqual(self.report().returncode, 0)
        self.state.update(status="complete", next_action="Coordinator accepts final evidence")
        self.append(3)
        final = json.loads(self.report().stdout)
        self.assertEqual(first["delegation"], final["delegation"])
        self.assertEqual((first["revision"], final["revision"]), (1, 3))
        self.assertNotEqual(first["event_key"], final["event_key"])
        self.assertEqual(json.loads(self.run_cli(
            "read", "--work", "parent-task", "--recent", "0", db=parent_db
        ).stdout)["state"]["children"][0]["revision"], 1)

    def test_failed_execution_keeps_compatible_blocked_status_and_failure_evidence(self):
        self.state.update(
            execution_role="executor", status="blocked",
            blocker="Failed: recovery exhausted; assertion still fails",
            next_action="Coordinator records failed disposition and decides next action",
            avoid=[{"attempt": "same parser input", "evidence": "assertion failure twice",
                    "retry_only_if": "new input evidence or changed implementation mandate"}],
        )
        self.append(kind="blocked", summary="Failed after authorized recovery; no unsafe retry")
        packet = json.loads(self.report().stdout)
        self.assertEqual(packet["status"], "blocked")
        self.assertIn("Failed", packet["summary"])
        self.assertEqual(packet["avoid"], self.state["avoid"])
        self.assertTrue(packet["evidence"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs control record models.

Written as `unittest.TestCase` because the repo test harness uses unittest
discovery.
"""

from __future__ import annotations

import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from app import to_mcp_task  # noqa: E402
from app.models import (  # noqa: E402
    CallbackDeliveryState,
    LifecycleState,
    PublicError,
    StartRequest,
    TaskRecord,
    map_aca_state,
)


class FoundryMcpAcaJobsModelTests(unittest.TestCase):
    def test_enum_contracts(self) -> None:
        self.assertEqual([state.name for state in LifecycleState], [
            "ACCEPTED",
            "STARTING",
            "RUNNING",
            "SUCCEEDED",
            "FAILED",
            "CANCELLED",
        ])
        self.assertEqual([state.value for state in LifecycleState], [
            "Accepted",
            "Starting",
            "Running",
            "Succeeded",
            "Failed",
            "Cancelled",
        ])
        self.assertEqual([state.name for state in CallbackDeliveryState], [
            "NOT_STARTED",
            "PENDING",
            "DELIVERED",
            "EXHAUSTED",
        ])
        self.assertEqual([state.value for state in CallbackDeliveryState], [
            "NotStarted",
            "Pending",
            "Delivered",
            "Exhausted",
        ])

    def test_public_error_carries_stable_code_and_safe_message(self) -> None:
        error = PublicError("ACA_EXECUTION_FAILED", "the task failed")
        self.assertEqual(error.code, "ACA_EXECUTION_FAILED")
        self.assertEqual(error.safe_message, "the task failed")
        self.assertEqual(str(error), "the task failed")

    def test_start_request_supports_aliases_and_https_only_input_ref(self) -> None:
        request = StartRequest(
            jobType="reindex",
            idempotencyKey="abc123",
            inputRef="https://example.invalid/input.json",
            callbackAlias="callback://jobs/reindex",
        )
        self.assertEqual(request.job_type, "reindex")
        self.assertEqual(request.idempotency_key, "abc123")
        self.assertEqual(str(request.input_ref), "https://example.invalid/input.json")
        self.assertEqual(request.callback_alias, "callback://jobs/reindex")
        dumped = request.model_dump(by_alias=True)
        self.assertIn("jobType", dumped)
        self.assertIn("idempotencyKey", dumped)
        self.assertIn("inputRef", dumped)
        self.assertIn("callbackAlias", dumped)
        self.assertEqual(dumped["jobType"], "reindex")
        self.assertEqual(dumped["idempotencyKey"], "abc123")

    def test_start_request_requires_callback_alias(self) -> None:
        with self.assertRaises(ValidationError):
            StartRequest(jobType="reindex", idempotencyKey="abc123", inputRef="https://example.invalid/input.json")

    def test_start_request_rejects_non_https_and_long_idempotency_key(self) -> None:
        with self.assertRaises(ValidationError):
            StartRequest(
                jobType="reindex",
                idempotencyKey="",
                inputRef="https://example.invalid/input.json",
                callbackAlias="ops",
            )
        with self.assertRaises(ValidationError):
            StartRequest(
                jobType="reindex",
                idempotencyKey="x" * 201,
                inputRef="https://example.invalid/input.json",
                callbackAlias="ops",
            )
        with self.assertRaises(ValidationError):
            StartRequest(
                jobType="reindex",
                idempotencyKey="abc123",
                inputRef="http://example.invalid/input.json",
                callbackAlias="ops",
            )

    def test_task_record_requires_callback_alias(self) -> None:
        with self.assertRaises(ValidationError):
            TaskRecord.model_validate(
                {
                    "taskId": str(uuid.uuid4()),
                    "ownerScope": "scope-a",
                    "jobType": "import",
                    "idempotencyKeyHash": "hash-1",
                    "requestFingerprint": "fingerprint-1",
                    "inputRef": "https://example.invalid/input.json",
                    "lifecycleState": "Accepted",
                    "callbackDeliveryState": "NotStarted",
                    "createdAt": "2026-01-02T03:04:05Z",
                    "updatedAt": "2026-01-02T03:04:05Z",
                }
            )

    def test_task_record_new_requires_callback_alias(self) -> None:
        with self.assertRaises(TypeError):
            TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
            )

    def test_task_record_new_is_deterministic_and_uses_utc_z_timestamps(self) -> None:
        fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with patch("app.models._utcnow", return_value=fixed):
            first = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )
            second = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )

        expected_task_id = uuid.uuid5(uuid.NAMESPACE_URL, "scope-a:import:hash-1")
        self.assertEqual(first.task_id, expected_task_id)
        self.assertEqual(second.task_id, expected_task_id)
        self.assertEqual(first.created_at, fixed)
        self.assertEqual(first.updated_at, fixed)
        self.assertEqual(first.created_at.tzinfo, timezone.utc)
        self.assertEqual(first.model_dump(mode="json", by_alias=True)["createdAt"], "2026-01-02T03:04:05Z")
        self.assertEqual(first.model_dump(mode="json", by_alias=True)["updatedAt"], "2026-01-02T03:04:05Z")

    def test_task_record_accepts_camel_case_aliases_and_etag(self) -> None:
        record = TaskRecord.model_validate(
            {
                "taskId": str(uuid.uuid4()),
                "ownerScope": "scope-a",
                "jobType": "import",
                "idempotencyKeyHash": "hash-1",
                "requestFingerprint": "fingerprint-1",
                "inputRef": "https://example.invalid/input.json",
                "callbackAlias": "callback://jobs/import",
                "lifecycleState": "Accepted",
                "callbackDeliveryState": "NotStarted",
                "createdAt": "2026-01-02T03:04:05Z",
                "updatedAt": "2026-01-02T03:04:05Z",
                "_etag": "etag-1",
            }
        )
        self.assertEqual(record.owner_scope, "scope-a")
        self.assertEqual(record.lifecycle_state, LifecycleState.ACCEPTED)
        self.assertEqual(record.callback_delivery_state, CallbackDeliveryState.NOT_STARTED)
        self.assertEqual(record.etag, "etag-1")
        dumped = record.model_dump(by_alias=True)
        self.assertIn("_etag", dumped)
        self.assertEqual(dumped["_etag"], "etag-1")

    def test_map_aca_state_honors_processing_running_and_succeeded_rules(self) -> None:
        with patch("app.models._utcnow", return_value=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)):
            record = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )

        self.assertEqual(map_aca_state(record, "Processing").lifecycle_state, LifecycleState.STARTING)

        claimed = record.model_copy(update={"worker_claimed_at": datetime(2026, 1, 2, 4, 0, 0, tzinfo=timezone.utc)})
        self.assertEqual(map_aca_state(claimed, "Processing").lifecycle_state, LifecycleState.RUNNING)
        self.assertEqual(map_aca_state(record, "Succeeded").lifecycle_state, LifecycleState.RUNNING)

        completed = map_aca_state(record, "Succeeded", result_url="https://example.invalid/result.json")
        self.assertEqual(completed.lifecycle_state, LifecycleState.SUCCEEDED)
        self.assertEqual(str(completed.result_url), "https://example.invalid/result.json")

        exhausted = map_aca_state(record, "Succeeded", reconciliation_exhausted=True)
        self.assertEqual(exhausted.lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(exhausted.error_code, "RESULT_REFERENCE_MISSING")

        succeeded_terminal = record.model_copy(
            update={
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": None,
            }
        )
        self.assertEqual(
            map_aca_state(succeeded_terminal, "Degraded", reconciliation_exhausted=True).lifecycle_state,
            LifecycleState.SUCCEEDED,
        )

        failed_terminal = record.model_copy(update={"lifecycle_state": LifecycleState.FAILED, "error_code": "BUSINESS_FAIL"})
        self.assertEqual(
            map_aca_state(failed_terminal, "Unknown", reconciliation_exhausted=True).lifecycle_state,
            LifecycleState.FAILED,
        )

    def test_map_aca_state_handles_failed_stopped_degraded_and_unknown(self) -> None:
        with patch("app.models._utcnow", return_value=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)):
            record = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )

        failed = map_aca_state(record, "Failed")
        self.assertEqual(failed.lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(failed.error_code, "ACA_EXECUTION_FAILED")

        existing_error = record.model_copy(update={"error_code": "CUSTOM_ERROR"})
        failed_existing = map_aca_state(existing_error, "Failed")
        self.assertEqual(failed_existing.error_code, "CUSTOM_ERROR")

        stopped = map_aca_state(record, "Stopped")
        self.assertEqual(stopped.lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(stopped.error_code, "ACA_EXECUTION_STOPPED")

        cancelled = map_aca_state(
            record.model_copy(update={"cancellation_requested_at": datetime(2026, 1, 2, 4, 0, 0, tzinfo=timezone.utc)}),
            "Stopped",
        )
        self.assertEqual(cancelled.lifecycle_state, LifecycleState.CANCELLED)
        self.assertIsNone(cancelled.error_code)

        running = record.model_copy(update={"lifecycle_state": LifecycleState.RUNNING})
        self.assertEqual(map_aca_state(running, "Degraded").lifecycle_state, LifecycleState.RUNNING)
        self.assertEqual(map_aca_state(running, "Unknown").lifecycle_state, LifecycleState.RUNNING)
        self.assertEqual(map_aca_state(running, "Degraded", reconciliation_exhausted=True).lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(
            map_aca_state(running, "Degraded", reconciliation_exhausted=True).error_code,
            "ACA_EXECUTION_STATE_UNRESOLVED",
        )
        self.assertEqual(map_aca_state(running, "Unknown", reconciliation_exhausted=True).lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(
            map_aca_state(running, "Unknown", reconciliation_exhausted=True).error_code,
            "ACA_EXECUTION_STATE_UNRESOLVED",
        )
        starting = record.model_copy(update={"lifecycle_state": LifecycleState.STARTING})
        accepted = record.model_copy(update={"lifecycle_state": LifecycleState.ACCEPTED})
        self.assertEqual(map_aca_state(starting, "Degraded").lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(map_aca_state(starting, "Unknown").lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(map_aca_state(accepted, "Degraded").lifecycle_state, LifecycleState.ACCEPTED)
        self.assertEqual(map_aca_state(accepted, "Unknown").lifecycle_state, LifecycleState.ACCEPTED)

        cancelled_terminal = record.model_copy(
            update={
                "lifecycle_state": LifecycleState.CANCELLED,
                "cancellation_requested_at": datetime(2026, 1, 2, 4, 0, 0, tzinfo=timezone.utc),
            }
        )
        self.assertEqual(
            map_aca_state(cancelled_terminal, "Unknown", reconciliation_exhausted=True).lifecycle_state,
            LifecycleState.CANCELLED,
        )

    def test_to_mcp_task_semantics(self) -> None:
        from fastmcp_tasks.models import GetTaskResult  # noqa: E402

        with patch("app.models._utcnow", return_value=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)):
            record = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )

        working = record.model_copy(update={"lifecycle_state": LifecycleState.RUNNING})
        working_task = to_mcp_task(working)
        self.assertIsInstance(working_task, GetTaskResult)
        self.assertEqual(working_task.status, "working")

        succeeded = record.model_copy(
            update={
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": "https://example.invalid/result.json",
            }
        )
        succeeded_task = to_mcp_task(succeeded)
        self.assertEqual(succeeded_task.status, "completed")
        self.assertEqual(succeeded_task.result["content"][0]["text"], "https://example.invalid/result.json")
        self.assertEqual(
            succeeded_task.result["structuredContent"],
            {"status": "Succeeded", "resultUrl": "https://example.invalid/result.json"},
        )
        self.assertFalse(succeeded_task.result["isError"])

        cancelled = record.model_copy(update={"lifecycle_state": LifecycleState.CANCELLED})
        cancelled_task = to_mcp_task(cancelled)
        self.assertEqual(cancelled_task.status, "cancelled")

        business_failed = record.model_copy(
            update={
                "lifecycle_state": LifecycleState.FAILED,
                "error_code": "ACA_EXECUTION_FAILED",
            }
        )
        business_failed_task = to_mcp_task(business_failed)
        self.assertEqual(business_failed_task.status, "completed")
        self.assertEqual(business_failed_task.result["content"][0]["text"], "ACA_EXECUTION_FAILED")
        self.assertTrue(business_failed_task.result["isError"])
        self.assertNotEqual(getattr(business_failed_task, "status", None), "failed")


if __name__ == "__main__":
    unittest.main()

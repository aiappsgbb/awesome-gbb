#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs control store."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from azure.core import MatchConditions
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

FASTMCP_TASKS_STUBBED = False
try:  # pragma: no cover - exercised only when the real dependency exists locally.
    from fastmcp_tasks.models import GetTaskResult  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local test shim only.
    FASTMCP_TASKS_STUBBED = True

    class _StubGetTaskResult(BaseModel):
        model_config = ConfigDict(populate_by_name=True, extra="forbid", strict=True)

        task_id: str = Field(serialization_alias="taskId", min_length=1)
        status: str
        created_at: str = Field(serialization_alias="createdAt", min_length=1)
        last_updated_at: str = Field(serialization_alias="lastUpdatedAt", min_length=1)
        ttl_ms: int | None = Field(default=None, serialization_alias="ttlMs")
        poll_interval_ms: int | None = Field(default=None, serialization_alias="pollIntervalMs")
        result: dict[str, object] | None = None
        error: dict[str, object] | None = None
        status_message: str | None = Field(default=None, serialization_alias="statusMessage")
        result_type: str = Field(default="complete", serialization_alias="resultType")

    fastmcp_tasks = types.ModuleType("fastmcp_tasks")
    fastmcp_tasks.__path__ = []  # type: ignore[attr-defined]
    fastmcp_tasks_models = types.ModuleType("fastmcp_tasks.models")
    fastmcp_tasks_models.GetTaskResult = _StubGetTaskResult
    fastmcp_tasks.models = fastmcp_tasks_models
    sys.modules["fastmcp_tasks"] = fastmcp_tasks
    sys.modules["fastmcp_tasks.models"] = fastmcp_tasks_models
    from fastmcp_tasks.models import GetTaskResult  # type: ignore  # noqa: E402

from app.models import CallbackDeliveryState, LifecycleState, PublicError, TaskRecord  # noqa: E402
from app.control_store import (  # noqa: E402
    ConcurrencyError,
    CosmosControlStore,
    InMemoryControlStore,
    InvalidTransition,
    _record_from_document,
)


class _CosmosError(Exception):
    def __init__(self, status_code: int, message: str = "boom", body: object | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class _ContainerProxy:
    def __init__(self) -> None:
        self.create_item = AsyncMock()
        self.read_item = AsyncMock()
        self.replace_item = AsyncMock()
        self.query_items = AsyncMock()


class FoundryMcpAcaJobsStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with patch("app.models._utcnow", return_value=fixed):
            self.task = TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://example.invalid/input.json",
                callback_alias="callback://jobs/import",
            )

    def _task_document(self, task: TaskRecord) -> dict[str, object]:
        document = task.model_dump(mode="json", by_alias=True, exclude_none=True)
        document["id"] = str(task.task_id)
        return document

    def _cosmos_document(self, task: TaskRecord, *, etag: str | None = None) -> dict[str, object]:
        document = self._task_document(task)
        document.update(
            {
                "_rid": "rid-1",
                "_self": "dbs/db1/colls/tasks/docs/1",
                "_attachments": "attachments/",
                "_ts": 1735787045,
            }
        )
        if etag is not None:
            document["_etag"] = etag
        return document

    async def test_in_memory_duplicate_conflict_etags_and_owner_isolation(self) -> None:
        store = InMemoryControlStore()

        first = await store.create_or_get(self.task)
        duplicate = await store.create_or_get(self.task.model_copy())

        self.assertEqual(first.task_id, duplicate.task_id)
        self.assertEqual(first.etag, "1")
        self.assertEqual(duplicate.etag, "1")

        changed = self.task.model_copy(update={"request_fingerprint": "fingerprint-2"})
        with self.assertRaises(PublicError) as error:
            await store.create_or_get(changed)
        self.assertEqual(error.exception.code, "IDEMPOTENCY_KEY_REUSED")

        with self.assertRaises(PublicError) as error:
            await store.get("scope-b", str(self.task.task_id))
        self.assertEqual(error.exception.code, "TASK_NOT_FOUND")

        fetched = await store.get(self.task.owner_scope, str(self.task.task_id))
        fetched.callback_error_code = "mutated"
        again = await store.get(self.task.owner_scope, str(self.task.task_id))
        self.assertIsNone(again.callback_error_code)

    async def test_in_memory_monotonicity_etags_and_terminal_callback_updates(self) -> None:
        store = InMemoryControlStore()
        current = await store.create_or_get(self.task)

        starting = current.model_copy(update={"lifecycle_state": LifecycleState.STARTING})
        started = await store.replace(starting, current.etag)
        self.assertEqual(started.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(started.etag, "2")

        running = started.model_copy(update={"lifecycle_state": LifecycleState.RUNNING})
        running_saved = await store.replace(running, started.etag)
        self.assertEqual(running_saved.lifecycle_state, LifecycleState.RUNNING)
        self.assertEqual(running_saved.etag, "3")

        succeeded = running_saved.model_copy(
            update={
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": self.task.input_ref,
            }
        )
        terminal = await store.replace(succeeded, running_saved.etag)
        self.assertEqual(terminal.lifecycle_state, LifecycleState.SUCCEEDED)
        self.assertEqual(terminal.etag, "4")

        callback_update = terminal.model_copy(
            update={
                "callback_delivery_state": CallbackDeliveryState.DELIVERED,
                "callback_error_code": "CALLBACK_DELIVERED",
            }
        )
        callback_saved = await store.replace(callback_update, terminal.etag)
        self.assertEqual(callback_saved.lifecycle_state, LifecycleState.SUCCEEDED)
        self.assertEqual(callback_saved.callback_delivery_state, CallbackDeliveryState.DELIVERED)
        self.assertEqual(callback_saved.callback_error_code, "CALLBACK_DELIVERED")
        self.assertEqual(callback_saved.etag, "5")

        stale = running_saved.model_copy(update={"etag": "3"})
        with self.assertRaises(ConcurrencyError):
            await store.replace(stale, "3")

        with self.assertRaises(InvalidTransition):
            await store.replace(terminal.model_copy(update={"lifecycle_state": LifecycleState.ACCEPTED}), callback_saved.etag)

    async def test_in_memory_replace_revalidates_full_record_before_accepting_model_copy_mutations(self) -> None:
        store = InMemoryControlStore()
        current = await store.create_or_get(self.task)
        starting = await store.replace(current.model_copy(update={"lifecycle_state": LifecycleState.STARTING}), current.etag)
        running = await store.replace(starting.model_copy(update={"lifecycle_state": LifecycleState.RUNNING}), starting.etag)
        succeeded = await store.replace(
            running.model_copy(
                update={
                    "lifecycle_state": LifecycleState.SUCCEEDED,
                    "result_url": self.task.input_ref,
                }
            ),
            running.etag,
        )

        invalid = succeeded.model_copy(update={"result_url": None})
        with self.assertRaises(InvalidTransition):
            await store.replace(invalid, succeeded.etag)

    async def test_list_reconcilable_filters_and_deep_copies_in_memory(self) -> None:
        store = InMemoryControlStore()
        accepted = self.task.model_copy(update={"etag": "1"})
        starting = self.task.model_copy(
            update={"task_id": uuid.uuid4(), "lifecycle_state": LifecycleState.STARTING, "etag": "2"}
        )
        running = self.task.model_copy(
            update={"task_id": uuid.uuid4(), "lifecycle_state": LifecycleState.RUNNING, "etag": "3"}
        )
        succeeded_pending = self.task.model_copy(
            update={
                "task_id": uuid.uuid4(),
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": self.task.input_ref,
                "callback_delivery_state": CallbackDeliveryState.PENDING,
                "aca_execution_id": None,
                "etag": "4",
            }
        )
        finished = self.task.model_copy(
            update={
                "task_id": uuid.uuid4(),
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": self.task.input_ref,
                "callback_delivery_state": CallbackDeliveryState.DELIVERED,
                "etag": "5",
            }
        )
        store._records = {
            (accepted.owner_scope, str(accepted.task_id)): accepted,
            (starting.owner_scope, str(starting.task_id)): starting,
            (running.owner_scope, str(running.task_id)): running,
            (succeeded_pending.owner_scope, str(succeeded_pending.task_id)): succeeded_pending,
            (finished.owner_scope, str(finished.task_id)): finished,
        }

        reconcilable = await store.list_reconcilable()
        ids = {str(record.task_id) for record in reconcilable}
        expected_ids = {
            str(accepted.task_id),
            str(starting.task_id),
            str(running.task_id),
            str(succeeded_pending.task_id),
        }
        self.assertEqual(ids, expected_ids)

        reconcilable_by_id = {str(record.task_id): record for record in reconcilable}
        reconcilable_by_id[str(accepted.task_id)].callback_alias = "mutated"
        again = await store.list_reconcilable()
        again_by_id = {str(record.task_id): record for record in again}
        self.assertEqual(again_by_id[str(accepted.task_id)].callback_alias, accepted.callback_alias)
        self.assertNotIn(str(finished.task_id), ids)

    async def test_cosmos_list_reconcilable_uses_safe_query_without_cross_partition_flag(self) -> None:
        container = _ContainerProxy()
        store = CosmosControlStore(container)
        accepted = self._cosmos_document(self.task, etag="7")
        starting = self._cosmos_document(
            self.task.model_copy(update={"task_id": uuid.uuid4(), "lifecycle_state": LifecycleState.STARTING}),
            etag="8",
        )
        running = self._cosmos_document(
            self.task.model_copy(update={"task_id": uuid.uuid4(), "lifecycle_state": LifecycleState.RUNNING}),
            etag="9",
        )
        container.query_items.return_value = [accepted, starting, running]

        reconcilable = await store.list_reconcilable()

        self.assertEqual(
            {str(record.task_id) for record in reconcilable},
            {str(self.task.task_id), str(starting["taskId"]), str(running["taskId"])},
        )
        container.query_items.assert_awaited_once()
        self.assertIn("c.lifecycleState IN ('Accepted', 'Starting', 'Running')", container.query_items.await_args.kwargs["query"])
        self.assertNotIn("enable_cross_partition_query", container.query_items.await_args.kwargs)

    async def test_cosmos_create_get_replace_translate_statuses_and_use_expected_calls(self) -> None:
        container = _ContainerProxy()
        store = CosmosControlStore(container)

        create_body = self._task_document(self.task)
        existing = self._cosmos_document(self.task, etag="7")
        created = self._cosmos_document(self.task, etag="7")
        updated = self._cosmos_document(self.task.model_copy(update={"callback_delivery_state": CallbackDeliveryState.DELIVERED}), etag="10")

        container.create_item.side_effect = _CosmosError(409, "conflict")
        container.read_item.return_value = existing

        duplicate = await store.create_or_get(self.task)
        self.assertEqual(duplicate.etag, "7")
        self.assertEqual(duplicate, _record_from_document(existing))
        self.assertEqual(container.create_item.await_count, 1)
        self.assertEqual(container.read_item.await_count, 1)
        self.assertEqual(container.create_item.await_args.args[0], create_body)
        self.assertEqual(container.read_item.await_args.kwargs, {"item": str(self.task.task_id), "partition_key": self.task.owner_scope})

        container.create_item.reset_mock()
        container.read_item.reset_mock()
        container.create_item.side_effect = None
        container.create_item.return_value = created
        created_record = await store.create_or_get(self.task.model_copy(update={"request_fingerprint": "fingerprint-1"}))
        self.assertEqual(created_record.etag, "7")
        self.assertEqual(container.create_item.await_args.args[0], create_body)
        self.assertEqual(created_record, _record_from_document(created))

        different = self.task.model_copy(update={"request_fingerprint": "fingerprint-2"})
        container.create_item.reset_mock()
        container.create_item.side_effect = _CosmosError(409, "conflict")
        container.read_item.return_value = existing
        with self.assertRaises(PublicError) as error:
            await store.create_or_get(different)
        self.assertEqual(error.exception.code, "IDEMPOTENCY_KEY_REUSED")

        container.read_item.reset_mock()
        container.read_item.side_effect = _CosmosError(404, "missing")
        with self.assertRaises(PublicError) as error:
            await store.get(self.task.owner_scope, str(self.task.task_id))
        self.assertEqual(error.exception.code, "TASK_NOT_FOUND")

        current = self.task.model_copy(update={"lifecycle_state": LifecycleState.RUNNING, "etag": "9"})
        container.read_item.side_effect = None
        container.read_item.return_value = self._cosmos_document(current, etag="9")
        container.replace_item.return_value = updated

        callback_update = current.model_copy(
            update={"callback_delivery_state": CallbackDeliveryState.DELIVERED, "etag": "9"}
        )
        replaced = await store.replace(callback_update, "9")
        self.assertEqual(replaced.callback_delivery_state, CallbackDeliveryState.DELIVERED)
        self.assertEqual(replaced, _record_from_document(updated))
        self.assertEqual(container.read_item.await_count, 2)
        self.assertEqual(container.replace_item.await_count, 1)
        self.assertEqual(
            container.replace_item.await_args.kwargs,
            {
                "item": str(self.task.task_id),
                "body": self._task_document(callback_update),
                "etag": "9",
                "match_condition": MatchConditions.IfNotModified,
            },
        )

        container.read_item.reset_mock()
        container.replace_item.reset_mock()
        container.read_item.return_value = self._cosmos_document(current, etag="9")
        invalid = current.model_copy(update={"lifecycle_state": LifecycleState.ACCEPTED})
        with self.assertRaises(InvalidTransition):
            await store.replace(invalid, "9")
        self.assertEqual(container.replace_item.await_count, 0)

        container.read_item.side_effect = None
        container.read_item.return_value = self._cosmos_document(current, etag="9")
        container.replace_item.side_effect = _CosmosError(412, "precondition failed")
        with self.assertRaises(ConcurrencyError):
            await store.replace(callback_update, "9")

    async def test_cosmos_replace_exact_status_translation_and_unavailable_fallbacks(self) -> None:
        container = _ContainerProxy()
        store = CosmosControlStore(container)
        current = self.task.model_copy(update={"lifecycle_state": LifecycleState.RUNNING, "etag": "9"})
        replace_body = self._task_document(current)
        current_document = self._cosmos_document(current, etag="9")

        container.read_item.reset_mock()
        container.read_item.side_effect = _CosmosError(404, "missing")
        with self.assertRaises(PublicError) as error:
            await store.replace(current, "9")
        self.assertEqual(error.exception.code, "TASK_NOT_FOUND")
        self.assertEqual(error.exception.safe_message, "task not found")
        self.assertIsInstance(error.exception.__cause__, _CosmosError)
        self.assertEqual(getattr(error.exception.__cause__, "status_code", None), 404)
        self.assertEqual(container.read_item.await_args.kwargs, {"item": str(self.task.task_id), "partition_key": self.task.owner_scope})
        container.replace_item.assert_not_awaited()

        container.read_item.reset_mock()
        container.read_item.side_effect = None
        container.read_item.return_value = current_document
        container.replace_item.side_effect = _CosmosError(404, "missing")
        with self.assertRaises(PublicError) as error:
            await store.replace(current, "9")
        self.assertEqual(error.exception.code, "TASK_NOT_FOUND")
        self.assertEqual(error.exception.safe_message, "task not found")
        self.assertIsInstance(error.exception.__cause__, _CosmosError)
        self.assertEqual(getattr(error.exception.__cause__, "status_code", None), 404)
        container.replace_item.assert_awaited_once_with(
            item=str(self.task.task_id),
            body=replace_body,
            etag="9",
            match_condition=MatchConditions.IfNotModified,
        )

        container.read_item.reset_mock()
        container.read_item.side_effect = None
        container.read_item.return_value = current_document
        container.replace_item.side_effect = _CosmosError(412, "precondition failed")
        with self.assertRaises(ConcurrencyError):
            await store.replace(current, "9")

        container.read_item.reset_mock()
        container.read_item.side_effect = _CosmosError(404, "owner resource does not exist for container tasks", body={"message": "owner resource does not exist"})
        with self.assertRaises(PublicError) as error:
            await store.get(self.task.owner_scope, str(self.task.task_id))
        self.assertEqual(error.exception.code, "CONTROL_STORE_UNAVAILABLE")
        self.assertEqual(error.exception.safe_message, "control store unavailable")
        self.assertNotIn("owner resource", str(error.exception))
        self.assertIsInstance(error.exception.__cause__, _CosmosError)
        self.assertEqual(getattr(error.exception.__cause__, "status_code", None), 404)

        for status_code in (429, 500):
            container.read_item.reset_mock()
            container.read_item.side_effect = None
            container.read_item.return_value = current_document
            container.replace_item.reset_mock()
            container.replace_item.side_effect = _CosmosError(status_code, "server exploded")
            with self.assertRaises(PublicError) as error:
                await store.replace(current, "9")
            self.assertEqual(error.exception.code, "CONTROL_STORE_UNAVAILABLE")
            self.assertEqual(error.exception.safe_message, "control store unavailable")
            self.assertIsInstance(error.exception.__cause__, _CosmosError)
            self.assertEqual(getattr(error.exception.__cause__, "status_code", None), status_code)
            container.replace_item.assert_awaited_once_with(
                item=str(self.task.task_id),
                body=replace_body,
                etag="9",
                match_condition=MatchConditions.IfNotModified,
            )


if __name__ == "__main__":
    unittest.main()

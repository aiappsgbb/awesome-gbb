#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs orchestrator."""

from __future__ import annotations

import sys
import types
import unittest
import uuid
import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from pydantic import BaseModel, ConfigDict, Field

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

from app.control_store import ConcurrencyError, InMemoryControlStore  # noqa: E402
from app.aca_jobs import AcaExecution  # noqa: E402
from app.models import LifecycleState, Policy, PublicError, StartRequest, TaskRecord  # noqa: E402
from app.orchestrator import Orchestrator  # noqa: E402


class ManualClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeJobs:
    def __init__(self) -> None:
        self.start = AsyncMock()
        self.get = AsyncMock()
        self.list = AsyncMock()
        self.stop = AsyncMock()


class FlakyStore(InMemoryControlStore):
    def __init__(self, *, fail_replace_times: int = 1) -> None:
        super().__init__()
        self.fail_replace_times = fail_replace_times

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord:
        if self.fail_replace_times > 0:
            self.fail_replace_times -= 1
            raise ConcurrencyError("task etag no longer matches")
        return await super().replace(task, etag)


class CoordinatedClaimStore(InMemoryControlStore):
    def __init__(
        self,
        *,
        fail_first_replace_for: str | None = None,
        retry_release_event: asyncio.Event | None = None,
        retry_block_task_name: str | None = None,
        second_winner_task_name: str | None = None,
    ) -> None:
        super().__init__()
        self.fail_first_replace_for = fail_first_replace_for
        self.retry_release_event = retry_release_event
        self.retry_block_task_name = retry_block_task_name
        self.second_winner_task_name = second_winner_task_name
        self.first_replace_failed = asyncio.Event()
        self.second_replace_committed = asyncio.Event()
        self._get_counts: dict[str, int] = {}
        self._failed_task_names: set[str] = set()

    @staticmethod
    def _task_name() -> str:
        task = asyncio.current_task()
        return task.get_name() if task is not None else "unknown"

    async def get(self, owner_scope: str, task_id: str) -> TaskRecord:
        name = self._task_name()
        self._get_counts[name] = self._get_counts.get(name, 0) + 1
        if self.retry_block_task_name == name and self._get_counts[name] >= 3:
            await (self.retry_release_event or self.second_replace_committed).wait()
        return await super().get(owner_scope, task_id)

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord:
        name = self._task_name()
        if self.fail_first_replace_for == name and name not in self._failed_task_names:
            self._failed_task_names.add(name)
            self.first_replace_failed.set()
            raise ConcurrencyError("task etag no longer matches")
        if self.second_winner_task_name == name:
            await self.first_replace_failed.wait()
        replaced = await super().replace(task, etag)
        if self.second_winner_task_name == name:
            self.second_replace_committed.set()
        return replaced


class FoundryMcpAcaJobsOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.fixed_now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        self.clock = ManualClock(self.fixed_now)
        self.sleep = AsyncMock()
        self.jobs = FakeJobs()
        self.policy = Policy(
            jobs={
                "import": {
                    "resource_group": "rg-jobs",
                    "job_name": "job-import",
                    "container_name": "worker",
                    "image_digest": "repo/image@sha256:" + "a" * 64,
                    "command": ["python", "-m", "app.job_worker"],
                }
            },
            callbacks={
                "callback": {
                    "url": "https://callback.example.invalid/hook",
                    "auth_mode": "managed_identity",
                    "audience": "api://callback",
                }
            },
            input_hosts={"input.example.invalid"},
            result_hosts={"result.example.invalid"},
        )
        self.owner_scope = "owner-a"
        self.request = StartRequest(
            jobType="import",
            idempotencyKey="key-1",
            inputRef="https://input.example.invalid/input.json",
            callbackAlias="callback",
        )

    def _orchestrator(self, store: InMemoryControlStore | None = None) -> Orchestrator:
        return Orchestrator(store or InMemoryControlStore(), self.jobs, self.policy, self.clock, sleep=self.sleep)

    def _make_execution(
        self,
        *,
        execution_id: str,
        status: str,
        start_time: datetime,
        task_id: str,
    ) -> AcaExecution:
        return AcaExecution(
            execution_id=execution_id,
            status=status,  # type: ignore[arg-type]
            start_time=start_time,
            args=["--owner-scope", self.owner_scope, "--task-id", task_id],
        )

    async def test_start_creates_claims_and_binds_execution(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        canonical_fingerprint = json.dumps(
            {
                "callbackAlias": self.request.callback_alias,
                "inputRef": str(self.request.input_ref),
                "jobType": self.request.job_type,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        expected_fingerprint = hashlib.sha256(canonical_fingerprint.encode("utf-8")).hexdigest()
        idempotency_material = f"{self.owner_scope}\0{self.request.job_type}\0{self.request.idempotency_key}"
        expected_task_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{self.owner_scope}:{self.request.job_type}:{hashlib.sha256(idempotency_material.encode('utf-8')).hexdigest()}",
        )
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(expected_task_id),
        )

        record = await orchestrator.start(self.request, self.owner_scope)

        self.assertEqual(record.task_id, expected_task_id)
        self.assertEqual(record.request_fingerprint, expected_fingerprint)
        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(record.aca_execution_id, "exec-1")
        self.assertEqual(record.start_attempt_count, 1)
        self.assertEqual(record.start_attempted_at, self.fixed_now)
        self.jobs.start.assert_awaited_once()

    async def test_start_duplicate_fingerprint_reuses_task_without_second_arm_call(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )

        first = await orchestrator.start(self.request, self.owner_scope)
        second = await orchestrator.start(self.request, self.owner_scope)

        self.assertEqual(first.task_id, second.task_id)
        self.assertEqual(self.jobs.start.await_count, 1)

    async def test_start_rejects_fingerprint_reuse_with_new_input(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )

        await orchestrator.start(self.request, self.owner_scope)
        with self.assertRaises(PublicError) as error:
            await orchestrator.start(
                self.request.model_copy(update={"input_ref": "https://input.example.invalid/other.json"}),
                self.owner_scope,
            )

        self.assertEqual(error.exception.code, "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(self.jobs.start.await_count, 1)

    async def test_start_rejects_invalid_policy_inputs_before_arming(self) -> None:
        orchestrator = self._orchestrator()
        self.jobs.start.reset_mock()

        with self.assertRaises(PublicError) as error:
            await orchestrator.start(
                self.request.model_copy(update={"job_type": "unknown"}),
                self.owner_scope,
            )
        self.assertEqual(error.exception.code, "INVALID_JOB_TYPE")
        self.jobs.start.assert_not_awaited()

        with self.assertRaises(PublicError) as error:
            await orchestrator.start(
                self.request.model_copy(update={"callback_alias": "missing"}),
                self.owner_scope,
            )
        self.assertEqual(error.exception.code, "INVALID_CALLBACK_ALIAS")

        with self.assertRaises(PublicError) as error:
            await orchestrator.start(
                self.request.model_copy(update={"input_ref": "https://other.example.invalid/input.json"}),
                self.owner_scope,
            )
        self.assertEqual(error.exception.code, "INVALID_INPUT_REFERENCE")

    async def test_start_definitive_rejection_persists_failed_and_raises(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_START_REJECTED", "arm start rejected")

        with self.assertRaises(PublicError) as error:
            await orchestrator.start(self.request, self.owner_scope)

        self.assertEqual(error.exception.code, "ARM_START_REJECTED")
        idempotency_material = f"{self.owner_scope}\0{self.request.job_type}\0{self.request.idempotency_key}"
        record = await store.get(
            self.owner_scope,
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:{hashlib.sha256(idempotency_material.encode('utf-8')).hexdigest()}")),
        )
        self.assertEqual(record.lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(record.error_code, "ARM_START_REJECTED")
        self.jobs.start.assert_awaited_once()

    async def test_start_uncertain_rejects_return_starting_without_execution_id(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")

        record = await orchestrator.start(self.request, self.owner_scope)

        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.assertIsNone(record.aca_execution_id)
        self.assertEqual(record.start_attempt_count, 1)

    async def test_get_status_refreshes_bound_execution_and_validates_result_url(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )
        created = await orchestrator.start(self.request, self.owner_scope)
        persisted = await store.replace(
            created.model_copy(
                update={
                    "lifecycle_state": LifecycleState.RUNNING,
                    "result_url": self.policy.validate_result("https://result.example.invalid/result.json"),
                }
            ),
            created.etag,
        )
        self.jobs.get.return_value = self._make_execution(
            execution_id="exec-1",
            status="Succeeded",
            start_time=self.fixed_now,
            task_id=str(persisted.task_id),
        )

        record = await orchestrator.get_status(self.owner_scope, str(persisted.task_id))

        self.assertEqual(record.lifecycle_state, LifecycleState.SUCCEEDED)
        self.assertEqual(str(record.result_url), "https://result.example.invalid/result.json")
        self.jobs.get.assert_awaited_once_with(self.policy.job("import"), "exec-1")

    async def test_get_status_unbound_start_calls_reconcile(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )
        created = await orchestrator.start(self.request, self.owner_scope)
        await store.replace(created.model_copy(update={"aca_execution_id": None}), created.etag)
        self.jobs.list.return_value = [
            self._make_execution(
                execution_id="exec-1",
                status="Running",
                start_time=self.fixed_now,
                task_id=str(created.task_id),
            )
        ]

        record = await orchestrator.get_status(self.owner_scope, str(created.task_id))

        self.assertEqual(record.aca_execution_id, "exec-1")
        self.assertEqual(record.lifecycle_state, LifecycleState.RUNNING)
        self.jobs.list.assert_awaited_once()

    async def test_cancel_before_start_attempt_marks_cancelled_without_azure(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )
        created = await orchestrator.start(self.request, self.owner_scope)
        await store.replace(
            created.model_copy(update={"start_attempt_count": 0, "start_attempted_at": None, "aca_execution_id": None}),
            created.etag,
        )

        cancelled = await orchestrator.cancel(self.owner_scope, str(created.task_id))

        self.assertEqual(cancelled.lifecycle_state, LifecycleState.CANCELLED)
        self.assertEqual(cancelled.start_attempt_count, 0)
        self.jobs.stop.assert_not_awaited()

    async def test_cancel_bound_execution_calls_stop_and_stays_nonterminal(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )
        created = await orchestrator.start(self.request, self.owner_scope)
        self.jobs.stop.return_value = None

        cancelled = await orchestrator.cancel(self.owner_scope, str(created.task_id))

        self.assertNotEqual(cancelled.lifecycle_state, LifecycleState.CANCELLED)
        self.assertIsNotNone(cancelled.cancellation_requested_at)
        self.jobs.stop.assert_awaited_once_with(self.policy.job("import"), "exec-1")

    async def test_cancel_uncertain_start_reconciles_only_to_stop(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        self.jobs.start.reset_mock()
        self.jobs.list.return_value = [
            self._make_execution(
                execution_id="exec-1",
                status="Running",
                start_time=self.fixed_now,
                task_id=str(created.task_id),
            )
        ]

        cancelled = await orchestrator.cancel(self.owner_scope, str(created.task_id))

        self.assertIsNotNone(cancelled.cancellation_requested_at)
        self.assertEqual(cancelled.aca_execution_id, "exec-1")
        self.jobs.start.assert_not_awaited()
        self.jobs.stop.assert_awaited_once()

    async def test_cancelled_starting_unbound_is_preserved_during_grace_without_restart(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        created = await store.create_or_get(
            TaskRecord.new(
                owner_scope=self.owner_scope,
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.invalid/input.json",
                callback_alias="callback",
            )
        )
        seeded = await store.replace(
            created.model_copy(
                update={
                    "lifecycle_state": LifecycleState.STARTING,
                    "start_attempt_count": 1,
                    "start_attempted_at": self.fixed_now - timedelta(seconds=5),
                    "cancellation_requested_at": self.fixed_now - timedelta(seconds=5),
                }
            ),
            created.etag,
        )
        self.jobs.list.return_value = []

        record = await orchestrator.reconcile(self.owner_scope, str(seeded.task_id))

        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(record.cancellation_requested_at, self.fixed_now - timedelta(seconds=5))
        self.assertIsNone(record.completed_at)
        self.jobs.start.assert_not_awaited()

    async def test_cancelled_starting_unbound_persists_after_grace_without_restart(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        created = await store.create_or_get(
            TaskRecord.new(
                owner_scope=self.owner_scope,
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.invalid/input.json",
                callback_alias="callback",
            )
        )
        seeded = await store.replace(
            created.model_copy(
                update={
                    "lifecycle_state": LifecycleState.STARTING,
                    "start_attempt_count": 1,
                    "start_attempted_at": self.fixed_now - timedelta(seconds=35),
                    "cancellation_requested_at": self.fixed_now - timedelta(seconds=35),
                }
            ),
            created.etag,
        )
        self.jobs.list.return_value = []

        record = await orchestrator.reconcile(self.owner_scope, str(seeded.task_id))

        self.assertEqual(record.lifecycle_state, LifecycleState.CANCELLED)
        self.assertEqual(record.cancellation_requested_at, self.fixed_now - timedelta(seconds=35))
        self.assertIsNotNone(record.completed_at)
        self.assertEqual(record.updated_at, self.fixed_now)
        self.jobs.start.assert_not_awaited()

    async def test_reconcile_zero_matches_retries_start_only_after_grace_and_without_cancellation(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = [
            PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable"),
            self._make_execution(
                execution_id="exec-2",
                status="Processing",
                start_time=self.fixed_now + timedelta(seconds=5),
                task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
            ),
        ]
        created = await orchestrator.start(self.request, self.owner_scope)
        self.jobs.start.reset_mock(side_effect=False)
        await store.replace(
            created.model_copy(update={"aca_execution_id": None, "start_attempt_count": 1}),
            created.etag,
        )
        self.jobs.list.return_value = []

        pending = await orchestrator.reconcile(self.owner_scope, str(created.task_id))
        self.assertEqual(pending.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(self.jobs.start.await_count, 0)

        self.clock.advance(3)
        updated = await orchestrator.reconcile(self.owner_scope, str(created.task_id))
        self.assertEqual(updated.start_attempt_count, 2)
        self.assertEqual(updated.aca_execution_id, "exec-2")
        self.assertEqual(self.jobs.start.await_count, 1)

    async def test_reconcile_one_match_binds_and_refreshes(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        await store.replace(created.model_copy(update={"aca_execution_id": None}), created.etag)
        self.jobs.list.return_value = [
            self._make_execution(
                execution_id="exec-1",
                status="Processing",
                start_time=self.fixed_now,
                task_id=str(created.task_id),
            )
        ]

        record = await orchestrator.reconcile(self.owner_scope, str(created.task_id))

        self.assertEqual(record.aca_execution_id, "exec-1")
        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.jobs.stop.assert_not_awaited()

    async def test_reconcile_multiple_matches_selects_deterministic_winner_and_stops_duplicates(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        await store.replace(created.model_copy(update={"aca_execution_id": None}), created.etag)
        early = self._make_execution(
            execution_id="aaa",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(created.task_id),
        )
        late = self._make_execution(
            execution_id="bbb",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(created.task_id),
        )
        self.jobs.list.return_value = [late, early]

        record = await orchestrator.reconcile(self.owner_scope, str(created.task_id))

        self.assertEqual(record.aca_execution_id, "aaa")
        self.jobs.stop.assert_awaited_once_with(self.policy.job("import"), "bbb")

    async def test_reconcile_multiple_matches_prefers_succeeded_over_older_running(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        created = await store.replace(
            created.model_copy(
                update={
                    "result_url": self.policy.validate_result("https://result.example.invalid/result.json"),
                }
            ),
            created.etag,
        )
        running = self._make_execution(
            execution_id="aaa",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(created.task_id),
        )
        succeeded = self._make_execution(
            execution_id="bbb",
            status="Succeeded",
            start_time=self.fixed_now + timedelta(seconds=1),
            task_id=str(created.task_id),
        )
        self.jobs.list.return_value = [running, succeeded]

        record = await orchestrator.reconcile(self.owner_scope, str(created.task_id))

        self.assertEqual(record.aca_execution_id, "bbb")
        self.assertEqual(record.lifecycle_state, LifecycleState.SUCCEEDED)
        self.jobs.stop.assert_awaited_once_with(self.policy.job("import"), "aaa")

    async def test_reconcile_duplicate_stop_is_best_effort(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        await store.replace(created.model_copy(update={"aca_execution_id": None}), created.etag)
        first = self._make_execution(
            execution_id="aaa",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(created.task_id),
        )
        second = self._make_execution(
            execution_id="bbb",
            status="Running",
            start_time=self.fixed_now,
            task_id=str(created.task_id),
        )
        self.jobs.list.return_value = [first, second]
        self.jobs.stop.side_effect = [None, PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")]

        record = await orchestrator.reconcile(self.owner_scope, str(created.task_id))

        self.assertEqual(record.aca_execution_id, "aaa")
        self.assertEqual(self.jobs.stop.await_count, 1)

    def test_select_winner_prefers_status_priority_then_start_time_then_execution_id(self) -> None:
        earlier_running = self._make_execution(
            execution_id="aaa",
            status="Running",
            start_time=self.fixed_now,
            task_id="task-a",
        )
        later_succeeded = self._make_execution(
            execution_id="bbb",
            status="Succeeded",
            start_time=self.fixed_now + timedelta(seconds=1),
            task_id="task-a",
        )
        earlier_processing = self._make_execution(
            execution_id="ccc",
            status="Processing",
            start_time=self.fixed_now - timedelta(seconds=1),
            task_id="task-a",
        )
        tie_running = self._make_execution(
            execution_id="ddd",
            status="Running",
            start_time=self.fixed_now,
            task_id="task-a",
        )

        self.assertEqual(
            Orchestrator._select_winner([earlier_running, later_succeeded, earlier_processing]),
            later_succeeded,
        )
        self.assertEqual(Orchestrator._select_winner([tie_running, earlier_running]), earlier_running)

    async def test_reconcile_exhaustion_marks_failed_after_three_attempts_or_five_minutes(self) -> None:
        store = InMemoryControlStore()
        orchestrator = self._orchestrator(store)
        self.jobs.start.side_effect = PublicError("ARM_STATUS_UNAVAILABLE", "arm status unavailable")
        created = await orchestrator.start(self.request, self.owner_scope)
        exhausted = await store.replace(
            created.model_copy(
                update={
                    "aca_execution_id": None,
                    "start_attempt_count": 3,
                    "start_attempted_at": self.fixed_now - timedelta(minutes=6),
                }
            ),
            created.etag,
        )
        self.jobs.list.return_value = []

        with self.assertRaises(PublicError) as error:
            await orchestrator.reconcile(self.owner_scope, str(exhausted.task_id))

        self.assertEqual(error.exception.code, "START_RECONCILIATION_EXHAUSTED")
        terminal = await store.get(self.owner_scope, str(exhausted.task_id))
        self.assertEqual(terminal.lifecycle_state, LifecycleState.FAILED)
        self.assertEqual(terminal.error_code, "START_RECONCILIATION_EXHAUSTED")

    async def test_claim_start_loses_when_cancellation_is_persisted_before_retry(self) -> None:
        retry_release = asyncio.Event()
        store = CoordinatedClaimStore(
            fail_first_replace_for="cancel-race",
            retry_block_task_name="cancel-race",
            retry_release_event=retry_release,
        )
        orchestrator = self._orchestrator(store)
        created = await store.create_or_get(
            TaskRecord.new(
                owner_scope=self.owner_scope,
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.invalid/input.json",
                callback_alias="callback",
            )
        )
        seeded = await store.replace(
            created.model_copy(
                update={
                    "lifecycle_state": LifecycleState.STARTING,
                    "start_attempt_count": 1,
                    "start_attempted_at": self.fixed_now - timedelta(seconds=5),
                }
            ),
            created.etag,
        )

        reconcile_task = asyncio.create_task(
            orchestrator.reconcile(self.owner_scope, str(seeded.task_id)),
            name="cancel-race",
        )
        await store.first_replace_failed.wait()

        current = await store.get(self.owner_scope, str(seeded.task_id))
        updated = await store.replace(
            current.model_copy(update={"cancellation_requested_at": self.fixed_now}),
            current.etag,
        )
        retry_release.set()

        record = await reconcile_task

        self.assertEqual(record.cancellation_requested_at, self.fixed_now)
        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(updated.cancellation_requested_at, self.fixed_now)
        self.jobs.start.assert_not_awaited()

    async def test_concurrent_reconcile_calls_after_one_412_only_start_once(self) -> None:
        store = CoordinatedClaimStore(
            fail_first_replace_for="reconcile-1",
            retry_block_task_name="reconcile-1",
            second_winner_task_name="reconcile-2",
        )
        orchestrator = self._orchestrator(store)
        created = await store.create_or_get(
            TaskRecord.new(
                owner_scope=self.owner_scope,
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.invalid/input.json",
                callback_alias="callback",
            )
        )
        seeded = await store.replace(
            created.model_copy(
                update={
                    "lifecycle_state": LifecycleState.STARTING,
                    "start_attempt_count": 1,
                    "start_attempted_at": self.fixed_now - timedelta(seconds=5),
                }
            ),
            created.etag,
        )
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(seeded.task_id),
        )

        first = asyncio.create_task(
            orchestrator.reconcile(self.owner_scope, str(seeded.task_id)),
            name="reconcile-1",
        )
        second = asyncio.create_task(
            orchestrator.reconcile(self.owner_scope, str(seeded.task_id)),
            name="reconcile-2",
        )

        await asyncio.gather(first, second)

        final = await store.get(self.owner_scope, str(seeded.task_id))

        self.assertEqual(self.jobs.start.await_count, 1)
        self.assertTrue(store.first_replace_failed.is_set())
        self.assertTrue(store.second_replace_committed.is_set())
        self.assertEqual(final.aca_execution_id, "exec-1")
        self.assertEqual(final.start_attempt_count, 2)

    async def test_store_mutation_retries_concurrency_error_by_rereading(self) -> None:
        store = FlakyStore(fail_replace_times=1)
        orchestrator = self._orchestrator(store)
        self.jobs.start.return_value = self._make_execution(
            execution_id="exec-1",
            status="Processing",
            start_time=self.fixed_now,
            task_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.owner_scope}:import:")),
        )

        record = await orchestrator.start(self.request, self.owner_scope)

        self.assertEqual(record.lifecycle_state, LifecycleState.STARTING)
        self.assertEqual(record.start_attempt_count, 1)


if __name__ == "__main__":
    unittest.main()

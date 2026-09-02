#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs job worker."""

from __future__ import annotations

import asyncio
import importlib
import os
import subprocess
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

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
        result: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
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

from app.control_store import InMemoryControlStore  # noqa: E402
from app.models import CallbackDeliveryState, LifecycleState, Policy, PublicError, TaskRecord  # noqa: E402


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _FakeOutputStore:
    def __init__(self, *, resource_exists_exc: type[BaseException] | None = None) -> None:
        self.resource_exists_exc = resource_exists_exc
        self.payloads: dict[str, dict[str, Any]] = {}
        self.urls: dict[str, str] = {}
        self.exists_overrides: dict[str, bool] = {}
        self.exists_calls: list[str] = []
        self.get_calls: list[str] = []
        self.write_calls: list[tuple[str, Any, bool]] = []
        self.raise_on_write: dict[str, BaseException] = {}

    async def exists(self, path: str) -> bool:
        self.exists_calls.append(path)
        if path in self.exists_overrides:
            return self.exists_overrides[path]
        return path in self.urls

    async def get(self, path: str) -> str:
        self.get_calls.append(path)
        return self.urls[path]

    async def write_json(self, path: str, payload: Any, overwrite: bool = False) -> str:
        self.write_calls.append((path, payload, overwrite))
        if path in self.raise_on_write:
            raise self.raise_on_write[path]
        if not overwrite and path in self.urls and self.resource_exists_exc is not None:
            raise self.resource_exists_exc("blob already exists")
        url = f"https://results.example.com/{path}"
        self.urls[path] = url
        self.payloads[path] = payload
        return url


class _FakeCallbackSender:
    def __init__(self, *, exhaust: bool = False) -> None:
        self.exhaust = exhaust
        self.calls: list[tuple[Any, dict[str, str]]] = []

    async def send(self, policy: Any, payload: dict[str, str]) -> None:
        self.calls.append((policy, payload))
        if self.exhaust:
            raise PublicError("CALLBACK_DELIVERY_EXHAUSTED", "callback delivery exhausted")


class _RecordingHandler:
    def __init__(self, *, result: Any = None, exc: BaseException | None = None) -> None:
        self.result = {"kind": "metadata"}
        if result is not None:
            self.result = result
        self.exc = exc
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, input_ref: str, task_id: str) -> Any:
        self.calls.append((input_ref, task_id))
        if self.exc is not None:
            raise self.exc
        return self.result


class _RecordingStore:
    def __init__(self) -> None:
        self.inner = InMemoryControlStore()
        self.create_calls: list[TaskRecord] = []
        self.get_calls: list[tuple[str, str]] = []
        self.replace_calls: list[tuple[TaskRecord, str | None]] = []

    async def create_or_get(self, task: TaskRecord) -> TaskRecord:
        self.create_calls.append(task.model_copy())
        return await self.inner.create_or_get(task)

    async def get(self, owner_scope: str, task_id: str) -> TaskRecord:
        self.get_calls.append((owner_scope, task_id))
        return await self.inner.get(owner_scope, task_id)

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord:
        self.replace_calls.append((task.model_copy(), etag))
        return await self.inner.replace(task, etag)


class FoundryMcpAcaJobsWorkerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.models = importlib.import_module("app.models")

    def setUp(self) -> None:
        self.JobPolicy = self.models.JobPolicy
        self.CallbackPolicy = self.models.CallbackPolicy
        self.Policy = self.models.Policy
        self.TaskRecord = self.models.TaskRecord
        self.LifecycleState = self.models.LifecycleState
        self.CallbackDeliveryState = self.models.CallbackDeliveryState
        self.PublicError = self.models.PublicError
        self.worker_module = None
        self.fixed_now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        with patch("app.models._utcnow", return_value=self.fixed_now):
            self.task = self.TaskRecord.new(
                owner_scope="scope-a",
                job_type="batch",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.com/jobs/1",
                callback_alias="ops",
            ).model_copy(update={"aca_execution_id": "execution-1"})
        self.policy = self.Policy(
            jobs={
                "batch": self.JobPolicy(
                    resource_group="rg",
                    job_name="batch-job",
                    container_name="worker",
                    image_digest="registry.azurecr.io/work@sha256:" + "a" * 64,
                    command=["python", "-m", "app.job_worker"],
                    allowed_owner_scopes={"scope-a"},
                )
            },
            callbacks={
                "ops": self.CallbackPolicy(
                    url="https://hooks.example.com/jobs",
                    auth_mode="managed_identity",
                    audience="api://mcp-callback",
                )
            },
            input_hosts={"input.example.com"},
            result_hosts={"results.example.com"},
        )

    def _module(self):
        if self.worker_module is None:
            try:
                self.worker_module = importlib.import_module("app.job_worker")
            except ModuleNotFoundError as exc:  # pragma: no cover - red phase failure path
                self.fail(f"app.job_worker is missing: {exc}")
        return self.worker_module

    def _task_path(self, task_id: str) -> str:
        return f"results/{task_id}/result.json"

    async def _build_worker(
        self,
        *,
        store: Any | None = None,
        output: _FakeOutputStore | None = None,
        handler: _RecordingHandler | None = None,
        callback_sender: _FakeCallbackSender | None = None,
        lease: timedelta = timedelta(minutes=5),
    ) -> tuple[Any, Any, _RecordingHandler, _FakeCallbackSender, _FakeOutputStore]:
        module = self._module()
        store = store or _RecordingStore()
        output = output or _FakeOutputStore(resource_exists_exc=module.ResourceExistsError)
        handler = handler or _RecordingHandler()
        callback_sender = callback_sender or _FakeCallbackSender()
        worker = module.JobWorker(
            store=store,
            output=output,
            handler=handler,
            callback_sender=callback_sender,
            policy=self.policy,
            clock=_Clock(self.fixed_now),
            lease=lease,
        )
        return worker, store, handler, callback_sender, output

    async def _seed_task(self, store: Any, task: TaskRecord | None = None) -> TaskRecord:
        task = task or self.task
        return await store.create_or_get(task)

    async def test_first_worker_claims_runs_handler_persists_result_and_sends_exact_callback(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        await self._seed_task(store)

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(handler.calls[0], ("https://input.example.com/jobs/1", str(self.task.task_id)))
        self.assertEqual(output.write_calls[0][0], self._task_path(str(self.task.task_id)))
        self.assertEqual(output.write_calls[0][2], False)
        self.assertEqual(output.payloads[self._task_path(str(self.task.task_id))], {"kind": "metadata"})
        self.assertEqual(len(callback_sender.calls), 1)
        callback_policy, payload = callback_sender.calls[0]
        self.assertEqual(callback_policy.url, self.policy.callback("ops").url)
        self.assertEqual(
            payload,
            {
                "taskId": str(self.task.task_id),
                "acaExecutionId": "execution-1",
                "status": "Succeeded",
                "resultUrl": output.urls[self._task_path(str(self.task.task_id))],
            },
        )
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        self.assertEqual(str(current.result_url), output.urls[self._task_path(str(self.task.task_id))])
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.DELIVERED)
        self.assertIsNone(current.callback_error_code)
        self.assertIsNone(current.worker_claim_token)
        self.assertIsNone(current.worker_claimed_at)
        self.assertIsNone(current.worker_claim_expires_at)
        self.assertEqual(store.replace_calls[0][0].lifecycle_state, self.LifecycleState.RUNNING)
        self.assertIsNotNone(store.replace_calls[0][0].worker_claimed_at)
        self.assertIsNotNone(store.replace_calls[0][0].worker_claim_token)
        self.assertEqual(
            store.replace_calls[0][0].worker_claim_expires_at,
            self.fixed_now + timedelta(minutes=5),
        )

    async def test_duplicate_active_worker_exits_zero_without_handler(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        claimed = self.task.model_copy(
            update={
                "lifecycle_state": self.LifecycleState.RUNNING,
                "worker_claimed_at": self.fixed_now,
                "worker_claim_token": "lease-1",
                "worker_claim_expires_at": self.fixed_now + timedelta(minutes=5),
            }
        )
        await self._seed_task(store, claimed)

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(callback_sender.calls, [])
        self.assertEqual(output.write_calls, [])
        self.assertEqual(store.replace_calls, [])

    async def test_expired_lease_reclaim_reuses_existing_output_without_handler(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        claimed = self.task.model_copy(
            update={
                "lifecycle_state": self.LifecycleState.RUNNING,
                "worker_claimed_at": self.fixed_now - timedelta(minutes=10),
                "worker_claim_token": "lease-1",
                "worker_claim_expires_at": self.fixed_now - timedelta(seconds=1),
            }
        )
        await self._seed_task(store, claimed)
        output.urls[self._task_path(str(self.task.task_id))] = (
            f"https://results.example.com/{self._task_path(str(self.task.task_id))}"
        )

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(output.get_calls, [self._task_path(str(self.task.task_id))])
        self.assertEqual(output.write_calls, [])
        self.assertEqual(len(callback_sender.calls), 1)
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        self.assertEqual(str(current.result_url), output.urls[self._task_path(str(self.task.task_id))])
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.DELIVERED)

    async def test_existing_output_recovery_skips_handler(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        self.task.model_copy(update={"lifecycle_state": self.LifecycleState.RUNNING})
        await self._seed_task(store, self.task.model_copy(update={"lifecycle_state": self.LifecycleState.RUNNING}))
        output.urls[self._task_path(str(self.task.task_id))] = (
            f"https://results.example.com/{self._task_path(str(self.task.task_id))}"
        )

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(output.get_calls, [self._task_path(str(self.task.task_id))])
        self.assertEqual(len(callback_sender.calls), 1)
        self.assertEqual(callback_sender.calls[0][1]["resultUrl"], output.urls[self._task_path(str(self.task.task_id))])

    async def test_write_race_uses_existing_url(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        await self._seed_task(store)
        output.raise_on_write[self._task_path(str(self.task.task_id))] = module_exc = self._module().ResourceExistsError(
            "exists"
        )
        output.exists_overrides[self._task_path(str(self.task.task_id))] = False
        output.urls[self._task_path(str(self.task.task_id))] = (
            f"https://results.example.com/{self._task_path(str(self.task.task_id))}"
        )

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(output.get_calls, [self._task_path(str(self.task.task_id))])
        self.assertIs(module_exc, output.raise_on_write[self._task_path(str(self.task.task_id))])
        self.assertEqual(len(callback_sender.calls), 1)
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(str(current.result_url), output.urls[self._task_path(str(self.task.task_id))])
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.DELIVERED)

    async def test_handler_failure_records_stable_worker_error_and_no_output_or_callback(self) -> None:
        for exc, expected in [
            (RuntimeError("boom"), "WORKER_EXECUTION_FAILED"),
            (PublicError("CUSTOM_WORKER_ERROR", "custom"), "CUSTOM_WORKER_ERROR"),
        ]:
            with self.subTest(exc=type(exc).__name__):
                worker, store, handler, callback_sender, output = await self._build_worker(handler=_RecordingHandler(exc=exc))
                await self._seed_task(store)

                code = await worker.run("scope-a", str(self.task.task_id))

                self.assertEqual(code, 0)
                current = await store.get("scope-a", str(self.task.task_id))
                self.assertEqual(current.lifecycle_state, self.LifecycleState.FAILED)
                self.assertEqual(current.error_code, expected)
                self.assertIsNone(current.result_url)
                self.assertEqual(callback_sender.calls, [])
                self.assertEqual(output.write_calls, [])

    async def test_callback_exhaustion_preserves_success_and_marks_exhausted(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker(
            callback_sender=_FakeCallbackSender(exhaust=True)
        )
        await self._seed_task(store)

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        self.assertIsNone(current.error_code)
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.EXHAUSTED)
        self.assertEqual(current.callback_error_code, "CALLBACK_DELIVERY_EXHAUSTED")
        self.assertIsNotNone(current.result_url)
        self.assertEqual(len(callback_sender.calls), 1)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(len(output.write_calls), 1)

    async def test_terminal_no_op(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        terminal = self.task.model_copy(
            update={
                "lifecycle_state": self.LifecycleState.SUCCEEDED,
                "result_url": self.policy.validate_result("https://results.example.com/results/task/result.json"),
                "callback_delivery_state": self.CallbackDeliveryState.DELIVERED,
            }
        )
        await self._seed_task(store, terminal)

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(callback_sender.calls, [])
        self.assertEqual(output.write_calls, [])
        self.assertEqual(store.replace_calls, [])

    def test_callback_payload_is_exact_four_fields(self) -> None:
        module = self._module()
        payload = module.callback_payload(
            str(self.task.task_id),
            "execution-1",
            "Succeeded",
            "https://results.example.com/results/task/result.json",
        )
        self.assertEqual(
            payload,
            {
                "taskId": str(self.task.task_id),
                "acaExecutionId": "execution-1",
                "status": "Succeeded",
                "resultUrl": "https://results.example.com/results/task/result.json",
            },
        )
        self.assertEqual(set(payload), {"taskId", "acaExecutionId", "status", "resultUrl"})

    def test_cli_parser_requires_owner_scope_and_task_id(self) -> None:
        module = self._module()
        parser = module.build_arg_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args([])
        args = parser.parse_args(["--owner-scope", "scope-a", "--task-id", str(self.task.task_id)])
        self.assertEqual(args.owner_scope, "scope-a")
        self.assertEqual(args.task_id, str(self.task.task_id))

    def test_module_help_exits_zero(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SKILL_DIR) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        completed = subprocess.run(
            [sys.executable, "-m", "app.job_worker", "--help"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--owner-scope", completed.stdout)
        self.assertIn("--task-id", completed.stdout)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for safe telemetry in foundry-mcp-aca-jobs."""

from __future__ import annotations

import asyncio
import builtins
import importlib
import logging
import os
import sys
import types
import unittest
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))


def _ensure_azure_worker_stubs() -> None:
    azure = sys.modules.get("azure")
    if azure is None:
        azure = types.ModuleType("azure")
        azure.__path__ = []  # type: ignore[attr-defined]
        sys.modules["azure"] = azure

    def _ensure_package(name: str) -> types.ModuleType:
        module = sys.modules.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = module
        parent_name, _, attr = name.rpartition(".")
        if parent_name:
            parent = sys.modules.get(parent_name)
            if parent is None:
                parent = _ensure_package(parent_name)
            setattr(parent, attr, module)
        return module

    def _ensure_class(module_name: str, class_name: str, factory: type[Any]) -> None:
        try:
            module = __import__(module_name, fromlist=[class_name])
        except ModuleNotFoundError:
            module = _ensure_package(module_name)
        if not hasattr(module, class_name):
            setattr(module, class_name, factory)

    class _AsyncCloseable:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.close = AsyncMock()

        async def aclose(self) -> None:
            await self.close()

    class _ManagedIdentityCredential(_AsyncCloseable):
        pass

    class _SecretClient(_AsyncCloseable):
        async def get_secret(self, name: str) -> Any:
            return types.SimpleNamespace(value=f"secret:{name}")

    class _ContainerClient:
        def __init__(self, url: str) -> None:
            self.url = url
            self._blob_clients: dict[str, Any] = {}
            self.close = AsyncMock()

        @classmethod
        def from_container_url(cls, url: str, credential: Any | None = None) -> "_ContainerClient":
            client = cls(url)
            client.credential = credential
            return client

        def get_blob_client(self, path: str) -> Any:
            client = self._blob_clients.get(path)
            if client is None:
                client = types.SimpleNamespace(
                    url=f"{self.url.rstrip('/')}/{path}",
                    upload_blob=AsyncMock(),
                    exists=AsyncMock(return_value=True),
                )
                self._blob_clients[path] = client
            return client

    class _CosmosClient(_AsyncCloseable):
        async def __aenter__(self) -> "_CosmosClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            await self.close()

    class _ContainerAppsAPIClient:
        pass

    _ensure_class("azure.core.exceptions", "HttpResponseError", Exception)
    _ensure_class("azure.core.exceptions", "ResourceExistsError", Exception)
    _ensure_class("azure.core", "MatchConditions", types.SimpleNamespace(IfNotModified="IfNotModified"))  # type: ignore[arg-type]
    _ensure_class("azure.identity.aio", "ManagedIdentityCredential", _ManagedIdentityCredential)
    _ensure_class("azure.keyvault.secrets.aio", "SecretClient", _SecretClient)
    _ensure_class("azure.storage.blob.aio", "ContainerClient", _ContainerClient)
    _ensure_class("azure.cosmos.aio", "CosmosClient", _CosmosClient)
    _ensure_class("azure.mgmt.appcontainers", "ContainerAppsAPIClient", _ContainerAppsAPIClient)


_ensure_azure_worker_stubs()


class _FakeCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def add(self, value: float, attributes: Mapping[str, str] | None = None) -> None:
        self.calls.append((value, dict(attributes or {})))


class _FakeHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, str]]] = []

    def record(self, value: float, attributes: Mapping[str, str] | None = None) -> None:
        self.calls.append((value, dict(attributes or {})))


class _FakeSpan:
    def __init__(self, tracer: "_FakeTracer", name: str, attributes: dict[str, str]) -> None:
        self.tracer = tracer
        self.name = name
        self.attributes = attributes

    def __enter__(self) -> "_FakeSpan":
        self.tracer.spans.append((self.name, dict(self.attributes)))
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.tracer.exits.append((self.name, exc_type.__name__ if exc_type else None))
        return False


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, str]]] = []
        self.exits: list[tuple[str, str | None]] = []

    def start_as_current_span(self, name: str, attributes: dict[str, str]) -> _FakeSpan:
        return _FakeSpan(self, name, attributes)


class _FakeMeter:
    def __init__(self) -> None:
        self.counter = _FakeCounter()
        self.histogram = _FakeHistogram()

    def create_counter(self, name: str) -> _FakeCounter:
        self.counter.name = name  # type: ignore[attr-defined]
        return self.counter

    def create_histogram(self, name: str, unit: str | None = None) -> _FakeHistogram:
        self.histogram.name = name  # type: ignore[attr-defined]
        self.histogram.unit = unit  # type: ignore[attr-defined]
        return self.histogram


class _FakeTelemetry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str], str | None, str | None]] = []

    @staticmethod
    def attributes(values: Mapping[str, Any]) -> dict[str, str]:
        return {key: str(value) for key, value in values.items() if key in {
            "task.id",
            "job.type",
            "task.state",
            "aca.execution.id",
            "operation",
            "outcome",
            "error.code",
            "azure.request.id",
        } and value is not None}

    @contextmanager
    def operation(self, name: str, attributes: Mapping[str, Any] | None = None):
        self.calls.append((name, self.attributes(attributes or {}), "enter", None))
        try:
            yield
        except Exception as exc:
            self.calls.append((name, self.attributes(attributes or {}), "failure", exc.__class__.__name__))
            raise
        else:
            self.calls.append((name, self.attributes(attributes or {}), "success", None))

    def record(
        self,
        operation: str,
        attributes: Mapping[str, Any] | None = None,
        *,
        outcome: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self.calls.append((operation, self.attributes(attributes or {}), outcome, error_code))


class _FlakyStore:
    def __init__(self, inner: Any, concurrency_error_cls: type[BaseException], *, fail_replace_times: int = 1) -> None:
        self.inner = inner
        self.concurrency_error_cls = concurrency_error_cls
        self.fail_replace_times = fail_replace_times

    async def create_or_get(self, task: Any) -> Any:
        return await self.inner.create_or_get(task)

    async def get(self, owner_scope: str, task_id: str) -> Any:
        return await self.inner.get(owner_scope, task_id)

    async def replace(self, task: Any, etag: str | None) -> Any:
        if self.fail_replace_times > 0:
            self.fail_replace_times -= 1
            raise self.concurrency_error_cls("task etag no longer matches")
        return await self.inner.replace(task, etag)


class FoundryMcpAcaJobsTelemetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.telemetry = importlib.import_module("app.telemetry")
        cls.models = importlib.import_module("app.models")
        cls.orchestrator_module = importlib.import_module("app.orchestrator")
        cls.worker_module = importlib.import_module("app.job_worker")
        cls.control_store = importlib.import_module("app.control_store")

    def setUp(self) -> None:
        self.TaskRecord = self.models.TaskRecord
        self.LifecycleState = self.models.LifecycleState
        self.CallbackDeliveryState = self.models.CallbackDeliveryState
        self.Policy = self.models.Policy
        self.JobPolicy = self.models.JobPolicy
        self.CallbackPolicy = self.models.CallbackPolicy
        self.PublicError = self.models.PublicError
        self.Orchestrator = self.orchestrator_module.Orchestrator
        self.JobWorker = self.worker_module.JobWorker
        self.InMemoryControlStore = self.control_store.InMemoryControlStore

    def run_async(self, coro: Any) -> Any:
        return asyncio.run(coro)

    def _new_task(self) -> Any:
        fixed = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
        with patch("app.models._utcnow", return_value=fixed):
            return self.TaskRecord.new(
                owner_scope="scope-a",
                job_type="import",
                idempotency_key_hash="hash-1",
                request_fingerprint="fingerprint-1",
                input_ref="https://input.example.invalid/input.json",
                callback_alias="callback",
            )

    def _policy(self) -> Any:
        return self.Policy(
            jobs={
                "import": self.JobPolicy(
                    resource_group="rg-jobs",
                    job_name="job-import",
                    container_name="worker",
                    image_digest="repo/image@sha256:" + "a" * 64,
                    command=["python", "-m", "app.job_worker"],
                )
            },
            callbacks={
                "callback": self.CallbackPolicy(
                    url="https://callback.example.invalid/hook",
                    auth_mode="managed_identity",
                    audience="api://callback",
                )
            },
            input_hosts={"input.example.invalid"},
            result_hosts={"result.example.invalid"},
        )

    def test_safe_keys_and_filters_keep_only_public_attributes(self) -> None:
        self.assertEqual(
            self.telemetry.SAFE_KEYS,
            {
                "task.id",
                "job.type",
                "task.state",
                "aca.execution.id",
                "operation",
                "outcome",
                "error.code",
                "azure.request.id",
            },
        )
        self.assertEqual(
            self.telemetry.METRIC_KEYS,
            {
                "operation",
                "job.type",
                "task.state",
                "outcome",
                "error.code",
            },
        )
        telem = self.telemetry.Telemetry(tracer=_FakeTracer(), meter=_FakeMeter())
        attrs = telem.attributes(
            {
                "task.id": "task-1",
                "job.type": "import",
                "task.state": "Accepted",
                "aca.execution.id": "exec-1",
                "operation": "orchestrator.start",
                "outcome": "success",
                "error.code": None,
                "azure.request.id": "req-1",
                "idempotency.key": "key-1",
                "input.url": "https://input.example.invalid/input.json?token=secret",
                "output.url": "https://result.example.invalid/out.json?access_token=secret",
                "token": "bearer",
                "secret": "vault-secret",
            }
        )
        self.assertEqual(
            attrs,
            {
                "task.id": "task-1",
                "job.type": "import",
                "task.state": "Accepted",
                "aca.execution.id": "exec-1",
                "operation": "orchestrator.start",
                "outcome": "success",
                "azure.request.id": "req-1",
            },
        )

    def test_record_filters_metric_attributes_and_drops_ids(self) -> None:
        tracer = _FakeTracer()
        meter = _FakeMeter()
        telem = self.telemetry.Telemetry(tracer=tracer, meter=meter)

        filtered = telem.record(
            "worker.business",
            {
                "task.id": "task-1",
                "aca.execution.id": "exec-1",
                "azure.request.id": "req-1",
                "job.type": "import",
                "task.state": "Running",
                "operation": "ignored",
                "outcome": "ignored",
                "error.code": "ignored",
                "extra": "drop-me",
            },
            outcome="success",
            error_code="E100",
        )

        self.assertEqual(
            filtered,
            {
                "operation": "worker.business",
                "job.type": "import",
                "task.state": "Running",
                "outcome": "success",
                "error.code": "E100",
            },
        )
        self.assertEqual(
            meter.counter.calls,
            [
                (
                    1,
                    {
                        "operation": "worker.business",
                        "job.type": "import",
                        "task.state": "Running",
                        "outcome": "success",
                        "error.code": "E100",
                    },
                )
            ],
        )

    def test_operation_records_success_failure_and_latency(self) -> None:
        tracer = _FakeTracer()
        meter = _FakeMeter()
        telem = self.telemetry.Telemetry(tracer=tracer, meter=meter)

        with patch.object(self.telemetry, "monotonic", side_effect=[10.0, 13.5]):
            with telem.operation(
                "orchestrator.start",
                {
                    "task.id": "task-1",
                    "job.type": "import",
                    "task.state": "Accepted",
                    "aca.execution.id": "exec-1",
                    "operation": "ignored",
                    "outcome": "ignored",
                    "error.code": "ignored",
                    "azure.request.id": "req-1",
                    "input.url": "https://input.example.invalid/input.json?token=secret",
                },
            ):
                pass

        self.assertEqual(tracer.spans, [("orchestrator.start", {
            "task.id": "task-1",
            "job.type": "import",
            "task.state": "Accepted",
            "aca.execution.id": "exec-1",
            "operation": "orchestrator.start",
            "outcome": "ignored",
            "error.code": "ignored",
            "azure.request.id": "req-1",
        })])
        self.assertEqual(meter.counter.calls, [(1, {
            "job.type": "import",
            "task.state": "Accepted",
            "operation": "orchestrator.start",
            "outcome": "success",
            "error.code": "ignored",
        })])
        self.assertEqual(meter.histogram.calls, [(3.5, {
            "job.type": "import",
            "task.state": "Accepted",
            "operation": "orchestrator.start",
            "outcome": "success",
            "error.code": "ignored",
        })])

        meter = _FakeMeter()
        telem = self.telemetry.Telemetry(tracer=tracer, meter=meter)
        with patch.object(self.telemetry, "monotonic", side_effect=[20.0, 21.25]):
            with self.assertRaises(RuntimeError):
                with telem.operation(
                    "worker.business",
                    {
                        "task.id": "task-2",
                        "job.type": "import",
                        "task.state": "Running",
                        "aca.execution.id": "exec-2",
                        "operation": "ignored",
                        "azure.request.id": "req-2",
                    },
                ):
                    raise RuntimeError("boom")
        self.assertEqual(meter.counter.calls[-1], (1, {
            "job.type": "import",
            "task.state": "Running",
            "operation": "worker.business",
            "outcome": "failure",
        }))
        self.assertEqual(meter.histogram.calls[-1], (1.25, {
            "job.type": "import",
            "task.state": "Running",
            "operation": "worker.business",
            "outcome": "failure",
        }))

    def test_configure_parses_semicolon_connection_string_and_masks_errors(self) -> None:
        module = self.telemetry
        with patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}, clear=False), \
            patch.object(module, "configure_azure_monitor", MagicMock()) as configure, \
            self.assertLogs("app.telemetry", level="INFO") as logs:
            module.configure()
        configure.assert_not_called()
        self.assertIn("INFO:app.telemetry:application insights disabled; no connection string configured", logs.output)

        with patch.dict(
            os.environ,
            {"APPLICATIONINSIGHTS_CONNECTION_STRING": "ApplicationId=abc;InstrumentationKey=secret-ikey;IngestionEndpoint=https://example.invalid/"},
            clear=False,
        ), patch.object(module, "configure_azure_monitor", MagicMock(side_effect=ValueError("boom"))) as configure, \
            self.assertLogs("app.telemetry", level="WARNING") as logs:
            module.configure()
        configure.assert_called_once()
        self.assertEqual(logs.output, ["WARNING:app.telemetry:application insights configuration failed: ValueError"])
        self.assertNotIn("secret-ikey", "\n".join(logs.output))

        with patch.dict(
            os.environ,
            {"APPLICATIONINSIGHTS_CONNECTION_STRING": "ApplicationId=abc;InstrumentationKey=   ;IngestionEndpoint=https://example.invalid/"},
            clear=False,
        ), patch.object(module, "configure_azure_monitor", MagicMock()) as configure, \
            self.assertLogs("app.telemetry", level="WARNING") as logs:
            module.configure()
        configure.assert_not_called()
        self.assertEqual(
            logs.output,
            ["WARNING:app.telemetry:application insights disabled; invalid connection string (redacted)"],
        )

    def test_configure_logs_optional_import_exception_class_without_leaking_value(self) -> None:
        module = self.telemetry
        real_import = builtins.__import__

        def fake_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
            if name == "azure.monitor.opentelemetry":
                raise RuntimeError("boom secret-ikey")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            reloaded = importlib.reload(module)
        self.addCleanup(importlib.reload, module)

        self.assertIsNone(reloaded.configure_azure_monitor)
        self.assertEqual(reloaded._configure_azure_monitor_import_error.__name__, "RuntimeError")

        with patch.dict(
            os.environ,
            {"APPLICATIONINSIGHTS_CONNECTION_STRING": "Foo=bar;InstrumentationKey=secret-ikey;IngestionEndpoint=https://example.invalid/"},
            clear=False,
        ), self.assertLogs("app.telemetry", level="WARNING") as logs:
            reloaded.configure()
        joined = "\n".join(logs.output)
        self.assertIn("RuntimeError", joined)
        self.assertNotIn("secret-ikey", joined)

    def test_orchestrator_records_safe_duplicate_etag_conflict_and_cancellation(self) -> None:
        telemetry = _FakeTelemetry()
        store = self.InMemoryControlStore()
        jobs = types.SimpleNamespace(
            start=AsyncMock(),
            get=AsyncMock(),
            list=AsyncMock(),
            stop=AsyncMock(),
        )
        policy = self._policy()
        request = self.models.StartRequest(
            jobType="import",
            idempotencyKey="key-1",
            inputRef="https://input.example.invalid/input.json",
            callbackAlias="callback",
        )
        clock_now = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)

        class _Clock:
            def __call__(self) -> datetime:
                return clock_now

        orchestrator = self.Orchestrator(store, jobs, policy, _Clock(), telemetry=telemetry)
        task = self._new_task()
        job = self.orchestrator_module.AcaExecution(
            execution_id="exec-1",
            status="Processing",
            start_time=clock_now,
            args=["--owner-scope", "scope-a", "--task-id", str(task.task_id)],
        )
        jobs.start.return_value = job

        first = self.run_async(orchestrator.start(request, "scope-a"))
        second = self.run_async(orchestrator.start(request, "scope-a"))
        self.assertEqual(first.task_id, second.task_id)
        self.assertTrue(any(call[0] == "duplicate" for call in telemetry.calls))
        self.assertTrue(any(call[0] == "orchestrator.start" for call in telemetry.calls))
        for _, attrs, _, _ in telemetry.calls:
            self.assertNotIn("key-1", str(attrs))
            self.assertNotIn("https://input.example.invalid/input.json", str(attrs))

        self.run_async(orchestrator.cancel("scope-a", str(first.task_id)))
        self.assertTrue(any(call[0] == "cancellation" for call in telemetry.calls))

        # Force a retrying store mutation so the ETag conflict counter is recorded.
        retry_store = _FlakyStore(self.InMemoryControlStore(), self.control_store.ConcurrencyError, fail_replace_times=1)
        orchestrator = self.Orchestrator(retry_store, jobs, policy, _Clock(), telemetry=telemetry)
        jobs.start.reset_mock()
        jobs.start.return_value = job
        self.run_async(orchestrator.start(request, "scope-a"))
        self.assertTrue(any(call[0] == "etag_conflict" for call in telemetry.calls))

        mismatch_store = self.InMemoryControlStore()
        mismatch_orchestrator = self.Orchestrator(mismatch_store, jobs, policy, _Clock(), telemetry=telemetry)
        jobs.start.reset_mock()
        jobs.start.side_effect = self.PublicError("DEPLOYMENT_CONTRACT_MISMATCH", "deployment contract mismatch")
        with self.assertRaises(self.PublicError):
            self.run_async(mismatch_orchestrator.start(request, "scope-a"))
        self.assertTrue(any(call[0] == "digest_mismatch" for call in telemetry.calls))

    def test_worker_records_safe_claim_output_and_callback_paths(self) -> None:
        telemetry = _FakeTelemetry()
        store = self.InMemoryControlStore()
        output = _FakeOutputStore()
        callbacks = _FakeCallbackSender(self.PublicError)
        handler = _FakeHandler(result={"kind": "metadata"})
        policy = self._policy()
        clock_now = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
        worker = self.JobWorker(store, output, handler, callbacks, policy, lambda: clock_now, telemetry=telemetry)
        task = self._new_task()
        self.run_async(store.create_or_get(task))
        current = self.run_async(store.get(task.owner_scope, str(task.task_id)))
        self.run_async(store.replace(current.model_copy(update={"lifecycle_state": self.LifecycleState.RUNNING}), current.etag))

        self.run_async(worker.run(task.owner_scope, str(task.task_id), execution_id="exec-1"))
        self.assertTrue(any(call[0] == "worker.claim" for call in telemetry.calls))
        self.assertTrue(any(call[0] == "worker.business" for call in telemetry.calls))
        self.assertTrue(any(call[0] == "worker.output" for call in telemetry.calls))
        self.assertTrue(any(call[0] == "worker.callback" for call in telemetry.calls))
        for _, attrs, _, _ in telemetry.calls:
            self.assertNotIn("https://input.example.invalid/input.json", str(attrs))
            self.assertNotIn("metadata", str(attrs))
            self.assertNotIn("secret", str(attrs))

        # Callback exhaustion and digest mismatch counters are recorded via the record API.
        self.assertTrue(any(call[0] == "callback_exhaustion" for call in telemetry.calls))

    def test_worker_failure_records_failure_and_avoids_sensitive_log_values(self) -> None:
        telemetry = _FakeTelemetry()
        store = self.InMemoryControlStore()
        output = _FakeOutputStore()
        callbacks = _FakeCallbackSender(self.PublicError)
        policy = self._policy()
        clock_now = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
        handler = _FakeHandler(exc=RuntimeError("input=https://input.example.invalid?token=secret"))
        worker = self.JobWorker(store, output, handler, callbacks, policy, lambda: clock_now, telemetry=telemetry)
        task = self._new_task()
        self.run_async(store.create_or_get(task))
        current = self.run_async(store.get(task.owner_scope, str(task.task_id)))
        self.run_async(store.replace(current.model_copy(update={"lifecycle_state": self.LifecycleState.RUNNING}), current.etag))

        self.run_async(worker.run(task.owner_scope, str(task.task_id), execution_id="exec-2"))
        self.assertTrue(any(call[2] == "failure" for call in telemetry.calls if call[0] == "worker.business"))
        joined = str(telemetry.calls)
        self.assertNotIn("secret", joined)
        self.assertNotIn("token=", joined)


class _FakeOutputStore:
    def __init__(self) -> None:
        self.urls: dict[str, str] = {}
        self.write_calls: list[tuple[str, Any, bool]] = []
        self.exists_calls: list[str] = []
        self.get_calls: list[str] = []

    async def exists(self, path: str) -> bool:
        self.exists_calls.append(path)
        return path in self.urls

    async def get(self, path: str) -> str:
        self.get_calls.append(path)
        return self.urls[path]

    async def write_json(self, path: str, payload: Any, overwrite: bool = False) -> str:
        self.write_calls.append((path, payload, overwrite))
        url = f"https://result.example.invalid/{path}"
        self.urls[path] = url
        return url


class _FakeCallbackSender:
    def __init__(self, error_cls: type[BaseException]) -> None:
        self.calls: list[tuple[Any, dict[str, str]]] = []
        self.error_cls = error_cls

    async def send(self, policy: Any, payload: dict[str, str]) -> None:
        self.calls.append((policy, payload))
        raise self.error_cls("CALLBACK_DELIVERY_EXHAUSTED", "callback delivery exhausted")


class _FakeHandler:
    def __init__(self, *, result: Any = None, exc: BaseException | None = None) -> None:
        self.result = result or {"kind": "metadata"}
        self.exc = exc
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, input_ref: str, task_id: str) -> Any:
        self.calls.append((input_ref, task_id))
        if self.exc is not None:
            raise self.exc
        return self.result


if __name__ == "__main__":
    unittest.main()

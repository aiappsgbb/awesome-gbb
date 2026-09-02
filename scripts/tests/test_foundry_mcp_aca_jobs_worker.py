#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs job worker."""

from __future__ import annotations

import asyncio
import importlib
import os
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

    class _BlobClient:
        def __init__(self, url: str) -> None:
            self.url = url
            self.upload_blob = AsyncMock()
            self.exists = AsyncMock(return_value=True)

    class _ContainerClient:
        def __init__(self, url: str) -> None:
            self.url = url
            self._blob_clients: dict[str, _BlobClient] = {}
            self.close = AsyncMock()

        @classmethod
        def from_container_url(cls, url: str, credential: Any | None = None) -> "_ContainerClient":
            client = cls(url)
            client.credential = credential
            return client

        def get_blob_client(self, path: str) -> _BlobClient:
            client = self._blob_clients.get(path)
            if client is None:
                client = _BlobClient(f"{self.url.rstrip('/')}/{path}")
                self._blob_clients[path] = client
            return client

    class _ContainerProxy:
        def __init__(self) -> None:
            self.create_item = AsyncMock()
            self.read_item = AsyncMock()
            self.replace_item = AsyncMock()

    class _DatabaseProxy:
        def __init__(self) -> None:
            self.container = _ContainerProxy()
            self.calls: list[str] = []

        def get_container_client(self, name: str) -> _ContainerProxy:
            self.calls.append(name)
            return self.container

    class _CosmosClient(_AsyncCloseable):
        def __init__(self, endpoint: str, credential: Any) -> None:
            super().__init__(endpoint, credential)
            self.endpoint = endpoint
            self.credential = credential
            self.database = _DatabaseProxy()

        async def __aenter__(self) -> "_CosmosClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            await self.close()

        def get_database_client(self, name: str) -> _DatabaseProxy:
            self.database.calls.append(name)
            return self.database

    class _AsyncClient(_AsyncCloseable):
        async def __aenter__(self) -> "_AsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            await self.close()

    class _HttpResponseError(Exception):
        def __init__(self, message: str = "", *, status_code: int | None = None, response: Any | None = None) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.response = response

    class _ResourceExistsError(Exception):
        pass

    class _MatchConditions:
        IfNotModified = "IfNotModified"

    _ensure_class("azure.core.exceptions", "HttpResponseError", _HttpResponseError)
    _ensure_class("azure.core.exceptions", "ResourceExistsError", _ResourceExistsError)
    _ensure_class("azure.core", "MatchConditions", _MatchConditions)  # type: ignore[arg-type]
    class _ContainerAppsAPIClient:
        pass

    _ensure_class("azure.mgmt.appcontainers", "ContainerAppsAPIClient", _ContainerAppsAPIClient)
    _ensure_class("azure.identity.aio", "ManagedIdentityCredential", _ManagedIdentityCredential)
    _ensure_class("azure.keyvault.secrets.aio", "SecretClient", _SecretClient)
    _ensure_class("azure.storage.blob.aio", "ContainerClient", _ContainerClient)
    _ensure_class("azure.cosmos.aio", "CosmosClient", _CosmosClient)
    _ensure_class("httpx", "AsyncClient", _AsyncClient)  # type: ignore[arg-type]


_ensure_azure_worker_stubs()

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


class _FakeBlobClient:
    def __init__(self, url: str, *, exists: bool = True) -> None:
        self.url = url
        self.upload_blob = AsyncMock()
        self.exists = AsyncMock(return_value=exists)


class _FakeContainerClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.close = AsyncMock()
        self._blob_clients: dict[str, _FakeBlobClient] = {}

    def get_blob_client(self, path: str) -> _FakeBlobClient:
        client = self._blob_clients.get(path)
        if client is None:
            client = _FakeBlobClient(f"{self.url.rstrip('/')}/{path}")
            self._blob_clients[path] = client
        return client


class _FakeDatabaseProxy:
    def __init__(self, container: Any) -> None:
        self.container = container
        self.calls: list[str] = []

    def get_container_client(self, name: str) -> Any:
        self.calls.append(name)
        return self.container


class _FakeCosmosClient:
    def __init__(self, endpoint: str, credential: Any, container: Any | None = None) -> None:
        self.endpoint = endpoint
        self.credential = credential
        self.close = AsyncMock()
        self.database = _FakeDatabaseProxy(container or object())
        self.database_names: list[str] = []

    async def __aenter__(self) -> "_FakeCosmosClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def get_database_client(self, name: str) -> _FakeDatabaseProxy:
        self.database_names.append(name)
        return self.database


class _FakeCredential:
    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.close = AsyncMock()


class _FakeHttpClient:
    def __init__(self) -> None:
        self.close = AsyncMock()
        self.aclose = AsyncMock()


class _FakeSecretClient:
    def __init__(self, vault_url: str, credential: Any) -> None:
        self.vault_url = vault_url
        self.credential = credential
        self.calls: list[str] = []
        self.aclose = AsyncMock()

    async def get_secret(self, name: str) -> Any:
        self.calls.append(name)
        return types.SimpleNamespace(value=f"secret:{name}")


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
        sleep: Any | None = None,
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
            sleep=sleep or AsyncMock(),
            lease=lease,
        )
        return worker, store, handler, callback_sender, output

    async def _seed_task(self, store: Any, task: TaskRecord | None = None) -> TaskRecord:
        task = task or self.task
        return await store.create_or_get(task)

    def test_blob_output_store_result_path_and_query_free_url(self) -> None:
        module = self._module()
        self.assertEqual(module.BlobOutputStore.result_path("task-1"), "results/task-1/result.json")

        container = _FakeContainerClient("https://results.example.com/container")
        output = module.BlobOutputStore(container)
        blob = container.get_blob_client("results/task-1/result.json")
        blob.url = "https://results.example.com/container/results/task-1/result.json?sig=secret"

        self.assertTrue(asyncio.run(output.exists("results/task-1/result.json")))
        self.assertEqual(asyncio.run(output.get("results/task-1/result.json")), "https://results.example.com/container/results/task-1/result.json")

    def test_blob_output_store_write_json_overwrites_false_and_sets_application_json(self) -> None:
        module = self._module()
        container = _FakeContainerClient("https://results.example.com/container")
        output = module.BlobOutputStore(container)
        blob = container.get_blob_client("results/task-1/result.json")
        blob.url = "https://results.example.com/container/results/task-1/result.json?sig=secret"

        result = asyncio.run(output.write_json("results/task-1/result.json", {"b": 2, "a": "x"}, overwrite=False))

        self.assertEqual(result, "https://results.example.com/container/results/task-1/result.json")
        blob.upload_blob.assert_awaited_once()
        args = blob.upload_blob.await_args
        self.assertEqual(args.args[0], b'{"a":"x","b":2}')
        self.assertEqual(args.kwargs["overwrite"], False)
        self.assertEqual(args.kwargs["content_type"], "application/json")

    def test_blob_output_store_get_missing_raises_and_exists_passthrough(self) -> None:
        module = self._module()
        container = _FakeContainerClient("https://results.example.com/container")
        output = module.BlobOutputStore(container)
        blob = container.get_blob_client("results/task-2/result.json")
        blob.exists = AsyncMock(return_value=False)

        with self.assertRaises(FileNotFoundError):
            asyncio.run(output.get("results/task-2/result.json"))
        self.assertEqual(asyncio.run(output.exists("results/task-2/result.json")), False)

        blob.exists = AsyncMock(return_value=True)
        blob.url = "https://results.example.com/container/results/task-2/result.json?query=secret"
        self.assertEqual(
            asyncio.run(output.get("results/task-2/result.json")),
            "https://results.example.com/container/results/task-2/result.json",
        )

    def test_build_worker_from_env_accepts_injected_store_output_and_sender(self) -> None:
        module = self._module()
        store = _RecordingStore()
        output = _FakeContainerClient("https://results.example.com/container")
        sender = object()
        env = {
            "MCP_ACA_JOBS_JOB_TYPE": "batch",
            "MCP_ACA_JOBS_JOB_RESOURCE_GROUP": "rg",
            "MCP_ACA_JOBS_JOB_NAME": "batch-job",
            "MCP_ACA_JOBS_JOB_CONTAINER_NAME": "worker",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": "registry.azurecr.io/work@sha256:" + "a" * 64,
            "MCP_ACA_JOBS_CALLBACK_URL": "https://hooks.example.com/jobs",
            "MCP_ACA_JOBS_CALLBACK_AUDIENCE": "api://mcp-callback",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://results.example.com/container",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(module.BlobOutputStore, "from_container_url") as from_container_url:
            worker = module.build_worker_from_env(store, output=output, callback_sender=sender, config=module.load_runtime_config_from_env())

        self.assertIs(worker._store, store)
        self.assertIs(worker._output, output)
        self.assertIs(worker._callback_sender, sender)
        from_container_url.assert_not_called()

    async def test_run_from_env_uses_managed_identity_defaults_and_shared_clients(self) -> None:
        module = self._module()
        fake_worker = types.SimpleNamespace(run=AsyncMock(return_value=17))
        fake_output = _FakeContainerClient("https://results.example.com/container")
        fake_credential = _FakeCredential("client-1")
        fake_http_client = _FakeHttpClient()
        fake_cosmos_container = object()
        fake_cosmos_client = _FakeCosmosClient("https://cosmos.example.com", fake_credential, container=fake_cosmos_container)
        fake_db_proxy = fake_cosmos_client.database
        fake_sender = object()
        env = {
            "AZURE_CLIENT_ID": "client-1",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "db-1",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "container-1",
            "MCP_ACA_JOBS_JOB_TYPE": "batch",
            "MCP_ACA_JOBS_JOB_RESOURCE_GROUP": "rg",
            "MCP_ACA_JOBS_JOB_NAME": "batch-job",
            "MCP_ACA_JOBS_JOB_CONTAINER_NAME": "worker",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": "registry.azurecr.io/work@sha256:" + "a" * 64,
            "MCP_ACA_JOBS_CALLBACK_URL": "https://hooks.example.com/jobs",
            "MCP_ACA_JOBS_CALLBACK_AUDIENCE": "api://mcp-callback",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://results.example.com/container",
            "CONTAINER_APP_JOB_EXECUTION_NAME": "job-exec-1",
            "MCP_ACA_JOBS_LEASE_MINUTES": "5",
        }
        with patch.dict(os.environ, env, clear=False), \
            patch.object(module, "ManagedIdentityCredential", return_value=fake_credential) as credential_ctor, \
            patch.object(module, "CosmosClient", return_value=fake_cosmos_client) as cosmos_ctor, \
            patch.object(module.BlobOutputStore, "from_container_url", return_value=fake_output) as blob_ctor, \
            patch.object(module.httpx, "AsyncClient", return_value=fake_http_client) as http_ctor, \
            patch.object(module, "CallbackSender", return_value=fake_sender) as sender_ctor, \
            patch.object(module, "CosmosControlStore", return_value="store-from-cosmos") as store_ctor, \
            patch.object(module, "build_worker_from_env", return_value=fake_worker) as build_worker_ctor:
            result = await module._run_from_env("scope-a", "task-1")

        self.assertEqual(result, 17)
        credential_ctor.assert_called_once_with(client_id="client-1")
        cosmos_ctor.assert_called_once_with(endpoint="https://cosmos.example.com", credential=fake_credential)
        self.assertEqual(fake_cosmos_client.database_names, ["db-1"])
        self.assertEqual(fake_db_proxy.calls, ["container-1"])
        blob_ctor.assert_called_once_with("https://results.example.com/container", credential=fake_credential)
        http_ctor.assert_called_once_with()
        sender_ctor.assert_called_once_with(fake_http_client, fake_credential, secret_client=None)
        store_ctor.assert_called_once_with(fake_cosmos_container)
        build_worker_ctor.assert_called_once()
        _, build_kwargs = build_worker_ctor.call_args
        self.assertEqual(build_kwargs["output"], fake_output)
        self.assertIs(build_kwargs["callback_sender"], fake_sender)
        self.assertIs(build_kwargs["credential"], fake_credential)
        self.assertEqual(build_kwargs["config"].lease, timedelta(minutes=5))
        fake_worker.run.assert_awaited_once_with("scope-a", "task-1", "job-exec-1")
        fake_http_client.aclose.assert_awaited()
        fake_credential.close.assert_awaited()
        fake_output.close.assert_awaited()

    async def test_run_from_env_uses_key_vault_secret_client_when_configured(self) -> None:
        module = self._module()
        fake_worker = types.SimpleNamespace(run=AsyncMock(return_value=19))
        fake_output = _FakeContainerClient("https://results.example.com/container")
        fake_credential = _FakeCredential("client-1")
        fake_http_client = _FakeHttpClient()
        fake_cosmos_client = _FakeCosmosClient("https://cosmos.example.com", fake_credential, container=object())
        fake_sender = object()
        fake_secret_client = _FakeSecretClient("https://vault.example.com", fake_credential)
        env = {
            "AZURE_CLIENT_ID": "client-1",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "db-1",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "container-1",
            "MCP_ACA_JOBS_JOB_TYPE": "batch",
            "MCP_ACA_JOBS_JOB_RESOURCE_GROUP": "rg",
            "MCP_ACA_JOBS_JOB_NAME": "batch-job",
            "MCP_ACA_JOBS_JOB_CONTAINER_NAME": "worker",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": "registry.azurecr.io/work@sha256:" + "a" * 64,
            "MCP_ACA_JOBS_CALLBACK_URL": "https://hooks.example.com/jobs",
            "MCP_ACA_JOBS_CALLBACK_AUTH_MODE": "key_vault",
            "MCP_ACA_JOBS_CALLBACK_VAULT_URL": "https://vault.example.com",
            "MCP_ACA_JOBS_CALLBACK_SECRET_NAME": "callback-secret",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://results.example.com/container",
            "CONTAINER_APP_JOB_EXECUTION_NAME": "job-exec-1",
            "MCP_ACA_JOBS_LEASE_MINUTES": "7",
        }
        with patch.dict(os.environ, env, clear=False), \
            patch.object(module, "ManagedIdentityCredential", return_value=fake_credential) as credential_ctor, \
            patch.object(module, "CosmosClient", return_value=fake_cosmos_client) as cosmos_ctor, \
            patch.object(module.BlobOutputStore, "from_container_url", return_value=fake_output) as blob_ctor, \
            patch.object(module.httpx, "AsyncClient", return_value=fake_http_client) as http_ctor, \
            patch.object(module, "SecretClient", return_value=fake_secret_client) as secret_ctor, \
            patch.object(module, "CallbackSender", return_value=fake_sender) as sender_ctor, \
            patch.object(module, "CosmosControlStore", return_value="store-from-cosmos") as store_ctor, \
            patch.object(module, "build_worker_from_env", return_value=fake_worker) as build_worker_ctor:
            result = await module._run_from_env("scope-a", "task-1")

        self.assertEqual(result, 19)
        credential_ctor.assert_called_once_with(client_id="client-1")
        cosmos_ctor.assert_called_once_with(endpoint="https://cosmos.example.com", credential=fake_credential)
        self.assertEqual(fake_cosmos_client.database_names, ["db-1"])
        blob_ctor.assert_called_once_with("https://results.example.com/container", credential=fake_credential)
        http_ctor.assert_called_once_with()
        secret_ctor.assert_called_once_with(vault_url="https://vault.example.com", credential=fake_credential)
        sender_ctor.assert_called_once_with(fake_http_client, fake_credential, secret_client=fake_secret_client)
        store_ctor.assert_called_once()
        build_worker_ctor.assert_called_once()
        _, build_kwargs = build_worker_ctor.call_args
        self.assertEqual(build_kwargs["config"].lease, timedelta(minutes=7))
        fake_worker.run.assert_awaited_once_with("scope-a", "task-1", "job-exec-1")
        fake_http_client.aclose.assert_awaited()
        fake_secret_client.aclose.assert_awaited()
        fake_credential.close.assert_awaited()
        fake_output.close.assert_awaited()

    async def test_run_from_env_requires_official_job_execution_name(self) -> None:
        module = self._module()
        fake_worker = types.SimpleNamespace(run=AsyncMock(return_value=17))
        fake_output = _FakeContainerClient("https://results.example.com/container")
        fake_credential = _FakeCredential("client-1")
        fake_http_client = _FakeHttpClient()
        fake_cosmos_client = _FakeCosmosClient("https://cosmos.example.com", fake_credential, container=object())
        fake_sender = object()
        env = {
            "AZURE_CLIENT_ID": "client-1",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "db-1",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "container-1",
            "MCP_ACA_JOBS_JOB_TYPE": "batch",
            "MCP_ACA_JOBS_JOB_RESOURCE_GROUP": "rg",
            "MCP_ACA_JOBS_JOB_NAME": "batch-job",
            "MCP_ACA_JOBS_JOB_CONTAINER_NAME": "worker",
            "MCP_ACA_JOBS_JOB_IMAGE_DIGEST": "registry.azurecr.io/work@sha256:" + "a" * 64,
            "MCP_ACA_JOBS_CALLBACK_URL": "https://hooks.example.com/jobs",
            "MCP_ACA_JOBS_CALLBACK_AUDIENCE": "api://mcp-callback",
            "MCP_ACA_JOBS_OUTPUT_CONTAINER_URL": "https://results.example.com/container",
        }
        with patch.dict(os.environ, env, clear=False), \
            patch.object(module, "ManagedIdentityCredential", return_value=fake_credential), \
            patch.object(module, "CosmosClient", return_value=fake_cosmos_client), \
            patch.object(module.BlobOutputStore, "from_container_url", return_value=fake_output), \
            patch.object(module.httpx, "AsyncClient", return_value=fake_http_client), \
            patch.object(module, "CallbackSender", return_value=fake_sender), \
            patch.object(module, "CosmosControlStore", return_value="store-from-cosmos"), \
            patch.object(module, "build_worker_from_env", return_value=fake_worker):
            with self.assertRaises(KeyError):
                await module._run_from_env("scope-a", "task-1")

    async def test_first_worker_claims_runs_handler_persists_result_and_sends_exact_callback(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        await self._seed_task(store, self.task.model_copy(update={"aca_execution_id": None}))

        execution_id = "execution-real-1"
        code = await worker.run("scope-a", str(self.task.task_id), execution_id)

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
                "acaExecutionId": execution_id,
                "status": "Succeeded",
                "resultUrl": output.urls[self._task_path(str(self.task.task_id))],
            },
        )
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.aca_execution_id, execution_id)
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
        self.assertEqual(store.replace_calls[0][0].aca_execution_id, execution_id)
        self.assertEqual(
            store.replace_calls[0][0].worker_claim_expires_at,
            self.fixed_now + timedelta(minutes=5),
        )

    async def test_conflicting_execution_id_fails_without_handler(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        await self._seed_task(store)

        code = await worker.run("scope-a", str(self.task.task_id), "execution-2")

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(callback_sender.calls, [])
        self.assertEqual(output.write_calls, [])
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.FAILED)
        self.assertEqual(current.error_code, "WORKER_EXECUTION_ID_MISMATCH")
        self.assertIsNone(current.result_url)
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.NOT_STARTED)

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

    async def test_callback_rejection_preserves_success_and_marks_exhausted(self) -> None:
        class _RejectedCallbackSender(_FakeCallbackSender):
            async def send(self, policy: Any, payload: dict[str, str]) -> None:
                self.calls.append((policy, payload))
                raise PublicError("CALLBACK_DELIVERY_REJECTED", "callback delivery rejected")

        worker, store, handler, callback_sender, output = await self._build_worker(
            callback_sender=_RejectedCallbackSender()
        )
        await self._seed_task(store)

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        self.assertIsNone(current.error_code)
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.EXHAUSTED)
        self.assertEqual(current.callback_error_code, "CALLBACK_DELIVERY_REJECTED")
        self.assertIsNotNone(current.result_url)
        self.assertEqual(len(callback_sender.calls), 1)
        self.assertEqual(len(handler.calls), 1)
        self.assertEqual(len(output.write_calls), 1)

    async def test_succeeded_pending_without_execution_id_polls_then_returns_without_callback(self) -> None:
        sleep = AsyncMock()
        worker, store, handler, callback_sender, output = await self._build_worker(sleep=sleep)
        await self._seed_task(
            store,
            self.task.model_copy(
                update={
                    "lifecycle_state": self.LifecycleState.SUCCEEDED,
                    "callback_delivery_state": self.CallbackDeliveryState.PENDING,
                    "result_url": self.policy.validate_result("https://results.example.com/results/task/result.json"),
                    "aca_execution_id": None,
                }
            ),
        )

        code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(code, 0)
        self.assertEqual(handler.calls, [])
        self.assertEqual(callback_sender.calls, [])
        self.assertEqual(output.write_calls, [])
        self.assertEqual(len(store.get_calls), 6)
        self.assertEqual(sleep.await_count, 5)
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.PENDING)
        self.assertIsNone(current.aca_execution_id)

    async def test_succeeded_pending_with_later_execution_id_delivers_callback_on_second_run(self) -> None:
        worker, store, handler, callback_sender, output = await self._build_worker()
        await self._seed_task(
            store,
            self.task.model_copy(
                update={
                    "lifecycle_state": self.LifecycleState.SUCCEEDED,
                    "callback_delivery_state": self.CallbackDeliveryState.PENDING,
                    "result_url": self.policy.validate_result("https://results.example.com/results/task/result.json"),
                    "aca_execution_id": None,
                }
            ),
        )

        first_code = await worker.run("scope-a", str(self.task.task_id))
        self.assertEqual(first_code, 0)
        self.assertEqual(callback_sender.calls, [])
        current = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(current.callback_delivery_state, self.CallbackDeliveryState.PENDING)

        await store.replace(
            current.model_copy(update={"aca_execution_id": "execution-77"}),
            current.etag,
        )

        second_code = await worker.run("scope-a", str(self.task.task_id))

        self.assertEqual(second_code, 0)
        self.assertEqual(len(callback_sender.calls), 1)
        _, payload = callback_sender.calls[0]
        self.assertEqual(payload["acaExecutionId"], "execution-77")
        self.assertEqual(payload["taskId"], str(self.task.task_id))
        self.assertEqual(current.lifecycle_state, self.LifecycleState.SUCCEEDED)
        final = await store.get("scope-a", str(self.task.task_id))
        self.assertEqual(final.callback_delivery_state, self.CallbackDeliveryState.DELIVERED)
        self.assertEqual(final.aca_execution_id, "execution-77")
        self.assertEqual(handler.calls, [])
        self.assertEqual(output.write_calls, [])

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

    def test_main_parses_args_and_runs_async_entrypoint(self) -> None:
        module = self._module()
        sentinel = object()
        with patch.object(module, "_run_from_env", new=unittest.mock.Mock(return_value=sentinel)) as run_from_env, patch.object(
            module.asyncio, "run", return_value=42
        ) as asyncio_run:
            result = module.main(["--owner-scope", "scope-a", "--task-id", "task-1"])

        self.assertEqual(result, 42)
        run_from_env.assert_called_once_with("scope-a", "task-1")
        asyncio_run.assert_called_once_with(sentinel)

    def test_module_help_mentions_required_arguments(self) -> None:
        module = self._module()
        help_text = module.build_arg_parser().format_help()
        self.assertIn("--owner-scope", help_text)
        self.assertIn("--task-id", help_text)


if __name__ == "__main__":
    unittest.main()

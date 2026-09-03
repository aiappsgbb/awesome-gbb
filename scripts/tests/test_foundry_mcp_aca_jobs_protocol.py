#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs SEP-2663 adapter."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import os
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
APP_DIR = SKILL_DIR / "app"
sys.path.insert(0, str(SKILL_DIR))

_STUBBED_MODULE_NAMES = (
    "azure",
    "azure.core",
    "azure.core.exceptions",
    "azure.identity",
    "azure.identity.aio",
    "azure.cosmos",
    "azure.cosmos.aio",
    "azure.storage",
    "azure.storage.blob",
    "azure.storage.blob.aio",
    "azure.mgmt",
    "azure.mgmt.appcontainers",
    "fastmcp",
    "fastmcp.server",
    "fastmcp.server.context",
    "fastmcp.server.extensions",
    "fastmcp.server.dependencies",
    "fastmcp.utilities",
    "fastmcp.utilities.tests",
    "fastmcp.utilities.tasks",
    "fastmcp_tasks",
    "fastmcp_tasks.models",
    "fastmcp_tasks.wire_production",
    "mcp",
    "mcp.server",
    "mcp.server.context",
    "mcp.shared",
    "mcp.shared.exceptions",
    "mcp.shared.inbound",
    "mcp_types",
    "mcp_types.jsonrpc",
    "mcp_types.version",
    "starlette",
    "starlette.requests",
    "starlette.responses",
)
_MISSING_MODULE = object()
_MODULES_BEFORE_STUBS = {
    name: sys.modules.get(name, _MISSING_MODULE) for name in _STUBBED_MODULE_NAMES
}
_ATTRIBUTES_BEFORE_STUBS = {
    (module_name, attribute): getattr(module, attribute, _MISSING_MODULE)
    for module_name, attribute in (
        ("azure.core.exceptions", "HttpResponseError"),
        ("azure.core.exceptions", "ResourceExistsError"),
        ("azure.identity.aio", "DefaultAzureCredential"),
    )
    if (module := sys.modules.get(module_name)) is not None
}
_ACTIVE_STUB_MODULES: dict[str, types.ModuleType] = {}


def _ensure_package(name: str, *, path: list[str] | None = None) -> types.ModuleType:
    if name in _STUBBED_MODULE_NAMES:
        module = _ACTIVE_STUB_MODULES.get(name)
        if module is None:
            module = types.ModuleType(name)
            module.__path__ = []  # type: ignore[attr-defined]
            _ACTIVE_STUB_MODULES[name] = module
            sys.modules[name] = module
        if path is not None:
            module.__path__ = path  # type: ignore[attr-defined]
        return module

    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = [] if path is None else path  # type: ignore[attr-defined]
        sys.modules[name] = module
    if path is not None:
        module.__path__ = path  # type: ignore[attr-defined]
    return module


def _restore_stubbed_modules() -> None:
    for name, original in _MODULES_BEFORE_STUBS.items():
        if original is _MISSING_MODULE:
            if sys.modules.get(name) is _ACTIVE_STUB_MODULES.get(name):
                sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _install_stubs() -> None:
    _ensure_package("app", path=[str(APP_DIR)])

    azure = _ensure_package("azure")
    azure_core = _ensure_package("azure.core")
    azure_core_exceptions = _ensure_package("azure.core.exceptions")
    azure_identity = _ensure_package("azure.identity")
    azure_identity_aio = _ensure_package("azure.identity.aio")
    azure_cosmos = _ensure_package("azure.cosmos")
    azure_cosmos_aio = _ensure_package("azure.cosmos.aio")
    azure_storage = _ensure_package("azure.storage")
    azure_storage_blob = _ensure_package("azure.storage.blob")
    azure_storage_blob_aio = _ensure_package("azure.storage.blob.aio")
    azure_mgmt = _ensure_package("azure.mgmt")
    azure_appcontainers = _ensure_package("azure.mgmt.appcontainers")

    class MatchConditions:
        IfNotModified = "IfNotModified"

    class HttpResponseError(Exception):
        def __init__(self, message: object | None = None, response: object | None = None, **_: Any) -> None:
            super().__init__(message)
            self.response = response
            self.status_code = getattr(response, "status_code", None)

    class ResourceExistsError(Exception):
        pass

    class ManagedIdentityCredential:
        def __init__(self, client_id: str | None = None) -> None:
            self.client_id = client_id
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class AsyncManagedIdentityCredential:
        def __init__(self, client_id: str | None = None) -> None:
            self.client_id = client_id
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    class CosmosContainer:
        def __init__(self, name: str) -> None:
            self.name = name
            self.records: dict[tuple[str, str], dict[str, Any]] = {}

        async def create_item(self, body: dict[str, Any]) -> dict[str, Any]:
            self.records[(body["ownerScope"], body["id"])] = body
            return body

        async def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
            return self.records[(partition_key, item)]

        async def replace_item(
            self,
            *,
            item: str,
            body: dict[str, Any],
            etag: str | None,
            match_condition: Any = None,
        ) -> dict[str, Any]:
            self.records[(body["ownerScope"], item)] = body
            return body

    class CosmosDatabase:
        def __init__(self, name: str) -> None:
            self.name = name
            self.containers: dict[str, CosmosContainer] = {}

        def get_container_client(self, name: str) -> CosmosContainer:
            container = self.containers.get(name)
            if container is None:
                container = CosmosContainer(name)
                self.containers[name] = container
            return container

    class CosmosClient:
        def __init__(self, endpoint: str, credential: Any | None = None) -> None:
            self.endpoint = endpoint
            self.credential = credential
            self.databases: dict[str, CosmosDatabase] = {}
            self.closed = False

        def get_database_client(self, name: str) -> CosmosDatabase:
            database = self.databases.get(name)
            if database is None:
                database = CosmosDatabase(name)
                self.databases[name] = database
            return database

        async def close(self) -> None:
            self.closed = True

    class FakeBlobClient:
        def __init__(self, path: str) -> None:
            self.path = path
            self.uploads: list[dict[str, Any]] = []
            self.payload: bytes | None = None

        async def upload_blob(self, data: Any, overwrite: bool = False) -> None:
            if self.payload is not None and not overwrite:
                raise ResourceExistsError("blob already exists")
            payload = data if isinstance(data, bytes) else bytes(data)
            self.uploads.append({"data": payload, "overwrite": overwrite})
            self.payload = payload

        def download_blob(self) -> Any:
            payload = self.payload or b""

            class _Downloader:
                def __init__(self, data: bytes) -> None:
                    self._data = data

                async def readall(self) -> bytes:
                    return self._data

            return _Downloader(payload)

    class ContainerClient:
        def __init__(self, url: str, credential: Any | None = None) -> None:
            self.url = url
            self.credential = credential
            self.closed = False
            self.blobs: dict[str, FakeBlobClient] = {}

        @classmethod
        def from_container_url(cls, url: str, credential: Any | None = None) -> "ContainerClient":
            return cls(url, credential)

        def get_blob_client(self, path: str) -> FakeBlobClient:
            blob = self.blobs.get(path)
            if blob is None:
                blob = FakeBlobClient(path)
                self.blobs[path] = blob
            return blob

        async def close(self) -> None:
            self.closed = True

    class ContainerAppsAPIClient:
        def __init__(self, credential: Any | None = None, subscription_id: str | None = None) -> None:
            self.credential = credential
            self.subscription_id = subscription_id
            self.jobs = types.SimpleNamespace(
                get=MagicMock(),
                begin_start=MagicMock(),
                begin_stop_execution=MagicMock(),
            )
            self.jobs_executions = types.SimpleNamespace(list=MagicMock())

    azure_core.MatchConditions = MatchConditions
    azure_core_exceptions.HttpResponseError = HttpResponseError
    azure_core_exceptions.ResourceExistsError = ResourceExistsError
    azure_identity.ManagedIdentityCredential = ManagedIdentityCredential
    azure_identity_aio.ManagedIdentityCredential = AsyncManagedIdentityCredential
    azure_cosmos_aio.CosmosClient = CosmosClient
    azure_storage_blob_aio.ContainerClient = ContainerClient
    azure_storage_blob.ContainerClient = ContainerClient
    azure_appcontainers.ContainerAppsAPIClient = ContainerAppsAPIClient
    azure.core = azure_core
    azure.identity = azure_identity
    azure.cosmos = azure_cosmos
    azure.mgmt = azure_mgmt
    azure.storage = azure_storage
    azure_core.exceptions = azure_core_exceptions
    azure_identity.aio = azure_identity_aio
    azure_cosmos.aio = azure_cosmos_aio
    azure_storage.blob = azure_storage_blob
    azure_storage_blob.aio = azure_storage_blob_aio
    azure_mgmt.appcontainers = azure_appcontainers

    fastmcp = _ensure_package("fastmcp")
    server = _ensure_package("fastmcp.server")
    fastmcp_context = _ensure_package("fastmcp.server.context")
    extensions = _ensure_package("fastmcp.server.extensions")
    dependencies = _ensure_package("fastmcp.server.dependencies")
    shared_inbound = _ensure_package("mcp.shared.inbound")
    utilities = _ensure_package("fastmcp.utilities")
    utilities_tests = _ensure_package("fastmcp.utilities.tests")
    utilities_tasks = _ensure_package("fastmcp.utilities.tasks")
    starlette = _ensure_package("starlette")
    starlette_requests = _ensure_package("starlette.requests")
    starlette_responses = _ensure_package("starlette.responses")

    class MethodBinding:
        def __init__(
            self,
            *,
            method: str,
            params_type: type[Any],
            handler: Any,
            protocol_versions: Any = None,
        ) -> None:
            self.method = method
            self.params_type = params_type
            self.handler = handler
            self.protocol_versions = protocol_versions

    class ServerExtension:
        identifier = "stub"

        def __init__(self) -> None:
            self.server = types.SimpleNamespace()

        def client_settings(self, ctx: Any) -> dict[str, Any] | None:
            return ctx.client_extension_settings(self.identifier)

    class Context:
        def __init__(
            self,
            *,
            request_context: Any | None = None,
            settings: dict[str, Any] | None = None,
        ) -> None:
            self.request_context = request_context
            self._settings = settings

        def client_extension_settings(self, identifier: str) -> dict[str, Any] | None:
            if identifier != "io.modelcontextprotocol/tasks":
                return None
            return self._settings

    class PlainTextResponse:
        def __init__(self, content: str = "", status_code: int = 200) -> None:
            self.status_code = status_code
            self.text = content
            self.body = content.encode("utf-8")

    class JSONResponse(PlainTextResponse):
        def __init__(self, content: Any = None, status_code: int = 200) -> None:
            payload = json.dumps(content, ensure_ascii=False)
            super().__init__(payload, status_code=status_code)
            self.content = content

    class FakeRequest:
        def __init__(self, *, headers: dict[str, str] | None = None, json_data: Any = None) -> None:
            self.headers = headers or {}
            self._json_data = json_data
            self._body = json.dumps(json_data, ensure_ascii=False).encode("utf-8") if json_data is not None else b""

        async def json(self) -> Any:
            return self._json_data

        async def body(self) -> bytes:
            return self._body

    class FakeToolResult(types.SimpleNamespace):
        pass

    class FastMCP:
        def __init__(self, name: str, *, lifespan: Any | None = None, tasks: bool = False) -> None:
            self.name = name
            self.lifespan = lifespan
            self.tasks = tasks
            self.tools: dict[str, Any] = {}
            self.routes: dict[tuple[str, str], Any] = {}
            self.extensions: list[Any] = []
            self.run_args: dict[str, Any] | None = None

        def tool(self, fn: Any | None = None, *, name: str | None = None, **_: Any):
            def decorator(func: Any) -> Any:
                self.tools[name or func.__name__] = func
                return func

            return decorator(fn) if fn is not None else decorator

        def custom_route(self, path: str, methods: list[str], name: str | None = None, include_in_schema: bool = True):
            def decorator(func: Any) -> Any:
                for method in methods:
                    self.routes[(path, method.upper())] = func
                return func

            return decorator

        def add_extension(self, extension: Any) -> None:
            self.extensions.append(extension)

        def run(self, *, transport: str, host: str, port: int) -> None:
            self.run_args = {"transport": transport, "host": host, "port": port}

        def client(self, *, headers: dict[str, str] | None = None, task_capability: bool = True) -> "FakeClient":
            return FakeClient(self, headers=headers or {}, task_capability=task_capability)

    class FakeClient:
        def __init__(self, server: FastMCP, *, headers: dict[str, str], task_capability: bool) -> None:
            self._server = server
            self._headers = headers
            self._task_capability = task_capability

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> FakeToolResult:
            async def call_next() -> Any:
                with patch("app.mcp_server.get_http_headers", return_value=self._headers):
                    tool = self._server.tools[name]
                    result = tool(**arguments)
                    if inspect.isawaitable(result):
                        result = await result
                    return result

            ctx = Context(
                request_context=ServerRequestContext(protocol_version="2026-07-28"),
                settings={"enabled": True} if self._task_capability else None,
            )
            params = types.SimpleNamespace(name=name, arguments=arguments)
            for extension in self._server.extensions:
                interceptor = getattr(extension, "intercept_tool_call", None)
                if interceptor is None:
                    continue
                with patch("app.aca_tasks_extension.get_http_headers", return_value=self._headers), patch(
                    "app.aca_tasks_extension.get_http_request", side_effect=RuntimeError("No active HTTP request found.")
                ):
                    outcome = await interceptor(params, ctx, call_next)
                if outcome is not None:
                    return FakeToolResult(data=_dump_tool_result(outcome))
            return FakeToolResult(data=_dump_tool_result(await call_next()))

        async def request(self, method: str, path: str, *, headers: dict[str, str] | None = None, json: Any = None) -> Any:
            route = self._server.routes[(path, method.upper())]
            request = FakeRequest(headers=headers or self._headers, json_data=json)
            outcome = route(request)
            if inspect.isawaitable(outcome):
                outcome = await outcome
            return outcome

    def _dump_tool_result(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(by_alias=True, exclude_none=True)
        if hasattr(value, "dict"):
            return value.dict(by_alias=True, exclude_none=True)
        return value

    extensions.MethodBinding = MethodBinding
    extensions.ServerExtension = ServerExtension
    fastmcp_context.Context = Context
    fastmcp.PlainTextResponse = PlainTextResponse
    fastmcp.JSONResponse = JSONResponse
    fastmcp.FastMCP = FastMCP
    utilities_tests.asgi_client = lambda server: server.client()  # pragma: no cover - helper for parity.
    starlette_requests.Request = FakeRequest
    starlette_responses.PlainTextResponse = PlainTextResponse
    starlette_responses.JSONResponse = JSONResponse
    starlette_responses.Response = PlainTextResponse
    starlette.requests = starlette_requests
    starlette.responses = starlette_responses
    shared_inbound.MCP_NAME_HEADER = "mcp-name"

    def encode_header_value(value: str) -> str:
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return f"=?base64?{encoded}?="

    def decode_header_value(value: str | None) -> str | None:
        if value is None or not value.startswith("=?base64?") or not value.endswith("?="):
            return value
        payload = value[len("=?base64?") : -2]
        try:
            return base64.b64decode(payload, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    shared_inbound.encode_header_value = encode_header_value
    shared_inbound.decode_header_value = decode_header_value

    def get_http_request() -> Any:
        raise RuntimeError("No active HTTP request found.")

    dependencies.get_http_headers = lambda: None
    dependencies.get_http_request = get_http_request
    server.context = fastmcp_context
    server.extensions = extensions
    server.dependencies = dependencies
    fastmcp.server = server
    utilities.tasks = utilities_tasks
    utilities_tasks.TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"

    mcp = _ensure_package("mcp")
    mcp_shared = _ensure_package("mcp.shared")
    mcp_shared.inbound = shared_inbound
    mcp_server = _ensure_package("mcp.server")
    mcp_server_context = _ensure_package("mcp.server.context")
    mcp_exceptions = _ensure_package("mcp.shared.exceptions")

    class MCPError(Exception):
        def __init__(self, *, code: int, message: str, data: Any | None = None) -> None:
            super().__init__(message)
            self.code = code
            self.message = message
            self.data = data

    mcp_exceptions.MCPError = MCPError
    mcp_shared.exceptions = mcp_exceptions
    class ServerRequestContext:
        def __init__(
            self,
            *,
            protocol_version: str,
            settings: dict[str, Any] | None = None,
        ) -> None:
            self.protocol_version = protocol_version
            self._settings = settings

        def client_extension_settings(self, identifier: str) -> dict[str, Any] | None:
            if identifier != "io.modelcontextprotocol/tasks":
                return None
            return self._settings

    mcp_server_context.ServerRequestContext = ServerRequestContext
    mcp_server.context = mcp_server_context
    mcp.shared = mcp_shared
    mcp.server = mcp_server

    mcp_types = _ensure_package("mcp_types")
    mcp_types.INVALID_PARAMS = -32602
    mcp_types.INTERNAL_ERROR = -32603
    mcp_types.RequestParams = BaseModel
    mcp_types.Result = BaseModel
    mcp_types_jsonrpc = _ensure_package("mcp_types.jsonrpc")
    mcp_types_jsonrpc.INVALID_PARAMS = -32602
    mcp_types_jsonrpc.INTERNAL_ERROR = -32603
    mcp_types_jsonrpc.HEADER_MISMATCH = -32020
    mcp_types_jsonrpc.MISSING_REQUIRED_CLIENT_CAPABILITY = -32021
    mcp_types_version = _ensure_package("mcp_types.version")
    mcp_types_version.MODERN_PROTOCOL_VERSIONS = ("2026-07-28",)
    mcp_types.jsonrpc = mcp_types_jsonrpc
    mcp_types.version = mcp_types_version

    fastmcp_tasks = _ensure_package("fastmcp_tasks")
    fastmcp_tasks_models = _ensure_package("fastmcp_tasks.models")
    fastmcp_tasks_wire = _ensure_package("fastmcp_tasks.wire_production")
    fastmcp_tasks.models = fastmcp_tasks_models
    fastmcp_tasks.wire_production = fastmcp_tasks_wire

    class _BaseTaskModel(BaseModel):
        model_config = ConfigDict(populate_by_name=True, extra="forbid")

    class CreateTaskResult(_BaseTaskModel):
        task_id: str = Field(serialization_alias="taskId")
        status: str
        created_at: str = Field(serialization_alias="createdAt")
        last_updated_at: str = Field(serialization_alias="lastUpdatedAt")
        ttl_ms: int | None = Field(serialization_alias="ttlMs")
        poll_interval_ms: int | None = Field(serialization_alias="pollIntervalMs")
        status_message: str | None = Field(default=None, serialization_alias="statusMessage")
        result_type: str = Field(default="task", serialization_alias="resultType")

    class GetTaskResult(_BaseTaskModel):
        task_id: str = Field(serialization_alias="taskId")
        status: str
        created_at: str = Field(serialization_alias="createdAt")
        last_updated_at: str = Field(serialization_alias="lastUpdatedAt")
        ttl_ms: int | None = Field(serialization_alias="ttlMs")
        poll_interval_ms: int | None = Field(serialization_alias="pollIntervalMs")
        status_message: str | None = Field(default=None, serialization_alias="statusMessage")
        result_type: str = Field(default="complete", serialization_alias="resultType")
        result: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        input_requests: dict[str, Any] | None = Field(default=None, serialization_alias="inputRequests")

    class UpdateTaskResult(_BaseTaskModel):
        result_type: str = Field(default="complete", serialization_alias="resultType")

    class CancelTaskResult(_BaseTaskModel):
        result_type: str = Field(default="complete", serialization_alias="resultType")

    class GetTaskParams(_BaseTaskModel):
        task_id: str = Field(alias="taskId")

    class UpdateTaskParams(_BaseTaskModel):
        task_id: str = Field(alias="taskId")
        input_responses: dict[str, Any] = Field(alias="inputResponses")

    CancelTaskParams = GetTaskParams

    def missing_capability_error_data() -> dict[str, Any]:
        return {"requiredCapabilities": {"extensions": {"io.modelcontextprotocol/tasks": {}}}}

    fastmcp_tasks_models.CreateTaskResult = CreateTaskResult
    fastmcp_tasks_models.GetTaskResult = GetTaskResult
    fastmcp_tasks_models.UpdateTaskResult = UpdateTaskResult
    fastmcp_tasks_models.CancelTaskResult = CancelTaskResult
    fastmcp_tasks_models.GetTaskParams = GetTaskParams
    fastmcp_tasks_models.UpdateTaskParams = UpdateTaskParams
    fastmcp_tasks_models.CancelTaskParams = CancelTaskParams
    fastmcp_tasks_models.MISSING_REQUIRED_CLIENT_CAPABILITY = -32021
    fastmcp_tasks_models.missing_capability_error_data = missing_capability_error_data

    fastmcp_tasks_wire.install = AsyncMock()
    fastmcp_tasks_wire.uninstall = AsyncMock()


_install_stubs()
try:
    import app.models as app_models  # noqa: E402
    from app.aca_tasks_extension import AcaTasksExtension  # noqa: E402
    from app import mcp_server as app_mcp_server  # noqa: E402
    from app.aca_jobs import AcaExecution  # noqa: E402
    from app.control_store import InMemoryControlStore  # noqa: E402
    from app.orchestrator import Orchestrator  # noqa: E402
    from app.models import PublicError, StartRequest, TaskRecord  # noqa: E402
    from fastmcp.server.extensions import MethodBinding  # noqa: E402
    from fastmcp.server.context import Context as FastMCPContext  # noqa: E402
    from fastmcp_tasks.models import (  # noqa: E402
        CancelTaskParams,
        CancelTaskResult,
        CreateTaskResult,
        GetTaskParams,
        MISSING_REQUIRED_CLIENT_CAPABILITY,
        UpdateTaskParams,
        UpdateTaskResult,
        missing_capability_error_data,
    )
    from fastmcp_tasks import wire_production  # noqa: E402
    from mcp.shared.inbound import MCP_NAME_HEADER, encode_header_value  # noqa: E402
    from mcp.server.context import ServerRequestContext  # noqa: E402
    from mcp.shared.exceptions import MCPError  # noqa: E402
    from mcp_types import INVALID_PARAMS  # noqa: E402
    from mcp_types.jsonrpc import HEADER_MISMATCH  # noqa: E402
finally:
    _restore_stubbed_modules()

_STUB_RESTORE_ERRORS = [
    f"{name} leaked or was replaced"
    for name, original in _MODULES_BEFORE_STUBS.items()
    if (
        name in sys.modules
        if original is _MISSING_MODULE
        else sys.modules.get(name) is not original
    )
]
_STUB_RESTORE_ERRORS.extend(
    f"{module_name}.{attribute} was replaced"
    for (module_name, attribute), original in _ATTRIBUTES_BEFORE_STUBS.items()
    if getattr(sys.modules[module_name], attribute, _MISSING_MODULE) is not original
)

app_package = sys.modules["app"]
app_package.to_mcp_task = app_models.to_mcp_task
app_package.StartRequest = app_models.StartRequest
app_package.TaskRecord = app_models.TaskRecord
app_package.PublicError = app_models.PublicError
app_package.LifecycleState = app_models.LifecycleState
app_package.CallbackEvent = app_models.CallbackEvent


class FakeOrchestrator:
    def __init__(self, task: TaskRecord | None = None, *, exc: Exception | None = None) -> None:
        self.task = task
        self.exc = exc
        self.start_calls: list[tuple[Any, str]] = []
        self.get_status_calls: list[tuple[str, str]] = []
        self.cancel_calls: list[tuple[str, str]] = []

    async def start(self, request: StartRequest, owner: str) -> TaskRecord:
        self.start_calls.append((request, owner))
        if self.exc is not None:
            raise self.exc
        assert self.task is not None
        return self.task

    async def get_status(self, owner: str, task_id: str) -> TaskRecord:
        self.get_status_calls.append((owner, task_id))
        if self.exc is not None:
            raise self.exc
        assert self.task is not None
        return self.task

    async def cancel(self, owner: str, task_id: str) -> TaskRecord:
        self.cancel_calls.append((owner, task_id))
        if self.exc is not None:
            raise self.exc
        assert self.task is not None
        return self.task


class FakeJobsClient:
    def __init__(self) -> None:
        self.start_calls: list[tuple[str, str, str]] = []
        self.get_calls: list[tuple[str, str]] = []
        self.list_calls: list[str] = []
        self.stop_calls: list[tuple[str, str]] = []
        self._execution = AcaExecution(
            execution_id="exec-1",
            status="Running",
            start_time=datetime.now(timezone.utc).replace(microsecond=0),
            args=[],
        )

    async def start(self, policy: Any, owner_scope: str, task_id: str) -> AcaExecution:
        self.start_calls.append((policy.job_name, owner_scope, task_id))
        self._execution = AcaExecution(
            execution_id="exec-1",
            status="Running",
            start_time=datetime.now(timezone.utc).replace(microsecond=0),
            args=["--owner-scope", owner_scope, "--task-id", task_id],
        )
        return self._execution

    async def get(self, policy: Any, execution_id: str) -> AcaExecution:
        self.get_calls.append((policy.job_name, execution_id))
        return self._execution.model_copy(update={"execution_id": execution_id})

    async def list(self, policy: Any) -> list[AcaExecution]:
        self.list_calls.append(policy.job_name)
        return [self._execution]

    async def stop(self, policy: Any, execution_id: str) -> None:
        self.stop_calls.append((policy.job_name, execution_id))


def _dump_model(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True, exclude_none=True)
    if hasattr(value, "dict"):
        return value.dict(by_alias=True, exclude_none=True)
    return dict(vars(value))


class ProtocolFixtureIsolationTests(unittest.TestCase):
    def test_dependency_stubs_do_not_escape_fixture_import(self) -> None:
        self.assertEqual(_STUB_RESTORE_ERRORS, [])


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.task = TaskRecord.new(
            owner_scope="owner-a",
            job_type="batch",
            idempotency_key_hash="hash-1",
            request_fingerprint="fingerprint-1",
            input_ref="https://example.invalid/input.json",
            callback_alias="callback",
        )
        self.orchestrator = FakeOrchestrator(self.task)
        self.owner_resolver = lambda headers: "owner-a"
        self.extension = AcaTasksExtension(self.orchestrator, self.owner_resolver)

    def test_module_exposes_exact_task_methods(self) -> None:
        self.assertEqual(self.extension.identifier, "io.modelcontextprotocol/tasks")
        methods = self.extension.methods()
        self.assertEqual(
            [(method.method, method.params_type) for method in methods],
            [
                ("tasks/get", GetTaskParams),
                ("tasks/update", UpdateTaskParams),
                ("tasks/cancel", CancelTaskParams),
            ],
        )
        self.assertTrue(all(isinstance(binding, MethodBinding) for binding in methods))
        self.assertEqual([binding.protocol_versions for binding in methods], [("2026-07-28",)] * 3)

    async def test_missing_task_capability_raises_protocol_error(self) -> None:
        ctx = ServerRequestContext(protocol_version="2026-07-28")
        with self.assertRaises(MCPError) as exc:
            await self.extension._get(ctx, GetTaskParams(taskId="task-1"))
        self.assertEqual(exc.exception.code, MISSING_REQUIRED_CLIENT_CAPABILITY)
        self.assertEqual(exc.exception.data, missing_capability_error_data())

    async def test_task_methods_allow_matching_task_header(self) -> None:
        request = types.SimpleNamespace(headers={MCP_NAME_HEADER: encode_header_value(str(self.task.task_id))})
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})

        for name, method, params in (
            ("get", AcaTasksExtension(self.orchestrator, self.owner_resolver)._get, GetTaskParams(taskId=str(self.task.task_id))),
            (
                "update",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._update,
                UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
            ),
            (
                "cancel",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._cancel,
                CancelTaskParams(taskId=str(self.task.task_id)),
            ),
        ):
            with self.subTest(method=name), patch("app.aca_tasks_extension.get_http_request", return_value=request):
                outcome = await method(ctx, params)
            if name == "get":
                self.assertIsInstance(outcome, app_models.GetTaskResult)
                self.assertEqual(outcome.task_id, str(self.task.task_id))
                self.assertEqual(outcome.status, "working")
            elif name == "update":
                self.assertEqual(_dump_model(outcome)["resultType"], "complete")
            else:
                self.assertEqual(_dump_model(outcome)["resultType"], "complete")

    async def test_task_methods_allow_absent_task_header(self) -> None:
        request = types.SimpleNamespace(headers={})
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})

        for name, method, params in (
            ("get", AcaTasksExtension(self.orchestrator, self.owner_resolver)._get, GetTaskParams(taskId=str(self.task.task_id))),
            (
                "update",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._update,
                UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
            ),
            (
                "cancel",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._cancel,
                CancelTaskParams(taskId=str(self.task.task_id)),
            ),
        ):
            with self.subTest(method=name), patch("app.aca_tasks_extension.get_http_request", return_value=request):
                await method(ctx, params)

    async def test_task_methods_allow_no_http_request(self) -> None:
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})

        for name, method, params in (
            ("get", AcaTasksExtension(self.orchestrator, self.owner_resolver)._get, GetTaskParams(taskId=str(self.task.task_id))),
            (
                "update",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._update,
                UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
            ),
            (
                "cancel",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._cancel,
                CancelTaskParams(taskId=str(self.task.task_id)),
            ),
        ):
            with self.subTest(method=name), patch("app.aca_tasks_extension.get_http_request", side_effect=RuntimeError("no request")):
                await method(ctx, params)

    async def test_task_methods_reject_mismatched_task_header(self) -> None:
        wrong_header = types.SimpleNamespace(
            headers={MCP_NAME_HEADER: encode_header_value("task-mismatch")}
        )
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})

        for name, method, params in (
            ("get", AcaTasksExtension(self.orchestrator, self.owner_resolver)._get, GetTaskParams(taskId=str(self.task.task_id))),
            (
                "update",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._update,
                UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
            ),
            (
                "cancel",
                AcaTasksExtension(self.orchestrator, self.owner_resolver)._cancel,
                CancelTaskParams(taskId=str(self.task.task_id)),
            ),
        ):
            orchestrator = FakeOrchestrator(self.task)
            extension = AcaTasksExtension(orchestrator, self.owner_resolver)
            with self.subTest(method=name), patch("app.aca_tasks_extension.get_http_request", return_value=wrong_header):
                with self.assertRaises(MCPError) as exc:
                    await getattr(extension, f"_{name}")(ctx, params)
            self.assertEqual(exc.exception.code, HEADER_MISMATCH)
            self.assertFalse(orchestrator.get_status_calls)
            self.assertFalse(orchestrator.cancel_calls)
            self.assertFalse(orchestrator.start_calls)

    async def test_get_returns_full_task_result(self) -> None:
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})
        result = await self.extension._get(ctx, GetTaskParams(taskId=str(self.task.task_id)))
        self.assertIsInstance(result, app_models.GetTaskResult)
        self.assertEqual(result.task_id, str(self.task.task_id))
        self.assertEqual(result.status, "working")
        self.assertEqual(result.ttl_ms, 86400000)
        self.assertEqual(result.poll_interval_ms, 2000)
        self.assertEqual(self.orchestrator.get_status_calls, [("owner-a", str(self.task.task_id))])

    async def test_update_validates_then_acknowledges(self) -> None:
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})
        result = await self.extension._update(
            ctx,
            UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
        )
        self.assertEqual(_dump_model(result)["resultType"], "complete")
        self.assertEqual(self.orchestrator.get_status_calls, [("owner-a", str(self.task.task_id))])

    async def test_cancel_calls_orchestrator_and_acknowledges(self) -> None:
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})
        result = await self.extension._cancel(ctx, CancelTaskParams(taskId=str(self.task.task_id)))
        self.assertEqual(_dump_model(result)["resultType"], "complete")
        self.assertEqual(self.orchestrator.cancel_calls, [("owner-a", str(self.task.task_id))])

    async def test_update_translates_unknown_task_to_safe_protocol_error(self) -> None:
        orchestrator = FakeOrchestrator(exc=PublicError("TASK_NOT_FOUND", "task not found"))
        extension = AcaTasksExtension(orchestrator, self.owner_resolver)
        ctx = ServerRequestContext(protocol_version="2026-07-28", settings={"enabled": True})
        with self.assertRaises(MCPError) as exc:
            await extension._update(
                ctx,
                UpdateTaskParams(taskId="task-unknown", inputResponses={"foo": "bar"}),
            )
        self.assertEqual(exc.exception.code, INVALID_PARAMS)
        self.assertEqual(str(exc.exception), "Task task-unknown not found")

    async def test_other_tool_calls_pass_through(self) -> None:
        call_next = AsyncMock(return_value="pass-through")
        outcome = await self.extension.intercept_tool_call(
            types.SimpleNamespace(name="other_tool", arguments={}),
            FastMCPContext(
                request_context=ServerRequestContext(protocol_version="2026-07-28"),
                settings={"enabled": True},
            ),
            call_next,
        )
        self.assertEqual(outcome, "pass-through")
        call_next.assert_awaited_once()

    async def test_unaware_start_without_request_context_passes_through(self) -> None:
        call_next = AsyncMock(return_value="pass-through")
        outcome = await self.extension.intercept_tool_call(
            types.SimpleNamespace(
                name="start_aca_job",
                arguments={
                    "jobType": "batch",
                    "idempotencyKey": "key-1",
                    "inputRef": "https://example.invalid/input.json",
                    "callbackAlias": "callback",
                },
            ),
            FastMCPContext(settings={"enabled": True}),
            call_next,
        )
        self.assertEqual(outcome, "pass-through")
        call_next.assert_awaited_once()

    async def test_unaware_start_on_legacy_protocol_passes_through(self) -> None:
        call_next = AsyncMock(return_value="pass-through")
        outcome = await self.extension.intercept_tool_call(
            types.SimpleNamespace(
                name="start_aca_job",
                arguments={
                    "jobType": "batch",
                    "idempotencyKey": "key-1",
                    "inputRef": "https://example.invalid/input.json",
                    "callbackAlias": "callback",
                },
            ),
            FastMCPContext(
                request_context=ServerRequestContext(protocol_version="2024-11-05"),
                settings={"enabled": True},
            ),
            call_next,
        )
        self.assertEqual(outcome, "pass-through")
        call_next.assert_awaited_once()

    async def test_awared_start_returns_create_task_result_without_calling_next(self) -> None:
        headers = {"x-ms-client-principal-id": "owner-a"}
        start_result = self.task.model_copy(update={"task_id": self.task.task_id, "created_at": self.task.created_at, "updated_at": self.task.updated_at})
        orchestrator = FakeOrchestrator(start_result)
        owner_calls: list[Any] = []

        def resolve_owner(passed_headers: Any) -> str:
            owner_calls.append(passed_headers)
            return "owner-a"

        extension = AcaTasksExtension(orchestrator, resolve_owner)
        call_next = AsyncMock(return_value="pass-through")
        request = types.SimpleNamespace(
            name="start_aca_job",
            arguments={
                "jobType": "batch",
                "idempotencyKey": "key-1",
                "inputRef": "https://example.invalid/input.json",
                "callbackAlias": "callback",
            },
        )
        context = FastMCPContext(
            request_context=ServerRequestContext(protocol_version="2026-07-28"),
            settings={"enabled": True},
        )
        with patch("app.aca_tasks_extension.get_http_headers", return_value=headers), patch.object(
            extension,
            "client_settings",
            side_effect=AssertionError("intercept_tool_call must use context.client_extension_settings"),
        ):
            outcome = await extension.intercept_tool_call(request, context, call_next)
        dumped = _dump_model(outcome)
        self.assertEqual(dumped["taskId"], str(self.task.task_id))
        self.assertEqual(dumped["status"], "working")
        self.assertEqual(dumped["ttlMs"], 86400000)
        self.assertEqual(dumped["pollIntervalMs"], 2000)
        self.assertEqual(owner_calls, [headers])
        self.assertEqual(orchestrator.start_calls[0][1], "owner-a")
        self.assertFalse(call_next.await_count)

    async def test_awared_start_uses_task_status_from_to_mcp_task(self) -> None:
        headers = {"x-ms-client-principal-id": "owner-a"}
        cases = (
            ("working", self.task.model_copy(update={"lifecycle_state": app_models.LifecycleState.RUNNING})),
            (
                "completed",
                self.task.model_copy(
                    update={
                        "lifecycle_state": app_models.LifecycleState.SUCCEEDED,
                        "result_url": "https://example.invalid/result.json",
                    }
                ),
            ),
            ("cancelled", self.task.model_copy(update={"lifecycle_state": app_models.LifecycleState.CANCELLED})),
            (
                "completed",
                self.task.model_copy(
                    update={
                        "lifecycle_state": app_models.LifecycleState.FAILED,
                        "error_code": "BUSINESS_FAIL",
                    }
                ),
            ),
        )

        for expected_status, task in cases:
            with self.subTest(status=expected_status):
                orchestrator = FakeOrchestrator(task)
                extension = AcaTasksExtension(orchestrator, self.owner_resolver)
                call_next = AsyncMock(return_value="pass-through")
                request = types.SimpleNamespace(
                    name="start_aca_job",
                    arguments={
                        "jobType": "batch",
                        "idempotencyKey": "key-1",
                        "inputRef": "https://example.invalid/input.json",
                        "callbackAlias": "callback",
                    },
                )
                context = FastMCPContext(
                    request_context=ServerRequestContext(protocol_version="2026-07-28"),
                    settings={"enabled": True},
                )
                with patch("app.aca_tasks_extension.get_http_headers", return_value=headers), patch.object(
                    extension,
                    "client_settings",
                    side_effect=AssertionError("intercept_tool_call must use context.client_extension_settings"),
                ):
                    outcome = await extension.intercept_tool_call(request, context, call_next)
                dumped = _dump_model(outcome)
                self.assertEqual(dumped["status"], app_models.to_mcp_task(task).status)
                self.assertEqual(dumped["status"], expected_status)
                self.assertFalse(call_next.await_count)

    async def test_lifespan_installs_and_uninstalls_serializer_only(self) -> None:
        with patch.object(wire_production, "install", MagicMock()) as install, patch.object(
            wire_production, "uninstall", MagicMock()
        ) as uninstall:
            async with self.extension.lifespan():
                install.assert_called_once()
                uninstall.assert_not_called()
            uninstall.assert_called_once()

    async def test_lifespan_reconciles_candidates_logs_safe_errors_and_closes_runtime(self) -> None:
        accepted = self.task.model_copy(update={"task_id": uuid.uuid4(), "etag": "1"})
        starting = self.task.model_copy(
            update={
                "task_id": uuid.uuid4(),
                "lifecycle_state": app_models.LifecycleState.STARTING,
                "etag": "2",
            }
        )

        async def reconcile(owner_scope: str, task_id: str) -> TaskRecord:
            if task_id == str(starting.task_id):
                raise PublicError("TASK_NOT_FOUND", "task not found")
            return accepted if task_id == str(accepted.task_id) else starting

        store = types.SimpleNamespace(list_reconcilable=AsyncMock(return_value=[accepted, starting]))
        orchestrator = types.SimpleNamespace(reconcile=AsyncMock(side_effect=reconcile))
        close = AsyncMock()
        policy = app_models.Policy(
            jobs={
                "batch": app_models.JobPolicy(
                    resource_group="rg-jobs",
                    job_name="worker-job",
                    container_name="worker",
                    image_digest="example.azurecr.io/worker@sha256:" + "a" * 64,
                    command=["python", "-m", "app.job_worker"],
                )
            },
            callbacks={
                "callback": app_models.CallbackPolicy(
                    url="https://callbacks.example/jobs",
                    auth_mode="managed_identity",
                    audience="api://callback",
                )
            },
            input_hosts={"storage.example.com"},
            result_hosts={"results.example.com"},
        )
        runtime = app_mcp_server.Runtime(
            orchestrator=orchestrator,
            store=store,
            policy=policy,
            callback_capture=types.SimpleNamespace(write=AsyncMock()),
            callback_principal_id="callback-principal-id",
            close=close,
        )
        real_sleep = asyncio.sleep

        with patch.object(app_mcp_server, "_reconcile_interval_seconds", return_value=120.0), patch.object(
            app_mcp_server.logger, "warning"
        ) as warning, patch.object(app_mcp_server.logger, "exception") as exception, patch.object(
            app_mcp_server.asyncio, "sleep", new=AsyncMock(side_effect=asyncio.CancelledError())
        ) as sleep:
            server = app_mcp_server.build_server(runtime)
            async with server.lifespan(server):
                await real_sleep(0)

        self.assertEqual(orchestrator.reconcile.await_count, 2)
        self.assertEqual(orchestrator.reconcile.await_args_list[0].args, (accepted.owner_scope, str(accepted.task_id)))
        self.assertEqual(orchestrator.reconcile.await_args_list[1].args, (starting.owner_scope, str(starting.task_id)))
        warning.assert_called_once_with(
            "reconcile failed for owner=%s task=%s: %s",
            starting.owner_scope,
            str(starting.task_id),
            "task not found",
        )
        exception.assert_not_called()
        sleep.assert_awaited_once_with(60.0)
        close.assert_awaited_once()

    def test_build_server_does_not_add_pydocket_modules(self) -> None:
        before = {name for name in sys.modules if name.startswith("pydocket")}
        policy = app_models.Policy(
            jobs={
                "batch": app_models.JobPolicy(
                    resource_group="rg-jobs",
                    job_name="worker-job",
                    container_name="worker",
                    image_digest="example.azurecr.io/worker@sha256:" + "a" * 64,
                    command=["python", "-m", "app.job_worker"],
                )
            },
            callbacks={
                "callback": app_models.CallbackPolicy(
                    url="https://callbacks.example/jobs",
                    auth_mode="managed_identity",
                    audience="api://callback",
                )
            },
            input_hosts={"storage.example.com"},
            result_hosts={"results.example.com"},
        )
        runtime = app_mcp_server.Runtime(
            orchestrator=self.orchestrator,
            store=InMemoryControlStore(),
            policy=policy,
            callback_capture=types.SimpleNamespace(write=AsyncMock()),
            callback_principal_id="callback-principal-id",
        )
        server = app_mcp_server.build_server(runtime)
        after = {name for name in sys.modules if name.startswith("pydocket")}
        self.assertTrue(any(isinstance(extension, AcaTasksExtension) for extension in server.extensions))
        self.assertEqual(after, before)


class ServerTests(unittest.IsolatedAsyncioTestCase):
    def _policy(self) -> app_models.Policy:
        return app_models.Policy(
            jobs={
            "batch": app_models.JobPolicy(
                resource_group="rg-jobs",
                job_name="worker-job",
                container_name="worker",
                image_digest="example.azurecr.io/worker@sha256:" + "a" * 64,
                command=["python", "-m", "app.job_worker"],
            )
            },
            callbacks={
            "ops": app_models.CallbackPolicy(
                url="https://callbacks.example/jobs",
                auth_mode="managed_identity",
                audience="api://callback",
            )
            },
            input_hosts={"storage.example.com"},
            result_hosts={"results.example.com"},
        )

    def _runtime(
        self,
        *,
        orchestrator: Orchestrator | None = None,
        store: Any | None = None,
        callback_capture: Any | None = None,
        callback_principal_id: str = "callback-principal-id",
        trust_aca_auth_headers: bool = False,
    ) -> app_mcp_server.Runtime:
        store = store or InMemoryControlStore()
        jobs = FakeJobsClient()
        policy = self._policy()
        orchestrator = orchestrator or Orchestrator(
            store=store,
            jobs=jobs,
            policy=policy,
            clock=lambda: datetime.now(timezone.utc).replace(microsecond=0),
        )
        callback_capture = callback_capture or app_mcp_server.InMemoryCallbackCapture()
        return app_mcp_server.Runtime(
            orchestrator=orchestrator,
            store=store,
            policy=policy,
            callback_capture=callback_capture,
            callback_principal_id=callback_principal_id,
            trust_aca_auth_headers=trust_aca_auth_headers,
        )

    def test_callback_event_model_is_strict(self) -> None:
        event = app_models.CallbackEvent.model_validate(
            {
                "taskId": "task-1",
                "acaExecutionId": "exec-1",
                "status": "Succeeded",
                "resultUrl": "https://results.example/jobs/task-1.json",
            }
        )
        self.assertEqual(event.task_id, "task-1")
        self.assertEqual(event.aca_execution_id, "exec-1")
        self.assertEqual(event.status, "Succeeded")
        self.assertEqual(str(event.result_url), "https://results.example/jobs/task-1.json")
        with self.assertRaises(ValidationError):
            app_models.CallbackEvent.model_validate(
                {
                    "taskId": "task-1",
                    "acaExecutionId": "exec-1",
                    "status": "Succeeded",
                    "resultUrl": None,
                    "unexpected": True,
                }
            )

    def test_owner_scope_from_headers_requires_trusted_perimeter_and_principal(self) -> None:
        principal = "  Alice@example.com  "
        expected = hashlib.sha256("alice@example.com".encode("utf-8")).hexdigest()
        with self.assertRaises(PublicError) as exc:
            app_mcp_server.owner_scope_from_headers({"X-MS-CLIENT-PRINCIPAL-ID": principal})
        self.assertEqual(exc.exception.code, "TASK_FORBIDDEN")
        self.assertEqual(
            app_mcp_server.owner_scope_from_headers({"X-MS-CLIENT-PRINCIPAL-ID": principal}, trusted=True),
            expected,
        )
        with self.assertRaises(PublicError) as exc:
            app_mcp_server.owner_scope_from_headers(
                {"X-MS-CLIENT-PRINCIPAL-ID": principal},
                trusted=True,
                callback_principal_id="alice@example.com",
            )
        self.assertEqual(exc.exception.code, "TASK_FORBIDDEN")
        with self.assertRaises(PublicError) as exc:
            app_mcp_server.owner_scope_from_headers({}, trusted=True)
        self.assertEqual(exc.exception.code, "TASK_FORBIDDEN")

    def test_runtime_from_env_requires_aca_easy_auth_and_sets_trust_flag(self) -> None:
        env = {
            "AZURE_CLIENT_ID": "client-id-1",
            "AZURE_SUBSCRIPTION_ID": "sub-id-1",
            "MCP_ACA_JOBS_AUTH_MODE": "aca-easy-auth",
            "MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID": "callback-principal-id-1",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com:443/",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "jobs-db",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "jobs",
            "MCP_ACA_JOBS_CALLBACK_CONTAINER_URL": "https://storage.example.com/callbacks",
            "MCP_ACA_JOBS_POLICY_JSON": json.dumps(self._policy().model_dump(mode="json", by_alias=True)),
        }
        fake_blob_client = types.SimpleNamespace(upload_blob=AsyncMock())
        fake_container_client = types.SimpleNamespace(
            get_blob_client=MagicMock(return_value=fake_blob_client),
            close=AsyncMock(),
        )
        fake_cosmos_container = types.SimpleNamespace()
        fake_cosmos_database = types.SimpleNamespace(get_container_client=MagicMock(return_value=fake_cosmos_container))
        fake_cosmos_client = types.SimpleNamespace(
            get_database_client=MagicMock(return_value=fake_cosmos_database),
            close=AsyncMock(),
        )
        fake_sync_credential = types.SimpleNamespace(close=MagicMock())
        fake_async_credential = types.SimpleNamespace(close=AsyncMock())
        fake_app_client = types.SimpleNamespace(close=MagicMock())
        with patch.dict(os.environ, env, clear=False), patch.object(
            app_mcp_server, "ManagedIdentityCredential"
        ) as managed_identity, patch.object(app_mcp_server, "AioManagedIdentityCredential") as aio_managed_identity, patch.object(
            app_mcp_server, "ContainerAppsAPIClient", return_value=fake_app_client
        ) as jobs_client, patch.object(app_mcp_server, "CosmosClient", return_value=fake_cosmos_client) as cosmos_client, patch.object(
            app_mcp_server.ContainerClient, "from_container_url", return_value=fake_container_client
        ) as from_container_url:
            managed_identity.return_value = fake_sync_credential
            aio_managed_identity.return_value = fake_async_credential
            runtime = app_mcp_server.runtime_from_env()

        self.assertTrue(runtime.trust_aca_auth_headers)
        self.assertEqual(runtime.callback_principal_id, "callback-principal-id-1")
        managed_identity.assert_called_once_with(client_id="client-id-1")
        aio_managed_identity.assert_called_once_with(client_id="client-id-1")
        jobs_client.assert_called_once_with(credential=fake_sync_credential, subscription_id="sub-id-1")
        cosmos_client.assert_called_once_with("https://cosmos.example.com:443/", credential=fake_async_credential)
        from_container_url.assert_called_once_with("https://storage.example.com/callbacks", credential=fake_async_credential)

        bad_env = dict(env)
        bad_env["MCP_ACA_JOBS_AUTH_MODE"] = "bearer-token"
        with patch.dict(os.environ, bad_env, clear=False), patch.object(
            app_mcp_server, "ManagedIdentityCredential", side_effect=AssertionError("runtime must fail closed before auth setup")
        ), patch.object(
            app_mcp_server, "AioManagedIdentityCredential", side_effect=AssertionError("runtime must fail closed before auth setup")
        ), patch.object(
            app_mcp_server, "ContainerAppsAPIClient", side_effect=AssertionError("runtime must fail closed before auth setup")
        ), patch.object(
            app_mcp_server, "CosmosClient", side_effect=AssertionError("runtime must fail closed before auth setup")
        ), patch.object(
            app_mcp_server.ContainerClient, "from_container_url", side_effect=AssertionError("runtime must fail closed before auth setup")
        ):
            with self.assertRaises(RuntimeError):
                app_mcp_server.runtime_from_env()

    def test_build_server_registers_extension_routes_and_flat_tool_names(self) -> None:
        runtime = self._runtime(trust_aca_auth_headers=True)
        server = app_mcp_server.build_server(runtime)
        self.assertEqual(server.name, "foundry-mcp-aca-jobs")
        self.assertTrue(any(isinstance(extension, AcaTasksExtension) for extension in server.extensions))
        self.assertIn("start_aca_job", server.tools)
        self.assertIn("get_aca_job_status", server.tools)
        self.assertIn("cancel_aca_job", server.tools)
        self.assertIn(("/health", "GET"), server.routes)
        self.assertIn(("/callbacks/jobs", "POST"), server.routes)
        self.assertEqual(tuple(inspect.signature(server.tools["start_aca_job"]).parameters), ("jobType", "idempotencyKey", "inputRef", "callbackAlias"))
        self.assertEqual(tuple(inspect.signature(server.tools["get_aca_job_status"]).parameters), ("taskId",))
        self.assertEqual(tuple(inspect.signature(server.tools["cancel_aca_job"]).parameters), ("taskId",))

    async def test_tools_round_trip_and_restart_same_store(self) -> None:
        runtime = self._runtime(trust_aca_auth_headers=True)
        server = app_mcp_server.build_server(runtime)
        client = server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": "  Alice@example.com  "}, task_capability=False)

        started_at = monotonic()
        started = await client.call_tool(
            "start_aca_job",
            {
                "jobType": "batch",
                "idempotencyKey": "key-1",
                "inputRef": "https://storage.example.com/input.json",
                "callbackAlias": "ops",
            },
        )
        self.assertLess(monotonic() - started_at, 1.0)
        self.assertEqual(started.data["lifecycleState"], "Running")
        task_id = started.data["taskId"]
        self.assertEqual(
            runtime.orchestrator._jobs.start_calls[0][1],
            hashlib.sha256("alice@example.com".encode("utf-8")).hexdigest(),
        )

        status_started_at = monotonic()
        status = await client.call_tool("get_aca_job_status", {"taskId": task_id})
        self.assertLess(monotonic() - status_started_at, 1.0)
        cancel_started_at = monotonic()
        cancelled = await client.call_tool("cancel_aca_job", {"taskId": task_id})
        self.assertLess(monotonic() - cancel_started_at, 1.0)
        self.assertEqual(status.data["taskId"], task_id)
        self.assertEqual(cancelled.data["taskId"], task_id)

        restarted = app_mcp_server.build_server(runtime)
        restarted_client = restarted.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": "Alice@example.com"}, task_capability=False)
        restarted_started_at = monotonic()
        restarted_status = await restarted_client.call_tool("get_aca_job_status", {"taskId": task_id})
        self.assertLess(monotonic() - restarted_started_at, 1.0)
        self.assertEqual(restarted_status.data["taskId"], task_id)

    async def test_awared_start_short_circuits_tool_call(self) -> None:
        runtime = self._runtime(trust_aca_auth_headers=True)
        server = app_mcp_server.build_server(runtime)
        server.tools["start_aca_job"] = lambda **_: (_ for _ in ()).throw(AssertionError("tool should not run"))
        client = server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": "Alice@example.com"}, task_capability=True)
        started = await client.call_tool(
            "start_aca_job",
            {
                "jobType": "batch",
                "idempotencyKey": "key-2",
                "inputRef": "https://storage.example.com/input.json",
                "callbackAlias": "ops",
            },
        )
        self.assertEqual(started.data["resultType"], "task")
        self.assertIn("taskId", started.data)

    async def test_health_and_callback_route_validate_and_store_exact_fields(self) -> None:
        capture = app_mcp_server.InMemoryCallbackCapture()
        callback_principal_id = "callback-principal-id-1"
        runtime = self._runtime(
            callback_capture=capture,
            callback_principal_id=callback_principal_id,
            trust_aca_auth_headers=True,
        )
        server = app_mcp_server.build_server(runtime)
        callback_client = server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": callback_principal_id})
        agent_client = server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": "Alice@example.com"})

        health = await callback_client.request("GET", "/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.text, "ok")

        accepted = await callback_client.request(
            "POST",
            "/callbacks/jobs",
            json={
                "taskId": "task-1",
                "acaExecutionId": "exec-1",
                "status": "Succeeded",
                "resultUrl": "https://results.example/jobs/task-1.json",
            },
        )
        self.assertEqual(accepted.status_code, 202)
        self.assertEqual(
            capture.events,
            [
                {
                    "taskId": "task-1",
                    "acaExecutionId": "exec-1",
                    "status": "Succeeded",
                    "resultUrl": "https://results.example/jobs/task-1.json",
                }
            ],
        )

        rejected = await agent_client.request(
            "POST",
            "/callbacks/jobs",
            json={
                "taskId": "task-2",
                "acaExecutionId": "exec-2",
                "status": "Succeeded",
                "resultUrl": "https://results.example/jobs/task-2.json",
            },
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(json.loads(rejected.text), {"code": "TASK_FORBIDDEN", "detail": "caller is not authorized"})

        with patch("app.mcp_server.get_http_headers", return_value={"X-MS-CLIENT-PRINCIPAL-ID": callback_principal_id}):
            with self.assertRaises(PublicError) as exc:
                await server.tools["start_aca_job"](
                    jobType="batch",
                    idempotencyKey="key-3",
                    inputRef="https://storage.example.com/input.json",
                    callbackAlias="ops",
                )
        self.assertEqual(exc.exception.code, "TASK_FORBIDDEN")

        rejected = await callback_client.request(
            "POST",
            "/callbacks/jobs",
            json={
                "taskId": "task-1",
                "acaExecutionId": "exec-1",
                "status": "Succeeded",
                "resultUrl": None,
                "unexpected": True,
            },
        )
        self.assertEqual(rejected.status_code, 422)

    async def test_callbacks_route_requires_trusted_perimeter_and_is_idempotent(self) -> None:
        callback_principal_id = "callback-principal-id-2"
        untrusted_capture = app_mcp_server.BlobCallbackCapture(
            app_mcp_server.ContainerClient.from_container_url("https://callbacks.example/jobs")
        )
        untrusted_runtime = self._runtime(
            callback_capture=untrusted_capture,
            trust_aca_auth_headers=False,
        )
        untrusted_server = app_mcp_server.build_server(untrusted_runtime)
        untrusted_client = untrusted_server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": "Alice@example.com"})
        rejected = await untrusted_client.request(
            "POST",
            "/callbacks/jobs",
            json={
                "taskId": "task-1",
                "acaExecutionId": "exec-1",
                "status": "Succeeded",
                "resultUrl": "https://results.example/jobs/task-1.json",
            },
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(json.loads(rejected.text), {"code": "TASK_FORBIDDEN", "detail": "caller is not authorized"})

        container_client = app_mcp_server.ContainerClient.from_container_url("https://callbacks.example/jobs")
        trusted_runtime = self._runtime(
            callback_capture=app_mcp_server.BlobCallbackCapture(container_client),
            callback_principal_id=callback_principal_id,
            trust_aca_auth_headers=True,
        )
        trusted_server = app_mcp_server.build_server(trusted_runtime)
        trusted_client = trusted_server.client(headers={"X-MS-CLIENT-PRINCIPAL-ID": callback_principal_id})
        payload = {
            "taskId": "task-1",
            "acaExecutionId": "exec-1",
            "status": "Succeeded",
            "resultUrl": "https://results.example/jobs/task-1.json",
        }
        accepted = await trusted_client.request("POST", "/callbacks/jobs", json=payload)
        self.assertEqual(accepted.status_code, 202)
        duplicate = await trusted_client.request("POST", "/callbacks/jobs", json=payload)
        self.assertEqual(duplicate.status_code, 202)
        conflicting = await trusted_client.request(
            "POST",
            "/callbacks/jobs",
            json={
                "taskId": "task-1",
                "acaExecutionId": "exec-1",
                "status": "Failed",
                "resultUrl": "https://results.example/jobs/task-1.json",
            },
        )
        self.assertEqual(conflicting.status_code, 409)
        self.assertEqual(
            json.loads(conflicting.text),
            {"code": "CALLBACK_PAYLOAD_CONFLICT", "detail": "callback payload conflict"},
        )
        blob = container_client.get_blob_client("callbacks/task-1.json")
        self.assertEqual(json.loads(blob.payload.decode("utf-8")), payload)

    async def test_runtime_from_env_wires_clients_closes_resources_and_supports_help_without_env(self) -> None:
        env = {
            "AZURE_CLIENT_ID": "client-id-1",
            "AZURE_SUBSCRIPTION_ID": "sub-id-1",
            "MCP_ACA_JOBS_AUTH_MODE": "aca-easy-auth",
            "MCP_ACA_JOBS_CALLBACK_PRINCIPAL_ID": "callback-principal-id-1",
            "MCP_ACA_JOBS_COSMOS_ENDPOINT": "https://cosmos.example.com:443/",
            "MCP_ACA_JOBS_COSMOS_DATABASE": "jobs-db",
            "MCP_ACA_JOBS_COSMOS_CONTAINER": "jobs",
            "MCP_ACA_JOBS_CALLBACK_CONTAINER_URL": "https://storage.example.com/callbacks",
            "MCP_ACA_JOBS_POLICY_JSON": json.dumps(self._policy().model_dump(mode="json", by_alias=True)),
        }
        fake_blob_client = types.SimpleNamespace(upload_blob=AsyncMock())
        fake_container_client = types.SimpleNamespace(
            get_blob_client=MagicMock(return_value=fake_blob_client),
            close=AsyncMock(),
        )
        fake_cosmos_container = types.SimpleNamespace()
        fake_cosmos_database = types.SimpleNamespace(get_container_client=MagicMock(return_value=fake_cosmos_container))
        fake_cosmos_client = types.SimpleNamespace(
            get_database_client=MagicMock(return_value=fake_cosmos_database),
            close=AsyncMock(),
        )
        fake_sync_credential = types.SimpleNamespace(close=MagicMock())
        fake_async_credential = types.SimpleNamespace(close=AsyncMock())
        fake_app_client = types.SimpleNamespace(close=MagicMock())
        with patch.dict(os.environ, env, clear=False), patch.object(
            app_mcp_server, "ManagedIdentityCredential"
        ) as managed_identity, patch.object(app_mcp_server, "AioManagedIdentityCredential") as aio_managed_identity, patch.object(
            app_mcp_server, "ContainerAppsAPIClient", return_value=fake_app_client
        ) as jobs_client, patch.object(app_mcp_server, "CosmosClient", return_value=fake_cosmos_client) as cosmos_client, patch.object(
            app_mcp_server.ContainerClient, "from_container_url", return_value=fake_container_client
        ) as from_container_url:
            managed_identity.return_value = fake_sync_credential
            aio_managed_identity.return_value = fake_async_credential
            runtime = app_mcp_server.runtime_from_env()

        managed_identity.assert_called_once_with(client_id="client-id-1")
        aio_managed_identity.assert_called_once_with(client_id="client-id-1")
        jobs_client.assert_called_once_with(credential=fake_sync_credential, subscription_id="sub-id-1")
        cosmos_client.assert_called_once_with("https://cosmos.example.com:443/", credential=fake_async_credential)
        from_container_url.assert_called_once_with("https://storage.example.com/callbacks", credential=fake_async_credential)
        self.assertIsInstance(runtime.policy, app_models.Policy)
        self.assertEqual(runtime.policy.jobs["batch"].job_name, "worker-job")
        self.assertEqual(runtime.callback_principal_id, "callback-principal-id-1")
        self.assertTrue(runtime.trust_aca_auth_headers)
        self.assertIsNotNone(runtime.close)
        await runtime.close()
        fake_container_client.close.assert_awaited_once()
        fake_cosmos_client.close.assert_awaited_once()
        fake_app_client.close.assert_called_once()
        fake_async_credential.close.assert_awaited_once()
        fake_sync_credential.close.assert_called_once()
        with patch.dict(os.environ, {}, clear=True), patch.object(
            app_mcp_server, "runtime_from_env", side_effect=AssertionError("runtime factory should not run for --help")
        ), patch.object(app_mcp_server, "build_server", side_effect=AssertionError("build_server should not run for --help")):
            with self.assertRaises(SystemExit) as exc:
                app_mcp_server.main(["--help"])
        self.assertEqual(exc.exception.code, 0)

    def test_main_runs_streamable_http_with_default_host_and_port(self) -> None:
        runtime = self._runtime()
        fake_server = types.SimpleNamespace(run=MagicMock())
        with patch.object(app_mcp_server, "runtime_from_env", return_value=runtime) as runtime_from_env, patch.object(
            app_mcp_server, "build_server", return_value=fake_server
        ) as build_server:
            exit_code = app_mcp_server.main([])

        self.assertEqual(exit_code, 0)
        runtime_from_env.assert_called_once()
        build_server.assert_called_once_with(runtime)
        fake_server.run.assert_called_once_with(transport="streamable-http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    unittest.main()

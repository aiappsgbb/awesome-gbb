#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs SEP-2663 adapter."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
APP_DIR = SKILL_DIR / "app"
sys.path.insert(0, str(SKILL_DIR))


def _ensure_package(name: str, *, path: list[str] | None = None) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        module.__path__ = [] if path is None else path  # type: ignore[attr-defined]
        sys.modules[name] = module
    if path is not None:
        module.__path__ = path  # type: ignore[attr-defined]
    return module


def _install_stubs() -> None:
    _ensure_package("app", path=[str(APP_DIR)])

    fastmcp = _ensure_package("fastmcp")
    server = _ensure_package("fastmcp.server")
    extensions = _ensure_package("fastmcp.server.extensions")
    dependencies = _ensure_package("fastmcp.server.dependencies")
    utilities = _ensure_package("fastmcp.utilities")
    utilities_tasks = _ensure_package("fastmcp.utilities.tasks")

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

    extensions.MethodBinding = MethodBinding
    extensions.ServerExtension = ServerExtension
    dependencies.get_http_headers = lambda: None
    server.extensions = extensions
    server.dependencies = dependencies
    fastmcp.server = server
    utilities.tasks = utilities_tasks
    utilities_tasks.TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"

    mcp = _ensure_package("mcp")
    mcp_shared = _ensure_package("mcp.shared")
    mcp_exceptions = _ensure_package("mcp.shared.exceptions")

    class MCPError(Exception):
        def __init__(self, *, code: int, message: str, data: Any | None = None) -> None:
            super().__init__(message)
            self.code = code
            self.message = message
            self.data = data

    mcp_exceptions.MCPError = MCPError
    mcp_shared.exceptions = mcp_exceptions
    mcp.shared = mcp_shared

    mcp_types = _ensure_package("mcp_types")
    mcp_types.INVALID_PARAMS = -32602
    mcp_types.INTERNAL_ERROR = -32603
    mcp_types.RequestParams = BaseModel
    mcp_types.Result = BaseModel
    mcp_types_jsonrpc = _ensure_package("mcp_types.jsonrpc")
    mcp_types_jsonrpc.INVALID_PARAMS = -32602
    mcp_types_jsonrpc.INTERNAL_ERROR = -32603
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

import app.models as app_models  # noqa: E402
from app.aca_tasks_extension import AcaTasksExtension  # noqa: E402
from app.models import PublicError, StartRequest, TaskRecord  # noqa: E402
from fastmcp.server.extensions import MethodBinding  # noqa: E402
from fastmcp_tasks.models import (  # noqa: E402
    CancelTaskParams,
    CancelTaskResult,
    CreateTaskResult,
    GetTaskParams,
    GetTaskResult,
    MISSING_REQUIRED_CLIENT_CAPABILITY,
    UpdateTaskParams,
    UpdateTaskResult,
    missing_capability_error_data,
)
from fastmcp_tasks import wire_production  # noqa: E402
from mcp.shared.exceptions import MCPError  # noqa: E402
from mcp_types import INVALID_PARAMS  # noqa: E402

app_package = sys.modules["app"]
app_package.to_mcp_task = app_models.to_mcp_task
app_package.StartRequest = app_models.StartRequest
app_package.TaskRecord = app_models.TaskRecord
app_package.PublicError = app_models.PublicError
app_package.LifecycleState = app_models.LifecycleState


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


class FakeContext:
    def __init__(self, settings: dict[str, Any] | None) -> None:
        self._settings = settings

    def client_extension_settings(self, identifier: str) -> dict[str, Any] | None:
        if identifier != "io.modelcontextprotocol/tasks":
            return None
        return self._settings


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
        ctx = FakeContext(None)
        with self.assertRaises(MCPError) as exc:
            await self.extension._get(ctx, GetTaskParams(taskId="task-1"))
        self.assertEqual(exc.exception.code, MISSING_REQUIRED_CLIENT_CAPABILITY)
        self.assertEqual(exc.exception.data, missing_capability_error_data())

    async def test_get_returns_full_task_result(self) -> None:
        ctx = FakeContext({"enabled": True})
        result = await self.extension._get(ctx, GetTaskParams(taskId=str(self.task.task_id)))
        self.assertIsInstance(result, GetTaskResult)
        dumped = result.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(dumped["taskId"], str(self.task.task_id))
        self.assertEqual(dumped["status"], "working")
        self.assertEqual(dumped["ttlMs"], 86400000)
        self.assertEqual(dumped["pollIntervalMs"], 2000)
        self.assertEqual(self.orchestrator.get_status_calls, [("owner-a", str(self.task.task_id))])

    async def test_update_validates_then_acknowledges(self) -> None:
        ctx = FakeContext({"enabled": True})
        result = await self.extension._update(
            ctx,
            UpdateTaskParams(taskId=str(self.task.task_id), inputResponses={"foo": "bar"}),
        )
        self.assertIsInstance(result, UpdateTaskResult)
        self.assertEqual(result.model_dump(by_alias=True, exclude_none=True)["resultType"], "complete")
        self.assertEqual(self.orchestrator.get_status_calls, [("owner-a", str(self.task.task_id))])

    async def test_cancel_calls_orchestrator_and_acknowledges(self) -> None:
        ctx = FakeContext({"enabled": True})
        result = await self.extension._cancel(ctx, CancelTaskParams(taskId=str(self.task.task_id)))
        self.assertIsInstance(result, CancelTaskResult)
        self.assertEqual(result.model_dump(by_alias=True, exclude_none=True)["resultType"], "complete")
        self.assertEqual(self.orchestrator.cancel_calls, [("owner-a", str(self.task.task_id))])

    async def test_update_translates_unknown_task_to_safe_protocol_error(self) -> None:
        orchestrator = FakeOrchestrator(exc=PublicError("TASK_NOT_FOUND", "task not found"))
        extension = AcaTasksExtension(orchestrator, self.owner_resolver)
        ctx = FakeContext({"enabled": True})
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
            FakeContext({"enabled": True}),
            call_next,
        )
        self.assertEqual(outcome, "pass-through")
        call_next.assert_awaited_once()

    async def test_unaware_start_tool_calls_pass_through(self) -> None:
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
            FakeContext(None),
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
        with patch("app.aca_tasks_extension.get_http_headers", return_value=headers):
            outcome = await extension.intercept_tool_call(request, FakeContext({"enabled": True}), call_next)
        self.assertIsInstance(outcome, CreateTaskResult)
        dumped = outcome.model_dump(by_alias=True, exclude_none=True)
        self.assertEqual(dumped["taskId"], str(self.task.task_id))
        self.assertEqual(dumped["status"], "working")
        self.assertEqual(dumped["ttlMs"], 86400000)
        self.assertEqual(dumped["pollIntervalMs"], 2000)
        self.assertEqual(owner_calls, [headers])
        self.assertEqual(orchestrator.start_calls[0][1], "owner-a")
        self.assertFalse(call_next.await_count)

    async def test_lifespan_installs_and_uninstalls_serializer_only(self) -> None:
        with patch.object(wire_production, "install", MagicMock()) as install, patch.object(
            wire_production, "uninstall", MagicMock()
        ) as uninstall:
            async with self.extension.lifespan():
                install.assert_called_once()
                uninstall.assert_not_called()
            uninstall.assert_called_once()

    def test_source_does_not_reference_docket_or_tasks_extension(self) -> None:
        source = (APP_DIR / "aca_tasks_extension.py").read_text(encoding="utf-8")
        for forbidden in (
            "from fastmcp_tasks import TasksExtension",
            "TaskConfig",
            "pydocket",
            "docket_lifespan",
            "Docket(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()

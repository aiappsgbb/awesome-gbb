"""SEP-2663 adapter that projects ACA jobs as FastMCP tasks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.extensions import MethodBinding, ServerExtension
from fastmcp_tasks import wire_production
from fastmcp_tasks.models import (
    MISSING_REQUIRED_CLIENT_CAPABILITY,
    CancelTaskParams,
    CancelTaskResult,
    CreateTaskResult,
    GetTaskParams,
    GetTaskResult,
    UpdateTaskParams,
    UpdateTaskResult,
    missing_capability_error_data,
)
from mcp.server.context import ServerRequestContext
from mcp.shared.exceptions import MCPError
from mcp_types import INTERNAL_ERROR, INVALID_PARAMS

from .models import PublicError, StartRequest, to_mcp_task

try:  # pragma: no cover - modern protocol versions are importable in production.
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS
except ImportError:  # pragma: no cover - local stubs still exercise the adapter.
    MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ()

__all__ = ["AcaTasksExtension"]

_TASK_METHOD_VERSIONS = tuple(MODERN_PROTOCOL_VERSIONS)
_TASK_EXTENSION_ID = "io.modelcontextprotocol/tasks"
_TASK_TTL_MS = 86_400_000
_TASK_POLL_INTERVAL_MS = 2_000


def _utc_z(value: datetime | None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_protocol_error(error: PublicError, *, task_id: str | None = None) -> MCPError:
    message = error.safe_message
    if error.code in {"TASK_NOT_FOUND", "TASK_FORBIDDEN"}:
        if task_id:
            message = f"Task {task_id} not found"
        return MCPError(code=INVALID_PARAMS, message=message)
    return MCPError(code=INTERNAL_ERROR, message=message)


class AcaTasksExtension(ServerExtension):
    identifier = _TASK_EXTENSION_ID

    def __init__(
        self,
        orchestrator: Any,
        owner_resolver: Callable[[dict[str, Any]], str],
    ) -> None:
        self._orchestrator = orchestrator
        self._owner_resolver = owner_resolver

    def methods(self) -> Sequence[MethodBinding]:
        return (
            MethodBinding(
                method="tasks/get",
                params_type=GetTaskParams,
                handler=self._get,
                protocol_versions=_TASK_METHOD_VERSIONS,
            ),
            MethodBinding(
                method="tasks/update",
                params_type=UpdateTaskParams,
                handler=self._update,
                protocol_versions=_TASK_METHOD_VERSIONS,
            ),
            MethodBinding(
                method="tasks/cancel",
                params_type=CancelTaskParams,
                handler=self._cancel,
                protocol_versions=_TASK_METHOD_VERSIONS,
            ),
        )

    def _require_tasks_capability(self, ctx: ServerRequestContext[Any, Any]) -> None:
        if self.client_settings(ctx) is None:
            raise MCPError(
                code=MISSING_REQUIRED_CLIENT_CAPABILITY,
                message="This request targets io.modelcontextprotocol/tasks, but the client did not declare that extension for this request.",
                data=missing_capability_error_data(),
            )

    def _owner_scope(self) -> str:
        headers = get_http_headers() or {}
        return self._owner_resolver(headers)

    async def _load_task(self, owner_scope: str, task_id: str) -> Any:
        try:
            return await self._orchestrator.get_status(owner_scope, task_id)
        except PublicError as error:
            raise _safe_protocol_error(error, task_id=task_id) from error
        except MCPError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard for unknown store errors.
            raise MCPError(code=INTERNAL_ERROR, message="task unavailable") from exc

    async def _get(self, ctx: ServerRequestContext[Any, Any], params: GetTaskParams) -> GetTaskResult:
        self._require_tasks_capability(ctx)
        task = await self._load_task(self._owner_scope(), params.task_id)
        return to_mcp_task(task)

    async def _update(self, ctx: ServerRequestContext[Any, Any], params: UpdateTaskParams) -> UpdateTaskResult:
        self._require_tasks_capability(ctx)
        await self._load_task(self._owner_scope(), params.task_id)
        return UpdateTaskResult()

    async def _cancel(self, ctx: ServerRequestContext[Any, Any], params: CancelTaskParams) -> CancelTaskResult:
        self._require_tasks_capability(ctx)
        owner_scope = self._owner_scope()
        try:
            await self._orchestrator.cancel(owner_scope, params.task_id)
        except PublicError as error:
            raise _safe_protocol_error(error, task_id=params.task_id) from error
        except MCPError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard for unknown store errors.
            raise MCPError(code=INTERNAL_ERROR, message="task unavailable") from exc
        return CancelTaskResult()

    async def intercept_tool_call(self, params: Any, context: Context, call_next: Callable[[], Any]) -> Any:
        if getattr(params, "name", None) != "start_aca_job":
            return await call_next()
        request_context = context.request_context
        if request_context is None or request_context.protocol_version not in MODERN_PROTOCOL_VERSIONS:
            return await call_next()
        if context.client_extension_settings(self.identifier) is None:
            return await call_next()

        request = StartRequest.model_validate(getattr(params, "arguments", {}) or {})
        owner_scope = self._owner_resolver(get_http_headers() or {})
        try:
            task = await self._orchestrator.start(request, owner_scope)
        except PublicError as error:
            raise _safe_protocol_error(error) from error
        except MCPError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard for unknown store errors.
            raise MCPError(code=INTERNAL_ERROR, message="task unavailable") from exc

        return CreateTaskResult(
            task_id=str(task.task_id),
            status="working",
            created_at=_utc_z(getattr(task, "created_at", None)),
            last_updated_at=_utc_z(getattr(task, "updated_at", None)),
            ttl_ms=_TASK_TTL_MS,
            poll_interval_ms=_TASK_POLL_INTERVAL_MS,
        )

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        wire_production.install()
        try:
            yield
        finally:
            wire_production.uninstall()

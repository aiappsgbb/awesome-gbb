"""SEP-2663 adapter that projects ACA jobs as FastMCP tasks.

Source of truth for the prose example in ../../../SKILL.md § Standards-first MCP Tasks path.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from fastmcp.server.context import Context
from fastmcp.server.dependencies import get_http_headers, get_http_request
try:  # pragma: no cover - fallback for local stub environments.
    from fastmcp.server.extensions import MethodBinding, ServerExtension
except ImportError:  # pragma: no cover
    @dataclass(frozen=True)
    class MethodBinding:
        method: str
        params_type: Any
        handler: Callable[..., Any]
        protocol_versions: Sequence[str] = ()

    class ServerExtension:
        identifier = ""

        def client_settings(self, ctx: Any) -> Any:
            resolver = getattr(ctx, "client_extension_settings", None)
            if resolver is None:
                return None
            return resolver(self.identifier)

try:  # pragma: no cover - fallback for local stub environments.
    from fastmcp_tasks import wire_production
except ImportError:  # pragma: no cover
    class _WireProduction:
        def install(self) -> None:
            return None

        def uninstall(self) -> None:
            return None

    wire_production = _WireProduction()
try:  # pragma: no cover - fallback for local stub environments.
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
except ImportError:  # pragma: no cover
    MISSING_REQUIRED_CLIENT_CAPABILITY = -32021

    def missing_capability_error_data() -> dict[str, Any]:
        return {}

    class _TaskModel:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)

    class CancelTaskParams(_TaskModel):
        pass

    class CancelTaskResult(_TaskModel):
        pass

    class CreateTaskResult(_TaskModel):
        pass

    class GetTaskParams(_TaskModel):
        pass

    class GetTaskResult(_TaskModel):
        pass

    class UpdateTaskParams(_TaskModel):
        pass

    class UpdateTaskResult(_TaskModel):
        pass
try:  # pragma: no cover - compatibility for newer mcp package layouts.
    from mcp.server.context import ServerRequestContext
except ImportError:  # pragma: no cover
    from mcp.shared.context import RequestContext as ServerRequestContext

try:  # pragma: no cover - compatibility with newer mcp exception layouts.
    from mcp.shared.exceptions import MCPError as _ImportedMCPError
except ImportError:  # pragma: no cover
    _ImportedMCPError = None

if _ImportedMCPError is not None:  # pragma: no cover - preferred in tests and production.
    MCPError = _ImportedMCPError
else:  # pragma: no cover - local fallback when the mcp package is absent.
    class MCPError(Exception):
        def __init__(self, *, code: int, message: str, data: Any | None = None) -> None:
            super().__init__(message)
            self.code = code
            self.message = message
            self.data = data
try:  # pragma: no cover - compatibility for package-local or vendored types.
    from mcp_types import INTERNAL_ERROR, INVALID_PARAMS
except ImportError:  # pragma: no cover
    from mcp.types import INTERNAL_ERROR, INVALID_PARAMS
try:  # pragma: no cover - fallback for local stub environments.
    from mcp.shared.inbound import MCP_NAME_HEADER, decode_header_value
except ImportError:  # pragma: no cover
    import base64

    MCP_NAME_HEADER = "mcp-name"

    def decode_header_value(value: str | None) -> str | None:
        if value is None or not value.startswith("=?base64?") or not value.endswith("?="):
            return value
        payload = value[len("=?base64?") : -2]
        try:
            return base64.b64decode(payload, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

try:  # pragma: no cover - fallback for local stub environments.
    from mcp_types.jsonrpc import HEADER_MISMATCH
except ImportError:  # pragma: no cover
    HEADER_MISMATCH = -32020

from .models import PublicError, StartRequest, to_mcp_task

try:  # pragma: no cover - modern protocol versions are importable in production.
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS
except ImportError:  # pragma: no cover - local stubs still exercise the adapter.
    MODERN_PROTOCOL_VERSIONS: tuple[str, ...] = ("2026-07-28",)

__all__ = ["AcaTasksExtension"]

_TASK_METHOD_VERSIONS = tuple(MODERN_PROTOCOL_VERSIONS)
_TASK_EXTENSION_ID = "io.modelcontextprotocol/tasks"
_TASK_TTL_MS = 86_400_000
_TASK_POLL_INTERVAL_MS = 2_000


def _task_model(name: str) -> type[Any]:
    try:
        from fastmcp_tasks import models as task_models
    except ImportError:
        task_models = None
    if task_models is not None and hasattr(task_models, name):
        return getattr(task_models, name)
    return globals()[name]


def _modern_protocol_versions() -> tuple[str, ...]:
    return tuple(MODERN_PROTOCOL_VERSIONS) or ("2026-07-28",)


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

    def _require_matching_task_route(self, task_id: str) -> None:
        try:
            request = get_http_request()
        except RuntimeError:
            return

        header = request.headers.get(MCP_NAME_HEADER)
        if header is None:
            return
        if decode_header_value(header) != task_id:
            raise MCPError(
                code=HEADER_MISMATCH,
                message=f"{MCP_NAME_HEADER} header does not match the request body's 'taskId' parameter",
            )

    def _check_task_request(self, ctx: ServerRequestContext[Any, Any], task_id: str) -> None:
        self._require_tasks_capability(ctx)
        self._require_matching_task_route(task_id)

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
        self._check_task_request(ctx, params.task_id)
        task = await self._load_task(self._owner_scope(), params.task_id)
        return to_mcp_task(task)

    async def _update(self, ctx: ServerRequestContext[Any, Any], params: UpdateTaskParams) -> UpdateTaskResult:
        self._check_task_request(ctx, params.task_id)
        await self._load_task(self._owner_scope(), params.task_id)
        return _task_model("UpdateTaskResult")()

    async def _cancel(self, ctx: ServerRequestContext[Any, Any], params: CancelTaskParams) -> CancelTaskResult:
        self._check_task_request(ctx, params.task_id)
        owner_scope = self._owner_scope()
        try:
            await self._orchestrator.cancel(owner_scope, params.task_id)
        except PublicError as error:
            raise _safe_protocol_error(error, task_id=params.task_id) from error
        except MCPError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard for unknown store errors.
            raise MCPError(code=INTERNAL_ERROR, message="task unavailable") from exc
        return _task_model("CancelTaskResult")()

    async def intercept_tool_call(self, params: Any, context: Context, call_next: Callable[[], Any]) -> Any:
        if getattr(params, "name", None) != "start_aca_job":
            return await call_next()
        request_context = context.request_context
        if request_context is None or request_context.protocol_version not in _modern_protocol_versions():
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

        task_result = to_mcp_task(task)
        return _task_model("CreateTaskResult")(
            task_id=str(task.task_id),
            status=task_result.status,
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

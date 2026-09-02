"""FastMCP server assembly for foundry-mcp-aca-jobs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Annotated, Protocol, runtime_checkable

from azure.cosmos.aio import CosmosClient
from azure.identity import ManagedIdentityCredential
from azure.identity.aio import ManagedIdentityCredential as AioManagedIdentityCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from azure.storage.blob.aio import ContainerClient
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from pydantic import Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from .aca_jobs import AcaJobsAdapter
from .aca_tasks_extension import AcaTasksExtension
from .control_store import CosmosControlStore
from .models import CallbackEvent, Policy, PublicError, StartRequest, TaskRecord
from .orchestrator import Orchestrator
from .telemetry import configure as configure_telemetry

__all__ = [
    "BlobCallbackCapture",
    "CallbackCapture",
    "InMemoryCallbackCapture",
    "Runtime",
    "build_server",
    "main",
    "owner_scope_from_headers",
    "runtime_from_env",
]

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8080
_DEFAULT_PROTOCOL_VERSION = "2026-07-28"
_TASKS_EXTENSION_ID = "io.modelcontextprotocol/tasks"
_RECONCILE_SLEEP_MAX_SECONDS = 60.0

logger = logging.getLogger(__name__)


@runtime_checkable
class CallbackCapture(Protocol):
    async def write(self, event: CallbackEvent) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_principal(value: Any) -> str:
    return str(value).strip().casefold()


def _header_value(headers: Mapping[str, Any], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return None if value is None else str(value)
    return None


def owner_scope_from_headers(headers: Mapping[str, Any]) -> str:
    principal = _header_value(headers, "X-MS-CLIENT-PRINCIPAL-ID")
    if principal is None or not principal.strip():
        raise PublicError("TASK_FORBIDDEN", "caller is not authorized")
    normalized = _normalize_principal(principal)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Runtime:
    orchestrator: Orchestrator
    store: Any
    policy: Policy
    callback_capture: CallbackCapture
    close: Callable[[], Awaitable[None]] | None = None


class InMemoryCallbackCapture:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def write(self, event: CallbackEvent) -> None:
        self.events.append(event.model_dump(mode="json", by_alias=True, exclude_none=False))


class BlobCallbackCapture:
    def __init__(self, container_client: ContainerClient) -> None:
        self.container_client = container_client

    @classmethod
    def from_container_url(
        cls,
        container_url: str,
        credential: Any | None = None,
    ) -> "BlobCallbackCapture":
        return cls(ContainerClient.from_container_url(container_url, credential=credential))

    async def write(self, event: CallbackEvent) -> None:
        payload = event.model_dump(mode="json", by_alias=True, exclude_none=False)
        blob_client = self.container_client.get_blob_client(f"callbacks/{event.task_id}.json")
        await blob_client.upload_blob(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            overwrite=False,
        )

    async def close(self) -> None:
        close = getattr(self.container_client, "close", None)
        if close is None:
            return
        outcome = close()
        if inspect.isawaitable(outcome):
            await outcome


def _reconcile_interval_seconds() -> float | None:
    raw = os.getenv("MCP_ACA_JOBS_RECONCILE_INTERVAL_SECONDS")
    if raw is None or not raw.strip():
        return None
    try:
        interval = float(raw)
    except ValueError:
        return None
    return interval if interval > 0 else None


def _candidate_owner_task(candidate: Any) -> tuple[str, str] | None:
    if isinstance(candidate, TaskRecord):
        return str(candidate.owner_scope), str(candidate.task_id)
    if isinstance(candidate, Mapping):
        owner_scope = candidate.get("ownerScope") or candidate.get("owner_scope")
        task_id = candidate.get("taskId") or candidate.get("task_id")
        if owner_scope and task_id:
            return str(owner_scope), str(task_id)
        return None
    owner_scope = getattr(candidate, "owner_scope", None)
    task_id = getattr(candidate, "task_id", None)
    if owner_scope and task_id:
        return str(owner_scope), str(task_id)
    return None


async def _reconcile_loop(runtime: Runtime, interval_seconds: float) -> None:
    list_reconcilable = getattr(runtime.store, "list_reconcilable", None)
    if list_reconcilable is None:
        return
    sleep_seconds = max(0.1, min(interval_seconds, _RECONCILE_SLEEP_MAX_SECONDS))
    while True:
        try:
            candidates = list_reconcilable()
            if inspect.isawaitable(candidates):
                candidates = await candidates
            for candidate in candidates or ():
                owner_task = _candidate_owner_task(candidate)
                if owner_task is None:
                    continue
                owner_scope, task_id = owner_task
                try:
                    await runtime.orchestrator.reconcile(owner_scope, task_id)
                except asyncio.CancelledError:
                    raise
                except PublicError as error:
                    logger.warning("reconcile failed for owner=%s task=%s: %s", owner_scope, task_id, error.safe_message)
                except Exception:
                    logger.exception("reconcile failed for owner=%s task=%s", owner_scope, task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("reconcile loop failed")
        await asyncio.sleep(sleep_seconds)


def _json_response(content: Any, *, status_code: int) -> JSONResponse:
    return JSONResponse(content, status_code=status_code)


async def _close_resource(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if close is None:
        return
    outcome = close()
    if inspect.isawaitable(outcome):
        await outcome


def build_server(runtime: Runtime) -> FastMCP:
    configure_telemetry()

    reconciler_interval = _reconcile_interval_seconds()

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        reconciler_task: asyncio.Task[None] | None = None
        if reconciler_interval is not None and hasattr(runtime.store, "list_reconcilable"):
            reconciler_task = asyncio.create_task(_reconcile_loop(runtime, reconciler_interval))
        try:
            yield
        finally:
            if reconciler_task is not None:
                reconciler_task.cancel()
                with suppress(asyncio.CancelledError):
                    await reconciler_task
            if runtime.close is not None:
                await runtime.close()

    server = FastMCP("foundry-mcp-aca-jobs", lifespan=lifespan)
    server.add_extension(AcaTasksExtension(runtime.orchestrator, owner_scope_from_headers))

    @server.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok", status_code=200)

    @server.custom_route("/callbacks/jobs", methods=["POST"])
    async def callbacks_jobs(request: Request) -> JSONResponse | PlainTextResponse:
        owner_scope_from_headers(request.headers)
        try:
            body = await request.json()
            event = CallbackEvent.model_validate(body)
        except (ValidationError, ValueError, TypeError):
            return _json_response({"detail": "invalid callback event"}, status_code=422)
        await runtime.callback_capture.write(event)
        return PlainTextResponse("accepted", status_code=202)

    @server.tool
    async def start_aca_job(
        jobType: Annotated[str, Field(min_length=1)],
        idempotencyKey: Annotated[str, Field(min_length=1, max_length=200)],
        inputRef: Annotated[str, Field(min_length=1)],
        callbackAlias: Annotated[str, Field(min_length=1)],
    ) -> dict[str, Any]:
        owner_scope = owner_scope_from_headers(get_http_headers() or {})
        request = StartRequest.model_validate(
            {
                "jobType": jobType,
                "idempotencyKey": idempotencyKey,
                "inputRef": inputRef,
                "callbackAlias": callbackAlias,
            }
        )
        task = await runtime.orchestrator.start(request, owner_scope)
        return task.model_dump(mode="json", by_alias=True, exclude_none=False)

    @server.tool
    async def get_aca_job_status(taskId: Annotated[str, Field(min_length=1)]) -> dict[str, Any]:
        owner_scope = owner_scope_from_headers(get_http_headers() or {})
        task = await runtime.orchestrator.get_status(owner_scope, taskId)
        return task.model_dump(mode="json", by_alias=True, exclude_none=False)

    @server.tool
    async def cancel_aca_job(taskId: Annotated[str, Field(min_length=1)]) -> dict[str, Any]:
        owner_scope = owner_scope_from_headers(get_http_headers() or {})
        task = await runtime.orchestrator.cancel(owner_scope, taskId)
        return task.model_dump(mode="json", by_alias=True, exclude_none=False)

    return server


def runtime_from_env() -> Runtime:
    client_id = os.environ["AZURE_CLIENT_ID"]
    subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
    cosmos_endpoint = os.environ["MCP_ACA_JOBS_COSMOS_ENDPOINT"]
    cosmos_database = os.environ["MCP_ACA_JOBS_COSMOS_DATABASE"]
    cosmos_container = os.environ["MCP_ACA_JOBS_COSMOS_CONTAINER"]
    callback_container_url = os.environ["MCP_ACA_JOBS_CALLBACK_CONTAINER_URL"]
    policy = Policy.model_validate_json(os.environ["MCP_ACA_JOBS_POLICY_JSON"])

    sync_credential = ManagedIdentityCredential(client_id=client_id)
    async_credential = AioManagedIdentityCredential(client_id=client_id)
    cosmos_client = CosmosClient(cosmos_endpoint, credential=async_credential)
    app_client = ContainerAppsAPIClient(credential=sync_credential, subscription_id=subscription_id)
    database = cosmos_client.get_database_client(cosmos_database)
    container = database.get_container_client(cosmos_container)
    store = CosmosControlStore(container)
    jobs = AcaJobsAdapter(app_client)
    orchestrator = Orchestrator(store, jobs, policy, clock=_utcnow)
    callback_capture = BlobCallbackCapture.from_container_url(callback_container_url, credential=async_credential)

    async def close() -> None:
        await _close_resource(callback_capture)
        await _close_resource(cosmos_client)
        await _close_resource(app_client)
        await _close_resource(async_credential)
        await _close_resource(sync_credential)

    return Runtime(
        orchestrator=orchestrator,
        store=store,
        policy=policy,
        callback_capture=callback_capture,
        close=close,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs MCP server.")
    parser.add_argument("--host", default=_DEFAULT_HOST, help="Bind host for the MCP server.")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT, help="Bind port for the MCP server.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    runtime = runtime_from_env()
    mcp = build_server(runtime)
    mcp.run(transport="streamable-http", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

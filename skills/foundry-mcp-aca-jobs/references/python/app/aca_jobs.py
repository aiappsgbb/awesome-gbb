"""Canonical ACA Job adapter for foundry-mcp-aca-jobs."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from azure.core.exceptions import HttpResponseError
from azure.mgmt.appcontainers import ContainerAppsAPIClient
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import JobPolicy, PublicError

__all__ = ["AcaExecution", "AcaJobsAdapter", "AcaJobsClient"]

AcaExecutionStatus = Literal["Processing", "Running", "Succeeded", "Failed", "Stopped", "Degraded", "Unknown"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _safe_message(code: str) -> str:
    return {
        "TASK_FORBIDDEN": "task forbidden",
        "TASK_NOT_FOUND": "task not found",
        "ARM_STATUS_UNAVAILABLE": "arm status unavailable",
        "ARM_START_REJECTED": "arm start rejected",
        "ARM_STOP_REJECTED": "arm stop rejected",
        "DEPLOYMENT_CONTRACT_MISMATCH": "deployment contract mismatch",
    }.get(code, "arm status unavailable")


def _status_code(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    if status is not None:
        return status
    response = getattr(error, "response", None)
    return getattr(response, "status_code", None)


def _raw_value(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _raise_public_error(code: str, exc: BaseException | None = None) -> None:
    error = PublicError(code, _safe_message(code))
    if exc is not None:
        raise error from exc
    raise error


def _translate_http_error(error: HttpResponseError, *, phase: str) -> None:
    status = _status_code(error)
    if status == 403:
        _raise_public_error("TASK_FORBIDDEN", error)
    if status == 404:
        _raise_public_error("TASK_NOT_FOUND", error)
    if status in {408, 409, 429} or (status is not None and status >= 500):
        _raise_public_error("ARM_STATUS_UNAVAILABLE", error)
    if phase == "start" and status is not None and 400 <= status < 500:
        _raise_public_error("ARM_START_REJECTED", error)
    if phase == "stop" and status is not None and 400 <= status < 500:
        _raise_public_error("ARM_STOP_REJECTED", error)
    if status is None or (status is not None and 400 <= status < 500):
        _raise_public_error("ARM_STATUS_UNAVAILABLE", error)
    raise error


def _execution_id_from_response(response: Any) -> str:
    name = _raw_value(response, "name")
    identifier = _raw_value(response, "id")
    if name is None and identifier is None:
        _raise_public_error("DEPLOYMENT_CONTRACT_MISMATCH")
    if name is not None and identifier is not None:
        identifier_name = str(identifier).rstrip("/").rsplit("/", 1)[-1]
        if identifier_name != str(name):
            _raise_public_error("DEPLOYMENT_CONTRACT_MISMATCH")
        return str(name)
    if name is not None:
        return str(name)
    return str(identifier).rstrip("/").rsplit("/", 1)[-1]


def _execution_status(response: Any) -> AcaExecutionStatus:
    raw = _raw_value(_raw_value(response, "properties", response), "status")
    if raw in {"Processing", "Running", "Succeeded", "Failed", "Stopped", "Degraded", "Unknown"}:
        return raw
    return "Unknown"


def _execution_start_time(response: Any) -> datetime:
    raw = _raw_value(_raw_value(response, "properties", response), "start_time")
    if isinstance(raw, datetime):
        return _normalize_datetime(raw)
    return _utcnow()


def _expected_start_args(owner_scope: str, task_id: str) -> list[str]:
    return ["--owner-scope", owner_scope, "--task-id", task_id]


def _execution_args(response: Any) -> list[str]:
    properties = _raw_value(response, "properties", response)
    template = _raw_value(properties, "template")
    containers = _raw_value(template, "containers", []) or []
    if not containers:
        return []
    args = _raw_value(containers[0], "args", []) or []
    return [str(value) for value in args]


def _matching_worker_container(containers: list[Any], container_name: str) -> Any | None:
    matches = [container for container in containers if _raw_value(container, "name") == container_name]
    if len(matches) == 1:
        return matches[0]
    return None


def _execution_args_for_container(
    response: Any,
    container_name: str,
    *,
    strict: bool,
    phase: str,
) -> list[str]:
    properties = _raw_value(response, "properties", response)
    template = _raw_value(properties, "template")
    containers = _raw_value(template, "containers", []) or []
    if not containers:
        if strict:
            _raise_public_error("ARM_STATUS_UNAVAILABLE" if phase == "status" else "DEPLOYMENT_CONTRACT_MISMATCH")
        return []
    container = _matching_worker_container(containers, container_name)
    if container is None:
        if strict:
            _raise_public_error("ARM_STATUS_UNAVAILABLE" if phase == "status" else "DEPLOYMENT_CONTRACT_MISMATCH")
        return []
    args = _raw_value(container, "args", []) or []
    return [str(value) for value in args]


def _execution_from_response(
    response: Any,
    *,
    execution_id: str | None = None,
    container_name: str | None = None,
    strict_container_match: bool = True,
    phase: str = "status",
) -> "AcaExecution":
    args = (
        _execution_args_for_container(response, container_name, strict=strict_container_match, phase=phase)
        if container_name is not None
        else _execution_args(response)
    )
    return AcaExecution(
        execution_id=execution_id or _execution_id_from_response(response),
        status=_execution_status(response),
        start_time=_execution_start_time(response),
        args=args,
    )


def _execution_template_for_start(job: Any, policy: JobPolicy, owner_scope: str, task_id: str) -> Any:
    template = deepcopy(_raw_value(_raw_value(job, "properties", job), "template"))
    containers = _raw_value(template, "containers", []) or []
    if not containers:
        _raise_public_error("DEPLOYMENT_CONTRACT_MISMATCH")
    first = _matching_worker_container(containers, policy.container_name)
    if first is None:
        _raise_public_error("DEPLOYMENT_CONTRACT_MISMATCH")
    image = _raw_value(first, "image")
    command = _raw_value(first, "command")
    if image != policy.image_digest or list(command or []) != list(policy.command):
        _raise_public_error("DEPLOYMENT_CONTRACT_MISMATCH")
    if isinstance(first, dict):
        first["args"] = ["--owner-scope", owner_scope, "--task-id", task_id]
    else:
        first.args = ["--owner-scope", owner_scope, "--task-id", task_id]
    return template


def _start_execution_args(response: Any, policy: JobPolicy, owner_scope: str, task_id: str) -> list[str]:
    expected = _expected_start_args(owner_scope, task_id)
    properties = _raw_value(response, "properties", response)
    template = _raw_value(properties, "template")
    if template is None:
        return expected
    containers = _raw_value(template, "containers", None)
    if not containers:
        _raise_public_error("ARM_STATUS_UNAVAILABLE")
    args = _execution_args_for_container(response, policy.container_name, strict=True, phase="status")
    if args != expected:
        _raise_public_error("ARM_STATUS_UNAVAILABLE")
    return expected


class AcaExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(min_length=1)
    status: AcaExecutionStatus
    start_time: datetime
    args: list[str] = Field(default_factory=list)

    @field_validator("start_time")
    @classmethod
    def _coerce_start_time(cls, value: datetime) -> datetime:
        return _normalize_datetime(value)

    def matches_task(self, task_id: str, attempt_started_at: datetime | None) -> bool:
        if attempt_started_at is not None and _normalize_datetime(self.start_time) < _normalize_datetime(attempt_started_at):
            return False
        matches = 0
        for index, value in enumerate(self.args):
            if value != "--task-id":
                continue
            matches += 1
            if index + 1 >= len(self.args) or self.args[index + 1] != task_id:
                return False
        return matches == 1


@runtime_checkable
class AcaJobsClient(Protocol):
    async def start(self, policy: JobPolicy, owner_scope: str, task_id: str) -> AcaExecution: ...

    async def get(self, policy: JobPolicy, execution_id: str) -> AcaExecution: ...

    async def list(self, policy: JobPolicy) -> list[AcaExecution]: ...

    async def stop(self, policy: JobPolicy, execution_id: str) -> None: ...


class AcaJobsAdapter:
    def __init__(self, client: ContainerAppsAPIClient) -> None:
        self._client = client

    async def start(self, policy: JobPolicy, owner_scope: str, task_id: str) -> AcaExecution:
        try:
            job = await asyncio.to_thread(self._client.jobs.get, policy.resource_group, policy.job_name)
        except HttpResponseError as error:
            _translate_http_error(error, phase="read")

        template = _execution_template_for_start(job, policy, owner_scope, task_id)

        try:
            poller = await asyncio.to_thread(self._client.jobs.begin_start, policy.resource_group, policy.job_name, template)
        except HttpResponseError as error:
            _translate_http_error(error, phase="start")

        try:
            response = await asyncio.to_thread(poller.result)
        except HttpResponseError as error:
            _translate_http_error(error, phase="start")

        execution_id = _execution_id_from_response(response)
        status = _execution_status(response)
        if status == "Unknown" and _raw_value(_raw_value(response, "properties", response), "status") is None:
            status = "Processing"
        start_time = _execution_start_time(response)
        args = _start_execution_args(response, policy, owner_scope, task_id)
        return AcaExecution(execution_id=execution_id, status=status, start_time=start_time, args=args)

    async def get(self, policy: JobPolicy, execution_id: str) -> AcaExecution:
        try:
            response = await asyncio.to_thread(
                self._client.job_execution,
                policy.resource_group,
                policy.job_name,
                execution_id,
            )
        except HttpResponseError as error:
            _translate_http_error(error, phase="read")
        return _execution_from_response(response, execution_id=execution_id, container_name=policy.container_name)

    async def list(self, policy: JobPolicy) -> list[AcaExecution]:
        try:
            response = await asyncio.to_thread(
                lambda: list(self._client.jobs_executions.list(policy.resource_group, policy.job_name))
            )
        except HttpResponseError as error:
            _translate_http_error(error, phase="read")
        return [_execution_from_response(item, container_name=policy.container_name) for item in response]

    async def stop(self, policy: JobPolicy, execution_id: str) -> None:
        try:
            poller = await asyncio.to_thread(
                self._client.jobs.begin_stop_execution,
                policy.resource_group,
                policy.job_name,
                execution_id,
            )
        except HttpResponseError as error:
            _translate_http_error(error, phase="stop")
        try:
            await asyncio.to_thread(poller.result)
        except HttpResponseError as error:
            _translate_http_error(error, phase="stop")
        return None

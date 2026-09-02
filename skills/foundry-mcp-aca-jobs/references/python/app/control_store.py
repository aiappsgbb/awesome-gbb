"""Canonical durable task control store for foundry-mcp-aca-jobs."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Protocol, runtime_checkable

from azure.core import MatchConditions
from pydantic import ValidationError

from .models import LifecycleState, PublicError, TaskRecord

__all__ = [
    "ConcurrencyError",
    "ControlStore",
    "CosmosControlStore",
    "InMemoryControlStore",
    "InvalidTransition",
]


class ConcurrencyError(RuntimeError):
    """Raised when a task update loses its ETag race."""


class InvalidTransition(RuntimeError):
    """Raised when a task tries to move outside the allowed lifecycle graph."""


@runtime_checkable
class ControlStore(Protocol):
    async def create_or_get(self, task: TaskRecord) -> TaskRecord: ...

    async def get(self, owner_scope: str, task_id: str) -> TaskRecord: ...

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord: ...


_TERMINAL_STATES = frozenset(
    {
        LifecycleState.SUCCEEDED,
        LifecycleState.FAILED,
        LifecycleState.CANCELLED,
    }
)
_ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.ACCEPTED: frozenset(
        {
            LifecycleState.ACCEPTED,
            LifecycleState.STARTING,
            LifecycleState.RUNNING,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.STARTING: frozenset(
        {
            LifecycleState.STARTING,
            LifecycleState.RUNNING,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
        }
    ),
    LifecycleState.RUNNING: frozenset(
        {
            LifecycleState.RUNNING,
            LifecycleState.SUCCEEDED,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
        }
    ),
}
for _state in _TERMINAL_STATES:
    _ALLOWED_TRANSITIONS[_state] = frozenset({_state})

_COSMOS_SERVICE_KEYS = frozenset({"id", "_rid", "_self", "_attachments", "_ts"})
_COSMOS_404_INFRA_MARKERS = ("owner resource does not exist", "container", "database")


def _safe_not_found() -> PublicError:
    return PublicError("TASK_NOT_FOUND", "task not found")


def _safe_idempotency_reused() -> PublicError:
    return PublicError("IDEMPOTENCY_KEY_REUSED", "idempotency key reused")


def _safe_control_store_unavailable() -> PublicError:
    return PublicError("CONTROL_STORE_UNAVAILABLE", "control store unavailable")


def _status_code(error: BaseException) -> int | None:
    return getattr(error, "status_code", None)


def _error_text(error: BaseException) -> str:
    parts = [str(error)]
    for attribute in ("message", "body"):
        value = getattr(error, attribute, None)
        if value is None:
            continue
        if isinstance(value, bytes):
            parts.append(value.decode("utf-8", errors="ignore"))
        else:
            parts.append(str(value))
    return "\n".join(part for part in parts if part)


def _is_cosmos_infrastructure_404(error: BaseException) -> bool:
    text = _error_text(error).lower()
    return any(marker in text for marker in _COSMOS_404_INFRA_MARKERS)


def _task_document(record: TaskRecord) -> dict[str, Any]:
    document = record.model_dump(mode="json", by_alias=True, exclude_none=True)
    document["id"] = str(record.task_id)
    return document


def _record_from_document(document: Any) -> TaskRecord:
    data = dict(document)
    for key in _COSMOS_SERVICE_KEYS:
        data.pop(key, None)
    return TaskRecord.model_validate(data)


def _validate_full_task(task: TaskRecord) -> TaskRecord:
    try:
        return TaskRecord.model_validate(task.model_dump(mode="json", by_alias=True, exclude_none=True))
    except ValidationError as exc:  # pragma: no cover - exercised through InvalidTransition tests.
        raise InvalidTransition("task record violates the persisted model contract") from exc


def _copy_task(task: TaskRecord) -> TaskRecord:
    return deepcopy(task)


def _task_key(owner_scope: str, task_id: str) -> tuple[str, str]:
    return owner_scope, task_id


class InMemoryControlStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._records: dict[tuple[str, str], TaskRecord] = {}

    async def create_or_get(self, task: TaskRecord) -> TaskRecord:
        validated = _validate_full_task(task)
        key = _task_key(validated.owner_scope, str(validated.task_id))
        async with self._lock:
            current = self._records.get(key)
            if current is not None:
                if current.request_fingerprint != validated.request_fingerprint:
                    raise _safe_idempotency_reused()
                return _copy_task(current)

            created = validated.model_copy(update={"etag": "1"})
            self._records[key] = _copy_task(created)
            return _copy_task(created)

    async def get(self, owner_scope: str, task_id: str) -> TaskRecord:
        key = _task_key(owner_scope, task_id)
        async with self._lock:
            current = self._records.get(key)
            if current is None:
                raise _safe_not_found()
            return _copy_task(current)

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord:
        validated = _validate_full_task(task)
        key = _task_key(validated.owner_scope, str(validated.task_id))
        async with self._lock:
            current = self._records.get(key)
            if current is None:
                raise _safe_not_found()
            if etag is None or current.etag != etag:
                raise ConcurrencyError("task etag no longer matches")
            if validated.lifecycle_state not in _ALLOWED_TRANSITIONS[current.lifecycle_state]:
                raise InvalidTransition(
                    f"{current.lifecycle_state.value} -> {validated.lifecycle_state.value} is not allowed"
                )

            new_etag = str(int(current.etag or "0") + 1)
            stored = validated.model_copy(update={"etag": new_etag})
            self._records[key] = _copy_task(stored)
            return _copy_task(stored)


class CosmosControlStore:
    def __init__(self, container: Any) -> None:
        self._container = container

    async def create_or_get(self, task: TaskRecord) -> TaskRecord:
        validated = _validate_full_task(task)
        payload = _task_document(validated)
        try:
            created = await self._container.create_item(payload)
        except Exception as exc:  # pragma: no cover - exercised through status-translation tests.
            if _status_code(exc) == 409:
                existing = await self._read_existing(validated.owner_scope, str(validated.task_id))
                if existing.request_fingerprint != validated.request_fingerprint:
                    raise _safe_idempotency_reused()
                return _copy_task(existing)
            raise _safe_control_store_unavailable() from exc

        return _copy_task(_record_from_document(created if created is not None else payload))

    async def get(self, owner_scope: str, task_id: str) -> TaskRecord:
        try:
            current = await self._container.read_item(item=task_id, partition_key=owner_scope)
        except Exception as exc:  # pragma: no cover - exercised through status-translation tests.
            if _status_code(exc) == 404:
                if _is_cosmos_infrastructure_404(exc):
                    raise _safe_control_store_unavailable() from exc
                raise _safe_not_found() from exc
            raise _safe_control_store_unavailable() from exc
        return _copy_task(_record_from_document(current))

    async def replace(self, task: TaskRecord, etag: str | None) -> TaskRecord:
        validated = _validate_full_task(task)
        current = await self._read_existing(validated.owner_scope, str(validated.task_id))
        if etag is None or current.etag != etag:
            raise ConcurrencyError("task etag no longer matches")
        if validated.lifecycle_state not in _ALLOWED_TRANSITIONS[current.lifecycle_state]:
            raise InvalidTransition(f"{current.lifecycle_state.value} -> {validated.lifecycle_state.value} is not allowed")

        body = _task_document(validated)
        try:
            updated = await self._container.replace_item(
                item=str(validated.task_id),
                body=body,
                etag=etag,
                match_condition=MatchConditions.IfNotModified,
            )
        except Exception as exc:  # pragma: no cover - exercised through status-translation tests.
            if _status_code(exc) == 404:
                if _is_cosmos_infrastructure_404(exc):
                    raise _safe_control_store_unavailable() from exc
                raise _safe_not_found() from exc
            if _status_code(exc) == 412:
                raise ConcurrencyError("task etag no longer matches") from exc
            raise _safe_control_store_unavailable() from exc

        return _copy_task(_record_from_document(updated if updated is not None else body))

    async def _read_existing(self, owner_scope: str, task_id: str) -> TaskRecord:
        try:
            item = await self._container.read_item(item=task_id, partition_key=owner_scope)
        except Exception as exc:
            if _status_code(exc) == 404:
                if _is_cosmos_infrastructure_404(exc):
                    raise _safe_control_store_unavailable() from exc
                raise _safe_not_found() from exc
            raise _safe_control_store_unavailable() from exc
        return _record_from_document(item)

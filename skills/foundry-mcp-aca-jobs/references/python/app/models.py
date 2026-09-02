"""Canonical control-record models for foundry-mcp-aca-jobs.

Source of truth for the prose example in `../../SKILL.md § Control record and
lifecycle`.
"""

from __future__ import annotations

import sys
import types
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator

__all__ = [
    "CallbackDeliveryState",
    "GetTaskResult",
    "LifecycleState",
    "PublicError",
    "StartRequest",
    "TaskRecord",
    "map_aca_state",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _to_utc_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LifecycleState(StrEnum):
    Accepted = "Accepted"
    Starting = "Starting"
    Running = "Running"
    Succeeded = "Succeeded"
    Failed = "Failed"
    Cancelled = "Cancelled"


class CallbackDeliveryState(StrEnum):
    NotStarted = "NotStarted"
    Pending = "Pending"
    Delivered = "Delivered"
    Exhausted = "Exhausted"


class PublicError(Exception):
    """Stable, safe error surface for end users and external callers."""

    def __init__(self, code: str, safe_message: str) -> None:
        if not code:
            raise ValueError("code must be non-empty")
        if not safe_message:
            raise ValueError("safe_message must be non-empty")
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message

    def __str__(self) -> str:
        return self.safe_message


class StartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    job_type: str = Field(alias="jobType")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)
    input_ref: HttpUrl = Field(alias="inputRef")
    callback_alias: str | None = Field(default=None, alias="callbackAlias", min_length=1)

    @field_validator("input_ref")
    @classmethod
    def _https_only(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("inputRef must use https")
        return value


class _GetTaskResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task_id: UUID | None = None
    status: str
    result: dict[str, Any] | None = None
    error: dict[str, Any] | str | None = None
    status_message: str | None = None


try:  # pragma: no cover - exercised implicitly when the real dependency exists.
    from fastmcp_tasks.models import GetTaskResult  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local fallback only.
    package = sys.modules.setdefault("fastmcp_tasks", types.ModuleType("fastmcp_tasks"))
    _module = types.ModuleType("fastmcp_tasks.models")
    _module.GetTaskResult = _GetTaskResult
    package.models = _module
    sys.modules["fastmcp_tasks.models"] = _module
    GetTaskResult = _module.GetTaskResult


class TaskRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task_id: UUID = Field(alias="taskId")
    owner_scope: str = Field(alias="ownerScope")
    job_type: str = Field(alias="jobType")
    idempotency_key_hash: str = Field(alias="idempotencyKeyHash")
    request_fingerprint: str = Field(alias="requestFingerprint")
    input_ref: HttpUrl = Field(alias="inputRef")
    callback_alias: str | None = Field(default=None, alias="callbackAlias")
    lifecycle_state: LifecycleState = Field(default=LifecycleState.Accepted, alias="lifecycleState")
    aca_execution_id: str | None = Field(default=None, alias="acaExecutionId")
    result_url: HttpUrl | None = Field(default=None, alias="resultUrl")
    error_code: str | None = Field(default=None, alias="errorCode")
    callback_delivery_state: CallbackDeliveryState = Field(
        default=CallbackDeliveryState.NotStarted,
        alias="callbackDeliveryState",
    )
    callback_error_code: str | None = Field(default=None, alias="callbackErrorCode")
    cancellation_requested_at: datetime | None = Field(default=None, alias="cancellationRequestedAt")
    start_attempted_at: datetime | None = Field(default=None, alias="startAttemptedAt")
    start_attempt_count: int = Field(default=0, alias="startAttemptCount", ge=0)
    worker_claimed_at: datetime | None = Field(default=None, alias="workerClaimedAt")
    worker_claim_token: str | None = Field(default=None, alias="workerClaimToken")
    worker_claim_expires_at: datetime | None = Field(default=None, alias="workerClaimExpiresAt")
    created_at: datetime = Field(default_factory=_utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=_utcnow, alias="updatedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    etag: str | None = Field(default=None, alias="_etag")

    @field_serializer(
        "cancellation_requested_at",
        "start_attempted_at",
        "worker_claimed_at",
        "worker_claim_expires_at",
        "created_at",
        "updated_at",
        "completed_at",
        when_used="json",
    )
    def _serialize_datetimes(self, value: datetime | None) -> str | None:
        return _to_utc_z(value)

    @classmethod
    def new(
        cls,
        *,
        owner_scope: str,
        job_type: str,
        idempotency_key_hash: str,
        request_fingerprint: str,
        input_ref: str | HttpUrl,
        callback_alias: str | None = None,
    ) -> "TaskRecord":
        now = _utcnow()
        task_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{owner_scope}:{job_type}:{idempotency_key_hash}")
        return cls(
            taskId=task_id,
            ownerScope=owner_scope,
            jobType=job_type,
            idempotencyKeyHash=idempotency_key_hash,
            requestFingerprint=request_fingerprint,
            inputRef=input_ref,
            callbackAlias=callback_alias,
            lifecycleState=LifecycleState.Accepted,
            callbackDeliveryState=CallbackDeliveryState.NotStarted,
            createdAt=now,
            updatedAt=now,
        )

    def to_mcp_task(self) -> GetTaskResult:
        if self.lifecycle_state in {
            LifecycleState.Accepted,
            LifecycleState.Starting,
            LifecycleState.Running,
        }:
            return GetTaskResult(task_id=self.task_id, status="working")

        if self.lifecycle_state is LifecycleState.Cancelled:
            return GetTaskResult(task_id=self.task_id, status="cancelled")

        if self.lifecycle_state is LifecycleState.Succeeded:
            if self.result_url is None:
                return GetTaskResult(task_id=self.task_id, status="working")
            result = {
                "content": [{"type": "text", "text": str(self.result_url)}],
                "isError": False,
            }
            return GetTaskResult(task_id=self.task_id, status="completed", result=result)

        if self.lifecycle_state is LifecycleState.Failed:
            result = {
                "content": [{"type": "text", "text": self.error_code or "ACA_EXECUTION_FAILED"}],
                "isError": True,
            }
            return GetTaskResult(task_id=self.task_id, status="completed", result=result)

        return GetTaskResult(task_id=self.task_id, status="working")


def map_aca_state(
    record: TaskRecord,
    aca_state: str,
    *,
    result_url: str | HttpUrl | None = None,
) -> TaskRecord:
    if aca_state == "Processing":
        lifecycle_state = LifecycleState.Running if record.worker_claimed_at else LifecycleState.Starting
        return record.model_copy(update={"lifecycle_state": lifecycle_state, "updated_at": _utcnow()})

    if aca_state == "Running":
        return record.model_copy(update={"lifecycle_state": LifecycleState.Running, "updated_at": _utcnow()})

    if aca_state == "Succeeded":
        resolved_result_url = result_url if result_url is not None else record.result_url
        if resolved_result_url is None:
            return record.model_copy(update={"lifecycle_state": LifecycleState.Running, "updated_at": _utcnow()})
        updates: dict[str, Any] = {
            "lifecycle_state": LifecycleState.Succeeded,
            "updated_at": _utcnow(),
        }
        if result_url is not None:
            updates["result_url"] = result_url
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state == "Failed":
        updates = {
            "lifecycle_state": LifecycleState.Failed,
            "error_code": record.error_code or "ACA_EXECUTION_FAILED",
            "updated_at": _utcnow(),
        }
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state == "Stopped":
        if record.cancellation_requested_at is not None:
            updates = {
                "lifecycle_state": LifecycleState.Cancelled,
                "updated_at": _utcnow(),
            }
            if record.completed_at is None:
                updates["completed_at"] = _utcnow()
            return record.model_copy(update=updates)
        updates = {
            "lifecycle_state": LifecycleState.Failed,
            "error_code": record.error_code or "ACA_EXECUTION_STOPPED",
            "updated_at": _utcnow(),
        }
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state in {"Degraded", "Unknown"}:
        return record

    raise ValueError(f"unsupported ACA state: {aca_state}")

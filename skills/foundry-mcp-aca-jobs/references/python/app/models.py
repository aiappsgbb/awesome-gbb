"""Canonical control-record models for foundry-mcp-aca-jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Literal
from uuid import UUID
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator, model_validator

try:  # pragma: no cover - exercised only when the real dependency exists locally.
    from fastmcp_tasks.models import GetTaskResult
except ModuleNotFoundError:  # pragma: no cover - local test shim and CLI help fallback.
    class GetTaskResult(BaseModel):
        model_config = ConfigDict(populate_by_name=True, extra="forbid", strict=True)

        task_id: str = Field(serialization_alias="taskId", min_length=1)
        status: Literal["working", "input_required", "completed", "failed", "cancelled"]
        created_at: str = Field(serialization_alias="createdAt", min_length=1)
        last_updated_at: str = Field(serialization_alias="lastUpdatedAt", min_length=1)
        ttl_ms: int | None = Field(default=None, serialization_alias="ttlMs")
        poll_interval_ms: int | None = Field(default=None, serialization_alias="pollIntervalMs")
        result: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        status_message: str | None = Field(default=None, serialization_alias="statusMessage")
        result_type: Literal["complete"] = Field(default="complete", serialization_alias="resultType")

__all__ = [
    "CallbackDeliveryState",
    "CallbackPolicy",
    "GetTaskResult",
    "JobPolicy",
    "LifecycleState",
    "PublicError",
    "Policy",
    "StartRequest",
    "TaskRecord",
    "map_aca_state",
    "to_mcp_task",
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
    ACCEPTED = "Accepted"
    STARTING = "Starting"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class CallbackDeliveryState(StrEnum):
    NOT_STARTED = "NotStarted"
    PENDING = "Pending"
    DELIVERED = "Delivered"
    EXHAUSTED = "Exhausted"


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


class JobPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_group: str
    job_name: str
    container_name: str
    image_digest: str = Field(pattern=r"^[^@]+@sha256:[0-9a-f]{64}$")
    command: list[str]
    allowed_owner_scopes: set[str] | None = None

    @field_validator("command", mode="before")
    @classmethod
    def _command_must_be_an_exact_list(cls, value: Any) -> Any:
        if not isinstance(value, list):
            raise ValueError("command must be a list[str]")
        return value


class CallbackPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl
    auth_mode: Literal["managed_identity", "key_vault"]
    audience: str | None = Field(default=None, min_length=1)
    secret_name: str | None = Field(default=None, min_length=1)

    @field_validator("url")
    @classmethod
    def _url_must_be_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("callback url must use https")
        if value.username or value.password:
            raise ValueError("callback url must not contain credentials")
        if value.query:
            raise ValueError("callback url must not contain query parameters")
        return value

    @model_validator(mode="after")
    def _validate_auth_fields(self) -> "CallbackPolicy":
        if self.auth_mode == "managed_identity":
            if not self.audience:
                raise ValueError("audience is required for managed_identity callbacks")
        elif self.auth_mode == "key_vault":
            if not self.secret_name:
                raise ValueError("secret_name is required for key_vault callbacks")
        return self


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jobs: dict[str, JobPolicy] = Field(default_factory=dict)
    callbacks: dict[str, CallbackPolicy] = Field(default_factory=dict)
    input_hosts: set[str] = Field(default_factory=set)
    result_hosts: set[str] = Field(default_factory=set)

    def job(self, key: str) -> JobPolicy:
        try:
            return self.jobs[key]
        except KeyError as exc:
            raise PublicError("INVALID_JOB_TYPE", "job type is not allowlisted") from exc

    def callback(self, alias: str) -> CallbackPolicy:
        try:
            return self.callbacks[alias]
        except KeyError as exc:
            raise PublicError("INVALID_CALLBACK_ALIAS", "callback alias is not allowlisted") from exc

    def validate_input(self, value: str | HttpUrl) -> HttpUrl:
        return self._validate_reference(value, self.input_hosts, "INVALID_INPUT_REFERENCE")

    def validate_result(self, value: str | HttpUrl) -> HttpUrl:
        return self._validate_reference(value, self.result_hosts, "INVALID_RESULT_REFERENCE")

    @staticmethod
    def _validate_reference(value: str | HttpUrl, allowed_hosts: set[str], code: str) -> HttpUrl:
        if isinstance(value, HttpUrl):
            scheme = value.scheme
            hostname = (value.host or "").lower()
            username = value.username
            password = value.password
            query = value.query
            raw_url = f"{value.scheme}://{value.host}{value.path}"
            if value.port not in (None, 443):
                raw_url = f"{value.scheme}://{value.host}:{value.port}{value.path}"
            if value.query:
                raw_url = f"{raw_url}?{value.query}"
        else:
            parsed = urlsplit(str(value))
            scheme = parsed.scheme
            hostname = (parsed.hostname or "").lower()
            username = parsed.username
            password = parsed.password
            query = parsed.query
            raw_url = parsed.geturl()

        if scheme != "https" or not hostname:
            raise PublicError(code, "reference must use https")
        if username or password:
            raise PublicError(code, "reference must not contain credentials")
        if hostname not in {host.lower() for host in allowed_hosts}:
            raise PublicError(code, "reference host is not allowlisted")
        if any(_is_secret_query_key(name) for name, _ in parse_qsl(query, keep_blank_values=True)):
            raise PublicError(code, "reference query contains credentials")
        return HttpUrl(raw_url)


def _is_secret_query_key(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in {
        "token",
        "access_token",
        "id_token",
        "refresh_token",
        "sig",
        "signature",
        "secret",
        "key",
        "sas",
        "sastoken",
    } or normalized.endswith("_token")


class StartRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    job_type: str = Field(alias="jobType")
    idempotency_key: str = Field(alias="idempotencyKey", min_length=1, max_length=200)
    input_ref: HttpUrl = Field(alias="inputRef")
    callback_alias: str = Field(alias="callbackAlias", min_length=1)

    @field_validator("input_ref")
    @classmethod
    def _https_only(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("inputRef must use https")
        return value


class TaskRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task_id: UUID = Field(alias="taskId")
    owner_scope: str = Field(alias="ownerScope")
    job_type: str = Field(alias="jobType")
    idempotency_key_hash: str = Field(alias="idempotencyKeyHash")
    request_fingerprint: str = Field(alias="requestFingerprint")
    input_ref: HttpUrl = Field(alias="inputRef")
    callback_alias: str = Field(alias="callbackAlias", min_length=1)
    lifecycle_state: LifecycleState = Field(default=LifecycleState.ACCEPTED, alias="lifecycleState")
    aca_execution_id: str | None = Field(default=None, alias="acaExecutionId")
    result_url: HttpUrl | None = Field(default=None, alias="resultUrl")
    error_code: str | None = Field(default=None, alias="errorCode")
    callback_delivery_state: CallbackDeliveryState = Field(
        default=CallbackDeliveryState.NOT_STARTED,
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

    @model_validator(mode="after")
    def _validate_succeeded_requires_result_url(self) -> "TaskRecord":
        if self.lifecycle_state is LifecycleState.SUCCEEDED and self.result_url is None:
            raise ValueError("resultUrl is required when lifecycleState is Succeeded")
        return self

    @classmethod
    def new(
        cls,
        *,
        owner_scope: str,
        job_type: str,
        idempotency_key_hash: str,
        request_fingerprint: str,
        input_ref: str | HttpUrl,
        callback_alias: str,
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
            lifecycleState=LifecycleState.ACCEPTED,
            callbackDeliveryState=CallbackDeliveryState.NOT_STARTED,
            createdAt=now,
            updatedAt=now,
        )

    def to_mcp_task(self) -> GetTaskResult:
        task_fields = {
            "task_id": str(self.task_id),
            "created_at": _to_utc_z(self.created_at),
            "last_updated_at": _to_utc_z(self.updated_at),
            "ttl_ms": 86400000,
            "poll_interval_ms": 2000,
        }
        if self.lifecycle_state in {
            LifecycleState.ACCEPTED,
            LifecycleState.STARTING,
            LifecycleState.RUNNING,
        }:
            return GetTaskResult(status="working", **task_fields)

        if self.lifecycle_state is LifecycleState.CANCELLED:
            return GetTaskResult(status="cancelled", **task_fields)

        if self.lifecycle_state is LifecycleState.SUCCEEDED:
            if self.result_url is None:
                return GetTaskResult(
                    status="failed",
                    error={
                        "code": -32603,
                        "message": "RESULT_REFERENCE_MISSING",
                    },
                    **task_fields,
                )
            result = {
                "content": [{"type": "text", "text": str(self.result_url)}],
                "structuredContent": {
                    "status": "Succeeded",
                    "resultUrl": str(self.result_url),
                },
                "isError": False,
            }
            return GetTaskResult(status="completed", result=result, **task_fields)

        if self.lifecycle_state is LifecycleState.FAILED:
            result = {
                "content": [{"type": "text", "text": self.error_code or "ACA_EXECUTION_FAILED"}],
                "isError": True,
            }
            return GetTaskResult(status="completed", result=result, **task_fields)

        return GetTaskResult(status="working", **task_fields)


def to_mcp_task(task: TaskRecord) -> GetTaskResult:
    return task.to_mcp_task()


def map_aca_state(
    record: TaskRecord,
    aca_state: str,
    *,
    result_url: str | HttpUrl | None = None,
    result_validator: Callable[[str], HttpUrl] | None = None,
    reconciliation_exhausted: bool = False,
) -> TaskRecord:
    if record.lifecycle_state in {
        LifecycleState.SUCCEEDED,
        LifecycleState.FAILED,
        LifecycleState.CANCELLED,
    }:
        return record

    if aca_state == "Processing":
        lifecycle_state = LifecycleState.RUNNING if record.worker_claimed_at else LifecycleState.STARTING
        return record.model_copy(update={"lifecycle_state": lifecycle_state, "updated_at": _utcnow()})

    if aca_state == "Running":
        return record.model_copy(update={"lifecycle_state": LifecycleState.RUNNING, "updated_at": _utcnow()})

    if aca_state == "Succeeded":
        resolved_result_url = record.result_url
        if result_url is not None:
            if result_validator is None:
                raise PublicError("INVALID_RESULT_REFERENCE", "result reference must be validated before persistence")
            if isinstance(result_url, HttpUrl):
                if result_url.username or result_url.password:
                    raise PublicError("INVALID_RESULT_REFERENCE", "reference must not contain credentials")
                candidate_result_url = f"{result_url.scheme}://{result_url.host}{result_url.path}"
                if result_url.port not in (None, 443):
                    candidate_result_url = f"{result_url.scheme}://{result_url.host}:{result_url.port}{result_url.path}"
                if result_url.query:
                    candidate_result_url = f"{candidate_result_url}?{result_url.query}"
            else:
                candidate_result_url = result_url
            resolved_result_url = result_validator(candidate_result_url)
        if resolved_result_url is None:
            if reconciliation_exhausted:
                updates = {
                    "lifecycle_state": LifecycleState.FAILED,
                    "error_code": "RESULT_REFERENCE_MISSING",
                    "updated_at": _utcnow(),
                }
                if record.completed_at is None:
                    updates["completed_at"] = _utcnow()
                return record.model_copy(update=updates)
            return record.model_copy(update={"lifecycle_state": LifecycleState.RUNNING, "updated_at": _utcnow()})
        updates: dict[str, Any] = {
            "lifecycle_state": LifecycleState.SUCCEEDED,
            "updated_at": _utcnow(),
        }
        updates["result_url"] = resolved_result_url
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state == "Failed":
        updates = {
            "lifecycle_state": LifecycleState.FAILED,
            "error_code": record.error_code or "ACA_EXECUTION_FAILED",
            "updated_at": _utcnow(),
        }
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state == "Stopped":
        if record.cancellation_requested_at is not None:
            updates = {
                "lifecycle_state": LifecycleState.CANCELLED,
                "updated_at": _utcnow(),
            }
            if record.completed_at is None:
                updates["completed_at"] = _utcnow()
            return record.model_copy(update=updates)
        updates = {
            "lifecycle_state": LifecycleState.FAILED,
            "error_code": record.error_code or "ACA_EXECUTION_STOPPED",
            "updated_at": _utcnow(),
        }
        if record.completed_at is None:
            updates["completed_at"] = _utcnow()
        return record.model_copy(update=updates)

    if aca_state in {"Degraded", "Unknown"}:
        if reconciliation_exhausted:
            updates = {
                "lifecycle_state": LifecycleState.FAILED,
                "error_code": "ACA_EXECUTION_STATE_UNRESOLVED",
                "updated_at": _utcnow(),
            }
            if record.completed_at is None:
                updates["completed_at"] = _utcnow()
            return record.model_copy(update=updates)
        return record

    raise ValueError(f"unsupported ACA state: {aca_state}")

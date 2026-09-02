"""Canonical ACA Job worker for foundry-mcp-aca-jobs.

This module keeps the business worker separate from the MCP server and
persists job-owned output before any callback delivery.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from azure.core.exceptions import ResourceExistsError
from azure.identity.aio import ManagedIdentityCredential
from azure.storage.blob.aio import ContainerClient

from .callbacks import CallbackSender, callback_payload
from .control_store import ConcurrencyError, ControlStore
from .models import CallbackDeliveryState, CallbackPolicy, JobPolicy, LifecycleState, Policy, PublicError, TaskRecord

__all__ = [
    "BlobOutputStore",
    "JobWorker",
    "OutputStore",
    "build_arg_parser",
    "build_worker_from_env",
    "demo_handler",
    "main",
]

TERMINAL_STATES = {
    LifecycleState.SUCCEEDED,
    LifecycleState.FAILED,
    LifecycleState.CANCELLED,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _serialize_json(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@runtime_checkable
class OutputStore(Protocol):
    async def write_json(self, path: str, payload: Any, overwrite: bool = False) -> str: ...

    async def exists(self, path: str) -> bool: ...

    async def get(self, path: str) -> str: ...


class BlobOutputStore:
    def __init__(self, container_client: ContainerClient) -> None:
        self._container_client = container_client

    @classmethod
    def from_container_url(cls, container_url: str, credential: Any | None = None) -> "BlobOutputStore":
        if credential is None:
            credential = ManagedIdentityCredential()
        return cls(ContainerClient.from_container_url(container_url, credential=credential))

    @staticmethod
    def result_path(task_id: str) -> str:
        return f"results/{task_id}/result.json"

    async def write_json(self, path: str, payload: Any, overwrite: bool = False) -> str:
        blob_client = self._container_client.get_blob_client(path)
        await blob_client.upload_blob(
            _serialize_json(payload),
            overwrite=overwrite,
            content_type="application/json",
        )
        return _strip_query(str(blob_client.url))

    async def exists(self, path: str) -> bool:
        blob_client = self._container_client.get_blob_client(path)
        return await blob_client.exists()

    async def get(self, path: str) -> str:
        blob_client = self._container_client.get_blob_client(path)
        if not await blob_client.exists():
            raise FileNotFoundError(path)
        return _strip_query(str(blob_client.url))


@dataclass(frozen=True)
class WorkerRuntimeConfig:
    output_container_url: str
    lease: timedelta
    policy: Policy


class JobWorker:
    def __init__(
        self,
        store: ControlStore,
        output: OutputStore,
        handler: Callable[[str, str], Awaitable[Any] | Any],
        callback_sender: Any,
        policy: Policy,
        clock: Callable[[], datetime],
        lease: timedelta = timedelta(minutes=5),
    ) -> None:
        self._store = store
        self._output = output
        self._handler = handler
        self._callback_sender = callback_sender
        self._policy = policy
        self._clock = clock
        self._lease = lease

    async def run(self, owner_scope: str, task_id: str) -> int:
        current = await self._store.get(owner_scope, task_id)
        if current.lifecycle_state in TERMINAL_STATES:
            return 0

        now = self._clock()
        if current.worker_claim_expires_at is not None and current.worker_claim_expires_at > now:
            return 0

        claimed = await self._claim(current, now)
        if claimed is None:
            return 0

        result_path = self._output.result_path(str(claimed.task_id)) if hasattr(self._output, "result_path") else f"results/{claimed.task_id}/result.json"
        if await self._output.exists(result_path):
            result_url = await self._output.get(result_path)
        else:
            try:
                result = await _await_if_needed(self._handler(str(claimed.input_ref), str(claimed.task_id)))
            except PublicError as error:
                await self._persist_failure(claimed, error.code)
                return 0
            except Exception:
                await self._persist_failure(claimed, "WORKER_EXECUTION_FAILED")
                return 0

            try:
                result_url = await self._output.write_json(result_path, result, overwrite=False)
            except ResourceExistsError:
                result_url = await self._output.get(result_path)

        succeeded = await self._persist_succeeded(claimed, result_url)
        await self._send_callback(succeeded, result_url)
        return 0

    async def _claim(self, current: TaskRecord, now: datetime) -> TaskRecord | None:
        token = str(uuid4())
        next_task = current.model_copy(
            update={
                "lifecycle_state": LifecycleState.RUNNING,
                "worker_claimed_at": now,
                "worker_claim_token": token,
                "worker_claim_expires_at": now + self._lease,
                "updated_at": now,
            }
        )
        for _ in range(3):
            try:
                return await self._store.replace(next_task, current.etag)
            except ConcurrencyError:
                current = await self._store.get(current.owner_scope, str(current.task_id))
                if current.lifecycle_state in TERMINAL_STATES:
                    return None
                if current.worker_claim_expires_at is not None and current.worker_claim_expires_at > now:
                    return None
                next_task = current.model_copy(
                    update={
                        "lifecycle_state": LifecycleState.RUNNING,
                        "worker_claimed_at": now,
                        "worker_claim_token": token,
                        "worker_claim_expires_at": now + self._lease,
                        "updated_at": now,
                    }
                )
        return None

    async def _persist_failure(self, task: TaskRecord, error_code: str) -> TaskRecord:
        now = self._clock()
        failed = task.model_copy(
            update={
                "lifecycle_state": LifecycleState.FAILED,
                "error_code": error_code,
                "result_url": None,
                "callback_delivery_state": CallbackDeliveryState.NOT_STARTED,
                "callback_error_code": None,
                "worker_claimed_at": None,
                "worker_claim_token": None,
                "worker_claim_expires_at": None,
                "updated_at": now,
                "completed_at": now,
            }
        )
        return await self._store.replace(failed, task.etag)

    async def _persist_succeeded(self, task: TaskRecord, result_url: str) -> TaskRecord:
        now = self._clock()
        succeeded = task.model_copy(
            update={
                "lifecycle_state": LifecycleState.SUCCEEDED,
                "result_url": self._policy.validate_result(result_url),
                "error_code": None,
                "callback_delivery_state": CallbackDeliveryState.PENDING,
                "callback_error_code": None,
                "worker_claimed_at": None,
                "worker_claim_token": None,
                "worker_claim_expires_at": None,
                "updated_at": now,
                "completed_at": now,
            }
        )
        return await self._store.replace(succeeded, task.etag)

    async def _persist_callback_state(self, task: TaskRecord, state: CallbackDeliveryState, callback_error_code: str | None) -> TaskRecord:
        now = self._clock()
        updated = task.model_copy(
            update={
                "callback_delivery_state": state,
                "callback_error_code": callback_error_code,
                "updated_at": now,
            }
        )
        return await self._store.replace(updated, task.etag)

    async def _send_callback(self, task: TaskRecord, result_url: str) -> None:
        callback_policy = self._policy.callback(task.callback_alias)
        payload = callback_payload(
            str(task.task_id),
            task.aca_execution_id or str(task.task_id),
            "Succeeded",
            result_url,
        )
        try:
            await self._callback_sender.send(callback_policy, payload)
        except PublicError as error:
            if error.code != "CALLBACK_DELIVERY_EXHAUSTED":
                raise
            await self._persist_callback_state(task, CallbackDeliveryState.EXHAUSTED, error.code)
            return
        await self._persist_callback_state(task, CallbackDeliveryState.DELIVERED, None)


async def demo_handler(input_ref: str, task_id: str) -> dict[str, str]:
    parsed = urlsplit(input_ref)
    return {
        "taskId": task_id,
        "inputHost": parsed.hostname or "",
        "inputPath": parsed.path or "/",
    }


def _parse_hosts(value: str | None, *, default: set[str]) -> set[str]:
    if value is None:
        return set(default)
    return {part.strip() for part in value.split(",") if part.strip()}


def load_runtime_config_from_env() -> WorkerRuntimeConfig:
    job_type = os.environ["MCP_ACA_JOBS_JOB_TYPE"]
    job_resource_group = os.environ["MCP_ACA_JOBS_JOB_RESOURCE_GROUP"]
    job_name = os.environ["MCP_ACA_JOBS_JOB_NAME"]
    job_container_name = os.environ["MCP_ACA_JOBS_JOB_CONTAINER_NAME"]
    job_image_digest = os.environ["MCP_ACA_JOBS_JOB_IMAGE_DIGEST"]
    callback_url = os.environ["MCP_ACA_JOBS_CALLBACK_URL"]
    callback_audience = os.environ["MCP_ACA_JOBS_CALLBACK_AUDIENCE"]
    output_container_url = os.environ["MCP_ACA_JOBS_OUTPUT_CONTAINER_URL"]
    input_hosts = _parse_hosts(os.environ.get("MCP_ACA_JOBS_INPUT_HOSTS"), default={"input.example.com"})
    result_hosts = _parse_hosts(os.environ.get("MCP_ACA_JOBS_RESULT_HOSTS"), default={"results.example.com"})
    lease_minutes = int(os.environ.get("MCP_ACA_JOBS_LEASE_MINUTES", "5"))
    policy = Policy(
        jobs={
            job_type: JobPolicy(
                resource_group=job_resource_group,
                job_name=job_name,
                container_name=job_container_name,
                image_digest=job_image_digest,
                command=["python", "-m", "app.job_worker"],
                allowed_owner_scopes=None,
            )
        },
        callbacks={
            "ops": CallbackPolicy(
                url=callback_url,
                auth_mode="managed_identity",
                audience=callback_audience,
            )
        },
        input_hosts=input_hosts,
        result_hosts=result_hosts,
    )
    return WorkerRuntimeConfig(
        output_container_url=output_container_url,
        lease=timedelta(minutes=lease_minutes),
        policy=policy,
    )


def build_worker_from_env(store: ControlStore, *, clock: Callable[[], datetime] = _utcnow, handler: Any = demo_handler, callback_sender: Any | None = None) -> JobWorker:
    config = load_runtime_config_from_env()
    if callback_sender is None:
        raise RuntimeError("callback sender must be provided by the worker runtime")
    output = BlobOutputStore.from_container_url(config.output_container_url)
    return JobWorker(
        store=store,
        output=output,
        handler=handler,
        callback_sender=callback_sender,
        policy=config.policy,
        clock=clock,
        lease=config.lease,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the foundry-mcp-aca-jobs ACA Job worker.")
    parser.add_argument("--owner-scope", required=True, help="Owner scope for the durable control record.")
    parser.add_argument("--task-id", required=True, help="Task identifier to process.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _ = load_runtime_config_from_env()
    raise RuntimeError(
        "The command-line entrypoint is a thin wrapper around build_worker_from_env(); "
        "wire the store and callback sender in the hosting runtime before invoking run()."
    )


if __name__ == "__main__":
    raise SystemExit(main())

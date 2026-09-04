"""Canonical orchestration service for foundry-mcp-aca-jobs.

Source of truth for the prose example in ../../../SKILL.md § Idempotency and uncertain-start reconciliation.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from .aca_jobs import AcaExecution, AcaJobsClient
from .control_store import ConcurrencyError, ControlStore
from .models import LifecycleState, Policy, PublicError, StartRequest, TaskRecord, map_aca_state
from .telemetry import Telemetry, telemetry as default_telemetry

__all__ = ["Orchestrator"]

_START_RECONCILIATION_GRACE = timedelta(seconds=2)
_CANCELLATION_RECONCILIATION_GRACE = timedelta(seconds=30)
_START_RECONCILIATION_BUDGET = timedelta(minutes=5)
_UNRESOLVED_RECONCILIATION_BUDGET = timedelta(minutes=10)
_ACA_EXECUTION_PRIORITY = {
    "Succeeded": 0,
    "Running": 1,
    "Processing": 2,
    "Failed": 3,
    "Stopped": 4,
    "Degraded": 5,
    "Unknown": 6,
}


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class Orchestrator:
    def __init__(
        self,
        store: ControlStore,
        jobs: AcaJobsClient,
        policy: Policy,
        clock: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[Any] | Any] | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        self._store = store
        self._jobs = jobs
        self._policy = policy
        self._clock = clock
        self._sleep = sleep or asyncio.sleep
        self._telemetry = telemetry or default_telemetry

    @staticmethod
    def _canonical_request_fingerprint(request: StartRequest) -> str:
        payload = {
            "callbackAlias": request.callback_alias,
            "inputRef": str(request.input_ref),
            "jobType": request.job_type,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _idempotency_key_hash(self, owner_scope: str, request: StartRequest) -> str:
        data = f"{owner_scope}\0{request.job_type}\0{request.idempotency_key}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _telemetry_attributes(
        self,
        task: TaskRecord,
        operation: str,
        *,
        outcome: str | None = None,
        error_code: str | None = None,
        azure_request_id: str | None = None,
    ) -> dict[str, str]:
        return self._telemetry.attributes(
            {
                "task.id": str(task.task_id),
                "job.type": task.job_type,
                "task.state": task.lifecycle_state.value,
                "aca.execution.id": task.aca_execution_id,
                "operation": operation,
                "outcome": outcome,
                "error.code": error_code,
                "azure.request.id": azure_request_id,
            }
        )

    async def start(self, request: StartRequest, owner_scope: str) -> TaskRecord:
        job_policy = self._policy.job(request.job_type)
        if (
            job_policy.allowed_owner_scopes is not None
            and owner_scope not in job_policy.allowed_owner_scopes
        ):
            raise PublicError("INVALID_JOB_TYPE", "job type is not allowlisted")
        self._policy.callback(request.callback_alias)
        validated_input = self._policy.validate_input(request.input_ref)

        idempotency_key_hash = self._idempotency_key_hash(owner_scope, request)
        request_fingerprint = self._canonical_request_fingerprint(request)
        task = TaskRecord.new(
            owner_scope=owner_scope,
            job_type=request.job_type,
            idempotency_key_hash=idempotency_key_hash,
            request_fingerprint=request_fingerprint,
            input_ref=validated_input,
            callback_alias=request.callback_alias,
        )
        with self._telemetry.operation("orchestrator.start", self._telemetry_attributes(task, "orchestrator.start")):
            with self._telemetry.operation("store.create_or_get", self._telemetry_attributes(task, "store.create_or_get")):
                current = await self._store.create_or_get(task)

            if (
                current.lifecycle_state is not LifecycleState.ACCEPTED
                or current.start_attempt_count > 0
                or current.aca_execution_id is not None
            ):
                self._telemetry.record(
                    "duplicate",
                    self._telemetry_attributes(current, "duplicate"),
                    outcome="duplicate",
                )
                return current

            claimed = await self._claim_start(current)
            if claimed is None:
                with self._telemetry.operation("store.get", self._telemetry_attributes(current, "store.get")):
                    return await self._store.get(owner_scope, str(task.task_id))

            try:
                with self._telemetry.operation("aca.start", self._telemetry_attributes(claimed, "aca.start")):
                    execution = await self._jobs.start(job_policy, owner_scope, str(task.task_id))
            except PublicError as error:
                if error.code == "ARM_START_REJECTED":
                    await self._persist_failed_start(claimed, error)
                    raise
                if error.code == "ARM_STATUS_UNAVAILABLE":
                    return claimed
                if error.code == "DEPLOYMENT_CONTRACT_MISMATCH":
                    self._telemetry.record(
                        "digest_mismatch",
                        self._telemetry_attributes(claimed, "digest_mismatch"),
                        outcome="failure",
                        error_code=error.code,
                    )
                raise

            return await self._bind_execution(claimed, execution, job_policy)

    async def get_status(self, owner_scope: str, task_id: str) -> TaskRecord:
        with self._telemetry.operation("orchestrator.get", {"task.id": task_id, "operation": "orchestrator.get"}):
            with self._telemetry.operation("store.get", {"task.id": task_id, "operation": "store.get"}):
                task = await self._store.get(owner_scope, task_id)
            if task.lifecycle_state in {LifecycleState.SUCCEEDED, LifecycleState.FAILED, LifecycleState.CANCELLED}:
                return task

            if task.aca_execution_id is None:
                if task.lifecycle_state is LifecycleState.STARTING:
                    return await self.reconcile(owner_scope, task_id)
                return task

            job_policy = self._policy.job(task.job_type)
            try:
                with self._telemetry.operation("aca.get", self._telemetry_attributes(task, "aca.get")):
                    execution = await self._jobs.get(job_policy, task.aca_execution_id)
            except PublicError as error:
                if error.code == "ARM_STATUS_UNAVAILABLE":
                    return task
                if error.code == "DEPLOYMENT_CONTRACT_MISMATCH":
                    self._telemetry.record(
                        "digest_mismatch",
                        self._telemetry_attributes(task, "digest_mismatch"),
                        outcome="failure",
                        error_code=error.code,
                    )
                raise

            return await self._bind_execution(task, execution, job_policy)

    async def cancel(self, owner_scope: str, task_id: str) -> TaskRecord:
        with self._telemetry.operation("orchestrator.cancel", {"task.id": task_id, "operation": "orchestrator.cancel"}):
            with self._telemetry.operation("store.get", {"task.id": task_id, "operation": "store.get"}):
                task = await self._store.get(owner_scope, task_id)
            if task.lifecycle_state in {LifecycleState.SUCCEEDED, LifecycleState.FAILED, LifecycleState.CANCELLED}:
                return task

            task = await self._mark_cancellation_requested(task)
            self._telemetry.record(
                "cancellation",
                self._telemetry_attributes(task, "cancellation"),
                outcome="requested",
            )
            if task.start_attempt_count == 0 and task.aca_execution_id is None:
                return await self._persist_cancelled(task)

            job_policy = self._policy.job(task.job_type)
            if task.aca_execution_id is None:
                task = await self._reconcile_without_restart(task, job_policy)
                return task

            try:
                with self._telemetry.operation("aca.stop", self._telemetry_attributes(task, "aca.stop")):
                    await self._jobs.stop(job_policy, task.aca_execution_id)
            except PublicError as error:
                if error.code in {"ARM_STATUS_UNAVAILABLE", "ARM_STOP_REJECTED"}:
                    return task
                if error.code == "DEPLOYMENT_CONTRACT_MISMATCH":
                    self._telemetry.record(
                        "digest_mismatch",
                        self._telemetry_attributes(task, "digest_mismatch"),
                        outcome="failure",
                        error_code=error.code,
                    )
                raise
            return task

    async def reconcile(self, owner_scope: str, task_id: str) -> TaskRecord:
        with self._telemetry.operation("orchestrator.reconcile", {"task.id": task_id, "operation": "orchestrator.reconcile"}):
            with self._telemetry.operation("store.get", {"task.id": task_id, "operation": "store.get"}):
                task = await self._store.get(owner_scope, task_id)
            if task.lifecycle_state in {LifecycleState.SUCCEEDED, LifecycleState.FAILED, LifecycleState.CANCELLED}:
                return task
            job_policy = self._policy.job(task.job_type)
            return await self._reconcile(task, job_policy)

    @staticmethod
    def _can_claim_start(current: TaskRecord, expected: TaskRecord) -> bool:
        return (
            current.lifecycle_state in {LifecycleState.ACCEPTED, LifecycleState.STARTING}
            and current.cancellation_requested_at is None
            and current.aca_execution_id is None
            and current.start_attempt_count == expected.start_attempt_count
            and current.start_attempted_at == expected.start_attempted_at
        )

    async def _claim_start(self, task: TaskRecord) -> TaskRecord | None:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if not self._can_claim_start(current, task):
                return current
            return current.model_copy(
                update={
                    "lifecycle_state": LifecycleState.STARTING,
                    "start_attempted_at": current.start_attempted_at or now,
                    "start_attempt_count": current.start_attempt_count + 1,
                    "updated_at": now,
                }
            )

        for _ in range(3):
            with self._telemetry.operation("store.get", self._telemetry_attributes(task, "store.get")):
                current = await self._store.get(task.owner_scope, str(task.task_id))
            candidate = mutate(current)
            if candidate == current:
                return None
            try:
                with self._telemetry.operation("store.replace", self._telemetry_attributes(candidate, "store.replace")):
                    return await self._store.replace(candidate, current.etag)
            except ConcurrencyError:
                self._telemetry.record(
                    "etag_conflict",
                    self._telemetry_attributes(current, "etag_conflict"),
                    outcome="conflict",
                )
                with self._telemetry.operation("store.get", self._telemetry_attributes(task, "store.get")):
                    current = await self._store.get(task.owner_scope, str(task.task_id))
                if not self._can_claim_start(current, task):
                    return None
                continue

        return None

    async def _persist_failed_start(self, task: TaskRecord, error: PublicError) -> TaskRecord:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if current.lifecycle_state is LifecycleState.FAILED and current.error_code == error.code:
                return current
            return current.model_copy(
                update={
                    "lifecycle_state": LifecycleState.FAILED,
                    "error_code": error.code,
                    "updated_at": now,
                    "completed_at": current.completed_at or now,
                }
            )

        return await self._apply_with_retry(task.owner_scope, str(task.task_id), mutate)

    async def _bind_execution(self, task: TaskRecord, execution: AcaExecution, job_policy: Any) -> TaskRecord:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if current.lifecycle_state in {LifecycleState.SUCCEEDED, LifecycleState.FAILED, LifecycleState.CANCELLED}:
                return current
            if current.aca_execution_id not in {None, execution.execution_id}:
                return current
            result_url = str(current.result_url) if current.result_url is not None else None
            result_validator = self._policy.validate_result if result_url is not None else None
            unresolved = execution.status in {"Degraded", "Unknown"} or (
                execution.status == "Succeeded" and result_url is None
            )
            reconciliation_anchor = current.start_attempted_at or current.updated_at
            active_worker_lease = (
                current.worker_claim_token is not None
                and current.worker_claim_expires_at is not None
                and current.worker_claim_expires_at > now
            )
            reconciliation_exhausted = (
                unresolved
                and now - reconciliation_anchor >= _UNRESOLVED_RECONCILIATION_BUDGET
                and not active_worker_lease
            )
            candidate = current.model_copy(
                update={
                    "aca_execution_id": execution.execution_id,
                    "lifecycle_state": (
                        LifecycleState.RUNNING
                        if unresolved
                        else current.lifecycle_state
                    ),
                    "updated_at": now,
                }
            )
            mapped = map_aca_state(
                candidate,
                execution.status,
                result_url=result_url,
                result_validator=result_validator,
                reconciliation_exhausted=reconciliation_exhausted,
                now=now,
            )
            if reconciliation_exhausted and mapped.lifecycle_state is LifecycleState.FAILED:
                mapped = mapped.model_copy(
                    update={
                        "worker_claimed_at": None,
                        "worker_claim_token": None,
                        "worker_claim_expires_at": None,
                    }
                )
            if (
                mapped.lifecycle_state is LifecycleState.SUCCEEDED
                and current.lifecycle_state is LifecycleState.STARTING
            ):
                return candidate.model_copy(
                    update={
                        "lifecycle_state": LifecycleState.RUNNING,
                        "updated_at": now,
                    }
                )
            return mapped

        persisted = await self._apply_with_retry(task.owner_scope, str(task.task_id), mutate)
        if (
            persisted.cancellation_requested_at is not None
            and persisted.lifecycle_state
            not in {LifecycleState.SUCCEEDED, LifecycleState.FAILED, LifecycleState.CANCELLED}
            and persisted.aca_execution_id == execution.execution_id
        ):
            await self._best_effort_stop(job_policy, execution.execution_id)
        if (
            execution.status == "Succeeded"
            and persisted.lifecycle_state is LifecycleState.RUNNING
            and persisted.result_url is not None
            and persisted.aca_execution_id == execution.execution_id
        ):
            result_url = str(persisted.result_url)
            result_validator = self._policy.validate_result

            def promote(current: TaskRecord) -> TaskRecord:
                if current.aca_execution_id != execution.execution_id:
                    return current
                candidate = current.model_copy(
                    update={
                        "aca_execution_id": execution.execution_id,
                        "updated_at": now,
                    }
                )
                return map_aca_state(
                    candidate,
                    execution.status,
                    result_url=result_url,
                    result_validator=result_validator,
                    now=now,
                )

            return await self._apply_with_retry(task.owner_scope, str(task.task_id), promote)
        return persisted

    async def _persist_cancelled(self, task: TaskRecord) -> TaskRecord:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if current.lifecycle_state is LifecycleState.CANCELLED:
                return current
            return current.model_copy(
                update={
                    "lifecycle_state": LifecycleState.CANCELLED,
                    "updated_at": now,
                    "completed_at": current.completed_at or now,
                }
            )

        return await self._apply_with_retry(task.owner_scope, str(task.task_id), mutate)

    async def _mark_cancellation_requested(self, task: TaskRecord) -> TaskRecord:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if current.cancellation_requested_at is not None:
                return current
            return current.model_copy(
                update={
                    "cancellation_requested_at": now,
                    "updated_at": now,
                }
            )

        return await self._apply_with_retry(task.owner_scope, str(task.task_id), mutate)

    async def _apply_with_retry(
        self,
        owner_scope: str,
        task_id: str,
        mutator: Callable[[TaskRecord], TaskRecord],
    ) -> TaskRecord:
        last_error: ConcurrencyError | None = None
        for _ in range(3):
            with self._telemetry.operation("store.get", {"task.id": task_id, "operation": "store.get"}):
                current = await self._store.get(owner_scope, task_id)
            candidate = mutator(current)
            if candidate == current:
                return current
            try:
                with self._telemetry.operation("store.replace", self._telemetry_attributes(candidate, "store.replace")):
                    return await self._store.replace(candidate, current.etag)
            except ConcurrencyError as error:
                last_error = error
                self._telemetry.record(
                    "etag_conflict",
                    self._telemetry_attributes(current, "etag_conflict"),
                    outcome="conflict",
                )
                continue
        if last_error is not None:
            raise last_error
        with self._telemetry.operation("store.get", {"task.id": task_id, "operation": "store.get"}):
            return await self._store.get(owner_scope, task_id)

    async def _reconcile_matches(
        self,
        task: TaskRecord,
        job_policy: Any,
        matches: list[AcaExecution],
    ) -> tuple[TaskRecord, bool]:
        with self._telemetry.operation("store.get", self._telemetry_attributes(task, "store.get")):
            current = await self._store.get(task.owner_scope, str(task.task_id))
        if current.lifecycle_state in {
            LifecycleState.SUCCEEDED,
            LifecycleState.FAILED,
            LifecycleState.CANCELLED,
        }:
            return current, True
        if not matches:
            return current, False

        candidate = next(
            (
                execution
                for execution in matches
                if execution.execution_id == current.aca_execution_id
            ),
            None,
        )
        if current.aca_execution_id is None:
            candidate = self._select_winner(matches)

        persisted = current
        if candidate is not None:
            persisted = await self._bind_execution(current, candidate, job_policy)

        authoritative_id = persisted.aca_execution_id
        for execution in matches:
            if execution.execution_id != authoritative_id:
                await self._best_effort_stop(job_policy, execution.execution_id)
        return persisted, True

    async def _reconcile_without_restart(self, task: TaskRecord, job_policy: Any) -> TaskRecord:
        matches = await self._matching_executions(task, job_policy)
        current, handled = await self._reconcile_matches(task, job_policy, matches)
        if handled:
            return current
        if current.cancellation_requested_at is not None:
            return await self._persist_cancellation_if_ready(current)
        return current

    async def _reconcile(self, task: TaskRecord, job_policy: Any) -> TaskRecord:
        if task.cancellation_requested_at is not None:
            return await self._reconcile_without_restart(task, job_policy)

        matches = await self._matching_executions(task, job_policy)
        current, handled = await self._reconcile_matches(task, job_policy, matches)
        if handled or current.aca_execution_id is not None:
            return current
        task = current

        if task.start_attempted_at is None:
            return task

        now = self._clock()
        elapsed = now - task.start_attempted_at
        if task.start_attempt_count >= 3 or elapsed >= _START_RECONCILIATION_BUDGET:
            exhausted = await self._persist_reconciliation_exhausted(task)
            if (
                exhausted.lifecycle_state is LifecycleState.FAILED
                and exhausted.error_code == "START_RECONCILIATION_EXHAUSTED"
            ):
                raise PublicError(
                    "START_RECONCILIATION_EXHAUSTED",
                    "start reconciliation exhausted",
                )
            return exhausted

        if elapsed < _START_RECONCILIATION_GRACE:
            return task

        claimed = await self._claim_start(task)
        if claimed is None:
            with self._telemetry.operation("store.get", {"task.id": str(task.task_id), "operation": "store.get"}):
                return await self._store.get(task.owner_scope, str(task.task_id))

        try:
            with self._telemetry.operation("aca.start", self._telemetry_attributes(claimed, "aca.start")):
                execution = await self._jobs.start(job_policy, task.owner_scope, str(task.task_id))
        except PublicError as error:
            if error.code == "ARM_START_REJECTED":
                return await self._persist_failed_start(claimed, error)
            if error.code == "ARM_STATUS_UNAVAILABLE":
                return claimed
            if error.code == "DEPLOYMENT_CONTRACT_MISMATCH":
                self._telemetry.record(
                    "digest_mismatch",
                    self._telemetry_attributes(claimed, "digest_mismatch"),
                    outcome="failure",
                    error_code=error.code,
                )
            raise
        return await self._bind_execution(claimed, execution, job_policy)

    async def _persist_reconciliation_exhausted(self, task: TaskRecord) -> TaskRecord:
        now = self._clock()

        def mutate(current: TaskRecord) -> TaskRecord:
            if current.lifecycle_state is LifecycleState.FAILED and current.error_code == "START_RECONCILIATION_EXHAUSTED":
                return current
            if (
                current.lifecycle_state
                not in {LifecycleState.ACCEPTED, LifecycleState.STARTING}
                or current.aca_execution_id is not None
                or current.worker_claimed_at is not None
                or current.cancellation_requested_at is not None
            ):
                return current
            return current.model_copy(
                update={
                    "lifecycle_state": LifecycleState.FAILED,
                    "error_code": "START_RECONCILIATION_EXHAUSTED",
                    "updated_at": now,
                    "completed_at": current.completed_at or now,
                }
            )

        return await self._apply_with_retry(task.owner_scope, str(task.task_id), mutate)

    async def _persist_cancellation_if_ready(self, task: TaskRecord) -> TaskRecord:
        now = self._clock()
        if now - task.cancellation_requested_at < _CANCELLATION_RECONCILIATION_GRACE:
            return task
        return await self._persist_cancelled(task)

    async def _matching_executions(self, task: TaskRecord, job_policy: Any) -> list[AcaExecution]:
        with self._telemetry.operation("aca.list", self._telemetry_attributes(task, "aca.list")):
            executions = await self._jobs.list(job_policy)
        return [execution for execution in executions if execution.matches_task(str(task.task_id), task.start_attempted_at)]

    @staticmethod
    def _select_winner(executions: list[AcaExecution]) -> AcaExecution:
        return sorted(
            executions,
            key=lambda execution: (
                _ACA_EXECUTION_PRIORITY.get(execution.status, len(_ACA_EXECUTION_PRIORITY)),
                execution.start_time,
                execution.execution_id,
            ),
        )[0]

    async def _best_effort_stop(self, job_policy: Any, execution_id: str) -> None:
        try:
            with self._telemetry.operation("aca.stop", {"aca.execution.id": execution_id, "operation": "aca.stop"}):
                await self._jobs.stop(job_policy, execution_id)
        except PublicError as error:
            if error.code in {"ARM_STATUS_UNAVAILABLE", "ARM_STOP_REJECTED", "TASK_NOT_FOUND"}:
                return
            if error.code == "DEPLOYMENT_CONTRACT_MISMATCH":
                self._telemetry.record(
                    "digest_mismatch",
                    {"aca.execution.id": execution_id, "operation": "digest_mismatch"},
                    outcome="failure",
                    error_code=error.code,
                )
                return
            raise

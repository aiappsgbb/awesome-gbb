#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs ACA adapter."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

FASTMCP_TASKS_STUBBED = False
try:  # pragma: no cover - exercised only when the real dependency exists locally.
    from fastmcp_tasks.models import GetTaskResult  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local test shim only.
    FASTMCP_TASKS_STUBBED = True

    class GetTaskResult(types.SimpleNamespace):
        pass

    fastmcp_tasks = types.ModuleType("fastmcp_tasks")
    fastmcp_tasks.__path__ = []  # type: ignore[attr-defined]
    fastmcp_tasks_models = types.ModuleType("fastmcp_tasks.models")
    fastmcp_tasks_models.GetTaskResult = GetTaskResult
    fastmcp_tasks.models = fastmcp_tasks_models
    sys.modules["fastmcp_tasks"] = fastmcp_tasks
    sys.modules["fastmcp_tasks.models"] = fastmcp_tasks_models

try:  # pragma: no cover - exercised only when the real Azure SDK is unavailable.
    from azure.core.exceptions import HttpResponseError
    from azure.mgmt.appcontainers import ContainerAppsAPIClient
except ModuleNotFoundError:  # pragma: no cover - local fallback only.
    azure_module = types.ModuleType("azure")
    azure_core_module = types.ModuleType("azure.core")
    azure_core_exceptions_module = types.ModuleType("azure.core.exceptions")
    azure_mgmt_module = types.ModuleType("azure.mgmt")
    azure_appcontainers_module = types.ModuleType("azure.mgmt.appcontainers")

    class HttpResponseError(Exception):
        def __init__(self, message: object | None = None, response: object | None = None, **_: Any) -> None:
            super().__init__(message)
            self.response = response
            self.status_code = getattr(response, "status_code", None)

    class ContainerAppsAPIClient:  # pragma: no cover - fallback only.
        pass

    azure_core_exceptions_module.HttpResponseError = HttpResponseError
    azure_core_module.exceptions = azure_core_exceptions_module
    azure_module.core = azure_core_module
    azure_mgmt_module.appcontainers = azure_appcontainers_module
    azure_module.mgmt = azure_mgmt_module
    azure_appcontainers_module.ContainerAppsAPIClient = ContainerAppsAPIClient
    sys.modules.setdefault("azure", azure_module)
    sys.modules.setdefault("azure.core", azure_core_module)
    sys.modules.setdefault("azure.core.exceptions", azure_core_exceptions_module)
    sys.modules.setdefault("azure.mgmt", azure_mgmt_module)
    sys.modules.setdefault("azure.mgmt.appcontainers", azure_appcontainers_module)


def _http_response_error(status_code: int, message: str = "boom") -> HttpResponseError:
    response = SimpleNamespace(
        status_code=status_code,
        reason="reason",
        headers={},
        text=message,
    )
    class _HttpResponseError(Exception):
        pass

    error = _HttpResponseError(message)
    error.response = response
    error.status_code = status_code
    return error


class _Poller:
    def __init__(self, result: Any) -> None:
        self._result = result
        self.result = MagicMock(return_value=result)


class FoundryMcpAcaJobsAzureTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.models = importlib.import_module("app.models")
        cls.module = importlib.import_module("app.aca_jobs")
        cls.JobPolicy = cls.models.JobPolicy
        cls.PublicError = cls.models.PublicError
        cls.AcaExecution = cls.module.AcaExecution
        cls.AcaJobsAdapter = cls.module.AcaJobsAdapter

    def _policy(self) -> Any:
        return self.JobPolicy(
            resource_group="rg-jobs",
            job_name="job-worker",
            container_name="worker",
            image_digest="example.azurecr.io/worker@sha256:" + "a" * 64,
            command=["python", "-m", "app.job_worker"],
        )

    def _job(self) -> SimpleNamespace:
        container = SimpleNamespace(
            image=self._policy().image_digest,
            name="worker",
            command=["python", "-m", "app.job_worker"],
            args=["--owner-scope", "legacy-owner", "--task-id", "legacy-task"],
            env=[SimpleNamespace(name="KEEP", value="1")],
            resources=SimpleNamespace(cpu=1, memory="2Gi"),
        )
        template = SimpleNamespace(
            containers=[container],
            init_containers=[SimpleNamespace(name="init", command=["sh"], args=["-c", "echo init"], env=[])],
            volumes=[SimpleNamespace(name="vol")],
        )
        configuration = SimpleNamespace(
            trigger_type="Manual",
            identity_settings=[SimpleNamespace(name="mi")],
            secrets=[SimpleNamespace(name="secret")],
            registries=[SimpleNamespace(server="example.azurecr.io")],
        )
        return SimpleNamespace(
            properties=SimpleNamespace(
                template=template,
                configuration=configuration,
                environment_id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.App/managedEnvironments/env",
            ),
            identity=SimpleNamespace(type="UserAssigned", user_assigned_identities={"mi": {}}),
        )

    def _start_ack(self, execution_id: str, *, name: str | None = None, id_value: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            name=name or execution_id,
            id=id_value or f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.App/jobs/job-worker/executions/{execution_id}",
        )

    def _start_ack_with_template(
        self,
        execution_id: str,
        *,
        containers: list[Any],
        name: str | None = None,
        id_value: str | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            name=name or execution_id,
            id=id_value or f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.App/jobs/job-worker/executions/{execution_id}",
            properties=SimpleNamespace(
                status="Processing",
                start_time=datetime(2026, 9, 2, 17, 0, 0, tzinfo=timezone.utc),
                template=SimpleNamespace(containers=containers, init_containers=[], volumes=[]),
            ),
        )

    def _execution(
        self,
        *,
        execution_id: str,
        status: str,
        start_time: datetime,
        args: list[str],
        name: str | None = None,
    ) -> SimpleNamespace:
        container = SimpleNamespace(
            image=self._policy().image_digest,
            name="worker",
            command=["python", "-m", "app.job_worker"],
            args=args,
            env=[SimpleNamespace(name="KEEP", value="1")],
            resources=SimpleNamespace(cpu=1, memory="2Gi"),
        )
        return SimpleNamespace(
            name=name or execution_id,
            id=f"/subscriptions/sub/resourceGroups/rg/providers/Microsoft.App/jobs/job-worker/executions/{execution_id}",
            properties=SimpleNamespace(
                status=status,
                start_time=start_time,
                template=SimpleNamespace(containers=[container], init_containers=[], volumes=[]),
            ),
        )

    def _client(self, *, job: SimpleNamespace | None = None, execution: SimpleNamespace | None = None, listed: list[Any] | None = None) -> SimpleNamespace:
        client = SimpleNamespace()
        client.jobs = SimpleNamespace(
            get=MagicMock(return_value=job or self._job()),
            begin_start=MagicMock(),
            begin_stop_execution=MagicMock(),
        )
        client.job_execution = MagicMock(return_value=execution or self._execution(
            execution_id="execution-1",
            status="Running",
            start_time=datetime(2026, 9, 2, 17, 0, 0, tzinfo=timezone.utc),
            args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
        ))
        client.jobs_executions = SimpleNamespace(
            list=MagicMock(
                return_value=listed
                if listed is not None
                else [
                    self._execution(
                        execution_id="execution-2",
                        status="Processing",
                        start_time=datetime(2026, 9, 2, 17, 1, 0, tzinfo=timezone.utc),
                        args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                    ),
                    self._execution(
                        execution_id="execution-3",
                        status="Succeeded",
                        start_time=datetime(2026, 9, 2, 17, 2, 0, tzinfo=timezone.utc),
                        args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                    ),
                ]
            )
        )
        return client

    async def test_execution_model_requires_exact_status_and_matches_task_contract(self) -> None:
        allowed_statuses = [
            "Processing",
            "Running",
            "Succeeded",
            "Failed",
            "Stopped",
            "Degraded",
            "Unknown",
        ]
        start_time = datetime(2026, 9, 2, 17, 0, 0, tzinfo=timezone.utc)
        for status in allowed_statuses:
            with self.subTest(status=status):
                execution = self.AcaExecution(
                    execution_id="execution-1",
                    status=status,
                    start_time=start_time,
                    args=["--owner-scope", "owner-hash", "--task-id", "task-id", "--other", "value"],
                )
                self.assertEqual(execution.status, status)
                self.assertTrue(execution.matches_task("task-id", start_time))
                self.assertFalse(execution.matches_task("task-id", start_time + timedelta(seconds=1)))
                self.assertFalse(execution.matches_task("other-task", start_time))

        with self.assertRaises(Exception):
            self.AcaExecution(
                execution_id="execution-1",
                status="Done",
                start_time=start_time,
                args=["--task-id", "task-id"],
            )

        unmatched = self.AcaExecution(
            execution_id="execution-2",
            status="Running",
            start_time=start_time,
            args=["--task-id", "task-id", "--task-id", "different"],
        )
        self.assertFalse(unmatched.matches_task("task-id", start_time))
        self.assertFalse(
            self.AcaExecution(
                execution_id="execution-3",
                status="Running",
                start_time=start_time,
                args=["--task-id", "task-id", "--task-id", "task-id"],
            ).matches_task("task-id", start_time)
        )
        self.assertFalse(
            self.AcaExecution(
                execution_id="execution-4",
                status="Running",
                start_time=start_time,
                args=["--task-id", "wrong-task"],
            ).matches_task("task-id", start_time)
        )
        self.assertFalse(
            self.AcaExecution(
                execution_id="execution-5",
                status="Running",
                start_time=start_time,
                args=["--task-id", "task-id"],
            ).matches_task("task-id", start_time + timedelta(seconds=1))
        )

    async def test_start_builds_trusted_template_and_rejects_contract_mismatch(self) -> None:
        policy = self._policy()
        original_job = self._job()
        original_job.properties.template.containers = [
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "legacy-owner", "--task-id", "legacy-task"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        client = self._client(job=original_job)
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack("execution-123")
        client.jobs.begin_start.return_value = _Poller(begin_result)

        execution = await adapter.start(policy, "owner-hash", "task-id")

        client.jobs.get.assert_called_once_with(policy.resource_group, policy.job_name)
        client.jobs.begin_start.assert_called_once()
        args = client.jobs.begin_start.call_args.args
        self.assertEqual(args[:2], (policy.resource_group, policy.job_name))
        template = args[2]
        container = template.containers[1]
        self.assertEqual(container.image, policy.image_digest)
        self.assertEqual(container.command, policy.command)
        self.assertEqual(container.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])
        self.assertEqual(container.env, original_job.properties.template.containers[1].env)
        self.assertEqual(container.resources, original_job.properties.template.containers[1].resources)
        self.assertEqual(template.containers[0].name, "sidecar")
        self.assertEqual(template.containers[0].image, "example.azurecr.io/sidecar@sha256:" + "b" * 64)
        self.assertEqual(template.containers[0].command, ["sh", "-c", "echo sidecar"])
        self.assertEqual(template.containers[0].args, ["--sidecar", "value"])
        self.assertEqual(template.containers[1].name, policy.container_name)
        self.assertEqual(template.init_containers, original_job.properties.template.init_containers)
        self.assertEqual(template.volumes, original_job.properties.template.volumes)
        self.assertNotIn("inputRef", str(template))
        self.assertNotIn("callback", str(template))
        self.assertEqual(execution.execution_id, "execution-123")
        self.assertEqual(execution.status, "Processing")
        self.assertEqual(execution.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])
        self.assertTrue(execution.matches_task("task-id", execution.start_time))

        zero_match_job = self._job()
        zero_match_job.properties.template.containers = [
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name="assistant",
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "legacy-owner", "--task-id", "legacy-task"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        client_zero_match = self._client(job=zero_match_job)
        adapter_zero_match = self.AcaJobsAdapter(client_zero_match)
        client_zero_match.jobs.begin_start.return_value = _Poller(begin_result)
        with self.assertRaises(self.PublicError) as error:
            await adapter_zero_match.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "DEPLOYMENT_CONTRACT_MISMATCH")

        duplicate_match_job = self._job()
        duplicate_match_job.properties.template.containers = [
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "legacy-owner", "--task-id", "legacy-task"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "legacy-owner", "--task-id", "legacy-task"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        client_duplicate_match = self._client(job=duplicate_match_job)
        adapter_duplicate_match = self.AcaJobsAdapter(client_duplicate_match)
        client_duplicate_match.jobs.begin_start.return_value = _Poller(begin_result)
        with self.assertRaises(self.PublicError) as error:
            await adapter_duplicate_match.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "DEPLOYMENT_CONTRACT_MISMATCH")

        original_job.properties.template.containers[1].image = "example.azurecr.io/worker@sha256:" + "b" * 64
        client_bad_image = self._client(job=original_job)
        adapter_bad_image = self.AcaJobsAdapter(client_bad_image)
        client_bad_image.jobs.begin_start.return_value = _Poller(begin_result)
        with self.assertRaises(self.PublicError) as error:
            await adapter_bad_image.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "DEPLOYMENT_CONTRACT_MISMATCH")

        mismatch_job = self._job()
        mismatch_job.properties.template.containers[0].command = ["python", "-m", "app.other_worker"]
        client_bad_command = self._client(job=mismatch_job)
        adapter_bad_command = self.AcaJobsAdapter(client_bad_command)
        client_bad_command.jobs.begin_start.return_value = _Poller(begin_result)
        with self.assertRaises(self.PublicError) as error:
            await adapter_bad_command.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "DEPLOYMENT_CONTRACT_MISMATCH")

        mismatch_ack = self._start_ack("execution-123", name="execution-123", id_value="/different/id")
        client_bad_ack = self._client(job=self._job())
        adapter_bad_ack = self.AcaJobsAdapter(client_bad_ack)
        client_bad_ack.jobs.begin_start.return_value = _Poller(mismatch_ack)
        with self.assertRaises(self.PublicError) as error:
            await adapter_bad_ack.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "DEPLOYMENT_CONTRACT_MISMATCH")

    async def test_start_ack_with_worker_container_requires_exact_args(self) -> None:
        policy = self._policy()
        client = self._client(job=self._job())
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack_with_template(
            "execution-123",
            containers=[
                SimpleNamespace(
                    name=policy.container_name,
                    image=policy.image_digest,
                    command=policy.command,
                    args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                    env=[SimpleNamespace(name="KEEP", value="1")],
                    resources=SimpleNamespace(cpu=1, memory="2Gi"),
                )
            ],
        )
        client.jobs.begin_start.return_value = _Poller(begin_result)

        execution = await adapter.start(policy, "owner-hash", "task-id")

        self.assertEqual(execution.execution_id, "execution-123")
        self.assertEqual(execution.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])

    async def test_start_ack_without_template_returns_expected_args(self) -> None:
        policy = self._policy()
        client = self._client(job=self._job())
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack("execution-123")
        begin_result.properties = SimpleNamespace(status="Processing", start_time=datetime(2026, 9, 2, 17, 0, 0, tzinfo=timezone.utc))
        client.jobs.begin_start.return_value = _Poller(begin_result)

        execution = await adapter.start(policy, "owner-hash", "task-id")

        self.assertEqual(execution.execution_id, "execution-123")
        self.assertEqual(execution.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])

    async def test_start_ack_with_wrong_worker_container_is_unavailable(self) -> None:
        policy = self._policy()
        client = self._client(job=self._job())
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack_with_template(
            "execution-123",
            containers=[
                SimpleNamespace(
                    name="assistant",
                    image=policy.image_digest,
                    command=policy.command,
                    args=["--owner-scope", "ack-owner", "--task-id", "ack-task"],
                    env=[SimpleNamespace(name="KEEP", value="1")],
                    resources=SimpleNamespace(cpu=1, memory="2Gi"),
                )
            ],
        )
        client.jobs.begin_start.return_value = _Poller(begin_result)

        with self.assertRaises(self.PublicError) as error:
            await adapter.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "ARM_STATUS_UNAVAILABLE")

    async def test_start_ack_with_mismatched_worker_container_args_is_unavailable(self) -> None:
        policy = self._policy()
        client = self._client(job=self._job())
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack_with_template(
            "execution-123",
            containers=[
                SimpleNamespace(
                    name=policy.container_name,
                    image=policy.image_digest,
                    command=policy.command,
                    args=["--owner-scope", "ack-owner", "--task-id", "ack-task", "--extra", "value"],
                    env=[SimpleNamespace(name="KEEP", value="1")],
                    resources=SimpleNamespace(cpu=1, memory="2Gi"),
                )
            ],
        )
        client.jobs.begin_start.return_value = _Poller(begin_result)

        with self.assertRaises(self.PublicError) as error:
            await adapter.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "ARM_STATUS_UNAVAILABLE")

    async def test_start_ack_with_duplicate_worker_container_is_unavailable(self) -> None:
        policy = self._policy()
        client = self._client(job=self._job())
        adapter = self.AcaJobsAdapter(client)
        begin_result = self._start_ack_with_template(
            "execution-123",
            containers=[
                SimpleNamespace(
                    name=policy.container_name,
                    image=policy.image_digest,
                    command=policy.command,
                    args=["--owner-scope", "ack-owner", "--task-id", "ack-task"],
                    env=[SimpleNamespace(name="KEEP", value="1")],
                    resources=SimpleNamespace(cpu=1, memory="2Gi"),
                ),
                SimpleNamespace(
                    name="sidecar",
                    image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                    command=["sh", "-c", "echo sidecar"],
                    args=["--sidecar", "value"],
                    env=[SimpleNamespace(name="SIDE", value="1")],
                    resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
                ),
                SimpleNamespace(
                    name=policy.container_name,
                    image=policy.image_digest,
                    command=policy.command,
                    args=["--owner-scope", "ack-owner", "--task-id", "ack-task"],
                    env=[SimpleNamespace(name="KEEP", value="1")],
                    resources=SimpleNamespace(cpu=1, memory="2Gi"),
                ),
            ],
        )
        client.jobs.begin_start.return_value = _Poller(begin_result)

        with self.assertRaises(self.PublicError) as error:
            await adapter.start(policy, "owner-hash", "task-id")
        self.assertEqual(error.exception.code, "ARM_STATUS_UNAVAILABLE")

    async def test_get_list_stop_and_status_errors_translate_safely(self) -> None:
        policy = self._policy()
        listed = [
            self._execution(
                execution_id="execution-2",
                status="Processing",
                start_time=datetime(2026, 9, 2, 17, 1, 0, tzinfo=timezone.utc),
                args=["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "1"],
            ),
            self._execution(
                execution_id="execution-3",
                status="Succeeded",
                start_time=datetime(2026, 9, 2, 17, 2, 0, tzinfo=timezone.utc),
                args=["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "2"],
            ),
        ]
        listed[0].properties.template.containers = [
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=self._policy().image_digest,
                command=self._policy().command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "1"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        listed[1].properties.template.containers = [
            SimpleNamespace(
                name=policy.container_name,
                image=self._policy().image_digest,
                command=self._policy().command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "2"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
        ]
        client = self._client(
            execution=self._execution(
                execution_id="execution-1",
                status="Running",
                start_time=datetime(2026, 9, 2, 17, 0, 0, tzinfo=timezone.utc),
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
            ),
            listed=listed,
        )
        client.job_execution.return_value.properties.template.containers = [
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=self._policy().image_digest,
                command=self._policy().command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        adapter = self.AcaJobsAdapter(client)

        execution = await adapter.get(policy, "execution-1")
        self.assertEqual(execution.execution_id, "execution-1")
        self.assertEqual(execution.status, "Running")
        self.assertTrue(execution.matches_task("task-id", execution.start_time - timedelta(seconds=1)))
        self.assertEqual(execution.args, ["--owner-scope", "owner-hash", "--task-id", "task-id"])
        client.job_execution.assert_called_once_with(policy.resource_group, policy.job_name, "execution-1")

        listed = await adapter.list(policy)
        self.assertEqual([item.execution_id for item in listed], ["execution-2", "execution-3"])
        self.assertEqual([item.status for item in listed], ["Processing", "Succeeded"])
        self.assertEqual(listed[0].args, ["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "1"])
        self.assertEqual(listed[1].args, ["--owner-scope", "owner-hash", "--task-id", "task-id", "--retry", "2"])
        client.jobs_executions.list.assert_called_once_with(policy.resource_group, policy.job_name)

        stop_poller = _Poller(None)
        client.jobs.begin_stop_execution.return_value = stop_poller
        stopped = await adapter.stop(policy, "execution-1")
        self.assertIsNone(stopped)
        client.jobs.begin_stop_execution.assert_called_once_with(policy.resource_group, policy.job_name, "execution-1")
        self.assertEqual(stop_poller.result.call_count, 1)

        for status_code, expected_code in [
            (403, "TASK_FORBIDDEN"),
            (404, "TASK_NOT_FOUND"),
            (429, "ARM_STATUS_UNAVAILABLE"),
            (500, "ARM_STATUS_UNAVAILABLE"),
        ]:
            with self.subTest(operation="get", status_code=status_code):
                failing = self._client()
                failing.job_execution = MagicMock(side_effect=_http_response_error(status_code))
                adapter_failing = self.AcaJobsAdapter(failing)
                with self.assertRaises(self.PublicError) as error:
                    await adapter_failing.get(policy, "execution-1")
                self.assertEqual(error.exception.code, expected_code)
                self.assertNotIn("boom", str(error.exception))

        ambiguous_get = self._client(
            execution=self._execution(
                execution_id="execution-4",
                status="Running",
                start_time=datetime(2026, 9, 2, 17, 3, 0, tzinfo=timezone.utc),
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
            )
        )
        ambiguous_get.job_execution.return_value.properties.template.containers = [
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        adapter_ambiguous_get = self.AcaJobsAdapter(ambiguous_get)
        with self.assertRaises(self.PublicError) as error:
            await adapter_ambiguous_get.get(policy, "execution-4")
        self.assertEqual(error.exception.code, "ARM_STATUS_UNAVAILABLE")

        ambiguous_list = self._client(
            listed=[
                self._execution(
                    execution_id="execution-5",
                    status="Processing",
                    start_time=datetime(2026, 9, 2, 17, 4, 0, tzinfo=timezone.utc),
                    args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                )
            ]
        )
        ambiguous_list.jobs_executions.list.return_value[0].properties.template.containers = [
            SimpleNamespace(
                name="sidecar",
                image="example.azurecr.io/sidecar@sha256:" + "b" * 64,
                command=["sh", "-c", "echo sidecar"],
                args=["--sidecar", "value"],
                env=[SimpleNamespace(name="SIDE", value="1")],
                resources=SimpleNamespace(cpu=0.25, memory="256Mi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
            SimpleNamespace(
                name=policy.container_name,
                image=policy.image_digest,
                command=policy.command,
                args=["--owner-scope", "owner-hash", "--task-id", "task-id"],
                env=[SimpleNamespace(name="KEEP", value="1")],
                resources=SimpleNamespace(cpu=1, memory="2Gi"),
            ),
        ]
        adapter_ambiguous_list = self.AcaJobsAdapter(ambiguous_list)
        with self.assertRaises(self.PublicError) as error:
            await adapter_ambiguous_list.list(policy)
        self.assertEqual(error.exception.code, "ARM_STATUS_UNAVAILABLE")

        for status_code, expected_code in [
            (400, "ARM_START_REJECTED"),
            (401, "ARM_START_REJECTED"),
            (403, "TASK_FORBIDDEN"),
            (404, "TASK_NOT_FOUND"),
            (429, "ARM_STATUS_UNAVAILABLE"),
        ]:
            with self.subTest(operation="start", status_code=status_code):
                failing = self._client()
                failing.jobs.begin_start.side_effect = _http_response_error(status_code)
                adapter_failing = self.AcaJobsAdapter(failing)
                with self.assertRaises(self.PublicError) as error:
                    await adapter_failing.start(policy, "owner-hash", "task-id")
                self.assertEqual(error.exception.code, expected_code)
                self.assertNotIn("boom", str(error.exception))

        for status_code, expected_code in [
            (400, "ARM_STOP_REJECTED"),
            (403, "TASK_FORBIDDEN"),
            (404, "TASK_NOT_FOUND"),
            (409, "ARM_STATUS_UNAVAILABLE"),
            (429, "ARM_STATUS_UNAVAILABLE"),
        ]:
            with self.subTest(operation="stop", status_code=status_code):
                failing = self._client()
                failing.jobs.begin_stop_execution.side_effect = _http_response_error(status_code)
                adapter_failing = self.AcaJobsAdapter(failing)
                with self.assertRaises(self.PublicError) as error:
                    await adapter_failing.stop(policy, "execution-1")
                self.assertEqual(error.exception.code, expected_code)
                self.assertNotIn("boom", str(error.exception))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for the foundry-mcp-aca-jobs callback policies and sender."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-mcp-aca-jobs" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

FASTMCP_TASKS_STUBBED = False
try:  # pragma: no cover - exercised only when the real dependency exists locally.
    from fastmcp_tasks.models import GetTaskResult  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local test shim only.
    FASTMCP_TASKS_STUBBED = True

    class _StubGetTaskResult(BaseModel):
        model_config = ConfigDict(populate_by_name=True, extra="forbid", strict=True)

        task_id: str = Field(serialization_alias="taskId", min_length=1)
        status: str
        created_at: str = Field(serialization_alias="createdAt", min_length=1)
        last_updated_at: str = Field(serialization_alias="lastUpdatedAt", min_length=1)
        ttl_ms: int | None = Field(default=None, serialization_alias="ttlMs")
        poll_interval_ms: int | None = Field(default=None, serialization_alias="pollIntervalMs")
        result: dict[str, Any] | None = None
        error: dict[str, Any] | None = None
        status_message: str | None = Field(default=None, serialization_alias="statusMessage")
        result_type: str = Field(default="complete", serialization_alias="resultType")

    fastmcp_tasks = types.ModuleType("fastmcp_tasks")
    fastmcp_tasks.__path__ = []  # type: ignore[attr-defined]
    fastmcp_tasks_models = types.ModuleType("fastmcp_tasks.models")
    fastmcp_tasks_models.GetTaskResult = _StubGetTaskResult
    fastmcp_tasks.models = fastmcp_tasks_models
    sys.modules["fastmcp_tasks"] = fastmcp_tasks
    sys.modules["fastmcp_tasks.models"] = fastmcp_tasks_models
    from fastmcp_tasks.models import GetTaskResult  # type: ignore  # noqa: E402

from app.models import PublicError  # noqa: E402


class _Token:
    def __init__(self, token: str) -> None:
        self.token = token
        self.expires_on = int(datetime.now(tz=timezone.utc).timestamp()) + 3600


class _TokenCredential:
    def __init__(self, token: str) -> None:
        self.token = token
        self.scopes: list[str] = []

    async def get_token(self, *scopes: str, **_: Any) -> _Token:
        self.scopes.extend(scopes)
        return _Token(self.token)


class _Secret:
    def __init__(self, value: str) -> None:
        self.value = value


class _SecretClient:
    def __init__(self, secret_value: str) -> None:
        self.secret_value = secret_value
        self.calls: list[str] = []

    async def get_secret(self, name: str) -> _Secret:
        self.calls.append(name)
        return _Secret(self.secret_value)


class _FailingTokenCredential:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.scopes: list[str] = []

    async def get_token(self, *scopes: str, **_: Any) -> _Token:
        self.scopes.extend(scopes)
        raise self.exc


class _FailingSecretClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[str] = []

    async def get_secret(self, name: str) -> _Secret:
        self.calls.append(name)
        raise self.exc


class _LogCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(self.format(record))


class FoundryMcpAcaJobsCallbackTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.models = importlib.import_module("app.models")

    def setUp(self) -> None:
        self.JobPolicy = getattr(self.models, "JobPolicy", None)
        self.CallbackPolicy = getattr(self.models, "CallbackPolicy", None)
        self.Policy = getattr(self.models, "Policy", None)
        self.callback_payload = None
        self.CallbackSender = None

    def _callbacks_module(self):
        try:
            return importlib.import_module("app.callbacks")
        except ModuleNotFoundError as exc:  # pragma: no cover - red phase failure path
            self.fail(f"app.callbacks is missing: {exc}")

    def _make_policy(self, *, auth_mode: str = "managed_identity"):
        self.assertIsNotNone(self.JobPolicy, "JobPolicy missing from app.models")
        self.assertIsNotNone(self.CallbackPolicy, "CallbackPolicy missing from app.models")
        self.assertIsNotNone(self.Policy, "Policy missing from app.models")
        job_policy = self.JobPolicy(
            resource_group="rg",
            job_name="batch-job",
            container_name="worker",
            image_digest="registry.azurecr.io/work@sha256:" + "a" * 64,
            command=["python", "-m", "app.job_worker"],
            allowed_owner_scopes={"scope-a", "scope-b"},
        )
        callback_kwargs: dict[str, Any] = {
            "url": "https://hooks.example.com/jobs",
            "auth_mode": auth_mode,
        }
        if auth_mode == "managed_identity":
            callback_kwargs["audience"] = "api://mcp-callback"
        else:
            callback_kwargs["secret_name"] = "callback-secret"
        callback_policy = self.CallbackPolicy(**callback_kwargs)
        return self.Policy(
            jobs={"batch": job_policy},
            callbacks={"ops": callback_policy},
            input_hosts={"storage.example.com"},
            result_hosts={"results.example.com"},
        )

    def test_policy_lookup_rejects_unknown_job_and_callback_alias(self) -> None:
        policy = self._make_policy()
        with self.assertRaises(PublicError) as job_error:
            policy.job("missing")
        self.assertEqual(job_error.exception.code, "INVALID_JOB_TYPE")

        with self.assertRaises(PublicError) as alias_error:
            policy.callback("missing")
        self.assertEqual(alias_error.exception.code, "INVALID_CALLBACK_ALIAS")

    def test_job_policy_rejects_bad_digest_and_non_list_command(self) -> None:
        with self.assertRaises(ValidationError):
            self.JobPolicy(
                resource_group="rg",
                job_name="batch-job",
                container_name="worker",
                image_digest="registry.azurecr.io/work:latest",
                command=["python", "-m", "app.job_worker"],
            )

        with self.assertRaises(ValidationError):
            self.JobPolicy(
                resource_group="rg",
                job_name="batch-job",
                container_name="worker",
                image_digest="registry.azurecr.io/work@sha256:" + "b" * 64,
                command=("python", "-m", "app.job_worker"),  # type: ignore[arg-type]
            )

    def test_callback_policy_requires_https_and_auth_fields(self) -> None:
        with self.assertRaises(ValidationError):
            self.CallbackPolicy(url="http://hooks.example.com/jobs", auth_mode="managed_identity", audience="api://mcp-callback")

        with self.assertRaises(ValidationError):
            self.CallbackPolicy(
                url="https://user:pass@hooks.example.com/jobs",
                auth_mode="managed_identity",
                audience="api://mcp-callback",
            )

        with self.assertRaises(ValidationError):
            self.CallbackPolicy(
                url="https://hooks.example.com/jobs?next=https://example.invalid",
                auth_mode="managed_identity",
                audience="api://mcp-callback",
            )

        with self.assertRaises(ValidationError):
            self.CallbackPolicy(url="https://hooks.example.com/jobs", auth_mode="managed_identity")

        with self.assertRaises(ValidationError):
            self.CallbackPolicy(url="https://hooks.example.com/jobs", auth_mode="key_vault")

    def test_validate_input_and_result_rejects_bad_url_forms(self) -> None:
        policy = self._make_policy()
        invalid_urls = [
            ("validate_input", "http://storage.example.com/in/1", "INVALID_INPUT_REFERENCE"),
            ("validate_input", "https://user:pass@storage.example.com/in/1", "INVALID_INPUT_REFERENCE"),
            ("validate_input", "https://evil.example.com/in/1", "INVALID_INPUT_REFERENCE"),
            ("validate_input", "https://storage.example.com/in/1?token=secret", "INVALID_INPUT_REFERENCE"),
            ("validate_result", "http://results.example.com/out/1", "INVALID_RESULT_REFERENCE"),
            ("validate_result", "https://user:pass@results.example.com/out/1", "INVALID_RESULT_REFERENCE"),
            ("validate_result", "https://evil.example.com/out/1", "INVALID_RESULT_REFERENCE"),
            ("validate_result", "https://results.example.com/out/1?access_token=secret", "INVALID_RESULT_REFERENCE"),
        ]
        for method_name, value, code in invalid_urls:
            with self.subTest(method=method_name, value=value):
                with self.assertRaises(PublicError) as error:
                    getattr(policy, method_name)(value)
                self.assertEqual(error.exception.code, code)

    def test_validate_input_and_result_return_the_original_https_reference(self) -> None:
        policy = self._make_policy()
        input_ref = policy.validate_input("https://storage.example.com/in/1?version=1")
        result_ref = policy.validate_result("https://results.example.com/out/1?page=2")
        self.assertEqual(str(input_ref), "https://storage.example.com/in/1?version=1")
        self.assertEqual(str(result_ref), "https://results.example.com/out/1?page=2")

    def test_callback_payload_is_exactly_minimal(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        self.assertEqual(
            payload,
            {
                "taskId": "task-1",
                "acaExecutionId": "execution-1",
                "status": "Succeeded",
                "resultUrl": "https://results.example.com/out/1",
            },
        )

    async def test_managed_identity_sender_uses_bearer_header_and_redacts_token(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, request=request)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        logger = logging.getLogger("app.callbacks")
        logger.setLevel(logging.DEBUG)
        try:
            with self.assertLogs("app.callbacks", level="DEBUG") as logs:
                sender = callbacks.CallbackSender(client, credential)
                await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(credential.scopes, ["api://mcp-callback/.default"])
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.headers["Authorization"], "Bearer " + "test-token")
        self.assertEqual(json.loads(request.content), payload)
        self.assertIn("callback attempt 1 to https://hooks.example.com/jobs", "\n".join(logs.output))
        self.assertNotIn("test-token", "\n".join(logs.output))

    async def test_sender_logs_only_safe_host_and_path(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        policy = self.CallbackPolicy.model_construct(
            url=HttpUrl("https://user:pass@hooks.example.com/jobs?next=https://example.invalid"),
            auth_mode="managed_identity",
            audience="api://mcp-callback",
        )
        credential = _TokenCredential("test-token")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, request=request)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        collector = _LogCollector()
        logger = logging.getLogger("app.callbacks")
        logger.addHandler(collector)
        logger.setLevel(logging.DEBUG)
        try:
            sender = callbacks.CallbackSender(client, credential)
            await sender.send(policy, payload)
        finally:
            logger.removeHandler(collector)
            await client.aclose()

        joined = "\n".join(collector.messages)
        self.assertIn("callback attempt 1 to https://hooks.example.com/jobs", joined)
        self.assertNotIn("user:pass@", joined)
        self.assertNotIn("?next=", joined)

    async def test_timeout_exception_retries_then_succeeds(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        attempts = 0
        delays: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.TimeoutException("timeout", request=request)
            return httpx.Response(200, request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.0)
        try:
            await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(attempts, 2)
        self.assertEqual(delays, [1.0])

    async def test_request_error_retries_until_exhausted(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        attempts = 0
        delays: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.RequestError("network down", request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.0)
        try:
            with self.assertRaises(PublicError) as error:
                await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(error.exception.code, "CALLBACK_DELIVERY_EXHAUSTED")
        self.assertEqual(attempts, 5)
        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0])
        self.assertNotIn("test-token", str(error.exception))

    async def test_http_408_retries_then_succeeds(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        attempts: list[httpx.Request] = []
        delays: list[float] = []
        responses = [408, 200]

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request)
            return httpx.Response(responses[len(attempts) - 1], request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.0)
        try:
            await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(len(attempts), 2)
        self.assertEqual(delays, [1.0])

    async def test_key_vault_sender_awaits_async_secret_and_secret_header(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        secret_client = _SecretClient("kv-secret-456")
        requests: list[httpx.Request] = []

        async def unexpected_to_thread(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("asyncio.to_thread should not be used")

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(200, request=request)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        collector = _LogCollector()
        logger = logging.getLogger("app.callbacks")
        logger.addHandler(collector)
        logger.setLevel(logging.DEBUG)
        try:
            with mock.patch("app.callbacks.asyncio.to_thread", new=unexpected_to_thread):
                sender = callbacks.CallbackSender(client, _TokenCredential("unused"), secret_client=secret_client)
                await sender.send(self._make_policy(auth_mode="key_vault").callback("ops"), payload)
        finally:
            logger.removeHandler(collector)
            await client.aclose()

        self.assertEqual(secret_client.calls, ["callback-secret"])
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.headers["X-Callback-Key"], "kv-secret-456")
        self.assertEqual(json.loads(request.content), payload)
        self.assertNotIn("kv-secret-456", "\n".join(collector.messages))

    async def test_managed_identity_auth_acquisition_retries_then_exhausts_without_secret_leak(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _FailingTokenCredential(RuntimeError("bearer token for test-token unavailable"))
        attempts = 0
        delays: list[float] = []
        collector = _LogCollector()
        logger = logging.getLogger("app.callbacks")
        logger.addHandler(collector)
        logger.setLevel(logging.DEBUG)

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(200, request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.0)
        try:
            with self.assertRaises(PublicError) as error:
                await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            logger.removeHandler(collector)
            await client.aclose()

        self.assertEqual(error.exception.code, "CALLBACK_DELIVERY_EXHAUSTED")
        self.assertEqual(attempts, 0)
        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0])
        self.assertNotIn("test-token", str(error.exception))
        self.assertNotIn("bearer token for test-token unavailable", str(error.exception))
        self.assertNotIn("test-token", "\n".join(collector.messages))
        self.assertNotIn("bearer token for test-token unavailable", "\n".join(collector.messages))

    async def test_key_vault_auth_acquisition_retries_then_exhausts_without_secret_leak(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        secret_client = _FailingSecretClient(RuntimeError("kv-secret-456 unavailable"))
        delays: list[float] = []
        collector = _LogCollector()
        logger = logging.getLogger("app.callbacks")
        logger.addHandler(collector)
        logger.setLevel(logging.DEBUG)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, _TokenCredential("unused"), secret_client=secret_client, sleep=fake_sleep, random=lambda: 0.0)
        try:
            with self.assertRaises(PublicError) as error:
                await sender.send(self._make_policy(auth_mode="key_vault").callback("ops"), payload)
        finally:
            logger.removeHandler(collector)
            await client.aclose()

        self.assertEqual(error.exception.code, "CALLBACK_DELIVERY_EXHAUSTED")
        self.assertEqual(secret_client.calls, ["callback-secret"] * 5)
        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0])
        self.assertNotIn("kv-secret-456", str(error.exception))
        self.assertNotIn("kv-secret-456 unavailable", str(error.exception))
        self.assertNotIn("kv-secret-456", "\n".join(collector.messages))
        self.assertNotIn("kv-secret-456 unavailable", "\n".join(collector.messages))

    async def test_sender_retries_transient_failures_then_succeeds(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        attempts: list[httpx.Request] = []
        delays: list[float] = []
        responses = [429, 200]

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request)
            return httpx.Response(responses[len(attempts) - 1], request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.25)
        try:
            await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(len(attempts), 2)
        self.assertEqual(delays, [1.25])

    async def test_sender_exhausts_transient_failures(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        credential = _TokenCredential("test-token")
        attempts: list[httpx.Request] = []
        delays: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request)
            return httpx.Response(503, request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, credential, sleep=fake_sleep, random=lambda: 0.5)
        try:
            with self.assertRaises(PublicError) as error:
                await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(error.exception.code, "CALLBACK_DELIVERY_EXHAUSTED")
        self.assertEqual(len(attempts), 5)
        self.assertEqual(delays, [1.5, 2.5, 4.5, 8.5])

    async def test_sender_rejects_permanent_4xx_immediately(self) -> None:
        callbacks = self._callbacks_module()
        payload = callbacks.callback_payload(
            "task-1",
            "execution-1",
            "Succeeded",
            "https://results.example.com/out/1",
        )
        attempts: list[httpx.Request] = []
        delays: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(request)
            return httpx.Response(403, request=request)

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        sender = callbacks.CallbackSender(client, _TokenCredential("test-token"), sleep=fake_sleep)
        try:
            with self.assertRaises(PublicError) as error:
                await sender.send(self._make_policy().callback("ops"), payload)
        finally:
            await client.aclose()

        self.assertEqual(error.exception.code, "CALLBACK_DELIVERY_REJECTED")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(delays, [])


if __name__ == "__main__":
    unittest.main()

"""Canonical callback transport for foundry-mcp-aca-jobs.

The section references for this file are not yet published in SKILL.md, so this
module intentionally avoids unresolved section anchors in its docstring.
"""

from __future__ import annotations

import asyncio
import logging
import random as _random
from typing import Any, Callable, Protocol, runtime_checkable

import httpx

from .models import CallbackPolicy, PublicError

__all__ = ["AsyncTokenCredential", "CallbackSender", "callback_payload"]

logger = logging.getLogger(__name__)


@runtime_checkable
class AsyncTokenCredential(Protocol):
    async def get_token(self, *scopes: str, **kwargs: Any) -> Any: ...


@runtime_checkable
class _SecretClient(Protocol):
    def get_secret(self, name: str) -> Any: ...


def callback_payload(task_id: str, execution_id: str, status: str, result_url: str) -> dict[str, str]:
    return {
        "taskId": task_id,
        "acaExecutionId": execution_id,
        "status": status,
        "resultUrl": result_url,
    }


class CallbackSender:
    def __init__(
        self,
        client: httpx.AsyncClient,
        credential: AsyncTokenCredential,
        secret_client: _SecretClient | None = None,
        *,
        sleep: Callable[[float], Any] = asyncio.sleep,
        random: Callable[[], float] | None = None,
        timeout: float = 10.0,
        max_delay: float = 8.0,
    ) -> None:
        self._client = client
        self._credential = credential
        self._secret_client = secret_client
        self._sleep = sleep
        self._random = random or _random.random
        self._timeout = timeout
        self._max_delay = max_delay

    async def send(self, policy: CallbackPolicy, payload: dict[str, str]) -> None:
        headers = await self._headers_for(policy)
        for attempt in range(5):
            logger.debug("callback attempt %s to %s", attempt + 1, policy.url)
            try:
                response = await self._client.post(
                    str(policy.url),
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                logger.debug("callback transport transient on attempt %s: %s", attempt + 1, exc.__class__.__name__)
                if attempt == 4:
                    raise PublicError("CALLBACK_DELIVERY_EXHAUSTED", "callback delivery exhausted") from exc
                await self._sleep(self._delay_for_attempt(attempt))
                continue

            status = response.status_code
            if 200 <= status < 300:
                return
            if status in {408, 429} or status >= 500:
                logger.debug("callback HTTP transient status %s on attempt %s", status, attempt + 1)
                if attempt == 4:
                    raise PublicError("CALLBACK_DELIVERY_EXHAUSTED", "callback delivery exhausted")
                await self._sleep(self._delay_for_attempt(attempt))
                continue

            raise PublicError("CALLBACK_DELIVERY_REJECTED", "callback delivery rejected")

        raise PublicError("CALLBACK_DELIVERY_EXHAUSTED", "callback delivery exhausted")

    async def _headers_for(self, policy: CallbackPolicy) -> dict[str, str]:
        if policy.auth_mode == "managed_identity":
            token = await self._credential.get_token(f"{policy.audience}/.default")
            return {"Authorization": "Bearer " + token.token}

        if self._secret_client is None:
            raise PublicError("CALLBACK_DELIVERY_REJECTED", "callback secret client unavailable")

        secret = await asyncio.to_thread(self._secret_client.get_secret, policy.secret_name)
        return {"X-Callback-Key": secret.value}

    def _delay_for_attempt(self, attempt: int) -> float:
        return min(2**attempt, self._max_delay) + self._random()

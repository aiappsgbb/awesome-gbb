"""Canonical safe telemetry support for foundry-mcp-aca-jobs."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from contextlib import contextmanager
from time import monotonic
from typing import Any

try:  # pragma: no cover - optional dependency fallback.
    from opentelemetry import metrics as _metrics
    from opentelemetry import trace as _trace
except Exception:  # pragma: no cover - local fallback only.
    _metrics = None
    _trace = None

try:  # pragma: no cover - optional dependency fallback.
    from azure.monitor.opentelemetry import configure_azure_monitor as _configure_azure_monitor
except Exception:  # pragma: no cover - local fallback only.
    _configure_azure_monitor = None

configure_azure_monitor = _configure_azure_monitor

__all__ = ["SAFE_KEYS", "Telemetry", "configure", "telemetry"]

logger = logging.getLogger(__name__)

SAFE_KEYS = {
    "task.id",
    "job.type",
    "task.state",
    "aca.execution.id",
    "operation",
    "outcome",
    "error.code",
    "azure.request.id",
}


class _NoOpSpan:
    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _NoOpTracer:
    def start_as_current_span(self, name: str, attributes: Mapping[str, str]) -> _NoOpSpan:
        return _NoOpSpan()


class _NoOpCounter:
    def add(self, value: float, attributes: Mapping[str, str] | None = None) -> None:
        return None


class _NoOpHistogram:
    def record(self, value: float, attributes: Mapping[str, str] | None = None) -> None:
        return None


class _NoOpMeter:
    def create_counter(self, name: str) -> _NoOpCounter:
        return _NoOpCounter()

    def create_histogram(self, name: str, unit: str | None = None) -> _NoOpHistogram:
        return _NoOpHistogram()


def _default_tracer() -> Any:
    if _trace is None:
        return _NoOpTracer()
    return _trace.get_tracer("foundry-mcp-aca-jobs")


def _default_meter() -> Any:
    if _metrics is None:
        return _NoOpMeter()
    return _metrics.get_meter("foundry-mcp-aca-jobs")


class Telemetry:
    def __init__(self, tracer: Any | None = None, meter: Any | None = None) -> None:
        self.tracer = tracer or _default_tracer()
        self.meter = meter or _default_meter()
        self.operations = self.meter.create_counter("mcp_aca_jobs.operations")
        self.latency = self.meter.create_histogram("mcp_aca_jobs.operation.duration", unit="s")

    def attributes(self, values: Mapping[str, Any] | None = None) -> dict[str, str]:
        values = values or {}
        safe: dict[str, str] = {}
        for key, value in values.items():
            if key in SAFE_KEYS and value is not None:
                safe[key] = str(value)
        return safe

    def record(
        self,
        operation: str,
        attributes: Mapping[str, Any] | None = None,
        *,
        outcome: str | None = None,
        error_code: str | None = None,
    ) -> dict[str, str]:
        safe = self.attributes(attributes)
        safe["operation"] = operation
        if outcome is not None:
            safe["outcome"] = outcome
        if error_code is not None:
            safe["error.code"] = error_code
        self.operations.add(1, safe)
        return safe

    @contextmanager
    def operation(self, name: str, attributes: Mapping[str, Any] | None = None):
        started = monotonic()
        safe = self.attributes(attributes)
        safe["operation"] = name
        with self.tracer.start_as_current_span(name, attributes=safe):
            try:
                yield
            except Exception:
                self.record(name, safe, outcome="failure", error_code=safe.get("error.code"))
                raise
            else:
                self.record(name, safe, outcome="success", error_code=safe.get("error.code"))
            finally:
                self.latency.record(monotonic() - started, safe)


def configure() -> None:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not connection_string.strip():
        logger.info("application insights disabled; no connection string configured")
        return
    if not connection_string.startswith("InstrumentationKey="):
        logger.warning("application insights disabled; unsupported connection string (redacted)")
        return
    if configure_azure_monitor is None:
        logger.warning("application insights configuration failed: %s", "ModuleNotFoundError")
        return
    try:
        configure_azure_monitor()
    except Exception as exc:  # pragma: no cover - configuration path is guarded in tests.
        logger.warning("application insights configuration failed: %s", exc.__class__.__name__)


telemetry = Telemetry()

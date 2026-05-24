"""otel_init.py — drop-in OpenTelemetry initializer for ACA workloads.

Use in:
    - src/mcp/server.py        (FastMCP server)
    - src/bot/app.py            (microsoft-agents-* SDK bot)
    - src/workspace/app.py      (FastAPI gateway, if any)
    - src/jobs/*/main.py         (ACA Job cron entry-points)

Pattern:
    from otel_init import init_telemetry
    init_telemetry(role="<process>-mcp")  # call BEFORE any other init

Why call it first
-----------------
ACA's default LAW binding routes stdout/stderr to ContainerAppConsoleLogs_CL
ONLY when the container survives long enough to flush. Cron jobs that
crash early (Cosmos SDK import-time exceptions, identity acquisition
timeouts, etc.) leave NO console logs but DO leave OTel exception
spans IF init_telemetry() ran before the crash. Always init first.

Local-dev safety
----------------
If APPLICATIONINSIGHTS_CONNECTION_STRING is unset (the local-test pattern),
this function is a no-op — it logs a single info message and returns.
No exception. No noise. Lets the same code run in cloud and locally
without conditional imports.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)
_initialized = False


def init_telemetry(
    role: str,
    *,
    enable_azure_sdk: bool = True,
    enable_fastapi: bool = True,
    enable_requests: bool = True,
    extra_options: dict[str, Any] | None = None,
) -> bool:
    """Initialize Azure Monitor OpenTelemetry. Idempotent.

    Args:
        role: cloud_RoleName as it appears in App Insights queries.
              Convention: <process-slug>-<service> (e.g., 'your-process-mcp').
        enable_azure_sdk: capture Cosmos / AOAI / Search / Storage SDK calls.
        enable_fastapi: capture FastAPI request/response spans (MCP servers + bots).
        enable_requests: capture outbound HTTP via requests + urllib3.
        extra_options: additional instrumentation_options passed through.

    Returns:
        True if telemetry was initialized; False if no connection string.
    """
    global _initialized
    if _initialized:
        return True

    # O-012 workaround: check the underscore variant first (deploy.py passthrough),
    # then the standard name (platform auto-injection or explicit Bicep wiring).
    conn = os.environ.get("APPLICATION_INSIGHTS_CONNECTION_STRING") \
        or os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn or not conn.strip().startswith("InstrumentationKey="):
        _log.info(
            "No valid App Insights connection string — telemetry disabled "
            "(this is expected in local-test; see threadlight-local-test skill)"
        )
        return False

    # Normalize to the standard name so configure_azure_monitor picks it up
    conn = conn.strip()
    os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = conn

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        _log.warning(
            "azure-monitor-opentelemetry not installed; telemetry disabled. "
            "Add `azure-monitor-opentelemetry>=1.6.0` to requirements.txt."
        )
        return False

    options: dict[str, Any] = {
        "azure_sdk": {"enabled": enable_azure_sdk},
        "fastapi": {"enabled": enable_fastapi},
        "django": {"enabled": False},
        "flask": {"enabled": False},
        "psycopg2": {"enabled": False},
        "requests": {"enabled": enable_requests},
        "urllib3": {"enabled": enable_requests},
        "urllib": {"enabled": enable_requests},
    }
    if extra_options:
        options.update(extra_options)

    configure_azure_monitor(
        connection_string=conn,
        logger_name=role,
        instrumentation_options=options,
    )

    # Tag the role so AppIn cloud_RoleName is set explicitly. Without this,
    # the AzureMonitor exporter falls back to the OTLP service.name which
    # may default to "unknown_service:python" in container envs.
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource

        # Best-effort — newer SDK versions set this from the logger_name above
        # but older ones don't. Belt + braces.
        resource = Resource.create({"service.name": role})
        provider = trace.get_tracer_provider()
        if hasattr(provider, "_resource"):
            provider._resource = resource  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001
        _log.debug("could not pin service.name resource attribute: %s", e)

    _initialized = True
    _log.info("telemetry initialized — role=%s", role)
    return True

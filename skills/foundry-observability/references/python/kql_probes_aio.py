"""Canonical foundry-observability KQL probe helpers (async variants).

Source of truth for the prose example in `../../SKILL.md § Reusable KQL probe helpers`.

Mirror of kql_probes.py with `async def` signatures and aio clients.
Same return shape; same never-raises contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient
from azure.monitor.query import LogsQueryStatus  # enum is shared; no aio import needed

try:
    from .kql_probes import (  # reuse query strings — single source of truth
        _QUERY_TRACE_FRESHNESS,
        _QUERY_EXCEPTION_RATE,
        _QUERY_RAI_DENIALS,
        _QUERY_AGT_DENIALS,
        _QUERY_RATE_LIMIT_EVENTS,
        _parse_since,
        _now_iso,
    )
except ImportError:  # bare sys.path-on-directory consumption (e.g. test harness)
    from kql_probes import (  # type: ignore[no-redef]
        _QUERY_TRACE_FRESHNESS,
        _QUERY_EXCEPTION_RATE,
        _QUERY_RAI_DENIALS,
        _QUERY_AGT_DENIALS,
        _QUERY_RATE_LIMIT_EVENTS,
        _parse_since,
        _now_iso,
    )


async def trace_freshness(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Minutes since the most recent OTel trace for app_name."""
    client = None
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_TRACE_FRESHNESS.format(app_name=app_name, since=since)
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=_parse_since(since),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises — contract per awesome-gbb#245
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def exception_rate(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Exceptions per minute over the requested window (float)."""
    client = None
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_EXCEPTION_RATE.format(app_name=app_name, since=since)
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=_parse_since(since),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        if rows and rows[0][0] is not None:
            cnt = int(rows[0][0])
            window_minutes = _parse_since(since).total_seconds() / 60
            if window_minutes <= 0:
                window_minutes = 60.0
            result = float(cnt) / window_minutes
        else:
            result = None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises — contract per awesome-gbb#245
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def rai_denials(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of RAI-denial events emitted by app_name in the window."""
    client = None
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_RAI_DENIALS.format(app_name=app_name, since=since)
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=_parse_since(since),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises — contract per awesome-gbb#245
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def agt_denials(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of AGT deny-list trips emitted by app_name in the window."""
    client = None
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_AGT_DENIALS.format(app_name=app_name, since=since)
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=_parse_since(since),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises — contract per awesome-gbb#245
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass


async def rate_limit_events(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of 429 / rate-limit events emitted by app_name in the window."""
    client = None
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_RATE_LIMIT_EVENTS.format(app_name=app_name, since=since)
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=_parse_since(since),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises — contract per awesome-gbb#245
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass

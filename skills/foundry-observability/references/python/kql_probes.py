"""Canonical foundry-observability KQL probe helpers (sync variants).

Source of truth for the prose example in `../../SKILL.md § Reusable KQL probe helpers`.

Built to the contract in awesome-gbb#245 (threadlight v0.5.1 cross-cutting
telemetry self-verify when `kind: sibling-skill`). The five probes return a
stable dict shape so the consumer's evidence_globs can index them uniformly.

NOTE: This is build-to-contract, not lift-from-upstream. The threadlight
`production_ready.py` reference has only a trace-freshness-shaped query
inside `_check_obs_live`; the remaining four KQL queries are written here
to documented Application Insights table schemas (AppTraces, AppExceptions).

Public API (5 sync helpers, all same signature):
    from foundry_observability.kql_probes import trace_freshness
    result = trace_freshness(workspace_id="...", app_name="...",
                              since="1h", credential=None)

Returns:
    {"result": <typed primitive | None>, "confidence": 0.0..1.0,
     "last_probe_at": "ISO8601 UTC", "error": str | None}

Never raises. Catches every exception, returns error key with reason.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_since(since: str) -> timedelta:
    """Parse a duration string like '1h', '24h', '7d' into a timedelta.

    Falls back to 24 hours on unrecognised or non-positive input.
    """
    since = since.strip().lower()
    if since.endswith("d"):
        try:
            n = int(since[:-1])
            return timedelta(days=n) if n > 0 else timedelta(hours=24)
        except ValueError:
            pass
    elif since.endswith("h"):
        try:
            n = int(since[:-1])
            return timedelta(hours=n) if n > 0 else timedelta(hours=24)
        except ValueError:
            pass
    return timedelta(hours=24)


# KQL queries as module-level constants so kql_probes_aio.py can import them
# without duplicating the strings. app_name and since are interpolated into
# KQL at call time. Both are expected to come from trusted configuration
# (CI env vars, callers within the same process) — no sanitisation is performed.

_QUERY_TRACE_FRESHNESS = """AppTraces
| where AppRoleName == '{app_name}'
| summarize last_seen = max(TimeGenerated)
| extend minutes_since = datetime_diff('minute', now(), last_seen)
| project minutes_since"""

_QUERY_EXCEPTION_RATE = """AppExceptions
| where AppRoleName == '{app_name}'
| where TimeGenerated > ago({since})
| summarize cnt = count()
| project cnt"""

_QUERY_RAI_DENIALS = """AppTraces
| where AppRoleName == '{app_name}'
| where TimeGenerated > ago({since})
| where tostring(Properties['event_type']) == 'rai_denial' or Message has 'rai_denial'
| count"""

_QUERY_AGT_DENIALS = """AppTraces
| where AppRoleName == '{app_name}'
| where TimeGenerated > ago({since})
| where tostring(Properties['event_type']) == 'agt_deny' or Message has 'agt_deny'
| count"""

_QUERY_RATE_LIMIT_EVENTS = """AppTraces
| where AppRoleName == '{app_name}'
| where TimeGenerated > ago({since})
| where tostring(Properties['http_status']) == '429' or Message has '429' or Message has 'rate limit'
| count"""


def trace_freshness(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Minutes since the most recent OTel trace for app_name."""
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_TRACE_FRESHNESS.format(app_name=app_name, since=since)
        response = client.query_workspace(
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


def exception_rate(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Exceptions per minute over the requested window (float)."""
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_EXCEPTION_RATE.format(app_name=app_name, since=since)
        response = client.query_workspace(
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


def rai_denials(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of RAI-denial events emitted by app_name in the window."""
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_RAI_DENIALS.format(app_name=app_name, since=since)
        response = client.query_workspace(
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


def agt_denials(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of AGT deny-list trips emitted by app_name in the window."""
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_AGT_DENIALS.format(app_name=app_name, since=since)
        response = client.query_workspace(
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


def rate_limit_events(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Count of 429 / rate-limit events emitted by app_name in the window."""
    try:
        if credential is None:
            credential = DefaultAzureCredential()
        client = LogsQueryClient(credential)
        query = _QUERY_RATE_LIMIT_EVENTS.format(app_name=app_name, since=since)
        response = client.query_workspace(
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

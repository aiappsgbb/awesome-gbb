"""Reusable KQL probe helpers for Log Analytics / App Insights.

Lifted from threadlight's production_ready.py for shared reuse.
Threadlight's _kql_* helpers are the source of truth for query bodies;
this module wraps them in a stable per-helper return shape so consumers
can compose them without re-deriving the query strings.

Public API:
    trace_freshness(app_insights_id, hours=24) -> dict
    exception_rate(app_insights_id, hours=24) -> dict
    rai_denials(workspace_id, hours=24) -> dict
    agt_denials(workspace_id, hours=24) -> dict
    rate_limit_events(workspace_id, hours=24) -> dict

All helpers return:
    {
        "metric": "<helper_name>",
        "result": {...} | None,
        "confidence": "high" | "medium" | "low",
        "last_probe_at": "<ISO 8601 UTC>",
        "stale": bool,           # only meaningful for freshness helpers
        "error": str | None,     # never raises
    }

Source of truth for the prose example in `../../SKILL.md § Reusable KQL probe helpers (v1.1.6+)`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient


_QUERY_DIR = Path(__file__).parent.parent / "references" / "queries"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client() -> LogsQueryClient:
    return LogsQueryClient(DefaultAzureCredential())


def _read_query(name: str) -> str:
    """Read a raw KQL file from references/queries/<name>.kql."""
    return (_QUERY_DIR / f"{name}.kql").read_text()


def _wrap(metric: str, result: dict | None, *, error: str | None = None,
          stale: bool = False, confidence: str = "high") -> dict:
    return {
        "metric": metric,
        "result": result,
        "confidence": confidence,
        "last_probe_at": _now_iso(),
        "stale": stale,
        "error": error,
    }


def trace_freshness(app_insights_id: str, hours: int = 24) -> dict:
    """Return freshness of the latest trace in App Insights.

    Stale = no traces in the window. Caller decides what 'stale enough
    to alarm' means.
    """
    query = (
        "traces | summarize freshest_at = max(timestamp) by cloud_RoleName "
        "| sort by freshest_at desc | take 1"
    )
    try:
        response = _client().query_resource(
            resource_id=app_insights_id,
            query=query,
            timespan=timedelta(hours=hours),
        )
        if not response.tables or not response.tables[0].rows:
            return _wrap("trace_freshness",
                         {"freshest_at": None, "cloud_RoleName": None, "stale": True},
                         stale=True, confidence="medium")
        row = response.tables[0].rows[0]
        freshest_at_str = str(row[0])
        freshest_at = datetime.fromisoformat(freshest_at_str.replace("Z", "+00:00"))
        stale = (datetime.now(timezone.utc) - freshest_at) > timedelta(hours=hours)
        return _wrap("trace_freshness",
                     {"freshest_at": freshest_at_str,
                      "cloud_RoleName": str(row[1]),
                      "stale": stale},
                     stale=stale)
    except Exception as e:
        return _wrap("trace_freshness", None,
                     error=f"{type(e).__name__}: {e}", confidence="low")


def exception_rate(app_insights_id: str, hours: int = 24) -> dict:
    query = (
        "exceptions | summarize count_per_hour = count() / toreal(%d), "
        "breakdown = bag_pack_columns(cloud_RoleName) by cloud_RoleName"
    ) % hours
    try:
        response = _client().query_resource(
            resource_id=app_insights_id, query=query,
            timespan=timedelta(hours=hours),
        )
        rows = response.tables[0].rows if response.tables else []
        total = sum(float(r[0]) for r in rows) if rows else 0.0
        breakdown = {str(r[1]) if len(r) > 1 else "unknown": float(r[0])
                     for r in rows}
        return _wrap("exception_rate",
                     {"count_per_hour": total,
                      "window_hours": hours,
                      "breakdown_by_role": breakdown})
    except Exception as e:
        return _wrap("exception_rate", None,
                     error=f"{type(e).__name__}: {e}", confidence="low")


def rai_denials(workspace_id: str, hours: int = 24) -> dict:
    """Count RAI content-filter denials in a Log Analytics workspace."""
    query = _read_query("rai_denials")
    return _workspace_count_probe("rai_denials", workspace_id, query, hours,
                                  result_keys=("count", "by_category"))


def agt_denials(workspace_id: str, hours: int = 24) -> dict:
    """Count AGT policy denials by policy_id + deny_path."""
    query = _read_query("agt_denials")
    return _workspace_count_probe("agt_denials", workspace_id, query, hours,
                                  result_keys=("count", "by_policy_id",
                                               "by_deny_path"))


def rate_limit_events(workspace_id: str, hours: int = 24) -> dict:
    query = _read_query("rate_limit")
    return _workspace_count_probe("rate_limit_events", workspace_id, query,
                                  hours, result_keys=("count", "by_model"))


def _workspace_count_probe(metric: str, workspace_id: str, query: str,
                           hours: int, result_keys: tuple[str, ...]) -> dict:
    try:
        response = _client().query_workspace(
            workspace_id=workspace_id, query=query,
            timespan=timedelta(hours=hours),
        )
        if not response.tables or not response.tables[0].rows:
            empty = {k: 0 if k == "count" else {} for k in result_keys}
            empty["window_hours"] = hours
            return _wrap(metric, empty)
        # Caller's responsibility to shape the dict — we only know counts
        # generically. Each KQL file is authored to return columns matching
        # result_keys order; we hand back the raw rows + a count summary.
        rows = response.tables[0].rows
        total = len(rows)
        result = {
            "count": total,
            "window_hours": hours,
            "rows": [list(r) for r in rows],
        }
        return _wrap(metric, result)
    except Exception as e:
        return _wrap(metric, None,
                     error=f"{type(e).__name__}: {e}", confidence="low")

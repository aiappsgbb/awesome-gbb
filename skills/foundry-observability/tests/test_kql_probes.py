"""Unit tests for foundry_observability.kql_probes.

All tests mock azure.monitor.query.LogsQueryClient — no live calls.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from kql_probes import trace_freshness


def _mock_logs_response(rows):
    """Build a fake azure.monitor.query LogsQueryResult."""
    table = MagicMock()
    table.rows = rows
    table.columns = ["freshest_at", "cloud_RoleName"]
    response = MagicMock()
    response.tables = [table]
    response.status = "Success"
    return response


def test_trace_freshness_returns_fresh_when_recent(monkeypatch):
    fresh_iso = datetime.now(timezone.utc).isoformat()
    fake_client = MagicMock()
    fake_client.query_resource.return_value = _mock_logs_response(
        [[fresh_iso, "threadlight-svc"]]
    )

    with patch("kql_probes.LogsQueryClient", return_value=fake_client):
        result = trace_freshness(
            app_insights_id="/subscriptions/x/resourceGroups/y/providers/microsoft.insights/components/z",
            hours=24,
        )

    assert result["metric"] == "trace_freshness"
    assert result["stale"] is False
    assert result["result"]["cloud_RoleName"] == "threadlight-svc"
    assert result["confidence"] in {"high", "medium", "low"}
    assert result["error"] is None


def test_trace_freshness_marks_stale_when_old(monkeypatch):
    stale_iso = "2024-01-01T00:00:00+00:00"
    fake_client = MagicMock()
    fake_client.query_resource.return_value = _mock_logs_response(
        [[stale_iso, "threadlight-svc"]]
    )

    with patch("kql_probes.LogsQueryClient", return_value=fake_client):
        result = trace_freshness(app_insights_id="/x/y/z", hours=24)

    assert result["stale"] is True
    assert result["error"] is None


def test_trace_freshness_swallows_errors():
    fake_client = MagicMock()
    fake_client.query_resource.side_effect = RuntimeError("boom")

    with patch("kql_probes.LogsQueryClient", return_value=fake_client):
        result = trace_freshness(app_insights_id="/x/y/z", hours=24)

    assert result["result"] is None
    assert result["error"] is not None
    assert "boom" in result["error"]
    assert result["confidence"] == "low"

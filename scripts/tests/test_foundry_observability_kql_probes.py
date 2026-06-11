"""Unit tests for the foundry-observability KQL probe helpers.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/245
Implements the threadlight cross-cutting telemetry self-verify path.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-observability" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from kql_probes import (  # noqa: E402
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
)


@pytest.fixture
def mock_credential():
    return MagicMock(name="DefaultAzureCredential")


@pytest.fixture
def fake_client_factory(monkeypatch):
    """Replace LogsQueryClient with a fake that returns canned tables."""
    fake_client = MagicMock()
    monkeypatch.setattr("kql_probes.LogsQueryClient", lambda cred: fake_client)
    return fake_client


def _required_keys(result: dict) -> None:
    assert "result" in result
    assert "confidence" in result
    assert "last_probe_at" in result
    # error key MAY be present (None on success, str on failure)
    if "error" in result:
        assert result["error"] is None or isinstance(result["error"], str)


@pytest.mark.parametrize("probe", [
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
])
def test_every_probe_returns_required_keys(probe, mock_credential, fake_client_factory):
    fake_client_factory.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
    result = probe(workspace_id="fake-ws", app_name="fake-app",
                   credential=mock_credential)
    _required_keys(result)


@pytest.mark.parametrize("probe", [
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
])
def test_every_probe_never_raises_on_client_error(probe, mock_credential, fake_client_factory):
    """The contract is 'never raises'. Catch every exception, return error key."""
    fake_client_factory.query_workspace.side_effect = RuntimeError("transient KQL failure")
    result = probe(workspace_id="fake-ws", app_name="fake-app",
                   credential=mock_credential)
    _required_keys(result)
    assert result["error"] is not None
    assert "transient" in result["error"].lower() or "failure" in result["error"].lower()
    assert result["confidence"] == 0.0


def test_trace_freshness_returns_minutes_int(mock_credential, fake_client_factory):
    """Sanity: trace_freshness returns an int (minutes since last trace)."""
    fake_client_factory.query_workspace.return_value = MagicMock(
        tables=[MagicMock(rows=[[12]])]
    )
    result = trace_freshness(workspace_id="fake-ws", app_name="fake-app",
                              credential=mock_credential)
    assert isinstance(result["result"], int)
    assert result["confidence"] > 0.0


def test_async_variants_have_same_signature():
    """The async module exists and exposes the same 5 names."""
    from kql_probes_aio import (
        trace_freshness, exception_rate, rai_denials,
        agt_denials, rate_limit_events,
    )
    for fn in [trace_freshness, exception_rate, rai_denials,
               agt_denials, rate_limit_events]:
        # Async helpers should be coroutine functions
        import asyncio
        assert asyncio.iscoroutinefunction(fn), f"{fn.__name__} should be async"

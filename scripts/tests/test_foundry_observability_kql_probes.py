"""Unit tests for the foundry-observability KQL probe helpers.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/245
Implements the threadlight cross-cutting telemetry self-verify path.

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:
    python -m unittest discover -s scripts/tests -p 'test_*.py' -v
`unittest discover` cannot resolve pytest's fixtures.
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-observability" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from kql_probes import (  # noqa: E402
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
)


def _required_keys(result: dict) -> None:
    assert "result" in result
    assert "confidence" in result
    assert "last_probe_at" in result
    # error key MAY be present (None on success, str on failure)
    if "error" in result:
        assert result["error"] is None or isinstance(result["error"], str)


class TestKqlProbes(unittest.TestCase):
    def _setup_fake_client(self):
        """Create and return a MagicMock credential and fake client factory."""
        mock_credential = MagicMock(name="DefaultAzureCredential")
        fake_client = MagicMock()
        return mock_credential, fake_client

    def test_every_probe_returns_required_keys_trace_freshness(self) -> None:
        """trace_freshness returns required keys."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = trace_freshness(workspace_id="fake-ws", app_name="fake-app",
                                    credential=mock_credential)
            _required_keys(result)

    def test_every_probe_returns_required_keys_exception_rate(self) -> None:
        """exception_rate returns required keys."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = exception_rate(workspace_id="fake-ws", app_name="fake-app",
                                   credential=mock_credential)
            _required_keys(result)

    def test_every_probe_returns_required_keys_rai_denials(self) -> None:
        """rai_denials returns required keys."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = rai_denials(workspace_id="fake-ws", app_name="fake-app",
                                credential=mock_credential)
            _required_keys(result)

    def test_every_probe_returns_required_keys_agt_denials(self) -> None:
        """agt_denials returns required keys."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = agt_denials(workspace_id="fake-ws", app_name="fake-app",
                                credential=mock_credential)
            _required_keys(result)

    def test_every_probe_returns_required_keys_rate_limit_events(self) -> None:
        """rate_limit_events returns required keys."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(tables=[MagicMock(rows=[[5]])])
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = rate_limit_events(workspace_id="fake-ws", app_name="fake-app",
                                      credential=mock_credential)
            _required_keys(result)

    def test_every_probe_never_raises_on_client_error_trace_freshness(self) -> None:
        """trace_freshness never raises. Catch every exception, return error key."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.side_effect = RuntimeError("transient KQL failure")
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = trace_freshness(workspace_id="fake-ws", app_name="fake-app",
                                    credential=mock_credential)
            _required_keys(result)
            self.assertIsNotNone(result["error"])
            self.assertTrue("transient" in result["error"].lower() or "failure" in result["error"].lower())
            self.assertEqual(result["confidence"], 0.0)

    def test_every_probe_never_raises_on_client_error_exception_rate(self) -> None:
        """exception_rate never raises. Catch every exception, return error key."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.side_effect = RuntimeError("transient KQL failure")
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = exception_rate(workspace_id="fake-ws", app_name="fake-app",
                                   credential=mock_credential)
            _required_keys(result)
            self.assertIsNotNone(result["error"])
            self.assertTrue("transient" in result["error"].lower() or "failure" in result["error"].lower())
            self.assertEqual(result["confidence"], 0.0)

    def test_every_probe_never_raises_on_client_error_rai_denials(self) -> None:
        """rai_denials never raises. Catch every exception, return error key."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.side_effect = RuntimeError("transient KQL failure")
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = rai_denials(workspace_id="fake-ws", app_name="fake-app",
                                credential=mock_credential)
            _required_keys(result)
            self.assertIsNotNone(result["error"])
            self.assertTrue("transient" in result["error"].lower() or "failure" in result["error"].lower())
            self.assertEqual(result["confidence"], 0.0)

    def test_every_probe_never_raises_on_client_error_agt_denials(self) -> None:
        """agt_denials never raises. Catch every exception, return error key."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.side_effect = RuntimeError("transient KQL failure")
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = agt_denials(workspace_id="fake-ws", app_name="fake-app",
                                credential=mock_credential)
            _required_keys(result)
            self.assertIsNotNone(result["error"])
            self.assertTrue("transient" in result["error"].lower() or "failure" in result["error"].lower())
            self.assertEqual(result["confidence"], 0.0)

    def test_every_probe_never_raises_on_client_error_rate_limit_events(self) -> None:
        """rate_limit_events never raises. Catch every exception, return error key."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.side_effect = RuntimeError("transient KQL failure")
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = rate_limit_events(workspace_id="fake-ws", app_name="fake-app",
                                      credential=mock_credential)
            _required_keys(result)
            self.assertIsNotNone(result["error"])
            self.assertTrue("transient" in result["error"].lower() or "failure" in result["error"].lower())
            self.assertEqual(result["confidence"], 0.0)

    def test_trace_freshness_returns_minutes_int(self) -> None:
        """Sanity: trace_freshness returns an int (minutes since last trace)."""
        mock_credential, fake_client = self._setup_fake_client()
        fake_client.query_workspace.return_value = MagicMock(
            tables=[MagicMock(rows=[[12]])]
        )
        
        with patch("kql_probes.LogsQueryClient", return_value=fake_client):
            result = trace_freshness(workspace_id="fake-ws", app_name="fake-app",
                                    credential=mock_credential)
            self.assertIsInstance(result["result"], int)
            self.assertGreater(result["confidence"], 0.0)

    def test_async_variants_have_same_signature(self) -> None:
        """The async module exists and exposes the same 5 names."""
        from kql_probes_aio import (
            trace_freshness, exception_rate, rai_denials,
            agt_denials, rate_limit_events,
        )
        for fn in [trace_freshness, exception_rate, rai_denials,
                   agt_denials, rate_limit_events]:
            # Async helpers should be coroutine functions
            self.assertTrue(asyncio.iscoroutinefunction(fn), f"{fn.__name__} should be async")


if __name__ == "__main__":
    unittest.main()

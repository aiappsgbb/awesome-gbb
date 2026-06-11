"""Unit tests for the foundry-evals last-run introspection helper.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/247
Implements the threadlight EVAL-201 self-verify path.

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:
    python -m unittest discover -s scripts/tests -p 'test_*.py' -v
`unittest discover` cannot resolve pytest's `tmp_path` fixture.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-evals" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from last_run import last_run_summary  # noqa: E402


def _write_run(evals_dir: Path, ran_at: datetime, run_id: str, scenarios: list[dict]) -> None:
    """Write a fake run manifest in the layout the helper expects."""
    run_dir = evals_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "ran_at": ran_at.isoformat(),
        "run_id": run_id,
        "scenarios": scenarios,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class TestLastRunSummary(unittest.TestCase):
    def test_empty_evals_dir_returns_none(self) -> None:
        """No runs ever → returns None."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            (tmp_path / "evals").mkdir()
            result = last_run_summary(evals_dir=str(tmp_path / "evals"))
            self.assertIsNone(result)

    def test_single_green_run(self) -> None:
        """One green run → all scenarios passed, no breaches."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc) - timedelta(hours=1),
                run_id="r001",
                scenarios=[
                    {"name": "s1", "passed": True, "latency_ms": 100},
                    {"name": "s2", "passed": True, "latency_ms": 200},
                ],
            )
            result = last_run_summary(evals_dir=str(evals))
            self.assertIsNotNone(result)
            self.assertEqual(result["scenarios_total"], 2)
            self.assertEqual(result["scenarios_passed"], 2)
            self.assertEqual(result["scenarios_failed"], 0)
            self.assertEqual(result["threshold_breaches"], [])
            self.assertFalse(result["stale"])
            self.assertGreater(result["confidence"], 0.5)
            self.assertEqual(result["run_id"], "r001")

    def test_red_run_reports_breaches(self) -> None:
        """Mixed run → failed scenarios appear in threshold_breaches."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc) - timedelta(hours=2),
                run_id="r002",
                scenarios=[
                    {"name": "s1", "passed": True, "latency_ms": 100},
                    {"name": "s2", "passed": False, "latency_ms": 9999, "reason": "latency budget exceeded"},
                ],
            )
            result = last_run_summary(evals_dir=str(evals))
            self.assertIsNotNone(result)
            self.assertEqual(result["scenarios_failed"], 1)
            self.assertGreaterEqual(len(result["threshold_breaches"]), 1)
            self.assertTrue(any("s2" in b for b in result["threshold_breaches"]))

    def test_stale_run_flagged(self) -> None:
        """Run older than 7 days → stale: True."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc) - timedelta(days=10),
                run_id="r003",
                scenarios=[{"name": "s1", "passed": True, "latency_ms": 100}],
            )
            result = last_run_summary(evals_dir=str(evals))
            self.assertIsNotNone(result)
            self.assertTrue(result["stale"])

    def test_latency_percentiles_computed(self) -> None:
        """p50 + p95 latency are computed when at least 2 scenarios exist."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc),
                run_id="r004",
                scenarios=[
                    {"name": f"s{i}", "passed": True, "latency_ms": i * 100}
                    for i in range(1, 11)
                ],
            )
            result = last_run_summary(evals_dir=str(evals))
            self.assertIsNotNone(result)
            self.assertIsNotNone(result["p50_latency_ms"])
            self.assertIsNotNone(result["p95_latency_ms"])
            self.assertGreaterEqual(result["p95_latency_ms"], result["p50_latency_ms"])

    def test_required_keys_present_on_red_run(self) -> None:
        """Every documented dict key is present when a run exists."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc),
                run_id="r005",
                scenarios=[{"name": "s1", "passed": False, "latency_ms": 50}],
            )
            result = last_run_summary(evals_dir=str(evals))
            required = {
                "ran_at", "run_id", "scenarios_total", "scenarios_passed",
                "scenarios_failed", "threshold_breaches", "p50_latency_ms",
                "p95_latency_ms", "confidence", "stale", "source",
            }
            self.assertTrue(required.issubset(result.keys()))

    def test_failed_scenario_with_latency_overage_counts_once(self) -> None:
        """Scenario that is both failed AND exceeds latency → breach counts once, not twice."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            _write_run(
                evals,
                ran_at=datetime.now(timezone.utc) - timedelta(hours=1),
                run_id="r006",
                scenarios=[
                    {"name": "timeout_scenario", "passed": False, "reason": "timeout", "latency_ms": 9000},
                ],
            )
            result = last_run_summary(evals_dir=str(evals), spec_section_9={"latency_budget_ms": 5000})
            self.assertIsNotNone(result)
            # Only ONE breach entry: the failure reason, not the latency (which should not also append).
            self.assertEqual(len(result["threshold_breaches"]), 1)
            # The breach should contain the scenario name and the failure reason.
            self.assertIn("timeout_scenario", result["threshold_breaches"][0])
            self.assertIn("timeout", result["threshold_breaches"][0])

    def test_mixed_naive_and_aware_ran_at_does_not_crash(self) -> None:
        """Mixed naive and aware datetimes → sort does not crash; returns most recent."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            evals = tmp_path / "evals"
            evals.mkdir()
            # First run: naive datetime (1 hour ago in UTC, with tzinfo stripped)
            naive_dt = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
            _write_run(
                evals,
                ran_at=naive_dt,
                run_id="r_naive",
                scenarios=[{"name": "s1", "passed": True, "latency_ms": 100}],
            )
            # Second run: aware datetime (now in UTC) — more recent
            aware_dt = datetime.now(timezone.utc)
            _write_run(
                evals,
                ran_at=aware_dt,
                run_id="r_aware",
                scenarios=[{"name": "s2", "passed": True, "latency_ms": 200}],
            )
            # Call should not crash and should return the most recent (aware_dt).
            result = last_run_summary(evals_dir=str(evals))
            self.assertIsNotNone(result)
            self.assertEqual(result["run_id"], "r_aware")


if __name__ == "__main__":
    unittest.main()


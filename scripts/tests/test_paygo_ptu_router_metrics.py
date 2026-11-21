"""Offline tests for paygo-ptu-cost-analyzer's router-aware metrics path."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REFS = Path(__file__).resolve().parents[2] / "skills" / "paygo-ptu-cost-analyzer" / "references"
sys.path.insert(0, str(REFS))

import router_metrics as rm  # noqa: E402

SAMPLE = json.loads((REFS / "sample_router_metrics.json").read_text(encoding="utf-8"))


def _series(metric: str, dep: str, model: str, values: list[float]) -> dict:
    return {
        "name": {"value": metric},
        "timeseries": [{
            "metadatavalues": [
                {"name": {"value": "modeldeploymentname"}, "value": dep},
                {"name": {"value": "modelname"}, "value": model},
            ],
            "data": [{"timeStamp": f"2026-01-19T09:0{i}:00Z", "total": v} for i, v in enumerate(values)],
        }],
    }


# Mirrors the live test: 10 direct + 10 routed requests served by the own
# gpt-5.4-mini deployment; DeepSeek router-managed with disagreeing families.
LIVE_SHAPE = {"value": [
    _series("InputTokens", "gpt-5.4-mini", "gpt-5.4-mini", [200, 136]),
    _series("OutputTokens", "gpt-5.4-mini", "gpt-5.4-mini", [100, 95]),
    _series("InputTokens", "model-router", "deepseek-v4.1-flash", [46, None]),
    _series("ModelRouterInputTokens", "model-router", "gpt-5.4-mini", [100, 68]),
    _series("ModelRouterOutputTokens", "model-router", "gpt-5.4-mini", [50, 45]),
    _series("ModelRouterInputTokens", "model-router", "DeepSeek-V4.1-Flash", [84, 0]),
]}


class RouterMetricsTest(unittest.TestCase):
    def test_parse_lowercases_names_and_keeps_idle_minutes(self):
        rows = rm.parse_metrics_payload(LIVE_SHAPE)
        self.assertIn("deepseek-v4.1-flash", {r["model"] for r in rows})
        nulls = [r for r in rows if r["metric"] == "InputTokens" and r["model"].startswith("deepseek")]
        self.assertEqual([r["value"] for r in nulls], [46.0, 0.0])

    def test_parse_rejects_payload_without_token_metrics(self):
        with self.assertRaises(ValueError):
            rm.parse_metrics_payload({"value": [{"name": {"value": "Latency"}, "timeseries": []}]})

    def test_routed_on_own_deployment_is_separated_from_direct(self):
        s = rm.summarize(rm.parse_metrics_payload(LIVE_SHAPE))
        mini = next(r for r in s["served_models"] if r["model"] == "gpt-5.4-mini")
        self.assertEqual(mini["total_input_tokens"], 336)
        self.assertEqual(mini["routed_on_own_input_tokens"], 168)
        self.assertEqual(mini["direct_input_tokens"], 168)
        self.assertEqual(s["router_deployments"], ["model-router"])

    def test_metric_family_disagreement_never_invents_own_load(self):
        s = rm.summarize(rm.parse_metrics_payload(LIVE_SHAPE))
        ds = next(r for r in s["served_models"] if r["model"] == "deepseek-v4.1-flash")
        self.assertEqual(ds["routed_on_own_input_tokens"], 0)
        self.assertEqual(ds["direct_input_tokens"], 0)

    def test_sample_mix_detects_auto_router_and_flags(self):
        s = rm.summarize(rm.parse_metrics_payload(SAMPLE), ptu_catalog=["gpt-5.4-mini", "gpt-4.1"],
                         candidate_model="gpt-5.4-mini")
        self.assertEqual(s["router_deployments"], ["model-router", "model-router-2025-11-18"])
        mini = next(r for r in s["served_models"] if r["model"] == "gpt-5.4-mini")
        self.assertGreater(mini["routed_on_own_input_tokens"], 0)
        self.assertGreater(mini["direct_input_tokens"], 0)
        self.assertAlmostEqual(
            mini["total_input_tokens"],
            mini["direct_input_tokens"] + mini["routed_input_tokens"], delta=1)
        flags = {(f["model"], f["reason"].split(":")[0]) for f in s["flags"]}
        self.assertIn(("gpt-4.1", "routed traffic lands on a watched (older) pool model"), flags)
        self.assertIn(("deepseek-v4.1-flash", "no PTU pricing in models.json"), flags)
        self.assertNotIn("gpt-5.4-mini", {f["model"] for f in s["flags"]})

    def test_fee_charges_routed_input_and_optionally_excludes_cached(self):
        s = {"routed_input_tokens": 2_000_000.0, "routed_cached_tokens": 500_000.0}
        self.assertAlmostEqual(rm.router_fee(s, 0.14, 0.5)["monthly_cost"], 0.56)
        self.assertAlmostEqual(rm.router_fee(s, 0.14, 0.5, exclude_cached=True)["window_cost"], 0.21)

    def test_minute_series_direct_only_removes_routed_load(self):
        rows = rm.parse_metrics_payload(LIVE_SHAPE)
        both = rm.minute_series(rows, "gpt-5.4-mini")
        direct = rm.minute_series(rows, "gpt-5.4-mini", include_routed=False)
        self.assertEqual(sum(m["input_tokens_sum"] for m in both), 336)
        self.assertEqual(sum(m["input_tokens_sum"] for m in direct), 168)
        self.assertEqual(len(both), 2)


@unittest.skipUnless(
    all(importlib.util.find_spec(m) for m in ("pandas", "numpy", "matplotlib")),
    "analyzer dependencies not installed",
)
class RouterReportEndToEndTest(unittest.TestCase):
    def test_report_contains_router_sections(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run(
                [sys.executable, str(REFS / "run_report.py"), "--router-metrics",
                 str(REFS / "sample_router_metrics.json"), "--model", "gpt-5.4-mini",
                 "--router-fee-per-m", "0.14", "--out-dir", out],
                check=True, capture_output=True, text=True)
            md = (Path(out) / "report.md").read_text(encoding="utf-8")
            for marker in ("PTU Sizing", "PAYGO Baseline", "p95", "## Router-aware load",
                           "router absorbs into PTU", "### Router fee", "### Sizing risk flags"):
                self.assertIn(marker, md)
            meta = json.loads((Path(out) / "report.json").read_text(encoding="utf-8"))["metadata"]
            self.assertNotIn("markdown", meta["router"])
            self.assertGreater(meta["router"]["whatif"]["with_routed"]["ptus"],
                               meta["router"]["whatif"]["direct_only"]["ptus"])


if __name__ == "__main__":
    unittest.main()

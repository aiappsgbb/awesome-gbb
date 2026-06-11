"""Canonical foundry-evals last-run introspection helper.

Source of truth for the prose example in `../../SKILL.md § Programmatic last-run introspection`.

Build-to-contract per issue #247; no upstream precedent in threadlight production_ready.py.
Returns a stable dict shape that threadlight's EVAL-201 finding consumes
when `kind: sibling-skill`.

Public API:
    from foundry_evals.last_run import last_run_summary
    summary = last_run_summary(evals_dir="evals/", spec_section_9=spec_data)

Returns None if no eval has ever run. Otherwise a dict with documented keys.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

STALE_AFTER_DAYS = 7


def last_run_summary(
    evals_dir: str = "evals/",
    spec_section_9: dict[str, Any] | None = None,
) -> Optional[dict[str, Any]]:
    """Return the most-recent eval run summary, or None if none exist."""
    root = Path(evals_dir)
    runs_dir = root / "runs"
    if not runs_dir.exists():
        return None

    manifests: list[tuple[datetime, Path, dict]] = []
    for manifest_path in runs_dir.glob("*/manifest.json"):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            ran_at_dt = datetime.fromisoformat(data["ran_at"])
            # Normalize to UTC-aware to handle mixed naive/aware comparisons
            if ran_at_dt.tzinfo is None:
                ran_at_dt = ran_at_dt.replace(tzinfo=timezone.utc)
            else:
                ran_at_dt = ran_at_dt.astimezone(timezone.utc)
            manifests.append((ran_at_dt, manifest_path, data))
        except Exception:
            continue

    if not manifests:
        return None

    # Pick the most recent
    manifests.sort(key=lambda t: t[0], reverse=True)
    ran_at, manifest_path, data = manifests[0]

    scenarios = data.get("scenarios", [])
    total = len(scenarios)
    passed = sum(1 for s in scenarios if s.get("passed"))
    failed = total - passed

    breaches: list[str] = []
    for s in scenarios:
        if not s.get("passed"):
            reason = s.get("reason") or "scenario failed"
            breaches.append(f"{s.get('name', '<unnamed>')}: {reason}")
        # Spec section 9 threshold cross-checks (optional, only for passing scenarios)
        elif spec_section_9 is not None:
            latency_budget = spec_section_9.get("latency_budget_ms")
            if latency_budget is not None and s.get("latency_ms", 0) > latency_budget:
                breaches.append(
                    f"{s.get('name', '<unnamed>')}: latency {s['latency_ms']}ms > budget {latency_budget}ms"
                )

    latencies = [s["latency_ms"] for s in scenarios if "latency_ms" in s]
    p50 = float(statistics.median(latencies)) if latencies else None
    p95 = (
        float(statistics.quantiles(latencies, n=20)[-1])
        if len(latencies) >= 2 else (float(latencies[0]) if latencies else None)
    )

    age = datetime.now(timezone.utc) - ran_at.astimezone(timezone.utc)
    stale = age > timedelta(days=STALE_AFTER_DAYS)

    confidence = 1.0 if total > 0 else 0.0
    if stale:
        confidence *= 0.5

    return {
        "ran_at": ran_at.isoformat(),
        "run_id": data.get("run_id", manifest_path.parent.name),
        "scenarios_total": total,
        "scenarios_passed": passed,
        "scenarios_failed": failed,
        "threshold_breaches": breaches,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "confidence": confidence,
        "stale": stale,
        "source": str(manifest_path),
    }

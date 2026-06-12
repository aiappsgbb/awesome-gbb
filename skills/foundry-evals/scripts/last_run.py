"""Last-eval-run introspection for foundry-evals.

Lifts threadlight's _foundry_evals_last_run() into a stable shared API.

Public API:
    last_run_summary(evals_dir="evals/",
                     spec_section_9=None,
                     freshness_hours=168) -> dict | None

Returns:
    None if no eval-summary file or App Insights record exists.
    Otherwise a dict with at minimum:
        {
            "shape": "native" | "azure-ai-evals",
            "stale": bool,
            "source": "local" | "app-insights",
            "error": str | None,
            ...shape-specific fields (run_id / evaluation_name / metrics / totals...)
        }
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _detect_shape(payload: dict) -> str:
    if "totals" in payload and "metrics" in payload:
        return "native"
    if "evaluation_name" in payload or "studio_url" in payload:
        return "azure-ai-evals"
    return "unknown"


def _parse_completed_at(payload: dict, shape: str) -> datetime | None:
    candidates = []
    if shape == "native":
        candidates.append(payload.get("completed_at"))
    elif shape == "azure-ai-evals":
        candidates.append(payload.get("created_at"))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(
                str(candidate).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            continue
    return None


def _read_local(evals_dir: Path, freshness_hours: int) -> dict | None:
    try:
        files = list(evals_dir.glob("*.json"))
        if not files:
            return None
        latest = max(files, key=lambda p: p.stat().st_mtime)
        payload = json.loads(latest.read_text())
    except json.JSONDecodeError as e:
        return {
            "shape": "unknown",
            "stale": True,
            "source": "local",
            "error": f"JSONDecodeError: {e}",
        }
    except OSError as e:
        # PermissionError, FileNotFoundError (race), IsADirectoryError, etc.
        # all derive from OSError. Honor the docstring "Never raises" contract.
        return {
            "shape": "unknown",
            "stale": True,
            "source": "local",
            "error": f"{type(e).__name__}: {e}",
        }
    shape = _detect_shape(payload)
    completed_at = _parse_completed_at(payload, shape)
    stale = True
    if completed_at:
        stale = (datetime.now(timezone.utc) - completed_at) > timedelta(
            hours=freshness_hours
        )
    return {
        **payload,
        "shape": shape,
        "stale": stale,
        "source": "local",
        "error": None,
    }


def _read_app_insights(freshness_hours: int) -> dict | None:
    """Optional App Insights fallback. Skipped when conn-string not set."""
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return None
    try:
        from azure.monitor.query import LogsQueryClient
        from azure.identity import DefaultAzureCredential
    except ImportError:
        return {
            "shape": "unknown",
            "stale": True,
            "source": "app-insights",
            "error": "azure-monitor-query not installed — pip install -r requirements.txt",
        }
    # Defer the actual query implementation to a follow-up — threadlight
    # currently only ships the local-file path; App Insights fallback is
    # documented as an opt-in extension here.
    return None


def last_run_summary(
    evals_dir: str = "evals/",
    spec_section_9: dict[str, Any] | None = None,  # noqa: ARG001 (reserved for v1.3)
    freshness_hours: int = 168,
) -> dict | None:
    """Read the latest eval-run summary, preferring local files."""
    local = _read_local(Path(evals_dir), freshness_hours)
    if local is not None:
        return local
    return _read_app_insights(freshness_hours)

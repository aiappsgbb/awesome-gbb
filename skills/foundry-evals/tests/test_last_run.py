"""Unit tests for foundry_evals.last_run.

All tests run against synthetic fixtures under tests/fixtures/.
No live App Insights / Foundry calls.
"""

import sys
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from last_run import last_run_summary


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_last_run_returns_none_when_no_files(tmp_path):
    result = last_run_summary(evals_dir=str(tmp_path))
    assert result is None


def test_last_run_reads_native_shape(tmp_path):
    shutil.copy(FIXTURE_DIR / "native_summary.json",
                tmp_path / "summary.json")
    result = last_run_summary(evals_dir=str(tmp_path))
    assert result is not None
    assert result["run_id"] == "ci-smoke-eval-abc12345"
    assert result["totals"]["passes"] == 48
    assert "shape" in result and result["shape"] == "native"


def test_last_run_reads_azure_ai_evals_shape(tmp_path):
    shutil.copy(FIXTURE_DIR / "azure_ai_evals_summary.json",
                tmp_path / "summary.json")
    result = last_run_summary(evals_dir=str(tmp_path))
    assert result is not None
    assert result["evaluation_name"] == "customer-pilot-smoke"
    assert result["shape"] == "azure-ai-evals"


def test_last_run_freshness_flag_stale(tmp_path):
    payload = json.loads((FIXTURE_DIR / "native_summary.json").read_text())
    # Force completed_at well before the default 168 h window
    payload["completed_at"] = "2024-01-01T00:00:00+00:00"
    (tmp_path / "summary.json").write_text(json.dumps(payload))

    result = last_run_summary(evals_dir=str(tmp_path), freshness_hours=168)
    assert result is not None
    assert result["stale"] is True


def test_last_run_records_error_on_malformed(tmp_path):
    (tmp_path / "summary.json").write_text("{not-valid-json")
    result = last_run_summary(evals_dir=str(tmp_path))
    assert result is not None
    assert result.get("error") is not None
    assert "JSONDecodeError" in result["error"] or "json" in result["error"].lower()


def test_last_run_picks_newest_file_by_mtime(tmp_path):
    """The 'newest *.json by mtime wins' semantics must hold when
    multiple summary files exist. Older files MUST be ignored."""
    import os
    import time

    older = tmp_path / "older.json"
    older.write_text(
        json.dumps(
            {
                "run_id": "older-run-id",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "totals": {"runs": 1, "passes": 1, "failures": 0},
                "metrics": {},
            }
        )
    )
    # Force a deterministic older mtime regardless of FS resolution.
    older_mtime = time.time() - 60
    os.utime(older, (older_mtime, older_mtime))

    newer = tmp_path / "newer.json"
    newer.write_text(
        json.dumps(
            {
                "run_id": "newer-run-id",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "totals": {"runs": 2, "passes": 2, "failures": 0},
                "metrics": {},
            }
        )
    )

    result = last_run_summary(evals_dir=str(tmp_path))
    assert result is not None
    assert result["run_id"] == "newer-run-id"

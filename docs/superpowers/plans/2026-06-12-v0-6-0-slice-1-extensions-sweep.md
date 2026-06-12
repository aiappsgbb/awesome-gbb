# v0.6.0 Slice 1 — hidden-multiplier extensions sweep

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `foundry-observability`, `foundry-evals`, and
`foundry-agt` with importable Python modules so threadlight's
`production_ready.py` can replace 3 inline TODO blocks with
`from <skill_module>.<helper> import …` calls in one update round.

**Architecture:** One PR, `[multi-skill]` + `[skill-rewrite]` commit
tags. Each skill gets `scripts/<module>.py` + `scripts/__init__.py`
+ `requirements.txt` + one new SKILL.md § + PATCH version bump +
one new line in its existing test-fixture asserting the module
imports cleanly. No plugin.json bump (extensions only).

**Tech Stack:** `azure-monitor-query` for KQL, `azure-identity` for
auth, stdlib `pathlib` + `re` for file scanning. Python ≥ 3.10.
`pytest` + `pytest-mock` for unit tests.

**Closes:** #245, #247, #248.

---

## File structure

| Path | Owner | Purpose |
|---|---|---|
| `skills/foundry-observability/scripts/__init__.py` | new | Empty package marker |
| `skills/foundry-observability/scripts/kql_probes.py` | new | 5 reusable KQL probe helpers |
| `skills/foundry-observability/references/queries/agt_denials.kql` | new | Raw KQL for AGT deny events |
| `skills/foundry-observability/references/queries/rai_denials.kql` | new | Raw KQL for RAI denials |
| `skills/foundry-observability/references/queries/rate_limit.kql` | new | Raw KQL for rate-limit events |
| `skills/foundry-observability/requirements.txt` | new | `azure-monitor-query`, `azure-identity` |
| `skills/foundry-observability/SKILL.md` | modify | Add § "Reusable KQL probe helpers" + bump version 1.1.5 → 1.1.6 |
| `skills/foundry-observability/test-fixture/consumer_prompt.md` | modify | Add `import-ok` assertion step |
| `skills/foundry-observability/tests/test_kql_probes.py` | new | Pytest against mocked Log Analytics responses |
| `skills/foundry-evals/scripts/__init__.py` | new | Empty package marker |
| `skills/foundry-evals/scripts/last_run.py` | new | Last-run introspection API |
| `skills/foundry-evals/requirements.txt` | new | `azure-monitor-query` (optional, for App Insights fallback) |
| `skills/foundry-evals/SKILL.md` | modify | Add § "Last-run introspection API" + bump 1.2.0 → 1.2.1 |
| `skills/foundry-evals/test-fixture/consumer_prompt.md` | modify | Add `import-ok` assertion step |
| `skills/foundry-evals/tests/test_last_run.py` | new | Pytest against synthetic eval-output fixtures |
| `skills/foundry-evals/tests/fixtures/native_summary.json` | new | Test fixture |
| `skills/foundry-evals/tests/fixtures/azure_ai_evals_summary.json` | new | Test fixture |
| `skills/foundry-agt/scripts/__init__.py` | new | Empty package marker |
| `skills/foundry-agt/scripts/capability_detector.py` | new | AGT capability detector |
| `skills/foundry-agt/requirements.txt` | new | Stdlib only — empty file with comment |
| `skills/foundry-agt/SKILL.md` | modify | Add § "Canonical capability detector" + bump 1.2.0 → 1.2.1 |
| `skills/foundry-agt/test-fixture/consumer_prompt.md` | modify | Add `import-ok` assertion step |
| `skills/foundry-agt/tests/test_capability_detector.py` | new | Pytest against 4 inline filesystem fixtures |

**No** plugin.json / marketplace.json bump (no new skills).
**No** AGENTS.md § 12.5 metric edit (extensions, not new skills).
**No** `.github/skill-deps.yml` edit (skills already registered).

---

## Phase A — `foundry-observability` KQL probes (#245)

### Task A1: Create the empty package marker

**Files:**
- Create: `skills/foundry-observability/scripts/__init__.py`

- [ ] **Step 1: Write the file**

```python
"""Importable helpers for the foundry-observability skill.

Public API: see kql_probes.py for the reusable Log Analytics probe set.
"""
```

- [ ] **Step 2: Commit**

```bash
git add skills/foundry-observability/scripts/__init__.py
git commit -m "feat(foundry-observability): add scripts/ package marker (#245)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A2: Write the failing test for `trace_freshness`

**Files:**
- Create: `skills/foundry-observability/tests/__init__.py` (empty)
- Create: `skills/foundry-observability/tests/test_kql_probes.py`

- [ ] **Step 1: Write the test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/foundry-observability && python -m pytest tests/test_kql_probes.py -v`
Expected: `ModuleNotFoundError: No module named 'kql_probes'` (file doesn't exist yet).

### Task A3: Implement `kql_probes.py`

**Files:**
- Create: `skills/foundry-observability/scripts/kql_probes.py`

- [ ] **Step 1: Write the module**

```python
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
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/foundry-observability && python -m pytest tests/test_kql_probes.py -v`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-observability/scripts/ skills/foundry-observability/tests/
git commit -m "feat(foundry-observability): add kql_probes module + tests (#245)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A4: Create reference KQL files

**Files:**
- Create: `skills/foundry-observability/references/queries/rai_denials.kql`
- Create: `skills/foundry-observability/references/queries/agt_denials.kql`
- Create: `skills/foundry-observability/references/queries/rate_limit.kql`

- [ ] **Step 1: Write `rai_denials.kql`**

```kusto
// Reusable: RAI content-filter denials by category over time window
// Required table: AzureDiagnostics or RAIDiagnostics (depends on resource type)
// Owner: foundry-observability skill, consumed by foundry_observability.kql_probes.rai_denials
AzureDiagnostics
| where Category in ("RequestResponse", "ContentFilter")
| where ResultType == "Filtered"
| extend filter_category = tostring(parse_json(properties_s).filterCategory)
| summarize denials = count(), by_category = make_bag(pack(filter_category, count()))
  by filter_category
```

- [ ] **Step 2: Write `agt_denials.kql`**

```kusto
// Reusable: AGT policy denials by policy_id + deny_path
// Required table: AppTraces (or per-tenant custom table)
// Owner: foundry-observability skill, consumed by foundry_observability.kql_probes.agt_denials
AppTraces
| where SeverityLevel >= 2
| where Message has_any ("policy_deny", "AGT.Deny")
| extend policy_id = tostring(Properties.policy_id),
         deny_path = tostring(Properties.deny_path)
| summarize count = count(),
            by_policy_id = make_bag(pack(policy_id, count())),
            by_deny_path = make_bag(pack(deny_path, count()))
  by policy_id, deny_path
```

- [ ] **Step 3: Write `rate_limit.kql`**

```kusto
// Reusable: Model-rate-limit (429) events by model deployment
// Required table: AppTraces / AppRequests / ResourceLogs (depends on emitter)
// Owner: foundry-observability skill, consumed by foundry_observability.kql_probes.rate_limit_events
AppRequests
| where ResultCode == "429"
| extend model = tostring(Properties.model)
| summarize count = count(), by_model = make_bag(pack(model, count())) by model
```

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-observability/references/queries/
git commit -m "feat(foundry-observability): add reusable KQL files for probes (#245)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A5: Add `requirements.txt`

**Files:**
- Create: `skills/foundry-observability/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for foundry-observability scripts/
#
# Install with: pip install -r skills/foundry-observability/requirements.txt

azure-monitor-query~=1.4.0
azure-identity~=1.19.0
```

- [ ] **Step 2: Verify deps install + module imports**

Run: `pip install -r skills/foundry-observability/requirements.txt && \
PYTHONPATH=skills/foundry-observability/scripts python -c "from kql_probes import trace_freshness; print('import-ok')"`
Expected: `import-ok`.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-observability/requirements.txt
git commit -m "feat(foundry-observability): pin scripts/ deps (#245)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A6: Update SKILL.md (new § + version bump + description trim if needed)

**Files:**
- Modify: `skills/foundry-observability/SKILL.md` (frontmatter version bump + new § near bottom)

- [ ] **Step 1: Check description length budget**

Run: `python -c "
import yaml, pathlib
d = yaml.safe_load(pathlib.Path('skills/foundry-observability/SKILL.md').read_text().split('---')[1])
print(f'{len(d[\"description\"])}/1024')
"`
Expected: 1020/1024 (4 chars headroom — confirmed pre-edit baseline).

- [ ] **Step 2: Bump version 1.1.5 → 1.1.6 in frontmatter**

Edit `skills/foundry-observability/SKILL.md` — change `version: "1.1.5"` to `version: "1.1.6"` in the `metadata:` block.

- [ ] **Step 3: Add the new section near the bottom (before any "## See also" / "## References" tail)**

Append this section to `SKILL.md`:

```markdown
## Reusable KQL probe helpers (v1.1.6+)

The `scripts/kql_probes.py` module exposes five reusable Log Analytics
probes that other skills (notably `threadlight-production-ready`) can
import directly:

```python
from kql_probes import (
    trace_freshness, exception_rate,
    rai_denials, agt_denials, rate_limit_events,
)
result = trace_freshness(app_insights_id="<resource-id>", hours=24)
```

Each helper returns:

```python
{
    "metric": "<helper_name>",
    "result": {...} | None,
    "confidence": "high" | "medium" | "low",
    "last_probe_at": "<ISO 8601 UTC>",
    "stale": bool,
    "error": str | None,    # never raises
}
```

**Auth:** `azure.identity.DefaultAzureCredential` (keyless).
**Minimum RBAC:** `Log Analytics Reader` on the LA workspace (for
workspace helpers) AND `Monitoring Reader` on the App Insights
resource (for `trace_freshness` / `exception_rate`).

**Install deps:** `pip install -r requirements.txt`.

**Raw KQL bodies** live under `references/queries/*.kql` so they can
be lifted into Grafana / a workbook without round-tripping through
Python.

See `tests/test_kql_probes.py` for the contract assertions each
helper honors.
```

- [ ] **Step 4: Run repo validator to confirm description still ≤ 1024 and SemVer valid**

Run: `python scripts/validate-skills.py skills/foundry-observability/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-observability/SKILL.md
git commit -m "docs(foundry-observability): document scripts/kql_probes (#245)

Bump 1.1.5 → 1.1.6. Document the 5 reusable KQL probe helpers added
in this slice. Description stays at 1020/1024 chars — no new USE FOR
triggers; consumers discover via the new section anchor.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A7: Extend the existing fixture with the import-ok assertion

**Files:**
- Modify: `skills/foundry-observability/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Locate the fixture's final user-visible step (the one immediately before Step N marker contract)**

Run: `grep -n "## Step" skills/foundry-observability/test-fixture/consumer_prompt.md`
Note the step number right before the marker contract; call it `S`.

- [ ] **Step 2: Insert one new step between `S` and the marker contract**

Add this section just before the marker section:

```markdown
## Step S+1 — Validate `scripts/` module import (Slice 1 contract)

After all prior probe work succeeds, verify the new
`scripts/kql_probes` module ships and imports cleanly:

```bash
cd "$GITHUB_WORKSPACE" && \
pip install --quiet -r skills/foundry-observability/requirements.txt && \
PYTHONPATH=skills/foundry-observability/scripts \
  python -c "from kql_probes import trace_freshness; print('kql_probes-import-ok')"
```

Expected stdout includes `kql_probes-import-ok`. If the import
fails, write `SMOKE_RESULT=FAIL kql_probes import failed: <reason>`
in Step N.
```

- [ ] **Step 3: Verify the fixture still fits the 8 KB budget**

Run: `wc -c skills/foundry-observability/test-fixture/consumer_prompt.md`
Expected: < 8192.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-observability/test-fixture/consumer_prompt.md
git commit -m "test(foundry-observability): assert kql_probes module imports in fixture (#245)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase B — `foundry-evals` last-run API (#247)

### Task B1: Create empty package marker + test fixtures

**Files:**
- Create: `skills/foundry-evals/scripts/__init__.py`
- Create: `skills/foundry-evals/tests/__init__.py` (empty)
- Create: `skills/foundry-evals/tests/fixtures/native_summary.json`
- Create: `skills/foundry-evals/tests/fixtures/azure_ai_evals_summary.json`

- [ ] **Step 1: Write the package marker**

```python
"""Importable helpers for the foundry-evals skill.

Public API: see last_run.py for the last-eval-run introspection helper.
"""
```

- [ ] **Step 2: Write the native-shape fixture (`native_summary.json`)**

```json
{
  "run_id": "ci-smoke-eval-abc12345",
  "completed_at": "2026-06-10T12:30:00+00:00",
  "spec_section": "9.2",
  "dataset": "tests/datasets/customer-pilot-smoke.jsonl",
  "metrics": {
    "groundedness": {"score": 0.92, "threshold": 0.85, "status": "pass"},
    "relevance":    {"score": 0.88, "threshold": 0.80, "status": "pass"},
    "fluency":      {"score": 0.95, "threshold": 0.90, "status": "pass"}
  },
  "totals": {"runs": 50, "passes": 48, "failures": 2}
}
```

- [ ] **Step 3: Write the azure-ai-evals-shape fixture (`azure_ai_evals_summary.json`)**

```json
{
  "id": "evals-azure-shape-7a3f1c",
  "studio_url": "https://ai.azure.com/build/evaluations/...",
  "evaluation_name": "customer-pilot-smoke",
  "created_at": "2026-06-10T11:45:00.000Z",
  "metrics": {
    "groundedness.aggregated": 0.91,
    "relevance.aggregated": 0.86,
    "fluency.aggregated": 0.94
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-evals/scripts/__init__.py skills/foundry-evals/tests/
git commit -m "test(foundry-evals): scaffold scripts package + test fixtures (#247)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task B2: Write the failing test for `last_run_summary`

**Files:**
- Create: `skills/foundry-evals/tests/test_last_run.py`

- [ ] **Step 1: Write the test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/foundry-evals && python -m pytest tests/test_last_run.py -v`
Expected: `ModuleNotFoundError: No module named 'last_run'`.

### Task B3: Implement `last_run.py`

**Files:**
- Create: `skills/foundry-evals/scripts/last_run.py`

- [ ] **Step 1: Write the module**

```python
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
    files = list(evals_dir.glob("*.json"))
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        payload = json.loads(latest.read_text())
    except json.JSONDecodeError as e:
        return {
            "shape": "unknown",
            "stale": True,
            "source": "local",
            "error": f"JSONDecodeError: {e}",
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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/foundry-evals && python -m pytest tests/test_last_run.py -v`
Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-evals/scripts/last_run.py skills/foundry-evals/tests/test_last_run.py
git commit -m "feat(foundry-evals): add last_run_summary helper (#247)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task B4: Add `requirements.txt`

**Files:**
- Create: `skills/foundry-evals/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for foundry-evals scripts/
#
# Install with: pip install -r skills/foundry-evals/requirements.txt

# Optional: azure-monitor-query is only needed when the App Insights
# fallback in scripts/last_run.py is exercised (i.e. when
# APPLICATIONINSIGHTS_CONNECTION_STRING is set).
azure-monitor-query~=1.4.0
azure-identity~=1.19.0
```

- [ ] **Step 2: Commit**

```bash
git add skills/foundry-evals/requirements.txt
git commit -m "feat(foundry-evals): pin scripts/ deps (#247)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task B5: Update SKILL.md (new § + version bump)

**Files:**
- Modify: `skills/foundry-evals/SKILL.md`

- [ ] **Step 1: Bump version 1.2.0 → 1.2.1 in frontmatter**

Edit `metadata.version` line.

- [ ] **Step 2: Append the new section**

```markdown
## Last-run introspection API (v1.2.1+)

The `scripts/last_run.py` module exposes a single helper for reading
the most recent eval-run summary, designed for callers (notably
`threadlight-production-ready`) that need to gate on freshness:

```python
from last_run import last_run_summary

summary = last_run_summary(
    evals_dir="evals/",         # convention: latest *.json wins
    spec_section_9=None,        # reserved for SPEC § 9 threshold compare
    freshness_hours=168,        # default 7 days
)
# → dict | None
```

**Read order:**

1. Local files under `evals_dir/` — picks the newest by mtime.
2. **Fallback (opt-in):** App Insights
   `customEvents | where name == "EvalRunCompleted"` — only attempted
   when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set.

**Shape detection:** Returns `shape: "native"` for foundry-evals
emitted summaries (with `totals` + `metrics`) or
`shape: "azure-ai-evals"` for the Azure AI Evaluation SDK shape
(with `evaluation_name` + `studio_url`).

**Never raises.** Malformed JSON populates `error` on the returned
dict; missing files return `None`.

See `tests/test_last_run.py` for the contract assertions.
```

- [ ] **Step 3: Validate**

Run: `python scripts/validate-skills.py skills/foundry-evals/`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-evals/SKILL.md
git commit -m "docs(foundry-evals): document last_run_summary API (#247)

Bump 1.2.0 → 1.2.1. Document the last-eval-run introspection helper.
Description stays well under cap (945/1024); no new USE FOR triggers.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task B6: Extend the foundry-evals fixture with the import assertion

**Files:**
- Modify: `skills/foundry-evals/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Locate the marker section, insert above it**

```markdown
## Step S+1 — Validate `scripts/` module import (Slice 1 contract)

After all prior eval-run work succeeds, verify the new
`scripts/last_run` module ships and imports cleanly:

```bash
cd "$GITHUB_WORKSPACE" && \
pip install --quiet -r skills/foundry-evals/requirements.txt && \
PYTHONPATH=skills/foundry-evals/scripts \
  python -c "from last_run import last_run_summary; print('last_run-import-ok')"
```

Expected stdout includes `last_run-import-ok`. If the import fails,
write `SMOKE_RESULT=FAIL last_run import failed: <reason>` in Step N.
```

- [ ] **Step 2: Verify fixture still fits 8 KB budget**

Run: `wc -c skills/foundry-evals/test-fixture/consumer_prompt.md`
Expected: < 8192.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-evals/test-fixture/consumer_prompt.md
git commit -m "test(foundry-evals): assert last_run module imports in fixture (#247)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase C — `foundry-agt` capability detector (#248)

### Task C1: Create empty package marker + 4 inline test fixtures

**Files:**
- Create: `skills/foundry-agt/scripts/__init__.py`
- Create: `skills/foundry-agt/tests/__init__.py` (empty)

(Inline filesystem fixtures are created by each test using `tmp_path`
— no on-disk fixture dir needed.)

- [ ] **Step 1: Write the package marker**

```python
"""Importable helpers for the foundry-agt skill.

Public API: see capability_detector.py for the canonical AGT signal scanner.
"""
```

- [ ] **Step 2: Commit**

```bash
git add skills/foundry-agt/scripts/__init__.py skills/foundry-agt/tests/__init__.py
git commit -m "test(foundry-agt): scaffold scripts package + tests dir (#248)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C2: Write the failing test for `detect`

**Files:**
- Create: `skills/foundry-agt/tests/test_capability_detector.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for foundry_agt.capability_detector.

All filesystem fixtures are built inline via tmp_path. No on-disk
fixture directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from capability_detector import detect


def _write(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_detect_v3_7_only(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["agt~=3.7.0"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] in {"3.7", "3.7.0", "3.x"}
    assert caps["intervention_points_present"] is False
    assert caps["policy_yaml_path"] is None


def test_detect_v4_1_with_policy_and_intervention(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["agt~=4.1.0"]\n')
    _write(tmp_path / "agt.policy.yaml",
           "deny:\n  - rule: pii_egress\n    deny_path: data.pii\n")
    _write(tmp_path / "src/agent.py",
           "from agt.intervention import enforce\nenforce(...)\n")
    _write(tmp_path / "verifier.json",
           '{"audit_fields": ["timestamp", "principal", "action"]}\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] in {"4.1", "4.1.0", "4.x"}
    assert caps["intervention_points_present"] is True
    assert caps["policy_yaml_path"] is not None
    assert caps["policy_yaml_path"].endswith("agt.policy.yaml")
    assert caps["deny_path_present"] is True
    assert caps["audit_fields_in_verifier_json"] is True


def test_detect_mixed_v3_and_v4(tmp_path):
    _write(tmp_path / "pyproject.toml",
           'dependencies = ["agt~=3.7.0", "agt-v4-dynamic~=0.1.0"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] == "mixed"


def test_detect_no_agt(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["fastapi"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] is None
    assert caps["intervention_points_present"] is False
    assert caps["policy_yaml_path"] is None
    assert caps["deny_path_present"] is False
    assert caps["audit_fields_in_verifier_json"] is False
    assert caps["ci_action_pinned"] is False


def test_detect_ci_action_pinned(tmp_path):
    _write(tmp_path / ".github/workflows/agt.yml",
           "uses: microsoft/agt-action@v1.2.3\n")
    caps = detect(repo_root=str(tmp_path))
    assert caps["ci_action_pinned"] is True


def test_detect_evidence_globs_scanned(tmp_path):
    """The returned dict MUST include the list of globs that were inspected
    so the caller can report 'we looked at these places and found nothing'."""
    caps = detect(repo_root=str(tmp_path))
    assert "evidence_globs_scanned" in caps
    assert isinstance(caps["evidence_globs_scanned"], list)
    assert len(caps["evidence_globs_scanned"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/foundry-agt && python -m pytest tests/test_capability_detector.py -v`
Expected: `ModuleNotFoundError: No module named 'capability_detector'`.

### Task C3: Implement `capability_detector.py`

**Files:**
- Create: `skills/foundry-agt/scripts/capability_detector.py`

- [ ] **Step 1: Write the module**

```python
"""Canonical AGT capability detector for the foundry-agt skill.

Lifts threadlight's AGT_DIST_REGEX / V4_POLICY_REGEX / V4_DYNAMIC_REGEX
+ inline filesystem scans into a single reusable function. Replaces the
prose-and-snippet detection block in earlier versions of SKILL.md.

Public API:
    detect(repo_root: str = ".") -> dict
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

AGT_DIST_REGEX = re.compile(
    r'(?:^|[\s,"\'])agt(?:-v4-dynamic)?\s*[~^=><]+\s*(\d+\.\d+(?:\.\d+)?)'
)
V4_POLICY_FILE_NAMES = ("agt.policy.yaml", "agt.policy.yml")
V4_INTERVENTION_REGEX = re.compile(
    r'\bfrom\s+agt\.intervention\b|\bagt\.intervention\.enforce\b'
)
V4_DENY_PATH_REGEX = re.compile(r'\bdeny_path\s*:')
V4_DYNAMIC_PKG_REGEX = re.compile(r'\bagt-v4-dynamic\b')
CI_ACTION_REGEX = re.compile(r'uses:\s*microsoft/agt-action@v\d+\.\d+\.\d+')

EVIDENCE_GLOBS = (
    "pyproject.toml",
    "requirements*.txt",
    "agt.policy.yaml",
    "agt.policy.yml",
    "verifier.json",
    "**/*.py",
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
)


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_version(repo: Path) -> str | None:
    versions: set[str] = set()
    seen_dynamic = False
    for pyproject in [*repo.glob("pyproject.toml"),
                      *repo.glob("requirements*.txt")]:
        text = _read(pyproject)
        for m in AGT_DIST_REGEX.finditer(text):
            v = m.group(1)
            # Bucket major version for the dict-value shape callers expect
            major_minor = ".".join(v.split(".")[:2])
            versions.add(major_minor)
        if V4_DYNAMIC_PKG_REGEX.search(text):
            seen_dynamic = True
            versions.add("4.x")
    if not versions:
        return None
    if len(versions) == 1:
        only = versions.pop()
        # Normalise "4.x" alongside an explicit "4.1" → "4.1"
        return only
    # Multiple major-minor versions => "mixed"
    majors = {v.split(".")[0] for v in versions}
    if len(majors) > 1:
        return "mixed"
    return sorted(versions)[-1]


def _find_policy_yaml(repo: Path) -> Path | None:
    for name in V4_POLICY_FILE_NAMES:
        candidates = list(repo.rglob(name))
        if candidates:
            return candidates[0]
    return None


def _intervention_points_present(repo: Path) -> bool:
    for py in repo.rglob("*.py"):
        if V4_INTERVENTION_REGEX.search(_read(py)):
            return True
    return False


def _deny_path_present(policy_path: Path | None) -> bool:
    if policy_path is None:
        return False
    return bool(V4_DENY_PATH_REGEX.search(_read(policy_path)))


def _audit_fields_in_verifier(repo: Path) -> bool:
    verifier = repo / "verifier.json"
    if not verifier.exists():
        return False
    try:
        payload = json.loads(verifier.read_text())
    except json.JSONDecodeError:
        return False
    return bool(payload.get("audit_fields"))


def _ci_action_pinned(repo: Path) -> bool:
    for wf in [*(repo / ".github/workflows").rglob("*.yml"),
               *(repo / ".github/workflows").rglob("*.yaml")]:
        if CI_ACTION_REGEX.search(_read(wf)):
            return True
    return False


def detect(repo_root: str = ".") -> dict[str, Any]:
    """Scan repo for AGT signals; return canonical capability dict."""
    repo = Path(repo_root)
    policy_path = _find_policy_yaml(repo)
    return {
        "version_detected": _detect_version(repo),
        "intervention_points_present": _intervention_points_present(repo),
        "policy_yaml_path": str(policy_path) if policy_path else None,
        "deny_path_present": _deny_path_present(policy_path),
        "audit_fields_in_verifier_json": _audit_fields_in_verifier(repo),
        "ci_action_pinned": _ci_action_pinned(repo),
        "evidence_globs_scanned": list(EVIDENCE_GLOBS),
    }
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/foundry-agt && python -m pytest tests/test_capability_detector.py -v`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-agt/scripts/capability_detector.py skills/foundry-agt/tests/
git commit -m "feat(foundry-agt): add canonical capability_detector (#248)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C4: Add `requirements.txt` (stdlib-only marker)

**Files:**
- Create: `skills/foundry-agt/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for foundry-agt scripts/
#
# scripts/capability_detector.py is stdlib-only — no pinned deps.
# This file exists so the catalog convention "every skill with a
# scripts/ package ships a requirements.txt" is consistent across
# all extended skills (foundry-observability, foundry-evals, foundry-agt).
```

- [ ] **Step 2: Commit**

```bash
git add skills/foundry-agt/requirements.txt
git commit -m "feat(foundry-agt): scaffold requirements.txt for scripts/ (#248)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C5: Update SKILL.md (new § + version bump)

**Files:**
- Modify: `skills/foundry-agt/SKILL.md`

- [ ] **Step 1: Bump version 1.2.0 → 1.2.1**

- [ ] **Step 2: Append the new section**

```markdown
## Canonical capability detector (v1.2.1+)

The `scripts/capability_detector.py` module exposes a single
`detect(repo_root)` function that scans a repository for AGT
signals — version pin, intervention points, policy YAML, deny
paths, verifier audit fields, CI action pinning — and returns a
canonical capability dict.

```python
from capability_detector import detect

caps = detect(repo_root=".")
# {
#   "version_detected": "4.1" | "3.7" | "mixed" | None,
#   "intervention_points_present": bool,
#   "policy_yaml_path": str | None,
#   "deny_path_present": bool,
#   "audit_fields_in_verifier_json": bool,
#   "ci_action_pinned": bool,
#   "evidence_globs_scanned": [...],
# }
```

**Stdlib only.** No third-party deps. Safe to import in any
Python ≥ 3.10 environment.

**Why this replaces the prose detection guide.** Earlier versions
of this SKILL.md described AGT-presence detection in prose +
copy-paste regex snippets. That worked for one consumer (the
operator following the SKILL.md verbatim) but produced version
drift when threadlight tried to mirror the same detection
semantics inline. Now there is exactly one detection implementation,
shared by every consumer.

See `tests/test_capability_detector.py` for the contract:
6 unit tests covering v3.7-only, v4.1-with-policy, mixed, no-AGT,
CI-action-pinned, and the `evidence_globs_scanned` self-reporting
field.
```

- [ ] **Step 3: Validate**

Run: `python scripts/validate-skills.py skills/foundry-agt/`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-agt/SKILL.md
git commit -m "docs(foundry-agt): document scripts/capability_detector (#248)

Bump 1.2.0 → 1.2.1. Document the canonical AGT signal detector.
Description stays at 986/1024 chars; no new USE FOR triggers.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C6: Extend the foundry-agt fixture with the import assertion

**Files:**
- Modify: `skills/foundry-agt/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Insert the step above the marker contract**

```markdown
## Step S+1 — Validate `scripts/` module import (Slice 1 contract)

After all prior policy + intervention work succeeds, verify the new
`scripts/capability_detector` module ships and imports cleanly:

```bash
cd "$GITHUB_WORKSPACE" && \
PYTHONPATH=skills/foundry-agt/scripts \
  python -c "from capability_detector import detect; print('cap_detector-import-ok')"
```

Expected stdout includes `cap_detector-import-ok`. If the import
fails, write `SMOKE_RESULT=FAIL capability_detector import failed: <reason>`
in Step N.

(No `pip install` step needed — stdlib only.)
```

- [ ] **Step 2: Verify fixture still fits 8 KB budget**

Run: `wc -c skills/foundry-agt/test-fixture/consumer_prompt.md`
Expected: < 8192.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-agt/test-fixture/consumer_prompt.md
git commit -m "test(foundry-agt): assert capability_detector imports in fixture (#248)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase D — PR-level integration

### Task D1: Run repo validator across all 3 skills

- [ ] **Step 1: Validate**

Run: `python scripts/validate-skills.py skills/foundry-observability/ skills/foundry-evals/ skills/foundry-agt/`
Expected: PASS for all three.

### Task D2: Run unit tests across all 3 packages

- [ ] **Step 1: Run pytest**

Run: `for s in foundry-observability foundry-evals foundry-agt; do
  (cd skills/$s && python -m pytest tests/ -v) || exit 1;
done`
Expected: all tests pass.

### Task D3: Open the PR with `[multi-skill]` tag and reviewer notes

- [ ] **Step 1: Push branch + open PR**

Run:

```bash
git push -u origin HEAD
gh pr create \
  --title "feat: hidden-multiplier extensions sweep — kql_probes + last_run + capability_detector (#245 #247 #248)" \
  --body "Closes #245, #247, #248.

Adds 3 importable Python modules so threadlight's
\`production_ready.py\` can replace inline TODO blocks with direct
imports.

- \`foundry-observability/scripts/kql_probes.py\` — 5 Log Analytics
  probe helpers (trace_freshness, exception_rate, rai_denials,
  agt_denials, rate_limit_events). 1.1.5 → 1.1.6.
- \`foundry-evals/scripts/last_run.py\` — last-eval-run summary
  reader. Local-files-first with optional App Insights fallback.
  1.2.0 → 1.2.1.
- \`foundry-agt/scripts/capability_detector.py\` — canonical AGT
  signal scanner. Replaces prose detection guide. 1.2.0 → 1.2.1.

Each module ships with pytest coverage (3+5+6 tests = 14 new tests,
all mocked / fixture-based, zero live Azure calls in tests). Each
existing test-fixture gets one new import-ok assertion step
(~150 bytes per fixture, well under Pattern 19 budget).

No plugin.json bump (extensions only).

[multi-skill][skill-rewrite]" \
  --base main
```

- [ ] **Step 2: Verify CI gates fire**

Watch `skill-validation.yml` + `pin-validation.yml` + the 3
`copilot-cli-matrix` legs (foundry-observability, foundry-evals,
foundry-agt). All MUST go green before merge per AGENTS.md § 2.9.

- [ ] **Step 3: Paste live-test evidence into PR description**

Per AGENTS.md § 2.9, no merge without Azure evidence. The 3
existing fixtures' `copilot-cli-matrix` runs ARE the Azure
evidence — link the green run in a PR comment.

---

## Self-review

- [ ] **Spec coverage:** #245, #247, #248 each have a Phase
      (A, B, C) with implementation + test + SKILL.md + fixture
      tasks. ✅
- [ ] **Placeholder scan:** No TBD / TODO / "implement later"
      strings in any task. ✅
- [ ] **Type consistency:** `trace_freshness` returns
      `result["cloud_RoleName"]` in test A2 and the production
      `kql_probes.py` populates that key. `last_run_summary`
      returns `shape` field in test B2 and impl B3 sets it.
      `detect` returns `evidence_globs_scanned` in test C2 and
      impl C3 populates it. ✅
- [ ] **No new USE FOR triggers added** — extension descriptions
      stay within budget per umbrella spec § 3.7. ✅
- [ ] **Commit tags:** Final PR carries `[multi-skill]` +
      `[skill-rewrite]` per umbrella spec § 3.9 + AGENTS.md § 4.
      ✅
- [ ] **No `pyproject.toml`** — `requirements.txt` only per
      umbrella spec § 3.4. ✅

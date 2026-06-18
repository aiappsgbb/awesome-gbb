# Slice A — Hidden-multiplier helpers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift threadlight's inline `_detect_agt_profile()`, `_kql_*`, and `_foundry_evals_last_run()` helpers into proper SKILL.md helpers in `foundry-agt`, `foundry-observability`, and `foundry-evals` so threadlight v0.5.1 can flip 7+ findings from `kind: manual` to `kind: sibling-skill`.

**Architecture:** Three independent extension PRs collapsed into one multi-skill PR. Each helper lives in `skills/<host>/references/python/<helper>.py` per AGENTS.md §7 SSOT rule; SKILL.md gets a new section that cross-links the reference file without duplicating code. Pure-Python helpers; no Azure deploy work. Tests are pytest unit tests with mocked clients and `tmp_path` fixtures — no Copilot-CLI fixtures, no Azure E2E.

**Tech Stack:** Python 3.11+, pytest, `azure-monitor-query` (existing on foundry-observability), `azure-identity` (existing chain).

**Spec:** [`docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md`](../specs/2026-06-11-v060-upstream-landings-design.md) §4.1
**Issues closed:** #248, #245, #247
**Threadlight unlock:** v0.5.1 (7+ recipes flip)

---

## File Structure

**Create:**
- `skills/foundry-agt/references/python/capability_detector.py`
- `skills/foundry-agt/references/python/__init__.py` (if not present)
- `skills/foundry-observability/references/python/kql_probes.py`
- `skills/foundry-observability/references/python/kql_probes_aio.py`
- `skills/foundry-observability/references/python/__init__.py` (if not present)
- `skills/foundry-evals/references/python/last_run.py`
- `skills/foundry-evals/references/python/__init__.py` (if not present)
- `scripts/tests/test_foundry_agt_capability_detector.py`
- `scripts/tests/test_foundry_observability_kql_probes.py`
- `scripts/tests/test_foundry_evals_last_run.py`

**Modify:**
- `skills/foundry-agt/SKILL.md` (new "Using the canonical capability detector" section; MINOR bump)
- `skills/foundry-observability/SKILL.md` (new "Reusable KQL probe helpers" section; MINOR bump)
- `skills/foundry-observability/references/upstream-pin.md` (verify `azure-monitor-query` listed; MINOR bump if updated)
- `skills/foundry-evals/SKILL.md` (new "Programmatic last-run introspection" section; MINOR bump)
- `plugin.json` (PATCH bump, e.g. `4.x.y` → `4.x.(y+1)`)
- `.github/plugin/marketplace.json` (PATCH bump matched to plugin.json)

**Read-only (reference):**
- Threadlight source: https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-production-ready/scripts/production_ready.py (the canonical baselines per AGENTS.md §7)
- Threadlight contract: https://raw.githubusercontent.com/aiappsgbb/threadlight-skills/main/skills/threadlight-production-ready/references/sibling-skills-map.md

**Do NOT touch:**
- Any other skill under `skills/`
- Any CI workflow under `.github/workflows/`
- `.github/skill-deps.yml` (no new skills added)
- AGENTS.md (no §12.5 stat changes; skill count unchanged at 27)

---

## Phase 0 — Setup

### Task 0.1: Fetch threadlight reference implementations

**Files:**
- Read: cached temp location of your choice

- [ ] **Step 1: Fetch the threadlight script that contains the canonical helpers**

Run:
```bash
mkdir -p /tmp/v060-refs
curl -fsSL https://raw.githubusercontent.com/aiappsgbb/threadlight-skills/main/skills/threadlight-production-ready/scripts/production_ready.py \
  -o /tmp/v060-refs/production_ready.py
wc -l /tmp/v060-refs/production_ready.py
```

Expected: file downloads, line count ≥ 500.

- [ ] **Step 2: Identify the relevant function blocks**

Run:
```bash
grep -n "^def _detect_agt_profile\|^def _kql_\|^def _foundry_evals_last_run\|^V4_DIST_REGEX\|^V4_POLICY_REGEX\|^V4_DYNAMIC_REGEX" /tmp/v060-refs/production_ready.py
```

Expected: 5-8 line numbers reported. Note the start line of each helper for the lifts in later tasks.

- [ ] **Step 3: Skim each helper to estimate LOC**

Run:
```bash
sed -n '/^def _detect_agt_profile/,/^def [^_]/p' /tmp/v060-refs/production_ready.py | wc -l
sed -n '/^def _kql_/,/^def [^_]/p' /tmp/v060-refs/production_ready.py | wc -l
sed -n '/^def _foundry_evals_last_run/,/^def [^_]/p' /tmp/v060-refs/production_ready.py | wc -l
```

Expected: _detect_agt_profile ≥ 50, _kql_* family ≥ 100, _foundry_evals_last_run ≥ 40 (rough; per spec §4.1 these are 60-150 LOC each).

No commit here — pure read-only exploration.

---

## Phase 1 — Issue #248: foundry-agt canonical capability detector

### Task 1.1: Write the failing test file

**Files:**
- Create: `scripts/tests/test_foundry_agt_capability_detector.py`

- [ ] **Step 1: Write the failing test**

Create the file with this content:

```python
"""Unit tests for the foundry-agt canonical capability detector.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/248
Implements the threadlight AGT-V4-001..007 self-verify path.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Add the skill's reference dir to sys.path
SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from capability_detector import detect  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def test_empty_repo_returns_default_shape(tmp_path: Path) -> None:
    """A repo with no AGT artifacts returns every flag False / list empty."""
    result = detect(repo_root=str(tmp_path))

    assert result["version_detected"] is None
    assert result["detection_confidence"] == 0.0
    assert result["package_pins"] == {}
    assert result["intervention_points_present"] is False
    assert result["policy_yaml_path"] is None
    assert result["deny_path_present"] is False
    assert result["audit_fields_in_verifier_json"] == []
    assert result["ci_action_pinned"] is False
    assert isinstance(result["evidence_globs_scanned"], list)


def test_full_v4_repo_returns_high_confidence(tmp_path: Path) -> None:
    """A repo with pinned v4 + intervention points + policy YAML + pinned CI action returns full confidence."""
    _write(tmp_path / "pyproject.toml", """
        [project]
        dependencies = ["foundry-agt==4.0.0"]
        """)
    _write(tmp_path / "src" / "agent.py", """
        from foundry_agt.intervention import V4_DIST_REGEX  # noqa
        from foundry_agt.intervention import V4_POLICY_REGEX  # noqa
        from foundry_agt.intervention import V4_DYNAMIC_REGEX  # noqa
        """)
    _write(tmp_path / "policies" / "agt.yaml", """
        version: 4
        deny:
          - "*.exfiltration"
        """)
    _write(tmp_path / "verifiers" / "audit.json", """
        {"audit_fields": ["actor", "tool", "outcome", "policy_version"]}
        """)
    _write(tmp_path / ".github" / "workflows" / "agt.yml", """
        jobs:
          verify:
            steps:
              - uses: foundry-agt/verify@a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
        """)

    result = detect(repo_root=str(tmp_path))

    assert result["version_detected"] == "4.0.0"
    assert result["detection_confidence"] >= 0.8
    assert "foundry-agt" in result["package_pins"]
    assert result["intervention_points_present"] is True
    assert result["policy_yaml_path"] is not None
    assert result["deny_path_present"] is True
    assert "actor" in result["audit_fields_in_verifier_json"]
    assert result["ci_action_pinned"] is True


def test_missing_policy_yaml_returns_none_path(tmp_path: Path) -> None:
    """Pinned v4 package but no AGT policy YAML returns policy_yaml_path: None."""
    _write(tmp_path / "pyproject.toml", """
        [project]
        dependencies = ["foundry-agt==4.0.0"]
        """)
    result = detect(repo_root=str(tmp_path))
    assert result["version_detected"] == "4.0.0"
    assert result["policy_yaml_path"] is None
    assert result["deny_path_present"] is False


def test_ci_action_unpinned_returns_false(tmp_path: Path) -> None:
    """GitHub Action referenced by tag (not SHA) flags as unpinned."""
    _write(tmp_path / ".github" / "workflows" / "agt.yml", """
        jobs:
          verify:
            steps:
              - uses: foundry-agt/verify@v4
        """)
    result = detect(repo_root=str(tmp_path))
    assert result["ci_action_pinned"] is False


def test_returns_all_required_keys(tmp_path: Path) -> None:
    """The contract requires every key always present, even on empty input."""
    result = detect(repo_root=str(tmp_path))
    required_keys = {
        "version_detected", "detection_confidence", "package_pins",
        "intervention_points_present", "policy_yaml_path", "deny_path_present",
        "audit_fields_in_verifier_json", "ci_action_pinned",
        "evidence_globs_scanned",
    }
    assert required_keys.issubset(result.keys())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/ricchi/.copilot/repos/copilot-worktrees/awesome-gbb/unsafecode-probable-guide && python -m pytest scripts/tests/test_foundry_agt_capability_detector.py -v 2>&1 | tail -20`

Expected: FAIL with `ModuleNotFoundError: No module named 'capability_detector'` (the reference module doesn't exist yet).

### Task 1.2: Implement capability_detector by lifting from threadlight

**Files:**
- Create: `skills/foundry-agt/references/python/__init__.py` (empty marker if missing)
- Create: `skills/foundry-agt/references/python/capability_detector.py`

- [ ] **Step 1: Ensure the `__init__.py` exists**

Run:
```bash
mkdir -p skills/foundry-agt/references/python
test -f skills/foundry-agt/references/python/__init__.py || \
  echo '"""Canonical Python helpers for the foundry-agt skill."""' \
  > skills/foundry-agt/references/python/__init__.py
```

- [ ] **Step 2: Create the canonical reference file header**

Create `skills/foundry-agt/references/python/capability_detector.py` starting with this header (per AGENTS.md §7 validator convention):

```python
"""Canonical foundry-agt capability detector.

Source of truth for the prose example in `../../SKILL.md § Using the canonical capability detector`.

Lifted from threadlight `production_ready.py::_detect_agt_profile()` per issue #248.
Returns a stable dict shape that threadlight's AGT-V4-001..007 findings consume
when `kind: sibling-skill`.

Public API:
    from foundry_agt.capability_detector import detect
    caps = detect(repo_root=".")

The return dict ALWAYS contains every key, even on an empty repo. Never raises.
"""
```

- [ ] **Step 3: Lift the implementation from threadlight**

Append the body of the function. Inspect `/tmp/v060-refs/production_ready.py` from Task 0.1 to find `_detect_agt_profile()`, `V4_DIST_REGEX`, `V4_POLICY_REGEX`, `V4_DYNAMIC_REGEX` and the AGT-V4-001..007 helpers. Lift them verbatim with two adaptations:

1. Rename `_detect_agt_profile(repo_root)` to `detect(repo_root: str = ".") -> dict`. Remove the leading underscore — this is the public API now.
2. Ensure every dict key from the contract in Step 1 above is always present, even if the underlying helper would skip a missing-data branch. Add defensive defaults at the end (e.g. `result.setdefault("audit_fields_in_verifier_json", [])`).

If the threadlight source uses helpers like `_glob_repo` or `_parse_pyproject`, lift those too into the same module as private (leading-underscore) helpers.

Example shape (your actual lift will be larger):

```python
import re
from pathlib import Path
from typing import Any

V4_DIST_REGEX = re.compile(r"foundry-agt\s*[=~><]+\s*4")  # confirm against source
V4_POLICY_REGEX = re.compile(r"V4_POLICY_REGEX")
V4_DYNAMIC_REGEX = re.compile(r"V4_DYNAMIC_REGEX")


def detect(repo_root: str = ".") -> dict[str, Any]:
    root = Path(repo_root)
    result: dict[str, Any] = {
        "version_detected": None,
        "detection_confidence": 0.0,
        "package_pins": {},
        "intervention_points_present": False,
        "policy_yaml_path": None,
        "deny_path_present": False,
        "audit_fields_in_verifier_json": [],
        "ci_action_pinned": False,
        "evidence_globs_scanned": [],
    }
    # ... lift detection passes from threadlight here ...
    return result
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/ricchi/.copilot/repos/copilot-worktrees/awesome-gbb/unsafecode-probable-guide && python -m pytest scripts/tests/test_foundry_agt_capability_detector.py -v 2>&1 | tail -20`

Expected: 5 tests PASS. If any fails, inspect the threadlight source for behavioural differences and adjust either the test (if the threadlight contract is more nuanced than your test asserts) or the implementation (if the lift missed a branch).

- [ ] **Step 5: Commit the helper + tests**

Run:
```bash
git add skills/foundry-agt/references/python/ scripts/tests/test_foundry_agt_capability_detector.py
git commit -m "foundry-agt: add canonical capability detector helper

Lifts threadlight production_ready.py::_detect_agt_profile + AGT-V4-001..007
regexes into a public detect() helper. Closes #248.

Source of truth: skills/foundry-agt/references/python/capability_detector.py
SKILL.md cross-link section follows in next commit.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.3: Add the SKILL.md cross-link section

**Files:**
- Modify: `skills/foundry-agt/SKILL.md`

- [ ] **Step 1: Read the existing SKILL.md structure**

Run: `grep -nE "^## |^### " skills/foundry-agt/SKILL.md | head -40`

Note the section before which the new section should live. Suggested placement: after the main "How the skill works" section and before "See also" / "Roadmap" / "Cross-references".

- [ ] **Step 2: Add the new section**

Open `skills/foundry-agt/SKILL.md` and insert this section in the determined location:

```markdown
## Using the canonical capability detector

When you need a programmatic read of the host repo's AGT posture
(version pinned, intervention points present, policy YAML discovered,
audit fields in the verifier JSON, CI action SHA-pinned), call the
canonical helper:

```python
from foundry_agt.capability_detector import detect

caps = detect(repo_root=".")
# caps["version_detected"]               → str | None
# caps["detection_confidence"]           → 0.0..1.0
# caps["package_pins"]                   → dict[str, str]
# caps["intervention_points_present"]    → bool
# caps["policy_yaml_path"]               → str | None
# caps["deny_path_present"]              → bool
# caps["audit_fields_in_verifier_json"]  → list[str]
# caps["ci_action_pinned"]               → bool
# caps["evidence_globs_scanned"]         → list[str]
```

> **MUST:** Copy verbatim from
> [`references/python/capability_detector.py`](references/python/capability_detector.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
> That file is the canonical lift of threadlight's
> `_detect_agt_profile()` + AGT-V4-001..007 regexes. Maps directly to
> the threadlight `kind: sibling-skill` contract.

The return dict ALWAYS contains every key listed above. The helper
NEVER raises — on filesystem errors or partial data, it returns the
default shape with `detection_confidence: 0.0`.
```

- [ ] **Step 3: Bump the SKILL.md MINOR version**

Run: `grep -n "version:" skills/foundry-agt/SKILL.md | head -3`

Note the current `metadata.version` value (e.g. `"4.1.0"`). Bump MINOR (e.g. → `"4.2.0"`) per AGENTS.md §5 (new documented section + new public capability).

- [ ] **Step 4: Run lint locally**

Run: `python scripts/validate-skills.py 2>&1 | tail -30`

Expected: PASS with no errors. If the validator complains about a missing `§ Using the canonical capability detector` cross-link in the reference file header, edit the header to match the section title exactly (AGENTS.md §7 validator check #2).

- [ ] **Step 5: Commit the SKILL.md change**

Run:
```bash
git add skills/foundry-agt/SKILL.md
git commit -m "foundry-agt: document canonical capability detector helper

Adds SKILL.md section cross-linking to references/python/capability_detector.py.
Bumps metadata.version MINOR for the new documented capability.

Refs #248.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — Issue #245: foundry-observability KQL probe helpers

### Task 2.1: Write the failing test file

**Files:**
- Create: `scripts/tests/test_foundry_observability_kql_probes.py`

- [ ] **Step 1: Write the failing test**

Create the file:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/ricchi/.copilot/repos/copilot-worktrees/awesome-gbb/unsafecode-probable-guide && python -m pytest scripts/tests/test_foundry_observability_kql_probes.py -v 2>&1 | tail -20`

Expected: FAIL with `ModuleNotFoundError: No module named 'kql_probes'`.

### Task 2.2: Implement kql_probes.py (sync variants)

**Files:**
- Create: `skills/foundry-observability/references/python/__init__.py` (if missing)
- Create: `skills/foundry-observability/references/python/kql_probes.py`

- [ ] **Step 1: Ensure `__init__.py` exists**

Run:
```bash
mkdir -p skills/foundry-observability/references/python
test -f skills/foundry-observability/references/python/__init__.py || \
  echo '"""Canonical Python helpers for the foundry-observability skill."""' \
  > skills/foundry-observability/references/python/__init__.py
```

- [ ] **Step 2: Create the sync KQL probes module**

Create `skills/foundry-observability/references/python/kql_probes.py` with this header:

```python
"""Canonical foundry-observability KQL probe helpers (sync variants).

Source of truth for the prose example in `../../SKILL.md § Reusable KQL probe helpers`.

Lifted from threadlight `production_ready.py::_kql_*` helpers per issue #245.
Returns a stable dict shape that threadlight's cross-cutting telemetry
findings consume when `kind: sibling-skill`.

Public API (5 sync helpers, all same signature):
    from foundry_observability.kql_probes import trace_freshness
    result = trace_freshness(workspace_id="...", app_name="...", since="1h", credential=None)

Returns:
    {"result": <typed primitive>, "confidence": 0.0..1.0,
     "last_probe_at": "ISO8601", "error": str | None}

Never raises. Catches every exception, returns error key with reason.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
```

- [ ] **Step 3: Lift the 5 helpers from threadlight**

Inspect `/tmp/v060-refs/production_ready.py` for `_kql_trace_freshness`, `_kql_exception_rate`, `_kql_rai_denials`, `_kql_agt_denials`, `_kql_rate_limit_events`. Lift each verbatim with these adaptations:

1. Drop the leading underscore — these are public now.
2. Standardize the signature: `def <name>(workspace_id: str, app_name: str, *, since: str = "1h", credential: Any = None) -> dict`.
3. Wrap each helper's body in `try / except Exception as exc:` returning `{"result": None, "confidence": 0.0, "last_probe_at": _now_iso(), "error": str(exc)}`.
4. If `credential is None`, default to `DefaultAzureCredential()`.

Template for one helper (apply pattern to all 5):

```python
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trace_freshness(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    """Minutes since the most recent OTel trace for app_name."""
    if credential is None:
        credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)
    try:
        query = f"""
AppTraces
| where AppRoleName == '{app_name}'
| summarize last_seen = max(TimeGenerated)
| extend minutes_since = datetime_diff('minute', now(), last_seen)
| project minutes_since
""".strip()
        response = client.query_workspace(workspace_id=workspace_id,
                                          query=query,
                                          timespan=timedelta(hours=24))
        if response.status == LogsQueryStatus.PARTIAL:
            confidence = 0.5
        else:
            confidence = 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:  # never raises
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
```

Repeat for the other 4 helpers, lifting each one's KQL query from threadlight. Names: `exception_rate`, `rai_denials`, `agt_denials`, `rate_limit_events`.

- [ ] **Step 4: Run the sync tests to verify they pass**

Run: `python -m pytest scripts/tests/test_foundry_observability_kql_probes.py -v -k "not async_variants" 2>&1 | tail -30`

Expected: 11 PASS (5 from `test_every_probe_returns_required_keys` × parametrize + 5 from never-raises × parametrize + 1 sanity test). The async test will still fail until Task 2.3.

### Task 2.3: Add the async variants module

**Files:**
- Create: `skills/foundry-observability/references/python/kql_probes_aio.py`

- [ ] **Step 1: Create the async module**

Create `skills/foundry-observability/references/python/kql_probes_aio.py`:

```python
"""Canonical foundry-observability KQL probe helpers (async variants).

Source of truth for the prose example in `../../SKILL.md § Reusable KQL probe helpers`.

Mirror of kql_probes.py with `async def` signatures and aio clients.
Same return shape; same never-raises contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from azure.identity.aio import DefaultAzureCredential
from azure.monitor.query.aio import LogsQueryClient
from azure.monitor.query import LogsQueryStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def trace_freshness(
    workspace_id: str,
    app_name: str,
    *,
    since: str = "1h",
    credential: Any = None,
) -> dict[str, Any]:
    if credential is None:
        credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)
    try:
        query = f"""
AppTraces
| where AppRoleName == '{app_name}'
| summarize last_seen = max(TimeGenerated)
| extend minutes_since = datetime_diff('minute', now(), last_seen)
| project minutes_since
""".strip()
        response = await client.query_workspace(
            workspace_id=workspace_id,
            query=query,
            timespan=timedelta(hours=24),
        )
        confidence = 0.5 if response.status == LogsQueryStatus.PARTIAL else 1.0
        rows = response.tables[0].rows if response.tables else []
        result = int(rows[0][0]) if rows and rows[0][0] is not None else None
        return {"result": result, "confidence": confidence,
                "last_probe_at": _now_iso(), "error": None}
    except Exception as exc:
        return {"result": None, "confidence": 0.0,
                "last_probe_at": _now_iso(), "error": str(exc)}
    finally:
        try:
            await client.close()
        except Exception:
            pass


# Mirror the other 4 sync helpers with async def signatures and the same
# KQL queries. Names: exception_rate, rai_denials, agt_denials, rate_limit_events.
```

Repeat the async template for the remaining 4 helpers, copying the KQL query strings from `kql_probes.py` so query text stays in sync between sync and async variants.

- [ ] **Step 2: Run the full test file**

Run: `python -m pytest scripts/tests/test_foundry_observability_kql_probes.py -v 2>&1 | tail -30`

Expected: ALL tests PASS, including `test_async_variants_have_same_signature`.

- [ ] **Step 3: Commit the helpers + tests**

```bash
git add skills/foundry-observability/references/python/ \
        scripts/tests/test_foundry_observability_kql_probes.py
git commit -m "foundry-observability: add reusable KQL probe helpers (sync + async)

Five canonical probes lifted from threadlight production_ready.py per #245:
trace_freshness, exception_rate, rai_denials, agt_denials, rate_limit_events.

Each helper returns {result, confidence, last_probe_at, error}; never raises.
Sync variants in kql_probes.py; async variants in kql_probes_aio.py.

SKILL.md cross-link section follows in next commit.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.4: Update SKILL.md + upstream-pin

**Files:**
- Modify: `skills/foundry-observability/SKILL.md`
- Modify: `skills/foundry-observability/references/upstream-pin.md`

- [ ] **Step 1: Add the SKILL.md cross-link section**

Run: `grep -nE "^## |^### " skills/foundry-observability/SKILL.md | head -40`

Pick a placement (suggested: after the main "Logging + KQL patterns" section if present, otherwise after "How the skill works"). Insert:

```markdown
## Reusable KQL probe helpers

When you need a programmatic read of OTel telemetry health for a Foundry
workload (trace freshness, exception rate, RAI denials, AGT denials, rate
limit events), call the canonical helpers:

```python
from foundry_observability.kql_probes import (
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
)

result = trace_freshness(workspace_id="<law-workspace-id>",
                          app_name="my-agent", since="1h")
# result["result"]         → int minutes (None on error)
# result["confidence"]     → 0.0..1.0
# result["last_probe_at"]  → ISO8601 UTC
# result["error"]          → None on success, str on failure
```

For async callers (FastAPI, Quart, etc.) use the mirrored aio module:

```python
from foundry_observability.kql_probes_aio import trace_freshness
result = await trace_freshness(workspace_id=..., app_name=...)
```

| Helper | Returns | Notes |
|---|---|---|
| `trace_freshness` | minutes since last OTel trace | int |
| `exception_rate` | exceptions / minute over window | float |
| `rai_denials` | RAI denial event count | int |
| `agt_denials` | AGT deny-list trip count | int |
| `rate_limit_events` | 429 + throttle event count | int |

> **MUST:** Copy verbatim from
> [`references/python/kql_probes.py`](references/python/kql_probes.py) and
> [`references/python/kql_probes_aio.py`](references/python/kql_probes_aio.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

Every helper NEVER raises. On any exception (auth failure, KQL syntax
error, transient outage) the helper returns `{result: None, confidence: 0.0,
error: "<reason>"}`.
```

- [ ] **Step 2: Bump SKILL.md MINOR**

Run: `grep -n "version:" skills/foundry-observability/SKILL.md | head -3`

Note current value, bump MINOR (e.g. `"3.5.0"` → `"3.6.0"`).

- [ ] **Step 3: Inspect the upstream pin**

Run: `grep -n "azure-monitor-query\|azure-identity" skills/foundry-observability/references/upstream-pin.md`

If `azure-monitor-query` is already in `packages[]`, no action. If not, add it under `packages:`:

```yaml
packages:
  - name: azure-monitor-query
    version: "~=1.4.0"  # confirm latest stable at impl time via PyPI
    purpose: KQL probe helpers (sync + async variants for trace_freshness, exception_rate, rai_denials, agt_denials, rate_limit_events)
```

If you add a package, bump the pin file's `last_validated` to today's date and bump the SKILL.md MINOR a second time only if the version was already bumped without this change — generally one MINOR bump for the whole task is fine.

- [ ] **Step 4: Run lint locally**

Run: `python scripts/validate-skills.py 2>&1 | tail -30`

Expected: PASS.

- [ ] **Step 5: Commit the SKILL.md + pin update**

```bash
git add skills/foundry-observability/SKILL.md \
        skills/foundry-observability/references/upstream-pin.md
git commit -m "foundry-observability: document KQL probe helpers + pin update

Adds SKILL.md section cross-linking kql_probes.py and kql_probes_aio.py.
Updates upstream-pin.md packages[] with azure-monitor-query if missing.
Bumps metadata.version MINOR.

Refs #245.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Issue #247: foundry-evals last-run introspection

### Task 3.1: Write the failing test file

**Files:**
- Create: `scripts/tests/test_foundry_evals_last_run.py`

- [ ] **Step 1: Write the failing test**

Create the file:

```python
"""Unit tests for the foundry-evals last-run introspection helper.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/247
Implements the threadlight EVAL-201 self-verify path.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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


def test_empty_evals_dir_returns_none(tmp_path: Path) -> None:
    """No runs ever → returns None."""
    (tmp_path / "evals").mkdir()
    result = last_run_summary(evals_dir=str(tmp_path / "evals"))
    assert result is None


def test_single_green_run(tmp_path: Path) -> None:
    """One green run → all scenarios passed, no breaches."""
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
    assert result is not None
    assert result["scenarios_total"] == 2
    assert result["scenarios_passed"] == 2
    assert result["scenarios_failed"] == 0
    assert result["threshold_breaches"] == []
    assert result["stale"] is False
    assert result["confidence"] > 0.5
    assert result["run_id"] == "r001"


def test_red_run_reports_breaches(tmp_path: Path) -> None:
    """Mixed run → failed scenarios appear in threshold_breaches."""
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
    assert result is not None
    assert result["scenarios_failed"] == 1
    assert len(result["threshold_breaches"]) >= 1
    assert any("s2" in b for b in result["threshold_breaches"])


def test_stale_run_flagged(tmp_path: Path) -> None:
    """Run older than 7 days → stale: True."""
    evals = tmp_path / "evals"
    evals.mkdir()
    _write_run(
        evals,
        ran_at=datetime.now(timezone.utc) - timedelta(days=10),
        run_id="r003",
        scenarios=[{"name": "s1", "passed": True, "latency_ms": 100}],
    )
    result = last_run_summary(evals_dir=str(evals))
    assert result is not None
    assert result["stale"] is True


def test_latency_percentiles_computed(tmp_path: Path) -> None:
    """p50 + p95 latency are computed when at least 2 scenarios exist."""
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
    assert result is not None
    assert result["p50_latency_ms"] is not None
    assert result["p95_latency_ms"] is not None
    assert result["p95_latency_ms"] >= result["p50_latency_ms"]


def test_required_keys_present_on_red_run(tmp_path: Path) -> None:
    """Every documented dict key is present when a run exists."""
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
    assert required.issubset(result.keys())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest scripts/tests/test_foundry_evals_last_run.py -v 2>&1 | tail -20`

Expected: FAIL with `ModuleNotFoundError: No module named 'last_run'`.

### Task 3.2: Implement last_run.py

**Files:**
- Create: `skills/foundry-evals/references/python/__init__.py` (if missing)
- Create: `skills/foundry-evals/references/python/last_run.py`

- [ ] **Step 1: Ensure `__init__.py` exists**

Run:
```bash
mkdir -p skills/foundry-evals/references/python
test -f skills/foundry-evals/references/python/__init__.py || \
  echo '"""Canonical Python helpers for the foundry-evals skill."""' \
  > skills/foundry-evals/references/python/__init__.py
```

- [ ] **Step 2: Create last_run.py with the header + lift**

Create `skills/foundry-evals/references/python/last_run.py`:

```python
"""Canonical foundry-evals last-run introspection helper.

Source of truth for the prose example in `../../SKILL.md § Programmatic last-run introspection`.

Lifted from threadlight `production_ready.py::_foundry_evals_last_run()` per issue #247.
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
            ran_at = datetime.fromisoformat(data["ran_at"])
            manifests.append((ran_at, manifest_path, data))
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
        # Spec section 9 threshold cross-checks (optional)
        if spec_section_9 is not None:
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
```

> **NOTE:** This is a "best effort lift" starting point. Inspect
> `/tmp/v060-refs/production_ready.py::_foundry_evals_last_run` from Task
> 0.1 and reconcile — if threadlight's helper uses a different manifest
> layout (e.g. `summary.json` instead of `manifest.json`, or a different
> latency field name), align the lift to match threadlight's source so
> the dispatch contract holds.

- [ ] **Step 3: Run the tests to verify they pass**

Run: `python -m pytest scripts/tests/test_foundry_evals_last_run.py -v 2>&1 | tail -20`

Expected: 6 PASS. If the lift used a different manifest layout than the test, either: (a) update the tests' `_write_run` helper to match the lift, or (b) update the lift to match threadlight's actual layout — pick whichever keeps parity with threadlight source.

- [ ] **Step 4: Commit helper + tests**

```bash
git add skills/foundry-evals/references/python/ \
        scripts/tests/test_foundry_evals_last_run.py
git commit -m "foundry-evals: add last-run introspection helper

Lifts threadlight production_ready.py::_foundry_evals_last_run per #247.
Returns None if no run exists, otherwise a dict with scenarios_total/passed/
failed, threshold_breaches, p50/p95 latency, confidence, stale flag.

SKILL.md cross-link section follows in next commit.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.3: Add the SKILL.md cross-link section

**Files:**
- Modify: `skills/foundry-evals/SKILL.md`

- [ ] **Step 1: Find the insertion point**

Run: `grep -nE "^## |^### " skills/foundry-evals/SKILL.md | head -50`

Pick a section near existing "After a run" / "Reading results" content if present, otherwise add a new top-level section near the end before "See also".

- [ ] **Step 2: Insert the section**

```markdown
## Programmatic last-run introspection

When you need a machine-readable summary of the most recent eval run
(scenarios total/passed/failed, threshold breaches, p50/p95 latency,
stale flag), call the canonical helper:

```python
from foundry_evals.last_run import last_run_summary

summary = last_run_summary(evals_dir="evals/", spec_section_9=spec_data)
if summary is None:
    print("No eval has ever run.")
else:
    print(f"Run {summary['run_id']} at {summary['ran_at']}: "
          f"{summary['scenarios_passed']}/{summary['scenarios_total']} passed")
    if summary["stale"]:
        print(f"⚠ Run is stale (> 7 days old)")
    for breach in summary["threshold_breaches"]:
        print(f"  - {breach}")
```

The return dict (when not `None`) always contains: `ran_at`, `run_id`,
`scenarios_total`, `scenarios_passed`, `scenarios_failed`,
`threshold_breaches`, `p50_latency_ms`, `p95_latency_ms`,
`confidence`, `stale`, `source`.

The `spec_section_9` parameter is optional — if provided, it should be
a dict with thresholds (e.g. `{"latency_budget_ms": 1500}`) that the
helper cross-checks against each scenario.

> **MUST:** Copy verbatim from
> [`references/python/last_run.py`](references/python/last_run.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.
```

- [ ] **Step 3: Bump SKILL.md MINOR**

Run: `grep -n "version:" skills/foundry-evals/SKILL.md | head -3`

Note current, bump MINOR.

- [ ] **Step 4: Lint**

Run: `python scripts/validate-skills.py 2>&1 | tail -20`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-evals/SKILL.md
git commit -m "foundry-evals: document last-run introspection helper

Adds SKILL.md section cross-linking references/python/last_run.py.
Bumps metadata.version MINOR.

Refs #247.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 4 — Catalog wrap-up

### Task 4.1: Bump plugin.json + marketplace.json

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Read current versions**

Run: `grep -E '"version"' plugin.json .github/plugin/marketplace.json`

Expected: both show the same version (e.g. `"4.15.0"`).

- [ ] **Step 2: Bump PATCH in both**

Edit each file: bump the patch component (e.g. `4.15.0` → `4.15.1`). PATCH bump is correct per AGENTS.md §5.1 — no new skills added, only SKILL.md content additions.

- [ ] **Step 3: Verify build-plugins check**

Run: `python scripts/build-plugins.py --check 2>&1 | tail -10`

Expected: PASS, both manifests aligned.

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "plugin: PATCH bump for v0.6.0 Slice A helpers

Three SKILL.md MINOR bumps (foundry-agt, foundry-observability,
foundry-evals) for canonical Python helper additions. No new skills.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4.2: Rebuild the docs site

**Files:**
- Modify: `docs/` (generated artifacts)

- [ ] **Step 1: Run the site build**

Run: `python3 scripts/build-site.py --out docs/ 2>&1 | tail -20`

Expected: build completes, several `docs/skills/foundry-*/index.html` files updated.

- [ ] **Step 2: Inspect git status for the generated diff**

Run: `git status docs/ | head -20`

Expected: at least 3 SKILL.md-derived HTML pages updated (`foundry-agt`, `foundry-observability`, `foundry-evals`).

- [ ] **Step 3: Commit the generated docs**

```bash
git add docs/
git commit -m "docs: rebuild static site for Slice A helpers

Generated by scripts/build-site.py. Updates foundry-agt,
foundry-observability, and foundry-evals SKILL.md-derived pages.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4.3: Final lint sweep

- [ ] **Step 1: Run the full validator**

Run: `python scripts/validate-skills.py 2>&1 | tail -30`

Expected: PASS across all 27 skills.

- [ ] **Step 2: Run the full pytest unit suite for the three test files**

Run:
```bash
python -m pytest \
  scripts/tests/test_foundry_agt_capability_detector.py \
  scripts/tests/test_foundry_observability_kql_probes.py \
  scripts/tests/test_foundry_evals_last_run.py \
  -v 2>&1 | tail -40
```

Expected: all tests PASS (5 + 12 + 6 = 23 tests).

- [ ] **Step 3: If any check fails, fix inline and amend the last commit**

Use `git commit --amend --no-edit` to fold fixes into the prior commit. Re-run validate-skills + pytest. Don't push until both are green.

### Task 4.4: Push the branch and prepare PR description

- [ ] **Step 1: Verify branch state**

Run:
```bash
git log --oneline origin/main..HEAD
git status
```

Expected: ~8 commits, clean tree.

- [ ] **Step 2: Push the branch**

Run: `git push -u origin unsafecode/v060-upstream-planning`

Or whatever execution branch the executor is on (the planning branch will be different from the execution branch in practice; the planning branch only carries this plan + the spec).

- [ ] **Step 3: Draft the PR body**

Title: `Slice A: foundry-agt + foundry-observability + foundry-evals helpers (#248 #245 #247)`

Body skeleton:

```markdown
**Closes:** #248 #245 #247
**Unblocks:** aiappsgbb/threadlight-skills v0.5.1 flip release (7+ findings)
**Spec:** docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md (§4.1)
**Plan:** docs/superpowers/plans/2026-06-11-v060-slice-a-hidden-multipliers.md

## What changes

- **foundry-agt** — new `references/python/capability_detector.py` lifted
  from threadlight `_detect_agt_profile`. SKILL.md cross-links the helper.
  MINOR bump.
- **foundry-observability** — new `references/python/kql_probes.py` (sync)
  + `kql_probes_aio.py` (async) lifted from threadlight `_kql_*` helpers.
  SKILL.md cross-links both. Pin updated for `azure-monitor-query`. MINOR bump.
- **foundry-evals** — new `references/python/last_run.py` lifted from
  threadlight `_foundry_evals_last_run`. SKILL.md cross-links the helper.
  MINOR bump.
- **plugin.json + marketplace.json** — PATCH bump (no new skills).

## Test plan

- 23 pytest unit tests across the three new test files, all green locally.
- `python scripts/validate-skills.py` PASS.
- `python scripts/build-plugins.py --check` PASS.
- `python scripts/build-site.py --out docs/` rebuilds; generated diff
  committed.

## Multi-skill tag

This PR touches 3 skills; commit message body includes `[multi-skill]`
per AGENTS.md §10.3.

## Live Azure testing (AGENTS.md §2.9)

These are pure-Python helpers with no Azure deploy dependency. The KQL
probes accept a `credential` parameter and target an Azure Log Analytics
workspace at call time — they are validated by mocked-client unit tests
in this PR and will be exercised live in threadlight's v0.5.1 self-verify
run after merge. No new E2E pytest required per §2.8 (these helpers
don't ship new Azure-connecting code; they wrap existing SDK clients).
```

Commit the PR body draft into the session-state artifacts dir if helpful:
```bash
mkdir -p /Users/ricchi/.copilot/session-state/<session-id>/files/pr-drafts
# write the body to slice-a.md, do not commit
```

- [ ] **Step 4: STOP and hand back to the human**

Per the planning task framing, **do not open the PR yourself**. Surface
the PR body draft, the commit list, the test summary, and let the human
review + open. After human approval, follow the standard merge protocol.

---

## Self-Review checklist

After completing all phases:

- [ ] All 23 pytest tests pass locally.
- [ ] `validate-skills.py` PASS.
- [ ] `build-plugins.py --check` PASS.
- [ ] Three SKILL.md MINOR bumps (one per host).
- [ ] One `plugin.json` PATCH bump matched in `marketplace.json`.
- [ ] One docs/ rebuild commit.
- [ ] Commit message body for the SKILL.md updates includes `[multi-skill]` tag.
- [ ] Threadlight reference URLs are preserved in each helper's docstring header.
- [ ] No identifier leaks in tracked files (placeholders only).
- [ ] AGENTS.md §12.5 stats unchanged (no new skills added in Slice A).

---

## Done criteria

Slice A is "done" when:
1. PR merged to `main`.
2. CI green on `skill-validation.yml`, `automation-pr-gate.yml`, `pin-validation.yml` (if foundry-observability pin changed), and `skill-test.yml` import smoke for the three host skills.
3. Threadlight is unblocked to open its v0.5.1 flip PR for the 7+ findings.

Slice B begins after Slice A merges (or in parallel if the executor has bandwidth and wants to test the multi-PR review cadence).

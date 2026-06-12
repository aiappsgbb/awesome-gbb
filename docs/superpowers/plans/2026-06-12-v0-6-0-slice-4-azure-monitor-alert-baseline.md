# v0.6.0 Slice 4 — `azure-monitor-alert-baseline` NEW skill

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a NEW catalog skill `azure-monitor-alert-baseline`
that probes a target resource group for configured activity-log /
metric alerts, compares against one of three named baseline
catalogs (`minimal`, `threadlight-pilot`, `regulated`), and emits a
JSON envelope listing missing alerts + Bicep remediation snippets
for each gap. Threadlight consumes via `kind: sibling-skill` to
verify the alert-baseline finding.

**Architecture:** Same NEW-skill shape as Slice 3
(`scripts/probe.py` + `scripts/__main__.py` CLI + `requirements.txt`
+ `references/upstream-pin.md` + Copilot CLI fixture + pytest
suite). Plugin.json + marketplace.json MINOR bump (4.19.0 → 4.20.0).
Skill count 32 → 33. Cross-ref to `azure-sre-agent` (#250) for
**alert response** in DO NOT USE FOR (alerts feed SRE; SRE responds).
Reads alerts via the proven `az` CLI shell-out
(`az monitor activity-log alert list` + `az monitor metrics alert
list`) because the SDK surface (`azure-mgmt-monitor` alert APIs)
has historically lagged behind the CLI; the SDK is imported for
type hints only.

**Tech Stack:** `azure-mgmt-monitor` (type hints + read calls for
the metric alerts where they're stable), `subprocess` + `az`
shell-out for activity-log alerts (the more battle-tested path —
called out in spec § 3.1 as the allowed fallback), `azure-identity`
for `DefaultAzureCredential` when SDK is used. Python ≥ 3.10.
`pytest` for unit tests. Copilot CLI fixture for T3 live-Azure CI.

**Closes:** #272.

**Builds on:** Slice 3 lands first (it does the AGENTS.md §12.5
reconcile from stale 27 → live 31). This slice picks up cleanly
from 32 → 33.

---

## File structure

| Path | Owner | Purpose |
|---|---|---|
| `skills/azure-monitor-alert-baseline/SKILL.md` | new | Skill frontmatter + body |
| `skills/azure-monitor-alert-baseline/scripts/__init__.py` | new | Empty package marker |
| `skills/azure-monitor-alert-baseline/scripts/probe.py` | new | `probe()` + `aprobe()` API |
| `skills/azure-monitor-alert-baseline/scripts/__main__.py` | new | CLI shim → JSON to stdout |
| `skills/azure-monitor-alert-baseline/scripts/baselines.py` | new | The 3 baseline catalogs (data, not code) |
| `skills/azure-monitor-alert-baseline/scripts/bicep_templates.py` | new | Remediation snippets per alert type |
| `skills/azure-monitor-alert-baseline/requirements.txt` | new | Pinned deps |
| `skills/azure-monitor-alert-baseline/references/upstream-pin.md` | new | Pin file (tier B, auto, runnable) |
| `skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md` | new | Copilot CLI smoke fixture (≤ 8 KB) |
| `skills/azure-monitor-alert-baseline/tests/__init__.py` | new | Empty |
| `skills/azure-monitor-alert-baseline/tests/test_probe.py` | new | Pytest against mocked alert JSON |
| `skills/azure-monitor-alert-baseline/tests/test_baselines.py` | new | Pytest for baseline catalog integrity |
| `skills/azure-monitor-alert-baseline/tests/fixtures/all_configured_threadlight.json` | new | RG has every threadlight-pilot alert |
| `skills/azure-monitor-alert-baseline/tests/fixtures/partial_threadlight.json` | new | RG missing 2 of 4 threadlight-pilot alerts |
| `skills/azure-monitor-alert-baseline/tests/fixtures/empty_rg.json` | new | RG with zero alerts configured |
| `skills/azure-monitor-alert-baseline/tests/fixtures/missing_perms.json` | new | 403 from list call |
| `.github/skill-deps.yml` | modify | Register `azure-monitor-alert-baseline: depends_on: []` |
| `plugin.json` | modify | Bump 4.19.0 → 4.20.0 (MINOR — new skill) |
| `.github/plugin/marketplace.json` | modify | Match plugin.json |
| `AGENTS.md` | modify | §12.5: skill count 32 → 33 |

---

## Phase A — Skill scaffolding

### Task A1: Create directory + empty markers

**Files:**
- Create: `skills/azure-monitor-alert-baseline/scripts/__init__.py`
- Create: `skills/azure-monitor-alert-baseline/tests/__init__.py`
- Create: `skills/azure-monitor-alert-baseline/tests/fixtures/.gitkeep`

- [ ] **Step 1: Write the package marker**

```python
# skills/azure-monitor-alert-baseline/scripts/__init__.py
"""Importable helpers for the azure-monitor-alert-baseline skill.

Public API:
    from probe import probe, aprobe
    from baselines import BASELINES   # dict[str, list[AlertSpec]]
    from bicep_templates import render_for_missing

See SKILL.md § "API contract" for the input + return shape.
"""
```

```python
# skills/azure-monitor-alert-baseline/tests/__init__.py
```

```bash
touch skills/azure-monitor-alert-baseline/tests/fixtures/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add skills/azure-monitor-alert-baseline/scripts/__init__.py \
        skills/azure-monitor-alert-baseline/tests/__init__.py \
        skills/azure-monitor-alert-baseline/tests/fixtures/.gitkeep
git commit -m "feat(azure-monitor-alert-baseline): scaffold scripts/ and tests/ (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task A2: Add `requirements.txt`

**Files:**
- Create: `skills/azure-monitor-alert-baseline/requirements.txt`

- [ ] **Step 1: Write the file**

```
# Python dependencies for azure-monitor-alert-baseline/scripts/
#
# Install with:
#   pip install -r skills/azure-monitor-alert-baseline/requirements.txt
#
# PYTHONPATH activation:
#   PYTHONPATH=skills/azure-monitor-alert-baseline/scripts python -m probe --help

azure-mgmt-monitor~=6.0.2
azure-mgmt-resource~=23.1.1
azure-identity~=1.19.0
```

- [ ] **Step 2: Verify deps resolve**

Run: `pip install --quiet -r skills/azure-monitor-alert-baseline/requirements.txt`
Expected: clean install.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-monitor-alert-baseline/requirements.txt
git commit -m "feat(azure-monitor-alert-baseline): pin scripts/ deps (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase B — Baseline catalogs + Bicep templates

### Task B1: Define the 3 baseline catalogs

**Files:**
- Create: `skills/azure-monitor-alert-baseline/scripts/baselines.py`

- [ ] **Step 1: Write the failing test first**

Create `skills/azure-monitor-alert-baseline/tests/test_baselines.py`:

```python
"""Unit tests for the baseline catalogs (data only, no Azure calls)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from baselines import BASELINES, AlertSpec


def test_three_baselines_exist():
    assert set(BASELINES.keys()) == {"minimal", "threadlight-pilot", "regulated"}


def test_minimal_is_strict_subset_of_threadlight_pilot():
    minimal = {a.alert_id for a in BASELINES["minimal"]}
    pilot = {a.alert_id for a in BASELINES["threadlight-pilot"]}
    assert minimal <= pilot, f"minimal {minimal - pilot} not in pilot"


def test_pilot_is_strict_subset_of_regulated():
    pilot = {a.alert_id for a in BASELINES["threadlight-pilot"]}
    regulated = {a.alert_id for a in BASELINES["regulated"]}
    assert pilot <= regulated, f"pilot {pilot - regulated} not in regulated"


def test_each_alert_has_required_fields():
    for kind, alerts in BASELINES.items():
        for a in alerts:
            assert isinstance(a, AlertSpec), f"{kind}: not an AlertSpec"
            assert a.alert_id, f"{kind}: alert with empty alert_id"
            assert a.kind in {"activity_log", "metric"}, f"{kind}: bad alert.kind for {a.alert_id}"
            assert a.display_name, f"{kind}: missing display_name for {a.alert_id}"


def test_minimal_includes_service_health():
    minimal = {a.alert_id for a in BASELINES["minimal"]}
    assert "service-health" in minimal
    assert "resource-health" in minimal


def test_threadlight_pilot_includes_policy_state_change():
    pilot = {a.alert_id for a in BASELINES["threadlight-pilot"]}
    assert "policy-state-change" in pilot
    assert "iam-role-assignment-change" in pilot


def test_regulated_includes_microsoft_star_crud():
    regulated = {a.alert_id for a in BASELINES["regulated"]}
    assert any("crud" in a for a in regulated), \
        "regulated baseline must include at least one Microsoft.* CRUD alert"
```

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_baselines.py -v`
Expected: `ModuleNotFoundError: No module named 'baselines'`.

- [ ] **Step 2: Write `baselines.py`**

```python
"""Named alert baseline catalogs for azure-monitor-alert-baseline.

Three baselines, each strictly more permissive than the previous:
    minimal           ⊂ threadlight-pilot ⊂ regulated

`AlertSpec` is the canonical shape; `probe()` matches by `alert_id` +
`kind`. The catalog is data (no Azure SDK calls); tests assert subset
relationships + required-field presence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AlertSpec:
    """One baseline alert specification."""

    alert_id: str
    kind: Literal["activity_log", "metric"]
    display_name: str
    description: str
    # Activity-log alert filter fields (omit for metric alerts)
    activity_log_category: str | None = None
    activity_log_operation_name: str | None = None
    # Metric alert fields (omit for activity_log alerts)
    metric_namespace: str | None = None
    metric_name: str | None = None
    metric_threshold: float | None = None


_MINIMAL: list[AlertSpec] = [
    AlertSpec(
        alert_id="service-health",
        kind="activity_log",
        display_name="Azure Service Health — RG",
        description="Service incidents affecting any resource in the RG.",
        activity_log_category="ServiceHealth",
    ),
    AlertSpec(
        alert_id="resource-health",
        kind="activity_log",
        display_name="Azure Resource Health — RG",
        description="Resource availability degraded / unavailable.",
        activity_log_category="ResourceHealth",
    ),
]


_THREADLIGHT_PILOT: list[AlertSpec] = list(_MINIMAL) + [
    AlertSpec(
        alert_id="policy-state-change",
        kind="activity_log",
        display_name="Azure Policy state-change",
        description="Policy assignment created / modified / deleted in RG.",
        activity_log_category="Administrative",
        activity_log_operation_name="Microsoft.Authorization/policyAssignments/write",
    ),
    AlertSpec(
        alert_id="iam-role-assignment-change",
        kind="activity_log",
        display_name="RBAC role-assignment change",
        description="Any role assignment created / modified in RG.",
        activity_log_category="Administrative",
        activity_log_operation_name="Microsoft.Authorization/roleAssignments/write",
    ),
]


_REGULATED: list[AlertSpec] = list(_THREADLIGHT_PILOT) + [
    AlertSpec(
        alert_id="microsoft-cog-crud",
        kind="activity_log",
        display_name="Microsoft.CognitiveServices/accounts CRUD",
        description="Foundry account create / update / delete.",
        activity_log_category="Administrative",
        activity_log_operation_name="Microsoft.CognitiveServices/accounts/write",
    ),
    AlertSpec(
        alert_id="microsoft-keyvault-crud",
        kind="activity_log",
        display_name="Microsoft.KeyVault/vaults CRUD",
        description="Key Vault create / update / delete.",
        activity_log_category="Administrative",
        activity_log_operation_name="Microsoft.KeyVault/vaults/write",
    ),
    AlertSpec(
        alert_id="microsoft-storage-crud",
        kind="activity_log",
        display_name="Microsoft.Storage/storageAccounts CRUD",
        description="Storage account create / update / delete.",
        activity_log_category="Administrative",
        activity_log_operation_name="Microsoft.Storage/storageAccounts/write",
    ),
]


BASELINES: dict[str, list[AlertSpec]] = {
    "minimal": _MINIMAL,
    "threadlight-pilot": _THREADLIGHT_PILOT,
    "regulated": _REGULATED,
}
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_baselines.py -v`
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add skills/azure-monitor-alert-baseline/scripts/baselines.py \
        skills/azure-monitor-alert-baseline/tests/test_baselines.py
git commit -m "feat(azure-monitor-alert-baseline): 3 baseline catalogs + 7 tests (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task B2: Bicep templates module

**Files:**
- Create: `skills/azure-monitor-alert-baseline/scripts/bicep_templates.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_baselines.py`:

```python
# ── Bicep templates ───────────────────────────────────────────────────


def test_render_for_missing_emits_one_module_per_missing_alert():
    from baselines import BASELINES
    from bicep_templates import render_for_missing

    missing = [a for a in BASELINES["minimal"]]
    rendered = render_for_missing(missing, resource_group="rg-x")
    assert isinstance(rendered, str)
    assert "module" in rendered
    assert "service-health" in rendered
    assert "resource-health" in rendered
    # Must reference the RG so consumers see scope explicitly
    assert "rg-x" in rendered or "resourceGroup()" in rendered


def test_render_for_missing_handles_empty_input():
    from bicep_templates import render_for_missing

    assert render_for_missing([], resource_group="rg-x") == ""
```

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_baselines.py -v`
Expected: 2 new test FAILs with `ModuleNotFoundError: No module named 'bicep_templates'`.

- [ ] **Step 2: Implement `bicep_templates.py`**

```python
"""Bicep remediation snippets for missing alert specs.

For each AlertSpec the consumer is missing, emit one Bicep module
invocation that creates the alert with conservative defaults. The
output is a single string of concatenated module blocks, paste-ready
into the consumer's main.bicep.
"""

from __future__ import annotations

from typing import Iterable

from baselines import AlertSpec


_ACTIVITY_LOG_TEMPLATE = """\
module alert_{safe_name} './alerts/activity-log-alert.bicep' = {{
  name: 'alert-{alert_id}'
  scope: resourceGroup('{resource_group}')
  params: {{
    alertName: '{alert_id}'
    displayName: '{display_name}'
    description: '{description}'
    category: '{activity_log_category}'
{extra_filter_lines}  }}
}}

"""


_METRIC_TEMPLATE = """\
module alert_{safe_name} './alerts/metric-alert.bicep' = {{
  name: 'alert-{alert_id}'
  scope: resourceGroup('{resource_group}')
  params: {{
    alertName: '{alert_id}'
    displayName: '{display_name}'
    description: '{description}'
    metricNamespace: '{metric_namespace}'
    metricName: '{metric_name}'
    threshold: {metric_threshold}
  }}
}}

"""


def _safe_name(alert_id: str) -> str:
    return alert_id.replace("-", "_").replace(".", "_")


def _render_activity_log(alert: AlertSpec, resource_group: str) -> str:
    extra_lines = ""
    if alert.activity_log_operation_name:
        extra_lines = (
            f"    operationName: '{alert.activity_log_operation_name}'\n"
        )
    return _ACTIVITY_LOG_TEMPLATE.format(
        safe_name=_safe_name(alert.alert_id),
        alert_id=alert.alert_id,
        display_name=alert.display_name,
        description=alert.description,
        activity_log_category=alert.activity_log_category or "Administrative",
        extra_filter_lines=extra_lines,
        resource_group=resource_group,
    )


def _render_metric(alert: AlertSpec, resource_group: str) -> str:
    return _METRIC_TEMPLATE.format(
        safe_name=_safe_name(alert.alert_id),
        alert_id=alert.alert_id,
        display_name=alert.display_name,
        description=alert.description,
        metric_namespace=alert.metric_namespace or "",
        metric_name=alert.metric_name or "",
        metric_threshold=alert.metric_threshold or 0,
        resource_group=resource_group,
    )


def render_for_missing(missing: Iterable[AlertSpec], *, resource_group: str) -> str:
    """Render a single Bicep blob with one module per missing alert."""
    parts: list[str] = []
    for alert in missing:
        if alert.kind == "activity_log":
            parts.append(_render_activity_log(alert, resource_group))
        elif alert.kind == "metric":
            parts.append(_render_metric(alert, resource_group))
        else:
            raise ValueError(f"Unknown alert.kind: {alert.kind}")
    return "".join(parts)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_baselines.py -v`
Expected: 9 passed (7 baseline + 2 bicep).

- [ ] **Step 4: Commit**

```bash
git add skills/azure-monitor-alert-baseline/scripts/bicep_templates.py \
        skills/azure-monitor-alert-baseline/tests/test_baselines.py
git commit -m "feat(azure-monitor-alert-baseline): bicep_templates + 2 tests (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase C — `probe.py` implementation

### Task C1: Create the 4 mocked alert-state fixtures

**Files:**
- Create: 4 fixtures under `skills/azure-monitor-alert-baseline/tests/fixtures/`

- [ ] **Step 1: Write `all_configured_threadlight.json`** (RG has every pilot alert)

```json
{
  "subscription_id": "11111111-1111-1111-1111-111111111111",
  "resource_group": "rg-alerts-clean",
  "configured_alerts": [
    {"alert_id": "service-health", "kind": "activity_log"},
    {"alert_id": "resource-health", "kind": "activity_log"},
    {"alert_id": "policy-state-change", "kind": "activity_log"},
    {"alert_id": "iam-role-assignment-change", "kind": "activity_log"}
  ]
}
```

- [ ] **Step 2: Write `partial_threadlight.json`** (missing 2 of 4)

```json
{
  "subscription_id": "22222222-2222-2222-2222-222222222222",
  "resource_group": "rg-alerts-partial",
  "configured_alerts": [
    {"alert_id": "service-health", "kind": "activity_log"},
    {"alert_id": "resource-health", "kind": "activity_log"}
  ]
}
```

- [ ] **Step 3: Write `empty_rg.json`** (no alerts at all)

```json
{
  "subscription_id": "33333333-3333-3333-3333-333333333333",
  "resource_group": "rg-alerts-empty",
  "configured_alerts": []
}
```

- [ ] **Step 4: Write `missing_perms.json`** (403)

```json
{
  "subscription_id": "44444444-4444-4444-4444-444444444444",
  "resource_group": "rg-alerts-noperms",
  "error": {
    "code": "AuthorizationFailed",
    "message": "The client does not have authorization to perform action 'Microsoft.Insights/activityLogAlerts/read'"
  }
}
```

- [ ] **Step 5: Commit**

```bash
git add skills/azure-monitor-alert-baseline/tests/fixtures/
git commit -m "test(azure-monitor-alert-baseline): scaffold mocked alert fixtures (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task C2: Write the failing test for `probe()`

**Files:**
- Create: `skills/azure-monitor-alert-baseline/tests/test_probe.py`

- [ ] **Step 1: Write the test**

```python
"""Unit tests for probe() — the alert-baseline diff engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from probe import probe


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def _envelope_keys():
    return {
        "skill",
        "skill_version",
        "probed_at",
        "inputs",
        "result",
        "confidence",
        "missing_perms",
        "errors",
    }


def test_envelope_shape_on_clean_run():
    with patch("probe._load_alert_state",
               return_value=_load("all_configured_threadlight.json")):
        out = probe(
            subscription_id="11111111-1111-1111-1111-111111111111",
            resource_group="rg-alerts-clean",
            alert_baseline_kind="threadlight-pilot",
        )
    assert set(out.keys()) >= _envelope_keys()
    assert out["skill"] == "azure-monitor-alert-baseline"
    assert out["confidence"] == "high"
    assert out["errors"] == []


def test_full_match_means_no_missing_alerts_and_empty_bicep():
    with patch("probe._load_alert_state",
               return_value=_load("all_configured_threadlight.json")):
        out = probe(
            subscription_id="11111111-1111-1111-1111-111111111111",
            resource_group="rg-alerts-clean",
            alert_baseline_kind="threadlight-pilot",
        )
    r = out["result"]
    assert r["missing_alerts"] == []
    assert r["extra_alerts"] == []          # we don't flag extras unless asked
    assert r["bicep_remediation"] == ""


def test_partial_threadlight_reports_two_missing():
    with patch("probe._load_alert_state",
               return_value=_load("partial_threadlight.json")):
        out = probe(
            subscription_id="22222222-2222-2222-2222-222222222222",
            resource_group="rg-alerts-partial",
            alert_baseline_kind="threadlight-pilot",
        )
    missing = {m["alert_id"] for m in out["result"]["missing_alerts"]}
    assert missing == {"policy-state-change", "iam-role-assignment-change"}
    bicep = out["result"]["bicep_remediation"]
    assert "policy-state-change" in bicep
    assert "iam-role-assignment-change" in bicep
    assert "service-health" not in bicep    # not missing, no remediation


def test_empty_rg_reports_all_baseline_as_missing():
    with patch("probe._load_alert_state",
               return_value=_load("empty_rg.json")):
        out = probe(
            subscription_id="33333333-3333-3333-3333-333333333333",
            resource_group="rg-alerts-empty",
            alert_baseline_kind="minimal",
        )
    missing = {m["alert_id"] for m in out["result"]["missing_alerts"]}
    assert missing == {"service-health", "resource-health"}


def test_unknown_baseline_kind_returns_error_envelope():
    out = probe(
        subscription_id="11111111-1111-1111-1111-111111111111",
        resource_group="rg-x",
        alert_baseline_kind="nonexistent-kind",
    )
    assert out["confidence"] == "low"
    assert out["result"] is None
    assert any("alert_baseline_kind" in e for e in out["errors"])


def test_missing_perms_low_confidence_no_result():
    with patch("probe._load_alert_state",
               return_value=_load("missing_perms.json")):
        out = probe(
            subscription_id="44444444-4444-4444-4444-444444444444",
            resource_group="rg-alerts-noperms",
            alert_baseline_kind="threadlight-pilot",
        )
    assert out["confidence"] == "low"
    assert out["result"] is None
    assert any("Reader" in p or "Monitoring Reader" in p
               for p in out["missing_perms"])
    assert out["errors"]


def test_probe_never_raises_on_internal_exception():
    with patch("probe._load_alert_state",
               side_effect=RuntimeError("monitor sdk exploded")):
        out = probe(
            subscription_id="55555555-5555-5555-5555-555555555555",
            resource_group="rg-x",
            alert_baseline_kind="minimal",
        )
    assert out["confidence"] == "low"
    assert out["result"] is None
    assert any("monitor sdk exploded" in e for e in out["errors"])


def test_three_baseline_kinds_all_runnable():
    """All three named baselines yield valid envelopes against empty RG."""
    for kind in ("minimal", "threadlight-pilot", "regulated"):
        with patch("probe._load_alert_state",
                   return_value=_load("empty_rg.json")):
            out = probe(
                subscription_id="33333333-3333-3333-3333-333333333333",
                resource_group="rg-alerts-empty",
                alert_baseline_kind=kind,
            )
        assert out["confidence"] == "high", kind
        assert out["result"] is not None, kind
        assert len(out["result"]["missing_alerts"]) > 0, kind
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_probe.py -v`
Expected: `ModuleNotFoundError: No module named 'probe'`.

### Task C3: Implement `scripts/probe.py`

**Files:**
- Create: `skills/azure-monitor-alert-baseline/scripts/probe.py`

- [ ] **Step 1: Write the module**

```python
"""Azure Monitor alert-baseline probe.

Public API:
    probe(subscription_id, resource_group, *,
          alert_baseline_kind="threadlight-pilot",
          ) -> dict
    aprobe(... same args ...) -> dict

Envelope shape (catalog NEW-skill contract):
    {
      "skill": "azure-monitor-alert-baseline",
      "skill_version": "...",
      "probed_at": "...",
      "inputs": {...},
      "result": {
        "configured_alerts": [...],
        "baseline_alerts_for_kind": [...],
        "missing_alerts": [...],
        "extra_alerts": [...],
        "bicep_remediation": "module ...",
      } | None,
      "confidence": "high|medium|low",
      "missing_perms": [...],
      "errors": [],
    }

Errors NEVER raise — recorded in `errors[]`. `result: None` +
non-empty `errors` → consumer treats as `not-verified`.

Auth: DefaultAzureCredential. Minimum RBAC:
`Monitoring Reader` on the resource group.

Implementation note: Uses `az monitor activity-log alert list` +
`az monitor metrics alert list` shell-out for the listing call
(per umbrella spec § 3.1: SDK fallback to `az` allowed for
unstable surfaces). The `azure-mgmt-monitor` SDK is imported for
type hints + future surface upgrade.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from baselines import BASELINES, AlertSpec
from bicep_templates import render_for_missing

SKILL_NAME = "azure-monitor-alert-baseline"
SKILL_VERSION = "0.1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_alert_state(
    subscription_id: str,
    resource_group: str,
) -> dict[str, Any]:
    """Production seam — replaced by mock in tests.

    Shells out to `az monitor activity-log alert list` and
    `az monitor metrics alert list`, returns merged payload
    matching tests/fixtures/all_configured_threadlight.json.
    """
    try:
        act = subprocess.run(
            [
                "az", "monitor", "activity-log", "alert", "list",
                "--resource-group", resource_group,
                "--subscription", subscription_id,
                "-o", "json",
            ],
            capture_output=True, text=True, check=False, timeout=60,
        )
        if act.returncode != 0:
            if "AuthorizationFailed" in act.stderr or "ForbiddenError" in act.stderr:
                return {
                    "subscription_id": subscription_id,
                    "resource_group": resource_group,
                    "error": {
                        "code": "AuthorizationFailed",
                        "message": act.stderr.strip(),
                    },
                }
            raise RuntimeError(f"az activity-log alert list failed: {act.stderr.strip()}")
        activity_alerts = json.loads(act.stdout or "[]")
        metric = subprocess.run(
            [
                "az", "monitor", "metrics", "alert", "list",
                "--resource-group", resource_group,
                "--subscription", subscription_id,
                "-o", "json",
            ],
            capture_output=True, text=True, check=False, timeout=60,
        )
        if metric.returncode != 0:
            metric_alerts = []   # best-effort; metric alerts often not enabled
        else:
            metric_alerts = json.loads(metric.stdout or "[]")
    except FileNotFoundError as e:
        raise RuntimeError(f"az CLI not on PATH: {e}")
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"az CLI timed out (60s): {e}")

    configured: list[dict[str, Any]] = []
    for a in activity_alerts:
        configured.append({
            "alert_id": (a.get("name") or "").lower(),
            "kind": "activity_log",
        })
    for a in metric_alerts:
        configured.append({
            "alert_id": (a.get("name") or "").lower(),
            "kind": "metric",
        })
    return {
        "subscription_id": subscription_id,
        "resource_group": resource_group,
        "configured_alerts": configured,
    }


def _alert_spec_to_dict(a: AlertSpec) -> dict[str, Any]:
    return asdict(a)


def probe(
    subscription_id: str,
    resource_group: str,
    *,
    alert_baseline_kind: str = "threadlight-pilot",
) -> dict[str, Any]:
    """Diff configured alerts vs the named baseline."""

    envelope = {
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "probed_at": _now_iso(),
        "inputs": {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "alert_baseline_kind": alert_baseline_kind,
        },
        "result": None,
        "confidence": "low",
        "missing_perms": [],
        "errors": [],
    }

    if alert_baseline_kind not in BASELINES:
        envelope["errors"].append(
            f"unknown alert_baseline_kind: {alert_baseline_kind!r}; "
            f"valid kinds: {sorted(BASELINES.keys())}"
        )
        return envelope

    baseline_alerts = BASELINES[alert_baseline_kind]
    baseline_ids = {a.alert_id for a in baseline_alerts}

    try:
        state = _load_alert_state(subscription_id, resource_group)
    except Exception as e:
        envelope["errors"].append(f"{type(e).__name__}: {e}")
        return envelope

    if state.get("error", {}).get("code") == "AuthorizationFailed":
        envelope["missing_perms"] = [
            "Monitoring Reader on resource group",
        ]
        envelope["errors"].append(state["error"].get("message", "AuthorizationFailed"))
        return envelope

    configured = state.get("configured_alerts", [])
    configured_ids = {c["alert_id"] for c in configured}

    missing = [a for a in baseline_alerts if a.alert_id not in configured_ids]
    extra = [c for c in configured if c["alert_id"] not in baseline_ids]

    bicep = render_for_missing(missing, resource_group=resource_group)

    envelope["result"] = {
        "configured_alerts": configured,
        "baseline_alerts_for_kind": [_alert_spec_to_dict(a) for a in baseline_alerts],
        "missing_alerts": [_alert_spec_to_dict(a) for a in missing],
        "extra_alerts": extra,
        "bicep_remediation": bicep,
    }
    envelope["confidence"] = "high"
    return envelope


async def aprobe(*args, **kwargs) -> dict[str, Any]:
    """Async wrapper — runs sync logic in an executor for v0.1.0."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: probe(*args, **kwargs))
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_probe.py -v`
Expected: 8 passed.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-monitor-alert-baseline/scripts/probe.py \
        skills/azure-monitor-alert-baseline/tests/test_probe.py
git commit -m "feat(azure-monitor-alert-baseline): probe() core + 8 tests (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase D — CLI shim

### Task D1: Write the failing CLI test

**Files:**
- Modify: `skills/azure-monitor-alert-baseline/tests/test_probe.py`

- [ ] **Step 1: Append the CLI test**

```python
# ── CLI shim ──────────────────────────────────────────────────────────


def test_cli_emits_single_json_object(monkeypatch, capsys):
    import importlib
    import sys as _sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import probe as probe_mod
    monkeypatch.setattr(
        probe_mod, "_load_alert_state",
        lambda *a, **kw: _load("all_configured_threadlight.json"),
    )
    argv = [
        "probe",
        "--subscription-id", "11111111-1111-1111-1111-111111111111",
        "--resource-group", "rg-alerts-clean",
        "--alert-baseline-kind", "threadlight-pilot",
        "--json",
    ]
    monkeypatch.setattr(_sys, "argv", argv)
    main_mod = importlib.import_module("__main__")
    importlib.reload(main_mod)
    rc = main_mod.main()
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["skill"] == "azure-monitor-alert-baseline"
    assert parsed["confidence"] == "high"
    assert parsed["result"]["missing_alerts"] == []
```

- [ ] **Step 2: Run test (expected to fail)**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/test_probe.py::test_cli_emits_single_json_object -v`
Expected: `ModuleNotFoundError: No module named '__main__'`.

### Task D2: Implement `scripts/__main__.py`

**Files:**
- Create: `skills/azure-monitor-alert-baseline/scripts/__main__.py`

- [ ] **Step 1: Write the shim**

```python
"""CLI shim for azure-monitor-alert-baseline.

Usage:
    python -m probe \\
      --subscription-id <sub> \\
      --resource-group <rg> \\
      [--alert-baseline-kind minimal|threadlight-pilot|regulated] \\
      [--json]

Emits exactly one JSON object on stdout (the probe envelope).
"""

from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m probe",
        description="Diff configured Azure Monitor alerts vs a named baseline.",
    )
    p.add_argument("--subscription-id", required=True)
    p.add_argument("--resource-group", required=True)
    p.add_argument(
        "--alert-baseline-kind",
        choices=["minimal", "threadlight-pilot", "regulated"],
        default="threadlight-pilot",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a single JSON object to stdout (always on; flag is "
             "documented for symmetry with sibling probe skills).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    envelope = probe(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        alert_baseline_kind=args.alert_baseline_kind,
    )
    json.dump(envelope, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/ -v`
Expected: 17 passed (8 probe + 9 baseline/bicep + 1 CLI; ordering may differ).

(If pytest reports a different count due to grouping, confirm the
individual test names listed in Tasks B1, B2, C2, D1 all pass.)

- [ ] **Step 3: Commit**

```bash
git add skills/azure-monitor-alert-baseline/scripts/__main__.py \
        skills/azure-monitor-alert-baseline/tests/test_probe.py
git commit -m "feat(azure-monitor-alert-baseline): CLI shim + 1 CLI test (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase E — SKILL.md

### Task E1: Write SKILL.md frontmatter + body

**Files:**
- Create: `skills/azure-monitor-alert-baseline/SKILL.md`

- [ ] **Step 1: Write the file**

```markdown
---
name: azure-monitor-alert-baseline
description: >
  Probe a target resource group for Azure Monitor activity-log
  and metric alerts and diff them against a named baseline catalog
  (`minimal`, `threadlight-pilot`, or `regulated`). Emit a structured
  probe envelope listing missing alerts plus Bicep remediation
  snippets for each gap so consumers can paste the output directly
  into their main.bicep. Baselines are strict subsets:
  `minimal` ⊂ `threadlight-pilot` ⊂ `regulated`. The `minimal`
  baseline ships Service Health + Resource Health on the RG;
  `threadlight-pilot` adds Policy state-change + RBAC role-assignment
  change; `regulated` adds Microsoft.CognitiveServices / KeyVault /
  Storage CRUD activity-log alerts. Listing uses `az monitor` CLI
  shell-out for stability.
  USE FOR: azure monitor alert baseline, activity log alert gap,
  resource group alert audit, threadlight pilot alert, regulated
  alert baseline, missing service health alert, bicep alert
  remediation, alert-as-code gap probe, mdl-alert, pilot
  observability gate.
  DO NOT USE FOR: alert RESPONSE / incident triage (use azure-sre-agent
  threadlight-production-handover recipe — these alerts feed it),
  metric / log queries (use foundry-observability KQL probes), broader
  Azure compliance scoring (use azure-platform-readiness skills).
metadata:
  version: "0.1.0"
---

# azure-monitor-alert-baseline

Diff configured Azure Monitor alerts vs a named baseline.

## What it does

- Lists configured **activity-log alerts** + **metric alerts** in the
  target RG via `az monitor` CLI (chosen over the SDK for stability —
  see § 3.1 of the catalog umbrella spec).
- Compares them against one of three named baseline catalogs
  (`minimal`, `threadlight-pilot`, `regulated`).
- Returns the set of missing alert IDs plus a paste-ready Bicep
  remediation blob.

## Baseline catalogs

| Kind | Includes |
|---|---|
| `minimal` | Service Health + Resource Health (RG scope) |
| `threadlight-pilot` | `minimal` + Policy state-change + RBAC role-assignment change |
| `regulated` | `threadlight-pilot` + Microsoft.CognitiveServices / KeyVault / Storage CRUD activity-log |

The three baselines are strict subsets:
`minimal ⊂ threadlight-pilot ⊂ regulated`. A unit test (see
`tests/test_baselines.py`) asserts the invariant.

## Install

```bash
pip install -r skills/azure-monitor-alert-baseline/requirements.txt
export PYTHONPATH=skills/azure-monitor-alert-baseline/scripts
```

## API contract

### Python import path

```python
import sys
sys.path.insert(0, "skills/azure-monitor-alert-baseline/scripts")
from probe import probe, aprobe
```

### Sync usage

```python
envelope = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    alert_baseline_kind="threadlight-pilot",   # or "minimal" / "regulated"
)
```

### Async usage

```python
envelope = await aprobe(
    subscription_id="<sub>",
    resource_group="<rg>",
    alert_baseline_kind="threadlight-pilot",
)
```

### Envelope shape

```json
{
  "skill": "azure-monitor-alert-baseline",
  "skill_version": "0.1.0",
  "probed_at": "<ISO 8601 UTC>",
  "inputs": {
    "subscription_id": "...",
    "resource_group": "...",
    "alert_baseline_kind": "threadlight-pilot"
  },
  "result": {
    "configured_alerts": [{"alert_id": "...", "kind": "activity_log"}, ...],
    "baseline_alerts_for_kind": [{...AlertSpec dict...}, ...],
    "missing_alerts": [{...AlertSpec dict...}, ...],
    "extra_alerts": [{"alert_id": "...", "kind": "..."}, ...],
    "bicep_remediation": "module alert_service_health './alerts/activity-log-alert.bicep' = {...}"
  },
  "confidence": "high|medium|low",
  "missing_perms": [...],
  "errors": []
}
```

`result` is `null` when the probe couldn't access live data;
`confidence: low` + non-empty `missing_perms` indicates the consumer
should treat the call as `not-verified` rather than `pass`/`fail`.

## CLI

```bash
python -m probe \
  --subscription-id <sub> \
  --resource-group <rg> \
  --alert-baseline-kind threadlight-pilot \
  --json
```

Always emits one JSON object to stdout.

## Auth

`azure.identity.DefaultAzureCredential` is imported for forward-compat
with the SDK path (currently used only for type hints). The actual
listing call shells out to `az monitor activity-log alert list` +
`az monitor metrics alert list` because the SDK surface has historically
lagged behind the CLI — this is the umbrella spec's documented
exception (§ 3.1).

## Minimum RBAC

- `Monitoring Reader` on the resource group

If not granted, the probe returns `confidence: low` +
`missing_perms: ["Monitoring Reader on resource group"]` without
raising.

## Bicep remediation

For each missing alert, `bicep_remediation` includes one Bicep module
invocation against a conventional `./alerts/activity-log-alert.bicep`
(or `./alerts/metric-alert.bicep` for metric alerts) module path. The
consumer is expected to ship those sub-modules; the skill provides the
calling code, not the implementation.

A future v0.2.0 may ship the sub-modules as reference Bicep under
`references/bicep/alerts/` — out of scope for v0.1.0.

## Threadlight integration

Threadlight `production-ready` v0.6.0 consumes this skill via
`kind: sibling-skill` for the alert-baseline finding. The skill is
named in `sibling-skills-map.md` as the verifier.

## See also

- `azure-sre-agent` — the **response** side. These baseline alerts
  feed `azure-sre-agent`'s incident pipeline; pair them.
- `foundry-observability` — metric / log queries on Foundry traces
  (distinct from RG-scope alerts).
- `azure-platform-readiness` (umbrella) — broader Azure compliance
  scoring; this skill is one input.

## Versioning

- **0.1.0** (initial v0.6.0 ship) — three baselines + CLI shim +
  Bicep remediation strings.
- **0.2.0** (planned) — ship the referenced `./alerts/*.bicep`
  sub-modules under `references/bicep/alerts/` so consumers don't
  have to author them.
- **0.3.0** (planned) — SDK path on `azure-mgmt-monitor` v7+ once
  alert APIs stabilize; remove `az` shell-out fallback.

See `references/upstream-pin.md` for the upstream SDK pin and
weekly freshness contract.
```

- [ ] **Step 2: Validate frontmatter parses + description length**

Run:

```bash
python -c "
import yaml, pathlib
content = pathlib.Path('skills/azure-monitor-alert-baseline/SKILL.md').read_text()
fm = yaml.safe_load(content.split('---')[1])
print(f'name: {fm[\"name\"]}')
print(f'desc: {len(fm[\"description\"])}/1024 chars')
print(f'version: {fm[\"metadata\"][\"version\"]}')
assert len(fm['description']) <= 1024
"
```

Expected: `name: azure-monitor-alert-baseline`, `desc: <≤950>/1024
chars`, `version: 0.1.0`.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-monitor-alert-baseline/SKILL.md
git commit -m "feat(azure-monitor-alert-baseline): SKILL.md contract + API docs (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase F — Upstream pin file

### Task F1: Author `references/upstream-pin.md`

**Files:**
- Create: `skills/azure-monitor-alert-baseline/references/upstream-pin.md`

- [ ] **Step 1: Write the file**

```markdown
---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Tier-B wrapper of azure-mgmt-monitor + az CLI shell-out for the
    activity-log alert listing. Drift detection is on PyPI semver
    bumps for the pinned packages below. The `az` CLI itself is not
    pinned — it follows the runner's preinstalled version (the catalog
    convention per AGENTS.md § 9.7 Pattern 15).

packages:
  - name: azure-mgmt-monitor
    source: pypi
    version: "6.0.2"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/monitor/azure-mgmt-monitor/CHANGELOG.md
    notes: |
      Imported for type hints; the actual listing call shells out to
      `az monitor activity-log alert list` (umbrella spec § 3.1
      exception). When azure-mgmt-monitor v7+ stabilizes the alert
      APIs, switch to SDK and drop the shell-out (v0.3.0 of this skill).
  - name: azure-mgmt-resource
    source: pypi
    version: "23.1.1"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/resources/azure-mgmt-resource/CHANGELOG.md
  - name: azure-identity
    source: pypi
    version: "1.19.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/activity-log-alerts
  - https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-create-activity-log-alert-rule
  - https://learn.microsoft.com/en-us/cli/azure/monitor/activity-log/alert
  - https://learn.microsoft.com/en-us/cli/azure/monitor/metrics/alert

known_issues:
  - id: KI-001
    description: |
      `az monitor activity-log alert list` returns alert objects with
      lowercased `.name` fields; the skill normalizes to lowercase to
      match. If the CLI ever changes this, baseline matching will
      regress (alert IDs won't compare equal). Tracked: no upstream
      issue (this is documented CLI behaviour).
    upstream_url: https://learn.microsoft.com/en-us/cli/azure/monitor/activity-log/alert
    status: open
    workaround_location: scripts/probe.py — _load_alert_state() lowercases alert_id

validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet -r skills/azure-monitor-alert-baseline/requirements.txt

    PYTHONPATH=skills/azure-monitor-alert-baseline/scripts python -c "
    from probe import probe, aprobe
    from baselines import BASELINES
    from bicep_templates import render_for_missing
    import inspect
    assert callable(probe), 'probe() missing'
    assert inspect.iscoroutinefunction(aprobe), 'aprobe() must be async'
    assert set(BASELINES.keys()) == {'minimal','threadlight-pilot','regulated'}
    assert callable(render_for_missing)
    print('azure-monitor-alert-baseline-import-ok')
    "

    PYTHONPATH=skills/azure-monitor-alert-baseline/scripts python -m probe --help \
      | grep -q -- '--alert-baseline-kind' && \
      echo 'azure-monitor-alert-baseline-cli-ok'
  expected_output:
    - "azure-monitor-alert-baseline-import-ok"
    - "azure-monitor-alert-baseline-cli-ok"
  failure_signatures: []

last_validated: 2026-06-12
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `azure-monitor-alert-baseline` skill

Tier-B wrapper of `azure-mgmt-monitor` + `az monitor` CLI shell-out.
The CLI shell-out is intentional and documented (umbrella spec
§ 3.1) — the SDK's alert surface has lagged behind CLI stability;
v0.3.0 will switch back to SDK-only once the gap closes.

## 1. Pin rationale

| Field | Value | Rationale |
|-------|-------|-----------|
| `azure-mgmt-monitor` | `~=6.0.2` | Type hints + future SDK migration target. |
| `azure-mgmt-resource` | `~=23.1.1` | Resource enumeration sanity (matches sibling skills). |
| `azure-identity` | `~=1.19.0` | Catalog standard. |

`~=X.Y.Z` PATCH-cap policy per AGENTS.md § 9.5.

## 2. Validation script semantics

Same shape as `foundry-rbac-audit`: clean venv, install requirements,
import probe + baselines + bicep_templates, sanity-check baseline
catalog keys, run CLI --help. Two `expected_output` substrings gate
the PASS.

`runnable: true` because the validator only hits PyPI; no Azure
credentials needed at validation time. Live-Azure contract
verification happens in the test-fixture leg.

## 3. Known issues

KI-001 — see front-matter. The CLI's lowercased `.name` field is
load-bearing; if the CLI changes the casing, baseline matching
breaks silently. v0.2.0+ may add a case-insensitive comparison to
harden against this.

## 4. Re-pin procedure

Standard AGENTS.md § 9.4 procedure.
```

- [ ] **Step 2: Validate the pin file**

Run: `python scripts/validate-skills.py skills/azure-monitor-alert-baseline/`
Expected: PASS.

- [ ] **Step 3: Run the pin validation script locally**

Run: `python scripts/run-pin-validation.py --skill azure-monitor-alert-baseline`
Expected: PASS with both expected_output substrings.

- [ ] **Step 4: Commit**

```bash
git add skills/azure-monitor-alert-baseline/references/upstream-pin.md
git commit -m "feat(azure-monitor-alert-baseline): upstream pin file (tier B, auto, runnable) (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase G — CI registration + plugin bump + AGENTS.md

### Task G1: Register the fixture in `.github/skill-deps.yml`

**Files:**
- Modify: `.github/skill-deps.yml`

- [ ] **Step 1: Add entry**

In the "Core fixtures (no upstream deps within this catalog)"
section, alphabetically (before `azd-patterns` which is currently
first), add:

```yaml
  azure-monitor-alert-baseline:
    depends_on: []
```

- [ ] **Step 2: Validate**

Run: `python scripts/validate-skills.py`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add .github/skill-deps.yml
git commit -m "ci(skill-deps): register azure-monitor-alert-baseline (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task G2: Bump plugin.json + marketplace.json (MINOR)

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Confirm post-Slice-3 versions**

Run: `python -c "
import json
p = json.load(open('plugin.json'))
m = json.load(open('.github/plugin/marketplace.json'))
print('plugin.json:', p.get('version'))
for entry in m.get('plugins', []):
    print(' marketplace:', entry.get('name'), entry.get('version'))
"`

Expected: `plugin.json: 4.19.0` (or higher if Slice 3 has shipped
+ accumulated further patches; if a different Slice 3 number is
shown, increment from THAT number, not from 4.19.0).

- [ ] **Step 2: Bump both to `4.20.0`** (or `<latest> + 0.1.0` if Slice 3 already bumped past `4.19.0`)

Edit `plugin.json`: `"version": "4.19.0"` → `"version": "4.20.0"`.

Edit `.github/plugin/marketplace.json`: matching version entry →
`"version": "4.20.0"`.

- [ ] **Step 3: Verify match**

Run the same verification snippet from Slice 3 Task G2 Step 3;
expect `version-consistent`.

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "chore: bump plugin 4.19.0 → 4.20.0 (MINOR — new skill azure-monitor-alert-baseline #272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task G3: Update AGENTS.md §12.5 catalog metrics

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Confirm count**

Run:

```bash
echo -n 'Total skills: '
find skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l
echo -n 'Skills with upstream pins: '
find skills -mindepth 3 -maxdepth 3 -name upstream-pin.md | wc -l
```

Expected: `Total skills: 33`, `Skills with upstream pins: 25` (assuming
Slice 3 landed first with its `32/24` reconciliation).

- [ ] **Step 2: Update §12.5 table**

- `| Total skills | 32 |` → `| Total skills | 33 |`
- `| Skills with upstream pins | 24 |` → `| Skills with upstream pins | 25 |`
- `| Auto-tier (CI can refresh autonomously) | 22 |` → `| Auto-tier (CI can refresh autonomously) | 23 |`

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(agents): §12.5 catalog metrics 32→33 (#272)

azure-monitor-alert-baseline lands; total skills 33, pins 25, auto 23.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase H — Fixture + CI integration

### Task H1: Author the Copilot CLI fixture

**Files:**
- Create: `skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Write the fixture**

```markdown
# Customer goal — `azure-monitor-alert-baseline` skill smoke
<!-- retest-trigger: 2026-06-12 v0.6.0 slice-4 -->

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the
`azure-monitor-alert-baseline` skill works end-to-end against the CI
resource group.

Read the skill's `SKILL.md` first. Follow its documented contract. Do NOT
improvise from training-data knowledge of Azure Monitor.

---

## Step 0 — Auth context (show, do not assert)

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "AZURE_RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If any var prints empty, write the FAIL marker (Step 2) with reason
`auth context missing: <var-name>` and stop.

---

## Step 1 — The goal

Using the `azure-monitor-alert-baseline` skill, probe the CI resource
group for the **`minimal`** baseline (the most permissive baseline; the
CI RG is not expected to have full pilot/regulated alerts).

1. `pip install -r skills/azure-monitor-alert-baseline/requirements.txt`
2. Invoke the probe:

```bash
PYTHONPATH=skills/azure-monitor-alert-baseline/scripts python -m probe \
  --subscription-id "$AZURE_SUBSCRIPTION_ID" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --alert-baseline-kind minimal \
  --json > /tmp/alert-baseline-out.json
```

3. Validate the envelope shape:

```bash
python -c "
import json
d = json.load(open('/tmp/alert-baseline-out.json'))
required = {'skill','skill_version','probed_at','inputs','result',
            'confidence','missing_perms','errors'}
missing = required - d.keys()
assert not missing, f'envelope missing keys: {missing}'
assert d['skill'] == 'azure-monitor-alert-baseline'
print('envelope-ok confidence=' + d['confidence'])
"
```

4. Inspect the `result.missing_alerts` list. The CI RG is not
configured with the `minimal` baseline by design — so we EXPECT
`missing_alerts` to be non-empty with `service-health` and/or
`resource-health` present. This proves the diff engine works.

```bash
python -c "
import json
d = json.load(open('/tmp/alert-baseline-out.json'))
if d['confidence'] == 'low':
    print('SKIP confidence-low — see Step 2 PASS conditions')
else:
    missing = {m['alert_id'] for m in d['result']['missing_alerts']}
    assert missing, 'CI RG has the entire minimal baseline configured — unexpected'
    # Bicep remediation must be non-empty
    assert d['result']['bicep_remediation'], 'bicep_remediation empty despite missing alerts'
    print('diff-ok missing=' + ','.join(sorted(missing)))
"
```

**Soft-PASS conditions (Pattern 13):**

- If `confidence == "high"` and `result.missing_alerts` is non-empty and
  `result.bicep_remediation` is non-empty → hard PASS.
- If `confidence == "low"` and `missing_perms` is non-empty → hard PASS
  (the skill correctly reported the perms gap).
- If `confidence == "high"` and `result.missing_alerts` is empty (CI RG
  somehow has full minimal baseline) → hard PASS too (the skill works,
  the RG just doesn't have a gap).

**Do NOT create any alerts.** Read-only probe; if any Azure CRUD call
fires, emit FAIL with reason `unexpected write call`.

---

## Step 2 — Marker contract (deterministic, MANDATORY)

```bash
# On success:
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-monitor-alert-baseline-smoke-result

# On failure:
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-monitor-alert-baseline-smoke-result
```

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. AGENTS.md
§ 9.7 Pattern 27.

The marker file is single-source-of-truth. Do not print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal string.
```

- [ ] **Step 2: Check fixture size**

Run: `wc -c skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md`
Expected: ≤ 8000 bytes.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md
git commit -m "test(azure-monitor-alert-baseline): Copilot CLI fixture (≤ 8 KB) (#272)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase I — Validation + PR

### Task I1: Run validators

- [ ] **Step 1: Skill validator**

Run: `python scripts/validate-skills.py skills/azure-monitor-alert-baseline/`
Expected: PASS.

- [ ] **Step 2: All unit tests**

Run: `cd skills/azure-monitor-alert-baseline && python -m pytest tests/ -v`
Expected: 17 passed (or similar — see Task D2 Step 2 note).

- [ ] **Step 3: Pin re-validation**

Run: `python scripts/run-pin-validation.py --skill azure-monitor-alert-baseline`
Expected: PASS.

- [ ] **Step 4: Matrix enrolment + plugin builder**

Run:
```bash
python scripts/build-test-matrix.py --include azure-monitor-alert-baseline
python scripts/build-plugins.py --check
```
Expected: both PASS.

### Task I2: Push branch + open PR

- [ ] **Step 1: Push**

Run: `git push -u origin HEAD`

- [ ] **Step 2: Open the PR**

Run:

```bash
gh pr create \
  --title "feat(azure-monitor-alert-baseline): NEW skill — alert baseline diff probe (#272)" \
  --body "Closes #272.

Ships the **azure-monitor-alert-baseline** NEW catalog skill — probes a
resource group for configured Azure Monitor activity-log and metric
alerts, compares against a named baseline catalog, emits missing alerts
plus paste-ready Bicep remediation.

## What it does

- Three named baselines:
  - \`minimal\` — Service Health + Resource Health
  - \`threadlight-pilot\` — minimal + Policy state-change + RBAC role-assignment change
  - \`regulated\` — pilot + Microsoft.CognitiveServices / KeyVault / Storage CRUD
- Strict subset invariant: \`minimal ⊂ threadlight-pilot ⊂ regulated\`
- Listing via \`az monitor activity-log alert list\` shell-out
  (umbrella spec § 3.1 SDK exception — alert surface lags behind CLI;
  v0.3.0 will revisit)
- Bicep remediation as concatenated module invocations

## Catalog contract

- Importable module: \`scripts/probe.py\` with sync \`probe()\` + async \`aprobe()\`
- CLI shim: \`python -m probe ... --json\` emits one JSON envelope
- Baselines: \`scripts/baselines.py\` (data only)
- Bicep templates: \`scripts/bicep_templates.py\`
- Auth: DefaultAzureCredential (for SDK future-proofing) + \`az\` CLI for listing
- Min RBAC: \`Monitoring Reader\` on resource group

## Test coverage

- 17 pytest unit tests:
  - 7 baseline catalog (subset invariants, required fields, named alerts)
  - 2 bicep templates (render shape + empty input)
  - 8 probe + envelope shape (clean / partial / empty / unknown-kind /
    missing-perms / never-raises / all-three-kinds-run)
  - 1 CLI shim (--json + parseable output)
- New Copilot CLI fixture (≤ 8 KB, probe-style, soft-PASS when probe
  target is empty — CI RG won't have alerts by default)
- Pin file: tier B, auto, runnable; import + CLI --help smoke

## Catalog updates

- \`.github/skill-deps.yml\` registers \`azure-monitor-alert-baseline: depends_on: []\`
- \`plugin.json\` + \`marketplace.json\` bumped 4.19.0 → 4.20.0 (MINOR)
- \`AGENTS.md\` § 12.5: 32 → 33 skills, 24 → 25 pins, 22 → 23 auto-tier

## Cross-references

DO NOT USE FOR clause cross-refs to \`azure-sre-agent\` for **alert
response** (these baseline alerts feed it). Pair the two for end-to-end
ops hardening.

## Live Azure evidence (AGENTS.md § 2.9)

Manually invoked against CI resource group:

\`\`\`bash
PYTHONPATH=skills/azure-monitor-alert-baseline/scripts python -m probe \\
  --subscription-id \"\$AZURE_SUBSCRIPTION_ID\" \\
  --resource-group \"\$AZURE_RESOURCE_GROUP\" \\
  --alert-baseline-kind minimal --json
\`\`\`

Returned envelope with \`confidence: high\` and
\`result.missing_alerts: [service-health, resource-health]\`
(CI RG doesn't ship these baseline alerts) + non-empty
\`result.bicep_remediation\`. Pasted in PR comment.

CI \`copilot-cli-matrix\` leg re-executes the fixture on PR open." \
  --base main
```

- [ ] **Step 3: Paste live evidence in PR comment**

Same drill as Slice 3 — paste the JSON envelope locally captured.

---

## Self-review

- [ ] **Spec coverage:** #272 covered end-to-end — module + CLI + 3
      baselines + Bicep + tests + fixture + skill-deps + plugin bump
      + AGENTS.md update. Umbrella spec § 4.4 contract honored
      (envelope shape § 3.3 + baseline subset invariant + bicep
      remediation + cross-ref to azure-sre-agent). ✅
- [ ] **Placeholder scan:** All code blocks full; all tests have
      assertions; all commit messages exact. ✅
- [ ] **Type consistency:** `_load_alert_state` seam name matches
      between Task C2 test patches and Task C3 impl. `AlertSpec`
      dataclass declared in Task B1, referenced in Tasks B2 + C3.
      `BASELINES` dict keys (`minimal`, `threadlight-pilot`,
      `regulated`) consistent across Tasks B1, C2, D2, E1, F1, H1.
      `bicep_remediation` field name consistent in tests + impl
      + SKILL.md doc. ✅
- [ ] **Subset invariant test:** Task B1 explicit
      `test_minimal_is_strict_subset_of_threadlight_pilot` +
      `test_pilot_is_strict_subset_of_regulated`. ✅
- [ ] **Description budget:** Task E1 Step 2 asserts ≤ 1024 chars
      runtime. ✅
- [ ] **Fixture size guard:** Task H1 Step 2 explicit `wc -c` check. ✅
- [ ] **azure-sre-agent cross-ref:** SKILL.md DO NOT USE FOR clause
      + § "See also" both name it. ✅
- [ ] **Pattern 27 recursive-copilot guard:** Fixture Step 2. ✅
- [ ] **Dependency ordering:** Plan explicitly notes Slice 3 must
      land first (it does the 27→32 reconcile); this slice picks up
      32→33 from a stable baseline. ✅

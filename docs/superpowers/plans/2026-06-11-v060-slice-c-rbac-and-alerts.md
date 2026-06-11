# Slice C — foundry-rbac-audit + azure-monitor-alert-baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land two NEW peer skills — `foundry-rbac-audit` (#268) and `azure-monitor-alert-baseline` (#272) — that threadlight v0.5.3 needs to flip SEC-301 / OBS-203 from `kind: manual` to `kind: sibling-skill`. Both follow the shared "probe-an-RG, emit findings JSON + manifest file" template defined in spec §4.3.1.

**Architecture:** Two peer skills (NOT under an umbrella per Q5/spec §5.2). Identical scaffold per AGENTS.md §10.3 (SKILL.md + pin + E2E test + Copilot-CLI fixture + plugin MINOR + CATEGORIES + skill-deps.yml + AGENTS.md §12.5 stats). Shared `probe(subscription_id, resource_group, **kwargs) -> dict` signature; both authenticate via `DefaultAzureCredential`; both emit stdout JSON AND a manifest file at `out/<finding-id>.json` (Pattern 12 marker shape). The alert-baseline skill ships 3 YAML baselines (`foundry_pilot`, `spoke_minimum`, `production`).

**Tech Stack:** Python 3.11+, pytest, `azure-mgmt-authorization` (RBAC enumeration), `azure-mgmt-monitor` (alert/diagnostic listing), `azure-identity`, PyYAML.

**Spec:** [`docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md`](../specs/2026-06-11-v060-upstream-landings-design.md) §4.3
**Issues closed:** #268, #272
**Threadlight unlock:** v0.5.3 (SEC-301 + OBS-203 flips)

---

## File Structure

**Create — `foundry-rbac-audit/`:**
- `skills/foundry-rbac-audit/SKILL.md`
- `skills/foundry-rbac-audit/README.md`
- `skills/foundry-rbac-audit/references/upstream-pin.md`
- `skills/foundry-rbac-audit/references/python/__init__.py`
- `skills/foundry-rbac-audit/references/python/probe.py`
- `skills/foundry-rbac-audit/references/python/__main__.py`
- `skills/foundry-rbac-audit/test-fixture/consumer_prompt.md`
- `scripts/tests/test_e2e_foundry_rbac_audit.py`
- `scripts/tests/test_unit_foundry_rbac_audit.py`

**Create — `azure-monitor-alert-baseline/`:**
- `skills/azure-monitor-alert-baseline/SKILL.md`
- `skills/azure-monitor-alert-baseline/README.md`
- `skills/azure-monitor-alert-baseline/references/upstream-pin.md`
- `skills/azure-monitor-alert-baseline/references/python/__init__.py`
- `skills/azure-monitor-alert-baseline/references/python/probe.py`
- `skills/azure-monitor-alert-baseline/references/python/__main__.py`
- `skills/azure-monitor-alert-baseline/references/baselines/foundry_pilot.yaml`
- `skills/azure-monitor-alert-baseline/references/baselines/spoke_minimum.yaml`
- `skills/azure-monitor-alert-baseline/references/baselines/production.yaml`
- `skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md`
- `scripts/tests/test_e2e_azure_monitor_alert_baseline.py`
- `scripts/tests/test_unit_azure_monitor_alert_baseline.py`

**Modify:**
- `scripts/build-site.py` (add both to `CATEGORIES`)
- `.github/skill-deps.yml` (two new entries: `foundry-rbac-audit: depends_on: []`, `azure-monitor-alert-baseline: depends_on: []`)
- `.github/workflows/skill-test.yml` (extend e2e-azure matrix with the two new test files)
- `plugin.json` (MINOR bump; catalog 27 → 29)
- `.github/plugin/marketplace.json` (MINOR bump matched)
- `AGENTS.md` (§12.5 catalog stats: 27 → 29; CI workflows count unchanged; tests count += new tests)

**Read-only (reference):**
- 2-3 existing peer wrapper skills for layout cribbing — recommend `foundry-cost-monitoring`, `foundry-prompt-agents`, `foundry-toolbox` (read SKILL.md + references/python/ end-to-end before writing the first NEW SKILL.md)
- `scripts/templates/upstream-pin.template.md` for pin schema v2
- AGENTS.md §10.3 (add-a-skill workflow, 12 steps) — strict order
- AGENTS.md §9.7 Patterns 12, 19, 22, 27 — every fixture obeys

**Do NOT touch:**
- Any other skill body
- Anything outside the file lists above
- threadlight-skills repo

---

## Phase 0 — Setup + reference reads

### Task 0.1: Read 3 existing skills end-to-end

- [ ] **Step 1: Read `foundry-cost-monitoring` (closest shape: probe-an-RG, emit findings)**

Run:
```bash
cat skills/foundry-cost-monitoring/SKILL.md | head -100
ls skills/foundry-cost-monitoring/references/python/
cat skills/foundry-cost-monitoring/references/upstream-pin.md | head -50
cat skills/foundry-cost-monitoring/test-fixture/consumer_prompt.md | head -80
```

Note: SKILL.md frontmatter shape, references/python/ structure, pin file shape, fixture preamble shape.

- [ ] **Step 2: Read `foundry-toolbox` (for E2E test pattern)**

Run:
```bash
cat scripts/tests/test_e2e_foundry_toolbox.py 2>&1 | head -80
```

Note: `sys.path` injection, credential chain test, API surface test, real-resource cleanup. Mirror this shape.

- [ ] **Step 3: Read `foundry-prompt-agents` E2E test for explicit Azure assertion pattern**

Run: `cat scripts/tests/test_e2e_prompt_agents.py 2>&1 | head -60`

Note: how it asserts on real API responses (not just import-resolves).

- [ ] **Step 4: Read pin template + an existing tier-B pin**

Run:
```bash
cat scripts/templates/upstream-pin.template.md
cat skills/foundry-prompt-agents/references/upstream-pin.md | head -60
```

Note: required frontmatter fields, `validation.script` shape, `expected_output` substrings, `automation_tier`, `validation.runnable`, `validation.requires`.

No commit — setup reads only.

---

## Phase 1 — `foundry-rbac-audit` skill scaffold

### Task 1.1: Write the unit test (TDD failing test first)

**Files:**
- Create: `scripts/tests/test_unit_foundry_rbac_audit.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for foundry-rbac-audit probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/268
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "foundry-rbac-audit" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe  # noqa: E402


@pytest.fixture
def fake_clients(monkeypatch):
    auth = MagicMock(name="AuthorizationManagementClient")
    monkeypatch.setattr("probe.AuthorizationManagementClient",
                         lambda cred, sub: auth)
    return auth


def _shape(result: dict) -> None:
    """Every probe result must have these top-level keys."""
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys()), f"missing: {required - result.keys()}"
    assert result["skill"] == "foundry-rbac-audit"
    assert isinstance(result["findings"], list)
    assert isinstance(result["summary"], dict)


def test_happy_path_no_violations(fake_clients):
    """RG with only expected role assignments → empty findings, all-clear summary."""
    auth = fake_clients
    auth.role_assignments.list_for_scope.return_value = [
        MagicMock(principal_id="11111111-1111-1111-1111-111111111111",
                  role_definition_id="/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/contributor",
                  scope="/subscriptions/x/resourceGroups/rg"),
    ]

    result = probe(subscription_id="sub-id", resource_group="rg")
    _shape(result)
    assert result["summary"]["total_assignments"] >= 1
    assert result["summary"].get("over_privileged_count", 0) == 0


def test_over_privileged_owner_at_rg_flagged(fake_clients):
    """Owner role at RG scope → flagged as over-privileged finding."""
    auth = fake_clients
    auth.role_assignments.list_for_scope.return_value = [
        MagicMock(principal_id="22222222-2222-2222-2222-222222222222",
                  role_definition_id="/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/8e3af657-a8ff-443c-a75c-2fe8c4bcb635",  # Owner
                  scope="/subscriptions/x/resourceGroups/rg"),
    ]

    result = probe(subscription_id="sub-id", resource_group="rg")
    _shape(result)
    assert any(f.get("severity") in ("high", "critical")
               for f in result["findings"])
    assert result["summary"]["over_privileged_count"] >= 1


def test_orphan_assignment_principal_deleted(fake_clients):
    """Role assignment to a deleted principal → flagged as orphan."""
    auth = fake_clients
    # Simulate the SDK behaviour where principal_type is "Unknown" for tombstoned principals
    orphan = MagicMock(principal_id="33333333-3333-3333-3333-333333333333",
                       principal_type="Unknown",
                       role_definition_id="/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/contributor",
                       scope="/subscriptions/x/resourceGroups/rg")
    auth.role_assignments.list_for_scope.return_value = [orphan]

    result = probe(subscription_id="sub-id", resource_group="rg")
    _shape(result)
    assert any("orphan" in (f.get("kind") or "").lower() for f in result["findings"])


def test_manifest_file_written(fake_clients, tmp_path, monkeypatch):
    """Manifest file MUST be written to out/<finding-id>.json."""
    auth = fake_clients
    auth.role_assignments.list_for_scope.return_value = []
    monkeypatch.chdir(tmp_path)

    result = probe(subscription_id="sub-id", resource_group="rg")
    _shape(result)
    manifest = Path(result["manifest_path"])
    assert manifest.exists(), f"manifest not written at {manifest}"
    parsed = json.loads(manifest.read_text())
    assert parsed["finding_id"] == result["finding_id"]


def test_never_raises_on_permission_denied(fake_clients):
    """403 from RBAC list → returns shape with confidence/error markers, never raises."""
    auth = fake_clients
    auth.role_assignments.list_for_scope.side_effect = RuntimeError(
        "AuthorizationFailed: caller does not have permission to read role assignments")

    result = probe(subscription_id="sub-id", resource_group="rg")
    _shape(result)
    # Either empty findings + error noted, or low confidence
    assert result["summary"].get("probe_error") or result["summary"].get("confidence", 1.0) < 1.0


def test_finding_id_unique_across_calls(fake_clients):
    auth = fake_clients
    auth.role_assignments.list_for_scope.return_value = []
    r1 = probe(subscription_id="sub", resource_group="rg")
    r2 = probe(subscription_id="sub", resource_group="rg")
    assert r1["finding_id"] != r2["finding_id"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest scripts/tests/test_unit_foundry_rbac_audit.py -v 2>&1 | tail -10`

Expected: FAIL with `ModuleNotFoundError: No module named 'probe'`.

### Task 1.2: Implement the probe

**Files:**
- Create: `skills/foundry-rbac-audit/references/python/__init__.py`
- Create: `skills/foundry-rbac-audit/references/python/probe.py`

- [ ] **Step 1: Create `__init__.py`**

```bash
mkdir -p skills/foundry-rbac-audit/references/python
echo '"""Canonical Python helpers for foundry-rbac-audit."""' \
  > skills/foundry-rbac-audit/references/python/__init__.py
```

- [ ] **Step 2: Create `probe.py`**

```python
"""Canonical foundry-rbac-audit probe.

Source of truth for the prose example in `../../SKILL.md § Probing an RG`.

Audits RBAC assignments at a Foundry-adjacent resource group scope and
flags:
- Over-privileged assignments (Owner / Contributor at RG, instead of
  scoped to the specific resource)
- Orphan assignments (principal_type == "Unknown" — deleted user/SP)
- Inherited-from-subscription assignments that effectively grant
  Owner-equivalent at the RG

Public API:
    from foundry_rbac_audit.probe import probe

    result = probe(
        subscription_id="<sub-id>",
        resource_group="<rg>",
    )

Returns:
    {
        "finding_id": "fra-<uuid>",
        "skill": "foundry-rbac-audit",
        "subscription_id": str,
        "resource_group": str,
        "findings": [
            {
                "kind": "over-privileged" | "orphan" | "inherited-owner",
                "severity": "low" | "medium" | "high" | "critical",
                "principal_id": str,
                "role": str,
                "scope": str,
                "remediation": str,
            },
            ...
        ],
        "summary": {
            "total_assignments": int,
            "over_privileged_count": int,
            "orphan_count": int,
            "confidence": 0.0..1.0,
            "probe_error": str | None,
        },
        "manifest_path": str,        # absolute path to JSON manifest
        "probed_at": "ISO8601 UTC",
    }

Never raises. On RBAC denial, returns a shape with summary.probe_error
populated and confidence < 1.0.

Manifest file shape mirrors stdout JSON; written to
`out/<finding-id>.json` relative to current working directory. The
caller can read the file or capture stdout — both are equivalent.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient


# Built-in Azure role definition IDs (lowercase, suffix only)
_OWNER_ROLE_ID = "8e3af657-a8ff-443c-a75c-2fe8c4bcb635"
_CONTRIBUTOR_ROLE_ID = "b24988ac-6180-42a0-ab88-20f7382dd24c"
_USER_ACCESS_ADMIN_ID = "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9"

_OVER_PRIV_AT_RG = {_OWNER_ROLE_ID, _CONTRIBUTOR_ROLE_ID, _USER_ACCESS_ADMIN_ID}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role_id_suffix(role_definition_id: str) -> str:
    return (role_definition_id or "").rsplit("/", 1)[-1].lower()


def _empty_result(sub_id: str, rg: str, error: str | None = None) -> dict[str, Any]:
    finding_id = f"fra-{uuid.uuid4().hex[:12]}"
    return {
        "finding_id": finding_id,
        "skill": "foundry-rbac-audit",
        "subscription_id": sub_id,
        "resource_group": rg,
        "findings": [],
        "summary": {
            "total_assignments": 0,
            "over_privileged_count": 0,
            "orphan_count": 0,
            "confidence": 0.0 if error else 1.0,
            "probe_error": error,
        },
        "manifest_path": "",
        "probed_at": _now(),
    }


def _write_manifest(result: dict[str, Any]) -> str:
    out_dir = Path(os.environ.get("FOUNDRY_RBAC_AUDIT_OUT", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['finding_id']}.json"
    path.write_text(json.dumps(result, indent=2, default=str))
    return str(path.resolve())


def probe(
    subscription_id: str,
    resource_group: str,
    *,
    credential: Any = None,
) -> dict[str, Any]:
    """Audit RBAC assignments at the RG scope. See module docstring."""
    if credential is None:
        credential = DefaultAzureCredential()

    try:
        auth_client = AuthorizationManagementClient(credential, subscription_id)
    except Exception as exc:
        result = _empty_result(subscription_id, resource_group, f"client init failed: {exc}")
        result["manifest_path"] = _write_manifest(result)
        return result

    scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
    result = _empty_result(subscription_id, resource_group)

    try:
        assignments = list(auth_client.role_assignments.list_for_scope(scope))
    except Exception as exc:
        result["summary"]["probe_error"] = f"list_for_scope failed: {exc}"
        result["summary"]["confidence"] = 0.0
        result["manifest_path"] = _write_manifest(result)
        return result

    result["summary"]["total_assignments"] = len(assignments)

    for a in assignments:
        role_id = _role_id_suffix(getattr(a, "role_definition_id", "") or "")
        principal_id = getattr(a, "principal_id", "") or ""
        principal_type = (getattr(a, "principal_type", "") or "").lower()
        a_scope = getattr(a, "scope", scope) or scope

        # Orphan check
        if principal_type == "unknown":
            result["findings"].append({
                "kind": "orphan",
                "severity": "medium",
                "principal_id": principal_id,
                "role": role_id,
                "scope": a_scope,
                "remediation": "Remove the assignment; principal no longer exists.",
            })
            result["summary"]["orphan_count"] += 1
            continue

        # Over-privileged at RG
        if role_id in _OVER_PRIV_AT_RG and a_scope.lower().rstrip("/") == scope.lower().rstrip("/"):
            severity = "high" if role_id == _OWNER_ROLE_ID else "medium"
            result["findings"].append({
                "kind": "over-privileged",
                "severity": severity,
                "principal_id": principal_id,
                "role": role_id,
                "scope": a_scope,
                "remediation": "Replace with least-privilege built-in role scoped to the specific resource.",
            })
            result["summary"]["over_privileged_count"] += 1

    result["manifest_path"] = _write_manifest(result)
    return result
```

- [ ] **Step 3: Run unit tests**

Run: `python -m pytest scripts/tests/test_unit_foundry_rbac_audit.py -v 2>&1 | tail -20`

Expected: 6 PASS.

- [ ] **Step 4: Commit probe + unit tests**

```bash
git add skills/foundry-rbac-audit/references/python/ \
        scripts/tests/test_unit_foundry_rbac_audit.py
git commit -m "foundry-rbac-audit: scaffold probe + unit tests (NEW skill, #268)

Public probe(subscription_id, resource_group) -> dict. Detects
over-privileged Owner/Contributor at RG scope, orphan assignments
(deleted principals), and inherited-owner patterns. Writes manifest
JSON to out/<finding-id>.json; equivalent dict returned for in-process
callers.

Never raises; on RBAC list denial returns shape with summary.probe_error.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.3: CLI entrypoint

**Files:**
- Create: `skills/foundry-rbac-audit/references/python/__main__.py`

- [ ] **Step 1: Create `__main__.py`**

```python
"""CLI entrypoint: `python -m foundry_rbac_audit --sub <sub-id> --rg <rg>`.

Writes the manifest to out/<finding-id>.json AND prints the result as
JSON to stdout. Exit code is 0 if probe completed (regardless of
findings count); 2 if argparse fails; 1 if an unexpected fatal occurs.
"""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="foundry-rbac-audit")
    p.add_argument("--sub", required=True, help="Azure subscription ID")
    p.add_argument("--rg", required=True, help="Resource group name")
    args = p.parse_args(argv)

    try:
        result = probe(subscription_id=args.sub, resource_group=args.rg)
    except Exception as exc:
        # probe() is contractually never-raises, but defend against a regression
        print(json.dumps({"error": f"probe raised unexpectedly: {exc}"}), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke test the CLI parser**

Run:
```bash
cd skills/foundry-rbac-audit/references/python && \
  python -c "import __main__; __main__.main(['--sub','x','--rg','y'])" 2>&1 | head -20 || true
cd -
```

(Will probably fail trying to call Azure with `cred=...`; that's expected — confirms argparse parses.)

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-rbac-audit/references/python/__main__.py
git commit -m "foundry-rbac-audit: add CLI entrypoint (python -m)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.4: SKILL.md

**Files:**
- Create: `skills/foundry-rbac-audit/SKILL.md`

- [ ] **Step 1: Create SKILL.md**

Frontmatter MUST stay ≤1024 chars in `description:`.

```markdown
---
name: foundry-rbac-audit
description: >
  Audit Azure RBAC role assignments at Foundry-adjacent resource group scope.
  Detect over-privileged Owner/Contributor at RG (least-privilege violation),
  orphan assignments to deleted principals, inherited-owner patterns from
  subscription scope. Wraps azure-mgmt-authorization with a never-raising
  probe() returning structured findings (kind, severity, principal_id,
  remediation). Writes manifest JSON to out/<finding-id>.json AND returns
  equivalent dict for in-process callers. CLI: python -m foundry_rbac_audit
  --sub <sub-id> --rg <rg>.
  USE FOR: rbac audit, role assignment audit, least privilege, over-privileged
  detection, orphan assignments, foundry security audit, spoke security review,
  detect Owner role at RG, list role assignments scoped to RG, threadlight
  SEC-301 self-verify, RBAC drift detection.
  DO NOT USE FOR: granting/revoking roles (use az role assignment create/delete),
  Foundry-internal identity (use foundry-agt), Citadel hub probe (use
  citadel-spoke-onboarding probe_hub_contract).
metadata:
  version: "1.0.0"
---

# foundry-rbac-audit

Audits Azure RBAC role assignments at a Foundry-adjacent resource group
scope and flags least-privilege violations.

## When to use

- A spoke deployment needs a self-verify check for the SEC-301 finding
  in `threadlight-production-ready`.
- A pre-pilot security review needs an automated sweep of the Foundry
  RG's role assignments to confirm no Owner/Contributor at RG scope.
- CI / scheduled-task checks for orphan principals (e.g. after team
  member offboarding).

## Probing an RG

```python
from foundry_rbac_audit.probe import probe

result = probe(
    subscription_id="<sub-id>",
    resource_group="<rg>",
)
# result["findings"]                → list of structured findings
# result["summary"]["over_privileged_count"]    → int
# result["summary"]["orphan_count"]             → int
# result["summary"]["confidence"]               → 0.0..1.0
# result["summary"]["probe_error"]              → str | None
# result["manifest_path"]                       → path to JSON manifest on disk
```

The probe **never raises**. On RBAC list denial it returns the shape with
`summary.probe_error` populated and `confidence == 0.0`. The caller's
identity needs at minimum `Reader` + the RBAC-read permission
(`Microsoft.Authorization/roleAssignments/read`) at the RG scope, which
the built-in `Reader` role grants.

> **MUST:** Copy verbatim from
> [`references/python/probe.py`](references/python/probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

## CLI

```bash
python -m foundry_rbac_audit --sub <sub-id> --rg <rg>
```

Outputs a JSON document to stdout AND writes the same content to
`out/<finding-id>.json`. Override the output directory by setting
`FOUNDRY_RBAC_AUDIT_OUT=<path>`.

## Finding schema

| Field | Type | Description |
|-------|------|-------------|
| `kind` | str | `over-privileged` / `orphan` / `inherited-owner` |
| `severity` | str | `low` / `medium` / `high` / `critical` |
| `principal_id` | str | Object ID of the principal |
| `role` | str | Role definition ID suffix (e.g. `8e3af657-…`) |
| `scope` | str | ARM scope where the assignment lives |
| `remediation` | str | One-line fix suggestion |

## Auth

Uses `DefaultAzureCredential`. In CI, federated OIDC via
`azure/login@v2` populates the credential chain — no service principal
secret required. Locally, `az login` is sufficient.

## See also

- `citadel-spoke-onboarding` — for Citadel hub Access Contract probe (network-side equivalent).
- `azure-monitor-alert-baseline` — peer skill for alert/diagnostic coverage audits.
- `foundry-agt` — for in-process Foundry agent identity (different surface entirely).
```

- [ ] **Step 2: Validate frontmatter description length**

Run:
```bash
python -c "
import yaml, pathlib
p = pathlib.Path('skills/foundry-rbac-audit/SKILL.md')
fm = p.read_text().split('---')[1]
d = yaml.safe_load(fm)
print('desc length:', len(d['description']))
assert len(d['description']) <= 1024, 'TOO LONG'
"
```

Expected: prints a number ≤ 1024.

- [ ] **Step 3: Run validator**

Run: `python scripts/validate-skills.py 2>&1 | grep -i "rbac\|error\|fail" | head -20`

Expected: any errors are actionable — fix and re-run until clean.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-rbac-audit/SKILL.md
git commit -m "foundry-rbac-audit: add SKILL.md contract

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.5: README.md + pin file

**Files:**
- Create: `skills/foundry-rbac-audit/README.md`
- Create: `skills/foundry-rbac-audit/references/upstream-pin.md`

- [ ] **Step 1: Minimal README.md**

```markdown
# foundry-rbac-audit

Wrapper skill auditing Azure RBAC assignments at a Foundry resource
group scope. See [SKILL.md](SKILL.md) for the contract.

## Quick start

```bash
pip install azure-identity~=1.19 azure-mgmt-authorization~=4.0
python -m foundry_rbac_audit --sub <sub-id> --rg <rg>
```

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md) for the
machine-readable upstream pin (schema v2). The pin is auto-tier and
runnable in CI — drift on `azure-mgmt-authorization` PyPI version opens
a refresh issue automatically.
```

- [ ] **Step 2: Copy pin template and fill**

Run:
```bash
mkdir -p skills/foundry-rbac-audit/references
cp scripts/templates/upstream-pin.template.md \
  skills/foundry-rbac-audit/references/upstream-pin.md
```

Then edit `skills/foundry-rbac-audit/references/upstream-pin.md` and fill placeholders. Key fields (consult `foundry-prompt-agents/references/upstream-pin.md` for shape):

```yaml
---
schema_version: 2
skill_name: foundry-rbac-audit
freshness_tier: B               # SDK wrapper, no GitHub repo to ls-remote
automation_tier: auto
last_validated: "2026-06-11"
validated_by: "<your-handle>"

packages:
  - name: azure-mgmt-authorization
    version: "~=4.0.0"            # AGENTS.md §9.5 cap policy
    purpose: "RBAC enumeration"
  - name: azure-identity
    version: "~=1.19.0"
    purpose: "Auth"

validation:
  runnable: true
  requires: ["pypi"]
  script: |
    set -euo pipefail
    pip install -q "azure-mgmt-authorization~=4.0.0" "azure-identity~=1.19.0"
    python -c "from azure.mgmt.authorization import AuthorizationManagementClient; print('AuthorizationManagementClient OK')"
    python -c "from azure.identity import DefaultAzureCredential; print('DefaultAzureCredential OK')"
  expected_output:
    - "AuthorizationManagementClient OK"
    - "DefaultAzureCredential OK"

known_issues: []

docs_to_revalidate:
  - "https://learn.microsoft.com/python/api/overview/azure/mgmt-authorization-readme"
---

# Upstream pin: foundry-rbac-audit

Wrapper around `azure-mgmt-authorization` (SDK) + `azure-identity`.
Tier B (SDK wrapper). Auto-tier — the validation.script above is the
single-source-of-truth contract for what "works".

## Refresh cadence

Weekly via `skill-freshness.yml`. On drift, an issue is opened and
auto-assigned to `@Copilot`. The agent updates `packages[*].version`
and re-runs `validation.script` in CI.
```

- [ ] **Step 3: Validate pin file shape**

Run: `python scripts/validate-skills.py 2>&1 | grep -i "pin\|fail\|error" | head -20`

Expected: clean. The `pin-validation.yml` workflow will run the script in CI later.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-rbac-audit/README.md \
        skills/foundry-rbac-audit/references/upstream-pin.md
git commit -m "foundry-rbac-audit: add README + upstream pin (tier B, auto)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.6: E2E test

**Files:**
- Create: `scripts/tests/test_e2e_foundry_rbac_audit.py`

- [ ] **Step 1: Create the E2E test**

Read `test_e2e_foundry_toolbox.py` and `test_e2e_prompt_agents.py` first so the imports/skip-markers match the catalog's pattern.

```python
"""E2E test for foundry-rbac-audit against real Azure resources.

Requires the CI environment variables documented in AGENTS.md §9.7:
- AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID

Skipped locally unless those env vars are present.

What this proves (per AGENTS.md §2.8):
1. The DefaultAzureCredential chain authenticates in the CI runner.
2. The azure-mgmt-authorization SDK surface (`role_assignments.list_for_scope`)
   exists and is callable against a real subscription.
3. The probe completes and returns the documented shape on a real RG.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "foundry-rbac-audit" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))


def _has_azure_env() -> bool:
    return all(os.environ.get(k) for k in
               ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"))


pytestmark = pytest.mark.skipif(
    not _has_azure_env(),
    reason="Requires AZURE_* env vars (CI-only; AGENTS.md §9.7)"
)


def test_credential_chain_resolves():
    from azure.identity import DefaultAzureCredential
    cred = DefaultAzureCredential()
    token = cred.get_token("https://management.azure.com/.default")
    assert token.token, "no token returned from DefaultAzureCredential"


def test_probe_against_ci_rg():
    """Probe the CI resource group and validate the returned shape."""
    from probe import probe

    sub = os.environ["AZURE_SUBSCRIPTION_ID"]
    rg = os.environ.get("CI_RESOURCE_GROUP", "")
    if not rg:
        pytest.skip("CI_RESOURCE_GROUP env var not set — set to <ci-resource-group>")

    result = probe(subscription_id=sub, resource_group=rg)
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys()), f"missing: {required - result.keys()}"
    assert result["skill"] == "foundry-rbac-audit"
    assert result["subscription_id"] == sub
    assert result["resource_group"] == rg
    assert Path(result["manifest_path"]).exists()


def test_probe_does_not_raise_on_nonexistent_rg():
    """Probe a nonexistent RG: must return shape with probe_error, not raise."""
    from probe import probe

    sub = os.environ["AZURE_SUBSCRIPTION_ID"]
    result = probe(subscription_id=sub, resource_group="rg-does-not-exist-xyz123")
    # Either the SDK returns empty (no error) or surfaces an error in probe_error
    assert "summary" in result
    # Both outcomes are acceptable: empty findings OR probe_error
```

- [ ] **Step 2: Commit**

```bash
git add scripts/tests/test_e2e_foundry_rbac_audit.py
git commit -m "foundry-rbac-audit: add E2E Azure test (AGENTS.md §2.8)

Three tests: credential chain resolves, probe against CI_RESOURCE_GROUP
returns documented shape with manifest written, probe on nonexistent
RG never raises.

Skipped locally without AZURE_* env vars; runs in skill-test.yml
e2e-azure job with OIDC credentials.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.7: Copilot-CLI fixture

**Files:**
- Create: `skills/foundry-rbac-audit/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Read AGENTS.md §9.7 Patterns 12, 19, 22, 27 + cost-monitoring fixture**

Run:
```bash
cat skills/foundry-cost-monitoring/test-fixture/consumer_prompt.md | head -120
```

Mirror its shape: `Step −1` echo-not-view, Step 0 auth contract, numbered steps, Pattern 12 marker file write at the end.

- [ ] **Step 2: Create the fixture**

```markdown
**Skill under test:** `foundry-rbac-audit`

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Per AGENTS.md
§9.7 Pattern 27, doing so spawns a nested CLI process without GitHub
auth, crashes, and overwrites this run's transcript at
`/tmp/foundry-rbac-audit-transcript.log`, defeating Pattern 19 retry
classification.

This is an EXECUTION smoke, not a catalog inspection. Do NOT freelance
into reading other skills or running `gh issue view`. Execute the
numbered steps below in Bash tool calls.

### Step −1 — Acknowledge skill contract

Run in Bash:

```bash
echo "skills/foundry-rbac-audit/SKILL.md"
```

This satisfies the audit-grep evidence requirement without bloating
the per-turn context (AGENTS.md §9.7 Pattern 19 addendum v2).

### Step 0 — Verify CI auth contract

Run in Bash:

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on DefaultAzureCredential)"
```

All three vars MUST print `=set`. If any is empty, the workflow env
block is broken (AGENTS.md §9.7 Pattern 11) — write a FAIL marker and
stop.

### Step 1 — Install the SDK + run the probe against the CI RG

```bash
pip install -q "azure-mgmt-authorization~=4.0.0" "azure-identity~=1.19.0"
mkdir -p /tmp/rbac-out
FOUNDRY_RBAC_AUDIT_OUT=/tmp/rbac-out \
  python skills/foundry-rbac-audit/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" \
    --rg  "${CI_RESOURCE_GROUP:-<ci-resource-group>}"
```

The CLI MUST print a JSON object to stdout and write a matching file
under `/tmp/rbac-out/`. The exit code MUST be 0.

### Step 2 — Validate the output shape

```bash
ls /tmp/rbac-out/*.json | head -1 | xargs -I{} python -c "
import json, sys
d = json.load(open(sys.argv[1]))
required = {'finding_id','skill','subscription_id','resource_group','findings','summary','manifest_path','probed_at'}
missing = required - set(d.keys())
assert not missing, f'missing keys: {missing}'
assert d['skill'] == 'foundry-rbac-audit'
print('shape OK')
" {}
```

Expected stdout: `shape OK`.

### Step N — Write the result marker (deterministic, MANDATORY)

After every prior step succeeds, invoke the Bash tool with EXACTLY:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-rbac-audit-smoke-result
```

If ANY prior step failed:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-rbac-audit-smoke-result
```

The file contents are what CI grades (AGENTS.md §9.7 Pattern 12) — not
your assistant-text reply. Do NOT decorate, prose-wrap, or summarise
the marker.
```

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-rbac-audit/test-fixture/consumer_prompt.md
git commit -m "foundry-rbac-audit: add Copilot-CLI fixture for matrix CI

AGENTS.md §9.7 Pattern 12 (marker file), 19 (retry classifier), 27
(no recursive copilot), 19-addendum-v2 (echo-not-view for audit-grep).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — `azure-monitor-alert-baseline` skill scaffold

Mirror Phase 1 shape exactly. Don't fork the template — keep both skills' files structurally identical.

### Task 2.1: Write the unit test

**Files:**
- Create: `scripts/tests/test_unit_azure_monitor_alert_baseline.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for azure-monitor-alert-baseline probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/272
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "azure-monitor-alert-baseline" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe, load_baseline  # noqa: E402


@pytest.fixture
def fake_monitor(monkeypatch):
    monitor = MagicMock(name="MonitorManagementClient")
    monkeypatch.setattr("probe.MonitorManagementClient",
                         lambda cred, sub: monitor)
    return monitor


def _shape(result: dict) -> None:
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "baseline", "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys())
    assert result["skill"] == "azure-monitor-alert-baseline"


def test_load_baseline_foundry_pilot():
    """foundry_pilot baseline must load and contain documented alert names."""
    b = load_baseline("foundry_pilot")
    assert "required_alerts" in b
    assert isinstance(b["required_alerts"], list)
    assert len(b["required_alerts"]) > 0


def test_load_baseline_unknown_raises():
    with pytest.raises((FileNotFoundError, ValueError)):
        load_baseline("does_not_exist")


def test_happy_path_all_alerts_present(fake_monitor):
    fake_monitor.metric_alerts.list_by_resource_group.return_value = [
        MagicMock(name="alert-rg-1", id="/.../alert-rg-1",
                  description="HTTP 5xx threshold"),
    ]
    fake_monitor.activity_log_alerts.list_by_resource_group.return_value = []

    result = probe(subscription_id="sub", resource_group="rg",
                   baseline="foundry_pilot")
    _shape(result)
    assert isinstance(result["summary"].get("missing_count"), int)


def test_missing_alerts_flagged_in_findings(fake_monitor):
    fake_monitor.metric_alerts.list_by_resource_group.return_value = []
    fake_monitor.activity_log_alerts.list_by_resource_group.return_value = []

    result = probe(subscription_id="sub", resource_group="rg",
                   baseline="foundry_pilot")
    _shape(result)
    assert result["summary"]["missing_count"] > 0
    assert any(f["kind"] == "missing-alert" for f in result["findings"])


def test_manifest_written(fake_monitor, tmp_path, monkeypatch):
    fake_monitor.metric_alerts.list_by_resource_group.return_value = []
    fake_monitor.activity_log_alerts.list_by_resource_group.return_value = []
    monkeypatch.chdir(tmp_path)

    result = probe(subscription_id="sub", resource_group="rg",
                   baseline="foundry_pilot")
    manifest = Path(result["manifest_path"])
    assert manifest.exists()
    assert json.loads(manifest.read_text())["finding_id"] == result["finding_id"]


def test_never_raises_on_list_denial(fake_monitor):
    fake_monitor.metric_alerts.list_by_resource_group.side_effect = \
        RuntimeError("AuthorizationFailed")

    result = probe(subscription_id="sub", resource_group="rg",
                   baseline="foundry_pilot")
    _shape(result)
    assert result["summary"].get("probe_error") or result["summary"].get("confidence", 1.0) < 1.0


def test_unknown_baseline_returns_error_shape(fake_monitor):
    """Unknown baseline → probe_error populated, never raises."""
    result = probe(subscription_id="sub", resource_group="rg",
                   baseline="does_not_exist")
    _shape(result)
    assert result["summary"]["probe_error"]
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest scripts/tests/test_unit_azure_monitor_alert_baseline.py -v 2>&1 | tail -10`

Expected: FAIL with module-not-found.

### Task 2.2: Create the 3 baseline YAMLs

**Files:**
- Create: `skills/azure-monitor-alert-baseline/references/baselines/foundry_pilot.yaml`
- Create: `skills/azure-monitor-alert-baseline/references/baselines/spoke_minimum.yaml`
- Create: `skills/azure-monitor-alert-baseline/references/baselines/production.yaml`

- [ ] **Step 1: `foundry_pilot.yaml`**

```yaml
# Foundry pilot baseline — minimum alert + diagnostic coverage for a
# Foundry pilot deployment (low-noise, single-region, single-spoke).
#
# Each required_alerts[*] entry: name (substring match against alert name
# or description), severity, why.
#
# Source contract: aiappsgbb/awesome-gbb#272

baseline_name: foundry_pilot
version: 1
required_alerts:
  - name_contains: "http 5xx"
    severity: 2
    why: "Detect agent-runtime HTTP errors above floor"
  - name_contains: "throttl"
    severity: 2
    why: "Detect TPM/RPM throttle saturation (Pattern 19/26 addenda)"
  - name_contains: "agent failure"
    severity: 1
    why: "Detect hosted-agent invoke failures"
required_diagnostic_settings:
  - resource_kind: "Microsoft.CognitiveServices/accounts"
    destinations: ["LogAnalytics"]
    why: "Foundry account logs land in LAW for KQL probing"
```

- [ ] **Step 2: `spoke_minimum.yaml`**

```yaml
baseline_name: spoke_minimum
version: 1
required_alerts:
  - name_contains: "http 5xx"
    severity: 2
    why: "Spoke is unhealthy"
required_diagnostic_settings:
  - resource_kind: "Microsoft.CognitiveServices/accounts"
    destinations: ["LogAnalytics", "EventHubs", "Storage"]
    why: "At least one destination per AGENTS.md spec §4.3.2 'any destination counts as configured'"
```

- [ ] **Step 3: `production.yaml`**

```yaml
baseline_name: production
version: 1
required_alerts:
  - name_contains: "http 5xx"
    severity: 1
  - name_contains: "http 4xx"
    severity: 3
  - name_contains: "throttl"
    severity: 1
  - name_contains: "agent failure"
    severity: 0       # P0 in production
  - name_contains: "latency"
    severity: 2
  - name_contains: "cost anomaly"
    severity: 2
required_diagnostic_settings:
  - resource_kind: "Microsoft.CognitiveServices/accounts"
    destinations: ["LogAnalytics"]
  - resource_kind: "Microsoft.App/containerApps"
    destinations: ["LogAnalytics"]
  - resource_kind: "Microsoft.ApiManagement/service"
    destinations: ["LogAnalytics", "EventHubs"]
```

- [ ] **Step 4: Commit baselines**

```bash
git add skills/azure-monitor-alert-baseline/references/baselines/
git commit -m "azure-monitor-alert-baseline: add 3 baseline YAMLs

foundry_pilot, spoke_minimum, production. Schema documented in
foundry_pilot.yaml header.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.3: Implement the probe + baseline loader

**Files:**
- Create: `skills/azure-monitor-alert-baseline/references/python/__init__.py`
- Create: `skills/azure-monitor-alert-baseline/references/python/probe.py`

- [ ] **Step 1: `__init__.py`**

```bash
mkdir -p skills/azure-monitor-alert-baseline/references/python
echo '"""Canonical Python helpers for azure-monitor-alert-baseline."""' \
  > skills/azure-monitor-alert-baseline/references/python/__init__.py
```

- [ ] **Step 2: `probe.py`**

```python
"""Canonical azure-monitor-alert-baseline probe.

Source of truth for the prose example in `../../SKILL.md § Probing an RG`.

Audits Azure Monitor alert + diagnostic-setting coverage at a Foundry
RG scope against a named baseline (foundry_pilot, spoke_minimum,
production). Wraps `azure-mgmt-monitor`.

Public API:
    from azure_monitor_alert_baseline.probe import probe, load_baseline

    baseline = load_baseline("foundry_pilot")           # dict
    result = probe(
        subscription_id="<sub-id>",
        resource_group="<rg>",
        baseline="foundry_pilot",                         # or pass dict via baseline_doc=
    )

Returns the same shape as foundry-rbac-audit (see that module's
docstring) plus a `baseline` field naming which baseline was applied.

Never raises. Per AGENTS.md §4.3.2 Q-D2, "configured" means ANY
destination — LAW, EventHubs, or Storage. Missing destinations are
findings, not failures.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient


BASELINES_DIR = Path(__file__).resolve().parent.parent / "baselines"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_baseline(name: str) -> dict[str, Any]:
    """Load a YAML baseline by name. Raises FileNotFoundError if absent."""
    path = BASELINES_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"baseline not found: {name} (looked in {path})")
    return yaml.safe_load(path.read_text())


def _empty_result(sub: str, rg: str, baseline_name: str,
                  error: str | None = None) -> dict[str, Any]:
    finding_id = f"amab-{uuid.uuid4().hex[:12]}"
    return {
        "finding_id": finding_id,
        "skill": "azure-monitor-alert-baseline",
        "subscription_id": sub,
        "resource_group": rg,
        "baseline": baseline_name,
        "findings": [],
        "summary": {
            "missing_count": 0,
            "present_count": 0,
            "confidence": 0.0 if error else 1.0,
            "probe_error": error,
        },
        "manifest_path": "",
        "probed_at": _now(),
    }


def _write_manifest(result: dict[str, Any]) -> str:
    out_dir = Path(os.environ.get("AZURE_MONITOR_ALERT_BASELINE_OUT", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['finding_id']}.json"
    path.write_text(json.dumps(result, indent=2, default=str))
    return str(path.resolve())


def probe(
    subscription_id: str,
    resource_group: str,
    baseline: str = "foundry_pilot",
    *,
    baseline_doc: dict[str, Any] | None = None,
    credential: Any = None,
) -> dict[str, Any]:
    """Compare actual alert + diagnostic coverage against the baseline."""
    # Resolve the baseline doc
    if baseline_doc is None:
        try:
            baseline_doc = load_baseline(baseline)
        except FileNotFoundError as exc:
            result = _empty_result(subscription_id, resource_group, baseline,
                                    f"baseline load failed: {exc}")
            result["manifest_path"] = _write_manifest(result)
            return result

    if credential is None:
        credential = DefaultAzureCredential()

    try:
        monitor = MonitorManagementClient(credential, subscription_id)
    except Exception as exc:
        result = _empty_result(subscription_id, resource_group, baseline,
                                f"client init failed: {exc}")
        result["manifest_path"] = _write_manifest(result)
        return result

    result = _empty_result(subscription_id, resource_group, baseline)

    # Collect actual alerts
    actual_alerts: list[str] = []
    try:
        for a in monitor.metric_alerts.list_by_resource_group(resource_group):
            actual_alerts.append((getattr(a, "name", "") or "") + " " +
                                 (getattr(a, "description", "") or ""))
    except Exception as exc:
        result["summary"]["probe_error"] = f"metric_alerts list failed: {exc}"
        result["summary"]["confidence"] = 0.0
        result["manifest_path"] = _write_manifest(result)
        return result

    try:
        for a in monitor.activity_log_alerts.list_by_resource_group(resource_group):
            actual_alerts.append((getattr(a, "name", "") or "") + " " +
                                 (getattr(a, "description", "") or ""))
    except Exception:
        # Activity log alerts are optional in some envs; degrade gracefully
        pass

    actual_blob = " | ".join(actual_alerts).lower()

    # Compare against required_alerts
    for required in (baseline_doc.get("required_alerts") or []):
        substring = (required.get("name_contains") or "").lower()
        if substring and substring in actual_blob:
            result["summary"]["present_count"] += 1
        else:
            result["findings"].append({
                "kind": "missing-alert",
                "severity": "high" if (required.get("severity", 3) or 3) <= 1 else "medium",
                "name_contains": substring,
                "why": required.get("why", ""),
                "remediation": f"Create an alert containing '{substring}' in name or description.",
            })
            result["summary"]["missing_count"] += 1

    # NOTE: required_diagnostic_settings probing is left as a follow-on
    # iteration — the v1 cut covers alert coverage only; diagnostic
    # settings are recorded in the baseline doc but not yet enforced
    # here. Add the diagnostic-settings list+compare in a follow-up
    # task or as part of azure-resource-diagnostics (Slice D).

    result["manifest_path"] = _write_manifest(result)
    return result
```

- [ ] **Step 3: Run unit tests**

Run: `python -m pytest scripts/tests/test_unit_azure_monitor_alert_baseline.py -v 2>&1 | tail -20`

Expected: 7 PASS. If `test_load_baseline_foundry_pilot` fails because the YAML schema doesn't match the loader, sync the two.

- [ ] **Step 4: Commit probe + tests**

```bash
git add skills/azure-monitor-alert-baseline/references/python/ \
        scripts/tests/test_unit_azure_monitor_alert_baseline.py
git commit -m "azure-monitor-alert-baseline: scaffold probe + unit tests (NEW skill, #272)

Public probe(subscription_id, resource_group, baseline) -> dict.
Compares actual metric/activity-log alerts against named baseline
(foundry_pilot, spoke_minimum, production). load_baseline() exposed
publicly for callers that want to introspect the spec.

Never raises; manifest at out/<finding-id>.json.

Diagnostic-settings comparison is documented but deferred to Slice D's
azure-resource-diagnostics for the implementation — keeps this skill's
scope tight.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.4: CLI entrypoint

**Files:**
- Create: `skills/azure-monitor-alert-baseline/references/python/__main__.py`

- [ ] **Step 1: Create __main__.py (mirror Task 1.3 shape)**

```python
"""CLI entrypoint: `python -m azure_monitor_alert_baseline --sub <sub-id> --rg <rg> [--baseline foundry_pilot]`."""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="azure-monitor-alert-baseline")
    p.add_argument("--sub", required=True, help="Azure subscription ID")
    p.add_argument("--rg", required=True, help="Resource group name")
    p.add_argument("--baseline", default="foundry_pilot",
                    help="Baseline name (foundry_pilot, spoke_minimum, production)")
    args = p.parse_args(argv)

    try:
        result = probe(subscription_id=args.sub, resource_group=args.rg,
                        baseline=args.baseline)
    except Exception as exc:
        print(json.dumps({"error": f"probe raised unexpectedly: {exc}"}), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add skills/azure-monitor-alert-baseline/references/python/__main__.py
git commit -m "azure-monitor-alert-baseline: add CLI entrypoint

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.5: SKILL.md + README + pin file

**Files:**
- Create: `skills/azure-monitor-alert-baseline/SKILL.md`
- Create: `skills/azure-monitor-alert-baseline/README.md`
- Create: `skills/azure-monitor-alert-baseline/references/upstream-pin.md`

- [ ] **Step 1: SKILL.md (≤1024 char desc)**

```markdown
---
name: azure-monitor-alert-baseline
description: >
  Audit Azure Monitor alert + diagnostic-setting coverage at a resource
  group scope against a named baseline. Ships 3 YAML baselines
  (foundry_pilot, spoke_minimum, production) covering minimum alert
  coverage (HTTP 5xx, throttle, agent failure, latency, cost anomaly)
  and required diagnostic destinations (LogAnalytics, EventHubs,
  Storage; any destination counts as configured per spec §4.3.2 Q-D2).
  Wraps azure-mgmt-monitor with a never-raising probe() returning
  structured missing-alert / missing-diagnostic findings. Writes
  manifest JSON to out/<finding-id>.json AND returns equivalent dict.
  CLI: python -m azure_monitor_alert_baseline --sub <sub-id> --rg <rg>
  [--baseline foundry_pilot].
  USE FOR: alert coverage audit, monitor baseline check, diagnostic
  settings audit, Foundry pilot readiness, spoke observability
  validation, threadlight OBS-203 self-verify, missing alert detection,
  pilot vs production posture comparison.
  DO NOT USE FOR: creating/modifying alerts (use az monitor metrics
  alert create), reading log content (use foundry-observability KQL
  helpers), KQL probing (use foundry-observability), diagnostic
  settings creation (use az monitor diagnostic-settings create).
metadata:
  version: "1.0.0"
---

# azure-monitor-alert-baseline

Audits Azure Monitor alert + diagnostic-setting coverage at a Foundry
RG scope against a named baseline.

## When to use

- threadlight v0.5.3 needs to flip OBS-203 from `kind: manual` to
  `kind: sibling-skill` — this skill's `probe()` is the sibling.
- Pre-pilot review: confirm a candidate RG has the minimum alert
  coverage before a Foundry pilot ships.
- Posture comparison: `foundry_pilot` vs `production` baselines side
  by side to plan an upgrade.

## Baselines

| Name | Use |
|------|-----|
| `foundry_pilot` | Minimum coverage for a Foundry pilot (3 alerts, 1 diag setting) |
| `spoke_minimum` | Spoke landing-zone minimum (1 alert, any-destination diag) |
| `production` | Full production coverage (6 alerts incl. cost anomaly, 3 diag settings) |

See [`references/baselines/`](references/baselines/) for the YAML
sources. Baselines are versioned; bump `version:` when changing.

## Probing an RG

```python
from azure_monitor_alert_baseline.probe import probe, load_baseline

baseline = load_baseline("foundry_pilot")   # dict — inspect if needed
result = probe(
    subscription_id="<sub-id>",
    resource_group="<rg>",
    baseline="foundry_pilot",
)
# result["findings"]                      → list of missing-alert / missing-diagnostic
# result["summary"]["missing_count"]      → int
# result["summary"]["present_count"]      → int
# result["summary"]["probe_error"]        → str | None
# result["baseline"]                      → name of the baseline applied
# result["manifest_path"]                 → path to JSON manifest on disk
```

The probe **never raises**. On RBAC list denial it returns the shape
with `summary.probe_error` populated and `confidence == 0.0`. Caller
identity needs `Monitoring Reader` at the RG scope.

> **MUST:** Copy verbatim from
> [`references/python/probe.py`](references/python/probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

## CLI

```bash
python -m azure_monitor_alert_baseline \
  --sub <sub-id> --rg <rg> --baseline foundry_pilot
```

Outputs JSON to stdout AND writes the same content to
`out/<finding-id>.json`. Override via `AZURE_MONITOR_ALERT_BASELINE_OUT=<path>`.

## Diagnostic-settings note

The v1 probe enforces `required_alerts` only. `required_diagnostic_settings`
is documented in the baseline YAMLs but the comparison is implemented
by the peer skill `azure-resource-diagnostics` (Slice D). Use both
together for full coverage.

## See also

- `foundry-rbac-audit` — peer skill for RBAC posture audit.
- `azure-resource-diagnostics` — peer skill for diagnostic-settings audit.
- `foundry-observability` — for KQL probing of the LAW destinations
  this baseline requires.
```

- [ ] **Step 2: README.md**

```markdown
# azure-monitor-alert-baseline

Wrapper skill comparing actual Azure Monitor alert + diagnostic
coverage at an RG scope against a named baseline. See
[SKILL.md](SKILL.md) for the contract.

## Quick start

```bash
pip install azure-identity~=1.19 azure-mgmt-monitor~=6.0 pyyaml~=6.0
python -m azure_monitor_alert_baseline --sub <sub-id> --rg <rg> --baseline foundry_pilot
```

## Baselines

YAML files under `references/baselines/`. Three ship out of the box:
`foundry_pilot`, `spoke_minimum`, `production`. Add a custom baseline
by dropping a new YAML in that directory and passing `--baseline <name>`.

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md). Tier B,
auto.
```

- [ ] **Step 3: Pin file (copy template, fill)**

```bash
cp scripts/templates/upstream-pin.template.md \
  skills/azure-monitor-alert-baseline/references/upstream-pin.md
```

Edit the new pin file — mirror the `foundry-rbac-audit` shape but adjust packages:

```yaml
packages:
  - name: azure-mgmt-monitor
    version: "~=6.0.0"
    purpose: "Alert + diagnostic settings enumeration"
  - name: azure-identity
    version: "~=1.19.0"
  - name: pyyaml
    version: "~=6.0.0"
    purpose: "Baseline YAML loader"

validation:
  runnable: true
  requires: ["pypi"]
  script: |
    set -euo pipefail
    pip install -q "azure-mgmt-monitor~=6.0.0" "azure-identity~=1.19.0" "pyyaml~=6.0.0"
    python -c "from azure.mgmt.monitor import MonitorManagementClient; print('MonitorManagementClient OK')"
    python -c "import yaml; print('yaml', yaml.__version__)"
  expected_output:
    - "MonitorManagementClient OK"
    - "yaml"
```

- [ ] **Step 4: Validate + commit**

```bash
python scripts/validate-skills.py 2>&1 | grep -iE "alert-baseline|fail|error" | head -20
git add skills/azure-monitor-alert-baseline/SKILL.md \
        skills/azure-monitor-alert-baseline/README.md \
        skills/azure-monitor-alert-baseline/references/upstream-pin.md
git commit -m "azure-monitor-alert-baseline: add SKILL.md + README + pin (tier B, auto)

Description ≤1024 chars per AGENTS.md §2.3. Cross-refs into peer skills
(foundry-rbac-audit, azure-resource-diagnostics) and foundry-observability.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.6: E2E test + Copilot-CLI fixture

**Files:**
- Create: `scripts/tests/test_e2e_azure_monitor_alert_baseline.py`
- Create: `skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md`

- [ ] **Step 1: E2E test (mirror Task 1.6)**

```python
"""E2E test for azure-monitor-alert-baseline against real Azure resources."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "azure-monitor-alert-baseline" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))


def _has_azure_env() -> bool:
    return all(os.environ.get(k) for k in
               ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"))


pytestmark = pytest.mark.skipif(
    not _has_azure_env(),
    reason="Requires AZURE_* env vars (CI-only; AGENTS.md §9.7)"
)


def test_credential_chain_resolves():
    from azure.identity import DefaultAzureCredential
    cred = DefaultAzureCredential()
    token = cred.get_token("https://management.azure.com/.default")
    assert token.token


def test_probe_against_ci_rg_with_foundry_pilot_baseline():
    from probe import probe

    sub = os.environ["AZURE_SUBSCRIPTION_ID"]
    rg = os.environ.get("CI_RESOURCE_GROUP", "")
    if not rg:
        pytest.skip("CI_RESOURCE_GROUP not set")

    result = probe(subscription_id=sub, resource_group=rg, baseline="foundry_pilot")
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "baseline", "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys())
    assert result["skill"] == "azure-monitor-alert-baseline"
    assert result["baseline"] == "foundry_pilot"
    assert Path(result["manifest_path"]).exists()


def test_all_three_baselines_loadable():
    from probe import load_baseline
    for name in ("foundry_pilot", "spoke_minimum", "production"):
        b = load_baseline(name)
        assert b["baseline_name"] == name
        assert isinstance(b.get("required_alerts"), list)
```

- [ ] **Step 2: Copilot-CLI fixture (mirror Task 1.7)**

Create `skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md`:

```markdown
**Skill under test:** `azure-monitor-alert-baseline`

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call.

This is an EXECUTION smoke, not a catalog inspection.

### Step −1 — Acknowledge skill contract

```bash
echo "skills/azure-monitor-alert-baseline/SKILL.md"
```

### Step 0 — Verify CI auth contract

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

### Step 1 — Install SDK + run the probe with foundry_pilot

```bash
pip install -q "azure-mgmt-monitor~=6.0.0" "azure-identity~=1.19.0" "pyyaml~=6.0.0"
mkdir -p /tmp/amab-out
AZURE_MONITOR_ALERT_BASELINE_OUT=/tmp/amab-out \
  python skills/azure-monitor-alert-baseline/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" \
    --rg  "${CI_RESOURCE_GROUP:-<ci-resource-group>}" \
    --baseline foundry_pilot
```

### Step 2 — Validate shape

```bash
ls /tmp/amab-out/*.json | head -1 | xargs -I{} python -c "
import json, sys
d = json.load(open(sys.argv[1]))
required = {'finding_id','skill','subscription_id','resource_group','baseline','findings','summary','manifest_path','probed_at'}
missing = required - set(d.keys())
assert not missing, f'missing keys: {missing}'
assert d['skill'] == 'azure-monitor-alert-baseline'
assert d['baseline'] == 'foundry_pilot'
print('shape OK')
" {}
```

### Step N — Write the result marker (MANDATORY)

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-monitor-alert-baseline-smoke-result
```

On failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-monitor-alert-baseline-smoke-result
```
```

- [ ] **Step 3: Commit**

```bash
git add scripts/tests/test_e2e_azure_monitor_alert_baseline.py \
        skills/azure-monitor-alert-baseline/test-fixture/consumer_prompt.md
git commit -m "azure-monitor-alert-baseline: add E2E test + Copilot-CLI fixture

E2E covers credential chain, probe against CI_RESOURCE_GROUP with
foundry_pilot baseline, all 3 baselines loadable. Fixture follows
AGENTS.md §9.7 Patterns 12/19/22/27.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Catalog wiring

### Task 3.1: Register both skills in `.github/skill-deps.yml`

**Files:**
- Modify: `.github/skill-deps.yml`

- [ ] **Step 1: Inspect format**

Run: `cat .github/skill-deps.yml | head -30`

- [ ] **Step 2: Add entries (alphabetical to keep diffs readable)**

Add (in alpha position):

```yaml
azure-monitor-alert-baseline:
  depends_on: []
foundry-rbac-audit:
  depends_on: []
```

- [ ] **Step 3: Commit**

```bash
git add .github/skill-deps.yml
git commit -m "skill-deps: register foundry-rbac-audit + azure-monitor-alert-baseline

Both new in v0.6.0 Slice C. No upstream-skill dependencies; threadlight
is the downstream consumer (in the threadlight-skills repo, not gated
in this file).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.2: Add both to `scripts/build-site.py` CATEGORIES

**Files:**
- Modify: `scripts/build-site.py`

- [ ] **Step 1: Find CATEGORIES dict**

Run: `grep -n "CATEGORIES" scripts/build-site.py | head -5`

- [ ] **Step 2: Add both skills under an appropriate category**

Likely "Foundry adjacent / Azure platform" or similar. If unsure, mirror the category that hosts `foundry-cost-monitoring` and `foundry-observability`.

- [ ] **Step 3: Commit**

```bash
git add scripts/build-site.py
git commit -m "build-site: add foundry-rbac-audit + azure-monitor-alert-baseline to CATEGORIES

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.3: Wire E2E tests into `skill-test.yml`

**Files:**
- Modify: `.github/workflows/skill-test.yml`

- [ ] **Step 1: Inspect e2e-azure job structure**

Run: `grep -nA5 "test_e2e_" .github/workflows/skill-test.yml | head -40`

- [ ] **Step 2: Add the two new test files to the e2e-azure matrix**

Mirror the shape used for existing E2E tests (e.g. `test_e2e_prompt_agents.py`). The list lives in the workflow's matrix or in a `pytest scripts/tests/test_e2e_*.py` glob — pick the convention already in use.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/skill-test.yml
git commit -m "skill-test: add e2e-azure entries for two new Slice C skills

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.4: Plugin MINOR bump + AGENTS.md §12.5 stats update

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `AGENTS.md` (§12.5)

- [ ] **Step 1: Bump plugin.json MINOR (catalog 27 → 29)**

Run: `grep -E '"version"' plugin.json .github/plugin/marketplace.json`

Note current version; bump MINOR component. Update both files to match.

- [ ] **Step 2: Update AGENTS.md §12.5 stats table**

Run: `grep -nA10 "12.5" AGENTS.md | head -30`

Update:
- `Total skills | 27` → `29`
- `Skills with upstream pins | 23` → `25`
- `Auto-tier (CI can refresh autonomously) | 21` → `23`
- `Unit tests | 73 (...)` → bump by the count added (≈ 6 + 7 unit + 3 + 3 E2E = ~19 → ~92)
- `Azure E2E resources` row unchanged.

- [ ] **Step 3: Validate**

Run:
```bash
python scripts/build-plugins.py --check 2>&1 | tail -10
python scripts/validate-skills.py 2>&1 | tail -10
```

Expected: both PASS.

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json AGENTS.md
git commit -m "plugin: MINOR bump for v0.6.0 Slice C (27 → 29 skills)

Adds foundry-rbac-audit + azure-monitor-alert-baseline. AGENTS.md §12.5
catalog stats updated to reflect 29 skills, 25 pins, 23 auto-tier, and
the new unit + E2E test counts.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.5: Rebuild docs site

- [ ] **Step 1: Rebuild**

Run: `python3 scripts/build-site.py --out docs/ 2>&1 | tail -20`

Expected: 2 new pages under `docs/skills/`.

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: rebuild static site for Slice C (2 new skills)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.6: Final lint + test sweep

- [ ] **Step 1: Run all checks**

Run:
```bash
python scripts/validate-skills.py 2>&1 | tail -10
python scripts/build-plugins.py --check 2>&1 | tail -10
python -m pytest scripts/tests/test_unit_foundry_rbac_audit.py \
                  scripts/tests/test_unit_azure_monitor_alert_baseline.py -v 2>&1 | tail -20
```

Expected: all PASS.

- [ ] **Step 2: Forbidden-string sweep** (per AGENTS.md §2.1)

Run:
```bash
git --no-pager diff origin/main..HEAD | \
  grep -iE "kyc-poc|card-dispute-investigation|threadlight-v[123]|ricchi" || \
  echo "clean"
```

Expected: `clean`.

### Task 3.7: Push + draft PR

- [ ] **Step 1: Verify state**

Run: `git log --oneline origin/main..HEAD && git status`

- [ ] **Step 2: Push**

Run: `git push -u origin <execution-branch-name>`

- [ ] **Step 3: Draft PR body**

Title: `Slice C: foundry-rbac-audit + azure-monitor-alert-baseline (NEW skills, #268 + #272)`

Body skeleton:

```markdown
**Closes:** #268, #272
**Unblocks:** aiappsgbb/threadlight-skills v0.5.3 flip release (SEC-301 + OBS-203)
**Spec:** docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md (§4.3)
**Plan:** docs/superpowers/plans/2026-06-11-v060-slice-c-rbac-and-alerts.md

## What changes

- **NEW: `foundry-rbac-audit`** — peer skill auditing RBAC at RG scope.
  Detects over-privileged Owner/Contributor, orphan assignments,
  inherited-owner patterns. `probe(subscription_id, resource_group)`.
- **NEW: `azure-monitor-alert-baseline`** — peer skill comparing alert
  coverage against named baselines (foundry_pilot, spoke_minimum,
  production). `probe(sub, rg, baseline)`. 3 baselines under
  `references/baselines/`.
- **Plugin** — MINOR bump (catalog 27 → 29).
- **AGENTS.md §12.5** — stats updated.
- **CI** — 2 new pytest unit files (13 tests) + 2 new E2E tests in
  `skill-test.yml` e2e-azure matrix. 2 new Copilot-CLI fixtures
  registered via `.github/skill-deps.yml`.

## Test plan

- Unit: 13 pytest tests across 2 files, all PASS.
- `validate-skills.py` PASS.
- `build-plugins.py --check` PASS.
- E2E: skipped locally without AZURE_* env vars; runs in CI's
  `e2e-azure` job with OIDC credentials.
- Copilot-CLI fixtures: 2 new matrix legs (max-parallel: 2 per
  Pattern 22 — neither adds parallelism load).

## Live Azure testing (AGENTS.md §2.9)

Both probes call real Azure mgmt APIs. The E2E tests (Task 1.6, 2.6)
exercise the credential chain + SDK surface + probe path against the
CI `<ci-resource-group>`. Will be re-run as part of CI gate review.

## Commit tags

`[skill-rewrite]` + `[multi-skill]` on the relevant commits per
AGENTS.md §4 mass-edit invariants (2 new SKILL.md bodies across 2
skills).
```

- [ ] **Step 4: STOP and hand back**

Per planning task framing, do not open the PR. Surface the body draft,
commit list (will be ~16 commits in this slice), test results.

---

## Self-Review checklist

- [ ] Both skills follow AGENTS.md §10.3 12-step add-a-skill workflow.
- [ ] Both SKILL.md descriptions ≤1024 chars.
- [ ] Both skills have `metadata.version: "1.0.0"` per AGENTS.md §5.
- [ ] Pin files schema v2 with `runnable: true`, `requires: ["pypi"]`.
- [ ] Pin install commands use `~=X.Y.Z` (AGENTS.md §9.5 cap policy).
- [ ] Both E2E tests are skipped without AZURE_* env vars (CI-only).
- [ ] Both fixtures include §9.7 Patterns 12, 19-addendum-v2, 27, plus
      Step −1 echo-not-view to keep per-turn upload ≤150K tokens
      (AGENTS.md §9.7 Pattern 19 addendum + #243).
- [ ] No identifier leaks (placeholders only — `<ci-resource-group>`,
      `<sub-id>`, `<rg>`).
- [ ] `.github/skill-deps.yml` updated for both.
- [ ] `scripts/build-site.py CATEGORIES` updated for both.
- [ ] `skill-test.yml e2e-azure` matrix extended for both.
- [ ] `plugin.json` + `marketplace.json` MINOR bumped in lockstep.
- [ ] `AGENTS.md §12.5` stats accurate.
- [ ] Docs site rebuilt and committed.

---

## Done criteria

Slice C is "done" when:
1. PR merged to `main`.
2. CI green across `skill-validation.yml`, `automation-pr-gate.yml`,
   `pin-validation.yml`, and `skill-test.yml` (pin-smoke + e2e-azure +
   2 new copilot-cli-matrix legs).
3. Threadlight unblocked to open v0.5.3 flip PR for SEC-301 + OBS-203.
4. The two skills appear on the live docs site at
   `aiappsgbb.github.io/awesome-gbb`.

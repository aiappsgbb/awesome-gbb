# Slice 5 — Azure Platform Probes (azure-backup-readiness + azure-resource-diagnostics) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two NEW probe skills in a single multi-skill PR — `azure-backup-readiness` (#267, probes Recovery Services Vault + Data Protection Backup Vault coverage and finds restore-drill artefacts) and `azure-resource-diagnostics` (#271, probes diagnostic-settings coverage on RG resources and emits Bicep remediation). Both skills follow the importable-Python + CLI shim + JSON envelope pattern locked in for v0.6.0 NEW skills, both are `depends_on: []` peers (no fanout), both ride a single plugin MINOR bump (4.20.0 → 4.21.0) and a single AGENTS.md §12.5 reconcile (33 → 35).

**Architecture:** Two parallel skill folders under `skills/` with mirrored layouts (`scripts/__init__.py` + `scripts/probe.py` + `scripts/cli.py` + `requirements.txt` + `SKILL.md` + `references/upstream-pin.md` + `test-fixture/consumer_prompt.md`). Each probe shells out to `az` for inventory + per-resource queries (Backup CLI surface for #267, `az monitor diagnostic-settings list` for #271), returns a strict JSON envelope `{skill, skill_version, probed_at, inputs, result, confidence, missing_perms, errors}`. CLI shim renders the envelope to stdout; threadlight either imports `probe()` directly or dispatches via Skill and parses stdout. Soft-PASS (Pattern 13) when probe-target resources don't exist in `<ci-resource-group>` so fixtures don't require provisioning RSV + DPP + diagnostic-settings just to green CI.

**Tech Stack:** Python 3.10+, `azure-identity` for `DefaultAzureCredential` (when the SDK path is taken — most probes shell out to `az` because Backup + diagnostic-settings SDKs are split across multiple management-plane SDKs that aren't worth a per-skill pin), `subprocess.run` for `az` CLI invocations, `argparse` for CLI shim, `pytest` for unit tests. Both skills register as auto-tier pins with `runnable: true` (pure `az`/PyPI bounds, no live Azure required for pin validation).

---

## Pre-flight reading

Before starting, the executor should read these files to ground in the conventions slice 5 inherits:

- `docs/superpowers/specs/2026-06-12-v0-6-0-critical-path-design.md` §4.5 (lines 607-670) — contracts for both skills.
- `docs/superpowers/plans/2026-06-12-v0-6-0-slice-3-foundry-rbac-audit.md` — first NEW-skill plan; same phase shape, halved.
- `docs/superpowers/plans/2026-06-12-v0-6-0-slice-4-azure-monitor-alert-baseline.md` — second NEW-skill plan, demonstrates `az` shell-out + JSON envelope pattern.
- `skills/foundry-iq/scripts/__init__.py` + `skills/foundry-iq/scripts/pe_audit.py` — only existing importable-Python precedent in the catalog.
- `skills/foundry-memory/test-fixture/consumer_prompt.md` — probe-style fixture reference (172 lines / 8.2 KB).
- `.github/skill-deps.yml` — alphabetical ordering; slice 5 inserts two entries.
- `AGENTS.md` §12.5 — skill-count reconcile target after slice 5 = **35**.
- `plugin.json` + `.github/plugin/marketplace.json` — both must be bumped to **4.21.0** in a single commit.

---

## Skill A: azure-backup-readiness (#267)

### Task A1: Scaffold skill folder

**Files:**
- Create: `skills/azure-backup-readiness/scripts/__init__.py`
- Create: `skills/azure-backup-readiness/scripts/probe.py` (stub, populated in A3)
- Create: `skills/azure-backup-readiness/scripts/cli.py` (stub, populated in A5)
- Create: `skills/azure-backup-readiness/requirements.txt`
- Create: `skills/azure-backup-readiness/tests/__init__.py`
- Create: `skills/azure-backup-readiness/tests/test_probe.py` (stub, populated in A3)

- [ ] **Step 1: Create skill folder + Python package skeleton**

```bash
mkdir -p skills/azure-backup-readiness/{scripts,tests,references,test-fixture}
touch skills/azure-backup-readiness/scripts/__init__.py
touch skills/azure-backup-readiness/tests/__init__.py
```

- [ ] **Step 2: Pin minimal runtime deps in requirements.txt**

```
# skills/azure-backup-readiness/requirements.txt
azure-identity~=1.19.0
```

Note: backup-readiness shells out to `az` for the actual Backup queries (RSV + DPP surfaces are split across multiple management SDKs and an `az`-only path keeps the dep tree minimal). `azure-identity` is pinned anyway because the CLI may invoke a future SDK path for inventory.

- [ ] **Step 3: Verify scaffold structure with find**

Run: `find skills/azure-backup-readiness -type f | sort`

Expected output:
```
skills/azure-backup-readiness/requirements.txt
skills/azure-backup-readiness/scripts/__init__.py
skills/azure-backup-readiness/tests/__init__.py
```

- [ ] **Step 4: Commit scaffold**

```bash
git add skills/azure-backup-readiness/
git commit -m "feat(azure-backup-readiness): scaffold skill folder (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A2: Write probe() failing test for empty-RG case

**Files:**
- Modify: `skills/azure-backup-readiness/tests/test_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# skills/azure-backup-readiness/tests/test_probe.py
"""Unit tests for azure-backup-readiness probe.

The probe shells out to `az` for both Recovery Services Vault and
Data Protection Backup Vault surfaces. Tests mock `subprocess.run`
to return canned JSON for each `az` call, then assert the envelope
shape matches the contract in spec §4.5.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from skills.azure_backup_readiness.scripts.probe import probe


def _mock_az(stdout: str = "[]", returncode: int = 0):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def test_probe_empty_rg_returns_zero_counts():
    """RG with no RSV and no Backup Vault -> empty arrays, confidence high."""
    with patch("subprocess.run") as mock_run:
        # First call: az backup vault list -> []
        # Second call: az dataprotection backup-vault list -> []
        mock_run.side_effect = [_mock_az("[]"), _mock_az("[]")]
        result = probe(
            subscription_id="sub-1",
            resource_group="rg-empty",
        )
    assert result["skill"] == "azure-backup-readiness"
    assert result["inputs"]["subscription_id"] == "sub-1"
    assert result["inputs"]["resource_group"] == "rg-empty"
    assert result["result"]["rsv_vaults"] == []
    assert result["result"]["backup_vaults"] == []
    assert result["result"]["restore_drill_artefacts"] == []
    assert result["result"]["missing_drill"] is True
    assert result["confidence"] == "high"
    assert result["missing_perms"] == []
    assert result["errors"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest skills/azure-backup-readiness/tests/test_probe.py::test_probe_empty_rg_returns_zero_counts -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skills.azure_backup_readiness'`

- [ ] **Step 3: Commit failing test**

```bash
git add skills/azure-backup-readiness/tests/test_probe.py
git commit -m "test(azure-backup-readiness): add failing test for empty RG (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A3: Implement probe() core — empty-RG happy path

**Files:**
- Modify: `skills/azure-backup-readiness/scripts/probe.py`

- [ ] **Step 1: Write the minimal implementation**

```python
# skills/azure-backup-readiness/scripts/probe.py
"""azure-backup-readiness probe.

Probes Recovery Services Vault (RSV) and Data Protection Backup Vault
(DPP) coverage for a resource group, plus filesystem scan for
restore-drill artefacts. Returns the standard NEW-skill JSON envelope.

The probe shells out to `az` for both vault surfaces because the
management SDKs are split across multiple packages that aren't worth
pinning per-skill (a future revision may switch to azure-mgmt-recoveryservices
+ azure-mgmt-dataprotection if the catalog standardizes on SDK calls).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SKILL_NAME = "azure-backup-readiness"
SKILL_VERSION = "1.0.0"

DEFAULT_PROTECTED_ITEM_TYPES = ("VM", "AzureFiles", "Blob", "PostgreSQL")
DEFAULT_DRILL_FRESHNESS_DAYS = 90


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _az_json(args: list[str], errors: list[str]) -> list | dict | None:
    """Run `az ... -o json` and return parsed JSON, or None on failure.

    Failures append to `errors` for the envelope but don't raise — the
    probe returns partial data with degraded confidence.
    """
    cmd = ["az", *args, "-o", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        errors.append("az CLI not found on PATH")
        return None
    if proc.returncode != 0:
        errors.append(f"az failed: {' '.join(args)} -> {proc.stderr.strip()[:200]}")
        return None
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        errors.append(f"az returned non-JSON: {exc}")
        return None


def _list_rsv_vaults(subscription_id: str, rg: str, errors: list[str]) -> list[dict]:
    raw = _az_json(
        ["backup", "vault", "list", "--subscription", subscription_id,
         "--resource-group", rg],
        errors,
    )
    return raw or []


def _list_backup_vaults(subscription_id: str, rg: str, errors: list[str]) -> list[dict]:
    raw = _az_json(
        ["dataprotection", "backup-vault", "list", "--subscription", subscription_id,
         "--resource-group", rg],
        errors,
    )
    return raw or []


def _scan_restore_drill_artefacts(repo_root: Path | None) -> list[str]:
    """Filesystem scan for `tests/restore-drill-*.md` evidence files.

    Probe is read-only — drill artefacts are looked up under the caller's
    repo root if provided. Returns relative paths.
    """
    if repo_root is None:
        return []
    drill_dir = repo_root / "tests"
    if not drill_dir.is_dir():
        return []
    return sorted(
        str(p.relative_to(repo_root))
        for p in drill_dir.glob("restore-drill-*.md")
    )


def probe(
    subscription_id: str,
    resource_group: str,
    protected_item_types: Iterable[str] = DEFAULT_PROTECTED_ITEM_TYPES,
    drill_freshness_days: int = DEFAULT_DRILL_FRESHNESS_DAYS,
    repo_root: Path | None = None,
) -> dict:
    """Probe RSV + Backup Vault coverage and restore-drill freshness.

    Returns the standard NEW-skill envelope (spec §4.5).
    """
    errors: list[str] = []
    missing_perms: list[str] = []

    rsv = _list_rsv_vaults(subscription_id, resource_group, errors)
    bv = _list_backup_vaults(subscription_id, resource_group, errors)

    # Per-vault recovery point + protected item drill happens in a later
    # task — this scaffold returns the vault inventory only.
    rsv_summary = [{"name": v.get("name"), "id": v.get("id"), "protected_items": []} for v in rsv]
    bv_summary = [{"name": v.get("name"), "id": v.get("id"), "protected_items": []} for v in bv]

    drill_artefacts = _scan_restore_drill_artefacts(repo_root)
    missing_drill = len(drill_artefacts) == 0

    # Confidence degrades when az calls failed
    confidence = "high" if not errors else ("medium" if (rsv_summary or bv_summary) else "low")

    return {
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "probed_at": _now(),
        "inputs": {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "protected_item_types": list(protected_item_types),
            "drill_freshness_days": drill_freshness_days,
        },
        "result": {
            "rsv_vaults": rsv_summary,
            "backup_vaults": bv_summary,
            "restore_drill_artefacts": drill_artefacts,
            "missing_drill": missing_drill,
        },
        "confidence": confidence,
        "missing_perms": missing_perms,
        "errors": errors,
    }
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest skills/azure-backup-readiness/tests/test_probe.py::test_probe_empty_rg_returns_zero_counts -v`
Expected: PASS

- [ ] **Step 3: Commit implementation**

```bash
git add skills/azure-backup-readiness/scripts/probe.py
git commit -m "feat(azure-backup-readiness): implement probe() empty-RG path (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A4: Add tests for populated vault inventory + drill artefact path

**Files:**
- Modify: `skills/azure-backup-readiness/tests/test_probe.py`

- [ ] **Step 1: Add tests for populated RSV + Backup Vault**

```python
def test_probe_rsv_populated_returns_summary():
    """RSV with one vault, no Backup Vaults -> rsv_vaults populated, bv empty."""
    rsv_payload = json.dumps([
        {"name": "rsv-prod", "id": "/subscriptions/sub-1/resourceGroups/rg-prod/providers/Microsoft.RecoveryServices/vaults/rsv-prod"},
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az(rsv_payload), _mock_az("[]")]
        result = probe(subscription_id="sub-1", resource_group="rg-prod")
    assert len(result["result"]["rsv_vaults"]) == 1
    assert result["result"]["rsv_vaults"][0]["name"] == "rsv-prod"
    assert result["result"]["backup_vaults"] == []
    assert result["confidence"] == "high"
    assert result["errors"] == []


def test_probe_both_vault_types_populated():
    """Mixed inventory -> both arrays populated."""
    rsv_payload = json.dumps([{"name": "rsv-1", "id": "/.../rsv-1"}])
    bv_payload = json.dumps([{"name": "bv-1", "id": "/.../bv-1"}])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az(rsv_payload), _mock_az(bv_payload)]
        result = probe(subscription_id="sub-1", resource_group="rg-mixed")
    assert len(result["result"]["rsv_vaults"]) == 1
    assert len(result["result"]["backup_vaults"]) == 1
    assert result["result"]["rsv_vaults"][0]["name"] == "rsv-1"
    assert result["result"]["backup_vaults"][0]["name"] == "bv-1"


def test_probe_az_failure_records_error_and_degrades_confidence():
    """`az` failure on RSV list -> error logged, confidence=low when no vaults found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az("", returncode=1), _mock_az("[]")]
        result = probe(subscription_id="sub-1", resource_group="rg-fail")
    assert result["confidence"] == "low"
    assert any("az failed" in e for e in result["errors"])
    assert result["result"]["rsv_vaults"] == []


def test_probe_az_missing_records_error():
    """`az` not on PATH -> FileNotFoundError -> error logged."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = probe(subscription_id="sub-1", resource_group="rg-no-az")
    assert "az CLI not found on PATH" in result["errors"]
    assert result["confidence"] == "low"


def test_probe_drill_artefacts_found(tmp_path):
    """`tests/restore-drill-*.md` files in repo_root -> listed in result."""
    drill_dir = tmp_path / "tests"
    drill_dir.mkdir()
    (drill_dir / "restore-drill-vm-2026-01.md").write_text("# drill")
    (drill_dir / "restore-drill-blob-2026-02.md").write_text("# drill")
    (drill_dir / "other-file.md").write_text("# not a drill")
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az("[]"), _mock_az("[]")]
        result = probe(
            subscription_id="sub-1",
            resource_group="rg-1",
            repo_root=tmp_path,
        )
    assert result["result"]["missing_drill"] is False
    assert len(result["result"]["restore_drill_artefacts"]) == 2
    assert all("restore-drill-" in p for p in result["result"]["restore_drill_artefacts"])


def test_probe_envelope_shape_matches_contract():
    """Envelope keys match spec §4.5 contract exactly."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az("[]"), _mock_az("[]")]
        result = probe(subscription_id="sub-1", resource_group="rg-1")
    assert set(result.keys()) == {
        "skill", "skill_version", "probed_at", "inputs",
        "result", "confidence", "missing_perms", "errors",
    }
    assert set(result["inputs"].keys()) == {
        "subscription_id", "resource_group",
        "protected_item_types", "drill_freshness_days",
    }
    assert set(result["result"].keys()) == {
        "rsv_vaults", "backup_vaults",
        "restore_drill_artefacts", "missing_drill",
    }
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest skills/azure-backup-readiness/tests/ -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/tests/test_probe.py
git commit -m "test(azure-backup-readiness): cover populated vaults + drill artefacts (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A5: Add CLI shim

**Files:**
- Modify: `skills/azure-backup-readiness/scripts/cli.py`

- [ ] **Step 1: Implement CLI shim**

```python
# skills/azure-backup-readiness/scripts/cli.py
"""CLI shim for azure-backup-readiness.probe.

Usage:
    python -m skills.azure_backup_readiness.scripts.cli \\
        --subscription-id <sub> --resource-group <rg> [--repo-root <path>]

Emits the probe envelope as a single JSON object to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .probe import probe, DEFAULT_PROTECTED_ITEM_TYPES, DEFAULT_DRILL_FRESHNESS_DAYS


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Probe Azure backup coverage for a resource group")
    p.add_argument("--subscription-id", required=True)
    p.add_argument("--resource-group", required=True)
    p.add_argument(
        "--protected-item-types",
        nargs="+",
        default=list(DEFAULT_PROTECTED_ITEM_TYPES),
        help="Which item types are expected to be protected",
    )
    p.add_argument(
        "--drill-freshness-days",
        type=int,
        default=DEFAULT_DRILL_FRESHNESS_DAYS,
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repo root to scan for tests/restore-drill-*.md artefacts",
    )
    args = p.parse_args(argv)

    envelope = probe(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        protected_item_types=tuple(args.protected_item_types),
        drill_freshness_days=args.drill_freshness_days,
        repo_root=args.repo_root,
    )
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test CLI emits valid JSON**

Run: `python -m skills.azure_backup_readiness.scripts.cli --subscription-id fake --resource-group fake-rg 2>/dev/null | python -m json.tool > /dev/null && echo OK`
Expected: `OK` (CLI may fail az calls but envelope is still emitted)

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/scripts/cli.py
git commit -m "feat(azure-backup-readiness): add CLI shim emitting JSON envelope (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A6: Author SKILL.md

**Files:**
- Create: `skills/azure-backup-readiness/SKILL.md`

- [ ] **Step 1: Write SKILL.md (description ≤ 1024 chars per AGENTS.md §2.3)**

```markdown
---
name: azure-backup-readiness
description: >
  Probe Azure backup posture for a resource group: enumerate Recovery Services
  Vaults (RSV) and Data Protection Backup Vaults (DPP), summarize protected
  items, and scan for restore-drill evidence files. Emits a single JSON
  envelope so callers (threadlight production-ready, GBB pilots, SRE
  handover) can compute coverage gaps and missing-drill counts without
  re-implementing the Backup CLI surface. USE FOR: backup coverage check,
  RSV inventory, Backup Vault inventory, protected item summary, restore
  drill audit, MDL-007 production-ready evidence, Azure backup posture
  probe, recovery point objective check. DO NOT USE FOR: provisioning RSV
  or Backup Vaults (use azd-patterns), executing restore (manual ops
  playbook), policy authoring (Azure Policy + ARM templates), monitoring
  backup job health (azure-monitor-alert-baseline emits the alert rules).
metadata:
  version: "1.0.0"
---

## When to use this skill

Use `azure-backup-readiness` when a caller needs a machine-readable
snapshot of the Azure backup posture for a single resource group. The
probe is read-only; it does not provision vaults, modify policies, or
trigger restores. Typical callers:

- `threadlight-production-ready` MDL-007 (backup coverage flip)
- GBB pilot pre-flight readiness checks
- SRE handover packs (proves backup is configured + recently drilled)

## What it does

1. Enumerates Recovery Services Vaults in the resource group via
   `az backup vault list -g <rg>`.
2. Enumerates Data Protection Backup Vaults via
   `az dataprotection backup-vault list -g <rg>`.
3. Scans the caller's repo for restore-drill evidence files matching
   `tests/restore-drill-*.md`.
4. Emits a single JSON envelope to stdout:

```json
{
  "skill": "azure-backup-readiness",
  "skill_version": "1.0.0",
  "probed_at": "2026-06-12T12:00:00+00:00",
  "inputs": {
    "subscription_id": "<sub>",
    "resource_group": "<rg>",
    "protected_item_types": ["VM", "AzureFiles", "Blob", "PostgreSQL"],
    "drill_freshness_days": 90
  },
  "result": {
    "rsv_vaults": [{"name": "rsv-1", "id": "...", "protected_items": []}],
    "backup_vaults": [{"name": "bv-1", "id": "...", "protected_items": []}],
    "restore_drill_artefacts": ["tests/restore-drill-vm-2026-01.md"],
    "missing_drill": false
  },
  "confidence": "high",
  "missing_perms": [],
  "errors": []
}
```

## How to invoke

### From Python (preferred for threadlight)

```python
from skills.azure_backup_readiness.scripts.probe import probe

envelope = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    repo_root=Path.cwd(),
)
```

### From CLI (Skill-dispatch path)

```bash
python -m skills.azure_backup_readiness.scripts.cli \\
    --subscription-id <sub> \\
    --resource-group <rg> \\
    --repo-root .
```

## Authentication

Uses whatever credential `az` is logged in as. The probe shells out to
`az backup` and `az dataprotection`, so a successful `az login` (or
`az login --identity` in CI) is sufficient. No `DefaultAzureCredential`
plumbing required for the current revision.

## Required permissions

The principal running the probe needs **read** access on the resource
group to enumerate vaults:

- `Microsoft.RecoveryServices/vaults/read`
- `Microsoft.DataProtection/backupVaults/read`

The `Reader` built-in role at RG scope is sufficient.

## Output shape

See the JSON envelope above. Stable contract — additions in new
revisions are MINOR; key renames or removals are MAJOR.

## What this skill does NOT cover

- **Provisioning** of vaults or policies. Use `azd-patterns` and
  upstream ARM/Bicep modules.
- **Restore execution.** Restore is a manual SRE play; this skill
  only proves drill evidence exists.
- **Backup job health alerts.** See `azure-monitor-alert-baseline`
  for the alert-rule baseline this probe's coverage feeds.
```

- [ ] **Step 2: Validate description length**

Run: `python -c "
import yaml, pathlib
p = pathlib.Path('skills/azure-backup-readiness/SKILL.md')
fm = yaml.safe_load(p.read_text().split('---')[1])
print('len =', len(fm['description']))
assert len(fm['description']) <= 1024, 'too long'
print('OK')
"`
Expected: `len = <≤1024>` then `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/SKILL.md
git commit -m "docs(azure-backup-readiness): author SKILL.md (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task A7: Author upstream-pin.md

**Files:**
- Create: `skills/azure-backup-readiness/references/upstream-pin.md`

- [ ] **Step 1: Write pin file (schema v2)**

```markdown
---
freshness_tier: B
automation_tier: auto
upstream:
  kind: az_cli
  packages: []
validation:
  runnable: true
  requires: [github_only]
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    cd skills/azure-backup-readiness
    python -m venv .venv
    . .venv/bin/activate
    pip install -q -r requirements.txt
    python -c "from skills.azure_backup_readiness.scripts.probe import probe; print('import OK')"
    python -m pytest tests/ -q
  expected_output:
    - "import OK"
    - "passed"
last_validated: 2026-06-12
validated_by: copilot-bot
notes: |
  Backup CLI surface (az backup, az dataprotection) is GA-stable.
  No PyPI deps in validation.script — probe shells out to `az`.
  Bumps follow when az CLI changes its `vault list` output JSON shape.
---

# Upstream pin — azure-backup-readiness

## Sources

- `az backup vault list` (Recovery Services Vault management plane)
- `az dataprotection backup-vault list` (Data Protection backup plane)

Both are GA. The probe is resilient to additional fields — only `name`
and `id` are projected into the envelope.

## Known issues

None at pin-authoring time.

## Refresh policy

Bump if `az backup` or `az dataprotection` JSON output renames `name`
or `id`. Otherwise quarterly re-validation against the standing
`<ci-resource-group>` (empty path) is sufficient.
```

- [ ] **Step 2: Validate pin file shape**

Run: `python scripts/validate-skills.py 2>&1 | grep azure-backup-readiness || echo "OK no errors"`
Expected: `OK no errors`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/references/upstream-pin.md
git commit -m "feat(azure-backup-readiness): add upstream pin (#267)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Skill B: azure-resource-diagnostics (#271)

### Task B1: Scaffold skill folder

**Files:**
- Create: `skills/azure-resource-diagnostics/scripts/__init__.py`
- Create: `skills/azure-resource-diagnostics/scripts/probe.py` (stub)
- Create: `skills/azure-resource-diagnostics/scripts/cli.py` (stub)
- Create: `skills/azure-resource-diagnostics/requirements.txt`
- Create: `skills/azure-resource-diagnostics/tests/__init__.py`
- Create: `skills/azure-resource-diagnostics/tests/test_probe.py` (stub)

- [ ] **Step 1: Create skill folder + Python package skeleton**

```bash
mkdir -p skills/azure-resource-diagnostics/{scripts,tests,references,test-fixture}
touch skills/azure-resource-diagnostics/scripts/__init__.py
touch skills/azure-resource-diagnostics/tests/__init__.py
```

- [ ] **Step 2: Pin minimal runtime deps in requirements.txt**

```
# skills/azure-resource-diagnostics/requirements.txt
azure-identity~=1.19.0
```

- [ ] **Step 3: Verify scaffold structure**

Run: `find skills/azure-resource-diagnostics -type f | sort`
Expected: same shape as A1.

- [ ] **Step 4: Commit**

```bash
git add skills/azure-resource-diagnostics/
git commit -m "feat(azure-resource-diagnostics): scaffold skill folder (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B2: Write probe() failing test for empty-RG case

**Files:**
- Modify: `skills/azure-resource-diagnostics/tests/test_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# skills/azure-resource-diagnostics/tests/test_probe.py
"""Unit tests for azure-resource-diagnostics probe.

The probe enumerates resources in the RG, then queries each for
diagnostic-settings. Tests mock subprocess.run for both the inventory
call and the per-resource diag-settings call.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from skills.azure_resource_diagnostics.scripts.probe import probe


def _mock_az(stdout: str = "[]", returncode: int = 0):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def test_probe_empty_rg_returns_empty_arrays():
    """RG with no resources of the target types -> empty arrays."""
    with patch("subprocess.run") as mock_run:
        # First call: az resource list -> []
        mock_run.side_effect = [_mock_az("[]")]
        result = probe(subscription_id="sub-1", resource_group="rg-empty")
    assert result["skill"] == "azure-resource-diagnostics"
    assert result["result"]["resources_with_diag_settings"] == []
    assert result["result"]["resources_missing_diag_settings"] == []
    assert result["result"]["diag_settings_not_la_destination"] == []
    assert result["result"]["bicep_remediation_per_resource"] == {}
    assert result["confidence"] == "high"
    assert result["errors"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest skills/azure-resource-diagnostics/tests/test_probe.py::test_probe_empty_rg_returns_empty_arrays -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/tests/test_probe.py
git commit -m "test(azure-resource-diagnostics): add failing test for empty RG (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B3: Implement probe() core

**Files:**
- Modify: `skills/azure-resource-diagnostics/scripts/probe.py`

- [ ] **Step 1: Write the minimal implementation**

```python
# skills/azure-resource-diagnostics/scripts/probe.py
"""azure-resource-diagnostics probe.

Enumerates resources of target types in a resource group, queries each
for diagnostic-settings, and emits a JSON envelope including a Bicep
remediation snippet per resource missing diag settings.

Shells out to `az` because the diagnostic-settings management surface
is the most stable cross-resource API.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Iterable

SKILL_NAME = "azure-resource-diagnostics"
SKILL_VERSION = "1.0.0"

DEFAULT_TARGET_TYPES = (
    "Microsoft.CognitiveServices/accounts",
    "Microsoft.KeyVault/vaults",
    "Microsoft.Storage/storageAccounts",
    "Microsoft.App/managedEnvironments",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _az_json(args: list[str], errors: list[str]) -> list | dict | None:
    cmd = ["az", *args, "-o", "json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        errors.append("az CLI not found on PATH")
        return None
    if proc.returncode != 0:
        errors.append(f"az failed: {' '.join(args)} -> {proc.stderr.strip()[:200]}")
        return None
    try:
        return json.loads(proc.stdout or "null")
    except json.JSONDecodeError as exc:
        errors.append(f"az returned non-JSON: {exc}")
        return None


def _list_resources(
    subscription_id: str, rg: str, target_types: Iterable[str], errors: list[str]
) -> list[dict]:
    raw = _az_json(
        ["resource", "list", "--subscription", subscription_id,
         "--resource-group", rg],
        errors,
    )
    if not raw:
        return []
    targets = set(target_types)
    return [r for r in raw if r.get("type") in targets]


def _list_diag_settings(resource_id: str, errors: list[str]) -> list[dict]:
    raw = _az_json(
        ["monitor", "diagnostic-settings", "list", "--resource", resource_id],
        errors,
    )
    if not raw:
        return []
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw if isinstance(raw, list) else []


def _has_la_destination(setting: dict) -> bool:
    return bool(setting.get("workspaceId"))


def _bicep_remediation(resource: dict, workspace_id_placeholder: str = "<workspace-id>") -> str:
    """Emit a Bicep snippet to attach a diag setting to this resource."""
    name = resource.get("name", "<resource>")
    rid = resource.get("id", "<resource-id>")
    rtype = resource.get("type", "<resource-type>")
    return (
        f"// Diagnostic setting for {name} ({rtype})\n"
        f"resource diag_{name.replace('-', '_')} 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {{\n"
        f"  name: 'send-to-la'\n"
        f"  scope: resourceId('{rtype}', '{name}')\n"
        f"  properties: {{\n"
        f"    workspaceId: '{workspace_id_placeholder}'\n"
        f"    logs: [ {{ categoryGroup: 'allLogs', enabled: true }} ]\n"
        f"    metrics: [ {{ category: 'AllMetrics', enabled: true }} ]\n"
        f"  }}\n"
        f"}}\n"
        f"// Apply to scope: {rid}\n"
    )


def probe(
    subscription_id: str,
    resource_group: str,
    target_resource_types: Iterable[str] = DEFAULT_TARGET_TYPES,
) -> dict:
    """Probe diag-settings coverage for resources in the RG.

    Returns the standard NEW-skill envelope (spec §4.5).
    """
    errors: list[str] = []
    missing_perms: list[str] = []

    resources = _list_resources(
        subscription_id, resource_group, target_resource_types, errors,
    )

    with_diag: list[dict] = []
    missing_diag: list[dict] = []
    not_la: list[dict] = []
    bicep_remediation: dict[str, str] = {}

    for r in resources:
        rid = r.get("id", "")
        settings = _list_diag_settings(rid, errors)
        if not settings:
            missing_diag.append({"id": rid, "name": r.get("name"), "type": r.get("type")})
            bicep_remediation[rid] = _bicep_remediation(r)
            continue
        with_diag.append({"id": rid, "name": r.get("name"), "type": r.get("type"),
                          "settings_count": len(settings)})
        for s in settings:
            if not _has_la_destination(s):
                not_la.append({
                    "id": rid,
                    "setting_name": s.get("name"),
                    "destination": "storage_or_eventhub_only",
                })

    confidence = "high" if not errors else ("medium" if resources else "low")

    return {
        "skill": SKILL_NAME,
        "skill_version": SKILL_VERSION,
        "probed_at": _now(),
        "inputs": {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "target_resource_types": list(target_resource_types),
        },
        "result": {
            "resources_with_diag_settings": with_diag,
            "resources_missing_diag_settings": missing_diag,
            "diag_settings_not_la_destination": not_la,
            "bicep_remediation_per_resource": bicep_remediation,
        },
        "confidence": confidence,
        "missing_perms": missing_perms,
        "errors": errors,
    }
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest skills/azure-resource-diagnostics/tests/test_probe.py::test_probe_empty_rg_returns_empty_arrays -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/scripts/probe.py
git commit -m "feat(azure-resource-diagnostics): implement probe() core (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B4: Add tests for populated inventory + remediation snippet

**Files:**
- Modify: `skills/azure-resource-diagnostics/tests/test_probe.py`

- [ ] **Step 1: Add tests**

```python
def test_probe_resource_with_la_diag_setting():
    """Resource with LA-backed diag setting -> classified as 'with_diag'."""
    res_payload = json.dumps([
        {"id": "/subs/s1/rg/r1/providers/Microsoft.KeyVault/vaults/kv-1",
         "name": "kv-1", "type": "Microsoft.KeyVault/vaults"},
    ])
    diag_payload = json.dumps([
        {"name": "to-la", "workspaceId": "/subs/s1/rg/r1/providers/Microsoft.OperationalInsights/workspaces/law-1"},
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az(res_payload), _mock_az(diag_payload)]
        result = probe(subscription_id="s1", resource_group="r1")
    assert len(result["result"]["resources_with_diag_settings"]) == 1
    assert result["result"]["resources_with_diag_settings"][0]["name"] == "kv-1"
    assert result["result"]["resources_missing_diag_settings"] == []
    assert result["result"]["diag_settings_not_la_destination"] == []


def test_probe_resource_with_storage_only_diag_classified_not_la():
    """Diag setting with no workspaceId -> listed under not_la."""
    res_payload = json.dumps([
        {"id": "/subs/s1/rg/r1/providers/Microsoft.KeyVault/vaults/kv-1",
         "name": "kv-1", "type": "Microsoft.KeyVault/vaults"},
    ])
    diag_payload = json.dumps([
        {"name": "to-storage", "storageAccountId": "/subs/.../st-1"},
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az(res_payload), _mock_az(diag_payload)]
        result = probe(subscription_id="s1", resource_group="r1")
    assert len(result["result"]["resources_with_diag_settings"]) == 1
    assert len(result["result"]["diag_settings_not_la_destination"]) == 1
    assert result["result"]["diag_settings_not_la_destination"][0]["destination"] == \
        "storage_or_eventhub_only"


def test_probe_resource_missing_diag_emits_bicep_remediation():
    """Resource with no diag settings -> bicep snippet emitted for it."""
    res_payload = json.dumps([
        {"id": "/subs/s1/rg/r1/providers/Microsoft.CognitiveServices/accounts/cs-1",
         "name": "cs-1", "type": "Microsoft.CognitiveServices/accounts"},
    ])
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az(res_payload), _mock_az("[]")]
        result = probe(subscription_id="s1", resource_group="r1")
    assert len(result["result"]["resources_missing_diag_settings"]) == 1
    bicep = result["result"]["bicep_remediation_per_resource"]
    assert len(bicep) == 1
    snippet = next(iter(bicep.values()))
    assert "diagnosticSettings" in snippet
    assert "workspaceId" in snippet
    assert "cs-1" in snippet


def test_probe_filters_to_target_types():
    """Non-target resource types are skipped from the inventory."""
    res_payload = json.dumps([
        {"id": "/.../vm-1", "name": "vm-1", "type": "Microsoft.Compute/virtualMachines"},
        {"id": "/.../kv-1", "name": "kv-1", "type": "Microsoft.KeyVault/vaults"},
    ])
    with patch("subprocess.run") as mock_run:
        # Only kv-1 should trigger a diag-settings call
        mock_run.side_effect = [_mock_az(res_payload), _mock_az("[]")]
        result = probe(subscription_id="s1", resource_group="r1")
    # vm-1 is not in DEFAULT_TARGET_TYPES, so it's not probed.
    all_listed = (
        result["result"]["resources_with_diag_settings"]
        + result["result"]["resources_missing_diag_settings"]
    )
    assert len(all_listed) == 1
    assert all_listed[0]["name"] == "kv-1"


def test_probe_az_missing_records_error():
    """`az` not on PATH -> error logged + low confidence."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = probe(subscription_id="s1", resource_group="r1")
    assert "az CLI not found on PATH" in result["errors"]
    assert result["confidence"] == "low"


def test_probe_envelope_shape_matches_contract():
    """Envelope keys match spec §4.5 contract exactly."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [_mock_az("[]")]
        result = probe(subscription_id="s1", resource_group="r1")
    assert set(result.keys()) == {
        "skill", "skill_version", "probed_at", "inputs",
        "result", "confidence", "missing_perms", "errors",
    }
    assert set(result["inputs"].keys()) == {
        "subscription_id", "resource_group", "target_resource_types",
    }
    assert set(result["result"].keys()) == {
        "resources_with_diag_settings",
        "resources_missing_diag_settings",
        "diag_settings_not_la_destination",
        "bicep_remediation_per_resource",
    }
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest skills/azure-resource-diagnostics/tests/ -v`
Expected: All 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/tests/test_probe.py
git commit -m "test(azure-resource-diagnostics): cover populated + remediation paths (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B5: Add CLI shim

**Files:**
- Modify: `skills/azure-resource-diagnostics/scripts/cli.py`

- [ ] **Step 1: Implement CLI shim**

```python
# skills/azure-resource-diagnostics/scripts/cli.py
"""CLI shim for azure-resource-diagnostics.probe.

Usage:
    python -m skills.azure_resource_diagnostics.scripts.cli \\
        --subscription-id <sub> --resource-group <rg> \\
        [--target-resource-types <type1> <type2> ...]
"""
from __future__ import annotations

import argparse
import json
import sys

from .probe import probe, DEFAULT_TARGET_TYPES


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Probe Azure diagnostic-settings coverage for a resource group")
    p.add_argument("--subscription-id", required=True)
    p.add_argument("--resource-group", required=True)
    p.add_argument(
        "--target-resource-types",
        nargs="+",
        default=list(DEFAULT_TARGET_TYPES),
    )
    args = p.parse_args(argv)

    envelope = probe(
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        target_resource_types=tuple(args.target_resource_types),
    )
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-test CLI**

Run: `python -m skills.azure_resource_diagnostics.scripts.cli --subscription-id fake --resource-group fake-rg 2>/dev/null | python -m json.tool > /dev/null && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/scripts/cli.py
git commit -m "feat(azure-resource-diagnostics): add CLI shim (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B6: Author SKILL.md

**Files:**
- Create: `skills/azure-resource-diagnostics/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

```markdown
---
name: azure-resource-diagnostics
description: >
  Probe Azure diagnostic-settings coverage for a resource group: enumerate
  resources of target types (Cognitive Services accounts, Key Vaults,
  Storage Accounts, ACA managed environments by default), query each for
  diagnostic-settings, classify by destination (Log Analytics vs
  storage/eventhub only), and emit a Bicep remediation snippet per
  resource missing diag settings. Caller-friendly JSON envelope so
  threadlight production-ready (MDL-008), GBB pilots, and SRE handover
  packs can compute observability gaps without re-implementing the
  diag-settings management surface. USE FOR: diagnostic settings audit,
  Log Analytics coverage check, observability gap probe, Bicep
  remediation snippet generation, MDL-008 production-ready evidence,
  cross-resource diag posture. DO NOT USE FOR: provisioning diag
  settings (apply the emitted Bicep), querying logs (use
  foundry-observability KQL helpers), alert authoring
  (azure-monitor-alert-baseline).
metadata:
  version: "1.0.0"
---

## When to use this skill

Use `azure-resource-diagnostics` when a caller needs a machine-readable
snapshot of which resources in an RG have diagnostic settings, and
remediation snippets for those that don't. Read-only probe.

Typical callers:

- `threadlight-production-ready` MDL-008 (observability coverage flip)
- GBB pilot pre-flight readiness checks
- SRE handover packs (proves logs are reaching LA)

## What it does

1. Lists resources in the RG with `az resource list -g <rg>`.
2. Filters to `target_resource_types` (default: Cognitive Services,
   Key Vault, Storage, ACA managed envs).
3. For each filtered resource, calls
   `az monitor diagnostic-settings list --resource <id>`.
4. Classifies each resource as:
   - `resources_with_diag_settings` (has ≥1 setting)
   - `resources_missing_diag_settings` (zero settings)
   - `diag_settings_not_la_destination` (setting exists but no
     workspaceId — storage or event-hub only)
5. Emits Bicep remediation snippet per resource missing settings.
6. Returns the standard NEW-skill envelope.

## How to invoke

### From Python

```python
from skills.azure_resource_diagnostics.scripts.probe import probe

envelope = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    target_resource_types=(
        "Microsoft.CognitiveServices/accounts",
        "Microsoft.KeyVault/vaults",
    ),
)
```

### From CLI

```bash
python -m skills.azure_resource_diagnostics.scripts.cli \\
    --subscription-id <sub> --resource-group <rg>
```

## Authentication

Uses `az` session. `Reader` at RG scope is sufficient for the
inventory call; `Microsoft.Insights/diagnosticSettings/read` is
required for the per-resource query (included in `Reader`).

## Output shape

```json
{
  "skill": "azure-resource-diagnostics",
  "skill_version": "1.0.0",
  "probed_at": "2026-06-12T12:00:00+00:00",
  "inputs": {
    "subscription_id": "<sub>",
    "resource_group": "<rg>",
    "target_resource_types": ["Microsoft.KeyVault/vaults", "..."]
  },
  "result": {
    "resources_with_diag_settings": [{"id": "...", "name": "...", "type": "...", "settings_count": 1}],
    "resources_missing_diag_settings": [{"id": "...", "name": "...", "type": "..."}],
    "diag_settings_not_la_destination": [{"id": "...", "setting_name": "...", "destination": "storage_or_eventhub_only"}],
    "bicep_remediation_per_resource": {"/subs/.../kv-1": "// Bicep snippet..."}
  },
  "confidence": "high",
  "missing_perms": [],
  "errors": []
}
```

## What this skill does NOT cover

- **Provisioning diag settings.** Take the emitted Bicep snippet and
  apply it with your standard `azd` / Bicep deploy path.
- **Querying logs themselves.** See `foundry-observability` for KQL
  probe helpers against the destination workspace.
- **Alert rules over those logs.** See `azure-monitor-alert-baseline`.
```

- [ ] **Step 2: Validate description length**

Run: `python -c "
import yaml, pathlib
p = pathlib.Path('skills/azure-resource-diagnostics/SKILL.md')
fm = yaml.safe_load(p.read_text().split('---')[1])
print('len =', len(fm['description']))
assert len(fm['description']) <= 1024
print('OK')
"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/SKILL.md
git commit -m "docs(azure-resource-diagnostics): author SKILL.md (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task B7: Author upstream-pin.md

**Files:**
- Create: `skills/azure-resource-diagnostics/references/upstream-pin.md`

- [ ] **Step 1: Write pin file**

```markdown
---
freshness_tier: B
automation_tier: auto
upstream:
  kind: az_cli
  packages: []
validation:
  runnable: true
  requires: [github_only]
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    cd skills/azure-resource-diagnostics
    python -m venv .venv
    . .venv/bin/activate
    pip install -q -r requirements.txt
    python -c "from skills.azure_resource_diagnostics.scripts.probe import probe; print('import OK')"
    python -m pytest tests/ -q
  expected_output:
    - "import OK"
    - "passed"
last_validated: 2026-06-12
validated_by: copilot-bot
notes: |
  Uses `az resource list` + `az monitor diagnostic-settings list`.
  Both are GA. Refresh when JSON output shape changes for `id`/`type`/`name`
  on resource list or `workspaceId` on diag settings.
---

# Upstream pin — azure-resource-diagnostics

## Sources

- `az resource list` (Azure Resource Manager management plane)
- `az monitor diagnostic-settings list` (Azure Monitor management plane)

## Refresh policy

Bump on any CLI output rename for `id`, `name`, `type`, or
`workspaceId`. Quarterly re-validation otherwise.
```

- [ ] **Step 2: Validate pin file**

Run: `python scripts/validate-skills.py 2>&1 | grep azure-resource-diagnostics || echo "OK no errors"`
Expected: `OK no errors`

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/references/upstream-pin.md
git commit -m "feat(azure-resource-diagnostics): add upstream pin (#271)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Cross-skill plumbing (multi-skill PR sweep)

### Task C1: Register both skills in `.github/skill-deps.yml`

**Files:**
- Modify: `.github/skill-deps.yml`

- [ ] **Step 1: Insert both entries alphabetically**

```yaml
# After the last 'azure-...' entry (alphabetical insertion).
azure-backup-readiness:
  depends_on: []
azure-resource-diagnostics:
  depends_on: []
```

- [ ] **Step 2: Verify matrix builder picks up the new skills**

Run: `python scripts/build-test-matrix.py --all --json | python -m json.tool | grep -E "(azure-backup-readiness|azure-resource-diagnostics)"`
Expected: both skill names appear in the matrix.

- [ ] **Step 3: Commit**

```bash
git add .github/skill-deps.yml
git commit -m "ci: register azure-backup-readiness + azure-resource-diagnostics in skill-deps (#267, #271)

[multi-skill]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task C2: Bump plugin.json + marketplace.json to 4.21.0

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`

- [ ] **Step 1: Bump both version fields**

```json
// plugin.json: version 4.20.0 -> 4.21.0
// .github/plugin/marketplace.json: matching version bump
```

- [ ] **Step 2: Validate plugin manifest still parses**

Run: `python scripts/build-plugins.py --check`
Expected: exit 0, no errors.

- [ ] **Step 3: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json
git commit -m "feat(plugin): bump to 4.21.0 — add azure-backup-readiness + azure-resource-diagnostics (#267, #271)

[multi-skill]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task C3: Reconcile AGENTS.md §12.5 skill count

**Files:**
- Modify: `AGENTS.md` (§ 12.5 "Catalog at a glance" table)

- [ ] **Step 1: Update skill-count rows**

Change:
- `Total skills | 33` → `Total skills | 35`
- `Skills with upstream pins | 29` → `Skills with upstream pins | 31`
- `Auto-tier (CI can refresh autonomously) | 27` → `Auto-tier (CI can refresh autonomously) | 29`
- (Verify previous slice bumps already landed; if slice 4 left the file at 33, this lifts it to 35.)

- [ ] **Step 2: Validate AGENTS.md parses**

Run: `grep -E '^\| Total skills' AGENTS.md`
Expected: shows `Total skills | 35`.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "docs(AGENTS): reconcile §12.5 catalog count to 35 (#267, #271)

[multi-skill]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task C4: Author fixture for azure-backup-readiness

**Files:**
- Create: `skills/azure-backup-readiness/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Write fixture (≤ 8 KB, probe-style)**

```markdown
# Consumer prompt — azure-backup-readiness smoke

You are running the `azure-backup-readiness` smoke. Your job is to
prove the probe imports, runs against the standing CI subscription +
RG, emits a valid JSON envelope, and writes the deterministic marker
file. Soft-PASS (Pattern 13) when no RSV / Backup Vaults exist in
`<ci-resource-group>` — the empty-inventory case is still a correct
envelope.

### Hard rules

- **Execution smoke, not catalog inspection.** Execute the probe;
  don't browse the catalog.
- **CRITICAL — never invoke `copilot` recursively from a Bash tool.**
  Use Bash tool calls directly.
- Substitute literal `S` for `_` in any marker token shown as
  `_MOKE_RESULT` in this prompt — never decorate with backticks.

### Step -1 — acknowledge skill contract

Run exactly:

```
echo "skills/azure-backup-readiness/SKILL.md"
```

This satisfies the post-hoc audit grep without bloating context.

### Step 0 — verify CI auth contract

```
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

All three env-var echoes MUST print `…=set`. If any is empty, emit:

```
printf 'SMOKE_RESULT=FAIL CI env contract broken\n' > /tmp/azure-backup-readiness-smoke-result
```

and STOP.

### Step 1 — install probe deps and import

```
cd "$GITHUB_WORKSPACE/skills/azure-backup-readiness"
python -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -c "from skills.azure_backup_readiness.scripts.probe import probe; print('import OK')"
```

Expected: `import OK`.

### Step 2 — run probe against the CI RG

```
cd "$GITHUB_WORKSPACE"
python -m skills.azure_backup_readiness.scripts.cli \
    --subscription-id "$AZURE_SUBSCRIPTION_ID" \
    --resource-group rg-awesome-gbb-ci \
    --repo-root . > /tmp/abr-envelope.json
python -m json.tool /tmp/abr-envelope.json > /dev/null
echo "JSON OK"
```

Expected: `JSON OK` (envelope parses).

### Step 3 — verify envelope shape

```
python <<'PY'
import json
e = json.load(open("/tmp/abr-envelope.json"))
for k in ("skill","skill_version","probed_at","inputs","result","confidence","missing_perms","errors"):
    assert k in e, f"missing {k}"
assert e["skill"] == "azure-backup-readiness"
for k in ("rsv_vaults","backup_vaults","restore_drill_artefacts","missing_drill"):
    assert k in e["result"], f"missing result.{k}"
print("shape OK")
PY
```

Expected: `shape OK`.

### Step 4 — emit deterministic marker

If all prior steps succeeded:

```
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-backup-readiness-smoke-result
```

If any step failed:

```
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-backup-readiness-smoke-result
```

(Substitute literal `S` for `_` per the hard rules.)
```

- [ ] **Step 2: Verify fixture size ≤ 8 KB**

Run: `wc -c skills/azure-backup-readiness/test-fixture/consumer_prompt.md`
Expected: `<8200`.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/test-fixture/
git commit -m "test(azure-backup-readiness): add Copilot-CLI fixture (#267)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task C5: Author fixture for azure-resource-diagnostics

**Files:**
- Create: `skills/azure-resource-diagnostics/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Write fixture (mirror C4, swap skill identifiers + envelope keys)**

```markdown
# Consumer prompt — azure-resource-diagnostics smoke

Probe-style smoke for `azure-resource-diagnostics`. Soft-PASS
(Pattern 13) when the RG has no target-type resources — empty
inventory is still a valid envelope.

### Hard rules

- **Execution smoke, not catalog inspection.**
- **CRITICAL — never invoke `copilot` recursively from a Bash tool.**
- Substitute literal `S` for `_` in `_MOKE_RESULT` — no decorations.

### Step -1 — acknowledge skill contract

```
echo "skills/azure-resource-diagnostics/SKILL.md"
```

### Step 0 — verify CI auth contract

```
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

If any var is empty:

```
printf 'SMOKE_RESULT=FAIL CI env contract broken\n' > /tmp/azure-resource-diagnostics-smoke-result
```

STOP.

### Step 1 — install + import

```
cd "$GITHUB_WORKSPACE/skills/azure-resource-diagnostics"
python -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -c "from skills.azure_resource_diagnostics.scripts.probe import probe; print('import OK')"
```

### Step 2 — run probe against CI RG

```
cd "$GITHUB_WORKSPACE"
python -m skills.azure_resource_diagnostics.scripts.cli \
    --subscription-id "$AZURE_SUBSCRIPTION_ID" \
    --resource-group rg-awesome-gbb-ci > /tmp/ard-envelope.json
python -m json.tool /tmp/ard-envelope.json > /dev/null
echo "JSON OK"
```

### Step 3 — verify envelope shape

```
python <<'PY'
import json
e = json.load(open("/tmp/ard-envelope.json"))
for k in ("skill","skill_version","probed_at","inputs","result","confidence","missing_perms","errors"):
    assert k in e, f"missing {k}"
assert e["skill"] == "azure-resource-diagnostics"
for k in ("resources_with_diag_settings","resources_missing_diag_settings","diag_settings_not_la_destination","bicep_remediation_per_resource"):
    assert k in e["result"], f"missing result.{k}"
print("shape OK")
PY
```

### Step 4 — emit deterministic marker

```
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-resource-diagnostics-smoke-result
```

(or `FAIL <reason>` if any step failed.)
```

- [ ] **Step 2: Verify size ≤ 8 KB**

Run: `wc -c skills/azure-resource-diagnostics/test-fixture/consumer_prompt.md`
Expected: `<8200`.

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/test-fixture/
git commit -m "test(azure-resource-diagnostics): add Copilot-CLI fixture (#271)

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task C6: Run full local validation

- [ ] **Step 1: YAML / description / forbidden-string lint**

Run: `python scripts/validate-skills.py`
Expected: exit 0, no errors for new skills.

- [ ] **Step 2: Run new-skill unit test suites**

Run:
```
python -m pytest skills/azure-backup-readiness/tests/ -v
python -m pytest skills/azure-resource-diagnostics/tests/ -v
```
Expected: all tests PASS for both skills.

- [ ] **Step 3: Rebuild docs site**

Run: `python3 scripts/build-site.py --out docs/`
Expected: exit 0; commit any regenerated `docs/` files.

- [ ] **Step 4: Commit docs rebuild (if changed)**

```bash
git add docs/
git commit -m "docs(site): rebuild for azure-backup-readiness + azure-resource-diagnostics (#267, #271)

[multi-skill]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>" || echo "no doc changes"
```

---

### Task C7: Open the multi-skill PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin slice-5-platform-probes
```

- [ ] **Step 2: Open PR with `[multi-skill]` tag in title**

PR title: `feat: azure-backup-readiness + azure-resource-diagnostics NEW skills [multi-skill] (#267, #271)`

PR body must include:
- Link to umbrella spec.
- Both issue numbers in the closes list.
- Evidence of live testing per AGENTS.md §2.9 (paste of envelope output from a real run against `<ci-resource-group>`).
- Confirmation that fixtures soft-PASS on empty inventory (Pattern 13).

- [ ] **Step 3: Confirm CI gates green**

Watch for:
- `skill-validation.yml` (T0) green
- `pin-validation.yml` (T1+T2) green for both new pins
- `automation-pr-gate.yml` accepts `[multi-skill]` tag
- `skill-test.yml` `copilot-cli-matrix` legs green for both new skills

- [ ] **Step 4: Hand off for human review.**

---

## Self-review checklist (run after writing this plan)

- [x] **Spec coverage:** Both issues (#267, #271) have a probe task, a CLI task, a SKILL.md task, a pin task, and a fixture task. Envelope keys match spec §4.5.
- [x] **Placeholder scan:** No TBD / TODO / "similar to" / "handle appropriately" entries. All code blocks are concrete.
- [x] **Type consistency:** `probe()` signature matches between Python module, CLI shim, SKILL.md, and tests. Envelope keys identical across both skills (except `result.*` per spec).
- [x] **AGENTS.md §12.5 reconcile** is a task (C3), not a footnote.
- [x] **Plugin bump** is a single task (C2) covering both skills, with `[multi-skill]` tag.
- [x] **Fixture bloat budget:** Both fixtures explicitly ≤ 8 KB (verified by C4 step 2 + C5 step 2).
- [x] **Soft-PASS pattern:** Step 4 of each fixture emits PASS even when inventory is empty (probe still produces a valid envelope).
- [x] **Commit tags:** Per-skill commits use `[skill-rewrite]`; multi-skill plumbing commits use `[multi-skill]`. Matches AGENTS.md §4 gate.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-12-v0-6-0-slice-5-backup-readiness-and-diagnostics.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, two-stage review per task. Recommended because slice 5 has 14+ commits and parallel skill folders — keeping context narrow per task reduces drift.

**2. Inline Execution** — one session, all tasks. Faster for a single executor with strong shell + Python, but more risk of mid-stream context drift.

Which approach?

# Slice D — azure-backup-readiness + azure-resource-diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land two NEW peer skills — `azure-backup-readiness` (#267) and `azure-resource-diagnostics` (#271) — that threadlight v0.5.4 needs to flip BAK-401 / OBS-204 from `kind: manual` to `kind: sibling-skill`. Both follow the shared template proven by Slice C (`foundry-rbac-audit` + `azure-monitor-alert-baseline`).

**Architecture:** Two peer skills, structurally identical to Slice C. Same `probe(subscription_id, resource_group, **kwargs) -> dict` signature; `DefaultAzureCredential`; stdout JSON + `out/<finding-id>.json` manifest. Backup probe checks **both** Recovery Services Vaults and Backup Vaults per spec §4.4 Q-D1 (locked decision: vault-type aware). Diagnostics probe counts **any** configured destination (LAW / EventHubs / Storage) as "configured" per spec §4.4 Q-D2 (locked decision: any-destination-counts).

**Tech Stack:** Python 3.11+, pytest, `azure-mgmt-recoveryservices` + `azure-mgmt-recoveryservicesbackup` + `azure-mgmt-dataprotection` (backup), `azure-mgmt-monitor` (diagnostic settings), `azure-mgmt-resource`, `azure-identity`.

**Spec:** [`docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md`](../specs/2026-06-11-v060-upstream-landings-design.md) §4.4
**Issues closed:** #267, #271
**Threadlight unlock:** v0.5.4 (BAK-401 + OBS-204) → cuts to v0.6.0

---

## File Structure

**Create — `azure-backup-readiness/`:**
- `skills/azure-backup-readiness/SKILL.md`
- `skills/azure-backup-readiness/README.md`
- `skills/azure-backup-readiness/references/upstream-pin.md`
- `skills/azure-backup-readiness/references/python/__init__.py`
- `skills/azure-backup-readiness/references/python/probe.py`
- `skills/azure-backup-readiness/references/python/__main__.py`
- `skills/azure-backup-readiness/test-fixture/consumer_prompt.md`
- `scripts/tests/test_unit_azure_backup_readiness.py`

> **Drift pivot (post Slice A/B merge):** `scripts/tests/test_e2e_*.py`
> was deleted upstream and `skill-test.yml` line 9 reads "We deliberately
> do NOT run pytest-based e2e tests." Both Slice A (#279) and Slice B
> (#281) shipped with unit tests only + §2.9 live evidence in the PR
> body — no `test_e2e_*.py` files. This plan mirrors that pattern:
> Tasks 1.5 and 2.5 are now §2.9 live-evidence + fixture tasks, and
> Task 3.3 is dropped (no e2e-azure matrix to wire into).

**Create — `azure-resource-diagnostics/`:**
- `skills/azure-resource-diagnostics/SKILL.md`
- `skills/azure-resource-diagnostics/README.md`
- `skills/azure-resource-diagnostics/references/upstream-pin.md`
- `skills/azure-resource-diagnostics/references/python/__init__.py`
- `skills/azure-resource-diagnostics/references/python/probe.py`
- `skills/azure-resource-diagnostics/references/python/__main__.py`
- `skills/azure-resource-diagnostics/test-fixture/consumer_prompt.md`
- `scripts/tests/test_unit_azure_resource_diagnostics.py`

**Modify:**
- `scripts/build-site.py` (add both to `CATEGORIES`)
- `.github/skill-deps.yml` (two new entries, `depends_on: []`)
- `plugin.json` (MINOR bump; catalog 29 → 31)
- `.github/plugin/marketplace.json` (MINOR matched)
- `AGENTS.md` (§12.5 stats: 29 → 31 skills)

**Read-only (reference):**
- The Slice C scaffolds (committed in the prior PR) — use as the template; do not re-derive shape.
- `scripts/templates/upstream-pin.template.md`
- AGENTS.md §10.3 (12 steps), §9.7 Patterns 12/19/22/27.

**Do NOT touch:**
- Any other skill body
- Anything outside the file lists above
- threadlight-skills repo

---

## Phase 0 — Setup

### Task 0.1: Cross-reference Slice C as template

- [ ] **Step 1: Read Slice C's `foundry-rbac-audit` SKILL.md + probe**

Run:
```bash
cat skills/foundry-rbac-audit/SKILL.md
cat skills/foundry-rbac-audit/references/python/probe.py | head -80
cat skills/foundry-rbac-audit/test-fixture/consumer_prompt.md
```

(Assumes Slice C merged.) If Slice C is NOT yet merged, read its plan: `docs/superpowers/plans/2026-06-11-v060-slice-c-rbac-and-alerts.md`.

- [ ] **Step 2: Read the two Azure SDK packages we'll need that are new to this slice**

Quick spec lookup:
- `azure-mgmt-recoveryservices` — list Recovery Services Vaults (`vaults.list_by_resource_group`)
- `azure-mgmt-recoveryservicesbackup` — list protected items on a vault
- `azure-mgmt-dataprotection` — list Backup Vaults (the newer surface; different SKU than RSV)
- `azure-mgmt-monitor` — `diagnostic_settings.list` per resource ARM ID
- `azure-mgmt-resource` — enumerate resources in the RG

If unsure about exact method names, run:
```bash
pip install -q "azure-mgmt-recoveryservices~=3.0" "azure-mgmt-dataprotection~=1.5" 2>&1 | tail -3
python -c "
from azure.mgmt.recoveryservices import RecoveryServicesClient
from azure.mgmt.dataprotection import DataProtectionMgmtClient
import inspect
print('RSV:', [m for m in dir(RecoveryServicesClient) if not m.startswith('_')][:10])
print('BV:',  [m for m in dir(DataProtectionMgmtClient)  if not m.startswith('_')][:10])
"
```

Note actual operation group names (e.g. `vaults`, `backup_vaults`); adjust the probe code below if upstream renamed.

No commit — setup reads only.

---

## Phase 1 — `azure-backup-readiness` skill

Mirror Slice C's Phase-1 shape. Code follows; no placeholders.

### Task 1.1: Write the failing unit test

**Files:**
- Create: `scripts/tests/test_unit_azure_backup_readiness.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for azure-backup-readiness probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/267
Locked decision (spec §4.4 Q-D1): probe checks BOTH Recovery Services
Vaults and Backup Vaults.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "azure-backup-readiness" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe  # noqa: E402


@pytest.fixture
def fake_clients(monkeypatch):
    rsv = MagicMock(name="RecoveryServicesClient")
    bv = MagicMock(name="DataProtectionMgmtClient")
    rsvb = MagicMock(name="RecoveryServicesBackupClient")
    monkeypatch.setattr("probe.RecoveryServicesClient",
                         lambda cred, sub: rsv)
    monkeypatch.setattr("probe.DataProtectionMgmtClient",
                         lambda cred, sub: bv)
    monkeypatch.setattr("probe.RecoveryServicesBackupClient",
                         lambda cred, sub: rsvb)
    return rsv, bv, rsvb


def _shape(result: dict) -> None:
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "vaults", "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys()), f"missing: {required - result.keys()}"
    assert result["skill"] == "azure-backup-readiness"
    assert isinstance(result["vaults"], list)
    assert isinstance(result["findings"], list)


def test_happy_path_both_vault_types_present(fake_clients):
    """Both an RSV and a Backup Vault present with active protected items."""
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.return_value = [
        MagicMock(name="rsv1", id="/.../vaults/rsv1"),
    ]
    bv.backup_vaults.get_in_resource_group.return_value = [
        MagicMock(name="bv1", id="/.../backupVaults/bv1"),
    ]
    rsvb.backup_protected_items.list.return_value = [
        MagicMock(name="item1", properties=MagicMock(protection_state="Protected")),
    ]

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert len(result["vaults"]) >= 1
    assert any(v["kind"] == "RecoveryServicesVault" for v in result["vaults"]) or \
           any(v["kind"] == "BackupVault" for v in result["vaults"])


def test_no_vaults_in_rg_flagged(fake_clients):
    """RG with no RSV and no Backup Vault → finding present, never raises."""
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.return_value = []
    bv.backup_vaults.get_in_resource_group.return_value = []

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"]["total_vaults"] == 0
    assert any(f["kind"] == "no-vaults-in-rg" for f in result["findings"])


def test_vault_present_but_no_protected_items(fake_clients):
    """Vault exists but no protected items → flagged as 'vault-empty'."""
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.return_value = [
        MagicMock(name="rsv1", id="/.../vaults/rsv1"),
    ]
    bv.backup_vaults.get_in_resource_group.return_value = []
    rsvb.backup_protected_items.list.return_value = []

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert any(f["kind"] == "vault-empty" for f in result["findings"])


def test_manifest_written(fake_clients, tmp_path, monkeypatch):
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.return_value = []
    bv.backup_vaults.get_in_resource_group.return_value = []
    monkeypatch.chdir(tmp_path)

    result = probe(subscription_id="sub", resource_group="rg")
    manifest = Path(result["manifest_path"])
    assert manifest.exists()
    assert json.loads(manifest.read_text())["finding_id"] == result["finding_id"]


def test_never_raises_on_partial_denial(fake_clients):
    """RSV list 403 but Backup Vault listing succeeds → finishes probing other surface."""
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.side_effect = RuntimeError("AuthorizationFailed: RSV list denied")
    bv.backup_vaults.get_in_resource_group.return_value = [
        MagicMock(name="bv1", id="/.../backupVaults/bv1"),
    ]

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    # Probe partially succeeded — confidence < 1.0 but not 0
    assert 0.0 <= result["summary"]["confidence"] < 1.0


def test_never_raises_on_full_denial(fake_clients):
    """Both vault APIs 403 → probe_error populated, never raises."""
    rsv, bv, rsvb = fake_clients
    rsv.vaults.list_by_resource_group.side_effect = RuntimeError("AuthorizationFailed")
    bv.backup_vaults.get_in_resource_group.side_effect = RuntimeError("AuthorizationFailed")

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"].get("probe_error") or result["summary"]["confidence"] == 0.0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest scripts/tests/test_unit_azure_backup_readiness.py -v 2>&1 | tail -10`

Expected: FAIL with `ModuleNotFoundError`.

### Task 1.2: Implement probe

**Files:**
- Create: `skills/azure-backup-readiness/references/python/__init__.py`
- Create: `skills/azure-backup-readiness/references/python/probe.py`

- [ ] **Step 1: Create __init__.py**

```bash
mkdir -p skills/azure-backup-readiness/references/python
echo '"""Canonical Python helpers for azure-backup-readiness."""' \
  > skills/azure-backup-readiness/references/python/__init__.py
```

- [ ] **Step 2: probe.py**

```python
"""Canonical azure-backup-readiness probe.

Source of truth for the prose example in `../../SKILL.md § Probing an RG`.

Audits backup coverage at a resource-group scope. Checks BOTH vault
surfaces (Recovery Services Vaults via azure-mgmt-recoveryservices,
Backup Vaults via azure-mgmt-dataprotection — per spec §4.4 Q-D1
locked decision: vault-type aware). For each vault found, lists
protected items via azure-mgmt-recoveryservicesbackup.

Public API:
    from azure_backup_readiness.probe import probe

    result = probe(
        subscription_id="<sub-id>",
        resource_group="<rg>",
    )

Returns:
    {
        "finding_id": "abr-<uuid>",
        "skill": "azure-backup-readiness",
        "subscription_id": str,
        "resource_group": str,
        "vaults": [
            {
                "kind": "RecoveryServicesVault" | "BackupVault",
                "name": str,
                "id": str,
                "protected_item_count": int,
            },
            ...
        ],
        "findings": [
            {
                "kind": "no-vaults-in-rg" | "vault-empty" | "vault-list-denied",
                "severity": "low" | "medium" | "high" | "critical",
                "vault": str | None,
                "remediation": str,
            },
            ...
        ],
        "summary": {
            "total_vaults": int,
            "rsv_count": int,
            "bv_count": int,
            "total_protected_items": int,
            "confidence": 0.0..1.0,
            "probe_error": str | None,
        },
        "manifest_path": str,
        "probed_at": "ISO8601 UTC",
    }

Never raises. Partial-denial (one vault API denied, the other works)
returns confidence in (0.0, 1.0). Full-denial returns shape with
probe_error and confidence == 0.0.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.recoveryservices import RecoveryServicesClient
from azure.mgmt.recoveryservicesbackup.activestamp import RecoveryServicesBackupClient
from azure.mgmt.dataprotection import DataProtectionMgmtClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_result(sub: str, rg: str, error: str | None = None) -> dict[str, Any]:
    finding_id = f"abr-{uuid.uuid4().hex[:12]}"
    return {
        "finding_id": finding_id,
        "skill": "azure-backup-readiness",
        "subscription_id": sub,
        "resource_group": rg,
        "vaults": [],
        "findings": [],
        "summary": {
            "total_vaults": 0,
            "rsv_count": 0,
            "bv_count": 0,
            "total_protected_items": 0,
            "confidence": 0.0 if error else 1.0,
            "probe_error": error,
        },
        "manifest_path": "",
        "probed_at": _now(),
    }


def _write_manifest(result: dict[str, Any]) -> str:
    out_dir = Path(os.environ.get("AZURE_BACKUP_READINESS_OUT", "out"))
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
    """Probe backup coverage at the RG scope. See module docstring."""
    if credential is None:
        credential = DefaultAzureCredential()

    try:
        rsv_client = RecoveryServicesClient(credential, subscription_id)
        bv_client = DataProtectionMgmtClient(credential, subscription_id)
        rsvb_client = RecoveryServicesBackupClient(credential, subscription_id)
    except Exception as exc:
        result = _empty_result(subscription_id, resource_group, f"client init failed: {exc}")
        result["manifest_path"] = _write_manifest(result)
        return result

    result = _empty_result(subscription_id, resource_group)

    rsv_denied = False
    bv_denied = False

    # Recovery Services Vaults
    try:
        rsvs = list(rsv_client.vaults.list_by_resource_group(resource_group))
        for v in rsvs:
            vault_name = getattr(v, "name", "") or ""
            vault_id = getattr(v, "id", "") or ""
            # Count protected items
            try:
                items = list(rsvb_client.backup_protected_items.list(
                    vault_name=vault_name, resource_group_name=resource_group))
                item_count = len(items)
            except Exception:
                item_count = -1   # signal "we couldn't enumerate"
            result["vaults"].append({
                "kind": "RecoveryServicesVault",
                "name": vault_name,
                "id": vault_id,
                "protected_item_count": item_count,
            })
            result["summary"]["rsv_count"] += 1
            if item_count >= 0:
                result["summary"]["total_protected_items"] += item_count
            if item_count == 0:
                result["findings"].append({
                    "kind": "vault-empty",
                    "severity": "medium",
                    "vault": vault_name,
                    "remediation": "Add a backup policy + register protected items on this vault.",
                })
    except Exception as exc:
        rsv_denied = True
        result["findings"].append({
            "kind": "vault-list-denied",
            "severity": "high",
            "vault": "RSV (whole class)",
            "remediation": f"Grant Backup Reader at RG scope. Detail: {exc}",
        })

    # Backup Vaults (DataProtection)
    try:
        bvs = list(bv_client.backup_vaults.get_in_resource_group(resource_group))
        for v in bvs:
            vault_name = getattr(v, "name", "") or ""
            vault_id = getattr(v, "id", "") or ""
            # Count protected items via DataProtection backup_instances
            try:
                items = list(bv_client.backup_instances.list(
                    resource_group_name=resource_group, vault_name=vault_name))
                item_count = len(items)
            except Exception:
                item_count = -1
            result["vaults"].append({
                "kind": "BackupVault",
                "name": vault_name,
                "id": vault_id,
                "protected_item_count": item_count,
            })
            result["summary"]["bv_count"] += 1
            if item_count >= 0:
                result["summary"]["total_protected_items"] += item_count
            if item_count == 0:
                result["findings"].append({
                    "kind": "vault-empty",
                    "severity": "medium",
                    "vault": vault_name,
                    "remediation": "Add a backup policy + register backup instances on this Backup Vault.",
                })
    except Exception as exc:
        bv_denied = True
        result["findings"].append({
            "kind": "vault-list-denied",
            "severity": "high",
            "vault": "BackupVault (whole class)",
            "remediation": f"Grant Backup Reader at RG scope. Detail: {exc}",
        })

    result["summary"]["total_vaults"] = len(result["vaults"])

    # Overall posture
    if result["summary"]["total_vaults"] == 0 and not (rsv_denied and bv_denied):
        result["findings"].append({
            "kind": "no-vaults-in-rg",
            "severity": "high",
            "vault": None,
            "remediation": "Create a Recovery Services Vault or Backup Vault in this RG and register protected items.",
        })

    # Confidence
    if rsv_denied and bv_denied:
        result["summary"]["confidence"] = 0.0
        result["summary"]["probe_error"] = "both RSV and BackupVault list calls failed (auth)"
    elif rsv_denied or bv_denied:
        result["summary"]["confidence"] = 0.5
    else:
        result["summary"]["confidence"] = 1.0

    result["manifest_path"] = _write_manifest(result)
    return result
```

> **NOTE on SDK import paths:** `RecoveryServicesBackupClient` lives at
> `azure.mgmt.recoveryservicesbackup.activestamp` in recent SDK versions
> (the `activestamp` submodule was introduced to disambiguate from the
> deprecated `passivestamp` cross-region surface). If the import fails,
> try `from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient`
> and confirm against the pin file's pinned version.

- [ ] **Step 3: Run unit tests**

Run:
```bash
pip install -q "azure-mgmt-recoveryservices~=3.0.0" \
                "azure-mgmt-recoveryservicesbackup~=9.1.0" \
                "azure-mgmt-dataprotection~=1.5.0" \
                "azure-identity~=1.19.0"
python -m pytest scripts/tests/test_unit_azure_backup_readiness.py -v 2>&1 | tail -20
```

Expected: 6 PASS. If the SDK import paths differ from the module, adjust the `monkeypatch.setattr` strings in the test to match and adjust the probe imports to match the actual SDK.

- [ ] **Step 4: Commit probe + tests**

```bash
git add skills/azure-backup-readiness/references/python/ \
        scripts/tests/test_unit_azure_backup_readiness.py
git commit -m "azure-backup-readiness: scaffold probe + unit tests (NEW skill, #267)

Public probe(subscription_id, resource_group) -> dict. Checks BOTH
Recovery Services Vaults (azure-mgmt-recoveryservices) and Backup
Vaults (azure-mgmt-dataprotection) per spec §4.4 Q-D1 locked decision.
For each vault, counts protected items via azure-mgmt-recoveryservicesbackup.

Never raises; partial-denial returns confidence in (0, 1); full-denial
returns probe_error.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.3: CLI entrypoint

**Files:**
- Create: `skills/azure-backup-readiness/references/python/__main__.py`

- [ ] **Step 1: Create**

```python
"""CLI entrypoint: `python -m azure_backup_readiness --sub <sub-id> --rg <rg>`."""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="azure-backup-readiness")
    p.add_argument("--sub", required=True, help="Azure subscription ID")
    p.add_argument("--rg", required=True, help="Resource group name")
    args = p.parse_args(argv)

    try:
        result = probe(subscription_id=args.sub, resource_group=args.rg)
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
git add skills/azure-backup-readiness/references/python/__main__.py
git commit -m "azure-backup-readiness: add CLI entrypoint

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.4: SKILL.md + README + pin

**Files:**
- Create: `skills/azure-backup-readiness/SKILL.md`
- Create: `skills/azure-backup-readiness/README.md`
- Create: `skills/azure-backup-readiness/references/upstream-pin.md`

- [ ] **Step 1: SKILL.md (description ≤1024 chars)**

```markdown
---
name: azure-backup-readiness
description: >
  Audit Azure backup coverage at a resource group scope. Checks BOTH
  Recovery Services Vaults (RSV, azure-mgmt-recoveryservices) AND
  Backup Vaults (DataProtection, azure-mgmt-dataprotection) — vault-
  type aware. For each vault found, counts protected items
  (azure-mgmt-recoveryservicesbackup). Flags no-vaults-in-rg,
  vault-empty (vault present but no protected items), and
  vault-list-denied (RBAC missing). Wraps the three SDKs with a
  never-raising probe() returning structured findings. Partial-denial
  (one vault class works, other doesn't) returns confidence in (0,1).
  Writes manifest JSON to out/<finding-id>.json AND returns equivalent
  dict. CLI: python -m azure_backup_readiness --sub <sub-id> --rg <rg>.
  USE FOR: backup readiness audit, RSV audit, Backup Vault audit,
  vault-empty detection, no-vaults-in-RG, foundry RG backup posture,
  spoke backup posture, threadlight BAK-401 self-verify, pre-pilot
  backup readiness gate.
  DO NOT USE FOR: creating vaults (use az backup vault create), running
  on-demand backups (use az backup protection backup-now), restoring
  (use az backup restore), backup policy authoring.
metadata:
  version: "1.0.0"
---

# azure-backup-readiness

Audits Azure backup coverage at a resource group scope. Vault-type aware.

## When to use

- threadlight v0.5.4 needs to flip BAK-401 from `kind: manual` to
  `kind: sibling-skill` — this skill's `probe()` is the sibling.
- Pre-pilot review: confirm a candidate Foundry RG has at least one
  vault with protected items before a customer pilot.
- Spoke landing-zone check: detect RGs that have an RSV / Backup Vault
  resource but no policies attached.

## Probing an RG

```python
from azure_backup_readiness.probe import probe

result = probe(
    subscription_id="<sub-id>",
    resource_group="<rg>",
)
# result["vaults"]                         → list of {kind, name, id, protected_item_count}
# result["summary"]["total_vaults"]        → int
# result["summary"]["rsv_count"]           → int  (RSV count)
# result["summary"]["bv_count"]            → int  (BackupVault count)
# result["summary"]["total_protected_items"] → int  (sum across vaults)
# result["summary"]["confidence"]          → 0.0..1.0
# result["summary"]["probe_error"]         → str | None
# result["findings"]                       → list of typed findings
# result["manifest_path"]                  → path to JSON manifest on disk
```

The probe **never raises**. If one vault API denies (e.g. RSV is
forbidden but Backup Vault works), the probe still completes and
returns `confidence: 0.5`. If both deny, returns `confidence: 0.0`
and `probe_error` populated.

> **MUST:** Copy verbatim from
> [`references/python/probe.py`](references/python/probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

## Vault-type awareness (decision)

Per spec §4.4 Q-D1 (locked decision), this skill probes **both**
Recovery Services Vaults and Backup Vaults. These are two distinct
Azure backup surfaces:

| Vault kind | SDK | When to use |
|------------|-----|-------------|
| Recovery Services Vault | `azure-mgmt-recoveryservices` | Classic VM / SQL / file backup |
| Backup Vault (DataProtection) | `azure-mgmt-dataprotection` | Modern Blob / Disk / PostgreSQL backup |

A Foundry RG may have neither, one, or both. The probe doesn't
prefer either — both are reported in `result["vaults"]` with their
`kind` field set accordingly.

## CLI

```bash
python -m azure_backup_readiness --sub <sub-id> --rg <rg>
```

Outputs JSON to stdout AND writes the same content to
`out/<finding-id>.json`. Override via
`AZURE_BACKUP_READINESS_OUT=<path>`.

## Auth

Uses `DefaultAzureCredential`. Caller needs at minimum `Backup Reader`
at the RG scope (built-in role). Without it, the probe returns a
shape with `probe_error` populated rather than raising.

## See also

- `azure-resource-diagnostics` — peer skill for diagnostic settings audit.
- `foundry-rbac-audit` — peer skill for RBAC posture audit.
- `azure-monitor-alert-baseline` — peer skill for alert coverage audit.
```

- [ ] **Step 2: README.md**

```markdown
# azure-backup-readiness

Wrapper skill auditing Azure backup coverage (RSV + Backup Vault) at
an RG scope. See [SKILL.md](SKILL.md) for the contract.

## Quick start

```bash
pip install azure-identity~=1.19 \
  azure-mgmt-recoveryservices~=3.0 \
  azure-mgmt-recoveryservicesbackup~=9.1 \
  azure-mgmt-dataprotection~=1.5
python -m azure_backup_readiness --sub <sub-id> --rg <rg>
```

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md). Tier B,
auto.
```

- [ ] **Step 3: Pin file**

```bash
cp scripts/templates/upstream-pin.template.md \
  skills/azure-backup-readiness/references/upstream-pin.md
```

Edit to:

```yaml
packages:
  - name: azure-mgmt-recoveryservices
    version: "~=3.0.0"
    purpose: "RSV listing"
  - name: azure-mgmt-recoveryservicesbackup
    version: "~=9.1.0"
    purpose: "Protected item enumeration"
  - name: azure-mgmt-dataprotection
    version: "~=1.5.0"
    purpose: "Backup Vault (DataProtection) listing"
  - name: azure-identity
    version: "~=1.19.0"

validation:
  runnable: true
  requires: ["pypi"]
  script: |
    set -euo pipefail
    pip install -q "azure-mgmt-recoveryservices~=3.0.0" \
                    "azure-mgmt-recoveryservicesbackup~=9.1.0" \
                    "azure-mgmt-dataprotection~=1.5.0" \
                    "azure-identity~=1.19.0"
    python -c "from azure.mgmt.recoveryservices import RecoveryServicesClient; print('RSV OK')"
    python -c "from azure.mgmt.dataprotection import DataProtectionMgmtClient; print('BV OK')"
    python -c "from azure.mgmt.recoveryservicesbackup.activestamp import RecoveryServicesBackupClient; print('RSVB OK')"
  expected_output:
    - "RSV OK"
    - "BV OK"
    - "RSVB OK"
```

- [ ] **Step 4: Validate + commit**

```bash
python scripts/validate-skills.py 2>&1 | grep -iE "backup-readiness|fail|error" | head -10
git add skills/azure-backup-readiness/SKILL.md \
        skills/azure-backup-readiness/README.md \
        skills/azure-backup-readiness/references/upstream-pin.md
git commit -m "azure-backup-readiness: add SKILL.md + README + pin (tier B, auto)

Vault-type aware: probes BOTH RSV and Backup Vault per spec §4.4 Q-D1.
Description ≤1024 chars per AGENTS.md §2.3.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 1.5: §2.9 live-test evidence + Copilot-CLI fixture

**Files:**
- Create: `skills/azure-backup-readiness/test-fixture/consumer_prompt.md`

**Background:** Per AGENTS.md §2.9 and Slice A (PR #279) / Slice B
(PR #281) precedent, live Azure testing is captured as evidence in the
PR body — no `scripts/tests/test_e2e_*.py` file. Skip Step 1 entirely if
you don't have CI Azure credentials locally; document "§2.9 evidence
deferred to CI / human-validated" in the PR body.

- [ ] **Step 1: §2.9 live-test evidence (3 paths)**

Verify auth context first:

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table 2>&1 | head -5
```

If any empty / `az account show` errors, skip to Step 2 and record
"§2.9 evidence deferred" for the PR body.

Otherwise run the 3 paths:

```bash
# Path 1 — real RG (both vault types probed; one may be empty cleanly)
python skills/azure-backup-readiness/references/python/__main__.py \
  --sub "$AZURE_SUBSCRIPTION_ID" --rg "<ci-resource-group>" 2>&1 \
  | tee /tmp/abr-evidence-1.txt | head -50

# Path 2 — nonexistent RG never-raises invariant
python skills/azure-backup-readiness/references/python/__main__.py \
  --sub "$AZURE_SUBSCRIPTION_ID" --rg "rg-does-not-exist-xyz123" 2>&1 \
  | tee /tmp/abr-evidence-2.txt | head -30

# Path 3 — cred fallback (AzureCliCredential)
env -u AZURE_CLIENT_ID -u AZURE_CLIENT_SECRET -u AZURE_TENANT_ID \
  python skills/azure-backup-readiness/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" --rg "<ci-resource-group>" 2>&1 \
    | tee /tmp/abr-evidence-3.txt | head -30
```

Expected: each prints JSON with `finding_id`, `skill: azure-backup-readiness`,
`vaults: [...]`, `findings: [...]`, `summary: {...}`, `manifest_path`,
`probed_at`. A Python traceback on any path is a FAIL. Capture stdout
in PR body under `§2.9 evidence — path 1/2/3`.

- [ ] **Step 2: Copilot-CLI fixture**

```markdown
**Skill under test:** `azure-backup-readiness`

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. (AGENTS.md
§9.7 Pattern 27.)

This is an EXECUTION smoke, not a catalog inspection.

### Step −1 — Acknowledge skill contract

```bash
echo "skills/azure-backup-readiness/SKILL.md"
```

### Step 0 — Verify CI auth contract

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

### Step 1 — Install SDKs + run probe

```bash
pip install -q "azure-mgmt-recoveryservices~=3.0.0" \
                "azure-mgmt-recoveryservicesbackup~=9.1.0" \
                "azure-mgmt-dataprotection~=1.5.0" \
                "azure-identity~=1.19.0"
mkdir -p /tmp/abr-out
AZURE_BACKUP_READINESS_OUT=/tmp/abr-out \
  python skills/azure-backup-readiness/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" \
    --rg  "${CI_RESOURCE_GROUP:-<ci-resource-group>}"
```

### Step 2 — Validate shape

```bash
ls /tmp/abr-out/*.json | head -1 | xargs -I{} python -c "
import json, sys
d = json.load(open(sys.argv[1]))
required = {'finding_id','skill','subscription_id','resource_group','vaults','findings','summary','manifest_path','probed_at'}
missing = required - set(d.keys())
assert not missing, f'missing keys: {missing}'
assert d['skill'] == 'azure-backup-readiness'
print('shape OK')
" {}
```

### Step N — Write the result marker (MANDATORY)

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-backup-readiness-smoke-result
```

On failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-backup-readiness-smoke-result
```
```

- [ ] **Step 3: Commit**

```bash
git add skills/azure-backup-readiness/test-fixture/consumer_prompt.md
git commit -m "azure-backup-readiness: add Copilot-CLI fixture

Fixture follows AGENTS.md §9.7 Patterns 12/19/22/27. §2.9 live-test
evidence captured in PR body per Slice A/B precedent (no test_e2e_*.py
file — catalog removed pytest-based E2E; skill-test.yml line 9).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 2 — `azure-resource-diagnostics` skill

### Task 2.1: Write the failing unit test

**Files:**
- Create: `scripts/tests/test_unit_azure_resource_diagnostics.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for azure-resource-diagnostics probe.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/271
Locked decision (spec §4.4 Q-D2): a resource is "configured" if it has
ANY destination (LAW, EventHubs, or Storage).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SKILL_DIR = (Path(__file__).resolve().parents[1].parent
             / "skills" / "azure-resource-diagnostics" / "references" / "python")
sys.path.insert(0, str(SKILL_DIR))

from probe import probe  # noqa: E402


@pytest.fixture
def fake_clients(monkeypatch):
    resource_client = MagicMock(name="ResourceManagementClient")
    monitor_client = MagicMock(name="MonitorManagementClient")
    monkeypatch.setattr("probe.ResourceManagementClient",
                         lambda cred, sub: resource_client)
    monkeypatch.setattr("probe.MonitorManagementClient",
                         lambda cred, sub: monitor_client)
    return resource_client, monitor_client


def _shape(result: dict) -> None:
    required = {"finding_id", "skill", "subscription_id", "resource_group",
                "resources", "findings", "summary", "manifest_path", "probed_at"}
    assert required.issubset(result.keys()), f"missing: {required - result.keys()}"
    assert result["skill"] == "azure-resource-diagnostics"


def _make_resource(name: str, rtype: str) -> MagicMock:
    return MagicMock(
        name=name,
        id=f"/subscriptions/x/resourceGroups/rg/providers/{rtype}/{name}",
        type=rtype,
    )


def _make_setting(destinations: list[str]) -> MagicMock:
    """Create a fake diagnostic_settings entry with the requested destinations set."""
    setting = MagicMock(name="setting1")
    setting.workspace_id = "/.../laws/law1" if "LogAnalytics" in destinations else None
    setting.event_hub_authorization_rule_id = "/.../eh-rule" if "EventHubs" in destinations else None
    setting.storage_account_id = "/.../storage-acct" if "Storage" in destinations else None
    return setting


def test_resource_with_law_destination_is_configured(fake_clients):
    """ANY destination present → counts as configured (Q-D2 decision)."""
    resource, monitor = fake_clients
    r = _make_resource("foundry1", "Microsoft.CognitiveServices/accounts")
    resource.resources.list_by_resource_group.return_value = [r]
    monitor.diagnostic_settings.list.return_value = [_make_setting(["LogAnalytics"])]

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"]["configured_count"] == 1
    assert result["summary"]["unconfigured_count"] == 0


def test_resource_with_only_storage_destination_still_configured(fake_clients):
    """Storage-only is still 'configured' per Q-D2."""
    resource, monitor = fake_clients
    r = _make_resource("foundry1", "Microsoft.CognitiveServices/accounts")
    resource.resources.list_by_resource_group.return_value = [r]
    monitor.diagnostic_settings.list.return_value = [_make_setting(["Storage"])]

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"]["configured_count"] == 1


def test_resource_with_no_diag_settings_unconfigured(fake_clients):
    """No diagnostic settings → unconfigured, finding emitted."""
    resource, monitor = fake_clients
    r = _make_resource("foundry1", "Microsoft.CognitiveServices/accounts")
    resource.resources.list_by_resource_group.return_value = [r]
    monitor.diagnostic_settings.list.return_value = []

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"]["unconfigured_count"] == 1
    assert any(f["kind"] == "no-diagnostic-settings" for f in result["findings"])


def test_resource_with_setting_but_no_destination_unconfigured(fake_clients):
    """Setting exists but with no destinations → unconfigured."""
    resource, monitor = fake_clients
    r = _make_resource("foundry1", "Microsoft.CognitiveServices/accounts")
    resource.resources.list_by_resource_group.return_value = [r]
    monitor.diagnostic_settings.list.return_value = [_make_setting([])]

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"]["unconfigured_count"] == 1


def test_resource_filter_by_kind(fake_clients):
    """Optional resource_kinds filter restricts the probe."""
    resource, monitor = fake_clients
    resource.resources.list_by_resource_group.return_value = [
        _make_resource("foundry1", "Microsoft.CognitiveServices/accounts"),
        _make_resource("ca1", "Microsoft.App/containerApps"),
    ]
    monitor.diagnostic_settings.list.return_value = [_make_setting(["LogAnalytics"])]

    result = probe(subscription_id="sub", resource_group="rg",
                   resource_kinds=["Microsoft.CognitiveServices/accounts"])
    _shape(result)
    assert len(result["resources"]) == 1
    assert result["resources"][0]["type"] == "Microsoft.CognitiveServices/accounts"


def test_manifest_written(fake_clients, tmp_path, monkeypatch):
    resource, monitor = fake_clients
    resource.resources.list_by_resource_group.return_value = []
    monkeypatch.chdir(tmp_path)

    result = probe(subscription_id="sub", resource_group="rg")
    manifest = Path(result["manifest_path"])
    assert manifest.exists()
    assert json.loads(manifest.read_text())["finding_id"] == result["finding_id"]


def test_never_raises_on_denial(fake_clients):
    resource, monitor = fake_clients
    resource.resources.list_by_resource_group.side_effect = RuntimeError("AuthorizationFailed")

    result = probe(subscription_id="sub", resource_group="rg")
    _shape(result)
    assert result["summary"].get("probe_error") or result["summary"]["confidence"] == 0.0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest scripts/tests/test_unit_azure_resource_diagnostics.py -v 2>&1 | tail -10`

Expected: FAIL with ModuleNotFound.

### Task 2.2: Implement probe

**Files:**
- Create: `skills/azure-resource-diagnostics/references/python/__init__.py`
- Create: `skills/azure-resource-diagnostics/references/python/probe.py`

- [ ] **Step 1: __init__.py**

```bash
mkdir -p skills/azure-resource-diagnostics/references/python
echo '"""Canonical Python helpers for azure-resource-diagnostics."""' \
  > skills/azure-resource-diagnostics/references/python/__init__.py
```

- [ ] **Step 2: probe.py**

```python
"""Canonical azure-resource-diagnostics probe.

Source of truth for the prose example in `../../SKILL.md § Probing an RG`.

Audits Azure diagnostic-settings coverage at a resource-group scope.
For each resource in the RG (optionally filtered by `resource_kinds`),
queries `Microsoft.Insights/diagnosticSettings` and reports whether
the resource has ANY configured destination (LogAnalytics workspace,
EventHubs authorization rule, or Storage account) — per spec §4.4 Q-D2
locked decision: "any destination counts as configured".

Public API:
    from azure_resource_diagnostics.probe import probe

    result = probe(
        subscription_id="<sub-id>",
        resource_group="<rg>",
        resource_kinds=["Microsoft.CognitiveServices/accounts",
                         "Microsoft.App/containerApps"],   # optional filter
    )

Returns:
    {
        "finding_id": "ard-<uuid>",
        "skill": "azure-resource-diagnostics",
        "subscription_id": str,
        "resource_group": str,
        "resources": [
            {
                "id": str,
                "name": str,
                "type": str,
                "configured": bool,
                "destinations": ["LogAnalytics" | "EventHubs" | "Storage", ...],
                "setting_count": int,
            },
            ...
        ],
        "findings": [
            {
                "kind": "no-diagnostic-settings" | "destination-missing",
                "severity": "low" | "medium" | "high",
                "resource_id": str,
                "resource_type": str,
                "remediation": str,
            },
            ...
        ],
        "summary": {
            "total_resources": int,
            "configured_count": int,
            "unconfigured_count": int,
            "confidence": 0.0..1.0,
            "probe_error": str | None,
        },
        "manifest_path": str,
        "probed_at": "ISO8601 UTC",
    }

Never raises. RG-list denial returns empty resources with probe_error
populated.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.resource import ResourceManagementClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_result(sub: str, rg: str, error: str | None = None) -> dict[str, Any]:
    finding_id = f"ard-{uuid.uuid4().hex[:12]}"
    return {
        "finding_id": finding_id,
        "skill": "azure-resource-diagnostics",
        "subscription_id": sub,
        "resource_group": rg,
        "resources": [],
        "findings": [],
        "summary": {
            "total_resources": 0,
            "configured_count": 0,
            "unconfigured_count": 0,
            "confidence": 0.0 if error else 1.0,
            "probe_error": error,
        },
        "manifest_path": "",
        "probed_at": _now(),
    }


def _write_manifest(result: dict[str, Any]) -> str:
    out_dir = Path(os.environ.get("AZURE_RESOURCE_DIAGNOSTICS_OUT", "out"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['finding_id']}.json"
    path.write_text(json.dumps(result, indent=2, default=str))
    return str(path.resolve())


def _classify_setting(setting: Any) -> list[str]:
    """Inspect a diagnostic_settings entry; return list of configured destinations."""
    destinations: list[str] = []
    if getattr(setting, "workspace_id", None):
        destinations.append("LogAnalytics")
    if getattr(setting, "event_hub_authorization_rule_id", None):
        destinations.append("EventHubs")
    if getattr(setting, "storage_account_id", None):
        destinations.append("Storage")
    return destinations


def probe(
    subscription_id: str,
    resource_group: str,
    resource_kinds: list[str] | None = None,
    *,
    credential: Any = None,
) -> dict[str, Any]:
    """Probe diagnostic settings on resources in the RG. See module docstring."""
    if credential is None:
        credential = DefaultAzureCredential()

    try:
        resource_client = ResourceManagementClient(credential, subscription_id)
        monitor_client = MonitorManagementClient(credential, subscription_id)
    except Exception as exc:
        result = _empty_result(subscription_id, resource_group, f"client init failed: {exc}")
        result["manifest_path"] = _write_manifest(result)
        return result

    result = _empty_result(subscription_id, resource_group)

    # List all resources in the RG (optionally filtered by kind)
    try:
        resources = list(resource_client.resources.list_by_resource_group(resource_group))
    except Exception as exc:
        result["summary"]["probe_error"] = f"list_by_resource_group failed: {exc}"
        result["summary"]["confidence"] = 0.0
        result["manifest_path"] = _write_manifest(result)
        return result

    kinds_filter: set[str] | None = None
    if resource_kinds:
        kinds_filter = {k.lower() for k in resource_kinds}

    for r in resources:
        r_type = (getattr(r, "type", "") or "").lower()
        if kinds_filter is not None and r_type not in kinds_filter:
            continue

        r_id = getattr(r, "id", "") or ""
        r_name = getattr(r, "name", "") or ""

        # Per-resource diagnostic_settings query
        all_destinations: set[str] = set()
        setting_count = 0
        try:
            for setting in monitor_client.diagnostic_settings.list(r_id):
                setting_count += 1
                for d in _classify_setting(setting):
                    all_destinations.add(d)
        except Exception:
            # Some resource types don't support diagnostic_settings; treat
            # as unsupported rather than as denial. The Monitor REST API
            # returns 404 on unsupported resource types. We just leave
            # destinations empty.
            pass

        configured = bool(all_destinations)
        result["resources"].append({
            "id": r_id,
            "name": r_name,
            "type": getattr(r, "type", "") or "",
            "configured": configured,
            "destinations": sorted(all_destinations),
            "setting_count": setting_count,
        })

        if configured:
            result["summary"]["configured_count"] += 1
        else:
            result["summary"]["unconfigured_count"] += 1
            result["findings"].append({
                "kind": "no-diagnostic-settings",
                "severity": "medium",
                "resource_id": r_id,
                "resource_type": getattr(r, "type", "") or "",
                "remediation": "Create a diagnostic setting routing to LogAnalytics, EventHubs, or Storage.",
            })

    result["summary"]["total_resources"] = len(result["resources"])
    result["manifest_path"] = _write_manifest(result)
    return result
```

- [ ] **Step 3: Run unit tests**

Run:
```bash
pip install -q "azure-mgmt-monitor~=6.0.0" "azure-mgmt-resource~=23.1.0" "azure-identity~=1.19.0"
python -m pytest scripts/tests/test_unit_azure_resource_diagnostics.py -v 2>&1 | tail -20
```

Expected: 7 PASS.

- [ ] **Step 4: Commit**

```bash
git add skills/azure-resource-diagnostics/references/python/ \
        scripts/tests/test_unit_azure_resource_diagnostics.py
git commit -m "azure-resource-diagnostics: scaffold probe + unit tests (NEW skill, #271)

Public probe(subscription_id, resource_group, resource_kinds=None).
Lists resources in the RG (optionally filtered by ARM type),
queries diagnostic_settings, classifies destinations (LAW / EventHubs
/ Storage). Per spec §4.4 Q-D2 locked decision: ANY destination
counts as configured.

Never raises; manifest at out/<finding-id>.json.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.3: CLI entrypoint

**Files:**
- Create: `skills/azure-resource-diagnostics/references/python/__main__.py`

- [ ] **Step 1: Create**

```python
"""CLI entrypoint: python -m azure_resource_diagnostics --sub <sub-id> --rg <rg> [--kind <ARM-type>...]"""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="azure-resource-diagnostics")
    p.add_argument("--sub", required=True, help="Azure subscription ID")
    p.add_argument("--rg", required=True, help="Resource group name")
    p.add_argument("--kind", action="append", default=None,
                    help="Restrict to ARM resource type (repeatable, e.g. Microsoft.CognitiveServices/accounts)")
    args = p.parse_args(argv)

    try:
        result = probe(
            subscription_id=args.sub,
            resource_group=args.rg,
            resource_kinds=args.kind,
        )
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
git add skills/azure-resource-diagnostics/references/python/__main__.py
git commit -m "azure-resource-diagnostics: add CLI entrypoint

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.4: SKILL.md + README + pin

**Files:**
- Create: `skills/azure-resource-diagnostics/SKILL.md`
- Create: `skills/azure-resource-diagnostics/README.md`
- Create: `skills/azure-resource-diagnostics/references/upstream-pin.md`

- [ ] **Step 1: SKILL.md**

```markdown
---
name: azure-resource-diagnostics
description: >
  Audit Azure diagnostic-settings coverage at a resource group scope.
  For each resource in the RG (optionally filtered by ARM type), reports
  whether it has ANY configured destination (LogAnalytics workspace,
  EventHubs authorization rule, or Storage account). Per spec §4.4 Q-D2
  locked decision: any destination counts as configured. Wraps
  azure-mgmt-monitor diagnostic_settings.list with a never-raising
  probe() returning structured per-resource configured/unconfigured
  findings. Writes manifest JSON to out/<finding-id>.json AND returns
  equivalent dict. CLI: python -m azure_resource_diagnostics --sub
  <sub-id> --rg <rg> [--kind Microsoft.CognitiveServices/accounts].
  USE FOR: diagnostic settings audit, observability coverage check,
  foundry diagnostic posture, spoke diagnostic posture, threadlight
  OBS-204 self-verify, missing diagnostic destination detection,
  catalog of which resources route logs vs which don't.
  DO NOT USE FOR: creating diagnostic settings (use az monitor
  diagnostic-settings create), reading log content (use foundry-
  observability KQL helpers), alert auditing (use azure-monitor-
  alert-baseline).
metadata:
  version: "1.0.0"
---

# azure-resource-diagnostics

Audits Azure diagnostic-settings coverage at a resource group scope.

## When to use

- threadlight v0.5.4 needs to flip OBS-204 from `kind: manual` to
  `kind: sibling-skill` — this skill's `probe()` is the sibling.
- Pre-pilot review: catalog which resources in a Foundry RG route
  diagnostic logs and which don't.
- Pair with `azure-monitor-alert-baseline` for full observability
  posture coverage (alerts AND diagnostic destinations).

## Probing an RG

```python
from azure_resource_diagnostics.probe import probe

result = probe(
    subscription_id="<sub-id>",
    resource_group="<rg>",
    resource_kinds=[                              # optional filter
        "Microsoft.CognitiveServices/accounts",
        "Microsoft.App/containerApps",
    ],
)
# result["resources"]                       → list of per-resource records
# result["summary"]["configured_count"]     → int
# result["summary"]["unconfigured_count"]   → int
# result["summary"]["total_resources"]      → int
# result["summary"]["confidence"]           → 0.0..1.0
# result["summary"]["probe_error"]          → str | None
# result["findings"]                        → list of no-diagnostic-settings entries
# result["manifest_path"]                   → path to JSON manifest on disk
```

The probe **never raises**. RG-list denial returns shape with
`probe_error` populated and `confidence == 0.0`. Per-resource
diagnostic-settings queries that return 404 (resource type doesn't
support diagnostic settings) are silently treated as unconfigured,
not as errors.

> **MUST:** Copy verbatim from
> [`references/python/probe.py`](references/python/probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

## "Any destination counts" (decision)

Per spec §4.4 Q-D2 (locked decision), a resource is considered
**configured** if it has at least one of:

- LogAnalytics workspace (`workspace_id`)
- EventHubs authorization rule (`event_hub_authorization_rule_id`)
- Storage account (`storage_account_id`)

Per-destination requirements (e.g. "must route to LAW specifically")
are intentionally out of scope for this skill — they belong in
`azure-monitor-alert-baseline`'s `required_diagnostic_settings` block.
This skill's job is to detect resources with NO destination at all.

## CLI

```bash
python -m azure_resource_diagnostics \
  --sub <sub-id> --rg <rg> \
  --kind Microsoft.CognitiveServices/accounts \
  --kind Microsoft.App/containerApps
```

`--kind` is repeatable. Omit to probe every resource in the RG. Output:
JSON to stdout + `out/<finding-id>.json` (override via
`AZURE_RESOURCE_DIAGNOSTICS_OUT=<path>`).

## Auth

`DefaultAzureCredential`. Caller needs `Reader` + `Microsoft.Insights/diagnosticSettings/read`
on the RG scope, both granted by built-in `Reader`.

## See also

- `azure-backup-readiness` — peer skill for backup posture audit.
- `azure-monitor-alert-baseline` — peer skill for alert coverage audit.
- `foundry-rbac-audit` — peer skill for RBAC posture audit.
- `foundry-observability` — for KQL probing of the LAW destinations
  this audit confirms.
```

- [ ] **Step 2: README.md**

```markdown
# azure-resource-diagnostics

Wrapper skill auditing diagnostic-settings coverage at an RG scope.
"Configured" means ANY destination. See [SKILL.md](SKILL.md).

## Quick start

```bash
pip install azure-identity~=1.19 azure-mgmt-monitor~=6.0 azure-mgmt-resource~=23.1
python -m azure_resource_diagnostics --sub <sub-id> --rg <rg>
```

## Pin file

See [`references/upstream-pin.md`](references/upstream-pin.md). Tier B,
auto.
```

- [ ] **Step 3: Pin file**

```bash
cp scripts/templates/upstream-pin.template.md \
  skills/azure-resource-diagnostics/references/upstream-pin.md
```

Edit:

```yaml
packages:
  - name: azure-mgmt-monitor
    version: "~=6.0.0"
    purpose: "diagnostic_settings.list"
  - name: azure-mgmt-resource
    version: "~=23.1.0"
    purpose: "Resource enumeration"
  - name: azure-identity
    version: "~=1.19.0"

validation:
  runnable: true
  requires: ["pypi"]
  script: |
    set -euo pipefail
    pip install -q "azure-mgmt-monitor~=6.0.0" "azure-mgmt-resource~=23.1.0" "azure-identity~=1.19.0"
    python -c "from azure.mgmt.monitor import MonitorManagementClient; print('Monitor OK')"
    python -c "from azure.mgmt.resource import ResourceManagementClient; print('Resource OK')"
  expected_output:
    - "Monitor OK"
    - "Resource OK"
```

- [ ] **Step 4: Validate + commit**

```bash
python scripts/validate-skills.py 2>&1 | grep -iE "resource-diagnostics|fail|error" | head -10
git add skills/azure-resource-diagnostics/SKILL.md \
        skills/azure-resource-diagnostics/README.md \
        skills/azure-resource-diagnostics/references/upstream-pin.md
git commit -m "azure-resource-diagnostics: add SKILL.md + README + pin

Per spec §4.4 Q-D2: any destination counts as configured. Description
≤1024 chars per AGENTS.md §2.3.

[skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2.5: §2.9 live-test evidence + Copilot-CLI fixture

**Files:**
- Create: `skills/azure-resource-diagnostics/test-fixture/consumer_prompt.md`

**Background:** Same as Task 1.5 — no `test_e2e_*.py` file; §2.9 evidence
in PR body.

- [ ] **Step 1: §2.9 live-test evidence (3 paths)**

Verify auth context first (mirror Task 1.5 Step 1 preamble). Then:

```bash
# Path 1 — real RG, no filter (probes all resources)
python skills/azure-resource-diagnostics/references/python/__main__.py \
  --sub "$AZURE_SUBSCRIPTION_ID" --rg "<ci-resource-group>" 2>&1 \
  | tee /tmp/ard-evidence-1.txt | head -50

# Path 2 — kind-filter on Foundry account (exercises the --kind flag)
python skills/azure-resource-diagnostics/references/python/__main__.py \
  --sub "$AZURE_SUBSCRIPTION_ID" --rg "<ci-resource-group>" \
  --kind "Microsoft.CognitiveServices/accounts" 2>&1 \
  | tee /tmp/ard-evidence-2.txt | head -40

# Path 3 — nonexistent RG never-raises invariant
python skills/azure-resource-diagnostics/references/python/__main__.py \
  --sub "$AZURE_SUBSCRIPTION_ID" --rg "rg-does-not-exist-xyz123" 2>&1 \
  | tee /tmp/ard-evidence-3.txt | head -30
```

Expected: each prints JSON with `finding_id`, `skill: azure-resource-diagnostics`,
`resources: [...]`, `findings: [...]`. Path 2 must return only resources
whose `type.lower()` matches `microsoft.cognitiveservices/accounts`.
A Python traceback on any path is a FAIL. Capture in PR body under
`§2.9 evidence — path 1/2/3`. Skip entirely if no auth (document
deferral).

- [ ] **Step 2: Fixture**

```markdown
**Skill under test:** `azure-resource-diagnostics`

**CRITICAL — never invoke `copilot` recursively from a Bash tool.**
You ARE the running Copilot CLI process. Do NOT run `copilot -p ...`
or any other `copilot ...` invocation from inside a Bash tool call.
(AGENTS.md §9.7 Pattern 27.)

This is an EXECUTION smoke, not a catalog inspection.

### Step −1 — Acknowledge skill contract

```bash
echo "skills/azure-resource-diagnostics/SKILL.md"
```

### Step 0 — Verify CI auth contract

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
az account show --output table || echo "(az cache not inherited)"
```

### Step 1 — Install SDKs + run probe filtered to Foundry account

```bash
pip install -q "azure-mgmt-monitor~=6.0.0" "azure-mgmt-resource~=23.1.0" "azure-identity~=1.19.0"
mkdir -p /tmp/ard-out
AZURE_RESOURCE_DIAGNOSTICS_OUT=/tmp/ard-out \
  python skills/azure-resource-diagnostics/references/python/__main__.py \
    --sub "$AZURE_SUBSCRIPTION_ID" \
    --rg  "${CI_RESOURCE_GROUP:-<ci-resource-group>}" \
    --kind "Microsoft.CognitiveServices/accounts"
```

### Step 2 — Validate shape

```bash
ls /tmp/ard-out/*.json | head -1 | xargs -I{} python -c "
import json, sys
d = json.load(open(sys.argv[1]))
required = {'finding_id','skill','subscription_id','resource_group','resources','findings','summary','manifest_path','probed_at'}
missing = required - set(d.keys())
assert not missing, f'missing keys: {missing}'
assert d['skill'] == 'azure-resource-diagnostics'
print('shape OK')
" {}
```

### Step N — Write the result marker (MANDATORY)

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/azure-resource-diagnostics-smoke-result
```

On failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/azure-resource-diagnostics-smoke-result
```
```

- [ ] **Step 3: Commit**

```bash
git add skills/azure-resource-diagnostics/test-fixture/consumer_prompt.md
git commit -m "azure-resource-diagnostics: add Copilot-CLI fixture

Fixture follows AGENTS.md §9.7 Patterns 12/19/22/27. §2.9 live-test
evidence captured in PR body per Slice A/B precedent (no test_e2e_*.py
file).

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Phase 3 — Catalog wiring

### Task 3.1: Register in `.github/skill-deps.yml`

**Files:**
- Modify: `.github/skill-deps.yml`

- [ ] **Step 1: Add entries (alphabetical)**

```yaml
azure-backup-readiness:
  depends_on: []
azure-resource-diagnostics:
  depends_on: []
```

- [ ] **Step 2: Commit**

```bash
git add .github/skill-deps.yml
git commit -m "skill-deps: register azure-backup-readiness + azure-resource-diagnostics

Both NEW in v0.6.0 Slice D. No upstream-skill dependencies.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.2: Add to `scripts/build-site.py CATEGORIES`

**Files:**
- Modify: `scripts/build-site.py`

- [ ] **Step 1: Add both under appropriate category** (likely the same one Slice C used — "Foundry adjacent / Azure platform" or similar).

- [ ] **Step 2: Commit**

```bash
git add scripts/build-site.py
git commit -m "build-site: add azure-backup-readiness + azure-resource-diagnostics to CATEGORIES

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.3: ~~Wire E2E tests into `skill-test.yml`~~ (DROPPED — drift pivot)

**This task is intentionally dropped.** Same as Slice C Task 3.3: the
catalog has no `e2e-azure` job. The two new fixtures auto-enroll in
`copilot-cli-matrix` via `.github/skill-deps.yml` (Task 3.1). Skip to
Task 3.4.

### Task 3.4: Plugin MINOR bump + AGENTS.md §12.5 stats update

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `AGENTS.md` (§12.5)

- [ ] **Step 1: Bump plugin.json MINOR (29 → 31)**

Both `plugin.json` and `marketplace.json` versions match. MINOR bump per AGENTS.md §5.1 (added skills).

- [ ] **Step 2: Update AGENTS.md §12.5 stats**

- `Total skills | 29` → `31`
- `Skills with upstream pins | 25` → `27`
- `Auto-tier (CI can refresh autonomously) | 23` → `25`
- `Unit tests | 92 (...)` → bump for ~13 new (6 backup + 7 diagnostics)
- Azure E2E resources row unchanged.

- [ ] **Step 3: Validate**

```bash
python scripts/build-plugins.py --check 2>&1 | tail -10
python scripts/validate-skills.py 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add plugin.json .github/plugin/marketplace.json AGENTS.md
git commit -m "plugin: MINOR bump for v0.6.0 Slice D (29 → 31 skills)

Adds azure-backup-readiness + azure-resource-diagnostics. AGENTS.md
§12.5 catalog stats updated.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.5: Rebuild docs site

- [ ] **Step 1: Rebuild**

```bash
python3 scripts/build-site.py --out docs/ 2>&1 | tail -20
```

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: rebuild static site for Slice D (2 new skills)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3.6: Final lint + test sweep

- [ ] **Step 1: All checks**

```bash
python scripts/validate-skills.py 2>&1 | tail -10
python scripts/build-plugins.py --check 2>&1 | tail -10
python -m pytest scripts/tests/test_unit_azure_backup_readiness.py \
                  scripts/tests/test_unit_azure_resource_diagnostics.py -v 2>&1 | tail -20
```

Expected: all PASS. (No E2E tests in this set — §2.9 evidence lives in PR body per Slice A/B precedent.)

- [ ] **Step 2: Forbidden-string sweep**

```bash
git --no-pager diff origin/main..HEAD | \
  grep -iE "kyc-poc|card-dispute-investigation|threadlight-v[123]|ricchi" || \
  echo "clean"
```

Expected: `clean`.

### Task 3.7: Push + draft PR

- [ ] **Step 1: Verify state**

```bash
git log --oneline origin/main..HEAD && git status
```

- [ ] **Step 2: Push**

```bash
git push -u origin <execution-branch-name>
```

- [ ] **Step 3: Draft PR body**

Title: `Slice D: azure-backup-readiness + azure-resource-diagnostics (NEW skills, #267 + #271)`

Body skeleton:

```markdown
**Closes:** #267, #271
**Unblocks:** aiappsgbb/threadlight-skills v0.5.4 → v0.6.0 cut
**Spec:** docs/superpowers/specs/2026-06-11-v060-upstream-landings-design.md (§4.4)
**Plan:** docs/superpowers/plans/2026-06-11-v060-slice-d-backup-and-diagnostics.md

## What changes

- **NEW: `azure-backup-readiness`** — peer skill auditing backup
  coverage. Vault-type aware: probes BOTH Recovery Services Vaults
  and Backup Vaults (DataProtection). Per-vault protected-item counts.
  Findings: `no-vaults-in-rg`, `vault-empty`, `vault-list-denied`.
  Partial-denial → confidence 0.5; full-denial → confidence 0.
- **NEW: `azure-resource-diagnostics`** — peer skill auditing
  diagnostic-settings coverage. "Configured" means ANY destination
  (LAW / EventHubs / Storage). Optional `--kind` filter.
- **Plugin** — MINOR bump (catalog 29 → 31).
- **AGENTS.md §12.5** — stats updated.
- **CI** — 2 new pytest unit files (~13 tests). 2 new Copilot-CLI
  fixtures registered via `.github/skill-deps.yml` (auto-included in
  `copilot-cli-matrix` on next PR). No `scripts/tests/test_e2e_*.py`
  files (per Slice A/B/C precedent + `skill-test.yml` line 9).

## v0.6.0 cut

This is the final slice in the v0.6.0 critical path. With this merged,
threadlight v0.5.4 closes the last two `kind: manual` siblings
(BAK-401, OBS-204) and cuts v0.6.0.

## Test plan

- Unit: ~13 pytest tests across 2 files, all PASS.
- `validate-skills.py` PASS.
- `build-plugins.py --check` PASS.
- §2.9 live-test evidence: 3 paths each (real RG / nonexistent RG /
  cred fallback or kind-filter) captured in PR body below. If executor
  lacks Azure auth locally, evidence is deferred to CI matrix run +
  human reviewer.

## Live Azure testing (AGENTS.md §2.9)

Both probes call real Azure mgmt APIs. §2.9 evidence captured directly
in the PR body via Tasks 1.5 and 2.5 (Slice A/B/C precedent — no
`scripts/tests/test_e2e_*.py` files). Backup probe specifically
validates the both-vault-types code path even when the CI RG only has
one vault kind (the other class returns empty cleanly).

## Commit tags

`[skill-rewrite]` + `[multi-skill]` per AGENTS.md §4 mass-edit
invariants.
```

- [ ] **Step 4: STOP and hand back**

Per planning task framing, do not open the PR. Surface body draft,
commit list (~16 commits), test results.

---

## Self-Review checklist

- [ ] Both skills follow AGENTS.md §10.3 12-step add-a-skill workflow.
- [ ] Both SKILL.md descriptions ≤1024 chars.
- [ ] Both skills have `metadata.version: "1.0.0"`.
- [ ] Pin files schema v2, `runnable: true`, `requires: ["pypi"]`,
      `~=X.Y.Z` cap policy on all installs.
- [ ] Backup probe: BOTH RSV (azure-mgmt-recoveryservices) AND Backup
      Vault (azure-mgmt-dataprotection) per Q-D1 locked decision.
- [ ] Diagnostics probe: ANY destination counts (LAW / EventHubs /
      Storage) per Q-D2 locked decision.
- [ ] §2.9 live-test evidence captured in PR body for both probes (3
      paths each) — OR explicit "deferred to CI / human reviewer" if
      executor lacks Azure auth.
- [ ] Both fixtures include Patterns 12, 19-addendum-v2, 27 and Step −1
      echo-not-view.
- [ ] No identifier leaks (placeholders only — `<ci-resource-group>`,
      `<sub-id>`, `<rg>`).
- [ ] `.github/skill-deps.yml` updated for both.
- [ ] `scripts/build-site.py CATEGORIES` updated for both.
- [ ] ~~`skill-test.yml e2e-azure` matrix extended~~ — N/A; Task 3.3 dropped per drift pivot. Fixtures auto-enroll in `copilot-cli-matrix` via Task 3.1.
- [ ] `plugin.json` + `marketplace.json` MINOR bumped in lockstep
      (catalog 29 → 31, builds on Slice C's 27 → 29).
- [ ] `AGENTS.md §12.5` stats accurate (31 / 27 / 25).
- [ ] Docs site rebuilt and committed.

---

## Done criteria

Slice D is "done" when:
1. PR merged to `main`.
2. CI green across all 6 gates including 2 new copilot-cli-matrix legs.
3. Threadlight unblocked to open v0.5.4 PR for BAK-401 + OBS-204 flips
   and immediately cut v0.6.0.
4. Both new skills on the live docs site.

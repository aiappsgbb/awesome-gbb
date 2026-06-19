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

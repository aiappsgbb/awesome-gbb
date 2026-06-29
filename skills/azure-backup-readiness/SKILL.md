---
name: azure-backup-readiness
description: >
  Audit Azure backup coverage at resource-group scope. Checks BOTH
  Recovery Services Vaults (RSV, azure-mgmt-recoveryservices) AND
  Backup Vaults (DataProtection, azure-mgmt-dataprotection). For each
  vault found, counts protected items (azure-mgmt-recoveryservicesbackup).
  Flags no-vaults-in-rg, vault-empty (vault present but no protected
  items), and vault-list-denied (RBAC missing). Wraps the three SDKs
  with a never-raising probe() returning structured findings.
  Partial-denial (one vault class works, other doesn't) returns
  confidence in (0,1). Writes manifest JSON to out/<finding-id>.json
  and returns equivalent dict. CLI: python -m azure_backup_readiness
  --sub <sub-id> --rg <rg>. USE FOR: backup readiness audit, RSV audit,
  Backup Vault audit, vault-empty detection, no-vaults-in-RG, Foundry RG
  backup posture, spoke backup posture, BAK-401 self-verify. DO NOT USE
  FOR: creating vaults, running on-demand backups, restoring, or backup
  policy authoring; use Azure Backup CLI/Portal workflows instead.
metadata:
  version: "1.0.1"
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
    # protected_item_types=["VM", "SQLDataBase"],  # optional REL-007 filter
)
# result["vaults"]                         → list of {kind, name, id, protected_item_count}
# result["summary"]["total_vaults"]        → int
# result["summary"]["rsv_count"]           → int  (RSV count)
# result["summary"]["bv_count"]            → int  (BackupVault count)
# result["summary"]["total_protected_items"] → int  (sum across vaults, after type filter)
# result["summary"]["protected_item_types_filter"] → list[str] | None (echo of applied filter)
# result["summary"]["confidence"]          → 0.0..1.0
# result["summary"]["probe_error"]         → str | None
# result["findings"]                       → list of typed findings
# result["manifest_path"]                  → path to JSON manifest on disk
```

`protected_item_types` (the REL-007 sibling-contract input) is an
**optional** list of workload/datasource type tokens. When provided,
only protected items whose type matches one of the tokens
(case-insensitive substring) count toward
`total_protected_items` / per-vault `protected_item_count`. When
omitted (default), every protected item counts. The applied filter is
echoed back in `summary.protected_item_types_filter`.

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
# optional REL-007 type filter:
python -m azure_backup_readiness --sub <sub-id> --rg <rg> --protected-item-types VM SQLDataBase
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

---
name: azure-resource-diagnostics
description: >
  Audit Azure diagnostic-settings coverage at resource-group scope. For
  each resource in the RG (optionally filtered by target_resource_types —
  ARM types or snake_case logical kinds like storage_account), queries
  Microsoft.Insights/diagnosticSettings and reports whether ANY
  destination is configured (Log Analytics, Event Hubs, or Storage).
  Flags no-diagnostic-settings resources. Wraps azure-mgmt-monitor +
  azure-mgmt-resource with a never-raising probe() returning structured
  findings; RG-list denial returns confidence 0.0 with probe_error rather
  than raising. Writes manifest JSON to out/<finding-id>.json and returns
  the equivalent dict. CLI: python -m azure_resource_diagnostics --sub
  <sub-id> --rg <rg>. USE FOR: diagnostic settings audit, log routing
  coverage, no-diagnostic-settings detection, Foundry RG diagnostics,
  OBS-106 self-verify. DO NOT USE FOR: creating
  diagnostic settings, log-category policy authoring, querying the logs
  themselves, or metric-alert coverage (use azure-monitor-alert-baseline).
metadata:
  version: "1.0.1"
---

# azure-resource-diagnostics

Audits Azure diagnostic-settings coverage at a resource group scope.

## When to use

- threadlight v0.5.x needs to flip OBS-106 from `kind: manual` to
  `kind: sibling-skill` — this skill's `probe()` is the sibling.
- Pre-pilot review: confirm a candidate Foundry RG routes its resource
  logs somewhere (Log Analytics / Event Hubs / Storage) before a
  customer pilot.
- Spoke landing-zone check: detect resources that have no diagnostic
  settings configured at all.

## Probing an RG

```python
from azure_resource_diagnostics.probe import probe

result = probe(
    subscription_id="<sub-id>",
    resource_group="<rg>",
    # target_resource_types=["storage_account", "key_vault"],  # optional OBS-106 filter
)
# result["resources"]                          → list of {id, name, type, configured, destinations, setting_count}
# result["summary"]["total_resources"]         → int (after type filter)
# result["summary"]["configured_count"]        → int (≥1 destination set)
# result["summary"]["unconfigured_count"]      → int (no destination)
# result["summary"]["target_resource_types_filter"] → list[str] | None (echo of applied filter)
# result["summary"]["confidence"]              → 0.0..1.0
# result["summary"]["probe_error"]             → str | None
# result["findings"]                           → list of no-diagnostic-settings findings
# result["manifest_path"]                      → path to JSON manifest on disk
```

`target_resource_types` (the OBS-106 sibling-contract input) is an
**optional** list of resource-type tokens. Matching is robust: each
token is normalized (lowercased, non-alphanumerics stripped) and
matched as a substring of the normalized ARM type, so both raw ARM
types (`Microsoft.Storage/storageAccounts`) and snake_case logical
kinds (`storage_account`) select the same resources. When omitted
(default), every resource in the RG is probed. The applied filter is
echoed back in `summary.target_resource_types_filter`.

The probe **never raises**. If the RG resource listing is denied
(RBAC missing), the probe still returns a shape with `probe_error`
populated and `confidence: 0.0`. Resource types that don't support
diagnostic settings (Monitor returns 404) are treated as having no
destinations, not as a denial.

> **MUST:** Copy verbatim from
> [`references/python/probe.py`](references/python/probe.py).
> Do NOT redefine inline — the validator enforces single-source-of-truth.

## "Any destination counts" (decision)

Per spec §4.4 Q-D2 (locked decision), a resource is **configured** if
it has **any** diagnostic setting routing to **any** destination:

| Destination | Setting attribute | Meaning |
|-------------|-------------------|---------|
| Log Analytics | `workspace_id` | Logs → LAW workspace |
| Event Hubs | `event_hub_authorization_rule_id` | Logs → Event Hubs |
| Storage | `storage_account_id` | Logs → Storage account |

A diagnostic setting that exists but routes nowhere counts as
**unconfigured**. Each unconfigured resource produces a
`no-diagnostic-settings` finding.

## CLI

```bash
python -m azure_resource_diagnostics --sub <sub-id> --rg <rg>
# optional OBS-106 type filter (ARM types or logical kinds):
python -m azure_resource_diagnostics --sub <sub-id> --rg <rg> --target-resource-types storage_account key_vault
```

Outputs JSON to stdout AND writes the same content to
`out/<finding-id>.json`. Override via
`AZURE_RESOURCE_DIAGNOSTICS_OUT=<path>`.

## Auth

Uses `DefaultAzureCredential`. Caller needs at minimum `Monitoring
Reader` at the RG scope (built-in role) plus `Reader` to list
resources. Without it, the probe returns a shape with `probe_error`
populated rather than raising.

## See also

- `azure-backup-readiness` — peer skill for backup-coverage audit.
- `azure-monitor-alert-baseline` — peer skill for alert coverage audit.
- `foundry-rbac-audit` — peer skill for RBAC posture audit.

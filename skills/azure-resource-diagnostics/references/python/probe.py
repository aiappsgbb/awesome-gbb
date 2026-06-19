"""Canonical azure-resource-diagnostics probe.

Source of truth for the prose example in `../../SKILL.md § Probing an RG`.

Audits Azure diagnostic-settings coverage at a resource-group scope.
For each resource in the RG (optionally filtered by
`target_resource_types`), queries
`Microsoft.Insights/diagnosticSettings` and reports whether the
resource has ANY configured destination (LogAnalytics workspace,
EventHubs authorization rule, or Storage account) — per spec §4.4 Q-D2
locked decision: "any destination counts as configured".

Public API:
    from azure_resource_diagnostics.probe import probe

    result = probe(
        subscription_id="<sub-id>",
        resource_group="<rg>",
        target_resource_types=["Microsoft.CognitiveServices/accounts",
                               "storage_account"],   # optional OBS-106 filter
    )

`target_resource_types` (the OBS-106 sibling-contract input) is an
OPTIONAL list of resource-type tokens. Matching is robust: each token
is normalized (lowercased, non-alphanumerics stripped) and matched as a
substring of the normalized ARM type, so both raw ARM types
(`Microsoft.Storage/storageAccounts`) and snake_case logical kinds
(`storage_account`) match. Omit the filter to probe every resource in
the RG. The applied filter is echoed in
`summary.target_resource_types_filter`.

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
                "kind": "no-diagnostic-settings",
                "severity": "medium",
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
            "target_resource_types_filter": list[str] | None,
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
            "target_resource_types_filter": None,
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


def _norm(s: str) -> str:
    """Lowercase + keep only alphanumerics, so 'storage_account' and
    'Microsoft.Storage/storageAccounts' both normalize comparably."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _matches_types(resource_type: str, requested: list[str] | None) -> bool:
    """True when no filter is requested or the (normalized) requested token
    is a substring of the (normalized) ARM resource type."""
    if not requested:
        return True
    norm_type = _norm(resource_type)
    return any(_norm(req) in norm_type for req in requested if req)


def _classify_setting(setting: Any) -> list[str]:
    """Inspect a diagnostic_settings entry; return configured destinations."""
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
    target_resource_types: list[str] | None = None,
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
    result["summary"]["target_resource_types_filter"] = (
        list(target_resource_types) if target_resource_types else None
    )

    try:
        resources = list(resource_client.resources.list_by_resource_group(resource_group))
    except Exception as exc:
        result["summary"]["probe_error"] = f"list_by_resource_group failed: {exc}"
        result["summary"]["confidence"] = 0.0
        result["manifest_path"] = _write_manifest(result)
        return result

    for r in resources:
        r_type = getattr(r, "type", "") or ""
        if not _matches_types(r_type, target_resource_types):
            continue

        r_id = getattr(r, "id", "") or ""
        r_name = getattr(r, "name", "") or ""

        all_destinations: set[str] = set()
        setting_count = 0
        try:
            for setting in monitor_client.diagnostic_settings.list(r_id):
                setting_count += 1
                for d in _classify_setting(setting):
                    all_destinations.add(d)
        except Exception:
            # Some resource types don't support diagnostic settings (Monitor
            # returns 404). Treat as unsupported rather than denial — leave
            # destinations empty.
            pass

        configured = bool(all_destinations)
        result["resources"].append({
            "id": r_id,
            "name": r_name,
            "type": r_type,
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
                "resource_type": r_type,
                "remediation": "Create a diagnostic setting routing to LogAnalytics, EventHubs, or Storage.",
            })

    result["summary"]["total_resources"] = len(result["resources"])
    result["manifest_path"] = _write_manifest(result)
    return result

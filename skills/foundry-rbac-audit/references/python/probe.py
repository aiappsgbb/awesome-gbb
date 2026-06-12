"""IAM-101 probe: privilege-escalation role-assignment audit at RG scope.

Source of truth for the prose example in `../../SKILL.md § Probe Reference`.
Enumerates role assignments at a resource-group scope via
AuthorizationManagementClient, filters by principal type, and flags
Owner / User Access Administrator / RBAC Administrator assignments as
privilege-escalation observations.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient

PRIVILEGE_ESCALATION_ROLES = {
    "8e3af657-a8ff-443c-a75c-2fe8c4bcb635": ("Owner", "critical"),
    "18d7d88d-d35e-4fb5-a5c3-7773c20a72d9": ("User Access Administrator", "critical"),
    "f58310d9-a9f6-439a-9e8d-f62e7b41a168": ("Role Based Access Control Administrator", "high"),
}

# Maps SDK principal_type values → the filter tokens they match.
_PRINCIPAL_TYPE_MAP = {
    "User": {"user"},
    "ServicePrincipal": {"service_principal", "managed_identity"},
    "Group": {"group"},
}

_OUT_DIR = Path("out")
_MANIFEST_NAME = "IAM-101.json"


def _write_manifest(result: dict) -> None:
    """Write the result manifest. Swallows I/O errors to preserve probe()'s never-raise contract."""
    try:
        _OUT_DIR.mkdir(exist_ok=True)
        (_OUT_DIR / _MANIFEST_NAME).write_text(json.dumps(result, indent=2))
    except Exception:
        # never-raise contract (spec §4.3.1) — manifest absence will surface to the consumer
        pass


def probe(
    subscription_id: str,
    resource_group: str,
    target_principal_types: list[str],
    *,
    credential=None,
) -> dict:
    """Run the IAM-101 privilege-escalation check and return a spec §4.3.1 dict."""
    scope_dict = {
        "subscription_id": subscription_id,
        "resource_group": resource_group,
    }

    try:
        if credential is None:
            credential = DefaultAzureCredential()

        client = AuthorizationManagementClient(credential, subscription_id)
        scope = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"

        assignments = list(client.role_assignments.list_for_scope(scope))

        target_set = set(target_principal_types)
        filtered = [
            a for a in assignments
            if _PRINCIPAL_TYPE_MAP.get(a.principal_type, set()) & target_set
        ]

        observations = []
        for a in filtered:
            role_guid = a.role_definition_id.rsplit("/", 1)[-1]
            if role_guid not in PRIVILEGE_ESCALATION_ROLES:
                continue
            _, severity = PRIVILEGE_ESCALATION_ROLES[role_guid]
            role_def = client.role_definitions.get(scope, role_guid)
            observations.append({
                "principal_id": a.principal_id,
                "role_definition_id": a.role_definition_id,
                "role_name": role_def.role_name,
                "principal_type": a.principal_type,
                "severity": severity,
                "scope": a.scope,
            })

        if observations:
            result_val = "needs_attention"
            remediation_hints = [
                f"Review the {len(observations)} privilege-escalation assignment(s) at scope {scope};"
                " remove any that are not strictly required for daily operations.",
                "Prefer Contributor + a custom Authorization role over Owner"
                " where role-management is not needed.",
            ]
        else:
            result_val = "ok"
            remediation_hints = []

        confidence = 0.5 if len(filtered) == 0 else 1.0

        probed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        result = {
            "finding_id": "IAM-101",
            "scope": scope_dict,
            "result": result_val,
            "observations": observations,
            "remediation_hints": remediation_hints,
            "confidence": confidence,
            "probed_at": probed_at,
            "error": None,
        }

        _write_manifest(result)

        return result

    except Exception as exc:
        probed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result = {
            "finding_id": "IAM-101",
            "scope": scope_dict,
            "result": "errored",
            "observations": [],
            "remediation_hints": [],
            "confidence": 0.0,
            "probed_at": probed_at,
            "error": f"{type(exc).__name__}: {exc}",
        }

        _write_manifest(result)

        return result

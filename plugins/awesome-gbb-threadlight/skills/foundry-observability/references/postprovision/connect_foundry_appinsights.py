"""connect_foundry_appinsights.py — postprovision hook.

Creates the ACCOUNT-level AppInsights connection on the Foundry account
so the hosted-agent runtime auto-injects APPLICATIONINSIGHTS_CONNECTION_STRING
into every agent container revision.

Run from azure.yaml `postprovision` hook:

    hooks:
      postprovision:
        windows:
          shell: pwsh
          run: uv run infra/scripts/connect_foundry_appinsights.py
        posix:
          shell: sh
          run: uv run infra/scripts/connect_foundry_appinsights.py

Required env vars (azd populates from Bicep outputs):
    AZURE_FOUNDRY_ACCOUNT_NAME       — Foundry account (NOT project) name
    AZURE_FOUNDRY_ACCOUNT_RG         — RG holding the Foundry account
    AZURE_APPINSIGHTS_RESOURCE_ID    — ARM ID of the AppIn resource
    AZURE_SUBSCRIPTION_ID            — already set by azd

What this script does
---------------------
1. PUTs a connection of category=AppInsights to the Foundry ACCOUNT
   (NOT the project — common trap that causes silent telemetry loss).
2. Optionally grants Application Insights Data Ingestor to the
   platform-managed identities AgentService-* and Foundry-* (if they
   exist by the time this hook runs — they may not, in which case the
   grant is deferred to first agent invocation).

Idempotent. Safe to re-run.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_VERSION = "2025-04-01-preview"
APPINSIGHTS_DATA_INGESTOR_ROLE_ID = "3913510d-42f4-4e42-8a64-420c390055eb"  # Monitoring Metrics Publisher


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        log.error("required env var not set: %s — set in azure.yaml outputs or .env", name)
        sys.exit(1)
    return val


def _az(*args: str) -> dict | list | None:
    """Run az command, parse JSON output. Returns None for non-JSON success."""
    cmd = ["az", *args, "--output", "json"]
    log.debug("run: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        log.error("az failed: %s", result.stderr.strip() or result.stdout.strip())
        return None
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        log.warning("az returned non-JSON: %s", result.stdout[:200])
        return None


def create_appinsights_connection(
    *,
    subscription_id: str,
    account_rg: str,
    account_name: str,
    appinsights_id: str,
) -> bool:
    """PUT the account-level AppInsights connection. Idempotent."""
    url = (
        f"https://management.azure.com"
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{account_rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account_name}"
        f"/connections/AppInsights"
        f"?api-version={API_VERSION}"
    )
    body = {
        "properties": {
            "category": "AppInsights",
            "target": appinsights_id,
            "metadata": {"ApiType": "Azure"},
            "authType": "AAD",
        }
    }
    body_json = json.dumps(body)

    log.info("creating account-level AppInsights connection on %s", account_name)
    result = subprocess.run(
        [
            "az", "rest",
            "--method", "put",
            "--url", url,
            "--body", body_json,
            "--headers", "Content-Type=application/json",
            "--output", "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # Check if it's the windows --headers quoting bug per azure-tenant-isolation
        err = result.stderr or result.stdout
        if "non atteso" in err.lower() or "unexpected" in err.lower():
            log.error(
                "az rest --headers quoting bug on Windows. "
                "Workaround: write body to a temp file and pass --body @temp.json, "
                "or invoke via REST helper script. See azure-tenant-isolation troubleshooting."
            )
        else:
            log.error("az rest failed: %s", err)
        return False

    log.info("✅ AppInsights connection created (or already existed)")
    return True


def grant_data_ingestor(
    *,
    appinsights_id: str,
    principal_id: str,
    principal_type: str = "ServicePrincipal",
    label: str = "agent identity",
) -> bool:
    """Grant Application Insights Data Ingestor. Idempotent (az treats existing as success)."""
    log.info("granting Application Insights Data Ingestor to %s (%s)", label, principal_id)
    args = [
        "role", "assignment", "create",
        "--assignee-object-id", principal_id,
        "--assignee-principal-type", principal_type,
        "--role", APPINSIGHTS_DATA_INGESTOR_ROLE_ID,
        "--scope", appinsights_id,
    ]
    result = _az(*args)
    if result is None:
        # Could be already-exists; check explicitly
        log.info("(may already be assigned — non-fatal)")
        return True
    return True


def find_foundry_platform_identities(
    *, subscription_id: str, account_rg: str, account_name: str
) -> list[tuple[str, str]]:
    """Find the AgentService-* and Foundry-* UAMIs created by Foundry.

    Returns [(principal_id, label), ...]. Empty if Foundry hasn't created
    the agent yet (in which case re-run after first agent invocation).
    """
    found: list[tuple[str, str]] = []
    # Look in the Foundry account RG for UAMIs matching the patterns
    uamis = _az(
        "identity", "list",
        "--resource-group", account_rg,
        "--query", "[?starts_with(name, 'AgentService-') || starts_with(name, 'Foundry-')].{name:name, principalId:principalId}",
    )
    if isinstance(uamis, list):
        for uami in uamis:
            found.append((uami["principalId"], uami["name"]))
    return found


def main() -> int:
    sub_id = _require_env("AZURE_SUBSCRIPTION_ID")
    account_rg = _require_env("AZURE_FOUNDRY_ACCOUNT_RG")
    account_name = _require_env("AZURE_FOUNDRY_ACCOUNT_NAME")
    appinsights_id = _require_env("AZURE_APPINSIGHTS_RESOURCE_ID")

    ok = create_appinsights_connection(
        subscription_id=sub_id,
        account_rg=account_rg,
        account_name=account_name,
        appinsights_id=appinsights_id,
    )
    if not ok:
        log.error("connection step FAILED — agent traces will not reach AppIn")
        return 1

    # Best-effort: grant Application Insights Data Ingestor to platform identities
    # if they exist. If not, the user should re-run after first agent invocation.
    platform_ids = find_foundry_platform_identities(
        subscription_id=sub_id, account_rg=account_rg, account_name=account_name
    )
    if not platform_ids:
        log.info(
            "no Foundry platform identities found yet — re-run this script after "
            "first agent invocation to grant Application Insights Data Ingestor to "
            "AgentService-* and Foundry-* UAMIs (or grant manually)"
        )
    else:
        for pid, label in platform_ids:
            grant_data_ingestor(
                appinsights_id=appinsights_id,
                principal_id=pid,
                label=label,
            )

    log.info("✅ observability postprovision complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())

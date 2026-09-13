"""Canonical read-only account/private-endpoint/agent-subnet inventory.

Source of truth for `../../SKILL.md § Step 9a: Read-only network inventory`.
Management-plane observations do not certify runtime connectivity or authorize
subnet reuse. No SDK dependencies, resource writes, login or subscription switching.
"""

import argparse
import json
import os
import subprocess
import sys


def read_az(arguments):
    result = subprocess.run(
        ["az", *arguments, "--only-show-errors", "--output", "json"],
        check=True, capture_output=True, text=True, timeout=90,
    )
    return json.loads(result.stdout)


def summarize(account, endpoints, subnet):
    properties = account.get("properties") or {}
    states = [
        (endpoint.get("properties", endpoint).get("privateLinkServiceConnectionState") or {})
        .get("status", "Unknown")
        for endpoint in endpoints
    ]
    delegation_present = any(
        entry.get("serviceName") == "Microsoft.App/environments"
        for entry in subnet.get("delegations", [])
    )
    blockers = []
    if properties.get("provisioningState") != "Succeeded":
        blockers.append("ACCOUNT_NOT_SUCCEEDED")
    if properties.get("publicNetworkAccess") != "Disabled":
        blockers.append("PUBLIC_ACCESS_NOT_DISABLED")
    if not states or any(state != "Approved" for state in states):
        blockers.append("PRIVATE_ENDPOINT_NOT_APPROVED")
    if not delegation_present:
        blockers.append("AGENT_DELEGATION_MISSING")
    return {
        "account_state": properties.get("provisioningState", "Unknown"),
        "public_network_access": properties.get("publicNetworkAccess") or "Unknown",
        "private_endpoint_states": states,
        "agent_delegation_present": delegation_present,
        "service_association_link_count": len(subnet.get("serviceAssociationLinks") or []),
        "subnet_reuse": "OWNERSHIP_REVIEW_REQUIRED",
        "blockers": blockers,
        "runtime_connectivity": "NOT_TESTED",
    }


def collect(resource_group, account_name, vnet_resource_group, vnet, subnet,
            environment, reader=read_az):
    for name in ("AZURE_CONFIG_DIR", "AZD_CONFIG_DIR",
                 "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"):
        if not environment.get(name, "").strip():
            raise ValueError(f"Set {name} using azure-tenant-isolation before inspection")
    subscription = environment["AZURE_SUBSCRIPTION_ID"]
    context = reader(["account", "show", "--query", "{id:id,tenantId:tenantId}"])
    if (context.get("id") != subscription
            or context.get("tenantId") != environment["AZURE_TENANT_ID"]):
        raise ValueError("Azure context mismatch; no resource reads performed")
    account = reader([
        "cognitiveservices", "account", "show", "--name", account_name,
        "--resource-group", resource_group, "--subscription", subscription,
    ])
    endpoints = reader([
        "network", "private-endpoint-connection", "list", "--id", account["id"],
        "--subscription", subscription,
    ])
    subnet_state = reader([
        "network", "vnet", "subnet", "show", "--name", subnet, "--vnet-name", vnet,
        "--resource-group", vnet_resource_group, "--subscription", subscription,
    ])
    return summarize(account, endpoints, subnet_state)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--vnet-resource-group")
    parser.add_argument("--vnet", required=True)
    parser.add_argument("--subnet", required=True)
    args = parser.parse_args(argv)
    try:
        report = collect(
            args.resource_group, args.account, args.vnet_resource_group or args.resource_group,
            args.vnet, args.subnet, os.environ,
        )
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError,
            AttributeError) as error:
        # CLI stderr can contain resource inventory; never echo it into the report.
        print(f"Network inventory unavailable ({type(error).__name__}); no changes made.",
              file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 1 if report["blockers"] else 0


if __name__ == "__main__":
    sys.exit(main())

"""CLI entry point for the IAM-101 RBAC audit probe.

Invocation:
    python __main__.py \\
        --subscription-id <sub-id> \\
        --resource-group <rg> \\
        --target-principal-types user,service_principal

OR (when the dir is on sys.path):
    python -m __main__ \\
        --subscription-id <sub-id> ...

The probe writes `out/IAM-101.json` relative to CWD; this CLI also
prints the same dict as JSON to stdout for jq-friendly piping.
"""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def _parse_principal_types(raw: str) -> list[str]:
    """Split a comma-separated principal-types string into a list."""
    return [p.strip() for p in raw.split(",") if p.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="foundry-rbac-audit",
        description="Audit RBAC role assignments at a resource group scope (IAM-101 probe).",
    )
    parser.add_argument(
        "--subscription-id",
        required=True,
        help="Azure subscription ID",
    )
    parser.add_argument(
        "--resource-group",
        required=True,
        help="Resource group name",
    )
    parser.add_argument(
        "--target-principal-types",
        required=True,
        help="Comma-separated principal types to audit (e.g. user,service_principal,group)",
    )
    args = parser.parse_args(argv)

    target_types = _parse_principal_types(args.target_principal_types)

    try:
        result = probe(
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            target_principal_types=target_types,
        )
    except Exception as exc:
        print(
            json.dumps({"error": f"probe raised unexpectedly: {type(exc).__name__}: {exc}"}),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

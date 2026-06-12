"""CLI entry point for the SRE-104 alert-baseline probe.

Invocation:
    python __main__.py \\
        --subscription-id <sub-id> \\
        --resource-group <rg> \\
        --alert-baseline-kind foundry_pilot

OR (when the dir is on sys.path):
    python -m __main__ \\
        --subscription-id <sub-id> ...

The probe writes `out/SRE-104.json` relative to CWD; this CLI also
prints the same dict as JSON to stdout for jq-friendly piping.
"""
from __future__ import annotations

import argparse
import json
import sys

from probe import probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="azure-monitor-alert-baseline",
        description="Compare live Azure Monitor alert rules in a resource group against a baseline (SRE-104 probe).",
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
        "--alert-baseline-kind",
        required=True,
        choices=["foundry_pilot", "spoke_minimum", "production"],
        help="Baseline kind to compare against",
    )
    args = parser.parse_args(argv)

    try:
        result = probe(
            subscription_id=args.subscription_id,
            resource_group=args.resource_group,
            alert_baseline_kind=args.alert_baseline_kind,
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

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

"""Bulk-load PoC sample data into the local Cosmos emulator.

Reads JSON files under `tests/sample-data/cosmos/<container>/*.json`,
creates the database + containers (if missing), upserts each doc.

Usage (from PoC root):
    uv run python tests/seed_local_cosmos.py

Layout expected:
    tests/sample-data/cosmos/
      cases/
        dc001.json
        dc002.json
      events/
        dc001-evt-001.json
        ...

The container name = directory name. The partition-key path is read
from `references/local-stack/cosmos_pk_map.json` if present, else
defaults to `/id`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from azure.cosmos import CosmosClient, PartitionKey, exceptions


def _load_env_local() -> None:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        env = parent / ".env.local"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
            return


def main() -> int:
    _load_env_local()

    endpoint = os.environ["COSMOS_ENDPOINT"]
    key = os.environ["COSMOS_KEY"]
    db_name = os.environ["COSMOS_DATABASE"]
    verify_ssl = os.environ.get("COSMOS_VERIFY_SSL", "false").lower() != "false"

    sample_root = Path("tests/sample-data/cosmos")
    if not sample_root.is_dir():
        print(f"FATAL: {sample_root} not found", file=sys.stderr)
        return 1

    pk_map_file = Path("references/local-stack/cosmos_pk_map.json")
    pk_map: dict[str, str] = {}
    if pk_map_file.exists():
        pk_map = json.loads(pk_map_file.read_text())

    client = CosmosClient(endpoint, credential=key, connection_verify=verify_ssl)
    db = client.create_database_if_not_exists(id=db_name)
    print(f"[seed] database: {db_name}")

    for container_dir in sorted(p for p in sample_root.iterdir() if p.is_dir()):
        cname = container_dir.name
        pk_path = pk_map.get(cname, "/id")
        c = db.create_container_if_not_exists(id=cname, partition_key=PartitionKey(path=pk_path))
        print(f"[seed] container: {cname}  pk={pk_path}")
        n = 0
        for doc_file in sorted(container_dir.glob("*.json")):
            doc = json.loads(doc_file.read_text())
            try:
                c.upsert_item(doc)
                n += 1
            except exceptions.CosmosHttpResponseError as exc:
                print(f"[seed]   ERROR upserting {doc_file.name}: {exc}", file=sys.stderr)
        print(f"[seed]   {n} doc(s) upserted")

    return 0


if __name__ == "__main__":
    sys.exit(main())

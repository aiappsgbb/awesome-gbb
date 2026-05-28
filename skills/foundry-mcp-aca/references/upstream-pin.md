---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around MCP protocol packages and Azure Container Apps management SDKs — version-pinned, no git SHA tracking.

packages:
  - name: fastmcp
    source: pypi
    version: "2.14.7"
    upstream_changelog: https://pypi.org/project/fastmcp/#history
    notes: |
      SKILL.md mandates fastmcp>=2.0.0,<3.0.0 and records 2.14.7 as the known-good 2.x line before a 3.x path break.
  - name: mcp
    source: pypi
    version: "1.27.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
    notes: |
      MCP protocol package; version pulled transitively by fastmcp (fastmcp~=2.14.7 requires mcp>=1.24.0,<2.0).
  - name: azure-mgmt-appcontainers
    source: pypi
    version: "4.0.0"
    upstream_changelog: https://pypi.org/project/azure-mgmt-appcontainers/#history
    notes: |
      Azure Container Apps management SDK used for ACA resource operations; import smoke only, no live deploy.
  - name: azure-cosmos
    source: pypi
    version: "4.15.0"
    upstream_changelog: https://pypi.org/project/azure-cosmos/#history
    notes: |
      Async Cosmos MCP path requires the >=4.15 query_items signature discipline documented in SKILL.md.
  - name: azure-identity
    source: pypi
    version: "1.19.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      Keyless Azure SDK authentication floor from the reference requirements.
  - name: aiohttp
    source: pypi
    version: "3.9.0"
    upstream_changelog: https://pypi.org/project/aiohttp/#history
    notes: |
      Required async HTTP transport for azure-cosmos in the Python Cosmos MCP server.

docs_to_revalidate:
  - https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging
  - https://learn.microsoft.com/azure/container-apps/
  - https://pypi.org/project/fastmcp/
  - https://pypi.org/project/mcp/
  - https://pypi.org/project/azure-mgmt-appcontainers/
  - https://pypi.org/project/azure-cosmos/
  - https://pypi.org/project/azure-identity/
  - https://pypi.org/project/aiohttp/

known_issues:
  - id: KI-001
    description: Keep FastMCP pinned below 3.0.0 until the streamable-http mount-path change is explicitly revalidated.
    upstream_url: https://pypi.org/project/fastmcp/
    status: open
    workaround_location: SKILL.md § "Pin `fastmcp<3.0.0`"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "fastmcp~=2.14.7" \
      "azure-mgmt-appcontainers~=4.0.0" \
      "azure-cosmos~=4.15.0" \
      "azure-identity~=1.19.0" \
      "aiohttp~=3.9.0"
    python - <<'PY'
    from fastmcp import FastMCP
    import mcp
    from azure.mgmt.appcontainers import ContainerAppsAPIClient
    from azure.cosmos.aio import CosmosClient
    from azure.identity import DefaultAzureCredential
    import aiohttp
    print("ok foundry-mcp-aca imports")
    PY
  expected_output:
    - "ok foundry-mcp-aca imports"

last_validated: 2026-05-28
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-mcp-aca` skill

This Tier-B pin captures the MCP and Azure Container Apps package stack for import-only validation. It intentionally avoids live ACA deployment.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `fastmcp` | PyPI | **2.14.7** | Known-good 2.x line; keep `<3.0.0` |
| `mcp` | PyPI | **1.27.1** | Transitive via fastmcp (>=1.24.0,<2.0) |
| `azure-mgmt-appcontainers` | PyPI | **4.0.0** | ACA management SDK |
| `azure-cosmos` | PyPI | **4.15.0** | Cosmos MCP async SDK floor |
| `azure-identity` | PyPI | **1.19.0** | Keyless auth floor |
| `aiohttp` | PyPI | **3.9.0** | Async HTTP transport |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains `ok foundry-mcp-aca imports`.

## Known issues

### KI-001 — FastMCP 3.x path break

Keep the 2.x pin until the server and client path behavior has been revalidated against the Foundry MCP client.

---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around Microsoft Foundry Toolbox GA API, stable Python management SDK, Agent Framework hosted Toolbox consumer; preview Toolbox subfeatures separately labeled. Official CLI setup uses Beta microsoft.foundry 1.0.0-beta.1, which currently bundles Beta azure.ai.toolboxes 1.0.0-beta.2.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.4.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: Stable Toolbox management and stable ToolSearchToolboxTool.
  - name: agent-framework
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: Current core agent and MCP tool composition surface.
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: Exact prerelease containing FoundryToolbox; requires mcp>=1.24,<2.
  - name: mcp
    source: pypi
    version: "1.29.0"
    upstream_changelog: https://pypi.org/project/mcp/#history
    hold_below: "2.0.0"
    hold_reason: KI-002
    notes: Current MCP 1.x maintenance line; MCP 2 is blocked by the hosting package.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/install-cli-foundry-extensions
  - https://learn.microsoft.com/azure/foundry/agents/how-to/cli-project-context
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search
  - https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog
  - https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/agent-framework/
  - https://pypi.org/project/mcp/

known_issues:
  - id: KI-001
    description: |
      Preview-era Toolbox requests required `Foundry-Features: Toolboxes=V1Preview`. The GA Toolbox API removed that feature gate; stable clients must not depend on the header.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox
    status: closed_upstream_fixed
    workaround_location: removed in foundry-toolbox v2.0.0
  - id: KI-002
    description: agent-framework-foundry-hosting 1.0.0b260730 requires mcp>=1.24,<2, so MCP 2 cannot resolve with the canonical FoundryToolbox consumer.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7446
    status: open
    workaround_location: SKILL.md § "Current API matrix"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "azure-ai-projects~=2.4.0" \
      "agent-framework~=1.13.0" \
      "agent-framework-foundry-hosting==1.0.0b260730" \
      "mcp~=1.29.0"
    python - <<'PY'
    from importlib.metadata import version
    from agent_framework import MCPStreamableHTTPTool
    from agent_framework_foundry_hosting import FoundryToolbox
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        ToolSearchToolboxTool,
        ToolboxSearchPreviewToolboxTool,
    )
    from mcp import ClientSession

    class OfflineCredential:
        def get_token(self, *scopes, **kwargs):
            raise RuntimeError("network is outside the import smoke")
        def close(self):
            return None

    client = AIProjectClient(
        endpoint="https://example.services.ai.azure.com/api/projects/example",
        credential=OfflineCredential(),
    )
    assert callable(client.toolboxes.create_version)
    assert callable(client.toolboxes.get_version)
    assert callable(client.toolboxes.delete)
    assert ToolSearchToolboxTool().as_dict() == {"type": "toolbox_search"}
    assert ToolboxSearchPreviewToolboxTool().as_dict()["type"] == "toolbox_search_preview"
    assert FoundryToolbox and MCPStreamableHTTPTool and ClientSession
    assert version("azure-ai-projects").startswith("2.4.")
    assert version("agent-framework").startswith("1.13.")
    assert version("mcp").startswith("1.29.")
    client.close()
    print("ok stable toolbox search")
    print("ok foundry toolbox current stack")
    PY
  expected_output:
    - "ok stable toolbox search"
    - "ok foundry toolbox current stack"

last_validated: 2026-08-04
validated_by: ricchi
known_issues_count: 2
---

# Upstream pin — `foundry-toolbox` skill

This Tier-B pin captures the PyPI package stack and GA Toolbox API contract for the Foundry Toolbox wrapper.

The stable Python pins below are independent of the CLI distribution. For
standalone CLI workflows, install Beta `microsoft.foundry` `1.0.0-beta.1`;
its registry metadata currently bundles Beta `azure.ai.toolboxes`
`1.0.0-beta.2`, and existing-project commands require `azd ai project set`
before `azd ai toolbox create --from-file`.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.4.0** | Stable Toolbox management and stable `ToolSearchToolboxTool` |
| `agent-framework` | PyPI | **1.13.0** | Current core agent and MCP tool composition surface |
| `agent-framework-foundry-hosting` | PyPI | **1.0.0b260730** | Exact prerelease containing `FoundryToolbox`; requires `mcp>=1.24,<2` |
| `mcp` | PyPI | **1.29.0** | Current MCP 1.x maintenance line; MCP 2 is blocked by the hosting package |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains both `ok ...` lines.

## Known issues

### KI-001 - preview Toolbox feature header

Closed upstream. The GA Toolbox API no longer requires `Foundry-Features: Toolboxes=V1Preview`; v2.0.0 removes the workaround from canonical requests.

### KI-002 - MCP 2 blocked by Agent Framework hosting

`agent-framework-foundry-hosting==1.0.0b260730` requires
`mcp>=1.24,<2`. Keep MCP on the 1.29 maintenance line until
[microsoft/agent-framework#7446](https://github.com/microsoft/agent-framework/issues/7446)
is resolved by a released, live-validated hosting package.

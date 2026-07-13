---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around Microsoft Foundry Toolbox GA API, stable Python management SDK, Agent Framework hosted Toolbox consumer; preview Toolbox subfeatures separately labeled.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Stable management uses AIProjectClient.toolboxes and Toolbox-specific models.
  - name: agent-framework
    source: pypi
    version: "1.11.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      Agent, FoundryChatClient, MCPStreamableHTTPTool, local function-tool composition.
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0a260709"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: |
      Exact prerelease containing FoundryToolbox.
  - name: mcp
    source: pypi
    version: "1.28.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
    notes: |
      Streamable HTTP MCP primitives.

docs_to_revalidate:
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

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "azure-ai-projects~=2.3.0" "agent-framework~=1.11.0" "agent-framework-foundry-hosting==1.0.0a260709" "mcp~=1.28.1"
    python - <<'PY'
    from agent_framework import MCPStreamableHTTPTool, SkillsProvider
    from agent_framework_foundry_hosting import FoundryToolbox
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        CodeInterpreterToolboxTool,
        MCPToolboxTool,
        ToolboxSearchPreviewToolboxTool,
        ToolboxTool,
    )
    from mcp import ClientSession

    class OfflineCredential:
        def get_token(self, *scopes, **kwargs):
            raise RuntimeError("network access is not part of the import smoke")

        def close(self):
            return None

    client = AIProjectClient(
        endpoint="https://example.services.ai.azure.com/api/projects/example",
        credential=OfflineCredential(),
    )
    assert client.toolboxes is not None
    assert callable(client.toolboxes.create_version)
    assert callable(client.toolboxes.get_version)
    assert callable(client.toolboxes.delete)
    client.close()
    print("ok stable toolbox client")

    for model in (
        ToolboxTool,
        CodeInterpreterToolboxTool,
        MCPToolboxTool,
        ToolboxSearchPreviewToolboxTool,
    ):
        assert model is not None
    print("ok toolbox-specific models")

    assert FoundryToolbox is not None
    assert MCPStreamableHTTPTool is not None
    assert ClientSession is not None
    print("ok FoundryToolbox imports")

    try:
        from agent_framework.foundry import AzureAIToolbox
    except (ImportError, ModuleNotFoundError):
        print("ok AzureAIToolbox removed")
    else:
        raise SystemExit("AzureAIToolbox unexpectedly remains importable")

    try:
        SkillsProvider(skill_paths=".")
    except TypeError:
        print("ok skill_paths constructor removed")
    else:
        raise SystemExit("SkillsProvider(skill_paths=...) unexpectedly accepted")
    PY
  expected_output:
    - "ok stable toolbox client"
    - "ok toolbox-specific models"
    - "ok FoundryToolbox imports"
    - "ok AzureAIToolbox removed"
    - "ok skill_paths constructor removed"

last_validated: 2026-07-13
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `foundry-toolbox` skill

This Tier-B pin captures the PyPI package stack and GA Toolbox API contract for the Foundry Toolbox wrapper.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.3.0** | Stable management via `AIProjectClient.toolboxes` and Toolbox-specific models |
| `agent-framework` | PyPI | **1.11.0** | `Agent`, `FoundryChatClient`, `MCPStreamableHTTPTool`, local function-tool composition |
| `agent-framework-foundry-hosting` | PyPI | **1.0.0a260709** | Exact prerelease containing `FoundryToolbox` |
| `mcp` | PyPI | **1.28.1** | Streamable HTTP MCP primitives |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains all five `ok ...` lines.

## Known issues

### KI-001 - preview Toolbox feature header

Closed upstream. The GA Toolbox API no longer requires `Foundry-Features: Toolboxes=V1Preview`; v2.0.0 removes the workaround from canonical requests.

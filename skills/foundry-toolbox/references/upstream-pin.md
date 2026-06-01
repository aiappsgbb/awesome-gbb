---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Foundry Toolbox preview API and its Python SDK helpers — version-pinned, no git SHA tracking.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      SKILL.md verifies client.beta.toolboxes.create_version and related methods on azure-ai-projects 2.1.0.
  - name: agent-framework
    source: pypi
    version: "1.7.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      MAF surface used for MCPStreamableHTTPTool and hosted-agent toolbox consumption patterns.
      get_toolbox, select_toolbox_tools removed in 1.3.0; SkillsProvider(skill_paths=...) removed in 1.4.0.
  - name: mcp
    source: pypi
    version: "1.27.1"
    upstream_changelog: https://pypi.org/project/mcp/#history
    notes: |
      Toolbox endpoints are consumed as Streamable HTTP MCP endpoints.
      agent-framework 1.6.0 requires mcp>=1.24.0.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox
  - https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog
  - https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/agent-framework/
  - https://pypi.org/project/mcp/

known_issues:
  - id: KI-001
    description: |
      Toolbox calls require the preview opt-in header `Foundry-Features: Toolboxes=V1Preview`; remove this workaround only after upstream replaces the preview gate.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox
    status: open
    workaround_location: SKILL.md § "Step 2 — Wire into a hosted agent"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "azure-ai-projects~=2.1.0" "agent-framework~=1.7.0" "mcp~=1.27.0"
    python - <<'PY'
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import MCPTool, WebSearchTool, AzureAISearchTool
    from agent_framework import MCPStreamableHTTPTool
    from mcp import ClientSession
    print("ok foundry-toolbox imports")

    # Negative assertions — prove removed APIs stay removed
    import importlib
    ok = True
    try:
        from agent_framework.foundry import select_toolbox_tools
        print("FAIL select_toolbox_tools still importable")
        ok = False
    except (ImportError, ModuleNotFoundError):
        print("ok select_toolbox_tools removed")

    from agent_framework import SkillsProvider
    from pathlib import Path
    try:
        SkillsProvider(skill_paths=Path('.'))
        print("FAIL SkillsProvider(skill_paths=...) still accepted")
        ok = False
    except TypeError:
        print("ok skill_paths constructor removed")

    if not ok:
        raise SystemExit(1)
    PY
  expected_output:
    - "ok foundry-toolbox imports"
    - "ok select_toolbox_tools removed"
    - "ok skill_paths constructor removed"

last_validated: 2026-06-01
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `foundry-toolbox` skill

This Tier-B pin captures the PyPI package stack and preview-header dependency for the Foundry Toolbox API wrapper.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.1.0** | Toolbox beta client surface |
| `agent-framework` | PyPI | **1.7.0** | MAF MCP consumer surface |
| `mcp` | PyPI | **1.27.1** | Streamable HTTP MCP client primitives |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains `ok foundry-toolbox imports`.

## Known issues

### KI-001 — Toolboxes=V1Preview header

Every toolbox call currently requires `Foundry-Features: Toolboxes=V1Preview`. Keep this entry open until upstream removes or renames the preview opt-in header.

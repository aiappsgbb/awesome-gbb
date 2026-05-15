---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Foundry hosted-agents preview SDK stack — version-pinned, no git SHA tracking.

packages:
  - name: agent-framework-core
    source: pypi
    version: "1.3.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
  - name: agent-framework-foundry
    source: pypi
    version: "1.3.0"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0a260423"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
  - name: mcp
    source: pypi
    version: "1.10.0"
    upstream_changelog: https://pypi.org/project/mcp/#history
  - name: python-dotenv
    source: pypi
    version: "1.0.0"
    upstream_changelog: https://pypi.org/project/python-dotenv/#history

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/agent-framework/agents/skills?pivots=programming-language-python
  - https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
  - https://pypi.org/project/agent-framework-core/
  - https://pypi.org/project/agent-framework-foundry/
  - https://pypi.org/project/agent-framework-foundry-hosting/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/mcp/

known_issues:
  - id: KI-001
    description: |
      agent.yaml resources and scale blocks may be accepted by schema but dropped by the deployment path.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-hosted-agent-preview
    status: open
    workaround_location: SKILL.md § "Gotchas & Field Debugging Matrix"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "agent-framework-core~=1.3.0" "agent-framework-foundry~=1.3.0" "agent-framework-foundry-hosting==1.0.0a260423" "azure-ai-projects~=2.1.0" "azure-identity~=1.25.3" "mcp~=1.10.0" "python-dotenv~=1.0.0"
    python -c "from agent_framework.foundry import FoundryChatClient; from agent_framework_foundry_hosting import ResponsesHostServer; from azure.ai.projects import AIProjectClient; print('ok foundry-hosted-agents imports')"
  expected_output:
    - "ok foundry-hosted-agents imports"

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-hosted-agents` skill

This Tier-B pin captures the PyPI package stack for the Microsoft Foundry hosted-agent wrapper.

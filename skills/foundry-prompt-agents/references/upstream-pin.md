---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi_package
  notes: |
    Prompt agents are created via the azure-ai-projects SDK (v2 API surface).
    The PromptAgentDefinition class, tool classes (WebSearchTool, etc.), and
    the conversations/responses API are the core surface this skill documents.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Core SDK for prompt agent lifecycle: create_version, tools, conversations.
      PromptAgentDefinition is the key class. GA since 2.0.0.
  - name: azure-identity
    source: pypi
    version: "1.23.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential for authentication. Stable, low churn.

docs_to_revalidate:
  - https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/prompt-agent
  - https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/development-lifecycle
  - https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tool-catalog
  - https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/quickstart/create-agent
  - https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/quickstart/chat-with-agent
  - https://pypi.org/project/azure-ai-projects/

known_issues: []

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv-prompt-agents
    . .venv-prompt-agents/bin/activate
    pip install --quiet "azure-ai-projects~=${PINNED_VERSION:-2.1.0}" "azure-identity~=1.23.0"
    python -c "
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    print('import ok: AIProjectClient + PromptAgentDefinition')
    from azure.ai.projects.models import WebSearchTool, CodeInterpreterTool, FileSearchTool
    print('import ok: WebSearchTool + CodeInterpreterTool + FileSearchTool')
    from azure.ai.projects.models import MCPTool
    print('import ok: MCPTool')
    from azure.identity import DefaultAzureCredential
    print('import ok: DefaultAzureCredential')
    "
  expected_output:
    - "import ok: AIProjectClient + PromptAgentDefinition"
    - "import ok: WebSearchTool + CodeInterpreterTool + FileSearchTool"
    - "import ok: MCPTool"
    - "import ok: DefaultAzureCredential"

last_validated: 2026-06-11
validated_by: ricchi
---

## Audit trail

### 2026-06-11 — Initial pin (v1.0.0)

- `azure-ai-projects` 2.1.0 (GA) — PromptAgentDefinition, tool classes,
  conversations API all import cleanly
- `azure-identity` 1.23.0 — DefaultAzureCredential for auth
- Validation: pip install + import chain passes on macOS Python 3.13
- Skill authored from official MS docs + foundry-samples repo

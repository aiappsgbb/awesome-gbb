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
    version: "1.25.3"
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

known_issues:
  - id: KI-001
    title: "Project endpoint uses services.ai.azure.com (not ai.azure.com)"
    description: |
      The Foundry API endpoint format is https://<resource>.services.ai.azure.com/api/projects/<project>,
      NOT https://<resource>.ai.azure.com/... Some docs reference the shorter domain but it 404s.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 1 and § 9 troubleshooting.
  - id: KI-002
    title: "list() returns AgentDetails with .versions dict, not .version"
    description: |
      project.agents.list() yields AgentDetails objects with a .versions dict
      (keyed by "latest", "1", etc.), not a .version attribute. The
      create_version() return type (AgentVersionResponse) does have .version.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 4.
  - id: KI-003
    title: "delete_version() uses positional arg agent_version, not version="
    description: |
      The method signature is delete_version(agent_name, agent_version).
      Using keyword arg version= raises TypeError.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 4 and § 9.

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv-prompt-agents
    . .venv-prompt-agents/bin/activate
    pip install --quiet "azure-ai-projects~=${PINNED_VERSION:-2.1.0}" "azure-identity~=1.25.3"
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

last_validated: 2026-05-29
validated_by: copilot-bot
---

## Audit trail

### 2026-06-11 — T3 E2E validation + pin fixes (v1.0.1)

- **T3 E2E test passed** against `ai-account-juhp3jaizf6j2` (fruocco-1,
  rg-hosted-agent-demo) with gpt-4.1 model:
  - Created prompt agent `ci-e2e-prompt-test` via `create_version`
  - Chatted via conversations API, got exact expected response (`pong-ci-ok`)
  - Listed agents, confirmed agent appeared with correct `.versions` dict
  - Deleted agent via `delete_version("ci-e2e-prompt-test", "1")`
- **Endpoint format fix**: `services.ai.azure.com` not `ai.azure.com`
- **API surface corrections**: `.versions` dict on list, positional args on delete
- 3 known issues documented (KI-001 through KI-003)

### 2026-06-11 — Initial pin (v1.0.0)

- `azure-ai-projects` 2.1.0 (GA) — PromptAgentDefinition, tool classes,
  conversations API all import cleanly
- `azure-identity` 1.23.0 — DefaultAzureCredential for auth
- Validation: pip install + import chain passes on macOS Python 3.13
- Skill authored from official MS docs + foundry-samples repo

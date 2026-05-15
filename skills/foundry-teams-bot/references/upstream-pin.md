---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around microsoft-agents-* SDK packages, Foundry project invocation SDKs, and Teams manifest v1.21 conventions — version-pinned, no git SHA tracking.

packages:
  - name: microsoft-agents-activity
    source: pypi
    version: "0.9.0"
    upstream_changelog: https://pypi.org/project/microsoft-agents-activity/#history
    notes: |
      Microsoft Agents SDK package floor from the template requirements; 0.9.x is required for streaming_response.
  - name: microsoft-agents-authentication-msal
    source: pypi
    version: "0.9.0"
    upstream_changelog: https://pypi.org/project/microsoft-agents-authentication-msal/#history
    notes: |
      MsalConnectionManager UAMI auth package floor from the template requirements.
  - name: microsoft-agents-hosting-aiohttp
    source: pypi
    version: "0.9.0"
    upstream_changelog: https://pypi.org/project/microsoft-agents-hosting-aiohttp/#history
    notes: |
      aiohttp host integration package floor from the template requirements.
  - name: microsoft-agents-hosting-core
    source: pypi
    version: "0.9.0"
    upstream_changelog: https://pypi.org/project/microsoft-agents-hosting-core/#history
    notes: |
      Provides context.streaming_response used by the recommended Teams streaming template.
  - name: microsoft-agents-hosting-teams
    source: pypi
    version: "0.9.0"
    upstream_changelog: https://pypi.org/project/microsoft-agents-hosting-teams/#history
    notes: |
      Teams-specific hosting helpers from the template requirements.
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Foundry project SDK floor used by the bot-to-agent invocation patterns.
  - name: azure-identity
    source: pypi
    version: "1.19.0"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      Keyless identity floor from the template requirements.
  - name: aiohttp
    source: pypi
    version: "3.9.0"
    upstream_changelog: https://pypi.org/project/aiohttp/#history
    notes: |
      Bot web server dependency.
  - name: python-dotenv
    source: pypi
    version: "1.0.0"
    upstream_changelog: https://pypi.org/project/python-dotenv/#history
    notes: |
      Local configuration helper from the template requirements.

docs_to_revalidate:
  - https://learn.microsoft.com/microsoftteams/platform/bots/how-to/conversations/prompt-suggestions
  - https://learn.microsoft.com/microsoftteams/platform/resources/schema/manifest-schema
  - https://learn.microsoft.com/azure/bot-service/bot-service-resource-create-registration
  - https://pypi.org/project/microsoft-agents-hosting-core/
  - https://pypi.org/project/microsoft-agents-hosting-aiohttp/
  - https://pypi.org/project/microsoft-agents-hosting-teams/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/aiohttp/

known_issues:
  - id: KI-001
    description: Teams custom-engine-agent manifests must stay on manifestVersion 1.21 with prompt starters in bots[0].commandLists[0].commands, not customEngineAgents.conversationStarters.
    upstream_url: https://learn.microsoft.com/microsoftteams/platform/resources/schema/manifest-schema
    status: open
    workaround_location: |
      SKILL.md § "Step 4: Generate Teams Manifest"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "microsoft-agents-activity==0.9.0" \
      "microsoft-agents-authentication-msal==0.9.0" \
      "microsoft-agents-hosting-aiohttp==0.9.0" \
      "microsoft-agents-hosting-core==0.9.0" \
      "microsoft-agents-hosting-teams==0.9.0" \
      "azure-ai-projects==2.1.0" \
      "azure-identity==1.19.0" \
      "aiohttp==3.9.0" \
      "python-dotenv==1.0.0"
    python - <<'PY'
    import json
    import aiohttp
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    from microsoft_agents.hosting.core.app.streaming.streaming_response import StreamingResponse
    manifest = {
        "manifestVersion": "1.21",
        "bots": [{"scopes": ["personal", "copilot"], "commandLists": [{"scopes": ["personal", "copilot"], "commands": [{"title": "reset", "description": "Reset conversation"}]}]}],
        "copilotAgents": {"customEngineAgents": [{"id": "bot", "type": "bot"}]},
    }
    assert manifest["manifestVersion"] == "1.21"
    assert "copilot" in manifest["bots"][0]["scopes"]
    json.dumps(manifest)
    print("ok foundry-teams-bot imports and manifest parse")
    PY
  expected_output:
    - "ok foundry-teams-bot imports and manifest parse"

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-teams-bot` skill

This Tier-B pin captures the microsoft-agents SDK stack and Teams manifest v1.21 shape used by the bot templates.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `microsoft-agents-activity` | PyPI | **0.9.0** | Agents SDK floor |
| `microsoft-agents-authentication-msal` | PyPI | **0.9.0** | UAMI auth helper |
| `microsoft-agents-hosting-aiohttp` | PyPI | **0.9.0** | aiohttp host integration |
| `microsoft-agents-hosting-core` | PyPI | **0.9.0** | StreamingResponse support |
| `microsoft-agents-hosting-teams` | PyPI | **0.9.0** | Teams host integration |
| `azure-ai-projects` | PyPI | **2.1.0** | Foundry project SDK |
| `azure-identity` | PyPI | **1.19.0** | Keyless identity floor |
| `aiohttp` | PyPI | **3.9.0** | Web server |
| `python-dotenv` | PyPI | **1.0.0** | Local config helper |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains `ok foundry-teams-bot imports and manifest parse`.

## Known issues

### KI-001 — Teams manifest v1.21 shape

Keep the manifest schema workaround open until the Teams schema accepts a different custom-engine-agent prompt-starter shape.

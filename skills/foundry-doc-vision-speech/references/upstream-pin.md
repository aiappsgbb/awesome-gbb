---
schema_version: 2
freshness_tier: B
automation_tier: issue_only

upstream:
  type: pypi
  notes: |
    Wrapper around gpt-5.4 vision patterns, Document Intelligence v4, and Azure Speech SDKs — version-pinned, no git SHA tracking.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.1.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Toolbox preview floor is recorded as >=2.1.0; direct Foundry client patterns require >=2.0.0.
  - name: agent-framework
    source: pypi
    version: "1.3.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      MAF package family used by the FoundryChatClient vision path.
  - name: agent-framework-foundry
    source: pypi
    version: "1.3.0"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry/#history
    notes: |
      FoundryChatClient import surface for standalone vision agents.
  - name: azure-ai-documentintelligence
    source: pypi
    version: "1.0.2"
    upstream_changelog: https://pypi.org/project/azure-ai-documentintelligence/#history
    notes: |
      SDK floor recorded for the Document Intelligence v4 GA REST surface `2024-11-30`.
  - name: azure-cognitiveservices-speech
    source: pypi
    version: "1.40.0"
    upstream_changelog: https://pypi.org/project/azure-cognitiveservices-speech/#history
    notes: |
      SDK floor recorded for SpeechConfig token_credential support.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-ai-speech
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/agent-framework/
  - https://pypi.org/project/azure-ai-documentintelligence/
  - https://pypi.org/project/azure-cognitiveservices-speech/

known_issues:
  - id: KI-001
    description: Azure Speech MCP is not the default for network-secured Foundry projects; direct SDK validation requires live Azure resources.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-ai-speech
    status: open
    workaround_location: SKILL.md § "Pattern 0 — Foundry Toolbox"

validation:
  requires: [azure_subscription, foundry_project, pypi]
  runnable: false
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    echo "manual validation required: Azure subscription + Foundry project + AI services resources"
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "azure-ai-projects==2.1.0" \
      "agent-framework==1.3.0" \
      "agent-framework-foundry==1.3.0" \
      "azure-ai-documentintelligence==1.0.2" \
      "azure-cognitiveservices-speech==1.40.0"
    python - <<'PY'
    from azure.ai.projects.aio import AIProjectClient
    from agent_framework.foundry import FoundryChatClient
    from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
    import azure.cognitiveservices.speech as speechsdk
    print("ok foundry-doc-vision-speech imports")
    PY
  expected_output:
    - "manual validation required"
    - "ok foundry-doc-vision-speech imports"

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-doc-vision-speech` skill

This Tier-B pin captures package floors for the vision, Document Intelligence, and Speech SDK paths. Automation is `issue_only` because validation needs live Azure services and a Foundry project.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.1.0** | Foundry project SDK / Toolbox preview floor |
| `agent-framework` | PyPI | **1.3.0** | MAF runtime surface |
| `agent-framework-foundry` | PyPI | **1.3.0** | FoundryChatClient integration |
| `azure-ai-documentintelligence` | PyPI | **1.0.2** | Document Intelligence v4 SDK floor |
| `azure-cognitiveservices-speech` | PyPI | **1.40.0** | Speech token_credential floor |

## Verification checklist

Run the import smoke in `validation.script`, then exercise live DocIntel, Speech, and vision calls in a Foundry project.

## Known issues

### KI-001 — Speech MCP and live-service validation

Keep automation `issue_only` until the smoke can validate Speech, DocIntel, and vision paths without live project credentials.

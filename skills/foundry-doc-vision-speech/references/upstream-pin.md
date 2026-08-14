---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around gpt-5.4 vision patterns, Document Intelligence v4, and Azure Speech SDKs — version-pinned, no git SHA tracking.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Toolbox preview floor is recorded as >=2.1.0; direct Foundry client patterns require >=2.0.0.
      HELD AT 2.3.0 — do NOT bump to 2.4.0. `agent-framework-foundry` 1.10.4 declares
      `azure-ai-projects<2.4.0,>=2.2.0`, so 2.4.0 is excluded by that upper bound and pip
      resolution fails with ResolutionImpossible. The `~=2.3.0` cap already expresses this
      ceiling exactly (>=2.3.0, <2.4.0). Freshness detection only reads "latest on PyPI" and
      will keep proposing 2.4.0; re-check `agent-framework-foundry`'s bound before accepting.
  - name: agent-framework
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      MAF package family used by the FoundryChatClient vision path.
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
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
    version: "1.51.1"
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
      "azure-ai-projects~=2.3.0" \
      "agent-framework~=1.13.0" \
      "agent-framework-foundry~=1.10.4" \
      "azure-ai-documentintelligence~=1.0.2" \
      "azure-cognitiveservices-speech~=1.51.1"
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

last_validated: 2026-08-13
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-doc-vision-speech` skill

This Tier-B pin captures package floors for the vision, Document Intelligence, and Speech SDK paths. Automation is `auto`, but `validation.runnable` is `false` because the smoke needs live Azure services and a Foundry project — so this pin executes only under `run-pin-validation.py --include-azure` in the Azure-credentialed CI mode, never in the standard PyPI-only run.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.3.0** | Foundry project SDK / Toolbox preview floor. Held below 2.4.0 by `agent-framework-foundry`'s `<2.4.0` bound |
| `agent-framework` | PyPI | **1.13.0** | MAF runtime surface |
| `agent-framework-foundry` | PyPI | **1.10.4** | FoundryChatClient integration |
| `azure-ai-documentintelligence` | PyPI | **1.0.2** | Document Intelligence v4 SDK floor |
| `azure-cognitiveservices-speech` | PyPI | **1.51.1** | Speech token_credential floor |

## Verification checklist

Run the import smoke in `validation.script`, then exercise live DocIntel, Speech, and vision calls in a Foundry project.

## Known issues

### KI-001 — Speech MCP and live-service validation

Keep `validation.runnable` at `false` until the smoke can validate Speech, DocIntel, and vision paths without live project credentials. Until then the pin stays `automation_tier: auto` with Azure-credentialed execution only (`run-pin-validation.py --include-azure`).

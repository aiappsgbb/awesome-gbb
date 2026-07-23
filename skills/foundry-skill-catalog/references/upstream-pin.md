---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around the Microsoft Foundry Skills preview REST API and MAF SkillsProvider integration — version-pinned, no git SHA tracking.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      SKILL.md verifies client.beta.skills with allow_preview=True on azure-ai-projects 2.1.0.
  - name: agent-framework
    source: pypi
    version: "1.12.1"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: |
      Provides SkillsProvider, SkillsSource, and InlineSkill for runtime catalog consumption.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      Version recorded by the live verification notes in SKILL.md.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills
  - https://learn.microsoft.com/agent-framework/agents/skills?pivots=programming-language-python
  - https://agentskills.io/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/agent-framework/
  - https://pypi.org/project/azure-identity/

known_issues:
  - id: KI-001
    description: |
      Foundry Skills REST calls require the preview opt-in header `Foundry-Features: Skills=V1Preview` unless the SDK injects it via allow_preview=True.
    upstream_url: https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills
    status: open
    workaround_location: |
      SKILL.md § "The mandatory `Foundry-Features: Skills=V1Preview` header"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "azure-ai-projects~=2.3.0" "agent-framework~=1.12.1" "azure-identity~=1.25.3"
    python - <<'PY'
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    from agent_framework import InlineSkill, SkillsProvider, SkillsSource
    print("ok foundry-skill-catalog imports")
    PY
  expected_output:
    - "ok foundry-skill-catalog imports"

last_validated: 2026-07-23
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `foundry-skill-catalog` skill

This Tier-B pin captures the PyPI package stack and preview-header dependency for the Foundry Skills API wrapper.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.1.0** | Foundry Skills beta client |
| `agent-framework` | PyPI | **1.3.0** | SkillsProvider runtime |
| `azure-identity` | PyPI | **1.26.0b2** | Live verification note |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains `ok foundry-skill-catalog imports`.

## Known issues

### KI-001 — Skills=V1Preview header

Every REST call to `{project}/skills*` currently requires `Foundry-Features: Skills=V1Preview`, or SDK construction with `allow_preview=True` so the header is injected.

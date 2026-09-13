---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Native versioned Microsoft Foundry Skills preview API and the compatible
    FoundrySkillsSource consumer. SDK 2.6.0 uses download/download_version
    (not the download_content spelling in some Learn samples).

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.6.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      Native create/create_from_files, get_version, download_version, and
      update(default_version=...) with allow_preview=True.
  - name: agent-framework-core
    source: pypi
    version: "1.17.0"
    upstream_changelog: https://pypi.org/project/agent-framework-core/#history
    notes: |
      Provides SkillsProvider, SkillsSource, SkillFrontmatter, and InlineSkill.
      Required only for Pattern B; the build-only package reader/bundler uses
      no MAF imports. The adapter retains the legacy InlineSkill constructor.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      AzureCliCredential used for isolated manual live validation.
  - name: httpx
    source: pypi
    version: "0.28.1"
    upstream_changelog: https://pypi.org/project/httpx/#history
    notes: |
      Explicit SDK transport dependency.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills
  - https://learn.microsoft.com/agent-framework/agents/skills?pivots=programming-language-python
  - https://agentskills.io/
  - https://pypi.org/project/azure-ai-projects/
  - https://pypi.org/project/agent-framework-core/
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
    pip install --quiet "azure-ai-projects~=2.6.0" "agent-framework-core~=1.17.0" "azure-identity~=1.25.3" "httpx~=0.28.1"
    python - <<'PY'
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects.models import SkillInlineContent, CreateSkillVersionFromFilesBody
    from agent_framework import InlineSkill, SkillFrontmatter, SkillsProvider, SkillsSource
    print("ok foundry-skill-catalog imports")
    with DefaultAzureCredential() as credential:
        with AIProjectClient(
            endpoint="https://example.services.ai.azure.com/api/projects/example",
            credential=credential,
            allow_preview=True,
        ) as project:
            for name in ("create", "create_from_files", "get_version", "list_versions",
                         "download", "download_version", "update", "delete_version"):
                assert callable(getattr(project.beta.skills, name))
    print("ok native Skills version methods")
    PY
  expected_output:
    - "ok foundry-skill-catalog imports"
    - "ok native Skills version methods"

last_validated: 2026-09-13
validated_by: copilot-bot
known_issues_count: 1
---

# Upstream pin — `foundry-skill-catalog` skill

This Tier-B pin captures the native Skills API stack and preview-header
dependency. Its automated script is an offline import/method smoke, not an
Azure E2E or model-behavior test.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.6.0** | Native Skills version CRUD and downloads |
| `agent-framework-core` | PyPI | **1.17.0** | SkillsProvider / SkillFrontmatter runtime |
| `azure-identity` | PyPI | **1.25.3** | Isolated CLI credential |
| `httpx` | PyPI | **0.28.1** | Explicit transport dependency |

## Verification checklist

Run `validation.script`; both `expected_output` strings must appear.

Manual live validation on **2026-09-13** used a disposable UUID-named skill in
an explicitly tenant/subscription-isolated standing project. It created inline
versions 1 and 2, kept version 2 unpromoted, enumerated versions, promoted and
rolled back `default_version`, and loaded actual content through the canonical
`references/foundry_skills_source.py` module. A pinned version-1 consumer stayed
stable through both default changes, and current `SkillsProvider` constructed
successfully. Parent deletion returned `deleted=true`; readback returned 404.
No existing skills, infra, networking or RBAC were changed.

An additional disposable skill appended an unpromoted ZIP-backed version.
The canonical adapter loaded its body; `references/sync_skills.py` bundled
the pinned package and its asset. Rebundling the inline version removed the
obsolete asset. Deleting the nondefault version and then the parent both
returned `deleted=true` with 404 readback; generated local files were removed.

Post-review live revalidation exercised the canonical `sync_skills.py` CLI
with MAF imports disabled: inline and ZIP bundles passed using the shared
standard-library `skill_packages.py`. Explicit selections, including `{}`,
rejected stale output with unchanged files. The canonical adapter again loaded
promoted/rolled-back defaults while its version pin stayed stable. The new
disposable parent returned `deleted=true` and 404 on readback; all generated
local files were removed.

This evidence is API/adapter execution, not inference quality, private-network
support or Toolbox MCP discovery. SDK 2.1-era legacy package/placeholder
compatibility is unit-tested; the legacy service was not re-exercised.

## Known issues

### KI-001 — Skills=V1Preview header

Every REST call to `{project}/skills*` currently requires `Foundry-Features: Skills=V1Preview`, or SDK construction with `allow_preview=True` so the header is injected.

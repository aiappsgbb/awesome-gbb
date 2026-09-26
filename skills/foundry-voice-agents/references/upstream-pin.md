---
schema_version: 2
freshness_tier: B
automation_tier: issue_only
upstream:
  type: pypi_package
  notes: >
    UNRELEASED candidate. Stable SDK package, public-preview Voice Agent service.
    This pin validates local contracts only. Manual live functional and trace
    evidence, the metadata-only failure and retention exception are scoped
    separately in the candidate validation record.
packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.7.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/azure-ai-projects_2.7.0/sdk/ai/azure-ai-projects/CHANGELOG.md
    notes: Voice extra required. Dedicated environment; existing runtimes stay pinned.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/1.25.3/
docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/quickstarts/prompt-voice-agent
  - https://learn.microsoft.com/azure/foundry/agents/how-to/configure-voice-agent
  - https://learn.microsoft.com/azure/foundry/agents/concepts/voice-agent-observability
  - https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference
known_issues: []
validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    SKILL="skills/foundry-voice-agents"
    ENV="$(mktemp -d)"
    trap 'rm -rf -- "$ENV"' EXIT
    python3 -m venv "$ENV"
    "$ENV/bin/python" -m pip install --quiet -r "$SKILL/requirements-dev.txt" -c "$SKILL/constraints.txt"
    "$ENV/bin/python" -m unittest discover -s "$SKILL/tests" -v
    "$ENV/bin/python" -m pip check
    echo "voice offline contracts passed; live evidence is scope-specific"
  expected_output:
    - "voice offline contracts passed; live evidence is scope-specific"
last_validated: 2026-09-26
validated_by: copilot-bot
---

# Candidate dependency evidence

`last_validated` refers **only to offline contracts**, not a live test or release.
Projects 2.7.0 was released on 2026-09-18. Its published metadata requires Python
3.10+, OpenAI >=3 and optional websockets/aiohttp for voice. This client uses
Python 3.12 in the supported candidate cohort. Exact resolved package versions are in
`../constraints.txt`; the public PyPI artifacts were installed only into a private
candidate environment. The requirements file retains the `voice` extra when
installing under those constraints.

The local script is deliberately non-Azure. Do not reinterpret it as T3 or change
the release gates. A refresh must update requirements/constraints and rerun the
offline suite; Azure acceptance still needs the designed consumer fixture after
registration and explicit authorization. The initial offline run used macOS Python 3.14.5; the subsequent local/live
candidate uses Python 3.12.13. Linux coverage must come from targeted CI.

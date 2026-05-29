---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: microsoft/azure-skills
  ref: main
  pinned_sha: d02fd24f151f5133650eaa78e7da3cac2cedd72f
  license: MIT
  notes: |
    azd-patterns is mostly internal IP (tier C), but v1.1.3 borrowed three
    operational patterns from microsoft/azure-skills (azure-deploy + azure-prepare).
    This pin tracks the upstream source so weekly freshness detects if MS
    improves or changes those patterns.

    Borrowed items (all from microsoft/azure-skills at the pinned SHA):
    1. AcrPull polled retry loops (azure-deploy) — bash + PowerShell
    2. allowUserIdentityPrincipal:false CI/CD RBAC fix (azure-deploy)
    3. docker.context + language: field traps (azure-prepare)

# Also tracks microsoft/skills for the entra-agent-id cross-reference
# added to foundry-hosted-agents v1.7.0. Pin here because azd-patterns
# is the "ops knowledge base" skill and the cross-ref enriches the same
# RBAC / identity surface area.
secondary_upstream:
  type: github_repo
  repo: microsoft/skills
  ref: main
  pinned_sha: 325091fc44bafebc11330a442af58039248c9f29
  license: MIT
  notes: |
    entra-agent-id skill — fmi_path token exchange, OBO flows, cross-tenant
    agent identity. Referenced from foundry-hosted-agents § Identity & RBAC.
    ⚠️ As of this pin, entra-agent-id Step 2 uses cognitiveservices.azure.com
    scope — Foundry targets require ai.azure.com instead (documented in the
    cross-ref callout).

docs_to_revalidate:
  - https://github.com/microsoft/azure-skills/tree/main/skills/azure-deploy
  - https://github.com/microsoft/azure-skills/tree/main/skills/azure-prepare
  - https://github.com/microsoft/skills/tree/main/skills/entra-agent-id

known_issues:
  - id: KI-001
    description: "entra-agent-id Step 2 uses cognitiveservices.azure.com scope — fails for Foundry targets (need ai.azure.com)"
    upstream_url: https://github.com/microsoft/skills/issues
    status: open
    workaround_location: "foundry-hosted-agents SKILL.md § Identity & RBAC callout"

validation:
  requires:
    - github_only
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail

    # Check azure-skills repo still has the skills we borrowed from
    for skill in azure-deploy azure-prepare; do
      STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
        "https://github.com/microsoft/azure-skills/tree/main/skills/$skill")
      echo "azure-skills/$skill: HTTP $STATUS"
      [ "$STATUS" = "200" ] || { echo "FAIL: $skill not found"; exit 1; }
    done

    # Check entra-agent-id still exists in microsoft/skills
    STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
      "https://github.com/microsoft/skills/tree/main/skills/entra-agent-id")
    echo "skills/entra-agent-id: HTTP $STATUS"
    [ "$STATUS" = "200" ] || { echo "FAIL: entra-agent-id not found"; exit 1; }

    # Check for SHA drift
    CURRENT=$(git ls-remote https://github.com/microsoft/azure-skills main | cut -c1-40)
    echo "azure-skills HEAD: $CURRENT"
    echo "azure-skills pinned: ${PINNED_SHA:-d02fd24f151f5133650eaa78e7da3cac2cedd72f}"

    echo "VALIDATION_PASSED"

  expected_output:
    - "azure-skills/azure-deploy: HTTP 200"
    - "azure-skills/azure-prepare: HTTP 200"
    - "skills/entra-agent-id: HTTP 200"
    - "VALIDATION_PASSED"

last_validated: 2026-05-25
validated_by: ricchi
---

## Audit trail

### 2026-05-25 — initial pin (ricchi)

- Pinned `microsoft/azure-skills` at `d02fd24` (HEAD as of audit date)
- Pinned `microsoft/skills` at `3250916` (HEAD as of audit date)
- Borrowed 3 patterns from azure-deploy + azure-prepare into azd-patterns v1.1.3
- Added entra-agent-id cross-ref to foundry-hosted-agents v1.7.0
- Known issue: entra-agent-id scope mismatch documented in cross-ref callout

---
schema_version: 2
freshness_tier: A
automation_tier: auto

upstream:
  type: github_repo
  repo: microsoft/azure-skills
  ref: main
  pinned_sha: 3edfc3e7636d20c43fe7b24e9e6ca2c9e41c4ac7
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

# NOTE: entra-agent-id lives at microsoft/azure-skills/skills/entra-agent-id
# (the primary upstream pinned above) — NOT at microsoft/skills. A prior
# `secondary_upstream:` block here pinned the wrong repo (microsoft/skills,
# which exists but does not contain entra-agent-id; returns HTTP 404 for the
# path). Removed 2026-05-30 as part of Task 2.3 audit (see audit-trail Bug A).
# The primary upstream already covers entra-agent-id; no secondary pin needed.

docs_to_revalidate:
  - https://github.com/microsoft/azure-skills/tree/main/skills/azure-deploy
  - https://github.com/microsoft/azure-skills/tree/main/skills/azure-prepare
  - https://github.com/microsoft/azure-skills/tree/main/skills/entra-agent-id

known_issues:
  - id: KI-001
    description: "entra-agent-id Step 2 uses cognitiveservices.azure.com scope — fails for Foundry targets (need ai.azure.com)"
    upstream_url: https://github.com/microsoft/azure-skills/issues
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

    # Check entra-agent-id still exists in microsoft/azure-skills
    STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
      "https://github.com/microsoft/azure-skills/tree/main/skills/entra-agent-id")
    echo "azure-skills/entra-agent-id: HTTP $STATUS"
    [ "$STATUS" = "200" ] || { echo "FAIL: entra-agent-id not found"; exit 1; }

    # Check for SHA drift
    CURRENT=$(git ls-remote https://github.com/microsoft/azure-skills main | cut -c1-40)
    echo "azure-skills HEAD: $CURRENT"
    echo "azure-skills pinned: ${PINNED_SHA:-3edfc3e7636d20c43fe7b24e9e6ca2c9e41c4ac7}"

    echo "VALIDATION_PASSED"

  expected_output:
    - "azure-skills/azure-deploy: HTTP 200"
    - "azure-skills/azure-prepare: HTTP 200"
    - "azure-skills/entra-agent-id: HTTP 200"
    - "VALIDATION_PASSED"

last_validated: 2026-06-18
validated_by: copilot-bot
---

## Audit trail

### 2026-05-25 — initial pin (ricchi)

- Pinned `microsoft/azure-skills` at `d02fd24` (HEAD as of audit date)
- Pinned `microsoft/skills` at `3250916` (HEAD as of audit date) — ⚠️ this
  secondary pin was MIS-TARGETED; entra-agent-id lives at
  `microsoft/azure-skills`, not `microsoft/skills`. Removed in the
  2026-05-30 re-pin below.
- Borrowed 3 patterns from azure-deploy + azure-prepare into azd-patterns v1.1.3
- Added entra-agent-id cross-ref to foundry-hosted-agents v1.7.0
- Known issue: entra-agent-id scope mismatch documented in cross-ref callout

### 2026-06-18 — freshness-cycle re-pin (copilot-bot)

- Bumped `upstream.pinned_sha` from `7cb89c221ecc9eccb71580aaff3695408cdeef2b`
  to `3edfc3e7636d20c43fe7b24e9e6ca2c9e41c4ac7` (HEAD of `microsoft/azure-skills@main`
  as of 2026-06-18).
- Validation script passed: `azure-deploy` HTTP 200, `azure-prepare` HTTP 200,
  `entra-agent-id` HTTP 200, `VALIDATION_PASSED`.
- No upstream content changes affecting borrowed patterns (AcrPull retry loops,
  allowUserIdentityPrincipal RBAC fix, docker.context traps); drift is commits-only.
- `last_validated` updated to 2026-06-18.

### 2026-05-30 — Task 2.3 audit re-pin (copilot-bot)

Bug fixes applied per `docs/audit/azd-patterns-audit-trail.md` Class 15:

- **Bug A:** Removed the spurious `secondary_upstream:` block that
  pinned `microsoft/skills@325091fc...`. entra-agent-id is at
  `microsoft/azure-skills/.../entra-agent-id` (covered by the primary
  upstream above). `microsoft/skills` is a different Microsoft repo
  with unrelated content — returns HTTP 404 for the entra-agent-id
  path. Also updated `known_issues[0].upstream_url` to point at the
  correct issues tracker (`microsoft/azure-skills/issues`).
- **Bug B:** Updated `validation.script` `PINNED_SHA` fallback from
  the stale `d02fd24f...` to the current pin
  `7cb89c221ecc9eccb71580aaff3695408cdeef2b`. The pin at L10 was
  bumped from `d02fd24` → `7cb89c2` at some point after the
  2026-05-25 initial pin with no audit-trail entry; this commit
  closes that gap.
- **Bug C:** Added this audit entry documenting the re-pin and
  fix-set, per AGENTS.md § 9.4 step 4 requirement that every re-pin
  bumps the audit prose.
- **Bug D:** Bumped `last_validated:` to 2026-05-30.

Current pin SHA: `7cb89c221ecc9eccb71580aaff3695408cdeef2b` (verified
against `git ls-remote microsoft/azure-skills main`; live HEAD has
since advanced to `d3440b8...`, ~5mo drift — within freshness-lifecycle
tolerance per AGENTS.md § 9.1, will be handled by a separate freshness
PR).

No skill-body changes from upstream content in this re-pin (validation
script is unchanged in behavior; only the fallback string and metadata
were corrected).

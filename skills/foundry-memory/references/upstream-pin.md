---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: microsoft/skills
  ref: main
  pinned_sha: 325091fc44bafebc11330a442af58039248c9f29
  pinned_commit_message: |
    Merge pull request #317 from LarryOsterman/larryo/updated_rust_skills
  license: MIT
  notes: |
    The capability is real and documented in Microsoft Learn, but the upstream
    microsoft/skills repo does not ship a usable source skill under
    /skills/foundry-memory. At this pin the repo exposes only a symlink stub at
    .github/plugins/microsoft-foundry/skills/foundry-memory whose raw content is
    ../../azure-skills/skills/foundry-memory. The public tree path
    /skills/foundry-memory currently returns 404, so this awesome-gbb skill is
    an authored replacement rather than a straight wrapper.

packages: []

docs_to_revalidate:
  - https://github.com/microsoft/skills
  - https://github.com/microsoft/skills/tree/main/.github/plugins/microsoft-foundry/skills/foundry-memory
  - https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-memory
  - https://learn.microsoft.com/azure/foundry/agents/how-to/memory-usage
  - https://learn.microsoft.com/azure/foundry/how-to/develop/langchain-memory

known_issues: []

validation:
  requires:
    - github_only
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — full validation needs a live Azure subscription and Foundry project.
    set -euo pipefail

    GOT_SHA=$(git ls-remote https://github.com/microsoft/skills main | awk '{print $1}')
    echo "microsoft/skills main HEAD: $GOT_SHA"

    STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
      "https://github.com/microsoft/skills/tree/main/skills/foundry-memory")
    echo "skills/foundry-memory: HTTP $STATUS"

    SYMLINK_STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
      "https://github.com/microsoft/skills/tree/main/.github/plugins/microsoft-foundry/skills/foundry-memory")
    echo "symlink stub: HTTP $SYMLINK_STATUS"
  expected_output:
    - "microsoft/skills main HEAD:"
    - "skills/foundry-memory: HTTP"
    - "symlink stub: HTTP 200"
  failure_signatures: []

last_validated: 2026-05-25
validated_by: copilot-cli
known_issues_count: 0
---

# Upstream pin — `foundry-memory` skill

This file records the upstream state that the `foundry-memory` skill was
written against. The capability is real in Azure AI Foundry, but the upstream
`microsoft/skills` catalog currently exposes only a symlink stub instead of a
consumable `SKILL.md` under `skills/foundry-memory`.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `microsoft/skills` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `325091fc44bafebc11330a442af58039248c9f29` |
| **Pinned commit subject** | `Merge pull request #317 from LarryOsterman/larryo/updated_rust_skills` |
| **License** | `MIT` |
| **First authored against** | `2026-05-25` |
| **Last re-validated** | `2026-05-25` |

Refresh procedure:

```bash
git ls-remote https://github.com/microsoft/skills main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Why this pin is unusual

At this pin:

- `https://github.com/microsoft/skills/tree/main/skills/foundry-memory` → **404**
- `https://github.com/microsoft/skills/tree/main/.github/plugins/microsoft-foundry/skills/foundry-memory` → **200**
- raw symlink content → `../../azure-skills/skills/foundry-memory`

So the official capability exists, but the public `microsoft/skills` repo does
not provide a usable source skill in the normal `skills/<name>/` location.
This awesome-gbb skill is therefore authored from Microsoft Learn + SDK audit
material instead of copied from a stable upstream `SKILL.md`.

---

## 3. Verification checklist (the executable contract)

> **For coding agents**: `validation.runnable` is `false`. Do not treat this as
> a self-contained automation path; the repo smoke below only verifies the
> broken-symlink state. Functional validation still needs a live Foundry
> project, memory-enabled model deployments, and Azure subscription access.

```bash
#!/usr/bin/env bash
# HUMAN EXECUTION ONLY — full validation needs a live Azure subscription and Foundry project.
set -euo pipefail

GOT_SHA=$(git ls-remote https://github.com/microsoft/skills main | awk '{print $1}')
echo "microsoft/skills main HEAD: $GOT_SHA"

STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
  "https://github.com/microsoft/skills/tree/main/skills/foundry-memory")
echo "skills/foundry-memory: HTTP $STATUS"

SYMLINK_STATUS=$(curl -sL -o /dev/null -w '%{http_code}' \
  "https://github.com/microsoft/skills/tree/main/.github/plugins/microsoft-foundry/skills/foundry-memory")
echo "symlink stub: HTTP $SYMLINK_STATUS"
```

**Expected output** must contain (substring match):

- `microsoft/skills main HEAD:`
- `skills/foundry-memory: HTTP`
- `symlink stub: HTTP 200`

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `git ls-remote microsoft/skills main` | ✅ | `325091fc44bafebc11330a442af58039248c9f29` at authoring time |
| upstream tree path | ✅ | `skills/foundry-memory: HTTP 404` |
| symlink stub path | ✅ | `symlink stub: HTTP 200` |

Captured at `last_validated: 2026-05-25` by `copilot-cli`.

---

## 5. Re-pin procedure

When upstream advances:

1. Run `git ls-remote https://github.com/microsoft/skills main`
2. Update `upstream.pinned_sha` and `upstream.pinned_commit_message`
3. Re-run the repo smoke from § 3 to confirm whether the broken path is still
   404 and whether the symlink stub still exists
4. If Microsoft publishes a real upstream `skills/foundry-memory/SKILL.md`,
   rewrite this skill as a normal wrapper and PATCH-bump `skills/foundry-memory/SKILL.md`
5. Re-validate the Learn articles and any SDK snippets used in the body

---

## 6. URLs to re-validate

- <https://github.com/microsoft/skills>
- <https://github.com/microsoft/skills/tree/main/.github/plugins/microsoft-foundry/skills/foundry-memory>
- <https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-memory>
- <https://learn.microsoft.com/azure/foundry/agents/how-to/memory-usage>
- <https://learn.microsoft.com/azure/foundry/how-to/develop/langchain-memory>

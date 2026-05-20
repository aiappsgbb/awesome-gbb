---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: Azure-Samples/azd-ai-starter-basic
  ref: main
  pinned_sha: a781bbcc229048f6dd12771722342899d7cb23d7
  pinned_commit_message: |
    feat: add ACR support for existing AI projects when hosted agents require a registry (#59)
  license: MIT
  notes: |
    This skill wraps the `azd ai agent` + Azure Container Apps deployment pattern and
    vendors scaffold concepts from `azd-ai-starter-basic` so generated projects remain
    self-contained. Full validation runs `azd up` into a test subscription, so drift
    issues are human-triaged rather than assigned to GHCP automation.

docs_to_revalidate:
  - "https://github.com/Azure-Samples/azd-ai-starter-basic"
  - "https://github.com/Azure-Samples/azd-ai-starter-basic/blob/main/README.md"
  - "https://learn.microsoft.com/azure/developer/azure-developer-cli/"

known_issues: []

validation:
  requires:
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated az/azd auth
    # Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
    set -euo pipefail

    : "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
    : "${AZURE_TENANT_ID:?Set target tenant id}"
    : "${THREADLIGHT_PROJECT_DIR:?Set path to a generated threadlight-deploy azd project}"
    : "${AZURE_LOCATION:=swedencentral}"
    : "${AZURE_ENV_NAME:=upstream-pin-threadlight-deploy}"

    PINNED_SHA="${PINNED_SHA:-a781bbcc229048f6dd12771722342899d7cb23d7}"
    ROOT_DIR="$(pwd)"
    WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/threadlight-deploy}"
    THREADLIGHT_PROJECT_DIR="$(cd "$THREADLIGHT_PROJECT_DIR" && pwd)"

    rm -rf "$WORKDIR"
    mkdir -p "$WORKDIR"
    git clone --quiet https://github.com/Azure-Samples/azd-ai-starter-basic "$WORKDIR/azd-ai-starter-basic"
    cd "$WORKDIR/azd-ai-starter-basic"
    git checkout --quiet "$PINNED_SHA"
    test -f README.md

    actual_sub="$(az account show --query id -o tsv)"
    actual_tenant="$(az account show --query tenantId -o tsv)"
    test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
    test "$actual_tenant" = "$AZURE_TENANT_ID"
    az account set --subscription "$AZURE_SUBSCRIPTION_ID"

    cd "$THREADLIGHT_PROJECT_DIR"
    azd auth login --tenant-id "$AZURE_TENANT_ID"
    azd env select "$AZURE_ENV_NAME" || azd env new "$AZURE_ENV_NAME" \
      --subscription "$AZURE_SUBSCRIPTION_ID" \
      --location "$AZURE_LOCATION"
    azd up --no-prompt
    azd ai agent validate
    azd ai agent show
    azd ai agent invoke "Reply with the token THREADLIGHT_DEPLOY_SMOKE_OK only."

    echo "THREADLIGHT_DEPLOY_VALIDATION_PASS"
  expected_output:
    - "THREADLIGHT_DEPLOY_VALIDATION_PASS"
  failure_signatures: []

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 0
---

# Upstream pin — `threadlight-deploy` skill

This file is the **machine-readable validation contract** for the
`threadlight-deploy` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `Azure-Samples/azd-ai-starter-basic` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `a781bbcc229048f6dd12771722342899d7cb23d7` |
| **Pinned commit subject** | `feat: add ACR support for existing AI projects when hosted agents require a registry (#59)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-15` |

Refresh procedure:
```bash
git ls-remote https://github.com/Azure-Samples/azd-ai-starter-basic main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Verification checklist (the executable contract)

> **For coding agents**: `validation.runnable` is `false`. Do not run this in
> GHCP automation; it deploys a generated project with `azd up`.

```bash
#!/usr/bin/env bash
# HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated az/azd auth
# Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
: "${AZURE_TENANT_ID:?Set target tenant id}"
: "${THREADLIGHT_PROJECT_DIR:?Set path to a generated threadlight-deploy azd project}"
: "${AZURE_LOCATION:=swedencentral}"
: "${AZURE_ENV_NAME:=upstream-pin-threadlight-deploy}"

PINNED_SHA="${PINNED_SHA:-a781bbcc229048f6dd12771722342899d7cb23d7}"
ROOT_DIR="$(pwd)"
WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/threadlight-deploy}"
THREADLIGHT_PROJECT_DIR="$(cd "$THREADLIGHT_PROJECT_DIR" && pwd)"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
git clone --quiet https://github.com/Azure-Samples/azd-ai-starter-basic "$WORKDIR/azd-ai-starter-basic"
cd "$WORKDIR/azd-ai-starter-basic"
git checkout --quiet "$PINNED_SHA"
test -f README.md

actual_sub="$(az account show --query id -o tsv)"
actual_tenant="$(az account show --query tenantId -o tsv)"
test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
test "$actual_tenant" = "$AZURE_TENANT_ID"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"

cd "$THREADLIGHT_PROJECT_DIR"
azd auth login --tenant-id "$AZURE_TENANT_ID"
azd env select "$AZURE_ENV_NAME" || azd env new "$AZURE_ENV_NAME" \
  --subscription "$AZURE_SUBSCRIPTION_ID" \
  --location "$AZURE_LOCATION"
azd up --no-prompt
azd ai agent validate
azd ai agent show
azd ai agent invoke "Reply with the token THREADLIGHT_DEPLOY_SMOKE_OK only."

echo "THREADLIGHT_DEPLOY_VALIDATION_PASS"
```

**Expected output** must contain (substring match):

- `THREADLIGHT_DEPLOY_VALIDATION_PASS`

**Failure signatures**: none recorded.

---

## 3. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Issue-only validation procedure | ✅ | Human-run script documented for generated-project `azd up` + agent invoke. |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 4. Known issues at this pin

No linked upstream issues are recorded for this pin.

---

## 5. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/Azure-Samples/azd-ai-starter-basic main
   ```
2. **Diff scaffold assumptions** against the generated artifacts described in
   `threadlight-deploy` Phase 5, especially `azure.yaml`, `agent.yaml`, and
   vendored Bicep module shapes.
3. **Update front-matter**: set `upstream.pinned_sha` to the new value and
   `upstream.pinned_commit_message` to the new commit subject.
4. **Human-run validation**: run the script in § 2 in a disposable validation
   environment.
5. **Verify expected output**: each `expected_output[]` substring must appear.
6. **Update audit trail**: set `last_validated`, `validated_by`, and
   `known_issues_count`.
7. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
8. **Open PR**: touch only `references/upstream-pin.md` and the SKILL.md
   frontmatter version line unless the issue explicitly requests a scaffold change.

---

## 6. URLs to re-validate (link-rot detector input)

- <https://github.com/Azure-Samples/azd-ai-starter-basic>
- <https://github.com/Azure-Samples/azd-ai-starter-basic/blob/main/README.md>
- <https://learn.microsoft.com/azure/developer/azure-developer-cli/>

---

## 7. Cross-references worth bookmarking

- `README.md` — upstream starter usage and deployment notes
- `infra/` — upstream infrastructure scaffold patterns for generated projects

---

## 8. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. `automation_tier` is `issue_only` and `validation.runnable` is `false`.
>    Do not run the live validation script without explicit credentials from a human.
> 2. Open or update the drift issue with the new SHA and ask a human maintainer to
>    run § 2.
> 3. If the human posts passing evidence, update this pin file and bump only the
>    SKILL.md `metadata.version` PATCH line.

---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: microsoft-foundry/foundry-samples
  ref: main
  pinned_sha: 72a65ff0a41f597c1fd53e9125cbc344db566617
  pinned_commit_message: |
    feat: add azure-search-rag hosted agent sample (#283)
  license: MIT
  notes: |
    This skill vendors the `15-private-network-standard-agent-setup` Bicep reference
    under its own `templates/` folder and predates the upstream azd template. The
    vendored fork also layers awesome-gbb-only hub peering, APIM DNS-zone link, and
    reverse-peering output behavior on top. Refreshes must diff the upstream Bicep
    subtree and re-apply local additions; do not overwrite the vendored templates
    wholesale.

docs_to_revalidate:
  - "https://github.com/microsoft-foundry/foundry-samples"
  - "https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
  - "https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/README.md"

known_issues: []

validation:
  requires:
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated CLI profile
    # Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
    set -euo pipefail

    : "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
    : "${AZURE_TENANT_ID:?Set target tenant id}"
    : "${AZURE_LOCATION:=swedencentral}"
    : "${AZURE_RESOURCE_GROUP:?Set disposable resource group for validation}"
    : "${BICEP_PARAMETERS_FILE:?Set path to a reviewed .bicepparam for this test deployment}"
    : "${DEPLOYMENT_TIMESTAMP:=$(date -u +%Y%m%d%H%M%S)}"

    PINNED_SHA="${PINNED_SHA:-72a65ff0a41f597c1fd53e9125cbc344db566617}"
    ROOT_DIR="$(pwd)"
    WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-vnet-deploy}"
    BICEP_PARAMETERS_FILE="$(cd "$(dirname "$BICEP_PARAMETERS_FILE")" && pwd)/$(basename "$BICEP_PARAMETERS_FILE")"

    rm -rf "$WORKDIR"
    mkdir -p "$WORKDIR"
    git clone --quiet https://github.com/microsoft-foundry/foundry-samples "$WORKDIR/foundry-samples"
    cd "$WORKDIR/foundry-samples"
    git checkout --quiet "$PINNED_SHA"

    TEMPLATE_DIR="infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
    test -f "$TEMPLATE_DIR/main.bicep"

    actual_sub="$(az account show --query id -o tsv)"
    actual_tenant="$(az account show --query tenantId -o tsv)"
    test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
    test "$actual_tenant" = "$AZURE_TENANT_ID"
    az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors

    az bicep build \
      --file "$TEMPLATE_DIR/main.bicep" \
      --outfile "$WORKDIR/foundry-vnet-main.json"

    az deployment group what-if \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --template-file "$TEMPLATE_DIR/main.bicep" \
      --parameters "$BICEP_PARAMETERS_FILE" \
      --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

    az deployment group create \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --template-file "$TEMPLATE_DIR/main.bicep" \
      --parameters "$BICEP_PARAMETERS_FILE" \
      --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

    echo "FOUNDRY_VNET_DEPLOY_VALIDATION_PASS"
  expected_output:
    - "FOUNDRY_VNET_DEPLOY_VALIDATION_PASS"
  failure_signatures: []

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 0
---

# Upstream pin — `foundry-vnet-deploy` skill

This file is the **machine-readable validation contract** for the
`foundry-vnet-deploy` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit trail.
Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `microsoft-foundry/foundry-samples` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `72a65ff0a41f597c1fd53e9125cbc344db566617` |
| **Pinned commit subject** | `feat: add azure-search-rag hosted agent sample (#283)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-05-15` |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft-foundry/foundry-samples main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Verification checklist (the executable contract)

> **For coding agents**: `validation.runnable` is `false`. Do not run this in
> GHCP automation; it creates Azure resources in a disposable validation group.

```bash
#!/usr/bin/env bash
# HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated CLI profile
# Run this from a shell with AZURE_CONFIG_DIR set per azure-tenant-isolation skill
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
: "${AZURE_TENANT_ID:?Set target tenant id}"
: "${AZURE_LOCATION:=swedencentral}"
: "${AZURE_RESOURCE_GROUP:?Set disposable resource group for validation}"
: "${BICEP_PARAMETERS_FILE:?Set path to a reviewed .bicepparam for this test deployment}"
: "${DEPLOYMENT_TIMESTAMP:=$(date -u +%Y%m%d%H%M%S)}"

PINNED_SHA="${PINNED_SHA:-72a65ff0a41f597c1fd53e9125cbc344db566617}"
ROOT_DIR="$(pwd)"
WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-vnet-deploy}"
BICEP_PARAMETERS_FILE="$(cd "$(dirname "$BICEP_PARAMETERS_FILE")" && pwd)/$(basename "$BICEP_PARAMETERS_FILE")"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
git clone --quiet https://github.com/microsoft-foundry/foundry-samples "$WORKDIR/foundry-samples"
cd "$WORKDIR/foundry-samples"
git checkout --quiet "$PINNED_SHA"

TEMPLATE_DIR="infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
test -f "$TEMPLATE_DIR/main.bicep"

actual_sub="$(az account show --query id -o tsv)"
actual_tenant="$(az account show --query tenantId -o tsv)"
test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
test "$actual_tenant" = "$AZURE_TENANT_ID"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors

az bicep build \
  --file "$TEMPLATE_DIR/main.bicep" \
  --outfile "$WORKDIR/foundry-vnet-main.json"

az deployment group what-if \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file "$TEMPLATE_DIR/main.bicep" \
  --parameters "$BICEP_PARAMETERS_FILE" \
  --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

az deployment group create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file "$TEMPLATE_DIR/main.bicep" \
  --parameters "$BICEP_PARAMETERS_FILE" \
  --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

echo "FOUNDRY_VNET_DEPLOY_VALIDATION_PASS"
```

**Expected output** must contain (substring match):

- `FOUNDRY_VNET_DEPLOY_VALIDATION_PASS`

**Failure signatures**: none recorded.

---

## 3. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| Issue-only validation procedure | ✅ | Human-run script documented for Bicep build, what-if, and live deployment. |

Captured at `last_validated: 2026-05-15` by `ricchi`.

---

## 4. Known issues at this pin

No linked upstream issues are recorded for this pin.

---

## 5. Re-pin procedure

When upstream advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/microsoft-foundry/foundry-samples main
   ```
2. **Diff vendored Bicep carefully**: compare only
   `infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/`
   against this skill's vendored `templates/` subtree, then re-apply the local
   awesome-gbb-only additions called out in `upstream.notes`.
3. **Update front-matter**: set `upstream.pinned_sha` to the new value and
   `upstream.pinned_commit_message` to the new commit subject.
4. **Human-run validation**: run the script in § 2 in a disposable validation
   resource group.
5. **Verify expected output**: each `expected_output[]` substring must appear.
6. **Update audit trail**: set `last_validated`, `validated_by`, and
   `known_issues_count`.
7. **Bump SKILL.md `metadata.version` PATCH** per AGENTS.md § 5.
8. **Open PR**: touch only `references/upstream-pin.md` and the SKILL.md
   frontmatter version line unless the issue explicitly requests a vendored
   template refresh.

---

## 6. URLs to re-validate (link-rot detector input)

- <https://github.com/microsoft-foundry/foundry-samples>
- <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup>
- <https://github.com/microsoft-foundry/foundry-samples/blob/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/README.md>

---

## 7. Cross-references worth bookmarking

- `infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/` — upstream Bicep reference subtree
- `infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/README.md` — upstream deployment notes

---

## 8. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. `automation_tier` is `issue_only` and `validation.runnable` is `false`.
>    Do not run the live validation script without explicit credentials from a human.
> 2. This skill vendors and extends the upstream Bicep. Never overwrite the
>    skill's templates as part of a pin-only refresh.
> 3. If the human posts passing evidence, update this pin file and bump only the
>    SKILL.md `metadata.version` PATCH line.

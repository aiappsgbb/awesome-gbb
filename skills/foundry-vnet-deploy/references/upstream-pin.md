---
schema_version: 2
freshness_tier: A
automation_tier: issue_only

upstream:
  type: github_repo
  repo: microsoft-foundry/foundry-samples
  ref: main
  pinned_sha: 12c97fbbf0518a7cac02acc1706cd5000e813ce0
  pinned_commit_message: |
    .NET Align samples with latest MAF 1.12.0 and the new FHA responses v2.0 support (#624)
  license: MIT
  notes: |
    This skill vendors **two** Foundry-samples Bicep references under its own
    `templates/` folder (it predates the upstream azd templates):
      - `templates/standard-agent/`  <- `15-private-network-standard-agent-setup`
        (BYO Search + Storage + Cosmos, all reached over private endpoints).
      - `templates/basic-vnet/`      <- `11-private-network-basic-vnet`
        (platform-managed storage; App Insights + Log Analytics + Monitor Private
        Link Scope for private trace ingestion are upstream-native in template 11).
    awesome-gbb layers the same optional integrations on top of BOTH trees: hub
    peering (`spoke-hub-peering.bicep`), APIM DNS-zone link (`apim-dns-zone-link.bicep`),
    a `hubReversePeeringCommand` output, hosted-agent developer RBAC, and project-MI
    telemetry roles. Refreshes must diff EACH upstream subtree (15 and 11) against its
    vendored tree and re-apply the local additions; do not overwrite the vendored
    templates wholesale.

docs_to_revalidate:
  - "https://github.com/microsoft-foundry/foundry-samples"
  - "https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
  - "https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet"
  - "https://learn.microsoft.com/azure/foundry/agents/concepts/agents-networking-deep-dive"
  - "https://learn.microsoft.com/azure/foundry/how-to/configure-private-link"
  - "https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale"

known_issues: []

validation:
  requires:
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated CLI profile
    # Run from the repo root (or set SKILL_DIR) with AZURE_CONFIG_DIR set per azure-tenant-isolation
    set -euo pipefail

    : "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
    : "${AZURE_TENANT_ID:?Set target tenant id}"
    : "${AZURE_LOCATION:=swedencentral}"
    : "${AZURE_RESOURCE_GROUP:?Set disposable resource group for validation}"
    : "${BICEP_PARAMETERS_FILE:?Set path to a reviewed .bicepparam for this test deployment}"
    : "${DEPLOYMENT_TIMESTAMP:=$(date -u +%Y%m%d%H%M%S)}"
    # Which vendored template to live-deploy: standard-agent (template 15) or basic-vnet (template 11)
    : "${TEMPLATE_UNDER_TEST:=standard-agent}"

    PINNED_SHA="${PINNED_SHA:-12c97fbbf0518a7cac02acc1706cd5000e813ce0}"
    ROOT_DIR="$(pwd)"
    SKILL_DIR="${SKILL_DIR:-$ROOT_DIR/skills/foundry-vnet-deploy}"
    WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-vnet-deploy}"
    BICEP_PARAMETERS_FILE="$(cd "$(dirname "$BICEP_PARAMETERS_FILE")" && pwd)/$(basename "$BICEP_PARAMETERS_FILE")"

    # 1. Upstream integrity — clone at pinned SHA; BOTH source templates must exist + build
    rm -rf "$WORKDIR"
    mkdir -p "$WORKDIR"
    git clone --quiet https://github.com/microsoft-foundry/foundry-samples "$WORKDIR/foundry-samples"
    cd "$WORKDIR/foundry-samples"
    git checkout --quiet "$PINNED_SHA"

    STANDARD_SRC="infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
    BASIC_SRC="infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet"
    test -f "$STANDARD_SRC/main.bicep"
    test -f "$BASIC_SRC/main.bicep"
    az bicep build --file "$STANDARD_SRC/main.bicep" --outfile "$WORKDIR/upstream-standard.json"
    az bicep build --file "$BASIC_SRC/main.bicep"    --outfile "$WORKDIR/upstream-basic.json"

    # 2. Vendored integrity — BOTH shipped templates must build from the skill tree
    cd "$ROOT_DIR"
    test -f "$SKILL_DIR/templates/standard-agent/main.bicep"
    test -f "$SKILL_DIR/templates/basic-vnet/main.bicep"
    az bicep build --file "$SKILL_DIR/templates/standard-agent/main.bicep" --outfile "$WORKDIR/vendored-standard.json"
    az bicep build --file "$SKILL_DIR/templates/basic-vnet/main.bicep"    --outfile "$WORKDIR/vendored-basic.json"

    # 3. Live smoke — what-if + deploy the SELECTED vendored template
    DEPLOY_TEMPLATE="$SKILL_DIR/templates/$TEMPLATE_UNDER_TEST/main.bicep"
    test -f "$DEPLOY_TEMPLATE"

    actual_sub="$(az account show --query id -o tsv)"
    actual_tenant="$(az account show --query tenantId -o tsv)"
    test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
    test "$actual_tenant" = "$AZURE_TENANT_ID"
    az account set --subscription "$AZURE_SUBSCRIPTION_ID"
    az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors

    az deployment group what-if \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --template-file "$DEPLOY_TEMPLATE" \
      --parameters "$BICEP_PARAMETERS_FILE" \
      --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

    az deployment group create \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --template-file "$DEPLOY_TEMPLATE" \
      --parameters "$BICEP_PARAMETERS_FILE" \
      --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

    echo "FOUNDRY_VNET_DEPLOY_VALIDATION_PASS"
  expected_output:
    - "FOUNDRY_VNET_DEPLOY_VALIDATION_PASS"
  failure_signatures: []

last_validated: 2026-07-02
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
| **Pinned SHA** | `12c97fbbf0518a7cac02acc1706cd5000e813ce0` |
| **Pinned commit subject** | `.NET Align samples with latest MAF 1.12.0 and the new FHA responses v2.0 support (#624)` |
| **License** | `MIT` |
| **First authored against** | `2026-05-15` |
| **Last re-validated** | `2026-07-02` |

This skill now vendors **two** upstream Bicep references:

| Vendored tree | Upstream subtree | Storage model |
|---------------|------------------|---------------|
| `templates/standard-agent/` | `15-private-network-standard-agent-setup` | BYO Search + Storage + Cosmos (all private endpoints) |
| `templates/basic-vnet/` | `11-private-network-basic-vnet` | Platform-managed storage; App Insights + LAW + Monitor Private Link Scope native |

Refresh procedure:
```bash
git ls-remote https://github.com/microsoft-foundry/foundry-samples main
# Compare first column to pinned_sha in front-matter
```

---

## 2. Verification checklist (the executable contract)

> **For coding agents**: `validation.runnable` is `false`. Do not run this in
> GHCP automation; it creates Azure resources in a disposable validation group.
> It builds BOTH vendored templates locally, then live-deploys the one named by
> `TEMPLATE_UNDER_TEST` (default `standard-agent`; re-run with `basic-vnet` to
> exercise the platform-managed-storage path).

```bash
#!/usr/bin/env bash
# HUMAN EXECUTION ONLY — requires Azure subscription + tenant-isolated CLI profile
# Run from the repo root (or set SKILL_DIR) with AZURE_CONFIG_DIR set per azure-tenant-isolation
set -euo pipefail

: "${AZURE_SUBSCRIPTION_ID:?Set target Azure subscription id}"
: "${AZURE_TENANT_ID:?Set target tenant id}"
: "${AZURE_LOCATION:=swedencentral}"
: "${AZURE_RESOURCE_GROUP:?Set disposable resource group for validation}"
: "${BICEP_PARAMETERS_FILE:?Set path to a reviewed .bicepparam for this test deployment}"
: "${DEPLOYMENT_TIMESTAMP:=$(date -u +%Y%m%d%H%M%S)}"
# Which vendored template to live-deploy: standard-agent (template 15) or basic-vnet (template 11)
: "${TEMPLATE_UNDER_TEST:=standard-agent}"

PINNED_SHA="${PINNED_SHA:-12c97fbbf0518a7cac02acc1706cd5000e813ce0}"
ROOT_DIR="$(pwd)"
SKILL_DIR="${SKILL_DIR:-$ROOT_DIR/skills/foundry-vnet-deploy}"
WORKDIR="${WORKDIR:-$ROOT_DIR/.upstream-pin-work/foundry-vnet-deploy}"
BICEP_PARAMETERS_FILE="$(cd "$(dirname "$BICEP_PARAMETERS_FILE")" && pwd)/$(basename "$BICEP_PARAMETERS_FILE")"

# 1. Upstream integrity — clone at pinned SHA; BOTH source templates must exist + build
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
git clone --quiet https://github.com/microsoft-foundry/foundry-samples "$WORKDIR/foundry-samples"
cd "$WORKDIR/foundry-samples"
git checkout --quiet "$PINNED_SHA"

STANDARD_SRC="infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup"
BASIC_SRC="infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet"
test -f "$STANDARD_SRC/main.bicep"
test -f "$BASIC_SRC/main.bicep"
az bicep build --file "$STANDARD_SRC/main.bicep" --outfile "$WORKDIR/upstream-standard.json"
az bicep build --file "$BASIC_SRC/main.bicep"    --outfile "$WORKDIR/upstream-basic.json"

# 2. Vendored integrity — BOTH shipped templates must build from the skill tree
cd "$ROOT_DIR"
test -f "$SKILL_DIR/templates/standard-agent/main.bicep"
test -f "$SKILL_DIR/templates/basic-vnet/main.bicep"
az bicep build --file "$SKILL_DIR/templates/standard-agent/main.bicep" --outfile "$WORKDIR/vendored-standard.json"
az bicep build --file "$SKILL_DIR/templates/basic-vnet/main.bicep"    --outfile "$WORKDIR/vendored-basic.json"

# 3. Live smoke — what-if + deploy the SELECTED vendored template
DEPLOY_TEMPLATE="$SKILL_DIR/templates/$TEMPLATE_UNDER_TEST/main.bicep"
test -f "$DEPLOY_TEMPLATE"

actual_sub="$(az account show --query id -o tsv)"
actual_tenant="$(az account show --query tenantId -o tsv)"
test "$actual_sub" = "$AZURE_SUBSCRIPTION_ID"
test "$actual_tenant" = "$AZURE_TENANT_ID"
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION" --only-show-errors

az deployment group what-if \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file "$DEPLOY_TEMPLATE" \
  --parameters "$BICEP_PARAMETERS_FILE" \
  --parameters deploymentTimestamp="$DEPLOYMENT_TIMESTAMP"

az deployment group create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file "$DEPLOY_TEMPLATE" \
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
| Dual-template local build | ✅ | `az bicep build` of both `templates/standard-agent/main.bicep` and `templates/basic-vnet/main.bicep` succeeds (exit 0, warning-parity with upstream). |
| Issue-only live deploy (standard-agent) | ✅ | `az deployment group create` on CI sub `swedencentral`: full network-isolated stack Succeeded via documented Step 10b (account-caphost ARM timeout → REST caphost recovery). Account PNA=Disabled + agent injection; both caphosts Succeeded; 4 PEs; 6 DNS zones; 3 BYO connections; all project-MI roles applied. Evidence in the update PR body per AGENTS.md § 2.9. |
| Issue-only live deploy (basic-vnet) | ✅ | `az deployment group create` (`TEMPLATE_UNDER_TEST=basic-vnet`) on CI sub `swedencentral`: Succeeded (PT7M39S). Account PNA=Disabled; project caphost Succeeded; ACR Premium PNA=Disabled; 3 PEs; 8 DNS zones. Evidence in the update PR body per AGENTS.md § 2.9. |

Both live deployments re-validated `2026-07-02` by `ricchi` on the CI subscription
(`swedencentral`). standard-agent hit the documented account-capability-host ARM
timeout and was recovered via SKILL.md Step 10b (REST caphost creation + remaining
post-caphost role assignments via Bicep) — proving both the template and the
documented fallback. Full `az` evidence pasted into the update PR body
(no-evidence-no-merge per AGENTS.md § 2.9).

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
2. **Diff BOTH vendored Bicep subtrees carefully**: compare
   `infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/`
   against `templates/standard-agent/`, AND
   `infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet/`
   against `templates/basic-vnet/`, then re-apply the local awesome-gbb-only
   additions called out in `upstream.notes` to each tree.
3. **Update front-matter**: set `upstream.pinned_sha` to the new value and
   `upstream.pinned_commit_message` to the new commit subject.
4. **Human-run validation**: run the script in § 2 in a disposable validation
   resource group, once per `TEMPLATE_UNDER_TEST` value.
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
- <https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet>
- <https://learn.microsoft.com/azure/foundry/agents/concepts/agents-networking-deep-dive>
- <https://learn.microsoft.com/azure/foundry/how-to/configure-private-link>
- <https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale>

---

## 7. Cross-references worth bookmarking

- `infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup/` — upstream Bicep reference subtree (→ `templates/standard-agent/`)
- `infrastructure/infrastructure-setup-bicep/11-private-network-basic-vnet/` — upstream Bicep reference subtree (→ `templates/basic-vnet/`)
- `references/agent-networking.md` — hosted vs prompt agent subnet consumption + sizing
- `references/agent-tools-network-isolation.md` — tool reachability matrix under isolation

---

## 8. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. `automation_tier` is `issue_only` and `validation.runnable` is `false`.
>    Do not run the live validation script without explicit credentials from a human.
> 2. This skill vendors and extends **two** upstream Bicep trees. Never overwrite
>    the skill's templates as part of a pin-only refresh — diff each subtree (15
>    and 11) and re-apply the awesome-gbb additions listed in `upstream.notes`.
> 3. If the human posts passing evidence, update this pin file and bump only the
>    SKILL.md `metadata.version` PATCH line.

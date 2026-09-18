#!/usr/bin/env bash
#
# Canonical multi-tenant bootstrap — Azure Tenant Isolation enforcement.
#
# Source of truth for the prose example in `../../SKILL.md § Script
# preamble template`.
#
# Source this at the top of any shell script that touches Azure. It
# loads the tenant alias from ~/.azure-tenants/index.json, exports both
# AZURE_CONFIG_DIR + AZD_CONFIG_DIR (the foundation guard), and runs
# the az account show assertion (the second guard) — both per the
# two-layered design in ../../SKILL.md § Design.
#
# Usage:
#     # at the top of your deploy.sh / provision.sh
#     source "$(dirname "$0")/path/to/bootstrap.sh" prod
#
# Or as a standalone preamble (per SKILL.md § Script preamble template):
#     AZURE_TENANT_ALIAS=prod source bootstrap.sh
#
# Verified across the 2026-05-26 → 2026-05-29 agentic-loop pilots
# (weather-agent, learn-assistant, hybrid-mcp-agent, smb-credit-memo).
# Caught silent sub-drift between two subs in the same multi-sub tenant
# (T1 + MID-1; see agentic-loop SKILL § Validation history rows 2 + 7).

set -euo pipefail

# ── Azure Tenant Isolation (REQUIRED) ─────────────────────────────────
ALIAS="${1:-${AZURE_TENANT_ALIAS:-prod}}"
INDEX="${AZURE_TENANT_INDEX:-$HOME/.azure-tenants/index.json}"
INDEX=$(python3 -c 'import os,sys; print(os.path.expanduser(sys.argv[1]))' "$INDEX")

if [ ! -f "$INDEX" ]; then
  echo "❌ Tenant index not found at $INDEX" >&2
  echo "   Bootstrap one via the README in this skill (§ The tenant index file)." >&2
  exit 1
fi

TENANT_ID=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["tenants"][sys.argv[2]]["tenant_id"])' "$INDEX" "$ALIAS")
DEFAULT_SUB=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["tenants"][sys.argv[2]]["default_subscription"])' "$INDEX" "$ALIAS")
AZ_CFG=$(python3 -c 'import json,os,sys; t=json.load(open(sys.argv[1]))["tenants"][sys.argv[2]]; print(os.path.expanduser(t.get("config_dir") or "~/.azure-tenants/" + sys.argv[2]))' "$INDEX" "$ALIAS")
AZD_CFG=$(python3 -c 'import json,os,sys; t=json.load(open(sys.argv[1]))["tenants"][sys.argv[2]]; print(os.path.expanduser(t.get("azd_config_dir") or "~/.azd-tenants/" + sys.argv[2]))' "$INDEX" "$ALIAS")
ALLOWED_SUBS_JSON=$(python3 - "$INDEX" "$ALIAS" <<'PY'
import json
import sys

tenant = json.load(open(sys.argv[1]))["tenants"][sys.argv[2]]
allowed = tenant.get("allowed_subscriptions", [])
if not isinstance(allowed, list):
    sys.exit("allowed_subscriptions must be an array of non-empty names or IDs")
if not allowed:
    allowed = [tenant["default_subscription"]]
if not all(isinstance(value, str) and value.strip() for value in allowed):
    sys.exit("allowed_subscriptions (or default_subscription fallback) must contain non-empty names or IDs")
print(json.dumps(allowed))
PY
)

mkdir -p "$AZ_CFG" "$AZD_CFG"
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"

# Read only: preserve the user's active subscription, never select or log in.
if ! ACTUAL_TENANT=$(az account show --query tenantId -o tsv) \
  || ! ACTUAL_SUB=$(az account show --query name -o tsv) \
  || ! ACTUAL_SUB_ID=$(az account show --query id -o tsv); then
  echo "⚠️  No active az session could be verified in $AZ_CFG — check the az error above; authenticate explicitly if needed." >&2
  exit 1
fi

if [ -z "$ACTUAL_TENANT" ] || [ -z "$ACTUAL_SUB" ] || [ -z "$ACTUAL_SUB_ID" ]; then
  echo "⚠️  No active az session in $AZ_CFG — run 'az login --tenant $TENANT_ID'" >&2
  exit 1
fi

if [ "$ACTUAL_TENANT" != "$TENANT_ID" ]; then
  echo "❌ Tenant mismatch (got $ACTUAL_TENANT, want $TENANT_ID for alias '$ALIAS')" >&2
  echo "   This means the isolated config dir has a token from a different tenant." >&2
  echo "   Run: az login --tenant $TENANT_ID" >&2
  exit 1
fi

if ! python3 - "$ALLOWED_SUBS_JSON" "$ACTUAL_SUB" "$ACTUAL_SUB_ID" <<'PY'
import json
import sys

allowed = json.loads(sys.argv[1])
sys.exit(0 if sys.argv[2] in allowed or sys.argv[3] in allowed else 1)
PY
then
  echo "❌ Sub '$ACTUAL_SUB' ($ACTUAL_SUB_ID) not in allowed list for alias '$ALIAS': $ALLOWED_SUBS_JSON" >&2
  echo "   Choose the intended allowed subscription explicitly; bootstrap will not switch it." >&2
  exit 1
fi

echo "✓ Tenant isolation verified: alias=$ALIAS tenant=$TENANT_ID sub=$ACTUAL_SUB id=$ACTUAL_SUB_ID"

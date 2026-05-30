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

if [ ! -f "$INDEX" ]; then
  echo "❌ Tenant index not found at $INDEX" >&2
  echo "   Bootstrap one via the README in this skill (§ The tenant index file)." >&2
  exit 1
fi

TENANT_ID=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['tenant_id'])")
DEFAULT_SUB=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['default_subscription'])")
AZ_CFG=$(python3  -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('config_dir');     print(os.path.expanduser(v) if v else os.path.expanduser('~/.azure-tenants/$ALIAS'))")
AZD_CFG=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('azd_config_dir'); print(os.path.expanduser(v) if v else os.path.expanduser('~/.azd-tenants/$ALIAS'))")

mkdir -p "$AZ_CFG" "$AZD_CFG"
export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"

# Assertion — must match BOTH tenant + sub (per § The mandatory verify-before-act pattern).
# T1 from the audit: never auto-switch to a sub outside allowed_subscriptions.
ACTUAL_TENANT=$(az account show --query tenantId -o tsv 2>/dev/null || true)
ACTUAL_SUB=$(az account show --query name -o tsv 2>/dev/null || true)

if [ -z "$ACTUAL_TENANT" ]; then
  echo "⚠️  No active az session in $AZ_CFG — run 'az login --tenant $TENANT_ID'" >&2
  exit 1
fi

if [ "$ACTUAL_TENANT" != "$TENANT_ID" ]; then
  echo "❌ Tenant mismatch (got $ACTUAL_TENANT, want $TENANT_ID for alias '$ALIAS')" >&2
  echo "   This means the isolated config dir has a token from a different tenant." >&2
  echo "   Run: az login --tenant $TENANT_ID" >&2
  exit 1
fi

if [ "$ACTUAL_SUB" != "$DEFAULT_SUB" ]; then
  echo "❌ Sub mismatch (got $ACTUAL_SUB, want $DEFAULT_SUB for alias '$ALIAS')" >&2
  echo "   Run: az account set --subscription \"$DEFAULT_SUB\"" >&2
  exit 1
fi

echo "✓ Tenant isolation verified: alias=$ALIAS tenant=$TENANT_ID sub=$DEFAULT_SUB"

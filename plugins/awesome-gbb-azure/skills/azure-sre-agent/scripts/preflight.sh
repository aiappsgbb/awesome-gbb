#!/usr/bin/env bash
# scripts/preflight.sh — Azure SRE Agent pre-flight check
# Usage: bash scripts/preflight.sh [<subscription-id>]
#
# Validates the 5 gates the official Microsoft docs assume are already
# satisfied. Run before walking into a customer Tuesday meeting.

set -euo pipefail

SUB="${1:-$(az account show --query id -o tsv 2>/dev/null || true)}"
if [[ -z "$SUB" ]]; then
  echo "ERR: pass <subscription-id> or 'az login' first" >&2
  exit 2
fi

GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
fail() { echo "${RED}FAIL${OFF} $*"; exit 1; }
pass() { echo "${GREEN}PASS${OFF} $*"; }
warn() { echo "${YEL}WARN${OFF} $*"; }

echo "── Azure SRE Agent pre-flight against sub: $SUB ──"

# 1) Microsoft.App RP registered (DeploymentNotFound symptom)
state=$(az provider show --namespace Microsoft.App --subscription "$SUB" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)
if [[ "$state" == "Registered" ]]; then
  pass "Microsoft.App RP registered"
else
  fail "Microsoft.App RP is '$state'. Fix: az provider register --namespace Microsoft.App --subscription $SUB"
fi

# 2) Caller has RBAC perm to assign roles (SRE Agent provisioning needs this)
who=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)
if [[ -z "$who" ]]; then
  warn "Signed in as a service principal; ensure it has Microsoft.Authorization/roleAssignments/write at the target scope"
else
  has_owner=$(az role assignment list --assignee "$who" --subscription "$SUB" --query "[?roleDefinitionName=='Owner' || roleDefinitionName=='User Access Administrator'] | length(@)" -o tsv)
  if [[ "${has_owner:-0}" -ge 1 ]]; then
    pass "Caller has Owner or User Access Administrator role"
  else
    fail "Caller lacks Owner or User Access Administrator on sub $SUB — RBAC assignment to SRE Agent UAMI will fail"
  fi
fi

# 3) Region available
SUPPORTED=(swedencentral eastus2 uksouth australiaeast)
echo "    Supported preview regions: ${SUPPORTED[*]} (request more via aka.ms/sreagent/region)"
pass "Region check is informational; pick one of the above when deploying"

# 4) Network reachability (Zscaler / proxy trap)
for host in sre.azure.com www.azuresre.ai; do
  if curl -sS --max-time 5 --head "https://$host" >/dev/null 2>&1; then
    pass "Reachable: https://$host"
  else
    fail "Cannot reach https://$host — check Zscaler / corporate proxy allow-list for *.azuresre.ai + sre.azure.com"
  fi
done

# 5) Optional: Citadel JWT readiness (only check if env hints present)
if [[ -n "${CITADEL_GATEWAY_URL:-}" ]]; then
  if [[ -n "${CITADEL_PRODUCT_KEY:-}" ]] || [[ -n "${CITADEL_JWT:-}" ]]; then
    pass "Citadel gateway env set; credentials present"
  else
    warn "CITADEL_GATEWAY_URL set but no key/JWT — issue an Access Contract via citadel-spoke-onboarding before deploy"
  fi
fi

echo
echo "${GREEN}All pre-flight checks passed.${OFF} Next:"
echo "  git clone https://github.com/microsoft/sre-agent.git && cd sre-agent/sreagent-templates"
echo "  ./bin/install-prerequisites.sh"
echo "  ./bin/new-agent.sh --recipe minimal --non-interactive --set agentName=... --set location=swedencentral --set targetRGs=... -o my-agent/"
echo "  ./bin/deploy.sh my-agent/"

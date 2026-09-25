#!/usr/bin/env bash
#
# Local diagnostic for Foundry hosted agents returning `server_error`.
#
# Source of truth for the prose example in
# `../../SKILL.md § Diagnosing server_error locally`.
#
# Step 1 (pull `run.last_error` via the SYNC AIProjectClient) is documented
# inline in SKILL.md — it requires Python, not bash. This script handles
# steps 2-4: chat-model deployment quota inspection, direct model
# reproduction (bypassing the agent runtime), and an optional App Insights
# KQL probe.
#
# Required env:
#   AZURE_RESOURCE_GROUP    — RG containing the Foundry / Cognitive Services
#                             account
#   FOUNDRY_ACCOUNT         — Foundry / Cognitive Services account name
#   MODEL_DEPLOYMENT_NAME   — chat-model deployment name (the one the agent
#                             uses, NOT the agent name)
# Optional env:
#   APPINSIGHTS_RESOURCE_ID — full ARM resource ID; gates the KQL probe
#
# Usage:
#   AZURE_RESOURCE_GROUP=<rg> FOUNDRY_ACCOUNT=<acct> \
#   MODEL_DEPLOYMENT_NAME=<deployment> \
#     ./diagnose_server_error.sh

set -euo pipefail

: "${AZURE_RESOURCE_GROUP:?required}"
: "${FOUNDRY_ACCOUNT:?required}"
: "${MODEL_DEPLOYMENT_NAME:?required}"
: "${DIAGNOSTIC_EVIDENCE_DIR:?required existing owner-private directory}"
test -d "$DIAGNOSTIC_EVIDENCE_DIR" || { echo "BLOCKED: evidence directory missing" >&2; exit 1; }
umask 077

run_az() {
    python3 - "$@" <<'PY'
import subprocess, sys
try:
    result = subprocess.run(["az", *sys.argv[1:]], timeout=30)
except subprocess.TimeoutExpired:
    print("DIAGNOSTIC_IO_TIMEOUT: Azure CLI outcome unobserved", file=sys.stderr)
    raise SystemExit(124)
raise SystemExit(result.returncode)
PY
}

verdict="inconclusive"

echo "=== Step 2 — deployment quota (Capacity is TPM in thousands) ==="
run_az cognitiveservices account deployment list \
    -g "$AZURE_RESOURCE_GROUP" \
    -n "$FOUNDRY_ACCOUNT" \
    -o table

echo
echo "=== Step 3 — optional NEW model probe (not original-operation reconciliation) ==="
if [ "${ALLOW_NEW_MODEL_PROBE:-no}" != "yes" ]; then
    echo "No new inference authorized. Reconcile the original operation; quota metadata alone is inconclusive."
    exit 0
fi
endpoint="$(run_az cognitiveservices account show \
    -g "$AZURE_RESOURCE_GROUP" -n "$FOUNDRY_ACCOUNT" \
    --query "properties.endpoint" -o tsv)"
token="$(run_az account get-access-token \
    --resource https://cognitiveservices.azure.com \
    --query accessToken -o tsv)"

url="${endpoint%/}/openai/deployments/${MODEL_DEPLOYMENT_NAME}/chat/completions?api-version=2024-10-21"
body_file="$(mktemp "$DIAGNOSTIC_EVIDENCE_DIR/model-body.XXXXXX")"
headers_file="$(mktemp "$DIAGNOSTIC_EVIDENCE_DIR/model-headers.XXXXXX")"
http_code="$(curl -sS --connect-timeout 10 --max-time 30 -w "%{http_code}" -X POST "$url" \
    -o "$body_file" -D "$headers_file" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"ping"}],"max_tokens":5}')"
echo "HTTP $http_code"
echo "Raw response retained privately; do not publish body or headers without sanitization."
echo

if [ "$http_code" = "429" ]; then
    verdict="PROBE 429 (this new call was throttled; original failure cause is not established)"
elif [ "$http_code" = "200" ]; then
    verdict="PROBE SUCCEEDED (does not disprove throttling of the original request)"
fi

if [ -n "${APPINSIGHTS_RESOURCE_ID:-}" ]; then
    echo
    echo "=== Step 4 — App Insights probe (last 15 min, 429 / RateLimitExceeded) ==="
    if ! run_az monitor app-insights query \
        --ids "$APPINSIGHTS_RESOURCE_ID" \
        --analytics-query 'union requests, dependencies | where timestamp > ago(15m) | where resultCode == "429" or message contains "RateLimitExceeded" | project timestamp, name, resultCode, message | take 20' \
        -o table; then
        echo "Telemetry probe unavailable; this is not evidence of a platform failure." >&2
    fi
fi

echo
echo "=== Verdict ==="
echo "$verdict"
echo
echo "Any capacity change requires a separate approved capacity/cost decision."
echo "or:  az cognitiveservices account deployment update \\"
echo "       -g $AZURE_RESOURCE_GROUP -n $FOUNDRY_ACCOUNT \\"
echo "       --deployment-name $MODEL_DEPLOYMENT_NAME --capacity <N>"

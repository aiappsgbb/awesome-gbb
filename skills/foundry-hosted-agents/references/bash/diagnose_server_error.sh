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

verdict="inconclusive"

echo "=== Step 2 — deployment quota (Capacity is TPM in thousands) ==="
az cognitiveservices account deployment list \
    -g "$AZURE_RESOURCE_GROUP" \
    -n "$FOUNDRY_ACCOUNT" \
    -o table

echo
echo "=== Step 3 — reproduce a direct chat call (bypass agent layer) ==="
endpoint="$(az cognitiveservices account show \
    -g "$AZURE_RESOURCE_GROUP" -n "$FOUNDRY_ACCOUNT" \
    --query "properties.endpoint" -o tsv)"
token="$(az account get-access-token \
    --resource https://cognitiveservices.azure.com \
    --query accessToken -o tsv)"

url="${endpoint%/}/openai/deployments/${MODEL_DEPLOYMENT_NAME}/chat/completions?api-version=2024-10-21"
response="$(curl -sS -w "\n%{http_code}" -X POST "$url" \
    -H "Authorization: Bearer $token" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"ping"}],"max_tokens":5}')"
http_code="$(echo "$response" | tail -n1)"
body="$(echo "$response" | sed '$d')"

echo "HTTP $http_code"
echo "$body" | head -c 400
echo

if [ "$http_code" = "429" ]; then
    verdict="CONFIRMED 429 (direct call to deployment throttled — raise Capacity)"
elif [ "$http_code" = "200" ]; then
    verdict="NOT 429 (direct call succeeded — look elsewhere: identity, MCP, container crash)"
fi

if [ -n "${APPINSIGHTS_RESOURCE_ID:-}" ]; then
    echo
    echo "=== Step 4 — App Insights probe (last 15 min, 429 / RateLimitExceeded) ==="
    az monitor app-insights query \
        --ids "$APPINSIGHTS_RESOURCE_ID" \
        --analytics-query 'union requests, dependencies | where timestamp > ago(15m) | where resultCode == "429" or message contains "RateLimitExceeded" | project timestamp, name, resultCode, message | take 20' \
        -o table || true

    if [ "$verdict" = "inconclusive" ]; then
        verdict="LIKELY 429 (check App Insights output above; if non-empty, raise deployment Capacity)"
    fi
fi

echo
echo "=== Verdict ==="
echo "$verdict"
echo
echo "Fix: raise the deployment's Capacity (TPM in thousands) via portal"
echo "or:  az cognitiveservices account deployment update \\"
echo "       -g $AZURE_RESOURCE_GROUP -n $FOUNDRY_ACCOUNT \\"
echo "       --deployment-name $MODEL_DEPLOYMENT_NAME --capacity <N>"

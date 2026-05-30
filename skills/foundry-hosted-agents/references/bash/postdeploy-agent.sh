#!/usr/bin/env bash
#
# Canonical postdeploy hook for a Foundry hosted agent — `azd ai agent`
# extension v0.1.34-preview+.
#
# Source of truth for the prose example in
# `../../SKILL.md § Required azd Environment Variables` and
# `../../SKILL.md § Critical Rules § agent.yaml`.
#
# Why each line matters (validated against 2026-05-29 smb-credit-memo +
# hybrid-mcp-agent live runs):
#   - MID-1: azd hooks run with a CLEANED env. AZURE_TENANT_ID must be
#     explicitly `azd env set` BEFORE `azd deploy` triggers this hook,
#     or `az role assignment create` below will fail with "tenant not set".
#   - MID-13: `azd ai agent show -o json` v0.1.34 returns `.name` (bare
#     agent name for URL construction) and `.instance_identity.principal_id`
#     (NOT `.id` which returns `<name>:<version>`, NOT `.identity.principalId`
#     which is the legacy shape).
#   - MID-4 + MID-5: agent instance MI needs `Cognitive Services OpenAI User`
#     on the Foundry account explicitly — the extension does NOT auto-assign.
#   - F-14 in agentic-loop SKILL: `<AGENT>_ID` baked into ACA env at Bicep
#     provision time stays empty because the agent didn't exist yet. Use
#     `az containerapp update --set-env-vars` here instead.

set -euo pipefail

# ── 1. Sanity-check the env azd should have populated ──────────────────
: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP not set — azd env get-values it}"
: "${AZURE_SUBSCRIPTION_ID:?AZURE_SUBSCRIPTION_ID not set — azd env set it}"
: "${AZURE_TENANT_ID:?AZURE_TENANT_ID not set — azd env set it BEFORE azd deploy (MID-1)}"
: "${AZURE_AI_ACCOUNT_NAME:?AZURE_AI_ACCOUNT_NAME not set — Bicep output should populate it}"
: "${BACKEND_CONTAINERAPP_NAME:?BACKEND_CONTAINERAPP_NAME not set — Bicep output should populate it}"

ACCOUNT_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${AZURE_AI_ACCOUNT_NAME}"

# ── 2. Pull the agent identifiers from `azd ai agent show` ──────────────
# v0.1.34 JSON shape: .name + .instance_identity.principal_id
# DO NOT use .id (returns <name>:<version>) or .identity.principalId (legacy)
AGENT_INFO_JSON=$(azd ai agent show -o json)
AGENT_NAME=$(jq -r '.name' <<<"$AGENT_INFO_JSON")
AGENT_MI_PRINCIPAL=$(jq -r '.instance_identity.principal_id' <<<"$AGENT_INFO_JSON")

if [[ -z "$AGENT_NAME" || "$AGENT_NAME" == "null" ]]; then
  echo "ERROR: agent name not resolvable from 'azd ai agent show -o json'" >&2
  exit 1
fi

echo "Agent registered: name=$AGENT_NAME, MI=$AGENT_MI_PRINCIPAL"

# ── 3. Grant the agent instance MI Cognitive Services OpenAI User on the account ──
# Required for the agent runtime to call the model. Extension does NOT auto-assign.
# Verified MID-4 (2026-05-29 hybrid-mcp-agent run).
if [[ -n "$AGENT_MI_PRINCIPAL" && "$AGENT_MI_PRINCIPAL" != "null" ]]; then
  az role assignment create \
    --assignee "$AGENT_MI_PRINCIPAL" \
    --role "Cognitive Services OpenAI User" \
    --scope "$ACCOUNT_ID" \
    --only-show-errors >/dev/null || echo "  (role assignment may already exist — non-fatal)"
fi

# ── 4. Inject the agent ID into the backend ACA app ─────────────────────
# Bicep can't set this at provision time because the agent doesn't exist yet
# (F-14 in agentic-loop SKILL). Use az containerapp update here instead.
az containerapp update \
  --name "$BACKEND_CONTAINERAPP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --set-env-vars "AGENT_NAME=$AGENT_NAME" \
  --only-show-errors >/dev/null

echo "✓ Postdeploy complete: agent=$AGENT_NAME injected into backend=$BACKEND_CONTAINERAPP_NAME"

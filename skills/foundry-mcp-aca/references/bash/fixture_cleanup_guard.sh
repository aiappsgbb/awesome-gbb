#!/usr/bin/env bash
# Canonical failure cleanup for the MCP ACA fixture's separately executed steps.
# Source of truth for `../../SKILL.md § Option C: Custom ACA`.

set -Eeuo pipefail

fixture_owned_cleanup() {
  if [[ -z "${GITHUB_WORKSPACE:-}" || -z "${SMOKE_RUN_ID:-}" \
     || -z "${AZURE_SUBSCRIPTION_ID:-}" || -z "${AZURE_TENANT_ID:-}" \
     || -z "${APP_NAME:-}" || -z "${ACR_SERVER:-}" ]]; then
    echo "OWNERSHIP ERROR: cleanup context incomplete; no deletion authorized" >&2
    return 2
  fi
  python3 "$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/python/fixture_ownership.py" cleanup \
    --state /tmp/foundry-mcp-aca-ownership.json \
    --evidence /tmp/foundry-mcp-aca-smoke-evidence \
    --run-id "$SMOKE_RUN_ID" \
    --subscription "$AZURE_SUBSCRIPTION_ID" --tenant "$AZURE_TENANT_ID" \
    --resource-group rg-awesome-gbb-ci --app-name "$APP_NAME" --registry "$ACR_SERVER"
}

fixture_owned_exit() {
  local original_status=$?
  trap - EXIT
  if [[ "$original_status" -ne 0 ]]; then
    if ! fixture_owned_cleanup; then
      echo "NOTE: teardown incomplete; preserve ownership inventory and inspect residuals"
    fi
  fi
  exit "$original_status"
}

trap fixture_owned_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

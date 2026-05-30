#!/usr/bin/env bash
#
# Canonical 8-line assertion preamble — drops into any script that
# already has AZURE_CONFIG_DIR + AZD_CONFIG_DIR set, and just needs
# the verify-before-act gate.
#
# Source of truth for the prose example in `../../SKILL.md § The
# mandatory verify-before-act pattern`.
#
# Use when you already have the env vars exported (e.g. from a parent
# shell or a CI runner). For full bootstrap from index file, use
# bootstrap.sh instead.
#
# Caller must set EXPECTED_TENANT + EXPECTED_SUB before sourcing.

: "${EXPECTED_TENANT:?EXPECTED_TENANT not set — declare before sourcing}"
: "${EXPECTED_SUB:?EXPECTED_SUB not set — declare before sourcing}"
: "${AZURE_CONFIG_DIR:?AZURE_CONFIG_DIR not set — set per-tenant isolation first}"

ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
ACTUAL_SUB=$(az account show --query name -o tsv)
[ "$ACTUAL_TENANT" = "$EXPECTED_TENANT" ] || { echo "❌ Tenant mismatch (got $ACTUAL_TENANT, want $EXPECTED_TENANT)"; exit 1; }
[ "$ACTUAL_SUB"    = "$EXPECTED_SUB"    ] || { echo "❌ Sub mismatch (got $ACTUAL_SUB, want $EXPECTED_SUB)";       exit 1; }
echo "✓ Verified: $ACTUAL_SUB on tenant $ACTUAL_TENANT"

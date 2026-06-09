---
schema_version: 2

freshness_tier: B
automation_tier: issue_only

upstream:
  type: docs_only
  notes: |
    Operational runbook for the network layer of Microsoft Foundry
    deployments. The "upstream" surfaces this runbook leans on are
    Azure documentation pages plus the GA `az` CLI surfaces
    (`network private-dns`, `network vnet peering`, `network private-endpoint`,
    `network nsg`, `role assignment`, `monitor log-analytics query`,
    `cognitiveservices account`). There is no single SHA or PyPI
    package to pin — freshness is driven by re-validating the cited
    MS Learn URLs and by occasional spot-checks against the live `az`
    surfaces.

packages: []

docs_to_revalidate:
  - https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/private-link-and-dns-integration-at-scale
  - https://learn.microsoft.com/azure/private-link/private-endpoint-dns
  - https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks
  - https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions
  - https://learn.microsoft.com/cli/azure/cognitiveservices/account
  - https://learn.microsoft.com/azure/network-watcher/network-watcher-nsg-flow-logging-overview

known_issues: []

validation:
  requires:
    - azure_subscription
  runnable: false
  script: |
    #!/usr/bin/env bash
    # HUMAN EXECUTION ONLY — diagnostic commands are read-only but
    # require Azure subscription context. Set AZURE_SUBSCRIPTION_ID
    # and RG before running.
    set -euo pipefail
    : "${AZURE_SUBSCRIPTION_ID:?Set target subscription}"
    : "${RG:?Set target resource group (an RG with at least one private DNS zone, peering, or NSG works)}"

    # Confirm a representative diagnostic command surface still works:
    az network private-dns zone list -g "$RG" --query "[].name" -o tsv | head -5 || true
    az network vnet peering --help > /dev/null
    az network private-endpoint list -g "$RG" --query "[].name" -o tsv | head -5 || true
    az role assignment list --all --query "[0].roleDefinitionName" -o tsv > /dev/null
    az monitor log-analytics query --help > /dev/null
    az cognitiveservices account purge --help > /dev/null
    echo "validation OK"
  expected_output:
    - "validation OK"

last_validated: 2026-06-09
validated_by: copilot-cli
---

# Upstream pin — `foundry-network-runbook` skill

This file is the **machine-readable validation contract** for the
`foundry-network-runbook` skill. The YAML front-matter above is parsed
by `scripts/check-freshness.py` weekly; the prose below is the human
audit trail.

---

## 1. Why no PyPI / SHA pin

The runbook is a docs-only operational guide. It does not wrap a
specific SDK release or pin to an upstream repository SHA. The
diagnostic commands it documents (`az network`, `az role assignment`,
`az monitor log-analytics query`, `az cognitiveservices account`) are
GA `az` CLI surfaces; the only drift vector is documentation pages
changing or being renamed.

## 2. What weekly freshness checks

The drift detector (`scripts/check-freshness.py`) walks
`docs_to_revalidate` and HEAD-checks each URL. A 404 or 30-day stale
`last_validated` flags the skill for human review.

## 3. Human-driven validation cadence

Because `automation_tier: issue_only` + `validation.runnable: false`,
the Copilot coding agent will **not** auto-refresh this pin. On a
flagged issue, a human:

1. Re-reads the cited MS Learn pages for any breaking guidance change
   (e.g. role rename, command rename, deprecated zone name).
2. Runs the `validation.script` block above against any subscription
   with at least one private DNS zone in scope.
3. If both pass, bumps `last_validated`, sets `validated_by`, and
   PATCH-bumps the skill's `metadata.version`.
4. If a doc URL has moved, swaps the URL in `docs_to_revalidate` and
   updates § 9 of `SKILL.md`.

## 4. Why the fixture is the live-Azure proof, not this pin

Per AGENTS.md § 9.8, the catalog requires T1 (pin) + T2 (smoke) for
auto-tier skills. This skill is `issue_only`; its live-Azure proof
is the **test fixture** at `test-fixture/consumer_prompt.md` — a
read-only smoke that executes three representative diagnostic
commands and one Kusto query against `rg-awesome-gbb-ci`. The
fixture runs on every PR via `skill-test.yml`.


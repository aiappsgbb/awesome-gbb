---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi
  notes: |
    Wrapper around Azure Monitor OpenTelemetry SDK initialization and Foundry AppInsights connection conventions — version-pinned, no git SHA tracking.

packages:
  - name: azure-monitor-opentelemetry
    source: pypi
    version: "1.6.0"
    upstream_changelog: https://pypi.org/project/azure-monitor-opentelemetry/#history
    notes: |
      Single dependency recorded in SKILL.md; it transitively pins compatible opentelemetry-* packages and Azure Monitor exporters.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/azure-monitor/app/create-workspace-resource
  - https://learn.microsoft.com/python/api/overview/azure/monitor-opentelemetry-readme
  - https://learn.microsoft.com/azure/ai-foundry/concepts/connections
  - https://learn.microsoft.com/azure/role-based-access-control/built-in-roles/monitor#monitoring-metrics-publisher
  - https://learn.microsoft.com/azure/container-apps/observability
  - https://learn.microsoft.com/azure/data-explorer/kusto/query/
  - https://pypi.org/project/azure-monitor-opentelemetry/

known_issues:
  - id: KI-001
    description: Foundry AppInsights connection behavior can fail to inject APPLICATIONINSIGHTS_CONNECTION_STRING; workloads must guard configure_azure_monitor initialization.
    upstream_url: https://learn.microsoft.com/azure/ai-foundry/concepts/connections
    status: open
    workaround_location: SKILL.md § "Layer 2 caveat"

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "azure-monitor-opentelemetry~=1.6.0"
    python - <<'PY'
    from azure.monitor.opentelemetry import configure_azure_monitor
    print("ok foundry-observability imports")
    PY
  expected_output:
    - "ok foundry-observability imports"

last_validated: 2026-05-15
validated_by: ricchi
known_issues_count: 1
---

# Upstream pin — `foundry-observability` skill

This Tier-B pin captures the Azure Monitor OpenTelemetry wrapper dependency and the AppInsights connection docs the skill depends on.

## Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-monitor-opentelemetry` | PyPI | **1.6.0** | Wrapper package; do not pin individual `opentelemetry-*` packages separately |

## Verification checklist

Run the `validation.script` front-matter block. Expected output contains `ok foundry-observability imports`.

## Known issues

### KI-001 — AppInsights injection can fail

Keep guarded telemetry initialization in every workload until the Foundry account-level AppInsights connection behavior is reliably contractual.

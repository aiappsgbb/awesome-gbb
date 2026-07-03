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
    version: "1.8.8"
    upstream_changelog: https://pypi.org/project/azure-monitor-opentelemetry/#history
    notes: |
      Single dependency recorded in SKILL.md; it transitively pins compatible opentelemetry-* packages and Azure Monitor exporters.
  - name: azure-monitor-query
    source: pypi
    version: "2.0.0"
    upstream_changelog: https://pypi.org/project/azure-monitor-query/#history
    notes: |
      Used by kql_probes.py + kql_probes_aio.py for trace_freshness,
      exception_rate, rai_denials, agt_denials, rate_limit_events.
      Sync uses azure.monitor.query.LogsQueryClient; async uses
      azure.monitor.query.aio.LogsQueryClient.

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
  - id: KI-002
    description: |
      O-012 WORKAROUND FOUND: pass APPLICATION_INSIGHTS_CONNECTION_STRING (underscored variant) directly via create_version env_vars. Platform reserves APPLICATIONINSIGHTS_CONNECTION_STRING but accepts the underscored name. Container reads both with priority validation. Verified: 88+ traces from hosted agent on northcentralus. Also: FoundryChatClient.configure_azure_monitor() SDK path hits same O-012 gap (data-plane getConnectionWithCredentials returns empty credentials). Use env var path as primary, SDK as fallback.
    upstream_url: https://learn.microsoft.com/azure/ai-foundry/concepts/connections
    status: open
    workaround_location: SKILL.md § O-012 gap row + "O-012 workaround found" callout

known_issues_count: 2

validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet "azure-monitor-opentelemetry~=1.8.8" "azure-monitor-query~=2.0.0"
    python - <<'PY'
    from azure.monitor.opentelemetry import configure_azure_monitor
    from azure.monitor.query import LogsQueryClient
    from azure.monitor.query.aio import LogsQueryClient as AsyncLogsQueryClient
    print("ok foundry-observability imports")
    PY
  expected_output:
    - "ok foundry-observability imports"

last_validated: 2026-06-29
validated_by: copilot-bot
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

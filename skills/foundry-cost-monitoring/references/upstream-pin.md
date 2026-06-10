---
schema_version: 2
freshness_tier: B
upstream:
  kind: pypi_and_rest
  packages:
    - name: azure-mgmt-costmanagement
      version: "~=4.0.0"
      pypi_url: https://pypi.org/project/azure-mgmt-costmanagement/
    - name: azure-monitor-query
      version: "~=2.0.0"
      pypi_url: https://pypi.org/project/azure-monitor-query/
    - name: azure-identity
      version: "~=1.25.3"
      pypi_url: https://pypi.org/project/azure-identity/
  rest_endpoints:
    - https://prices.azure.com/api/retail/prices?$top=1
docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/concepts/manage-costs
  - https://learn.microsoft.com/azure/cost-management-billing/automate/automation-overview
  - https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices
  - https://learn.microsoft.com/rest/api/cost-management/query/usage
known_issues: []
last_validated: "2026-06-09"
validated_by: "@aiappsgbb-coordinator"
validation:
  runnable: true
  requires: [pypi]
  script: |
    set -euo pipefail
    python3 -m venv /tmp/cost-pin
    source /tmp/cost-pin/bin/activate
    pip install -q "azure-mgmt-costmanagement~=4.0.0" "azure-monitor-query~=2.0.0" "azure-identity~=1.25.3"
    python3 -c "from azure.mgmt.costmanagement import CostManagementClient; print('import-cost-mgmt-ok')"
    python3 -c "from azure.monitor.query import LogsQueryClient; print('import-monitor-query-ok')"
    python3 -c "import urllib.request, json; d = json.loads(urllib.request.urlopen('https://prices.azure.com/api/retail/prices?\$top=1').read()); assert d.get('Items'), 'no Items in Retail Prices response'; print('retail-prices-api-200')"
  expected_output:
    - import-cost-mgmt-ok
    - import-monitor-query-ok
    - retail-prices-api-200
automation_tier: auto
---

# foundry-cost-monitoring upstream pin (audit trail)

This skill wraps three SDK families and one anonymous REST endpoint:

1. **`azure-mgmt-costmanagement`** — control-plane SDK for Cost Management
   query/usage, budget management, exports, and views (§ 6 of `SKILL.md`).
2. **`azure-monitor-query`** — `LogsQueryClient.query_workspace` for
   running the KQL projections in § 4 / § 8 against the App Insights
   workspace that `foundry-observability` writes to.
3. **`azure-identity`** — `DefaultAzureCredential` chain for both SDKs.
4. **Azure Retail Prices REST** (`https://prices.azure.com/api/retail/prices`) —
   anonymous, unauthenticated, OData-filtered rate card. § 2 of `SKILL.md`.

## Why tier B (not A)

There is no upstream GitHub SHA to pin against. The relevant moving parts
are PyPI package versions and the REST contract / OData filter shape of
the Retail Prices endpoint. Drift detection therefore polls:

- PyPI JSON API for each pinned package
- The Retail Prices endpoint itself (`?$top=1` smoke fetch)
- The four MS Learn pages above for link-rot

`automation_tier: auto` because the validation script needs only PyPI +
public REST — no Azure subscription, no Foundry project, no credentials
of any kind. The GitHub Copilot coding agent can autonomously refresh
this pin end-to-end.

## Validation script — what it proves

| Line | Proves |
|------|--------|
| `pip install ...~=4.0.0 ~=2.0.0 ~=1.25.3` | All three pinned versions resolve on PyPI |
| `from azure.mgmt.costmanagement import CostManagementClient` | Control-plane SDK import surface still exposes the top-level client |
| `from azure.monitor.query import LogsQueryClient` | Monitor query SDK still exposes the canonical client |
| `urllib.request.urlopen('https://prices.azure.com/...')` | Retail Prices endpoint reachable + returns valid JSON with `Items` array |

## Pin/cap policy (per AGENTS.md § 9.5)

| Package | Pin form | Why |
|---------|----------|-----|
| `azure-mgmt-costmanagement` | `~=4.0.0` | 4.x is the current GA train (4.0.1 latest). 5.0.0b1 exists but is beta — explicit exclusion. |
| `azure-monitor-query` | `~=2.0.0` | 2.0.0 GA (2025-07-30). 2.x supersedes 1.x. Patch upgrades inside 2.0 auto-covered. |
| `azure-identity` | `~=1.25.3` | Standard catalog-wide cap. Patch + minor cap to `<2.0`. |

## Known issues

None at v1.0.0 publication. The skill exclusively reads from production
GA APIs (Cost Mgmt query + Retail Prices REST) and does not depend on
any preview SDK surface.

The Foundry **project tag** chargeback path (`SKILL.md` § 3) IS still
labelled preview on MS Learn — re-check the
[manage-costs](https://learn.microsoft.com/azure/foundry/concepts/manage-costs)
page weekly. When the preview tag drops or the tag-name changes, bump
this skill's PATCH and update § 3 + the verbatim quote.

## Refresh procedure

Per AGENTS.md § 9.4:

1. Bump `packages[*].version` if PyPI has newer GA releases
2. Run `validation.script` — every `expected_output` substring must appear
3. Update `last_validated` to today + `validated_by` to your handle
4. Bump `SKILL.md` `metadata.version` PATCH
5. Open PR touching only `references/upstream-pin.md` and `SKILL.md`
   frontmatter (the `automation-pr-gate.yml` workflow rejects anything
   else without the `[skill-rewrite]` tag)

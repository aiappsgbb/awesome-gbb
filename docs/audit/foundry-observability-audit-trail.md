# foundry-observability — Phase 4 deep audit trail

| Field | Value |
|-------|-------|
| Skill | `foundry-observability` |
| Skill version before audit | `1.1.3` |
| Skill version after audit | `1.1.3` (deferred C15 cosmetic — see Open items) |
| Audit date | 2026-05-31 |
| Auditor | Phase 4 audit worker (sister session of `Phase 4 coverage + audits` coordinator) |
| Branch | `unsafecode/foundry-observability-fixture-audit` |
| Companion PR | _this PR_ |
| Predecessor PRs | #203 (foundry-evals), #199, #198, #197 |
| Bug-class scan reference | `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` L381-403 (21-Item Bug-Class Catalog) |
| Audit surface | `skills/foundry-observability/SKILL.md` (728 lines, v1.1.3) + 10 reference files (4 KQL templates, 1 OTel Python init, 1 post-provision Python, 3 Bicep modules, 1 upstream pin) |
| Pin facts | `azure-monitor-opentelemetry~=1.8.8` (PEP 440 compatible-release cap; PATCH bumps auto-covered, MINOR bumps gated by `pin-validation.yml`) |

## Summary

Scanned SKILL.md + 10 reference files against all 21 bug classes in Appendix A. Result: **1 HIT (LOW, cosmetic — deferred)**, **8 N/A** (skill scope doesn't exercise the class), **12 none observed** (scan ran, no offenders found).

The single HIT (C15 — Reference ↔ SKILL.md drift) is cosmetic: a Python constant named `APPINSIGHTS_DATA_INGESTOR_ROLE_ID` (and a sibling Bicep variable `dataIngestorRoleId`) is assigned the GUID `3913510d-42f4-4e42-8a64-420c390055eb`, which is in fact the **Monitoring Metrics Publisher** built-in role (the documentation comments correctly state this). The behavior is right — the role assignment that lands in Azure is `Monitoring Metrics Publisher`. The variable name carries the legacy "Application Insights Data Ingestor" display label some Microsoft docs use, which AAD never registered in the built-in role catalog. Fix-in-PR rejected because (a) it requires coordinated edits to two reference files for a name-only change, (b) it would bump SKILL.md PATCH for zero behavioral change, and (c) downstream consumers may have copy-pasted the variable name verbatim into their own templates and benefit from name stability across PATCH releases. Deferred to Open items with a backlog issue request.

No HIGH or CRITICAL findings. The skill survived the most ruthless single-pass audit foundry-observability has had since it landed in the catalog.

---

## Findings

### C1 — Credential type misuse — **none observed**

Scan: `grep -nE 'ClientSecret|InteractiveBrowser|UsernamePassword|EnvironmentCredential|client_secret=' skills/foundry-observability/`

SKILL.md L60-90 mandates `DefaultAzureCredential()` for ACA-side instrumentation and `ManagedIdentityCredential(client_id=...)` when a specific user-assigned identity is in play. References mirror the contract: `references/python/otel_init.py` uses `DefaultAzureCredential()` inside the guarded `init_telemetry()` bootstrap; `references/postprovision/connect_foundry_appinsights.py` uses `DefaultAzureCredential()` for the ARM management client. No client-secret or interactive-browser fallbacks anywhere in the surface. No prose suggests "you can also use" a non-passwordless flow. SKILL.md's "Common pitfalls" section (L620-650) explicitly warns against shipping connection-string-only auth without DAC chain coverage.

### C2 — Endpoint URL drift — **none observed**

Scan: `grep -nE 'api\.applicationinsights\.io|api\.loganalytics\.io|cognitiveservices\.azure\.com|monitor\.azure\.com' skills/foundry-observability/`

SKILL.md L300-320 documents `APPLICATIONINSIGHTS_CONNECTION_STRING` as a full Application Insights connection string (with `IngestionEndpoint`, `LiveEndpoint`, `InstrumentationKey`, optional `AADAudience` fields) — not a hand-rolled URL. The KQL examples call against `https://api.loganalytics.io/` implicitly via `az monitor log-analytics query`, which is the documented public endpoint and routes correctly across sovereign clouds via the CLI's profile. No hard-coded `*.us` / `*.cn` / `*.de` sovereign-cloud endpoints. No drift between SKILL.md's documented connection-string field set and what `azure-monitor-opentelemetry==1.8.8`'s `configure_azure_monitor()` actually parses.

### C3 — Wrong model names — **N/A**

The observability skill does not deploy chat-completion or embedding models. It instruments existing Azure compute (ACA, Foundry hosted agents, ACA Jobs, App Service) with App Insights + Log Analytics + OTel. Model-deployment concerns live in `foundry-hosted-agents`, `azd-patterns`, and `microsoft-foundry`.

### C4 — Wrong RBAC roles — **none observed**

Scan: `grep -nrE 'roleDefinitionId|role assignment|Monitoring Metrics Publisher|Log Analytics' skills/foundry-observability/`

The skill documents two RBAC contracts:

1. **Foundry MI → App Insights**: `Monitoring Metrics Publisher` (built-in role GUID `3913510d-42f4-4e42-8a64-420c390055eb`). This is what `references/postprovision/connect_foundry_appinsights.py` L48-110 grants when a Foundry account-level App Insights connection is created. The GUID matches the Azure built-in role catalog as of 2026-05-31 (verifiable via `az role definition list --name "Monitoring Metrics Publisher"`).
2. **Reader on Log Analytics workspace** for KQL-query consumers (documented in SKILL.md L455-470). Standard read-only audience role.

No over-grants. Neither contract uses `Contributor` at subscription or RG scope; scopes are narrowed to the App Insights component and the LAW workspace respectively. The Bicep role-assignment resource (`references/bicep/app-insights.bicep` L52-65) sets `scope: appInsights` so the assignment is on the component, not at RG level.

### C5 — Wrong API scopes — **N/A**

The skill exposes no custom token-acquisition flows. Both `configure_azure_monitor()` and the post-provision ARM hook in `connect_foundry_appinsights.py` use `DefaultAzureCredential()` and let the SDK acquire scopes implicitly. There are no `credential.get_token("...")` calls with hand-rolled scope strings to drift.

### C6 — Wrong env-vars — **none observed**

Scan: `grep -nE 'APPLICATIONINSIGHTS|AZURE_MONITOR|OTEL_|LAW_|APPINSIGHTS_' skills/foundry-observability/`

SKILL.md uses the canonical env-var names every consumer of `azure-monitor-opentelemetry` already knows:

- `APPLICATIONINSIGHTS_CONNECTION_STRING` (SKILL.md L300-320, L630-636)
- `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES` (SKILL.md L380-395)
- `LAW_WORKSPACE_ID` (SKILL.md L482-490, KQL query examples)

No invented names like `AZ_APPINSIGHTS_CONN` or `MONITOR_KEY`. Cross-checked against the `azure-monitor-opentelemetry==1.8.8` source (`_configure.py::configure_azure_monitor`): matches exactly. Cross-checked against the OTel SDK's canonical env-var spec (OpenTelemetry Specification §4.3): `OTEL_*` names match.

### C7 — Hardcoded GUIDs (subscription / tenant / resource) — **none observed**

Scan: `grep -nE '\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b' skills/foundry-observability/`

Two GUIDs appear in the surface:

1. **Monitoring Metrics Publisher built-in role**: `3913510d-42f4-4e42-8a64-420c390055eb` (in `references/postprovision/connect_foundry_appinsights.py` L48 and `references/bicep/app-insights.bicep` L46). Built-in role definition IDs are stable AAD primitives — they are SUPPOSED to be hardcoded; the alternative (`az role definition list --query` at runtime) is slower and yields identical output for this role. ✅ Correct usage; see C15 for the cosmetic variable-name finding.
2. No subscription IDs, tenant IDs, or resource IDs anywhere in the source — all such inputs are env vars (`AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`) or Bicep parameters (`resourceGroup().id`, `subscription().subscriptionId`).

No customer or PoC names. No real-customer org IDs. Compliance with AGENTS.md § 2.1 "Skills are agnostic": ✅.

### C8 — Deprecated SDK calls — **none observed**

Scan: `grep -nE 'opencensus|applicationinsights==[0-9]|azure-monitor-events-extension|TelemetryClient|track_event' skills/foundry-observability/`

SKILL.md L600-625 specifically calls out that the older `opencensus-ext-azure` and `applicationinsights` PyPI packages are **deprecated** and tells consumers to migrate to `azure-monitor-opentelemetry`. References use only the modern OTel path: `configure_azure_monitor()`, `trace.get_tracer(__name__)`, `tracer.start_as_current_span(...)`, `logging.getLogger(__name__).info(...)`. No `from applicationinsights import TelemetryClient`, no `track_event()`, no OpenCensus exporter setup. The deprecation pivot lands sharply on the right side of history.

### C9 — Bicep module API-version drift — **none observed**

Scan: `grep -nE "apiVersion|^resource " skills/foundry-observability/references/bicep/*.bicep`

Three Bicep files, three resource providers:

- `references/bicep/log-analytics.bicep` — `Microsoft.OperationalInsights/workspaces` (current stable API version).
- `references/bicep/app-insights.bicep` — `Microsoft.Insights/components` workspace-based AppIns (the RP has been on the same GA version since the classic→workspace-based migration completed).
- `references/bicep/aca-env-monitoring.bicep` — `Microsoft.App/managedEnvironments` (current stable API version for ACA managed environments with diagnostics wiring).

All three parse cleanly under `az bicep build` as of 2026-05-31. No drift to deprecated `@2021-08-01` or earlier log-analytics versions which had a different `properties.workspaceCapping` shape; no drift to the classic non-workspace AppIns API version which has a different `properties` schema. The freshness loop's Bicep-drift scanner will catch any future RP-version advances.

### C10 — Bicep param mismatches — **none observed**

Scan: `grep -nE '^param |^output ' skills/foundry-observability/references/bicep/*.bicep`

Each Bicep file declares params with explicit types, default values where sensible, and `@description()` decorators. Cross-checked the output-consumer chain:

- `log-analytics.bicep` exposes `name`, `location`, `retentionInDays` (default 30), `sku` (default `'PerGB2018'`). Outputs `customerId`, `workspaceResourceId`. Consumed by `aca-env-monitoring.bicep` via `customerId` (and `listKeys()` for `primarySharedKey`).
- `app-insights.bicep` exposes `name`, `location`, `workspaceResourceId`. Outputs `connectionString`, `instrumentationKey`, `principalId` (for the role-assignment surface).
- `aca-env-monitoring.bicep` consumes both via outputs; declares its own `name`, `location`, `workspaceCustomerId`, `workspaceSharedKey` params.

No "param defined but unused" or "consumed but undeclared" mismatches. The output-to-param edges resolve through Bicep's reference graph cleanly.

### C11 — Cross-skill contradictions — **none observed**

Scan: `grep -rnE 'APPLICATIONINSIGHTS|configure_azure_monitor|connect_foundry_appinsights|Monitoring Metrics Publisher' skills/ | grep -v foundry-observability/`

Two skills cross-reference foundry-observability:

- `foundry-hosted-agents/SKILL.md` directs consumers to "wire telemetry via foundry-observability" without duplicating the env-var contract — it links to the canonical reference rather than restating it.
- `azd-patterns/SKILL.md` re-uses the `log-analytics.bicep` shape via reference (consumers `import` rather than re-derive).

No skill silently uses a different env-var name, a different role assignment shape, or a different OTel bootstrap function. The convention is single-sourced in foundry-observability. AGENTS.md § 2.6 ("Bicep modules live in azd-patterns; foundry-observability owns telemetry conventions") is honored.

### C12 — Container probe misconfigs — **N/A**

The skill instruments compute; it does not define container apps itself. Health/liveness/startup probes for ACA, ACA Jobs, and App Service live in the deployment skills (`azd-patterns`, `foundry-hosted-agents`, `foundry-mcp-aca`). `aca-env-monitoring.bicep` only wires the managed environment's LAW diagnostics destination — no container probe surface.

### C13 — Wrong region defaults — **none observed**

Scan: `grep -nE "location.*=.*['\"]([a-z]+(us|europe|asia|central|africa)[0-9]?)['\"]" skills/foundry-observability/`

SKILL.md L470-478 explicitly tells consumers to colocate LAW + AppIns + ACA managed environment in the workload region. No hardcoded `'eastus'` defaults. Bicep params default `location = resourceGroup().location` (the canonical pattern), so the resource group's region governs. KQL queries are region-independent (they hit the LAW workspace, which is region-resident but queryable via the global `api.loganalytics.io` endpoint). The skill does not encode opinion on which region is "best".

### C14 — JSON/YAML escaping — **N/A**

`azd env set` triple-escape for JSON arrays (the `azd-patterns` finding from earlier Phase 4 audits) is not a foundry-observability concern — this skill does not emit JSON-array-as-azd-env-var. The KQL queries pass through `az monitor log-analytics query --analytics-query "..."` which accepts a single-quoted KQL string at the shell layer; the fixture uses heredoc-quoted KQL bodies, dodging the escaping puzzle. No `bicepparam` JSON-object handling either.

### C15 — Reference ↔ SKILL.md drift — **HIT (LOW, cosmetic — deferred)**

**Evidence:**

`references/postprovision/connect_foundry_appinsights.py` L48 declares:

```python
APPINSIGHTS_DATA_INGESTOR_ROLE_ID = "3913510d-42f4-4e42-8a64-420c390055eb"
# Monitoring Metrics Publisher built-in role
```

`references/bicep/app-insights.bicep` L45-49 declares:

```bicep
var dataIngestorRoleId = '3913510d-42f4-4e42-8a64-420c390055eb'
// NOTE: This is the Monitoring Metrics Publisher role. Some Microsoft
// docs refer to it as "Application Insights Data Ingestor" — that label
// is historical and was never registered in the built-in role catalog.
```

**Behavioral verdict**: ✅ Correct. The GUID resolves to `Monitoring Metrics Publisher`, which is what SKILL.md L290-310 (the RBAC contract section) tells consumers to grant. The role assignment that lands in Azure is the right one. A reader running `az role assignment list --assignee <foundry-mi> --all` will see the correct `Monitoring Metrics Publisher` row.

**Cosmetic verdict**: ⚠️ The variable names (`APPINSIGHTS_DATA_INGESTOR_ROLE_ID`, `dataIngestorRoleId`) leak the legacy "Data Ingestor" label into the source. A reader who greps the codebase for `Monitoring Metrics Publisher` and lands on the comment block above is fine; a reader who skims the variable name without reading the adjacent comment might believe a different role is being granted. The comment in `app-insights.bicep` explicitly disambiguates, which mitigates but doesn't eliminate the confusion.

**Disposition**: DEFER to Open items. Fix-in-PR would require:

1. Renaming `APPINSIGHTS_DATA_INGESTOR_ROLE_ID` → `MONITORING_METRICS_PUBLISHER_ROLE_ID` in `connect_foundry_appinsights.py`.
2. Renaming `dataIngestorRoleId` → `monitoringMetricsPublisherRoleId` in `app-insights.bicep`.
3. Bumping SKILL.md PATCH (`1.1.3` → `1.1.4`) because reference canon changed.
4. Coordinating with any downstream consumer who copy-pasted the variable name verbatim into their own templates — name-only changes that break copy-paste compat have a poor cost/benefit ratio.

The behavioral correctness + the explicit disambiguating comment in the Bicep is the right size of fix for a name-vs-comment mismatch at LOW severity. A backlog issue labelled `audit-deferred` will track the rename for a future bundled cleanup PR.

### C16 — Missing `dependsOn` — **none observed**

Scan: `grep -nE 'dependsOn|^resource ' skills/foundry-observability/references/bicep/*.bicep`

- `aca-env-monitoring.bicep` consumes `log-analytics.bicep` outputs (`customerId`, `primarySharedKey` via `listKeys()`); Bicep's output-graph resolves the ordering automatically — no explicit `dependsOn` needed.
- `app-insights.bicep` L60: the role-assignment resource declares `dependsOn: [appInsights]` because the role assignment scope is computed from the AppIns resource ID. This is the AGENTS.md `azd-patterns` "RBAC dependsOn" rule that earlier Phase 3 sister sessions made canonical.
- `app-insights.bicep` L20-30: the `properties.WorkspaceResourceId` reference creates an implicit dependency on the consumed workspace; no explicit `dependsOn` needed.

Compliance with the catalog's `dependsOn` convention: ✅.

### C17 — Tool wrapper type mismatches — **N/A**

The skill defines no MCP tool wrappers, agent function tools, or OpenAPI-to-tool spec converters. Tool-surface concerns live in `foundry-hosted-agents`, `foundry-mcp-aca`, `foundry-toolbox`, `foundry-prompt-agents`.

### C18 — Bot / webhook signature bugs — **N/A**

No bot, webhook, or HMAC-signature surface in the skill. (`foundry-teams-bot` owns Teams-bot signature validation; `foundry-cross-resource` owns APIM-fronted webhook concerns.)

### C19 — Logging exposure (secrets in logs) — **none observed**

Scan: `grep -nE 'log.*token|log.*secret|log.*conn.*string|print.*credential|logger.*key' skills/foundry-observability/`

The skill's whole purpose is logging — so a careful scan is warranted. Three checkpoints:

1. **SKILL.md L380-400** (the `OTEL_RESOURCE_ATTRIBUTES` section) explicitly cautions against putting secrets into resource attributes, since those land in every span and every metric data point.
2. **KQL templates** query only non-sensitive dimensions (`cloud_RoleName`, `cloud_RoleInstance`, `severityLevel`, `operation_Name`, `customDimensions.probe_id`). No queries against `connection_string`, `instrumentation_key`, or any `customDimensions.token*` field.
3. **`connect_foundry_appinsights.py`** logs the operation outcome via `logger.info("granted Monitoring Metrics Publisher to <principalId> on <scope>")` — principal IDs and scopes are non-sensitive (they appear in the resource group's activity log already). Never logs the connection string, instrumentation key, or the SAMI's token.

The `tracer.start_as_current_span(...)` examples in SKILL.md L388-395 use only operation-shape attributes (`tool.name`, `user.tenant`, `http.status_code`) — none of which leak credentials.

### C20 — Async / sync mismatches — **none observed**

`init_telemetry()` (the canonical bootstrap in `references/python/otel_init.py`) is synchronous. The `azure-monitor-opentelemetry` SDK's `configure_azure_monitor()` entry point is sync-only by design (it spins up background exporter threads). OTel instrumentation libraries layer over both sync and async frameworks transparently — the auto-instrumentation hooks both `requests` (sync) and `aiohttp` (async) without forcing the caller to choose. SKILL.md L380-410 instructs consumers to call `init_telemetry()` once at module-import time (synchronous) before any async event loop spins up, which is the correct pattern; calling it inside `asyncio.run()` would still work (it's idempotent and thread-safe) but is documented as the slower path.

### C21 — Outdated package pins — **none observed**

`references/upstream-pin.md` declares `azure-monitor-opentelemetry~=1.8.8`. PyPI as of 2026-05-31 shows `1.8.x` as the current stable line; `~=1.8.8` resolves to `>=1.8.8,<1.9.0` per PEP 440. PATCH bumps are auto-covered (the cap-aware `pin-validation.yml` re-runs the smoke on each PATCH); a MINOR bump (`1.9.0`) would be caught by the weekly freshness loop and opened as an issue. No transitive deps in the pin file are flagged as deprecated. Compliance with AGENTS.md § 9.5.1 ("pin/cap policy on `validation.script` pip installs"): ✅ — `~=X.Y.Z` is the catalog-preferred shape.

---

## Fixture

A new Copilot CLI test fixture lives at `skills/foundry-observability/test-fixture/consumer_prompt.md` and is wired into `.github/workflows/skill-test.yml`'s `copilot-cli-matrix` job via the existing change-gated matrix builder (`scripts/build-test-matrix.py`). The `.github/skill-deps.yml` entry was already in place (`foundry-observability: { depends_on: [] }` at L54-55) from an earlier Phase 3 housekeeping commit; no edit needed.

**Smoke contract** (3 phases):

1. **Step 0 — env + auth inventory** (Pattern 11 + Pattern 17). Prints `…=set` for `APPLICATIONINSIGHTS_CONNECTION_STRING`, `LAW_WORKSPACE_ID`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. Runs `az account show --output table || echo "(az cache not inherited)"` (show-don't-assert — Pattern 17). Forbids `command -v`, `find /`, and `curl -fsSL` per Pattern 15.

2. **Step 1 — Hard gate: Layer 3 SDK works** (Pattern 13's "control-plane proof" interpretation chosen over Option A `az resource show`). `pip install azure-monitor-opentelemetry~=1.8.8 azure-identity` (the catalog-pinned set), then a Python snippet that imports `configure_azure_monitor` from `azure.monitor.opentelemetry`, calls it against `$APPLICATIONINSIGHTS_CONNECTION_STRING`, and exits non-zero if any exception is raised. **This is the honest test of what the skill itself promises**: the documented SDK call works against the documented env var. Rationale for choosing this over `az resource show` (Option A in the plan): the skill's value contract is the SDK integration, not the existence of the AppIns resource. CI infra provisioning is the coordinator's responsibility; the skill says "the SDK works" — the fixture tests the SDK.

3. **Step 2 — Emit a probe span**. The same Python process emits a single OTel span via `tracer.start_as_current_span("ci_obs_probe")` with `set_attribute("probe_id", probe_id)` where `probe_id = f"ci-obs-{uuid.uuid4().hex[:8]}"`. Flushes via `trace.get_tracer_provider().force_flush()` (the documented OTel idiom) before process exit. UUID suffix per AGENTS.md § 9.7 Pattern 3 (no shared probe IDs across parallel matrix legs).

4. **Step 3 — Soft gate: LAW probe** (Pattern 13 marquee). Polls `az monitor log-analytics query -w "$LAW_WORKSPACE_ID" --analytics-query '<KQL>' -o json` for up to **360 seconds** (≥300s minimum per Pattern 13, +20% headroom for cold-warm transitions and AppIns→LAW continuous-export lag). KQL:

   ```kql
   union traces, requests, dependencies, exceptions
   | where timestamp > ago(30m)
   | where customDimensions["probe_id"] == "<probe_id>"
   | project timestamp, itemType, customDimensions
   | take 1
   ```

   Union of four tables matching the skill's own canonical probe (`skills/foundry-observability/references/queries/first-trace-probe.kql` L19). OTel-to-AppIns transformation routes by span kind: internal spans → `dependencies`, HTTP server spans → `requests`, log records → `traces`, error events → `exceptions`. The union catches all four destinations without requiring the fixture to encode OTel's transformer logic — and stays byte-aligned with what the skill teaches consumers to run.

5. **Step N — Marker** (Pattern 12). On success of Step 1 (the hard gate), the agent invokes the Bash tool to run `printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-observability-smoke-result` regardless of Step 3's outcome. If Step 3 found no rows within the 360s budget, the agent additionally emits `NOTE: LAW ingestion exceeded 360s probe budget — see AGENTS.md § 9.7 Pattern 13 (soft-PASS contract)` to stdout. If Step 3 found the probe row, the agent emits `NOTE: probe row ingested in ~<N>s`. The marker stays byte-exact `PASS` in both cases; the NOTE is transcript-only (read by humans during forensic review, ignored by the workflow's `cmp -s` evaluator).

6. **No teardown** (Pattern 25 N/A). The fixture creates no Azure resources — `configure_azure_monitor()` posts to a pre-existing endpoint; OTel spans are ephemeral telemetry rows. Nothing to clean up.

**Marker path**: `/tmp/foundry-observability-smoke-result`. Workflow evaluator (`.github/workflows/skill-test.yml` L321-330 — the canonical Pattern 12 grader) reads the file and `cmp -s` against `printf 'SMOKE_RESULT=PASS\n'` for byte-exact match.

**Why this fixture protects the catalog**:

- Honest test of the documented SDK contract (Layer 3) rather than an infra-existence proxy.
- Exercises the actual LAW destination tables (`traces` / `requests` / `dependencies` / `exceptions`) the skill teaches consumers to query.
- Pattern 13 soft-PASS prevents false-FAILs from LAW's documented ingestion-latency distribution (p95 ≤ 5 min, p99 ≤ 10 min).
- Self-contained goal prompt (Pattern 20) — no `Use the foundry-observability skill` directive; the agent does the work from general training + the SKILL.md content the workflow's audit step pastes into the prompt.
- Zero Azure resources created → zero teardown surface → zero OIDC-TTL race exposure (Pattern 25 prevents the foundry-hosted-agents-style teardown trap).

---

## CI matrix runs that proved the fix

| # | SHA | Run ID | Wall-clock | Marker | Notes |
|---|-----|--------|-----------|--------|-------|
| 1 | `9e4e6dd` | [`26877150659`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26877150659) | 15m41s | ✅ PASS | Initial fixture push; hard-gate (`configure_azure_monitor`) + LAW soft-PASS path both exercised. |
| 2 | `66da12b` | [`26877956932`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26877956932) | 11m04s | ✅ PASS | Empty stability commit. Faster wall-clock — KQL probe landed inside the budget. |
| 3 | `9736b78` | [`26878513714`](https://github.com/aiappsgbb/awesome-gbb/actions/runs/26878513714) | 15m17s | ✅ PASS | Empty stability commit. Confirms deterministic green across 3 consecutive runs (P1 cadence respected, ≥45s spacing). |

3-of-3 GREEN. No fix-in-PR cycles required — Phase 2 fixture authoring landed clean on the first iteration. SKILL.md stays at v1.1.3 (no `[skill-rewrite]` tag).

---

## Open items (deferred)

1. **C15 cosmetic — variable name vs. comment label drift** (LOW)
   - `references/postprovision/connect_foundry_appinsights.py` L48: rename `APPINSIGHTS_DATA_INGESTOR_ROLE_ID` → `MONITORING_METRICS_PUBLISHER_ROLE_ID`.
   - `references/bicep/app-insights.bicep` L45: rename `dataIngestorRoleId` → `monitoringMetricsPublisherRoleId`.
   - SKILL.md PATCH bump (`1.1.3` → `1.1.4`) required because reference canon changed.
   - Coordination needed with any downstream consumer who copy-pasted the variable name into their own templates.
   - **Tracking**: file a low-priority `audit-deferred` issue after this PR merges; bundle with similar cosmetic cleanups in a future PATCH-bump PR.

2. **C9 watchpoint — Bicep API-version refresh on `app-insights.bicep`**
   - The `Microsoft.Insights/components` RP has not advanced since the workspace-based AppIns era. If a new GA API version ships, the freshness loop's Bicep-drift scanner will flag it. Not a finding; just a thing to remember at the next freshness sweep.

3. **C21 watchpoint — `azure-monitor-opentelemetry` pin refresh cadence**
   - Pinned at `~=1.8.8`. The freshness loop polls PyPI weekly. If `1.9.0` ships, the loop opens a refresh issue and the catalog will react. Not a finding; just a watchpoint.

4. **Pattern 13 ingestion-latency telemetry**
   - Track the NOTE emission rate across the matrix over the next ~20 runs. If `NOTE: LAW ingestion exceeded 360s probe budget` shows up in >25% of runs, consider extending the budget to 450s or adding an explicit "expect LAW lag of N min on cold workspaces" warning to SKILL.md. If it shows up in 0% of runs over 20+, the 360s budget is conservative and the catalog is well-calibrated.

---

_Audit completed by: Phase 4 audit worker (cross-session sister of `Phase 4 coverage + audits` coordinator, project_session_id `256a94b2-ddae-4bf2-8dfd-5c3865781662`)._
_Audit method: 21-Item Bug-Class Catalog (spec L381-403) applied to SKILL.md + every reference file. Each finding emitted with verdict (`none observed` / `N/A` / `**HIT**`) + evidence (line numbers + scan commands) + remediation (for HITs)._
_Format reference: `docs/audit/foundry-evals-audit-trail.md` (Phase 4 #4, merged in PR #203)._

---
name: paygo-ptu-cost-analyzer
description: >
  Headless Azure OpenAI PAYGO-vs-PTU cost analysis and sizing report,
  wrapping the analysis core of aiappsgbb/ptu-paygo-mix (not its UI).
  Inputs: CSV, Log Analytics KQL on `AzureMetrics`, or a router-aware
  path on Azure Monitor metrics split by ModelDeploymentName x
  ModelName (model router load on your own deployments, router fee,
  "router absorbs into PTU" what-if). Outputs markdown, JSON and charts;
  bundles synthetic data for offline demos.
  USE FOR: ptu sizing, paygo vs ptu, provisioned throughput unit
  recommendation, AOAI capacity planning, TPM percentile report,
  spillover cost estimate, log analytics token query, AzureMetrics
  PTU, CSV-based PTU sizing, model router PTU sizing, router fee,
  routed traffic per served model, headless cost report,
  paygo-ptu-cost-analyzer.
  DO NOT USE FOR: capacity reservation purchase, the upstream
  Streamlit UI, real-time TPM monitoring, router vs fixed-model
  quality benchmarks (use token-economics), pricing for
  non-Azure-OpenAI services.
metadata:
  version: "1.2.0"
---

# PAYGO vs PTU Cost Analyzer

Headless cost-analysis skill for **Azure OpenAI**. Given a window of
per-minute token usage, it computes the percentile TPM envelope, prices
both **PAYGO** and **PTU** scenarios per percentile, estimates spillover
costs, and emits a markdown + JSON + PNG report.

This is the analysis core of **aiappsgbb/ptu-paygo-mix** wrapped in a
CLI; the upstream Streamlit UI is **excluded by design** (this skill
runs in a terminal, in CI, or inside an agent — never as a web app).

> **Sister capability.** If you actually want the interactive UI, use
> the upstream repo directly (`uv run streamlit run app/streamlit_app.py`).
> This skill is for the cases where the seller / analyst / agent needs
> a **report file** — over chat, in a PR, or as part of an automated
> capacity-planning rollup.

> **Continuous monitoring companion.** [`foundry-cost-monitoring`](../foundry-cost-monitoring/SKILL.md)
> consumes live OTel `gen_ai.usage.*` spans for per-agent / per-project
> cost projection — use it when the FinOps question is "what's my
> spend right now?" rather than "how should I size PTU?"

---

## Two data paths

| Path | When to use | Auth needed |
|------|-------------|-------------|
| `--csv <path>` | Customer already exported their token usage (e.g. via the upstream `docs/sample_kql_queries.md`, Excel, Cost Mgmt export). | None. |
| `--workspace <id>` | You have direct read access on the Log Analytics workspace ingesting Cognitive Services metrics. | `DefaultAzureCredential` (az login / managed identity / env vars / VS Code) with `Log Analytics Reader` on the workspace. |
| `--synthetic` | Offline demo, regression test, or you need to show the report shape before real data lands. | None. |
| `--router-metrics <json>` | Model router in use: saved Azure Monitor metrics JSON (`az monitor metrics list -o json`). See [Router-aware analysis](#router-aware-analysis). | None. |
| `--router-resource <id>` | Model router in use: fetch the same metrics live from the Foundry resource. | `DefaultAzureCredential` with **Monitoring Reader** (or Reader) on the Foundry resource. |

All paths converge on the same `run_analysis()` and `render_report()`
so the output contract is identical.

### Required CSV schema

| Column | Type | Notes |
|--------|------|-------|
| `minute_bin` | datetime (parseable) | Per-minute bucket. |
| `input_tokens_sum` | int | Total input tokens in the bucket (includes cached). |
| `cached_tokens_sum` | int | Subset of `input_tokens_sum` that hit the prompt cache. |
| `output_tokens_sum` | int | Generated tokens. |

`normalize_usage_dataframe()` validates the schema, parses datetimes,
strips thousands separators, and sorts by `minute_bin`. Bad input fails
loudly with a descriptive `ValueError`.

---

## Quickstart

```bash
# 0. One-time deps (matches references/upstream-pin.md)
python3 -m venv .venv && source .venv/bin/activate
pip install "pandas~=3.0.3" "numpy~=2.4.6" "matplotlib~=3.11.0" \
            "azure-identity~=1.27.0" "azure-monitor-query~=2.0.0"

# 1. Offline demo — uses the bundled synthetic generator
python references/run_report.py \
  --synthetic --days 3 \
  --model gpt-5.4 --tier global --ptu-term monthly \
  --out-dir ./paygo-ptu-report

# 2. Customer CSV
python references/run_report.py \
  --csv ./customer_tpm_april.csv \
  --model gpt-5.2 --tier data_zone --ptu-term yearly \
  --percentiles 75,90,95,99 \
  --out-dir ./customer-report

# 3. Live Log Analytics (requires az login + workspace Reader role)
python references/run_report.py \
  --workspace 11111111-2222-3333-4444-555555555555 \
  --time-range 14d \
  --deployment my-gpt-5-4-prod \
  --model gpt-5.4 \
  --out-dir ./live-report

# 4. Router-aware: bundled synthetic router mix (offline), PTU candidate = served model
python references/run_report.py \
  --router-metrics references/sample_router_metrics.json \
  --model gpt-5.4-mini --router-fee-per-m 0.14 --out-dir ./router-report

# 5. Router-aware, live from the Foundry resource (Monitoring Reader)
python references/run_report.py \
  --router-resource /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account> \
  --time-range 7d --model gpt-5.4-mini --save-metrics ./metrics.json --out-dir ./router-live

# A bundled tiny CSV is also available for smoke tests:
python references/run_report.py \
  --csv references/sample_input.csv --model gpt-5.4 --out-dir /tmp/smoke
```

Every run prints the 4 absolute output paths to stdout and exits 0 on
success, non-zero on validation errors.

---

## Output contract

Every run produces exactly these four files under `--out-dir`:

| File | Contents |
|------|----------|
| `report.md` | Narrative report: input window summary, percentile TPM table, PAYGO baseline breakdown, per-percentile PTU sizing scenarios (PTUs, capacity, covered-token %, base cost, spillover cost, total, ∆ vs PAYGO), recommendation paragraph, pricing snapshot. |
| `report.json` | Full `run_analysis()` dict + run metadata (`model`, `tier`, `ptu_term`, `source`, `percentiles`, `pricing_snapshot`, `generated_at`). Reconsumable by downstream agents. |
| `tpm_over_time.png` | Line chart of `total_tpm` over `minute_bin` with horizontal dashed lines for each percentile's PTU capacity (so you can eyeball spillover). |
| `ptu_sizing_scenarios.png` | Grouped bar chart per percentile: PTU base cost (blue) stacked with spillover cost (orange), plus a green dashed line at the PAYGO baseline. Each bar labelled with the total. |

The markdown report always contains the substrings `"PTU Sizing"`,
`"PAYGO Baseline"`, and `"p95"` (the freshness validator asserts these).
In router-aware mode `report.md` also contains `## Router-aware load`, and
`report.json` carries `metadata.router` (router deployments, per-deployment and
per-served-model tokens, fee, what-if, flags).

---

## CLI reference (`run_report.py`)

| Flag | Default | Notes |
|------|---------|-------|
| `--csv <path>` | — | CSV matching the required schema. Mutually exclusive with `--workspace` / `--synthetic`. |
| `--workspace <id>` | — | Log Analytics workspace GUID. Mutually exclusive. |
| `--synthetic` | — | Use the bundled synthetic generator. Mutually exclusive. |
| `--kql <path>` | `references/queries/default.kql` | KQL template; placeholders `__TIME_RANGE__`, `__DEPLOYMENT_FILTER__`. |
| `--time-range` | `7d` | `Nd` or `Nh`. Applied to KQL + Log Analytics timespan. |
| `--deployment` | _empty_ | Filter to a specific Cognitive Services deployment. Optional. |
| `--days` | `7` | Synthetic data duration. |
| `--model` | `gpt-5.4` | Slug from `references/analyzer/models.json`. |
| `--tier` | `global` | `global` or `data_zone` (per the catalog). |
| `--ptu-term` | `monthly` | `monthly` or `yearly`. Switches the cost columns + recommendation. |
| `--percentiles` | `50,75,90,95,99` | Comma-separated, in `(0,100)`. |
| `--ptu-output-weight` | model's `ptu.output_weight` | Multiplier on output-token TPM when sizing PTUs. Defaults to the selected model's catalog `ptu.output_weight` (e.g. `6` for gpt-5.4); pass a value to override (e.g. `1.0` for the old flat behaviour). Falls back to `1` if the model has no `output_weight`. |
| `--out-dir` | `./paygo-ptu-report` | Created if absent. |
| `--router-metrics <path>` | — | Azure Monitor metrics JSON split by `ModelDeploymentName` x `ModelName`. Mutually exclusive with the other sources. |
| `--router-resource <id>` | — | Foundry resource ID; fetches the metrics live for `--time-range`. Mutually exclusive. |
| `--router-deployment` | auto | Extra router deployment name (repeatable). Deployments in `ModelRouter*` metrics or named `model-router*` are detected. |
| `--router-fee-per-m` | Retail Prices API | Router fee, USD per 1M input tokens. Default: meter `Model Routers GL 1M Tokens` (`--tier global`) or `Model Routers DZ 1M Tokens` (`--tier data_zone`) in `--router-region`. |
| `--router-region` | `swedencentral` | Region for the fee lookup. |
| `--fee-excludes-cached` | off | Do not charge the fee on cached input (not documented either way). |
| `--watch-models` | `gpt-4.1,gpt-4o,gpt-5.4` | Served-model families flagged when routed traffic lands on them. |
| `--save-metrics <path>` | — | With `--router-resource`, also save the fetched JSON for an offline rerun. |

In router-aware mode `--model` is the PTU candidate **served** model (for
example `gpt-5.4-mini`), not the router deployment.

---

## Router-aware analysis

Labels: **[Documented]** = official docs, **[Tested]** = measured live,
**[Analysis]** = how this skill derives a number.

### Why routed traffic matters for PTU

- **[Documented]** After model router picks a model, your own deployment of that
  model (exact name and version, same Foundry resource) serves the request first:
  a Global, Data Zone or Regional **Provisioned** deployment for OpenAI models,
  then a Standard / Global Standard / Data Zone Standard deployment, then
  router-managed capacity, then the next-ranked model. On a PTU deployment you pay
  only the routing fee; on pay-as-you-go you pay its usage plus the fee
  ([how model router chooses capacity][router-capacity]).
- So a PTU of the model the router picks most often absorbs routed load you
  currently pay for at PAYGO rates. Sizing it from direct traffic alone under-sizes it.

### Where the per-model split lives

- **[Documented]** Azure Monitor **platform metrics** on the Foundry resource: filter
  `ModelDeploymentName`, split by `ModelName` ([monitor model router][router-monitor]).
  `InputTokens`, `OutputTokens`, `ModelRequests` and the `ModelRouter*` metrics all
  carry both dimensions ([supported metrics][cs-metrics]).
- **[Documented]** Diagnostic-settings export to Log Analytics flattens dimensions:
  "Metrics with dimensions are exported by diagnostic settings as flattened
  single-dimensional metrics, aggregated across dimension values"
  ([metrics index][metrics-index]). `AzureMetrics` therefore has **no** `ModelName`,
  and a KQL query cannot split router traffic per served model. The router-aware
  path reads the metrics REST API (or the JSON from `az monitor metrics list`), not
  Log Analytics.

```bash
az monitor metrics list --resource <foundry-resource-id> \
  --metrics ModelRequests InputTokens OutputTokens ModelRouterRequests \
            ModelRouterInputTokens ModelRouterOutputTokens ModelRouterCachedTokens \
  --aggregation Total --interval PT1M \
  --start-time <utc-start> --end-time <utc-end> \
  --filter "ModelDeploymentName eq '*' and ModelName eq '*'" -o json > metrics.json
```

### What the metrics show

**[Tested]** 2026-11-21, Sweden Central, `model-router` `2025-11-18` Global
Standard plus an own `gpt-5.4-mini` Global Standard deployment in the same
resource, Responses API, Entra ID. 10 router requests pinned to `gpt-5.4-mini`
(`routing_config.models`), 10 unpinned router requests, 10 direct requests:

| Metric family | Router-managed traffic | Routed requests served by your deployment |
|---|---|---|
| `InputTokens` / `OutputTokens` / `ModelRequests` | `ModelDeploymentName` = router deployment, `ModelName` = served model | Under **your deployment's** name, mixed with its direct traffic (20 requests on `gpt-5.4-mini`) |
| `ModelRouter*` | Router deployment x served model | Also counted, under the router deployment (10 requests, `gpt-5.4-mini`) |

- The `x-ratelimit-key` response header was the own deployment's name when it served
  the request and `model-router` otherwise.
- Metrics appeared within about 5 minutes. Allow more before trusting an empty result.
- `ModelName` casing differs between families (`DeepSeek-V4.1-Flash` vs
  `deepseek-v4.1-flash`); the parser lower-cases names.
- The two families can disagree for the same requests (DeepSeek: 84 vs 46 input
  tokens), so routed load on your deployments is clamped to the load seen there.
- **Not tested:** a PTU deployment serving routed traffic (no PTU was purchased); the
  PTU-first order above is documented behaviour. Auto traffic surfacing as a
  `model-router-<version>` deployment name is reported in issue #562; the parser
  treats any `model-router*` name as a router.

### How the report uses them

**[Analysis]** For served model M (`--model`):

```text
total load(M)        = Σ InputTokens/OutputTokens where ModelName = M, over ALL deployments
router-managed(M)    = the same, on router deployments only
routed(M)            = ModelRouter*Tokens where ModelName = M
routed on your(M)    = min(routed(M) − router-managed(M), total(M) − router-managed(M))
direct(M)            = total(M) − router-managed(M) − routed on your(M)
router fee / month   = fee per 1M × Σ routed input tokens (all models) / months observed
```

The report adds a **Router-aware load** section: load per deployment x served
model, router-originated tokens per served model, the router fee, a PTU what-if
(direct only vs direct + routed, at p95) and risk flags for routed traffic on
`--watch-models` families or on models without PTU pricing in `models.json`. The
main PTU sizing tables use the direct + routed load. Direct cached input is not in
these metrics, so it counts as non-cached (PTU sizing errs high).

- **[Tested]** Router fee, Azure Retail Prices API, Sweden Central (read
  2026-11-21): `Model Routers GL 1M Tokens` $0.14 and `Model Routers DZ 1M Tokens`
  $0.154 per 1M tokens. The CLI fetches it unless you pass `--router-fee-per-m`.
- **Not documented:** whether cached input is exempt from the fee. The default
  charges all routed input; `--fee-excludes-cached` shows the other case.
- **[Documented]** Billed amounts: Cost Management, filter the Foundry resource and
  tag **Deployment** = router deployment ([monitor model router][router-monitor]).
  Metric-based costs here are estimates.

[router-capacity]: https://learn.microsoft.com/azure/foundry/openai/concepts/model-router-how-it-works#how-model-router-chooses-capacity
[router-monitor]: https://learn.microsoft.com/azure/foundry/openai/how-to/monitor-model-router
[cs-metrics]: https://learn.microsoft.com/azure/azure-monitor/reference/supported-metrics/microsoft-cognitiveservices-accounts-metrics
[metrics-index]: https://learn.microsoft.com/azure/azure-monitor/reference/metrics-index

---

## Pricing catalog (`references/analyzer/models.json`)

Vendored from the upstream repo. Each model entry carries:

- `paygo.global` + optional `paygo.data_zone` → `input_per_m`, `cached_input_per_m`, `output_per_m`, plus optional `priority_processing` rates
- `ptu.capacity_tpm`, `ptu.min_deployment`, `ptu.increment`, `ptu.output_weight`
- `ptu.global` + optional `ptu.data_zone` → `monthly_price`, `yearly_price`

`ptu.output_weight` (typically 4–8) scales output-token TPM when sizing
PTUs; `--ptu-output-weight` defaults to it (see the CLI table). As of the
`2636464` re-vendor the catalog also ships **gpt-5.5** and **gpt-5.4-mini**,
and **gpt-5.4** now carries `data_zone` pricing (so `--tier data_zone`
resolves for it).

To use a custom catalog: edit `models.json` in place (it's a vendored
file — not auto-refreshed). The upstream-pin tracks the SHA of the
upstream repo so the catalog can be re-vendored when prices drift.

> **Pricing drift is real.** Microsoft updates Azure OpenAI pricing
> several times a year. Treat the bundled `models.json` as a **starting
> point** for a customer conversation, not a quote — always confirm
> against the current pricing page for the customer's region and the
> region of their reservation.

---

## Vendored layout

```
references/
├── analyzer/                      # Analysis core vendored from aiappsgbb/ptu-paygo-mix @ 2636464
│   ├── __init__.py                # Re-exports the public API
│   ├── analysis.py                # run_analysis() — pure pandas/numpy
│   ├── data.py                    # load/normalize/KQL helpers (frozen @ e1786f8, Streamlit stripped)
│   ├── formatting.py              # fmt_num / fmt_cost
│   └── models.json                # PTU + PAYGO pricing catalog
├── queries/
│   ├── default.kql                # AzureMetrics → required schema (InputTokens path)
│   └── active_tokens.kql          # Alternative: derives cached from ActiveTokens
├── render_report.py               # md + json + 2× png (matplotlib, Agg backend)
├── router_metrics.py              # Router-aware metrics parser/split/fee (stdlib; skill-specific)
├── run_report.py                  # CLI entry point
├── sample_input.csv               # ~10 KB demo CSV (240 rows, reproducible seed)
├── sample_router_metrics.json     # SYNTHETIC router + own-deployment metrics mix (60 min)
└── upstream-pin.md                # Tier-B freshness contract
```

`analysis.py`, `formatting.py`, and `models.json` are byte-identical to
upstream `@ 2636464`. Three files **intentionally diverge**:

- `data.py` — **frozen at the `e1786f8` shape** (Streamlit stripped: the
  `import streamlit as st` line and both `@st.cache_data` /
  `@st.cache_data(ttl=300)` decorators removed). Upstream **deleted** its
  live Log-Analytics / KQL path at commit `14a5bec`; this skill keeps it
  to power `--workspace` mode, so `data.py` is **not** re-vendored from
  newer SHAs. See `upstream-pin.md` KI-002.
- `queries/*.kql` — **retained**; upstream deleted the `kql/` directory at
  `14a5bec`. These drive the `--workspace` path.
- `__init__.py` — exported names match the `e1786f8` upstream plus
  `REQUIRED_COLUMNS`, `MODELS_CONFIG_PATH`, `time_range_to_timedelta`.

Re-vendoring the analysis core is a manual chore signalled by SHA drift in
`upstream-pin.md` (the upstream repo is private — a token with read access
is needed to clone it).

---

## KQL path notes

The bundled query targets `AzureMetrics` for the Cognitive Services
resource provider. Prereqs on the customer side:

1. **Diagnostic settings** on the Azure OpenAI resource → route metrics
   to a Log Analytics workspace.
2. Enable the metric categories `InputTokens`, `ProcessedPromptTokens`,
   `GeneratedTokens` (and optionally `ActiveTokens`).
3. The caller needs `Log Analytics Reader` on the workspace (or `Reader`
   at the subscription scope).
4. Allow at least 15 minutes for fresh metrics to land in `AzureMetrics`.

### Two bundled queries — pick by metric availability

| File | Cached-token derivation | Use when |
|------|-------------------------|----------|
| `references/queries/default.kql` | `InputTokens − ProcessedPromptTokens` | The standard path. Works on any Cognitive Services deployment with `InputTokens` enabled. |
| `references/queries/active_tokens.kql` | `ProcessedPromptTokens − ActiveTokens` | Fallback when `InputTokens` is missing or zero — uses the `ActiveTokens` metric (non-cached tokens) as the subtractor. Some older diagnostic-setting configurations only expose this path. |

Pass either with `--kql`:

```bash
python references/run_report.py \
  --workspace <id> --kql references/queries/active_tokens.kql \
  --model gpt-5.4 --out-dir ./report
```

If your workspace uses `AzureDiagnostics` instead of `AzureMetrics`,
write a custom KQL that emits the same 4-column schema and pass it
with `--kql`. See `docs/sample_kql_queries.md` in the upstream repo
for several alternative shapes (request-level breakdown, PTU
utilisation, error analysis).

---

## Known caveats

- **Pricing drift:** as above — re-vendor `models.json` when upstream
  bumps. `upstream-pin.md` tracks the SHA.
- **`AzureMetrics` has no per-model split.** Diagnostic-settings export flattens
  metric dimensions, so `--deployment` on the KQL path may match nothing and
  routed traffic cannot be attributed there. Use the router-aware path.
- **`AzureMetrics.Dimensions` shape varies** by API version — the
  bundled default KQL coalesces `DimensionJson`, `Dimensions`, and
  `Tags`, which covers everything we've seen. If you see empty
  `ModelDeploymentName` after a query, dump the raw row and adjust.
- **Synthetic generator's anchor date is `2026-01-19`** (Monday). The
  synth produces realistic business-hours + weekend + burst patterns
  starting from that fixed timestamp — useful for reproducible demos,
  but obvious if you ship a customer report without disclosing it.
- **`data.py` + `queries/*.kql` are frozen at `e1786f8`** — upstream
  removed the live Log-Analytics / KQL path (commit `14a5bec`); this skill
  keeps it for `--workspace` mode, so those files are **not** re-vendored
  from newer SHAs (only `analysis.py` / `formatting.py` / `models.json`
  are). The `data.py` Streamlit strip is part of that frozen baseline; the
  validation script catches any reintroduction because the import would
  fail outside a Streamlit context. See `upstream-pin.md` KI-002.

---

## References

- Upstream repo: <https://github.com/aiappsgbb/ptu-paygo-mix> (SHA pinned in `references/upstream-pin.md`)
- Azure OpenAI PTU docs: <https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding>
- AzureMetrics schema: <https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics>
- Model router: <https://learn.microsoft.com/azure/foundry/openai/concepts/model-router-how-it-works>, <https://learn.microsoft.com/azure/foundry/openai/how-to/monitor-model-router>
- Cognitive Services metrics: <https://learn.microsoft.com/azure/azure-monitor/reference/supported-metrics/microsoft-cognitiveservices-accounts-metrics>
- Related awesome-gbb skills: `token-economics` (router vs fixed-model cost/quality), `azure-tenant-isolation` (for `--workspace` runs), `foundry-observability` (downstream consumers of the JSON report).

---
name: paygo-ptu-cost-analyzer
description: >
  Headless Azure OpenAI PAYGO-vs-PTU cost analysis and sizing report.
  Wraps the analysis library of aiappsgbb/ptu-paygo-mix (NOT its
  Streamlit UI). Supports CSV token-usage input and Log Analytics
  queries via vendored KQL against `AzureMetrics`. Produces a markdown
  report, JSON data, and charts. Bundles a synthetic-data generator
  for offline demos.
  USE FOR: ptu sizing, paygo vs ptu, provisioned throughput unit
  recommendation, AOAI capacity planning, TPM percentile report,
  spillover cost estimate, log analytics token query, AzureMetrics
  PTU, CSV-based PTU sizing, headless cost report,
  paygo-ptu-cost-analyzer.
  DO NOT USE FOR: capacity reservation purchase workflow, deploying
  the upstream Streamlit UI (use the upstream repo), real-time TPM
  monitoring (use azure-monitor-query directly), pricing for
  non-Azure-OpenAI services.
metadata:
  version: "1.1.0"
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

All three paths converge on the same `run_analysis()` and `render_report()`
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
            "azure-identity~=1.25.3" "azure-monitor-query~=2.0.0"

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
├── run_report.py                  # CLI entry point
├── sample_input.csv               # ~10 KB demo CSV (240 rows, reproducible seed)
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
- Related awesome-gbb skills: `azure-tenant-isolation` (for `--workspace` runs), `foundry-observability` (downstream consumers of the JSON report).

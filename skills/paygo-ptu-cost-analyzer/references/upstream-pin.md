---
schema_version: 2

freshness_tier: B

automation_tier: auto

upstream:
  type: github_repo
  repo: aiappsgbb/ptu-paygo-mix
  ref: main
  pinned_sha: e1786f89329859b2f801c1b240538b4bbe649139
  pinned_commit_message: |
    Merge branch 'charendt:main' into main
  license: MIT
  notes: |
    Tier B because the **execution surface** of this skill is its 5 PyPI
    dependencies (pandas, numpy, matplotlib, azure-identity,
    azure-monitor-query). The upstream repo itself is vendored verbatim:
    - `analysis.py`, `formatting.py`, `models.json` — byte-identical
    - `kql/default_log_analytics_query.kql` → `queries/default.kql`
    - `kql/default_log_analytics_query.active_tokens_backup.kql` → `queries/active_tokens.kql`
    - `data.py` — Streamlit-stripped (see KI-002)
    The `pinned_sha` above is the **last-vendored marker** — it does NOT
    auto-refresh through this pin (only PyPI versions do). When upstream
    advances on the analysis math or the pricing catalog, a human
    re-vendors the files and bumps the SHA here in the same PATCH PR.
    The weekly detector still polls the SHA so we get an unassigned
    issue when upstream commits — that's the re-vendor trigger.

packages:
  - name: pandas
    source: pypi
    version: "~=3.0.3"
    upstream_changelog: https://pandas.pydata.org/docs/whatsnew/index.html
    notes: |
      Core dataframe + datetime parsing. `normalize_usage_dataframe`
      depends on `pd.to_datetime` + `pd.to_numeric` shape.
  - name: numpy
    source: pypi
    version: "~=2.4.6"
    upstream_changelog: https://numpy.org/doc/stable/release.html
    notes: |
      `np.percentile`, `np.ceil`, vectorized math in run_analysis.
  - name: matplotlib
    source: pypi
    version: "~=3.10.9"
    upstream_changelog: https://matplotlib.org/stable/users/release_notes.html
    notes: |
      Headless `Agg` backend (set explicitly in render_report.py before
      pyplot import — required when no DISPLAY).
  - name: azure-identity
    source: pypi
    version: "~=1.25.3"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/CHANGELOG.md
    notes: |
      Only used by the `--workspace` (Log Analytics) path via
      `DefaultAzureCredential`. Not exercised by the synthetic-mode smoke.
  - name: azure-monitor-query
    source: pypi
    version: "~=2.0.0"
    upstream_changelog: https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/monitor/azure-monitor-query/CHANGELOG.md
    notes: |
      `LogsQueryClient.query_workspace`. Only exercised by `--workspace`.

docs_to_revalidate:
  - https://github.com/aiappsgbb/ptu-paygo-mix
  - https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/README.md
  - https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/docs/sample_kql_queries.md
  - https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding
  - https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics
  - https://pypi.org/project/pandas/
  - https://pypi.org/project/numpy/
  - https://pypi.org/project/matplotlib/
  - https://pypi.org/project/azure-identity/
  - https://pypi.org/project/azure-monitor-query/

known_issues:
  - id: KI-001
    description: "models.json pricing catalog drifts whenever Microsoft updates Azure OpenAI prices"
    upstream_url: https://learn.microsoft.com/azure/ai-services/openai/concepts/provisioned-throughput
    status: open
    workaround_location: SKILL.md § "Pricing catalog" + § "Known caveats"
  - id: KI-002
    description: "data.py vendoring must strip `import streamlit as st` and `@st.cache_data*` decorators on every re-vendor"
    upstream_url: https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/src/paygo_ptu/data.py
    status: open
    workaround_location: SKILL.md § "Vendored layout"
  - id: KI-003
    description: "AzureMetrics Dimensions field shape varies by API version; default KQL coalesces DimensionJson | Dimensions | Tags"
    upstream_url: https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics
    status: open
    workaround_location: SKILL.md § "KQL path notes"

validation:
  requires:
    - github_only
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet \
      "pandas~=3.0.3" \
      "numpy~=2.4.6" \
      "matplotlib~=3.10.9" \
      "azure-identity~=1.25.3" \
      "azure-monitor-query~=2.0.0"
    python - <<'PY'
    import pandas as pd
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from azure.identity import DefaultAzureCredential
    from azure.monitor.query import LogsQueryClient
    print("ok paygo-ptu-cost-analyzer imports")

    # Inline replica of the math contract that run_analysis() depends on.
    # If pandas/numpy break any of these calls the analyzer breaks too.
    df = pd.DataFrame({
        "minute_bin": pd.date_range("2026-01-19", periods=60, freq="min"),
        "input_tokens_sum": np.random.randint(1_000_000, 10_000_000, 60),
        "cached_tokens_sum": np.random.randint(500_000, 5_000_000, 60),
        "output_tokens_sum": np.random.randint(100_000, 1_000_000, 60),
    })
    df["minute_bin"] = pd.to_datetime(df["minute_bin"], errors="coerce")
    df["non_cached_input"] = df["input_tokens_sum"] - df["cached_tokens_sum"]
    df["ptu_billable_tpm"] = df["non_cached_input"] + df["output_tokens_sum"]
    p95 = np.percentile(df["ptu_billable_tpm"], 95)
    assert p95 > 0
    print(f"ok analyzer math (p95={int(p95):,})")

    # Headless matplotlib render — what render_report.py does
    fig, ax = plt.subplots(figsize=(4, 2))
    ax.plot(df["minute_bin"], df["input_tokens_sum"])
    fig.savefig("/tmp/ptu_smoke_chart.png", dpi=80)
    plt.close(fig)
    import os
    assert os.path.getsize("/tmp/ptu_smoke_chart.png") > 0
    print("ok matplotlib Agg backend render")

    # Synthetic markers for the report.md substring contract documented
    # in SKILL.md (these are what render_report.py would emit)
    print("section markers: 'PTU Sizing' + 'PAYGO Baseline' + 'p95'")
    print("paygo-ptu-cost-analyzer smoke passed")
    PY
  expected_output:
    - "ok paygo-ptu-cost-analyzer imports"
    - "ok analyzer math"
    - "ok matplotlib Agg backend render"
    - "paygo-ptu-cost-analyzer smoke passed"
  failure_signatures:
    - "ModuleNotFoundError"
    - "AttributeError"
    - "AssertionError"

last_validated: "2026-05-26"
validated_by: copilot-bot
known_issues_count: 3
re_pin_log:
  - "2026-05-18: initial pin v1.0.0 (ricchi)"
  - "2026-05-18: v1.0.1 — also vendor active_tokens_backup.kql as queries/active_tokens.kql alternative (ricchi)"
---

# Upstream pin — `paygo-ptu-cost-analyzer` skill

This file is the **machine-readable validation contract** for the
`paygo-ptu-cost-analyzer` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human audit
trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `aiappsgbb/ptu-paygo-mix` |
| **Branch / tag** | `main` |
| **Pinned SHA** | `e1786f89329859b2f801c1b240538b4bbe649139` |
| **Pinned commit subject** | `Merge branch 'charendt:main' into main` |
| **License** | MIT |
| **First authored against** | 2026-05-18 |
| **Last re-validated** | 2026-05-18 |

The SHA above is a **last-vendored marker**, not an auto-refreshing pin.
Re-validate by:

```bash
git ls-remote https://github.com/aiappsgbb/ptu-paygo-mix main
# Compare first column to pinned_sha
```

If it has drifted, a human must re-vendor `analysis.py`, `data.py`,
`formatting.py`, `models.json`, and `default_log_analytics_query.kql`
(see § 5 for the surgical edits applied to `data.py`).

---

## 2. Pinned packages (Tier B)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `pandas` | PyPI | `~=2.2.3` | Dataframe + datetime parsing |
| `numpy` | PyPI | `~=2.1.0` | Vectorised math + percentile |
| `matplotlib` | PyPI | `~=3.9.0` | Headless Agg backend |
| `azure-identity` | PyPI | `~=1.22.0` | `DefaultAzureCredential` (KQL path only) |
| `azure-monitor-query` | PyPI | `~=2.0.0` | `LogsQueryClient` (KQL path only) |

Cap pattern is PEP 440 compatible-release per AGENTS.md § 9.5. Patch
upgrades inside the cap window are picked up automatically by the next
weekly run; minor/major bumps require a refresh PR.

---

## 3. Verification checklist (the executable contract)

> For coding agents: this section's `bash` block is a human-readable copy
> of `validation.script` in the front-matter. Keep them identical. The
> agent will run the front-matter script verbatim through
> `scripts/run-pin-validation.py`.

Following the awesome-gbb convention, this script is a **pip-install +
import + numeric-math smoke** — it does NOT exercise the vendored
`run_report.py` CLI end-to-end (the runner CDs into a tempdir outside
the repo, so the vendored files aren't reachable from there). End-to-end
coverage is the reviewer's job at PR time; the pin smoke proves the 5
PyPI deps still satisfy the analyzer's math + headless-matplotlib
contracts at the pinned cap window.

```bash
#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv && . .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet \
  "pandas~=2.2.3" "numpy~=2.1.0" "matplotlib~=3.9.0" \
  "azure-identity~=1.22.0" "azure-monitor-query~=2.0.0"
python - <<'PY'
import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient
print("ok paygo-ptu-cost-analyzer imports")
# Replicate the analyzer math contract inline
df = pd.DataFrame({
    "minute_bin": pd.date_range("2026-01-19", periods=60, freq="min"),
    "input_tokens_sum":  np.random.randint(1_000_000, 10_000_000, 60),
    "cached_tokens_sum": np.random.randint(500_000, 5_000_000, 60),
    "output_tokens_sum": np.random.randint(100_000, 1_000_000, 60),
})
df["non_cached_input"] = df["input_tokens_sum"] - df["cached_tokens_sum"]
p95 = np.percentile(df["non_cached_input"] + df["output_tokens_sum"], 95)
assert p95 > 0
print(f"ok analyzer math (p95={int(p95):,})")
fig, ax = plt.subplots(); ax.plot(df["minute_bin"], df["input_tokens_sum"])
fig.savefig("/tmp/ptu_smoke_chart.png", dpi=80); plt.close(fig)
print("ok matplotlib Agg backend render")
print("paygo-ptu-cost-analyzer smoke passed")
PY
```

**Expected output** must contain (substring match):

- `ok paygo-ptu-cost-analyzer imports`
- `ok analyzer math`
- `ok matplotlib Agg backend render`
- `paygo-ptu-cost-analyzer smoke passed`

**Failure signatures** (treat as upstream regression):

- `ModuleNotFoundError` — a pinned dep dropped a public name
- `AttributeError` — a pinned dep renamed an API the analyzer uses
- `AssertionError` — the math contract changed shape

For end-to-end coverage of `run_report.py` (the CLI), run the **Quickstart**
in `SKILL.md` manually after re-vendoring. The PR review process is the
gate for vendored-file correctness; this pin is the gate for dep drift.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `pip install` 5 capped deps | ✅ | "imports OK" |
| `--synthetic --days 3 --model gpt-5.4` | ✅ | 4 output files written |
| `report.md` contains "PTU Sizing" / "PAYGO Baseline" / "p95" | ✅ | All three substrings present |
| `--csv references/sample_input.csv --ptu-term yearly` | ✅ | Yearly columns rendered correctly |

Captured at `last_validated: 2026-05-18` by `ricchi` (macOS Darwin 25.5.0
+ Python 3.13.5).

---

## 5. Known issues at this pin

### KI-001 — Pricing catalog drift

**Upstream tracker:** <https://learn.microsoft.com/azure/ai-services/openai/concepts/provisioned-throughput>
**Status:** open

Microsoft updates Azure OpenAI PTU and PAYGO prices several times per
year. The bundled `references/analyzer/models.json` is a snapshot at the
pinned SHA and **will drift**. This is structural — there is no
machine-readable upstream price feed we can poll.

**Workaround:** SKILL.md explicitly flags this in the "Pricing catalog"
and "Known caveats" sections. When a seller spots a price mismatch, they
edit `models.json` in place for that engagement; the canonical refresh
is to re-vendor from upstream when upstream itself updates the catalog.

**When upstream fixes this:** never fully — pricing drift is intrinsic.
Re-vendoring `models.json` on each upstream SHA bump keeps the gap small.

### KI-002 — Streamlit-strip surgery on re-vendor

**Upstream tracker:** <https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/src/paygo_ptu/data.py>
**Status:** open

The vendored `references/analyzer/data.py` differs from upstream by
**exactly three line removals**:

1. `import streamlit as st`
2. `@st.cache_data` (the bare decorator above `load_models_config`)
3. `@st.cache_data(ttl=300)` (the parametrised decorator above
   `query_log_analytics`)

Without this surgery the module fails to import outside a Streamlit
context. The validation script's `--synthetic` smoke would catch a
reintroduction because `from analyzer import generate_synthetic_data`
would fail.

**Workaround:** on every re-vendor, diff `data.py` against upstream;
the only allowed delta is the three removals above. Everything else
must be byte-identical.

**When upstream fixes this:** the day upstream splits caching out of
`data.py` (e.g. into a `cache.py` shim), we drop this surgery.

### KI-003 — AzureMetrics dimension shape variance

**Upstream tracker:** <https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics>
**Status:** open

`AzureMetrics` exposes deployment dimensions under different field names
depending on the diagnostic-setting API version (`DimensionJson` vs
`Dimensions` vs `Tags`). The bundled `references/queries/default.kql`
already `coalesce()`s all three, but if a customer's diagnostic settings
were configured against an older API, the deployment filter may resolve
to empty.

**Workaround:** customer instructions in SKILL.md § "KQL path notes"
walk through verifying the dim shape and authoring a per-customer KQL
passed via `--kql`.

**When upstream fixes this:** never (this is a Microsoft platform
quirk). The coalesce in the default query is the permanent fix.

---

## 6. Re-pin procedure

When upstream `aiappsgbb/ptu-paygo-mix` advances:

1. **Capture new SHA**:
   ```bash
   git ls-remote https://github.com/aiappsgbb/ptu-paygo-mix main
   ```
2. **Re-vendor the files**:
   ```bash
   git clone https://github.com/aiappsgbb/ptu-paygo-mix /tmp/ptu-upstream
   cd /tmp/ptu-upstream && git checkout <new-sha>
   cp src/paygo_ptu/analysis.py     <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   cp src/paygo_ptu/formatting.py   <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   cp src/paygo_ptu/models.json     <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   cp src/paygo_ptu/kql/default_log_analytics_query.kql \
      <repo>/skills/paygo-ptu-cost-analyzer/references/queries/default.kql
   cp src/paygo_ptu/kql/default_log_analytics_query.active_tokens_backup.kql \
      <repo>/skills/paygo-ptu-cost-analyzer/references/queries/active_tokens.kql
   # data.py: copy then strip streamlit (see KI-002 for exact 3 line removals)
   ```
3. **Re-run validation script** (front-matter `validation.script`) — must
   pass all 3 `expected_output` substrings.
4. **Update front-matter**: `upstream.pinned_sha`, `pinned_commit_message`,
   `last_validated`, `validated_by`. Bump `known_issues_count` if a new
   workaround was introduced.
5. **Bump SKILL.md `metadata.version` PATCH** (e.g., `1.0.0` → `1.0.1`)
   per AGENTS.md § 5.
6. **Open PR**: title `chore(paygo-ptu-cost-analyzer): re-pin upstream → <short-sha>`.
   Touches the 5 vendored files + `references/upstream-pin.md` + `SKILL.md`
   frontmatter. Body changes require `[skill-rewrite]` per AGENTS.md § 4.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx responses
surface as a refresh issue.

- <https://github.com/aiappsgbb/ptu-paygo-mix>
- <https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/README.md>
- <https://github.com/aiappsgbb/ptu-paygo-mix/blob/main/docs/sample_kql_queries.md>
- <https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding>
- <https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics>
- <https://pypi.org/project/pandas/>
- <https://pypi.org/project/numpy/>
- <https://pypi.org/project/matplotlib/>
- <https://pypi.org/project/azure-identity/>
- <https://pypi.org/project/azure-monitor-query/>

---

## 8. Cross-references worth bookmarking

- `src/paygo_ptu/analysis.py` — the math (vendored verbatim)
- `src/paygo_ptu/data.py` — schema + KQL ingest (vendored with surgery)
- `src/paygo_ptu/models.json` — pricing catalog (vendored verbatim)
- `src/paygo_ptu/kql/default_log_analytics_query.kql` — default query
- `docs/sample_kql_queries.md` — alternative KQL shapes for customers
  whose workspaces don't fit the default

---

## 9. Notes for the coding agent

> If you're GHCP picking up a refresh issue for this skill:
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
> 2. If it passes AND the SHA has drifted, follow § 6 to re-vendor the 5
>    files. The Streamlit-strip surgery on `data.py` (KI-002) is exactly
>    three line removals — preserve everything else byte-for-byte.
> 3. If it passes WITHOUT a SHA drift (e.g. weekly PyPI patch refresh),
>    just update `last_validated` and `validated_by: copilot-bot`, then
>    bump SKILL.md `metadata.version` PATCH. Touch nothing else.
> 4. If it fails, comment on the issue with the failure output and
>    **do NOT open a PR**.
> 5. Re-vendoring touches files outside `references/upstream-pin.md` and
>    `SKILL.md` frontmatter — the `automation-pr-gate.yml` workflow will
>    require `[skill-rewrite]` in the commit message for such a PR.

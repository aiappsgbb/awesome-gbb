---
schema_version: 2

freshness_tier: B

automation_tier: auto

upstream:
  type: github_repo
  repo: aiappsgbb/ptu-paygo-mix
  ref: main
  pinned_sha: 2636464b3604ec417771b4d96337c87c50d34c9f
  pinned_commit_message: |
    Merge branch 'charendt:main' into main
  license: MIT
  notes: |
    Tier B because the **execution surface** of this skill is its 5 PyPI
    dependencies (pandas, numpy, matplotlib, azure-identity,
    azure-monitor-query). The upstream analysis core is vendored:
    - `analysis.py`, `formatting.py`, `models.json` — byte-identical @ 2636464
    - `data.py` — **intentionally NOT re-vendored** past e1786f8: upstream
      deleted its live Log-Analytics / KQL path at 14a5bec, but this skill
      keeps it to power the CLI `--workspace` mode. Our `data.py` is the
      e1786f8 upstream module with the Streamlit lines stripped (see KI-002).
    - `queries/default.kql`, `queries/active_tokens.kql` — **retained**;
      upstream deleted the `kql/` directory at 14a5bec.
    The `pinned_sha` above is the **last-vendored marker** — it does NOT
    auto-refresh through this pin (only PyPI versions do). When upstream
    advances on the analysis math or the pricing catalog, a human
    re-vendors `analysis.py` / `formatting.py` / `models.json` and bumps
    the SHA here.
    As of 2026-07-06 the upstream repo `aiappsgbb/ptu-paygo-mix` is
    accessible again but **private** — SHA-drift re-vendoring is a manual
    chore (a token with repo read access is required; public CI cannot
    poll it, so the GitHub URLs stay out of `docs_to_revalidate`). All
    automated skill validation remains PyPI-only.

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
    version: "~=3.11.0"
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
    description: "data.py + queries/*.kql intentionally diverge from upstream: upstream deleted the live Log-Analytics/KQL path at 14a5bec, so this skill freezes data.py at e1786f8 (Streamlit lines stripped) and retains the .kql files to keep the CLI --workspace mode working"
    upstream_url: https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding
    status: open
    workaround_location: SKILL.md § "Vendored layout"
  - id: KI-003
    description: "AzureMetrics Dimensions field shape varies by API version; default KQL coalesces DimensionJson | Dimensions | Tags"
    upstream_url: https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics
    status: open
    workaround_location: SKILL.md § "KQL path notes"

validation:
  requires:
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
      "matplotlib~=3.11.0" \
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

last_validated: "2026-07-06"
validated_by: ricchi
known_issues_count: 3
re_pin_log:
  - "2026-05-18: initial pin v1.0.0 (ricchi)"
  - "2026-05-18: v1.0.1 — also vendor active_tokens_backup.kql as queries/active_tokens.kql alternative (ricchi)"
  - "2026-06-18: v1.0.6 — matplotlib ~=3.10.9 → ~=3.11.0 (MINOR); remove github_only from validation.requires (upstream repo aiappsgbb/ptu-paygo-mix is private/inaccessible); remove 3 dead docs_to_revalidate URLs; fix KI-002 upstream_url (copilot-bot)"
  - "2026-07-06: v1.1.0 — re-vendor upstream e1786f8 → 2636464: models.json adds gpt-5.5 + gpt-5.4-mini, data_zone pricing for gpt-5.4, priority_processing PAYGO rates, and ptu.output_weight (4/6/8); analysis.py + formatting.py byte-identical; wire run_report.py --ptu-output-weight to default from the model's catalog output_weight; KEEP skill-specific data.py + queries/*.kql --workspace path that upstream deleted at 14a5bec (repo accessible again but private) (ricchi)"
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
| **Pinned SHA** | `2636464b3604ec417771b4d96337c87c50d34c9f` |
| **Pinned commit subject** | `Merge branch 'charendt:main' into main` |
| **License** | MIT |
| **First authored against** | 2026-05-18 |
| **Last re-validated** | 2026-07-06 |

The SHA above is a **last-vendored marker**, not an auto-refreshing pin.
Re-validate by:

```bash
git ls-remote https://github.com/aiappsgbb/ptu-paygo-mix main
# Compare first column to pinned_sha
```

If it has drifted, a human re-vendors the **pure analysis core** —
`analysis.py`, `formatting.py`, and `models.json` — byte-identical from
the new SHA. `data.py` and `queries/*.kql` are **deliberately frozen**
(upstream deleted the live Log-Analytics/KQL path at 14a5bec; this skill
keeps it for `--workspace` mode — see § 5, KI-002).

---

## 2. Pinned packages (Tier B)

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `pandas` | PyPI | `~=3.0.3` | Dataframe + datetime parsing |
| `numpy` | PyPI | `~=2.4.6` | Vectorised math + percentile |
| `matplotlib` | PyPI | `~=3.11.0` | Headless Agg backend |
| `azure-identity` | PyPI | `~=1.25.3` | `DefaultAzureCredential` (KQL path only) |
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
  "pandas~=3.0.3" "numpy~=2.4.6" "matplotlib~=3.11.0" \
  "azure-identity~=1.25.3" "azure-monitor-query~=2.0.0"
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
| `pip install` 5 capped deps | ✅ | imports OK |
| `--synthetic --days 3 --model gpt-5.4` | ✅ | 4 output files written |
| `report.md` contains "PTU Sizing" / "PAYGO Baseline" / "p95" | ✅ | All three substrings present |
| `--csv references/sample_input.csv --ptu-term yearly` | ✅ | Yearly columns rendered correctly |
| `--synthetic --model gpt-5.4 --tier data_zone` (was broken pre-re-vendor) | ✅ | data_zone pricing now resolves (models.json gained the block) |
| `--synthetic --model gpt-5.5` (new catalog entry) | ✅ | New model prices + sizes render |
| `--synthetic --model gpt-5.4-mini` (new catalog entry) | ✅ | New model prices + sizes render |
| `--ptu-output-weight` defaults from catalog `ptu.output_weight` | ✅ | gpt-5.4 defaults to 6; explicit `--ptu-output-weight 1.0` still overrides |

Captured at `last_validated: 2026-07-06` by `ricchi` (macOS Darwin 25.5.0
+ Python 3.13.5). Re-vendor of upstream e1786f8 → 2636464 (Option C:
pure analysis core + pricing catalog; `--workspace`/KQL path retained).

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

### KI-002 — data.py + KQL intentionally diverge from upstream

**Upstream tracker:** <https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding>
**Status:** open (permanent design divergence)

At the pinned SHA `2636464`, upstream has **removed** the live
Log-Analytics path from `data.py` (the `query_log_analytics`,
`build_default_kql_query`, `load_kql_template`, `time_range_to_timedelta`
helpers and the `KQL_TEMPLATE_PATH` constant) and **deleted** the entire
`kql/` directory — all at commit `14a5bec`. That capability is what this
skill's CLI `--workspace` mode is built on.

Rather than lose `--workspace`, this skill **freezes** its own
`references/analyzer/data.py` and `references/queries/*.kql` at the
`e1786f8` shape. The only delta from that `e1786f8` upstream `data.py`
is the Streamlit strip — **three line removals**:

1. `import streamlit as st`
2. `@st.cache_data` (the bare decorator above `load_models_config`)
3. `@st.cache_data(ttl=300)` (the parametrised decorator above
   `query_log_analytics`)

Without that strip the module fails to import outside a Streamlit
context; the validation smoke catches any reintroduction because the
import would fail.

**Consequence for re-vendoring:** `data.py` and `queries/*.kql` are
**NOT** copied from newer upstream SHAs. Only `analysis.py`,
`formatting.py`, and `models.json` are re-vendored byte-identical. If a
future refresh wants to adopt upstream's model-autodetect / JSON-parse
path, that is a **separate, deliberate decision** (it would drop the live
`--workspace` query capability) — not a routine re-vendor.

**When upstream fixes this:** N/A — upstream removed the capability on
purpose (the Streamlit app now expects the caller to paste JSON). This
divergence is permanent unless the skill's `--workspace` mode is retired.

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

> **Note (2026-07-06):** The upstream repo `aiappsgbb/ptu-paygo-mix` is
> accessible again but **private** — a token with repo read access is
> required to clone it, and public CI cannot poll it. SHA-drift
> re-vendoring is therefore a **manual chore**, not an automated one.
> Only the **pure analysis core** is re-vendored; `data.py` and
> `queries/*.kql` are frozen (see § 5, KI-002).

When upstream `aiappsgbb/ptu-paygo-mix` advances (checked manually):

1. **Capture new SHA** (needs repo read access):
   ```bash
   git ls-remote https://github.com/aiappsgbb/ptu-paygo-mix main
   ```
2. **Re-vendor ONLY the pure analysis core** (byte-identical):
   ```bash
   git clone https://github.com/aiappsgbb/ptu-paygo-mix /tmp/ptu-upstream
   cd /tmp/ptu-upstream && git checkout <new-sha>
   cp src/paygo_ptu/analysis.py   <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   cp src/paygo_ptu/formatting.py <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   cp src/paygo_ptu/models.json   <repo>/skills/paygo-ptu-cost-analyzer/references/analyzer/
   # DO NOT copy data.py or the kql/ files — they are frozen (KI-002).
   # Upstream deleted the live Log-Analytics path at 14a5bec; this skill
   # keeps its e1786f8 data.py + queries/*.kql to power --workspace mode.
   ```
   Then re-check any CLI wiring that reads new catalog fields (e.g. the
   `--ptu-output-weight` default now falls back to `ptu.output_weight`).
3. **Re-run validation script** (front-matter `validation.script`) — must
   pass all 3 `expected_output` substrings — AND run the SKILL.md
   Quickstart end-to-end (`--synthetic`, `--csv sample_input.csv`) as the
   § 2.9 live-test evidence.
4. **Update front-matter**: `upstream.pinned_sha`, `pinned_commit_message`,
   `last_validated`, `validated_by`, and append a `re_pin_log` entry. Bump
   `known_issues_count` if a new workaround was introduced.
5. **Bump SKILL.md `metadata.version`** — PATCH for a like-for-like
   re-vendor, MINOR if the catalog gains new models or a CLI default
   changes (per AGENTS.md § 5).
6. **Open PR**: title `chore(paygo-ptu-cost-analyzer): re-pin upstream → <short-sha>`.
   Touches the 3 analysis-core files + `references/upstream-pin.md` +
   `SKILL.md`. Body changes require `[skill-rewrite]` per AGENTS.md § 4.

---

## 7. URLs to re-validate (link-rot detector input)

The detector runs `curl --head` against each URL weekly; 4xx/5xx responses
surface as a refresh issue.

> **Note (2026-07-06):** `https://github.com/aiappsgbb/ptu-paygo-mix`
> and its sub-URLs stay **out** of this list: the repo is accessible
> again but **private**, so an unauthenticated `curl --head` from CI
> still gets 404. Re-add them only if the repo is made public.

- <https://learn.microsoft.com/azure/ai-services/openai/how-to/provisioned-throughput-onboarding>
- <https://learn.microsoft.com/azure/azure-monitor/reference/tables/azuremetrics>
- <https://pypi.org/project/pandas/>
- <https://pypi.org/project/numpy/>
- <https://pypi.org/project/matplotlib/>
- <https://pypi.org/project/azure-identity/>
- <https://pypi.org/project/azure-monitor-query/>

---

## 8. Cross-references worth bookmarking

- `src/paygo_ptu/analysis.py` — the math (vendored verbatim @ 2636464)
- `src/paygo_ptu/formatting.py` — number formatting (vendored verbatim @ 2636464)
- `src/paygo_ptu/models.json` — pricing catalog (vendored verbatim @ 2636464)
- `src/paygo_ptu/data.py` — **upstream removed the KQL path at 14a5bec**;
  our `data.py` is frozen at the `e1786f8` shape (Streamlit-stripped)
- `docs/sample_kql_queries.md` — alternative KQL shapes for customers
  whose workspaces don't fit the default (still a useful reference)

---

## 9. Notes for the coding agent

> If you're GHCP picking up a refresh issue for this skill:
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
> 2. This skill's SHA-drift re-vendor is a **manual chore** — the upstream
>    repo is private, so you (public CI) cannot clone it. Do NOT attempt a
>    SHA re-vendor. Only `analysis.py` / `formatting.py` / `models.json`
>    are ever re-vendored, and `data.py` + `queries/*.kql` are frozen
>    (KI-002) — never copy newer upstream versions of those.
> 3. If the smoke passes (weekly PyPI patch refresh), just update
>    `last_validated` and `validated_by: copilot-bot`, then bump SKILL.md
>    `metadata.version` PATCH. Touch nothing else.
> 4. If it fails, comment on the issue with the failure output and
>    **do NOT open a PR**.
> 5. Re-vendoring touches files outside `references/upstream-pin.md` and
>    `SKILL.md` frontmatter — the `automation-pr-gate.yml` workflow will
>    require `[skill-rewrite]` in the commit message for such a PR.

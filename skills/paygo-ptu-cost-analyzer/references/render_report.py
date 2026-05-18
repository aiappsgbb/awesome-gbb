"""Render a PAYGO vs PTU analysis as markdown + JSON + PNG charts.

Pure-Python rendering — matplotlib only, no Streamlit, no Jupyter.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend before pyplot import
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _fmt_num(n: float) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.2f}K"
    return f"{n:,.0f}"


def _fmt_cost(n: float) -> str:
    return f"${n:,.2f}"


def _percentile_table(percentile_values: dict[int, float]) -> str:
    lines = ["| Percentile | Total TPM |", "| --- | ---: |"]
    for p in sorted(percentile_values):
        lines.append(f"| p{p} | {_fmt_num(percentile_values[p])} |")
    return "\n".join(lines)


def _paygo_table(paygo_breakdown: dict[str, float]) -> str:
    lines = ["| Component | Monthly cost |", "| --- | ---: |"]
    label_map = {
        "non_cached_input_cost_monthly": "Non-cached input",
        "cached_input_cost_monthly": "Cached input",
        "output_cost_monthly": "Output",
        "total_cost_monthly": "**Total PAYGO baseline**",
    }
    for key, label in label_map.items():
        if key in paygo_breakdown:
            lines.append(f"| {label} | {_fmt_cost(paygo_breakdown[key])} |")
    return "\n".join(lines)


def _scenarios_table(
    ptu_scenarios: dict[int, dict[str, Any]],
    paygo_monthly: float,
    ptu_term: str,
) -> str:
    cost_key = "total_yearly" if ptu_term == "yearly" else "total_monthly"
    ptu_cost_key = "ptu_yearly_cost" if ptu_term == "yearly" else "ptu_monthly_cost"
    term_label = "Yearly" if ptu_term == "yearly" else "Monthly"
    paygo_label = "annualised" if ptu_term == "yearly" else "monthly"
    paygo_baseline = paygo_monthly * 12 if ptu_term == "yearly" else paygo_monthly

    lines = [
        f"| Percentile | PTUs | PTU capacity (TPM) | PTU covered tokens | "
        f"{term_label} PTU cost | {term_label} spillover | "
        f"**{term_label} total** | vs PAYGO {paygo_label} |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for p in sorted(ptu_scenarios):
        s = ptu_scenarios[p]
        spillover_cost = s["spillover_cost"] * (12 if ptu_term == "yearly" else 1)
        total = s[cost_key]
        delta_pct = ((total - paygo_baseline) / paygo_baseline * 100) if paygo_baseline else 0.0
        delta_sign = "+" if delta_pct >= 0 else ""
        lines.append(
            f"| p{p} | {int(s['ptus'])} | {_fmt_num(s['ptu_capacity'])} | "
            f"{s['ptu_covered_token_pct']:.1f}% | "
            f"{_fmt_cost(s[ptu_cost_key])} | {_fmt_cost(spillover_cost)} | "
            f"**{_fmt_cost(total)}** | {delta_sign}{delta_pct:.1f}% |"
        )
    return "\n".join(lines)


def _recommend(
    ptu_scenarios: dict[int, dict[str, Any]],
    paygo_monthly: float,
    ptu_term: str,
) -> str:
    cost_key = "total_yearly" if ptu_term == "yearly" else "total_monthly"
    paygo_baseline = paygo_monthly * 12 if ptu_term == "yearly" else paygo_monthly

    best_p, best_cost = None, float("inf")
    for p, s in ptu_scenarios.items():
        if s[cost_key] < best_cost:
            best_p, best_cost = p, s[cost_key]

    if best_p is None:
        return "_No scenarios computed — cannot recommend._"

    s = ptu_scenarios[best_p]
    savings = paygo_baseline - best_cost
    savings_pct = (savings / paygo_baseline * 100) if paygo_baseline else 0.0

    if savings <= 0:
        return (
            f"**Recommendation: stay on PAYGO.** The cheapest PTU sizing tested "
            f"(p{best_p} → {int(s['ptus'])} PTUs) costs {_fmt_cost(best_cost)}, which is "
            f"{_fmt_cost(-savings)} **more** than the PAYGO baseline "
            f"({_fmt_cost(paygo_baseline)}). PTU only wins above this traffic envelope."
        )

    return (
        f"**Recommendation: provision {int(s['ptus'])} PTUs (sized to p{best_p}).** "
        f"This delivers an estimated {ptu_term} cost of {_fmt_cost(best_cost)} vs "
        f"{_fmt_cost(paygo_baseline)} on PAYGO — a saving of {_fmt_cost(savings)} "
        f"({savings_pct:.1f}%). PTU covers {s['ptu_covered_token_pct']:.1f}% of tokens; "
        f"the remaining {s['spillover_token_pct']:.1f}% spill over to PAYGO."
    )


def _render_markdown(
    df: pd.DataFrame,
    result: dict[str, Any],
    meta: dict[str, Any],
) -> str:
    ptu_term: str = meta["ptu_term"]
    paygo_monthly = result["paygo_monthly"]
    time_period_months = result["time_period_months"]
    minute_count = len(df)
    start, end = df["minute_bin"].min(), df["minute_bin"].max()

    parts = [
        f"# PAYGO vs PTU cost analysis — {meta['model']} ({meta['tier']})",
        "",
        f"_Generated: {meta['generated_at']}_  ",
        f"_Source: **{meta['source']}**_  ",
        f"_PTU term: **{ptu_term}** • Output weight: {meta['ptu_output_weight']}_",
        "",
        "## Input window",
        "",
        f"- Minute bins analysed: **{minute_count:,}**",
        f"- Time range: **{start}** → **{end}**",
        f"- Equivalent months observed: **{time_period_months:.2f}**",
        f"- Total tokens in window: **{_fmt_num(result['total_ptu_tokens'])}**",
        "",
        "## TPM percentile snapshot",
        "",
        _percentile_table(result["percentile_values"]),
        "",
        "## PAYGO Baseline",
        "",
        _paygo_table(result["paygo_breakdown"]),
        "",
        "## PTU Sizing scenarios",
        "",
        _scenarios_table(result["ptu_scenarios"], paygo_monthly, ptu_term),
        "",
        "## Recommendation",
        "",
        _recommend(result["ptu_scenarios"], paygo_monthly, ptu_term),
        "",
        "## Pricing snapshot used",
        "",
        "```json",
        json.dumps(meta["pricing_snapshot"], indent=2),
        "```",
        "",
    ]
    return "\n".join(parts)


def _plot_tpm_over_time(
    df: pd.DataFrame,
    ptu_scenarios: dict[int, dict[str, Any]],
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(df["minute_bin"], df["total_tpm"], linewidth=0.7, label="Total TPM")

    cmap = plt.get_cmap("tab10")
    for i, p in enumerate(sorted(ptu_scenarios)):
        cap = ptu_scenarios[p]["ptu_capacity"]
        ptus = int(ptu_scenarios[p]["ptus"])
        ax.axhline(
            cap,
            color=cmap(i),
            linestyle="--",
            linewidth=1.0,
            label=f"p{p} capacity ({ptus} PTUs = {_fmt_num(cap)} TPM)",
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Tokens per minute")
    ax.set_title("Total TPM over time vs PTU capacity scenarios")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def _plot_sizing_bars(
    ptu_scenarios: dict[int, dict[str, Any]],
    paygo_monthly: float,
    ptu_term: str,
    out_path: Path,
) -> None:
    cost_key = "total_yearly" if ptu_term == "yearly" else "total_monthly"
    ptu_cost_key = "ptu_yearly_cost" if ptu_term == "yearly" else "ptu_monthly_cost"
    term_label = "Yearly" if ptu_term == "yearly" else "Monthly"
    paygo_baseline = paygo_monthly * 12 if ptu_term == "yearly" else paygo_monthly

    percentiles = sorted(ptu_scenarios)
    labels = [f"p{p}" for p in percentiles]
    ptu_costs = [ptu_scenarios[p][ptu_cost_key] for p in percentiles]
    spill_costs = [
        ptu_scenarios[p]["spillover_cost"] * (12 if ptu_term == "yearly" else 1)
        for p in percentiles
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(labels))
    width = 0.55

    ax.bar(x, ptu_costs, width, label="PTU base cost", color="#1f77b4")
    ax.bar(x, spill_costs, width, bottom=ptu_costs, label="Spillover (PAYGO)", color="#ff7f0e")
    ax.axhline(
        paygo_baseline,
        color="#2ca02c",
        linestyle="--",
        linewidth=1.5,
        label=f"PAYGO baseline ({_fmt_cost(paygo_baseline)})",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel(f"{term_label} cost (USD)")
    ax.set_title(f"PTU sizing scenarios — {term_label.lower()} cost vs PAYGO")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for i, (base, spill) in enumerate(zip(ptu_costs, spill_costs)):
        total = base + spill
        ax.text(i, total, _fmt_cost(total), ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def render_report(
    df: pd.DataFrame,
    result: dict[str, Any],
    meta: dict[str, Any],
    out_dir: Path,
) -> dict[str, Path]:
    """Render report.md, report.json and 2 PNG charts under `out_dir`.

    Returns a dict mapping logical names to output paths.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {**meta, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    paths = {
        "markdown": out_dir / "report.md",
        "json": out_dir / "report.json",
        "tpm_chart": out_dir / "tpm_over_time.png",
        "sizing_chart": out_dir / "ptu_sizing_scenarios.png",
    }

    paths["markdown"].write_text(_render_markdown(df, result, meta), encoding="utf-8")

    payload = {
        "metadata": meta,
        "analysis": {
            "percentile_values": {str(k): float(v) for k, v in result["percentile_values"].items()},
            "time_period_months": result["time_period_months"],
            "paygo_monthly": result["paygo_monthly"],
            "paygo_breakdown": result["paygo_breakdown"],
            "ptu_scenarios": {
                str(p): {
                    k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                    for k, v in s.items()
                }
                for p, s in result["ptu_scenarios"].items()
            },
            "total_ptu_tokens": float(result["total_ptu_tokens"]),
        },
    }
    paths["json"].write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    _plot_tpm_over_time(df, result["ptu_scenarios"], paths["tpm_chart"])
    _plot_sizing_bars(
        result["ptu_scenarios"], result["paygo_monthly"], meta["ptu_term"], paths["sizing_chart"]
    )

    return paths

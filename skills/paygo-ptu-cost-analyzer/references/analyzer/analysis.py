from __future__ import annotations

import numpy as np
import pandas as pd


def run_analysis(
    df: pd.DataFrame,
    percentiles: list[int],
    *,
    ptu_output_weight: int,
    ptu_capacity_tpm: float,
    ptu_min_deployment: float,
    ptu_increment: float,
    effective_paygo_input_per_m: float,
    effective_paygo_cached_input_per_m: float,
    effective_paygo_output_per_m: float,
    effective_ptu_monthly_price: float,
    effective_ptu_yearly_price: float,
) -> dict:
    """Run the shared pre-calculations used across pages (mutates df in place)."""
    # Compute derived columns (idempotent if already done, but lightweight)
    df["total_tpm"] = df["input_tokens_sum"] + df["output_tokens_sum"]
    df["non_cached_input"] = df["input_tokens_sum"] - df["cached_tokens_sum"]
    df["effective_output_tpm"] = df["output_tokens_sum"] * ptu_output_weight
    df["ptu_billable_tpm"] = df["non_cached_input"] + df["effective_output_tpm"]

    # Global metrics
    percentile_values = {p: np.percentile(df["total_tpm"], p) for p in percentiles}
    ptu_percentile_values = {
        p: np.percentile(df["ptu_billable_tpm"], p) for p in percentiles
    }
    time_period_minutes = len(df)
    time_period_months = (time_period_minutes / 60 / 24) / 30

    # Cost Baseline (PAYGO)
    total_non_cached_input = df["non_cached_input"].sum()
    total_cached = df["cached_tokens_sum"].sum()
    total_output = df["output_tokens_sum"].sum()
    total_ptu_tokens = total_non_cached_input + total_cached + total_output

    paygo_non_cached_input_cost_monthly = (
        total_non_cached_input / 1e6 * effective_paygo_input_per_m
    ) / time_period_months
    paygo_cached_input_cost_monthly = (
        total_cached / 1e6 * effective_paygo_cached_input_per_m
    ) / time_period_months
    paygo_output_cost_monthly = (
        total_output / 1e6 * effective_paygo_output_per_m
    ) / time_period_months
    paygo_monthly = (
        paygo_non_cached_input_cost_monthly
        + paygo_cached_input_cost_monthly
        + paygo_output_cost_monthly
    )

    paygo_breakdown = {
        "non_cached_input_cost_monthly": paygo_non_cached_input_cost_monthly,
        "cached_input_cost_monthly": paygo_cached_input_cost_monthly,
        "output_cost_monthly": paygo_output_cost_monthly,
        "total_cost_monthly": paygo_monthly,
    }

    def calculate_ptu_scenario(percentile: int) -> dict:
        billable_threshold = np.percentile(df["ptu_billable_tpm"], percentile)
        raw_ptus = np.ceil(billable_threshold / ptu_capacity_tpm)
        ptus = max(
            ptu_min_deployment, np.ceil(raw_ptus / ptu_increment) * ptu_increment
        )
        ptu_capacity = ptus * ptu_capacity_tpm

        spillover_tpm = df["ptu_billable_tpm"].apply(lambda x: max(0, x - ptu_capacity))
        spillover_ratio = spillover_tpm / df["ptu_billable_tpm"].replace(0, 1)

        total_ptu_billable_tpm = df["ptu_billable_tpm"].sum()
        if total_ptu_billable_tpm > 0:
            ptu_demand_spillover_pct = min(
                100.0, max(0.0, 100 * spillover_tpm.sum() / total_ptu_billable_tpm)
            )
            ptu_demand_covered_pct = 100.0 - ptu_demand_spillover_pct
        else:
            ptu_demand_spillover_pct = 0.0
            ptu_demand_covered_pct = 0.0

        spill_input = (df["non_cached_input"] * spillover_ratio).sum()
        spill_output = (df["output_tokens_sum"] * spillover_ratio).sum()
        spill_cached = (df["cached_tokens_sum"] * spillover_ratio).sum()
        spill_tokens = spill_input + spill_output + spill_cached

        if total_ptu_tokens > 0:
            spillover_token_pct = min(
                100.0, max(0.0, 100 * spill_tokens / total_ptu_tokens)
            )
            ptu_covered_token_pct = 100.0 - spillover_token_pct
        else:
            spillover_token_pct = 0.0
            ptu_covered_token_pct = 0.0

        spill_non_cached_input_cost_monthly = (
            spill_input / 1e6 * effective_paygo_input_per_m
        ) / time_period_months
        spill_cached_input_cost_monthly = (
            spill_cached / 1e6 * effective_paygo_cached_input_per_m
        ) / time_period_months
        spill_output_cost_monthly = (
            spill_output / 1e6 * effective_paygo_output_per_m
        ) / time_period_months
        spill_cost = (
            spill_non_cached_input_cost_monthly
            + spill_cached_input_cost_monthly
            + spill_output_cost_monthly
        )

        return {
            "percentile": percentile,
            "threshold": billable_threshold,
            "ptus": ptus,
            "ptu_capacity": ptu_capacity,
            "spillover_pct": 100 * (spillover_tpm > 0).sum() / len(df),
            "ptu_demand_covered_pct": ptu_demand_covered_pct,
            "ptu_demand_spillover_pct": ptu_demand_spillover_pct,
            "ptu_covered_token_pct": ptu_covered_token_pct,
            "spillover_token_pct": spillover_token_pct,
            "ptu_monthly_cost": ptus * effective_ptu_monthly_price,
            "ptu_yearly_cost": ptus * effective_ptu_yearly_price,
            "spill_non_cached_input_cost_monthly": spill_non_cached_input_cost_monthly,
            "spill_cached_input_cost_monthly": spill_cached_input_cost_monthly,
            "spill_output_cost_monthly": spill_output_cost_monthly,
            "spillover_cost": spill_cost,
            "total_monthly": (ptus * effective_ptu_monthly_price) + spill_cost,
            "total_yearly": (ptus * effective_ptu_yearly_price) + spill_cost,
        }

    ptu_scenarios = {p: calculate_ptu_scenario(p) for p in percentiles}

    return {
        "percentile_values": percentile_values,
        "ptu_percentile_values": ptu_percentile_values,
        "time_period_months": time_period_months,
        "paygo_monthly": paygo_monthly,
        "paygo_breakdown": paygo_breakdown,
        "ptu_scenarios": ptu_scenarios,
        "total_ptu_tokens": total_ptu_tokens,
    }

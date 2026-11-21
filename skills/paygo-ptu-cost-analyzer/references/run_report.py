#!/usr/bin/env python3
"""Headless PAYGO vs PTU cost analysis report generator.

Input modes (mutually exclusive):

  --csv <path>                          # CSV matching required schema
  --workspace <id> [--kql --time-range  # Log Analytics workspace
                    --deployment]
  --synthetic [--days N]                # Self-generated demo data
  --router-metrics <json>               # Router-aware: saved Azure Monitor metrics
  --router-resource <foundry-id>        # Router-aware: live Azure Monitor metrics

Router-aware modes size PTU for `--model` as the SERVED model across every
deployment (router-managed + your own), add a "Router-aware load" section and
a direct-only vs with-routed PTU what-if with the router fee.

Outputs (under --out-dir):
  report.md, report.json,
  tpm_over_time.png, ptu_sizing_scenarios.png

Required CSV schema:
  minute_bin, input_tokens_sum, cached_tokens_sum, output_tokens_sum
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `analyzer` importable when run as a script
THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from datetime import datetime, timezone  # noqa: E402

import pandas as pd  # noqa: E402

import router_metrics  # noqa: E402

from analyzer import (  # noqa: E402
    build_default_kql_query,
    generate_synthetic_data,
    load_kql_template,
    REQUIRED_COLUMNS,
    load_models_config,
    normalize_usage_dataframe,
    query_log_analytics,
    run_analysis,
)
from render_report import render_report  # noqa: E402


DEFAULT_KQL_PATH = THIS_DIR / "queries" / "default.kql"


def _parse_percentiles(raw: str) -> list[int]:
    out = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid percentile: {token!r}") from exc
        if not (0 < value < 100):
            raise argparse.ArgumentTypeError(f"Percentile out of range (0,100): {value}")
        out.append(value)
    if not out:
        raise argparse.ArgumentTypeError("At least one percentile is required")
    return sorted(set(out))


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_report",
        description="Generate a headless PAYGO vs PTU cost analysis report.",
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", type=Path, help="Path to a usage CSV.")
    src.add_argument("--workspace", help="Log Analytics workspace ID (GUID).")
    src.add_argument(
        "--synthetic", action="store_true", help="Generate synthetic demo data."
    )
    src.add_argument(
        "--router-metrics",
        type=Path,
        help="Azure Monitor metrics JSON (az monitor metrics list -o json or REST) split by "
        "ModelDeploymentName x ModelName. Enables the router-aware analysis.",
    )
    src.add_argument(
        "--router-resource",
        help="Foundry resource ID: fetch router-aware metrics live (DefaultAzureCredential, "
        "Monitoring Reader). Uses --time-range.",
    )

    # Router-aware options
    p.add_argument(
        "--router-deployment",
        action="append",
        default=[],
        help="Extra router deployment name (repeatable). Routers seen in ModelRouter* "
        "metrics or named model-router* are detected automatically.",
    )
    p.add_argument(
        "--router-fee-per-m",
        type=float,
        default=None,
        help="Router fee in USD per 1M input tokens. Default: Azure Retail Prices API "
        "meter for --tier in --router-region.",
    )
    p.add_argument(
        "--router-region",
        default="swedencentral",
        help="Region for the router fee lookup (default: swedencentral).",
    )
    p.add_argument(
        "--fee-excludes-cached",
        action="store_true",
        help="Do not charge the router fee on cached input (not documented either way).",
    )
    p.add_argument(
        "--watch-models",
        default=",".join(router_metrics.DEFAULT_WATCH_MODELS),
        help="Comma-separated served-model families to flag when routed traffic lands on them.",
    )
    p.add_argument(
        "--save-metrics",
        type=Path,
        default=None,
        help="With --router-resource, also save the fetched metrics JSON here.",
    )

    # KQL-mode options
    p.add_argument(
        "--kql",
        type=Path,
        default=DEFAULT_KQL_PATH,
        help="KQL template path (default: vendored default.kql).",
    )
    p.add_argument(
        "--time-range",
        default="7d",
        help="Log Analytics query range, e.g. 7d, 24h (default: 7d).",
    )
    p.add_argument(
        "--deployment",
        default="",
        help="Filter to a specific Cognitive Services deployment name (optional).",
    )

    # Synthetic-mode options
    p.add_argument(
        "--days",
        type=int,
        default=7,
        help="Synthetic data duration in days (default: 7).",
    )

    # Analysis options
    p.add_argument(
        "--model",
        default="gpt-5.4",
        help="Model slug from references/analyzer/models.json (default: gpt-5.4).",
    )
    p.add_argument(
        "--tier",
        choices=["global", "data_zone"],
        default="global",
        help="Pricing tier (default: global).",
    )
    p.add_argument(
        "--ptu-term",
        choices=["monthly", "yearly"],
        default="monthly",
        help="PTU billing term (default: monthly).",
    )
    p.add_argument(
        "--percentiles",
        type=_parse_percentiles,
        default=[50, 75, 90, 95, 99],
        help="Comma-separated percentiles to analyse (default: 50,75,90,95,99).",
    )
    p.add_argument(
        "--ptu-output-weight",
        type=float,
        default=None,
        help=(
            "Output-token weight applied to PTU billable TPM. When omitted, "
            "defaults to the model's ptu.output_weight from models.json "
            "(falls back to 1 if the catalog entry lacks it)."
        ),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("./paygo-ptu-report"),
        help="Output directory (default: ./paygo-ptu-report).",
    )
    return p


def _resolve_pricing(models: dict, model_slug: str, tier: str) -> dict:
    if model_slug not in models:
        raise SystemExit(
            f"Model '{model_slug}' not found in catalog. "
            f"Known: {', '.join(sorted(models))}"
        )
    entry = models[model_slug]
    paygo = entry["paygo"].get(tier)
    ptu = entry["ptu"].get(tier)
    if paygo is None or ptu is None:
        raise SystemExit(
            f"Tier '{tier}' has no pricing for model '{model_slug}'. "
            f"Try the other tier from models.json."
        )
    return {
        "display_name": entry.get("display_name", model_slug),
        "paygo": paygo,
        "ptu_pricing": ptu,
        "ptu_capacity_tpm": entry["ptu"]["capacity_tpm"],
        "ptu_min_deployment": entry["ptu"]["min_deployment"],
        "ptu_increment": entry["ptu"]["increment"],
        "ptu_output_weight": entry["ptu"].get("output_weight", 1),
    }


def _router_timespan(time_range: str) -> str:
    from analyzer import time_range_to_timedelta

    end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = end - time_range_to_timedelta(time_range)
    return f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}"


def _load_router_rows(args: argparse.Namespace) -> tuple[list[dict], str]:
    if args.router_metrics:
        if not args.router_metrics.exists():
            raise SystemExit(f"Metrics JSON not found: {args.router_metrics}")
        payload = json.loads(args.router_metrics.read_text(encoding="utf-8"))
        source = f"azure-monitor-metrics:{args.router_metrics}"
    else:
        timespan = _router_timespan(args.time_range)
        payload = router_metrics.fetch_metrics(args.router_resource, timespan)
        if args.save_metrics:
            args.save_metrics.parent.mkdir(parents=True, exist_ok=True)
            args.save_metrics.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        source = f"azure-monitor-metrics:{args.router_resource}@{timespan}"
    return router_metrics.parse_metrics_payload(payload), source


def _series_df(rows: list[dict], model: str, include_routed: bool, routers: list[str]) -> pd.DataFrame:
    series = router_metrics.minute_series(rows, model, include_routed=include_routed, router_deployments=routers)
    return normalize_usage_dataframe(pd.DataFrame(series, columns=list(REQUIRED_COLUMNS)))


def _load_input(args: argparse.Namespace) -> tuple[pd.DataFrame, str]:
    if args.synthetic:
        df = generate_synthetic_data(duration_days=args.days)
        return normalize_usage_dataframe(df), f"synthetic ({args.days} days)"
    if args.csv:
        if not args.csv.exists():
            raise SystemExit(f"CSV not found: {args.csv}")
        df = pd.read_csv(args.csv)
        return normalize_usage_dataframe(df), f"csv:{args.csv}"
    if args.workspace:
        template = load_kql_template(str(args.kql))
        query = build_default_kql_query(template, args.time_range, args.deployment)
        df = query_log_analytics(args.workspace, query, args.time_range)
        return df, f"loganalytics:{args.workspace}@{args.time_range}"
    raise SystemExit("No input source supplied (need --csv, --workspace, or --synthetic).")


def _analyze(df: pd.DataFrame, args: argparse.Namespace, pricing: dict, ptu_output_weight: float) -> dict:
    return run_analysis(
        df,
        percentiles=args.percentiles,
        ptu_output_weight=ptu_output_weight,
        ptu_capacity_tpm=pricing["ptu_capacity_tpm"],
        ptu_min_deployment=pricing["ptu_min_deployment"],
        ptu_increment=pricing["ptu_increment"],
        effective_paygo_input_per_m=pricing["paygo"]["input_per_m"],
        effective_paygo_cached_input_per_m=pricing["paygo"]["cached_input_per_m"],
        effective_paygo_output_per_m=pricing["paygo"]["output_per_m"],
        effective_ptu_monthly_price=pricing["ptu_pricing"]["monthly_price"],
        effective_ptu_yearly_price=pricing["ptu_pricing"]["yearly_price"],
    )


def _whatif_row(label: str, result: dict, percentile: int) -> dict:
    s = result["ptu_scenarios"][percentile]
    return {
        "label": label,
        "billable_tpm": float(result["ptu_percentile_values"][percentile]),
        "ptus": float(s["ptus"]),
        "paygo_monthly": float(result["paygo_monthly"]),
        "total_monthly": float(s["total_monthly"]),
    }


def _router_analysis(args: argparse.Namespace, models: dict, pricing: dict, ptu_output_weight: float):
    rows, source = _load_router_rows(args)
    routers = args.router_deployment
    summary = router_metrics.summarize(
        rows,
        router_deployments=routers,
        watch_models=[m for m in args.watch_models.split(",") if m.strip()],
        ptu_catalog=models.keys(),
        candidate_model=args.model,
    )
    routers = summary["router_deployments"]
    df = _series_df(rows, args.model, True, routers)
    if df[["input_tokens_sum", "output_tokens_sum"]].to_numpy().sum() == 0:
        served = ", ".join(r["model"] for r in summary["served_models"]) or "none"
        raise SystemExit(f"No tokens for served model '{args.model}' in the metrics. Served models: {served}")
    direct_df = _series_df(rows, args.model, False, routers)
    result = _analyze(df, args, pricing, ptu_output_weight)
    direct = _analyze(direct_df, args, pricing, ptu_output_weight)

    fee_per_m = args.router_fee_per_m
    fee_source = "--router-fee-per-m"
    if fee_per_m is None:
        fee_per_m = router_metrics.fetch_router_fee(args.router_region, args.tier)
        fee_source = f"Azure Retail Prices API ({router_metrics.ROUTER_FEE_METERS[args.tier]}, {args.router_region})"
    fee = router_metrics.router_fee(summary, fee_per_m, result["time_period_months"], args.fee_excludes_cached)
    fee["source"] = fee_source

    ref = 95 if 95 in args.percentiles else max(args.percentiles)
    whatif = {
        "model": args.model,
        "percentile": ref,
        "direct_only": _whatif_row("Direct traffic only", direct, ref),
        "with_routed": _whatif_row("Direct + routed (router absorbs into PTU)", result, ref),
    }
    router_meta = {**summary, "fee": fee, "whatif": whatif,
                   "markdown": router_metrics.render_markdown(summary, fee, whatif)}
    return df, source, result, router_meta


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    models = load_models_config()
    pricing = _resolve_pricing(models, args.model, args.tier)

    ptu_output_weight = (
        args.ptu_output_weight
        if args.ptu_output_weight is not None
        else pricing["ptu_output_weight"]
    )

    router_meta = None
    if args.router_metrics or args.router_resource:
        df, source, result, router_meta = _router_analysis(args, models, pricing, ptu_output_weight)
    else:
        df, source = _load_input(args)
        result = _analyze(df, args, pricing, ptu_output_weight)

    meta = {
        "model": pricing["display_name"],
        "model_slug": args.model,
        "tier": args.tier,
        "ptu_term": args.ptu_term,
        "percentiles": args.percentiles,
        "ptu_output_weight": ptu_output_weight,
        "source": source,
        "pricing_snapshot": {
            "paygo": pricing["paygo"],
            "ptu": {
                "capacity_tpm": pricing["ptu_capacity_tpm"],
                "min_deployment": pricing["ptu_min_deployment"],
                "increment": pricing["ptu_increment"],
                **pricing["ptu_pricing"],
            },
        },
    }

    if router_meta is not None:
        meta["router"] = router_meta

    paths = render_report(df, result, meta, args.out_dir)
    print(f"Wrote {paths['markdown']}")
    print(f"Wrote {paths['json']}")
    print(f"Wrote {paths['tpm_chart']}")
    print(f"Wrote {paths['sizing_chart']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

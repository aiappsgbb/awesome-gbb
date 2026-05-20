#!/usr/bin/env python3
"""Headless PAYGO vs PTU cost analysis report generator.

Three input modes (mutually exclusive):

  --csv <path>                          # CSV matching required schema
  --workspace <id> [--kql --time-range  # Log Analytics workspace
                    --deployment]
  --synthetic [--days N]                # Self-generated demo data

Outputs (under --out-dir):
  report.md, report.json,
  tpm_over_time.png, ptu_sizing_scenarios.png

Required CSV schema:
  minute_bin, input_tokens_sum, cached_tokens_sum, output_tokens_sum
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `analyzer` importable when run as a script
THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

import pandas as pd  # noqa: E402

from analyzer import (  # noqa: E402
    build_default_kql_query,
    generate_synthetic_data,
    load_kql_template,
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
        default=1.0,
        help="Output-token weight applied to PTU billable TPM (default: 1.0).",
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
    }


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


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    models = load_models_config()
    pricing = _resolve_pricing(models, args.model, args.tier)

    df, source = _load_input(args)

    result = run_analysis(
        df,
        percentiles=args.percentiles,
        ptu_output_weight=args.ptu_output_weight,
        ptu_capacity_tpm=pricing["ptu_capacity_tpm"],
        ptu_min_deployment=pricing["ptu_min_deployment"],
        ptu_increment=pricing["ptu_increment"],
        effective_paygo_input_per_m=pricing["paygo"]["input_per_m"],
        effective_paygo_cached_input_per_m=pricing["paygo"]["cached_input_per_m"],
        effective_paygo_output_per_m=pricing["paygo"]["output_per_m"],
        effective_ptu_monthly_price=pricing["ptu_pricing"]["monthly_price"],
        effective_ptu_yearly_price=pricing["ptu_pricing"]["yearly_price"],
    )

    meta = {
        "model": pricing["display_name"],
        "model_slug": args.model,
        "tier": args.tier,
        "ptu_term": args.ptu_term,
        "percentiles": args.percentiles,
        "ptu_output_weight": args.ptu_output_weight,
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

    paths = render_report(df, result, meta, args.out_dir)
    print(f"Wrote {paths['markdown']}")
    print(f"Wrote {paths['json']}")
    print(f"Wrote {paths['tpm_chart']}")
    print(f"Wrote {paths['sizing_chart']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

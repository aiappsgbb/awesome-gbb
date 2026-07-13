"""Vendored PAYGO vs PTU cost analysis library.

Sourced from aiappsgbb/ptu-paygo-mix @ 2636464 (2026-07-06).
`analysis.py`, `formatting.py`, and `models.json` are byte-identical to
upstream. `data.py` intentionally DIVERGES: upstream removed its live
Log-Analytics / KQL path (commit 14a5bec), but this skill retains those
helpers to power the CLI's `--workspace` mode. `data.py` is also stripped
of the `import streamlit as st` line and `@st.cache_data` decorators so
the module runs headless.

Pure pandas/numpy math; no Azure/PyPI side effects on import.
"""

from .analysis import run_analysis
from .data import (
    KQL_TEMPLATE_PATH,
    MODELS_CONFIG_PATH,
    REQUIRED_COLUMNS,
    build_default_kql_query,
    generate_synthetic_data,
    load_kql_template,
    load_models_config,
    normalize_usage_dataframe,
    query_log_analytics,
    time_range_to_timedelta,
)
from .formatting import fmt_cost, fmt_num

__all__ = [
    "KQL_TEMPLATE_PATH",
    "MODELS_CONFIG_PATH",
    "REQUIRED_COLUMNS",
    "build_default_kql_query",
    "fmt_cost",
    "fmt_num",
    "generate_synthetic_data",
    "load_kql_template",
    "load_models_config",
    "normalize_usage_dataframe",
    "query_log_analytics",
    "run_analysis",
    "time_range_to_timedelta",
]

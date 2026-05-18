"""Vendored PAYGO vs PTU cost analysis library.

Sourced from aiappsgbb/ptu-paygo-mix @ e1786f89 (2026-04-07).
Stripped of Streamlit cache decorators and the `import streamlit as st`
in data.py so the module runs headless.

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

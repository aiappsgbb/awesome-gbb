from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = [
    "minute_bin",
    "input_tokens_sum",
    "cached_tokens_sum",
    "output_tokens_sum",
]

KQL_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "kql" / "default_log_analytics_query.kql"
)
MODELS_CONFIG_PATH = Path(__file__).resolve().parent / "models.json"


def load_models_config() -> dict[str, dict]:
    """Load model definitions from models.json.

    Returns a dict keyed by model slug, each containing pricing and PTU specs.
    """
    with open(MODELS_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def normalize_usage_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and validate a token usage dataframe to required schema."""
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

    normalized = df.copy()
    normalized["minute_bin"] = pd.to_datetime(normalized["minute_bin"], errors="coerce")
    if normalized["minute_bin"].isna().any():
        raise ValueError("Column 'minute_bin' contains invalid datetime values.")

    for col in ["input_tokens_sum", "cached_tokens_sum", "output_tokens_sum"]:
        normalized[col] = pd.to_numeric(
            normalized[col].astype(str).str.replace(",", ""), errors="coerce"
        )
        if normalized[col].isna().any():
            raise ValueError(f"Column '{col}' contains non-numeric values.")
        normalized[col] = normalized[col].astype(int)

    if (normalized["cached_tokens_sum"] < 0).any():
        raise ValueError("Column 'cached_tokens_sum' contains negative values.")

    return normalized.sort_values("minute_bin").reset_index(drop=True)


def load_kql_template(path_str: str) -> str:
    """Load a KQL template from file."""
    return Path(path_str).read_text(encoding="utf-8")


def build_default_kql_query(
    template_query: str, time_range: str, deployment_name: str
) -> str:
    """Inject template placeholders for time range and optional deployment filter."""
    deployment_filter = ""
    if deployment_name.strip():
        safe_name = deployment_name.replace("\\", "\\\\").replace('"', '\\"')
        deployment_filter = f'| where ModelDeploymentName == "{safe_name}"'

    return template_query.replace("__TIME_RANGE__", time_range).replace(
        "__DEPLOYMENT_FILTER__", deployment_filter
    )


def time_range_to_timedelta(time_range: str) -> timedelta:
    """Convert a KQL-style relative range token (e.g. 7d, 24h) to timedelta."""
    if time_range.endswith("d"):
        return timedelta(days=int(time_range[:-1]))
    if time_range.endswith("h"):
        return timedelta(hours=int(time_range[:-1]))
    raise ValueError(f"Unsupported time range format: {time_range}")


def query_log_analytics(workspace_id: str, query: str, time_range: str) -> pd.DataFrame:
    """Query Azure Log Analytics and return normalized dataframe."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.monitor.query import LogsQueryClient, LogsQueryStatus
    except ImportError as exc:
        raise RuntimeError(
            "Missing Azure dependencies. Install 'azure-identity' and 'azure-monitor-query'."
        ) from exc

    credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)
    response = client.query_workspace(
        workspace_id=workspace_id,
        query=query,
        timespan=time_range_to_timedelta(time_range),
    )

    if response.status == LogsQueryStatus.PARTIAL:
        message = (
            response.partial_error.message
            if response.partial_error
            else "Query returned partial results."
        )
        raise RuntimeError(message)

    if response.status != LogsQueryStatus.SUCCESS:
        raise RuntimeError("Log Analytics query failed.")

    if not response.tables:
        raise ValueError("Log Analytics query returned no tables.")

    table = response.tables[0]
    column_names = [
        column.name if hasattr(column, "name") else str(column)
        for column in table.columns
    ]
    result_df = pd.DataFrame(table.rows, columns=column_names)
    if result_df.empty:
        raise ValueError("Log Analytics query returned no rows.")

    return normalize_usage_dataframe(result_df)


def generate_synthetic_data(
    duration_days: int = 7,
    base_tpm_business: int = 10_000_000,
    base_tpm_quiet: int = 1_600_000,
    noise_ratio: float = 0.3,
    burst_probability: float = 0.002,
    burst_intensity: float = 3.0,
    cached_ratio: float = 0.65,
    output_ratio: float = 0.111,
) -> pd.DataFrame:
    """Generate synthetic token consumption data with realistic patterns."""

    start_date = datetime(2026, 1, 19, 0, 0, 0)  # Monday
    total_minutes = duration_days * 24 * 60
    timestamps = [start_date + timedelta(minutes=i) for i in range(total_minutes)]

    def get_base_traffic(dt: datetime) -> float:
        hour = dt.hour
        is_weekend = dt.weekday() >= 5
        is_quiet = 2 <= hour < 6

        if is_weekend:
            return base_tpm_quiet * 0.6 if is_quiet else base_tpm_quiet * 0.8
        if is_quiet:
            return base_tpm_quiet
        # Lunch dip
        if 12 <= hour < 13:
            return base_tpm_business * 0.7
        return base_tpm_business

    base_traffic = np.array([get_base_traffic(ts) for ts in timestamps])
    noise = np.random.normal(0, base_traffic * noise_ratio)
    traffic = np.maximum(base_traffic + noise, 100)

    # Add burst events
    burst_mask = np.random.random(total_minutes) < burst_probability
    burst_multipliers = np.random.uniform(1.5, burst_intensity, total_minutes)
    traffic[burst_mask] *= burst_multipliers[burst_mask]

    # Extend bursts for realism
    for idx in np.where(burst_mask)[0]:
        for offset in range(1, np.random.randint(2, 6)):
            if idx + offset < total_minutes:
                decay = 1 - (offset / 5) * 0.5
                traffic[idx + offset] = max(traffic[idx + offset], traffic[idx] * decay)

    input_tokens = traffic.astype(int)
    cached_ratios = np.clip(
        np.random.normal(cached_ratio, 0.08, total_minutes), 0.1, 0.6
    )
    cached_tokens = (input_tokens * cached_ratios).astype(int)
    output_ratios = np.clip(
        np.random.normal(output_ratio, 0.03, total_minutes), 0.05, 0.5
    )
    output_tokens = (input_tokens * output_ratios).astype(int)

    return pd.DataFrame(
        {
            "minute_bin": timestamps,
            "input_tokens_sum": input_tokens,
            "cached_tokens_sum": cached_tokens,
            "output_tokens_sum": output_tokens,
        }
    )

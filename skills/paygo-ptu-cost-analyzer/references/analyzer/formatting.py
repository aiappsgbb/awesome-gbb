def fmt_num(n: float, prefix: str = "", suffix: str = "") -> str:
    """Format large numbers compactly: 1234567 -> 1.2M, 12345 -> 12.3K"""
    abs_n = abs(n)
    if abs_n >= 1_000_000:
        return f"{prefix}{n / 1_000_000:.1f}M{suffix}"
    if abs_n >= 1_000:
        return f"{prefix}{n / 1_000:.0f}K{suffix}"
    return f"{prefix}{n:.0f}{suffix}"


def fmt_cost(n: float, suffix: str = "") -> str:
    """Format cost values with full precision under $100K: $12,345 vs $1.2M"""
    abs_n = abs(n)
    if abs_n >= 1_000_000:
        return f"${n / 1_000_000:.1f}M{suffix}"
    if abs_n >= 1_000:
        return f"${n:,.0f}{suffix}"
    return f"${n:.0f}{suffix}"

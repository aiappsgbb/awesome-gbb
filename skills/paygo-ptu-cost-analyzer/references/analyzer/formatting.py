def fmt_num(n: float, prefix: str = "", suffix: str = "") -> str:
    """Format large numbers compactly: 1.2K, 3.4M, 5.6B, 7.8T."""
    abs_n = abs(n)
    if abs_n >= 1_000_000_000_000:
        return f"{prefix}{n / 1_000_000_000_000:.2f}T{suffix}"
    if abs_n >= 1_000_000_000:
        return f"{prefix}{n / 1_000_000_000:.2f}B{suffix}"
    if abs_n >= 1_000_000:
        return f"{prefix}{n / 1_000_000:.1f}M{suffix}"
    if abs_n >= 1_000:
        return f"{prefix}{n / 1_000:.0f}K{suffix}"
    return f"{prefix}{n:.0f}{suffix}"


def fmt_cost(n: float, suffix: str = "") -> str:
    """Format cost values: full digits under $1M, then $1.2M / $3.4B / $5.6T."""
    abs_n = abs(n)
    if abs_n >= 1_000_000_000_000:
        return f"${n / 1_000_000_000_000:.2f}T{suffix}"
    if abs_n >= 1_000_000_000:
        return f"${n / 1_000_000_000:.2f}B{suffix}"
    if abs_n >= 1_000_000:
        return f"${n / 1_000_000:.1f}M{suffix}"
    if abs_n >= 1_000:
        return f"${n:,.0f}{suffix}"
    return f"${n:.0f}{suffix}"

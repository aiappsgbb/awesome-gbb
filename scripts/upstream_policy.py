"""Shared schema-v2 policy for automatic versus manual upstream SHA checks."""

from typing import Any


def sha_tracking_policy(frontmatter: dict[str, Any]) -> tuple[str, str]:
    upstream = frontmatter.get("upstream")
    if upstream is None:
        return "automatic", ""
    if not isinstance(upstream, dict):
        raise ValueError("upstream must be a mapping")
    mode = upstream.get("sha_tracking", "automatic")
    if mode not in ("automatic", "manual"):
        raise ValueError("upstream.sha_tracking must be automatic | manual")
    reason = upstream.get("sha_tracking_reason", "")
    if not isinstance(reason, str):
        raise ValueError("upstream.sha_tracking_reason must be a string")
    if mode == "manual":
        if not reason.strip():
            raise ValueError("manual SHA tracking requires a non-empty sha_tracking_reason")
        if upstream.get("type") != "github_repo":
            raise ValueError("manual SHA tracking requires upstream.type=github_repo")
        for field in ("repo", "ref", "pinned_sha"):
            value = upstream.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"manual SHA tracking requires upstream.{field}")
    return mode, reason

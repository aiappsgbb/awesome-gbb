"""Canonical runtime evidence producer for foundry-agt.

Source of truth for the prose example in `../../SKILL.md § Runtime audit evidence`.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

SCHEMA = "foundry-agt-runtime-evidence/v1"
REQUIRED_FIELDS: tuple[str, ...] = (
    "event_id",
    "timestamp",
    "event_type",
    "agent_id",
    "session_id",
    "policy_name",
    "tool_name",
    "decision",
    "reason",
    "evaluation_ms",
)


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(str(value).strip())


def build_evidence(
    events: Iterable[Mapping[str, object]],
    *,
    policy_version: str,
    redaction_policy: str,
    retention_policy: str,
    integrity_verified: bool,
    captured_at: str,
) -> dict[str, object]:
    """Build a language-neutral runtime evidence record."""

    if not isinstance(redaction_policy, str) or not redaction_policy.strip():
        raise ValueError("redaction_policy must be a non-empty repository-relative path string")
    if not isinstance(retention_policy, str) or not retention_policy.strip():
        raise ValueError("retention_policy must be a non-empty repository-relative path string")

    events_list = list(events)
    allow_count = 0
    deny_count = 0
    all_session_ids_non_empty = True

    for index, event in enumerate(events_list):
        if not isinstance(event, Mapping):
            raise ValueError(f"event[{index}] must be a mapping")

        missing = [field for field in REQUIRED_FIELDS if field not in event]
        if missing:
            raise ValueError(f"event[{index}] missing required field(s): {', '.join(missing)}")

        decision = str(event["decision"]).strip().lower()
        if decision == "allow":
            allow_count += 1
        elif decision == "deny":
            deny_count += 1

        all_session_ids_non_empty = all_session_ids_non_empty and _has_value(event["session_id"])

    if allow_count < 1 or deny_count < 1:
        raise ValueError("runtime evidence requires at least one allow and one deny decision")

    required_fields_observed = sorted(REQUIRED_FIELDS)
    evidence = {
        "schema": SCHEMA,
        "captured_at": captured_at,
        "policy_version": policy_version,
        "events_observed": {"allow": allow_count, "deny": deny_count},
        "required_fields_observed": required_fields_observed,
        "audit_sink": {"kind": "append-only", "persistent": True},
        "telemetry_sink": {
            "kind": "application-insights",
            "trace_correlated": all_session_ids_non_empty,
        },
        "redaction_policy": redaction_policy,
        "retention_policy": retention_policy,
        "integrity_verified": integrity_verified,
    }
    return evidence


def write_evidence(path: str | Path, evidence: Mapping[str, object]) -> None:
    """Write evidence as deterministic JSON with parents created."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


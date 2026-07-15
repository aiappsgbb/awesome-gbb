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

# CloudEvent envelope fields that are safe to preserve for track_event correlation.
_SAFE_CE_ENVELOPE_FIELDS: frozenset[str] = frozenset({"id", "time", "type", "source"})


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(str(value).strip())


def extract_cloudevent_payload(event: object) -> dict[str, object]:
    """Extract the AGT payload fields from a flat or CloudEvent-enveloped mapping.

    Accepts two forms:
    - **Flat mapping** — a dict that already contains the AGT event fields
      directly.  Returns only the keys present in ``REQUIRED_FIELDS``.
    - **Standard CloudEvent mapping** — a dict whose ``data`` value is itself
      a mapping (the AGT event payload lives there).  Returns only the keys
      present in ``REQUIRED_FIELDS`` from ``data``, plus any non-sensitive
      CloudEvent envelope fields listed in ``_SAFE_CE_ENVELOPE_FIELDS``
      (``id``, ``time``, ``type``, ``source``) that are not already supplied
      by the payload.

    The previous pattern ``{k: v for k, v in event.items() if k in
    _SAFE_FIELDS}`` silently emits ``{}`` for standard CloudEvent envelopes
    because none of the envelope keys (``specversion``, ``type``, ``source``,
    ``data``, …) are in ``REQUIRED_FIELDS``.  This helper avoids that pitfall
    by detecting and unwrapping the envelope first.

    Args:
        event: The raw event object to process.

    Returns:
        A dict containing only the safe, non-sensitive payload fields.

    Raises:
        ValueError: If *event* is not a mapping.
        ValueError: If the ``data`` key is present but its value is not a
            mapping.
    """
    if not isinstance(event, Mapping):
        raise ValueError(
            f"event must be a mapping, got {type(event).__name__!r}"
        )

    if "data" not in event:
        # Flat mapping — extract REQUIRED_FIELDS directly.
        return {k: v for k, v in event.items() if k in REQUIRED_FIELDS}

    # CloudEvent envelope form.
    data = event["data"]
    if not isinstance(data, Mapping):
        raise ValueError(
            f"CloudEvent 'data' must be a mapping, got {type(data).__name__!r}"
        )

    payload: dict[str, object] = {k: v for k, v in data.items() if k in REQUIRED_FIELDS}

    # Preserve explicitly safe envelope metadata for track_event correlation.
    for key in _SAFE_CE_ENVELOPE_FIELDS:
        if key in event and key not in payload:
            payload[key] = event[key]

    return payload


def build_evidence(
    events: Iterable[Mapping[str, object]],
    *,
    policy_version: str,
    redaction_policy: str,
    retention_policy: str,
    integrity_verified: bool,
    captured_at: str,
) -> dict[str, object]:
    """Build a language-neutral runtime evidence record.

    Args:
        events: Iterable of per-event metadata mappings (REQUIRED_FIELDS only).
        policy_version: Semver or date-stamp string identifying the active
            policy set.
        redaction_policy: Repository-relative path to the redaction policy
            document (e.g. ``"docs/pii-redaction.md"``).  Must be a non-empty
            string — inline policy objects are not accepted because Threadlight
            path-presence verification requires a resolvable file path.
        retention_policy: Repository-relative path to the retention policy
            document (e.g. ``"infra/monitoring.bicep"``).  The referenced
            document must declare lifecycle, throughput scaling, and
            backpressure.  Only the path is committed; the document body is not.
        integrity_verified: Result of ``AuditLog.verify_integrity()``.
        captured_at: ISO-8601 timestamp of evidence capture.

    Returns:
        A dict representing the evidence record, safe to serialize and commit.

    Raises:
        ValueError: If *redaction_policy* or *retention_policy* is not a
            non-empty string.
        ValueError: If any event is not a mapping or is missing required fields.
        ValueError: If there is not at least one allow and one deny decision.
    """
    if not isinstance(redaction_policy, str) or not redaction_policy.strip():
        raise ValueError(
            "redaction_policy must be a non-empty repository-relative path string"
        )
    if not isinstance(retention_policy, str) or not retention_policy.strip():
        raise ValueError(
            "retention_policy must be a non-empty repository-relative path string"
        )

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
        "events_observed": len(events_list),
        "allow_count": allow_count,
        "deny_count": deny_count,
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


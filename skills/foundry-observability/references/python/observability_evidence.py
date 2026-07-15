"""Canonical operating-evidence normalizer for foundry-observability.

Builds normalised evidence documents from a human-authored operating profile,
encoding alert coverage, trace-content policy, sampling rates, evaluator parity,
retention, and telemetry/evaluation budget.  Threadlight production-ready checks
OBS-107..109 and EVAL-106 consume the emitted evidence artifact.

Public API::

    from observability_evidence import build_evidence, write_evidence, validate_profile_with_schema
    evidence = build_evidence(profile, captured_at="2026-07-15T10:00:00Z")
    write_evidence(evidence, "specs/observability-evidence.json")

Schema identifiers:
  - Input profile:   foundry-observability-profile/v1  (observability-profile.schema.json)
  - Output evidence: foundry-observability-evidence/v1 (emitted as ``schema`` field)

Evaluator parity:
  ``evaluator_parity`` is ``True`` iff ``evaluator_definition.environments`` is
  **exactly** ``{"dev", "ci", "production"}``.  Extra environments **invalidate**
  parity — the approved plan requires the canonical three-environment set to
  confirm shared rollout discipline across the full SDLC.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROFILE_SCHEMA_ID: str = "foundry-observability-profile/v1"
_EVIDENCE_SCHEMA_ID: str = "foundry-observability-evidence/v1"
_REQUIRED_ALERTS: frozenset[str] = frozenset({"failure", "latency", "token_cost", "quality_safety"})
_PARITY_ENVIRONMENTS: frozenset[str] = frozenset({"dev", "ci", "production"})
_SCHEMA_PATH: Path = Path(__file__).parent.parent / "observability-profile.schema.json"

# ── optional jsonschema import ─────────────────────────────────────────────────
try:
    import jsonschema as _jsonschema  # type: ignore[import]
    _HAS_JSONSCHEMA: bool = True
except ImportError:
    _jsonschema = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False


# ── stdlib-only field validators ───────────────────────────────────────────────


def _require_non_blank_string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a bool, got {type(value).__name__}")
    return value


def _require_real_in_unit_interval(value: Any, field: str) -> float:
    """Require a real (non-bool) finite number in [0, 1]."""
    if isinstance(value, bool):
        raise TypeError(f"{field} must be a number, not bool")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number, got {type(value).__name__}")
    f = float(value)
    if not math.isfinite(f):
        raise ValueError(f"{field} must be finite, got {value!r}")
    if not 0.0 <= f <= 1.0:
        raise ValueError(f"{field} must be in [0, 1], got {value!r}")
    return f


def _require_positive_finite_number(value: Any, field: str) -> float:
    """Require a real (non-bool) finite number > 0."""
    if isinstance(value, bool):
        raise TypeError(f"{field} must be a number, not bool")
    if not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a number, got {type(value).__name__}")
    f = float(value)
    if not math.isfinite(f):
        raise ValueError(f"{field} must be finite, got {value!r}")
    if f <= 0.0:
        raise ValueError(f"{field} must be > 0, got {value!r}")
    return f


def _require_integer_ge(value: Any, field: str, minimum: int) -> int:
    """Require a strict Python int (not bool, not float) >= minimum."""
    if isinstance(value, bool):
        raise TypeError(f"{field} must be an int, not bool")
    if not isinstance(value, int):
        raise TypeError(f"{field} must be an int, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{field} must be >= {minimum}, got {value!r}")
    return value


def _parse_utc_timestamp(value: Any, field: str) -> str:
    """Parse and canonicalize a timezone-aware UTC ISO-8601 string.

    Accepts both ``Z`` and ``+00:00`` suffixes; rejects naive timestamps
    (no timezone) and non-UTC offsets.  Returns the canonicalized form with
    an explicit ``+00:00`` suffix via :meth:`datetime.isoformat`.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string, got {type(value).__name__}")
    # Normalize Z → +00:00 because datetime.fromisoformat before 3.11 rejects Z.
    normalized = value.rstrip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(
            f"{field} is not a valid ISO-8601 timestamp: {value!r}: {exc}"
        ) from exc
    if dt.tzinfo is None:
        raise ValueError(
            f"{field} must be timezone-aware (UTC), got naive timestamp: {value!r}"
        )
    if dt.utcoffset().total_seconds() != 0:
        raise ValueError(
            f"{field} must be UTC (offset 0), got {value!r}"
        )
    return dt.replace(tzinfo=timezone.utc).isoformat()


# ── stdlib-only profile validator ──────────────────────────────────────────────


def _validate_profile_stdlib(profile: dict) -> None:
    """Validate profile structure using stdlib only.

    Always exercised even when jsonschema is available.
    Raises ValueError for missing/wrong-valued fields; TypeError for wrong types.
    """
    if not isinstance(profile, dict):
        raise TypeError(f"profile must be a dict, got {type(profile).__name__}")

    required = {
        "schema", "action_group", "alerts", "evaluator_definition",
        "trace_policy", "sampling", "retention_days", "monthly_budget_usd",
    }
    missing = required - set(profile.keys())
    if missing:
        raise ValueError(f"profile missing required fields: {sorted(missing)}")

    if profile["schema"] != _PROFILE_SCHEMA_ID:
        raise ValueError(
            f"profile.schema must be {_PROFILE_SCHEMA_ID!r}, got {profile['schema']!r}"
        )

    # action_group
    ag = profile["action_group"]
    if not isinstance(ag, dict):
        raise TypeError(f"action_group must be a dict, got {type(ag).__name__}")
    _require_non_blank_string(ag.get("resource_id", ""), "action_group.resource_id")
    _require_non_blank_string(ag.get("owner", ""), "action_group.owner")

    # alerts
    alerts = profile["alerts"]
    if not isinstance(alerts, dict):
        raise TypeError(f"alerts must be a dict, got {type(alerts).__name__}")
    missing_alerts = _REQUIRED_ALERTS - set(alerts.keys())
    if missing_alerts:
        raise ValueError(f"missing alert categories: {', '.join(sorted(missing_alerts))}")
    for category, value in alerts.items():
        _require_non_blank_string(value, f"alerts.{category}")

    # evaluator_definition
    ev = profile["evaluator_definition"]
    if not isinstance(ev, dict):
        raise TypeError(f"evaluator_definition must be a dict, got {type(ev).__name__}")
    _require_non_blank_string(ev.get("name", ""), "evaluator_definition.name")
    _require_non_blank_string(ev.get("version", ""), "evaluator_definition.version")
    if "environments" not in ev:
        raise ValueError("evaluator_definition missing required field: environments")
    if not isinstance(ev["environments"], list):
        raise TypeError(
            f"evaluator_definition.environments must be a list, got {type(ev['environments']).__name__}"
        )

    # trace_policy
    tp = profile["trace_policy"]
    if not isinstance(tp, dict):
        raise TypeError(f"trace_policy must be a dict, got {type(tp).__name__}")
    if "content_recording" not in tp:
        raise ValueError("trace_policy missing required field: content_recording")
    _require_strict_bool(tp["content_recording"], "trace_policy.content_recording")
    _require_non_blank_string(tp.get("redaction_policy", ""), "trace_policy.redaction_policy")
    _require_non_blank_string(tp.get("readers_group", ""), "trace_policy.readers_group")

    # sampling
    sp = profile["sampling"]
    if not isinstance(sp, dict):
        raise TypeError(f"sampling must be a dict, got {type(sp).__name__}")
    for key in ("traces", "continuous_evaluation"):
        if key not in sp:
            raise ValueError(f"sampling missing required field: {key}")
        _require_real_in_unit_interval(sp[key], f"sampling.{key}")

    # retention_days
    _require_integer_ge(profile["retention_days"], "retention_days", 30)

    # monthly_budget_usd
    _require_positive_finite_number(profile["monthly_budget_usd"], "monthly_budget_usd")


# ── public API ─────────────────────────────────────────────────────────────────


def validate_profile_with_schema(profile: dict) -> None:
    """Validate an operating profile.

    Always runs stdlib validation first.  If jsonschema is installed, also
    validates against the bundled ``observability-profile.schema.json``.
    """
    _validate_profile_stdlib(profile)
    if _HAS_JSONSCHEMA and _SCHEMA_PATH.exists():
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        _jsonschema.validate(instance=profile, schema=schema)


def build_evidence(profile: dict, *, captured_at: str) -> dict[str, Any]:
    """Build a normalised operating-evidence document from a profile.

    Does **not** mutate ``profile``.

    Parameters
    ----------
    profile:
        An operating profile conforming to ``foundry-observability-profile/v1``.
    captured_at:
        Timezone-aware UTC ISO-8601 string for the evidence capture time.
        Both ``Z`` and ``+00:00`` are accepted; the output is canonicalized to
        ``+00:00``.

    Returns
    -------
    dict
        Evidence document with ``schema: foundry-observability-evidence/v1``.

    Raises
    ------
    ValueError
        If required fields are missing, out-of-range, or malformed.
    TypeError
        If any field carries the wrong Python type.
    """
    _validate_profile_stdlib(profile)
    ts = _parse_utc_timestamp(captured_at, "captured_at")

    ev_def = profile["evaluator_definition"]
    environments: frozenset[str] = frozenset(ev_def["environments"])
    evaluator_parity: bool = environments == _PARITY_ENVIRONMENTS

    alerts: dict = profile["alerts"]
    ag: dict = profile["action_group"]
    tp: dict = profile["trace_policy"]
    sp: dict = profile["sampling"]

    evidence: dict[str, Any] = {
        "schema": _EVIDENCE_SCHEMA_ID,
        "captured_at": ts,
        "action_group": {
            "resource_id": ag["resource_id"],
            "owner": ag["owner"],
        },
        "alert_categories": sorted(_REQUIRED_ALERTS),
        "alerts": dict(sorted(alerts.items())),
        "evaluator_definition": {
            "name": ev_def["name"],
            "version": ev_def["version"],
            "environments": sorted(ev_def["environments"]),
        },
        "evaluator_parity": evaluator_parity,
        "trace_policy": {
            "content_recording": tp["content_recording"],
            "redaction_policy": tp["redaction_policy"],
            "readers_group": tp["readers_group"],
        },
        "sampling": {
            "continuous_evaluation": float(sp["continuous_evaluation"]),
            "traces": float(sp["traces"]),
        },
        "retention_days": profile["retention_days"],
        "monthly_budget_usd": float(profile["monthly_budget_usd"]),
    }
    return evidence


def write_evidence(evidence: dict, path: "str | Path") -> None:
    """Write an evidence document as deterministic JSON with a trailing newline.

    Creates all parent directories as needed.  The output is sorted-key JSON so
    repeated calls with identical evidence produce byte-identical files.

    Parameters
    ----------
    evidence:
        Dict returned by :func:`build_evidence`.
    path:
        Destination file path (string or :class:`pathlib.Path`).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

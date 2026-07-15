"""Canonical evaluator-trust contract helper for foundry-evals.

Source of truth for the evaluator-trust contract in `../../SKILL.md § Trustworthy Evaluation Workflow`.

Builds normalised trust-evidence documents from a trust profile and a calibration
snapshot, encoding the reliability and pin checks that pilots require before promoting
an evaluation stack to production.

Public API::

    from eval_trust import build_trust_evidence, write_trust_evidence, validate_profile_with_schema
    evidence = build_trust_evidence(profile, calibration)
    write_trust_evidence(evidence, "evals/trust-evidence.json")

Schema identifiers:
  - Input profile:   foundry-evals-trust-profile/v1  (trust-profile.schema.json)
  - Output evidence: foundry-evals-trust-evidence/v1 (emitted as ``$schema`` field)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_EVIDENCE_SCHEMA_ID: str = "foundry-evals-trust-evidence/v1"
_VALID_ROLES: frozenset[str] = frozenset({"gate", "trend", "human_review"})
_SCHEMA_PATH: Path = Path(__file__).parent.parent / "trust-profile.schema.json"

# ── optional jsonschema import ────────────────────────────────────────────────
try:
    import jsonschema as _jsonschema  # type: ignore[import]
    _HAS_JSONSCHEMA: bool = True
except ImportError:
    _jsonschema = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False

# ── stdlib-only profile validator ─────────────────────────────────────────────


def _is_non_blank_string(value: str) -> bool:
    return value.strip() != ""


def _validate_profile_stdlib(profile: dict) -> None:
    """Validate profile structure using stdlib only.

    Always exercised even when jsonschema is available.
    Raises ValueError for missing/wrong-valued fields; TypeError for wrong types.
    """
    if not isinstance(profile, dict):
        raise TypeError(f"profile must be a dict, got {type(profile).__name__}")

    required = {"unit_of_analysis", "evaluators", "threshold_rationale", "last_calibrated_at", "sampling"}
    missing = required - set(profile.keys())
    if missing:
        raise ValueError(f"profile missing required fields: {sorted(missing)}")

    if profile["unit_of_analysis"] != "session":
        raise ValueError(
            f"unit_of_analysis must be 'session', got {profile['unit_of_analysis']!r}"
        )

    evaluators = profile["evaluators"]
    if not isinstance(evaluators, list) or len(evaluators) == 0:
        raise ValueError("evaluators must be a non-empty list")

    for i, ev in enumerate(evaluators):
        if not isinstance(ev, dict):
            raise TypeError(f"evaluators[{i}] must be a dict, got {type(ev).__name__}")
        ev_required = {"name", "role", "evaluator_version", "judge", "threshold"}
        ev_missing = ev_required - set(ev.keys())
        if ev_missing:
            raise ValueError(f"evaluators[{i}] missing required fields: {sorted(ev_missing)}")

        if not isinstance(ev["name"], str) or not ev["name"]:
            raise ValueError(f"evaluators[{i}].name must be a non-empty string")

        if ev["role"] not in _VALID_ROLES:
            raise ValueError(
                f"evaluators[{i}].role must be one of {sorted(_VALID_ROLES)}, got {ev['role']!r}"
            )

        if not isinstance(ev["evaluator_version"], str):
            raise TypeError(
                f"evaluators[{i}].evaluator_version must be a string, got {type(ev['evaluator_version']).__name__}"
            )
        if not _is_non_blank_string(ev["evaluator_version"]):
            raise ValueError(f"evaluators[{i}].evaluator_version must be a non-empty string")

        judge = ev["judge"]
        if not isinstance(judge, dict):
            raise TypeError(
                f"evaluators[{i}].judge must be a dict, got {type(judge).__name__}"
            )
        judge_required = {"deployment", "model", "version"}
        judge_missing = judge_required - set(judge.keys())
        if judge_missing:
            raise ValueError(
                f"evaluators[{i}].judge missing required fields: {sorted(judge_missing)}"
            )
        for field in judge_required:
            if not isinstance(judge[field], str):
                raise TypeError(
                    f"evaluators[{i}].judge.{field} must be a string, got {type(judge[field]).__name__}"
                )
            if not _is_non_blank_string(judge[field]):
                raise ValueError(
                    f"evaluators[{i}].judge.{field} must be a non-empty string"
                )

        if not isinstance(ev["threshold"], (int, float)) or isinstance(ev["threshold"], bool):
            raise TypeError(
                f"evaluators[{i}].threshold must be a number, got {type(ev['threshold']).__name__}"
            )

    if not isinstance(profile["threshold_rationale"], str):
        raise TypeError(
            f"threshold_rationale must be a string, got {type(profile['threshold_rationale']).__name__}"
        )

    if not isinstance(profile["last_calibrated_at"], str):
        raise TypeError(
            f"last_calibrated_at must be a string, got {type(profile['last_calibrated_at']).__name__}"
        )

    sampling = profile["sampling"]
    if not isinstance(sampling, dict):
        raise TypeError(f"sampling must be a dict, got {type(sampling).__name__}")
    if sampling.get("evaluation") != "diversity":
        raise ValueError(
            f"sampling.evaluation must be 'diversity', got {sampling.get('evaluation')!r}"
        )
    if sampling.get("sla") != "uniform":
        raise ValueError(
            f"sampling.sla must be 'uniform', got {sampling.get('sla')!r}"
        )


def _validate_calibration(calibration: dict) -> None:
    """Validate calibration data structure.

    Raises ValueError for missing fields or out-of-range values; TypeError for wrong types.
    """
    if not isinstance(calibration, dict):
        raise TypeError(f"calibration must be a dict, got {type(calibration).__name__}")

    required = {"captured_at", "known_good", "known_bad", "repeated_runs", "agreement", "flip_rate"}
    missing = required - set(calibration.keys())
    if missing:
        raise ValueError(f"calibration missing required fields: {sorted(missing)}")

    if not isinstance(calibration["captured_at"], str):
        raise TypeError(
            f"calibration.captured_at must be a string, got {type(calibration['captured_at']).__name__}"
        )

    for field in ("known_good", "known_bad", "repeated_runs"):
        val = calibration[field]
        if not isinstance(val, int) or isinstance(val, bool):
            raise TypeError(
                f"calibration.{field} must be an int, got {type(val).__name__}"
            )

    for field in ("agreement", "flip_rate"):
        val = calibration[field]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            raise TypeError(
                f"calibration.{field} must be a number, got {type(val).__name__}"
            )
        if not (0.0 <= float(val) <= 1.0):
            raise ValueError(
                f"calibration.{field} must be in [0, 1], got {val}"
            )


# ── derived-value helpers ─────────────────────────────────────────────────────


def _compute_pins(evaluators: list) -> bool:
    """Return True iff ALL evaluators have all version pin fields as non-empty strings.

    Validates every entry before returning True; never falsely emits True.
    """
    for ev in evaluators:
        ev_ver = ev.get("evaluator_version")
        if not isinstance(ev_ver, str) or not _is_non_blank_string(ev_ver):
            return False
        judge = ev.get("judge") if isinstance(ev.get("judge"), dict) else {}
        for field in ("deployment", "model", "version"):
            val = judge.get(field)
            if not isinstance(val, str) or not _is_non_blank_string(val):
                return False
    return True


def _compute_reliability(calibration: dict) -> bool:
    """Return True iff calibration meets all reliability thresholds."""
    return (
        calibration["known_good"] > 0
        and calibration["known_bad"] > 0
        and calibration["repeated_runs"] >= 4
        and float(calibration["agreement"]) >= 0.80
        and float(calibration["flip_rate"]) <= 0.10
    )


# ── public API ────────────────────────────────────────────────────────────────


def validate_profile_with_schema(profile: dict) -> None:
    """Validate a trust profile.

    Always runs stdlib validation first.  If jsonschema is installed, also
    validates against the bundled ``trust-profile.schema.json``.
    """
    _validate_profile_stdlib(profile)
    if _HAS_JSONSCHEMA and _SCHEMA_PATH.exists():
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        _jsonschema.validate(instance=profile, schema=schema)


def build_trust_evidence(profile: dict, calibration: dict) -> dict[str, Any]:
    """Build a normalised trust-evidence document from a profile and calibration snapshot.

    Parameters
    ----------
    profile:
        A trust profile conforming to ``foundry-evals-trust-profile/v1``.
    calibration:
        Calibration statistics with ``captured_at``, ``known_good``, ``known_bad``,
        ``repeated_runs``, ``agreement``, and ``flip_rate``.

    Returns
    -------
    dict
        Evidence document with ``$schema: foundry-evals-trust-evidence/v1``.

    Raises
    ------
    ValueError
        If the profile or calibration are structurally invalid, if any evaluator
        role is missing or not one of ``{gate, trend, human_review}``, or if the
        ``groundedness`` evaluator is assigned ``role: gate`` while calibration is
        unreliable (agreement < 0.80 or flip_rate > 0.10 or repeated_runs < 4).
    TypeError
        If any field carries the wrong Python type.
    """
    _validate_profile_stdlib(profile)
    _validate_calibration(calibration)

    evaluators: list[dict] = profile["evaluators"]
    evaluator_roles: dict[str, str] = {ev["name"]: ev["role"] for ev in evaluators}
    pins: bool = _compute_pins(evaluators)
    reliable: bool = _compute_reliability(calibration)

    # Groundedness hard-gate: cannot be role=gate when calibration is not reliable.
    groundedness_role: Optional[str] = evaluator_roles.get("groundedness")
    if groundedness_role == "gate" and not reliable:
        raise ValueError(
            "Groundedness cannot be role 'gate' unless calibration is reliable "
            "(required: known_good>0, known_bad>0, repeated_runs>=4, "
            "agreement>=0.80, flip_rate<=0.10). "
            "Set groundedness role to 'human_review' or fix calibration first."
        )

    calibration_summary: dict[str, Any] = {
        "captured_at": calibration["captured_at"],
        "known_good": calibration["known_good"],
        "known_bad": calibration["known_bad"],
        "repeated_runs": calibration["repeated_runs"],
        "agreement": calibration["agreement"],
        "flip_rate": calibration["flip_rate"],
        "reliable": reliable,
    }

    evidence: dict[str, Any] = {
        "$schema": _EVIDENCE_SCHEMA_ID,
        "captured_at": calibration["captured_at"],
        "session": profile["unit_of_analysis"],
        "evaluator_roles": evaluator_roles,
        "judge_and_evaluator_versions_pinned": pins,
        "calibration": calibration_summary,
        "evaluator_reliability_ok": reliable,
        "threshold_rationale": profile["threshold_rationale"],
        "last_calibrated_at": profile["last_calibrated_at"],
    }

    # Optional P1 fields — pass through when present in profile.
    for optional_key in ("evaluation_design", "task_specific_rubric", "simulator", "sampling", "benchmark"):
        if optional_key in profile:
            evidence[optional_key] = profile[optional_key]

    return evidence


def write_trust_evidence(evidence: dict, path: "str | Path") -> None:
    """Write a trust-evidence document as deterministic JSON with a trailing newline.

    Creates all parent directories as needed.  The output is sorted-key JSON
    so repeated calls with identical evidence produce byte-identical files.

    Parameters
    ----------
    evidence:
        Dict returned by :func:`build_trust_evidence`.
    path:
        Destination file path (string or :class:`pathlib.Path`).
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

"""Unit tests for the foundry-evals evaluator-trust contract helper.

Covers: module import (TDD missing-first), valid normalization, evaluator roles,
version-pin flag, reliable/unreliable calibration, groundedness hard-gate rejection,
missing/invalid roles, malformed types, deterministic write, valid/invalid fixtures,
schema shape, stdlib-fallback path, and trust-profile.yaml / calibration-run.json
contract pins.

Written as ``unittest.TestCase`` (NOT pytest fixtures) because
``.github/workflows/skill-test.yml::unit-tests`` invokes::

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

``unittest discover`` cannot resolve pytest's ``tmp_path`` fixture.
"""
from __future__ import annotations

import copy
import importlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# ---------------------------------------------------------------------------
# Resolve skill module path once so every test class can use it.
# ---------------------------------------------------------------------------
_SKILL_DIR = (
    Path(__file__).resolve().parents[1].parent
    / "skills"
    / "foundry-evals"
    / "references"
    / "python"
)
_REFS_DIR = _SKILL_DIR.parent
_DATA_DIR = _REFS_DIR / "data"
_SCHEMA_PATH = _REFS_DIR / "trust-profile.schema.json"

if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

# ---------------------------------------------------------------------------
# Optional yaml import — used by trust-profile.yaml contract tests.
# ---------------------------------------------------------------------------
try:
    import yaml as _yaml  # type: ignore[import]
    _HAS_YAML = True
except ImportError:
    _yaml = None  # type: ignore[assignment]
    _HAS_YAML = False

# ---------------------------------------------------------------------------
# Optional jsonschema import — mirrored from the module under test.
# ---------------------------------------------------------------------------
try:
    import jsonschema as _jsonschema  # type: ignore[import]
    _HAS_JSONSCHEMA = True
except ImportError:
    _jsonschema = None
    _HAS_JSONSCHEMA = False

# ---------------------------------------------------------------------------
# Minimal fixture data reused across tests.
# ---------------------------------------------------------------------------

_VALID_PROFILE: dict = {
    "unit_of_analysis": "session",
    "evaluators": [
        {
            "name": "task_completion",
            "role": "gate",
            "evaluator_version": "1.0.0",
            "judge": {"deployment": "gpt-4o-mini-eval", "model": "gpt-4o-mini-2024-07-18", "version": "2024-07-18"},
            "threshold": 0.80,
        },
        {
            "name": "groundedness",
            "role": "human_review",
            "evaluator_version": "1.1.0",
            "judge": {"deployment": "gpt-4o-eval", "model": "gpt-4o-2024-11-20", "version": "2024-11-20"},
            "threshold": 0.85,
        },
    ],
    "threshold_rationale": "Calibrated against 50 known-good / 20 known-bad sessions.",
    "last_calibrated_at": "2025-01-10T14:00:00Z",
    "sampling": {"evaluation": "diversity", "sla": "uniform"},
}

_VALID_CALIBRATION: dict = {
    "captured_at": "2025-01-10T14:00:00Z",
    "known_good": 50,
    "known_bad": 20,
    "repeated_runs": 5,
    "agreement": 0.92,
    "flip_rate": 0.05,
}

_UNRELIABLE_CALIBRATION: dict = {
    "captured_at": "2025-01-10T14:00:00Z",
    "known_good": 5,
    "known_bad": 2,
    "repeated_runs": 2,  # < 4
    "agreement": 0.65,   # < 0.80
    "flip_rate": 0.20,   # > 0.10
}


def _p(**overrides) -> dict:
    """Return a deep copy of _VALID_PROFILE with overrides applied at top level."""
    d = copy.deepcopy(_VALID_PROFILE)
    d.update(overrides)
    return d


def _c(**overrides) -> dict:
    """Return a deep copy of _VALID_CALIBRATION with overrides applied at top level."""
    d = copy.deepcopy(_VALID_CALIBRATION)
    d.update(overrides)
    return d


# ===========================================================================
# TDD: import test — this is the first test that would fail if the module
# does not exist.
# ===========================================================================


class TestModuleImport(unittest.TestCase):
    """Verify the module can be imported and exposes the required public API."""

    def test_import_succeeds(self) -> None:
        """eval_trust can be imported from the skill references directory."""
        mod = importlib.import_module("eval_trust")
        self.assertIsNotNone(mod)

    def test_public_api_present(self) -> None:
        """Public functions exist on the imported module."""
        import eval_trust  # noqa: F401
        from eval_trust import (  # noqa: F401
            build_trust_evidence,
            validate_profile_with_schema,
            write_trust_evidence,
        )

    def test_schema_id_constant(self) -> None:
        """Module exposes _EVIDENCE_SCHEMA_ID constant."""
        import eval_trust
        self.assertEqual(eval_trust._EVIDENCE_SCHEMA_ID, "foundry-evals-trust-evidence/v1")


# ===========================================================================
# Profile stdlib validation
# ===========================================================================


class TestProfileValidationStdlib(unittest.TestCase):
    """Tests for _validate_profile_stdlib — always exercises the stdlib path."""

    def setUp(self) -> None:
        from eval_trust import _validate_profile_stdlib
        self._validate = _validate_profile_stdlib

    def test_valid_profile_passes(self) -> None:
        self._validate(copy.deepcopy(_VALID_PROFILE))  # must not raise

    def test_missing_unit_of_analysis(self) -> None:
        p = _p()
        del p["unit_of_analysis"]
        with self.assertRaises(ValueError) as ctx:
            self._validate(p)
        self.assertIn("unit_of_analysis", str(ctx.exception))

    def test_missing_evaluators(self) -> None:
        p = _p()
        del p["evaluators"]
        with self.assertRaises(ValueError) as ctx:
            self._validate(p)
        self.assertIn("evaluators", str(ctx.exception))

    def test_missing_threshold_rationale(self) -> None:
        p = _p()
        del p["threshold_rationale"]
        with self.assertRaises(ValueError):
            self._validate(p)

    def test_missing_last_calibrated_at(self) -> None:
        p = _p()
        del p["last_calibrated_at"]
        with self.assertRaises(ValueError):
            self._validate(p)

    def test_missing_sampling(self) -> None:
        p = _p()
        del p["sampling"]
        with self.assertRaises(ValueError):
            self._validate(p)

    def test_wrong_unit_of_analysis(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(unit_of_analysis="tenant"))
        self.assertIn("session", str(ctx.exception))

    def test_empty_evaluators_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(evaluators=[]))
        self.assertIn("non-empty", str(ctx.exception))

    def test_evaluators_not_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._validate(_p(evaluators="task_completion"))

    def test_invalid_role_raises_valueerror_in_stdlib_validation(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["role"] = "hard-gate"
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("gate", str(ctx.exception).lower())

    def test_missing_role_field_raises_valueerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[0]["role"]
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("role", str(ctx.exception))

    def test_missing_judge_fields_raises_valueerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[0]["judge"]["deployment"]
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("deployment", str(ctx.exception))

    def test_wrong_sampling_evaluation_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(sampling={"evaluation": "random", "sla": "uniform"}))
        self.assertIn("diversity", str(ctx.exception))

    def test_wrong_sampling_sla_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_p(sampling={"evaluation": "diversity", "sla": "best-effort"}))
        self.assertIn("uniform", str(ctx.exception))

    def test_threshold_rationale_wrong_type_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            self._validate(_p(threshold_rationale=42))
        self.assertIn("threshold_rationale", str(ctx.exception))

    def test_threshold_not_number_raises_typeerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["threshold"] = "high"
        with self.assertRaises(TypeError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("threshold", str(ctx.exception))

    def test_bool_threshold_raises_typeerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["threshold"] = True
        with self.assertRaises(TypeError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("threshold", str(ctx.exception))

    def test_evaluator_version_not_string_raises_typeerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["evaluator_version"] = 100
        with self.assertRaises(TypeError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("evaluator_version", str(ctx.exception))

    def test_judge_field_not_string_raises_typeerror(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["judge"]["model"] = 42
        with self.assertRaises(TypeError) as ctx:
            self._validate(_p(evaluators=evs))
        self.assertIn("model", str(ctx.exception))

    def test_whitespace_only_pin_fields_raise_valueerror(self) -> None:
        cases = (
            ("evaluator_version", lambda ev: ev.__setitem__("evaluator_version", "   ")),
            ("judge.deployment", lambda ev: ev["judge"].__setitem__("deployment", " \t")),
            ("judge.model", lambda ev: ev["judge"].__setitem__("model", "\n")),
            ("judge.version", lambda ev: ev["judge"].__setitem__("version", "  ")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
                mutate(evs[0])
                with self.assertRaises(ValueError) as ctx:
                    self._validate(_p(evaluators=evs))
                self.assertIn("non-empty", str(ctx.exception))

    def test_profile_not_dict_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError):
            self._validate(["not", "a", "dict"])

    def test_additional_properties_tolerated(self) -> None:
        """Unknown future keys on the profile are allowed — extensible design."""
        p = _p()
        p["future_feature"] = {"experimental": True}
        p["evaluators"][0]["custom_tag"] = "v2"
        self._validate(p)  # must not raise


# ===========================================================================
# Calibration validation
# ===========================================================================


class TestCalibrationValidation(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import _validate_calibration
        self._validate = _validate_calibration

    def test_valid_calibration_passes(self) -> None:
        self._validate(copy.deepcopy(_VALID_CALIBRATION))

    def test_missing_captured_at(self) -> None:
        c = _c()
        del c["captured_at"]
        with self.assertRaises(ValueError) as ctx:
            self._validate(c)
        self.assertIn("captured_at", str(ctx.exception))

    def test_missing_known_good(self) -> None:
        c = _c()
        del c["known_good"]
        with self.assertRaises(ValueError):
            self._validate(c)

    def test_agreement_out_of_range_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_c(agreement=1.5))
        self.assertIn("agreement", str(ctx.exception))

    def test_flip_rate_negative_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._validate(_c(flip_rate=-0.01))
        self.assertIn("flip_rate", str(ctx.exception))

    def test_known_good_float_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            self._validate(_c(known_good=50.5))
        self.assertIn("known_good", str(ctx.exception))

    def test_known_bad_string_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            self._validate(_c(known_bad="twenty"))
        self.assertIn("known_bad", str(ctx.exception))

    def test_repeated_runs_string_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            self._validate(_c(repeated_runs="five"))
        self.assertIn("repeated_runs", str(ctx.exception))

    def test_calibration_not_dict_raises(self) -> None:
        with self.assertRaises(TypeError):
            self._validate(None)


# ===========================================================================
# Pin computation
# ===========================================================================


class TestComputePins(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import _compute_pins
        self._compute = _compute_pins

    def test_all_pinned_returns_true(self) -> None:
        self.assertTrue(self._compute(_VALID_PROFILE["evaluators"]))

    def test_missing_evaluator_version_returns_false(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[0]["evaluator_version"]
        self.assertFalse(self._compute(evs))

    def test_empty_evaluator_version_returns_false(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["evaluator_version"] = ""
        self.assertFalse(self._compute(evs))

    def test_missing_judge_deployment_returns_false(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[0]["judge"]["deployment"]
        self.assertFalse(self._compute(evs))

    def test_missing_judge_model_returns_false(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[1]["judge"]["model"]
        self.assertFalse(self._compute(evs))

    def test_missing_judge_version_returns_false(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["judge"]["version"] = ""
        self.assertFalse(self._compute(evs))

    def test_whitespace_only_pin_fields_return_false(self) -> None:
        cases = (
            ("evaluator_version", lambda ev: ev.__setitem__("evaluator_version", "   ")),
            ("judge.deployment", lambda ev: ev["judge"].__setitem__("deployment", " \t")),
            ("judge.model", lambda ev: ev["judge"].__setitem__("model", "\n")),
            ("judge.version", lambda ev: ev["judge"].__setitem__("version", "  ")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
                mutate(evs[0])
                self.assertFalse(self._compute(evs))

    def test_only_first_evaluator_unpinned_returns_false(self) -> None:
        """Validates ALL entries — one bad entry means False."""
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["evaluator_version"] = ""
        self.assertFalse(self._compute(evs))

    def test_empty_evaluator_list_returns_true(self) -> None:
        """Empty list: vacuously true (no entries to fail)."""
        self.assertTrue(self._compute([]))


# ===========================================================================
# Reliability computation
# ===========================================================================


class TestComputeReliability(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import _compute_reliability
        self._compute = _compute_reliability

    def test_reliable_calibration_returns_true(self) -> None:
        self.assertTrue(self._compute(_VALID_CALIBRATION))

    def test_known_good_zero_returns_false(self) -> None:
        self.assertFalse(self._compute(_c(known_good=0)))

    def test_known_bad_zero_returns_false(self) -> None:
        self.assertFalse(self._compute(_c(known_bad=0)))

    def test_repeated_runs_three_returns_false(self) -> None:
        self.assertFalse(self._compute(_c(repeated_runs=3)))

    def test_repeated_runs_four_returns_true(self) -> None:
        self.assertTrue(self._compute(_c(repeated_runs=4)))

    def test_agreement_below_threshold_returns_false(self) -> None:
        self.assertFalse(self._compute(_c(agreement=0.79)))

    def test_agreement_at_threshold_returns_true(self) -> None:
        self.assertTrue(self._compute(_c(agreement=0.80)))

    def test_flip_rate_above_threshold_returns_false(self) -> None:
        self.assertFalse(self._compute(_c(flip_rate=0.11)))

    def test_flip_rate_at_threshold_returns_true(self) -> None:
        self.assertTrue(self._compute(_c(flip_rate=0.10)))


# ===========================================================================
# build_trust_evidence
# ===========================================================================


class TestBuildTrustEvidence(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import build_trust_evidence
        self._build = build_trust_evidence

    # --- valid normalization ---

    def test_valid_normalization_returns_dict(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertIsInstance(ev, dict)

    def test_schema_field_present(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["$schema"], "foundry-evals-trust-evidence/v1")

    def test_captured_at_from_calibration(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["captured_at"], _VALID_CALIBRATION["captured_at"])

    def test_session_unit_from_profile(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["session"], "session")

    # --- evaluator roles ---

    def test_evaluator_roles_map_correct(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["evaluator_roles"]["task_completion"], "gate")
        self.assertEqual(ev["evaluator_roles"]["groundedness"], "human_review")

    def test_all_evaluators_in_roles_map(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        for e in _VALID_PROFILE["evaluators"]:
            self.assertIn(e["name"], ev["evaluator_roles"])

    # --- version pins ---

    def test_pins_true_when_all_pinned(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertTrue(ev["judge_and_evaluator_versions_pinned"])

    def test_pins_false_when_version_missing(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        del evs[0]["evaluator_version"]
        # Must also add it back as empty string to pass stdlib type check while
        # testing pin logic — use a non-string to trigger type error path, or
        # remove only from _compute_pins by injecting directly.
        from eval_trust import _compute_pins
        self.assertFalse(_compute_pins(evs))

    # --- reliability ---

    def test_reliability_ok_true_for_reliable_calibration(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertTrue(ev["evaluator_reliability_ok"])
        self.assertTrue(ev["calibration"]["reliable"])

    def test_reliability_ok_false_for_unreliable_calibration(self) -> None:
        ev = self._build(_VALID_PROFILE, _UNRELIABLE_CALIBRATION)
        self.assertFalse(ev["evaluator_reliability_ok"])
        self.assertFalse(ev["calibration"]["reliable"])

    def test_unreliable_calibration_does_not_raise_without_groundedness_gate(self) -> None:
        """Unreliable calibration emits diagnostic evidence; no error unless groundedness=gate."""
        ev = self._build(_VALID_PROFILE, _UNRELIABLE_CALIBRATION)
        self.assertIsInstance(ev, dict)

    # --- groundedness hard-gate rejection ---

    def test_groundedness_gate_with_unreliable_calibration_raises(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        for e in evs:
            if e["name"] == "groundedness":
                e["role"] = "gate"
        p = _p(evaluators=evs)
        with self.assertRaises(ValueError) as ctx:
            self._build(p, _UNRELIABLE_CALIBRATION)
        msg = str(ctx.exception)
        self.assertIn("Groundedness", msg)
        self.assertIn("human_review", msg)

    def test_groundedness_gate_with_reliable_calibration_succeeds(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        for e in evs:
            if e["name"] == "groundedness":
                e["role"] = "gate"
        p = _p(evaluators=evs)
        ev = self._build(p, _VALID_CALIBRATION)  # must not raise
        self.assertEqual(ev["evaluator_roles"]["groundedness"], "gate")

    # --- threshold rationale and timestamp ---

    def test_threshold_rationale_in_evidence(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["threshold_rationale"], _VALID_PROFILE["threshold_rationale"])

    def test_last_calibrated_at_in_evidence(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["last_calibrated_at"], _VALID_PROFILE["last_calibrated_at"])

    # --- optional P1 fields ---

    def test_evaluation_design_included_when_present(self) -> None:
        design = {"held_out_data_only": True, "rubric_applicable": True}
        p = _p(evaluation_design=design)
        ev = self._build(p, _VALID_CALIBRATION)
        self.assertEqual(ev["evaluation_design"], design)

    def test_evaluation_design_absent_when_not_in_profile(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertNotIn("evaluation_design", ev)

    def test_task_specific_rubric_included_when_present(self) -> None:
        rubric = {"reviewed": True, "version": "2.1"}
        p = _p(task_specific_rubric=rubric)
        ev = self._build(p, _VALID_CALIBRATION)
        self.assertEqual(ev["task_specific_rubric"], rubric)

    def test_simulator_included_when_present(self) -> None:
        simulator = {"used": False, "usr8_report": None}
        p = _p(simulator=simulator)
        ev = self._build(p, _VALID_CALIBRATION)
        self.assertEqual(ev["simulator"], simulator)

    def test_sampling_included_when_present(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        self.assertEqual(ev["sampling"], _VALID_PROFILE["sampling"])

    def test_benchmark_included_when_present(self) -> None:
        benchmark = {"applicable": True, "name": "baseline-2025Q1", "version": "1.0.0", "judge_version": "2024-07-18", "delta": 0.03}
        p = _p(benchmark=benchmark)
        ev = self._build(p, _VALID_CALIBRATION)
        self.assertEqual(ev["benchmark"], benchmark)

    # --- calibration summary structure ---

    def test_calibration_summary_fields(self) -> None:
        ev = self._build(_VALID_PROFILE, _VALID_CALIBRATION)
        cal = ev["calibration"]
        for field in ("captured_at", "known_good", "known_bad", "repeated_runs", "agreement", "flip_rate", "reliable"):
            self.assertIn(field, cal, f"calibration.{field} missing from evidence")

    # --- invalid inputs ---

    def test_invalid_role_raises_valueerror_in_build_trust_evidence(self) -> None:
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["role"] = "blocker"
        with self.assertRaises(ValueError):
            self._build(_p(evaluators=evs), _VALID_CALIBRATION)

    def test_bool_threshold_rejects_build_trust_evidence(self) -> None:
        p = _p()
        p["evaluators"][0]["threshold"] = True
        with self.assertRaises(TypeError) as ctx:
            self._build(p, _VALID_CALIBRATION)
        self.assertIn("threshold", str(ctx.exception))

    def test_whitespace_only_pin_fields_reject_build_trust_evidence(self) -> None:
        cases = (
            ("evaluator_version", lambda ev: ev.__setitem__("evaluator_version", "   ")),
            ("judge.deployment", lambda ev: ev["judge"].__setitem__("deployment", " \t")),
            ("judge.model", lambda ev: ev["judge"].__setitem__("model", "\n")),
            ("judge.version", lambda ev: ev["judge"].__setitem__("version", "  ")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                p = _p()
                mutate(p["evaluators"][0])
                with self.assertRaises(ValueError) as ctx:
                    self._build(p, _VALID_CALIBRATION)
                self.assertIn("non-empty", str(ctx.exception))

    def test_non_dict_profile_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError):
            self._build("not-a-dict", _VALID_CALIBRATION)

    def test_non_dict_calibration_raises_typeerror(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_VALID_PROFILE, [1, 2, 3])


# ===========================================================================
# write_trust_evidence
# ===========================================================================


class TestWriteTrustEvidence(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import build_trust_evidence, write_trust_evidence
        self._write = write_trust_evidence
        self._evidence = build_trust_evidence(_VALID_PROFILE, _VALID_CALIBRATION)

    def test_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.json"
            self._write(self._evidence, dest)
            self.assertTrue(dest.exists())

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "deep" / "nested" / "trust.json"
            self._write(self._evidence, dest)
            self.assertTrue(dest.exists())

    def test_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.json"
            self._write(self._evidence, dest)
            content = dest.read_text(encoding="utf-8")
            self.assertTrue(content.endswith("\n"))

    def test_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out.json"
            self._write(self._evidence, dest)
            parsed = json.loads(dest.read_text(encoding="utf-8"))
            self.assertEqual(parsed["$schema"], "foundry-evals-trust-evidence/v1")

    def test_deterministic_identical_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest1 = Path(tmp) / "out1.json"
            dest2 = Path(tmp) / "out2.json"
            self._write(copy.deepcopy(self._evidence), dest1)
            self._write(copy.deepcopy(self._evidence), dest2)
            self.assertEqual(dest1.read_bytes(), dest2.read_bytes())

    def test_accepts_string_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = str(Path(tmp) / "str-path.json")
            self._write(self._evidence, dest)
            self.assertTrue(Path(dest).exists())

    def test_sort_keys_determinism(self) -> None:
        """Keys are alphabetically sorted so output is stable across Python dicts."""
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "sorted.json"
            self._write(self._evidence, dest)
            content = dest.read_text(encoding="utf-8")
            parsed = json.loads(content)
            keys = list(parsed.keys())
            self.assertEqual(keys, sorted(keys))


# ===========================================================================
# Valid/invalid fixture files
# ===========================================================================


class TestFixtures(unittest.TestCase):
    def setUp(self) -> None:
        from eval_trust import _validate_profile_stdlib
        self._validate_stdlib = _validate_profile_stdlib

    def test_valid_fixture_file_exists(self) -> None:
        self.assertTrue((_DATA_DIR / "trust-profile.valid.json").exists())

    def test_invalid_fixture_file_exists(self) -> None:
        self.assertTrue((_DATA_DIR / "trust-profile.invalid.json").exists())

    def test_valid_fixture_is_parseable_json(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_invalid_fixture_is_parseable_json(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.invalid.json").read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_valid_fixture_passes_stdlib_validation(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        self._validate_stdlib(data)  # must not raise

    def test_invalid_fixture_fails_stdlib_validation(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.invalid.json").read_text(encoding="utf-8"))
        with self.assertRaises((ValueError, TypeError)):
            self._validate_stdlib(data)

    def test_valid_fixture_has_required_roles(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        roles = {e["name"]: e["role"] for e in data["evaluators"]}
        self.assertIn("task_completion", roles)
        self.assertEqual(roles["task_completion"], "gate")
        self.assertIn("groundedness", roles)
        self.assertEqual(roles["groundedness"], "human_review")
        self.assertIn("coherence", roles)
        self.assertEqual(roles["coherence"], "trend")

    def test_valid_fixture_has_simulator(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        self.assertIn("simulator", data)
        self.assertFalse(data["simulator"]["used"])
        self.assertIsNone(data["simulator"]["usr8_report"])

    def test_valid_fixture_has_benchmark_with_delta(self) -> None:
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        self.assertIn("benchmark", data)
        self.assertIn("delta", data["benchmark"])

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_valid_fixture_validates_against_schema(self) -> None:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        data = json.loads((_DATA_DIR / "trust-profile.valid.json").read_text(encoding="utf-8"))
        _jsonschema.validate(instance=data, schema=schema)  # must not raise

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_invalid_fixture_fails_jsonschema_validation(self) -> None:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        data = json.loads((_DATA_DIR / "trust-profile.invalid.json").read_text(encoding="utf-8"))
        with self.assertRaises(_jsonschema.ValidationError):
            _jsonschema.validate(instance=data, schema=schema)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_jsonschema_rejects_whitespace_only_pins(self) -> None:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        cases = (
            ("evaluator_version", lambda p: p["evaluators"][0].__setitem__("evaluator_version", "   ")),
            ("judge.deployment", lambda p: p["evaluators"][0]["judge"].__setitem__("deployment", " \t")),
            ("judge.model", lambda p: p["evaluators"][0]["judge"].__setitem__("model", "\n")),
            ("judge.version", lambda p: p["evaluators"][0]["judge"].__setitem__("version", "  ")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                data = copy.deepcopy(_VALID_PROFILE)
                mutate(data)
                with self.assertRaises(_jsonschema.ValidationError):
                    _jsonschema.validate(instance=data, schema=schema)


# ===========================================================================
# Schema file shape
# ===========================================================================


class TestSchemaShape(unittest.TestCase):
    def setUp(self) -> None:
        self._schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_schema_file_exists(self) -> None:
        self.assertTrue(_SCHEMA_PATH.exists())

    def test_schema_has_id(self) -> None:
        self.assertIn("$id", self._schema)
        self.assertEqual(self._schema["$id"], "foundry-evals-trust-profile/v1")

    def test_schema_has_type_object(self) -> None:
        self.assertEqual(self._schema["type"], "object")

    def test_schema_has_required_fields(self) -> None:
        required = set(self._schema.get("required", []))
        for field in ("unit_of_analysis", "evaluators", "threshold_rationale", "last_calibrated_at", "sampling"):
            self.assertIn(field, required, f"'{field}' missing from schema required")

    def test_schema_additional_properties_true(self) -> None:
        """Schema allows unknown future properties (extensible design)."""
        self.assertTrue(self._schema.get("additionalProperties", False))

    def test_schema_evaluator_role_enum(self) -> None:
        evaluator_def = self._schema["definitions"]["Evaluator"]
        role_enum = evaluator_def["properties"]["role"]["enum"]
        self.assertIn("gate", role_enum)
        self.assertIn("trend", role_enum)
        self.assertIn("human_review", role_enum)

    def test_schema_judge_required_fields(self) -> None:
        judge_def = self._schema["definitions"]["Judge"]
        for field in ("deployment", "model", "version"):
            self.assertIn(field, judge_def["required"])

    def test_schema_sampling_evaluation_enum(self) -> None:
        sampling_def = self._schema["definitions"]["Sampling"]
        self.assertEqual(sampling_def["properties"]["evaluation"]["enum"], ["diversity"])

    def test_schema_sampling_sla_enum(self) -> None:
        sampling_def = self._schema["definitions"]["Sampling"]
        self.assertEqual(sampling_def["properties"]["sla"]["enum"], ["uniform"])

    def test_schema_pin_patterns_reject_whitespace_only_strings(self) -> None:
        evaluator_props = self._schema["definitions"]["Evaluator"]["properties"]
        judge_props = self._schema["definitions"]["Judge"]["properties"]
        for field, props in (
            ("evaluator_version", evaluator_props),
            ("deployment", judge_props),
            ("model", judge_props),
            ("version", judge_props),
        ):
            with self.subTest(field=field):
                self.assertEqual(props[field]["pattern"], ".*\\S.*")


# ===========================================================================
# Stdlib fallback — always exercised even when jsonschema is installed
# ===========================================================================


class TestStdlibFallback(unittest.TestCase):
    """Exercises the stdlib validation path explicitly and independently of jsonschema."""

    def test_stdlib_rejects_invalid_profile_independently(self) -> None:
        """Call _validate_profile_stdlib directly — bypasses any jsonschema code path."""
        from eval_trust import _validate_profile_stdlib
        bad = {
            "unit_of_analysis": "tenant",
            "evaluators": [],
            "threshold_rationale": 99,
            "sampling": {"evaluation": "random", "sla": "best-effort"},
        }
        with self.assertRaises((ValueError, TypeError)):
            _validate_profile_stdlib(bad)

    def test_stdlib_accepts_valid_profile_independently(self) -> None:
        from eval_trust import _validate_profile_stdlib
        _validate_profile_stdlib(copy.deepcopy(_VALID_PROFILE))

    def test_stdlib_role_check_is_precise(self) -> None:
        from eval_trust import _validate_profile_stdlib
        evs = copy.deepcopy(_VALID_PROFILE["evaluators"])
        evs[0]["role"] = "GATE"  # wrong case — not in frozenset
        with self.assertRaises(ValueError) as ctx:
            _validate_profile_stdlib(_p(evaluators=evs))
        self.assertIn("gate", str(ctx.exception))

    def test_validate_profile_with_schema_rejects_whitespace_only_pins_without_jsonschema(self) -> None:
        """Force stdlib-only validation and ensure blank pin fields are rejected."""
        import eval_trust
        from eval_trust import validate_profile_with_schema

        cases = (
            ("evaluator_version", lambda p: p["evaluators"][0].__setitem__("evaluator_version", "   ")),
            ("judge.deployment", lambda p: p["evaluators"][0]["judge"].__setitem__("deployment", " \t")),
            ("judge.model", lambda p: p["evaluators"][0]["judge"].__setitem__("model", "\n")),
            ("judge.version", lambda p: p["evaluators"][0]["judge"].__setitem__("version", "  ")),
        )
        for label, mutate in cases:
            with self.subTest(label=label):
                bad = _p()
                mutate(bad)
                with mock.patch.object(eval_trust, "_HAS_JSONSCHEMA", False):
                    with self.assertRaises(ValueError) as ctx:
                        validate_profile_with_schema(bad)
                self.assertIn("non-empty", str(ctx.exception))

    def test_validate_profile_with_schema_rejects_bool_threshold_without_jsonschema(self) -> None:
        import eval_trust
        from eval_trust import validate_profile_with_schema

        bad = _p()
        bad["evaluators"][0]["threshold"] = True
        with mock.patch.object(eval_trust, "_HAS_JSONSCHEMA", False):
            with self.assertRaises(TypeError) as ctx:
                validate_profile_with_schema(bad)
        self.assertIn("threshold", str(ctx.exception))


# ===========================================================================
# trust-profile.yaml contract pins
# ===========================================================================


@unittest.skipUnless(_HAS_YAML, "pyyaml not installed")
class TestTrustProfileYAML(unittest.TestCase):
    """Pin tests for skills/foundry-evals/references/data/trust-profile.yaml.

    These tests document the expected structure of the YAML sample so any
    accidental edit is caught immediately.
    """

    _YAML_PATH = _DATA_DIR / "trust-profile.yaml"

    def setUp(self) -> None:
        from eval_trust import _validate_profile_stdlib, _compute_pins
        self._validate_stdlib = _validate_profile_stdlib
        self._compute_pins = _compute_pins
        self._profile: dict = _yaml.safe_load(
            self._YAML_PATH.read_text(encoding="utf-8")
        )

    def test_file_exists(self) -> None:
        self.assertTrue(self._YAML_PATH.exists(), "trust-profile.yaml must exist")

    def test_parses_as_yaml(self) -> None:
        data = _yaml.safe_load(self._YAML_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_passes_stdlib_validation(self) -> None:
        self._validate_stdlib(self._profile)  # must not raise

    def test_unit_of_analysis_is_session(self) -> None:
        self.assertEqual(self._profile["unit_of_analysis"], "session")

    def test_task_completion_is_gate(self) -> None:
        roles = {e["name"]: e["role"] for e in self._profile["evaluators"]}
        self.assertEqual(roles.get("task_completion"), "gate")

    def test_csat_is_gate(self) -> None:
        roles = {e["name"]: e["role"] for e in self._profile["evaluators"]}
        self.assertEqual(roles.get("csat"), "gate")

    def test_groundedness_is_human_review(self) -> None:
        roles = {e["name"]: e["role"] for e in self._profile["evaluators"]}
        self.assertEqual(roles.get("groundedness"), "human_review")

    def test_groundedness_not_gate(self) -> None:
        """groundedness must never be gate in the sample — enforces the default rule."""
        roles = {e["name"]: e["role"] for e in self._profile["evaluators"]}
        self.assertNotEqual(roles.get("groundedness"), "gate")

    def test_coherence_is_trend(self) -> None:
        roles = {e["name"]: e["role"] for e in self._profile["evaluators"]}
        self.assertEqual(roles.get("coherence"), "trend")

    def test_all_pins_set(self) -> None:
        self.assertTrue(self._compute_pins(self._profile["evaluators"]))

    def test_has_p1_task_specific_rubric(self) -> None:
        self.assertIn("task_specific_rubric", self._profile)
        self.assertIn("reviewed", self._profile["task_specific_rubric"])

    def test_has_p1_simulator_with_usr8_report(self) -> None:
        self.assertIn("simulator", self._profile)
        sim = self._profile["simulator"]
        self.assertIn("used", sim)
        self.assertIn("usr8_report", sim)

    def test_has_p1_benchmark(self) -> None:
        self.assertIn("benchmark", self._profile)
        bm = self._profile["benchmark"]
        for field in ("name", "version", "judge_version", "applicable"):
            self.assertIn(field, bm, f"benchmark.{field} missing")
        self.assertIn("delta", bm)

    def test_sampling_diversity_and_uniform(self) -> None:
        s = self._profile["sampling"]
        self.assertEqual(s["evaluation"], "diversity")
        self.assertEqual(s["sla"], "uniform")

    def test_threshold_rationale_is_string(self) -> None:
        self.assertIsInstance(self._profile["threshold_rationale"], str)
        self.assertGreater(len(self._profile["threshold_rationale"].strip()), 0)

    def test_last_calibrated_at_is_string(self) -> None:
        # yaml.safe_load must NOT parse it as a datetime — must remain a string
        self.assertIsInstance(self._profile["last_calibrated_at"], str)

    def test_no_real_arm_subscription_ids(self) -> None:
        text = self._YAML_PATH.read_text(encoding="utf-8")
        arm_re = re.compile(
            r"subscriptions/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.I,
        )
        self.assertIsNone(arm_re.search(text), "trust-profile.yaml must not contain real ARM IDs")

    def test_no_real_tenant_ids_in_judge_fields(self) -> None:
        text = self._YAML_PATH.read_text(encoding="utf-8")
        # Tenant IDs appear as 8-4-4-4-12 UUID not adjacent to a resource-path keyword
        # Check judge deployment names don't look like real GUIDs
        uuid_re = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
        matches = uuid_re.findall(text)
        self.assertEqual(matches, [], f"Unexpected UUID-shaped values in trust-profile.yaml: {matches}")


# ===========================================================================
# calibration-run.json contract pins
# ===========================================================================


class TestCalibrationRunJSON(unittest.TestCase):
    """Pin tests for skills/foundry-evals/references/data/calibration-run.json."""

    _JSON_PATH = _DATA_DIR / "calibration-run.json"

    def setUp(self) -> None:
        from eval_trust import _validate_calibration
        self._validate = _validate_calibration
        self._data: dict = json.loads(self._JSON_PATH.read_text(encoding="utf-8"))

    def test_file_exists(self) -> None:
        self.assertTrue(self._JSON_PATH.exists(), "calibration-run.json must exist")

    def test_parses_as_json(self) -> None:
        data = json.loads(self._JSON_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_schema_id(self) -> None:
        self.assertEqual(self._data["$schema"], "foundry-evals-calibration/v1")

    def test_passes_calibration_validation(self) -> None:
        self._validate(self._data)  # must not raise

    def test_repeated_runs_ge_four(self) -> None:
        self.assertGreaterEqual(self._data["repeated_runs"], 4)

    def test_agreement_reliable(self) -> None:
        self.assertGreaterEqual(self._data["agreement"], 0.80)

    def test_flip_rate_reliable(self) -> None:
        self.assertLessEqual(self._data["flip_rate"], 0.10)

    def test_known_good_positive(self) -> None:
        self.assertGreater(self._data["known_good"], 0)

    def test_known_bad_positive(self) -> None:
        self.assertGreater(self._data["known_bad"], 0)

    def test_captured_at_is_string(self) -> None:
        self.assertIsInstance(self._data["captured_at"], str)

    def test_runs_array_matches_repeated_runs_count(self) -> None:
        runs = self._data.get("runs", [])
        self.assertEqual(
            len(runs),
            self._data["repeated_runs"],
            "runs array length must equal repeated_runs",
        )

    def test_each_run_has_agreement_and_flip_rate(self) -> None:
        for i, run in enumerate(self._data.get("runs", [])):
            with self.subTest(run_index=i):
                self.assertIn("agreement", run)
                self.assertIn("flip_rate", run)
                self.assertIsInstance(run["agreement"], float)
                self.assertIsInstance(run["flip_rate"], float)


# ===========================================================================
# Trust evidence integration: YAML profile + JSON calibration → evidence doc
# ===========================================================================


@unittest.skipUnless(_HAS_YAML, "pyyaml not installed")
class TestTrustEvidenceIntegration(unittest.TestCase):
    """End-to-end contract: load YAML profile + JSON calibration, build evidence."""

    def setUp(self) -> None:
        from eval_trust import build_trust_evidence, write_trust_evidence
        self._build = build_trust_evidence
        self._write = write_trust_evidence

        self._profile: dict = _yaml.safe_load(
            (_DATA_DIR / "trust-profile.yaml").read_text(encoding="utf-8")
        )
        self._calibration: dict = json.loads(
            (_DATA_DIR / "calibration-run.json").read_text(encoding="utf-8")
        )
        self._evidence: dict = self._build(self._profile, self._calibration)

    def test_evidence_schema_id(self) -> None:
        self.assertEqual(self._evidence["$schema"], "foundry-evals-trust-evidence/v1")

    def test_evidence_session_field(self) -> None:
        self.assertEqual(self._evidence["session"], "session")

    def test_evidence_groundedness_not_gate(self) -> None:
        roles = self._evidence["evaluator_roles"]
        self.assertNotEqual(roles.get("groundedness"), "gate")

    def test_evidence_pins_set(self) -> None:
        self.assertTrue(self._evidence["judge_and_evaluator_versions_pinned"])

    def test_evidence_calibration_reliable(self) -> None:
        self.assertTrue(self._evidence["evaluator_reliability_ok"])

    def test_evidence_calibration_summary_present(self) -> None:
        cal = self._evidence["calibration"]
        for field in ("captured_at", "known_good", "known_bad", "repeated_runs", "agreement", "flip_rate", "reliable"):
            self.assertIn(field, cal, f"calibration.{field} missing from evidence")

    def test_write_evidence_deterministic(self) -> None:
        """write_trust_evidence produces byte-identical output on repeated calls."""
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path1 = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path2 = f.name
        try:
            self._write(self._evidence, path1)
            self._write(self._evidence, path2)
            self.assertEqual(
                Path(path1).read_bytes(),
                Path(path2).read_bytes(),
                "write_trust_evidence output must be deterministic",
            )
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_evidence_has_sampling_passthrough(self) -> None:
        self.assertIn("sampling", self._evidence)
        self.assertEqual(self._evidence["sampling"]["evaluation"], "diversity")
        self.assertEqual(self._evidence["sampling"]["sla"], "uniform")




# ===========================================================================
# YAML / valid JSON semantic equality
# ===========================================================================


@unittest.skipUnless(_HAS_YAML, "pyyaml not installed")
class TestYAMLJSONSemanticEquality(unittest.TestCase):
    """trust-profile.yaml and trust-profile.valid.json must be structurally equivalent.

    The YAML is the human-editable source of truth; the JSON is the machine-readable
    equivalent. Both must deserialise to semantically equal Python objects (modulo
    $schema and threshold_rationale whitespace differences acceptable to pyyaml).
    """

    _YAML_PATH = _DATA_DIR / "trust-profile.yaml"
    _JSON_PATH = _DATA_DIR / "trust-profile.valid.json"

    def _normalise(self, d: dict) -> dict:
        """Deep-normalise a profile dict for semantic comparison.

        - Strip leading/trailing whitespace from all string values recursively
          (YAML block scalars may carry a trailing newline).
        - Remove $schema — format identifier not semantically meaningful here.
        """
        import copy

        def _strip(v: object) -> object:
            if isinstance(v, str):
                return v.strip()
            if isinstance(v, dict):
                return {k: _strip(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_strip(item) for item in v]
            return v

        out = copy.deepcopy(d)
        out.pop("$schema", None)
        return _strip(out)  # type: ignore[return-value]

    def setUp(self) -> None:
        self._yaml_profile: dict = _yaml.safe_load(
            self._YAML_PATH.read_text(encoding="utf-8")
        )
        self._json_profile: dict = json.loads(
            self._JSON_PATH.read_text(encoding="utf-8")
        )

    def test_both_files_exist(self) -> None:
        self.assertTrue(self._YAML_PATH.exists())
        self.assertTrue(self._JSON_PATH.exists())

    def test_yaml_json_structural_equivalence(self) -> None:
        """YAML and valid JSON must produce semantically equal Python objects."""
        self.assertEqual(
            self._normalise(self._yaml_profile),
            self._normalise(self._json_profile),
            "trust-profile.yaml and trust-profile.valid.json are not semantically equal",
        )

    def test_both_have_all_p1_keys(self) -> None:
        p1_keys = {"evaluation_design", "task_specific_rubric", "simulator", "sampling", "benchmark"}
        for key in p1_keys:
            with self.subTest(key=key):
                self.assertIn(key, self._yaml_profile, f"YAML missing P1 key: {key}")
                self.assertIn(key, self._json_profile, f"JSON missing P1 key: {key}")


# ===========================================================================
# Normalized evidence: all P1 keys present
# ===========================================================================


@unittest.skipUnless(_HAS_YAML, "pyyaml not installed")
class TestNormalizedEvidenceP1Keys(unittest.TestCase):
    """Evidence built from the reference YAML must carry all P1 keys with correct structure."""

    def setUp(self) -> None:
        from eval_trust import build_trust_evidence
        self._build = build_trust_evidence
        self._profile: dict = _yaml.safe_load(
            (_DATA_DIR / "trust-profile.yaml").read_text(encoding="utf-8")
        )
        self._calibration: dict = json.loads(
            (_DATA_DIR / "calibration-run.json").read_text(encoding="utf-8")
        )
        self._evidence: dict = self._build(self._profile, self._calibration)

    def test_evidence_has_evaluation_design(self) -> None:
        self.assertIn("evaluation_design", self._evidence)
        ed = self._evidence["evaluation_design"]
        self.assertIsInstance(ed, dict)
        self.assertIn("held_out_data_only", ed)
        self.assertIn("rubric_applicable", ed)

    def test_evidence_has_task_specific_rubric(self) -> None:
        self.assertIn("task_specific_rubric", self._evidence)
        tsr = self._evidence["task_specific_rubric"]
        self.assertIsInstance(tsr, dict)
        self.assertIn("version", tsr)
        self.assertIn("reviewed", tsr)

    def test_evidence_has_simulator_with_usr8_report(self) -> None:
        self.assertIn("simulator", self._evidence)
        sim = self._evidence["simulator"]
        self.assertIsInstance(sim, dict)
        self.assertIn("used", sim)
        self.assertIn("usr8_report", sim)
        self.assertNotIn("note", sim)

    def test_evidence_has_sampling(self) -> None:
        self.assertIn("sampling", self._evidence)
        s = self._evidence["sampling"]
        self.assertEqual(s["evaluation"], "diversity")
        self.assertEqual(s["sla"], "uniform")

    def test_evidence_has_benchmark_with_authoritative_fields(self) -> None:
        self.assertIn("benchmark", self._evidence)
        bm = self._evidence["benchmark"]
        self.assertIsInstance(bm, dict)
        self.assertIn("applicable", bm)
        self.assertIn("name", bm)
        self.assertIn("version", bm)
        self.assertIn("judge_version", bm)
        self.assertIn("delta", bm)
        self.assertNotIn("pinned", bm)
        self.assertNotIn("judge", bm)
        self.assertNotIn("agent_config", bm)
        self.assertNotIn("run_metadata", bm)

    def test_evidence_does_not_use_old_field_names(self) -> None:
        """Validate no legacy field names appear in the evidence."""
        self.assertNotIn("task_rubric", self._evidence)
        for key in ("task_rubric", "pinned", "agent_config", "run_metadata"):
            bm = self._evidence.get("benchmark", {})
            self.assertNotIn(key, bm, f"benchmark must not contain legacy key: {key}")
        sim = self._evidence.get("simulator", {})
        self.assertNotIn("usr8", sim, "simulator.usr8 must be renamed to usr8_report")
        self.assertNotIn("note", sim, "simulator.note must not appear in normalized evidence")


if __name__ == "__main__":
    unittest.main()

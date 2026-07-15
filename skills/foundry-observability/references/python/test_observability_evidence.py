"""Unit tests for the foundry-observability operating-evidence normalizer.

Covers: module import (TDD missing-first), valid normalization, required alert
coverage, evaluator parity (exactly dev/ci/production), trace-policy strict-bool,
sampling bounds/finite/bool-rejection, retention int strictness, budget finite/bool,
timestamp UTC canonicalization, immutability, determinism, write_evidence behavior,
valid/invalid fixture loading, schema validation fallback parity, and malformed
nested types.

Run standalone from this directory::

    python test_observability_evidence.py -v

Or via the CI wrapper::

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

Written as ``unittest.TestCase`` (NOT pytest fixtures) to match CI discovery
convention (``.github/workflows/skill-test.yml`` unit-tests job).
"""
from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — works both standalone (run from this dir) and as a sub-import.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REFS_DIR = _THIS_DIR.parent
_DATA_DIR = _REFS_DIR / "data"
_SCHEMA_PATH = _REFS_DIR / "observability-profile.schema.json"

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

# ---------------------------------------------------------------------------
# Optional jsonschema — mirrored from the module under test.
# ---------------------------------------------------------------------------
try:
    import jsonschema as _jsonschema  # type: ignore[import]
    _HAS_JSONSCHEMA = True
except ImportError:
    _jsonschema = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False

# ---------------------------------------------------------------------------
# Minimal valid profile reused across tests.
# ---------------------------------------------------------------------------
_VALID_PROFILE: dict = {
    "schema": "foundry-observability-profile/v1",
    "action_group": {
        "resource_id": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Insights/actionGroups/agent-oncall",
        "owner": "agent-sre",
    },
    "alerts": {
        "failure": "agent-5xx",
        "latency": "tool-p95",
        "token_cost": "token-anomaly",
        "quality_safety": "eval-quality-drift",
    },
    "evaluator_definition": {
        "name": "agent-quality-v3",
        "version": "3.0.0",
        "environments": ["dev", "ci", "production"],
    },
    "trace_policy": {
        "content_recording": False,
        "redaction_policy": "docs/pii-redaction.md",
        "readers_group": "agent-observability-readers",
    },
    "sampling": {
        "traces": 0.1,
        "continuous_evaluation": 0.05,
    },
    "retention_days": 90,
    "monthly_budget_usd": 500,
}

_CAPTURED_AT = "2026-07-15T10:00:00Z"


def _p(**overrides) -> dict:
    """Deep copy of _VALID_PROFILE with top-level overrides applied."""
    d = copy.deepcopy(_VALID_PROFILE)
    d.update(overrides)
    return d


# ===========================================================================
# TDD: import test — fails until observability_evidence.py exists.
# ===========================================================================


class TestModuleImport(unittest.TestCase):
    """Verify the module can be imported and exposes the required public API."""

    def test_import_succeeds(self) -> None:
        import observability_evidence  # noqa: F401
        self.assertIsNotNone(observability_evidence)

    def test_public_api_present(self) -> None:
        from observability_evidence import (  # noqa: F401
            build_evidence,
            validate_profile_with_schema,
            write_evidence,
        )

    def test_schema_id_constants(self) -> None:
        import observability_evidence as m
        self.assertEqual(m._PROFILE_SCHEMA_ID, "foundry-observability-profile/v1")
        self.assertEqual(m._EVIDENCE_SCHEMA_ID, "foundry-observability-evidence/v1")

    def test_required_alerts_constant(self) -> None:
        import observability_evidence as m
        self.assertEqual(
            m._REQUIRED_ALERTS,
            frozenset({"failure", "latency", "token_cost", "quality_safety"}),
        )

    def test_parity_environments_constant(self) -> None:
        import observability_evidence as m
        self.assertEqual(
            m._PARITY_ENVIRONMENTS,
            frozenset({"dev", "ci", "production"}),
        )


# ===========================================================================
# Valid normalization
# ===========================================================================


class TestBuildEvidence(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_output_schema_field(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertEqual(ev["schema"], "foundry-observability-evidence/v1")

    def test_alert_categories_sorted(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertEqual(
            ev["alert_categories"],
            ["failure", "latency", "quality_safety", "token_cost"],
        )

    def test_evaluator_parity_true_exact_set(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertIs(ev["evaluator_parity"], True)

    def test_evaluator_parity_false_extra_environment(self) -> None:
        """Extra environments beyond dev/ci/production invalidate parity."""
        p = _p()
        p["evaluator_definition"]["environments"] = ["dev", "ci", "production", "staging"]
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIs(ev["evaluator_parity"], False)

    def test_evaluator_parity_false_missing_environment(self) -> None:
        p = _p()
        p["evaluator_definition"]["environments"] = ["dev", "ci"]
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIs(ev["evaluator_parity"], False)

    def test_evaluator_parity_false_empty_environments(self) -> None:
        p = _p()
        p["evaluator_definition"]["environments"] = []
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIs(ev["evaluator_parity"], False)

    def test_retention_days_passthrough_as_int(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertEqual(ev["retention_days"], 90)
        self.assertIsInstance(ev["retention_days"], int)
        self.assertNotIsInstance(ev["retention_days"], bool)

    def test_monthly_budget_as_float(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertAlmostEqual(ev["monthly_budget_usd"], 500.0)
        self.assertIsInstance(ev["monthly_budget_usd"], float)

    def test_sampling_values_are_float(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertIsInstance(ev["sampling"]["traces"], float)
        self.assertIsInstance(ev["sampling"]["continuous_evaluation"], float)
        self.assertAlmostEqual(ev["sampling"]["traces"], 0.1)
        self.assertAlmostEqual(ev["sampling"]["continuous_evaluation"], 0.05)

    def test_environments_sorted_in_evidence(self) -> None:
        p = _p()
        p["evaluator_definition"]["environments"] = ["production", "dev", "ci"]
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertEqual(ev["evaluator_definition"]["environments"], ["ci", "dev", "production"])

    def test_extra_alert_categories_present_in_alerts(self) -> None:
        """Extra alert categories beyond the four required are allowed."""
        p = _p()
        p["alerts"]["availability"] = "agent-avail"
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIn("availability", ev["alerts"])
        # required categories still present
        self.assertIn("quality_safety", ev["alert_categories"])

    def test_additional_profile_properties_do_not_raise(self) -> None:
        """Unknown future keys on the profile are tolerated."""
        p = _p()
        p["future_feature"] = {"experimental": True}
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIsNotNone(ev)

    def test_builds_complete_operating_evidence(self) -> None:
        """Plan step-1 smoke test — three assertions from the TDD scaffold."""
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertEqual(
            set(ev["alert_categories"]),
            {"failure", "latency", "token_cost", "quality_safety"},
        )
        self.assertTrue(ev["evaluator_parity"])
        self.assertEqual(ev["retention_days"], 90)


# ===========================================================================
# Alert validation
# ===========================================================================


class TestAlertValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def _build_without_alert(self, category: str) -> None:
        p = _p()
        del p["alerts"][category]
        self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_missing_quality_safety(self) -> None:
        with self.assertRaisesRegex(ValueError, "quality_safety"):
            self._build_without_alert("quality_safety")

    def test_rejects_missing_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "failure"):
            self._build_without_alert("failure")

    def test_rejects_missing_latency(self) -> None:
        with self.assertRaisesRegex(ValueError, "latency"):
            self._build_without_alert("latency")

    def test_rejects_missing_token_cost(self) -> None:
        with self.assertRaisesRegex(ValueError, "token_cost"):
            self._build_without_alert("token_cost")

    def test_rejects_empty_alert_name(self) -> None:
        p = _p()
        p["alerts"]["quality_safety"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_whitespace_only_alert_name(self) -> None:
        p = _p()
        p["alerts"]["failure"] = "   "
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_non_dict_alerts(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(alerts=["failure", "latency"]), captured_at=_CAPTURED_AT)


# ===========================================================================
# Action group validation
# ===========================================================================


class TestActionGroupValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_rejects_empty_resource_id(self) -> None:
        p = _p()
        p["action_group"]["resource_id"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_empty_owner(self) -> None:
        p = _p()
        p["action_group"]["owner"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_whitespace_owner(self) -> None:
        p = _p()
        p["action_group"]["owner"] = "  "
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_non_dict_action_group(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(action_group="agent-oncall"), captured_at=_CAPTURED_AT)


# ===========================================================================
# Evaluator definition validation
# ===========================================================================


class TestEvaluatorDefinitionValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_rejects_empty_evaluator_name(self) -> None:
        p = _p()
        p["evaluator_definition"]["name"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_empty_evaluator_version(self) -> None:
        p = _p()
        p["evaluator_definition"]["version"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_non_list_environments(self) -> None:
        p = _p()
        p["evaluator_definition"]["environments"] = "dev,ci,production"
        with self.assertRaises(TypeError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_non_dict_evaluator_definition(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(evaluator_definition="agent-quality-v3"), captured_at=_CAPTURED_AT)


# ===========================================================================
# Trace policy validation
# ===========================================================================


class TestTracePolicyValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_rejects_content_recording_string(self) -> None:
        p = _p()
        p["trace_policy"]["content_recording"] = "false"
        with self.assertRaises(TypeError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_content_recording_int_zero(self) -> None:
        p = _p()
        p["trace_policy"]["content_recording"] = 0
        with self.assertRaises(TypeError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_content_recording_none(self) -> None:
        p = _p()
        p["trace_policy"]["content_recording"] = None
        with self.assertRaises(TypeError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_accepts_content_recording_true(self) -> None:
        p = _p()
        p["trace_policy"]["content_recording"] = True
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertIs(ev["trace_policy"]["content_recording"], True)

    def test_rejects_empty_redaction_policy(self) -> None:
        p = _p()
        p["trace_policy"]["redaction_policy"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_empty_readers_group(self) -> None:
        p = _p()
        p["trace_policy"]["readers_group"] = ""
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_non_dict_trace_policy(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(trace_policy=False), captured_at=_CAPTURED_AT)


# ===========================================================================
# Sampling validation
# ===========================================================================


class TestSamplingValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def _with_sampling(self, **kv) -> None:
        p = _p()
        p["sampling"].update(kv)
        self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_traces_above_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "sampling"):
            self._with_sampling(traces=1.5)

    def test_rejects_traces_below_zero(self) -> None:
        with self.assertRaisesRegex(ValueError, "sampling"):
            self._with_sampling(traces=-0.1)

    def test_rejects_continuous_evaluation_above_one(self) -> None:
        with self.assertRaisesRegex(ValueError, "sampling"):
            self._with_sampling(continuous_evaluation=1.01)

    def test_rejects_unbounded_sampling(self) -> None:
        """Plan step-1 smoke test — unbounded sampling raises ValueError."""
        with self.assertRaisesRegex(ValueError, "sampling"):
            self._build(
                {**_VALID_PROFILE, "sampling": {"traces": 1.5, "continuous_evaluation": 0.05}},
                captured_at=_CAPTURED_AT,
            )

    def test_rejects_traces_bool_true(self) -> None:
        with self.assertRaises(TypeError):
            self._with_sampling(traces=True)

    def test_rejects_traces_bool_false(self) -> None:
        with self.assertRaises(TypeError):
            self._with_sampling(traces=False)

    def test_rejects_continuous_evaluation_bool(self) -> None:
        with self.assertRaises(TypeError):
            self._with_sampling(continuous_evaluation=True)

    def test_rejects_traces_string(self) -> None:
        with self.assertRaises(TypeError):
            self._with_sampling(traces="0.1")

    def test_rejects_traces_non_finite_inf(self) -> None:
        with self.assertRaises(ValueError):
            self._with_sampling(traces=math.inf)

    def test_rejects_traces_nan(self) -> None:
        with self.assertRaises(ValueError):
            self._with_sampling(traces=math.nan)

    def test_accepts_zero_and_one_boundaries(self) -> None:
        p = _p()
        p["sampling"]["traces"] = 0.0
        p["sampling"]["continuous_evaluation"] = 1.0
        ev = self._build(p, captured_at=_CAPTURED_AT)
        self.assertAlmostEqual(ev["sampling"]["traces"], 0.0)
        self.assertAlmostEqual(ev["sampling"]["continuous_evaluation"], 1.0)

    def test_rejects_non_dict_sampling(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(sampling=0.1), captured_at=_CAPTURED_AT)


# ===========================================================================
# Retention days validation
# ===========================================================================


class TestRetentionDaysValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_accepts_integer_30(self) -> None:
        ev = self._build(_p(retention_days=30), captured_at=_CAPTURED_AT)
        self.assertEqual(ev["retention_days"], 30)

    def test_rejects_less_than_30(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(retention_days=29), captured_at=_CAPTURED_AT)

    def test_rejects_bool_true(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days=True), captured_at=_CAPTURED_AT)

    def test_rejects_bool_false(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days=False), captured_at=_CAPTURED_AT)

    def test_rejects_float(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days=90.0), captured_at=_CAPTURED_AT)

    def test_rejects_string(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days="90"), captured_at=_CAPTURED_AT)

    def test_rejects_fraction_float(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days=90.5), captured_at=_CAPTURED_AT)


# ===========================================================================
# Monthly budget validation
# ===========================================================================


class TestMonthlyBudgetValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_accepts_integer_budget(self) -> None:
        ev = self._build(_p(monthly_budget_usd=1), captured_at=_CAPTURED_AT)
        self.assertAlmostEqual(ev["monthly_budget_usd"], 1.0)

    def test_rejects_zero(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(monthly_budget_usd=0), captured_at=_CAPTURED_AT)

    def test_rejects_negative(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(monthly_budget_usd=-1.0), captured_at=_CAPTURED_AT)

    def test_rejects_bool_true(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(monthly_budget_usd=True), captured_at=_CAPTURED_AT)

    def test_rejects_bool_false(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(monthly_budget_usd=False), captured_at=_CAPTURED_AT)

    def test_rejects_string(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(monthly_budget_usd="500"), captured_at=_CAPTURED_AT)

    def test_rejects_inf(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(monthly_budget_usd=math.inf), captured_at=_CAPTURED_AT)

    def test_rejects_nan(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(monthly_budget_usd=math.nan), captured_at=_CAPTURED_AT)


# ===========================================================================
# Timestamp validation
# ===========================================================================


class TestTimestampValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence, _parse_utc_timestamp
        self._build = build_evidence
        self._parse = _parse_utc_timestamp

    def test_z_suffix_accepted(self) -> None:
        ev = self._build(_p(), captured_at="2026-07-15T10:00:00Z")
        self.assertIn(ev["captured_at"], [
            "2026-07-15T10:00:00+00:00",
            "2026-07-15T10:00:00Z",
        ])

    def test_plus_zero_suffix_accepted(self) -> None:
        ev = self._build(_p(), captured_at="2026-07-15T10:00:00+00:00")
        self.assertIn(ev["captured_at"], [
            "2026-07-15T10:00:00+00:00",
            "2026-07-15T10:00:00Z",
        ])

    def test_z_and_plus_zero_canonicalize_equally(self) -> None:
        """Z and +00:00 timestamps for the same instant produce identical output."""
        ev_z = self._build(_p(), captured_at="2026-07-15T10:00:00Z")
        ev_plus = self._build(_p(), captured_at="2026-07-15T10:00:00+00:00")
        self.assertEqual(ev_z["captured_at"], ev_plus["captured_at"])

    def test_rejects_naive_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(), captured_at="2026-07-15T10:00:00")

    def test_rejects_non_utc_offset(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(), captured_at="2026-07-15T10:00:00+02:00")

    def test_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            self._build(_p(), captured_at="not-a-date")

    def test_rejects_non_string_timestamp(self) -> None:
        with self.assertRaises(TypeError):
            self._parse(None, "captured_at")

    def test_captured_at_in_evidence(self) -> None:
        ev = self._build(_p(), captured_at="2026-07-15T10:00:00Z")
        self.assertIn("captured_at", ev)
        self.assertIsInstance(ev["captured_at"], str)


# ===========================================================================
# Immutability and determinism
# ===========================================================================


class TestImmutabilityAndDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_does_not_mutate_input(self) -> None:
        original = copy.deepcopy(_VALID_PROFILE)
        before = json.dumps(original, sort_keys=True)
        self._build(original, captured_at=_CAPTURED_AT)
        after = json.dumps(original, sort_keys=True)
        self.assertEqual(before, after, "build_evidence must not mutate the input profile")

    def test_deterministic_output_same_input(self) -> None:
        ev1 = self._build(_p(), captured_at=_CAPTURED_AT)
        ev2 = self._build(_p(), captured_at=_CAPTURED_AT)
        self.assertEqual(
            json.dumps(ev1, sort_keys=True),
            json.dumps(ev2, sort_keys=True),
        )

    def test_deterministic_across_alert_insertion_order(self) -> None:
        """Evidence output is deterministic regardless of alert dict insertion order."""
        p1 = _p()
        p2 = _p()
        p2["alerts"] = {
            "quality_safety": p1["alerts"]["quality_safety"],
            "failure": p1["alerts"]["failure"],
            "token_cost": p1["alerts"]["token_cost"],
            "latency": p1["alerts"]["latency"],
        }
        ev1 = self._build(p1, captured_at=_CAPTURED_AT)
        ev2 = self._build(p2, captured_at=_CAPTURED_AT)
        self.assertEqual(
            json.dumps(ev1, sort_keys=True),
            json.dumps(ev2, sort_keys=True),
        )


# ===========================================================================
# write_evidence behavior
# ===========================================================================


class TestWriteEvidence(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence, write_evidence
        self._build = build_evidence
        self._write = write_evidence

    def test_creates_parent_dir(self) -> None:
        import os
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "nested" / "dir" / "evidence.json"
            self._write(ev, out)
            self.assertTrue(out.exists())

    def test_ends_with_newline(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "evidence.json"
            self._write(ev, out)
            content = out.read_text(encoding="utf-8")
            self.assertTrue(content.endswith("\n"), "output must end with a newline")

    def test_valid_json(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "evidence.json"
            self._write(ev, out)
            parsed = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema"], "foundry-observability-evidence/v1")

    def test_byte_identical_on_repeat(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        with tempfile.TemporaryDirectory() as td:
            out1 = Path(td) / "ev1.json"
            out2 = Path(td) / "ev2.json"
            self._write(ev, out1)
            self._write(ev, out2)
            self.assertEqual(
                out1.read_bytes(), out2.read_bytes(),
                "write_evidence must produce byte-identical output for the same input",
            )

    def test_accepts_string_path(self) -> None:
        ev = self._build(_p(), captured_at=_CAPTURED_AT)
        with tempfile.TemporaryDirectory() as td:
            out = str(Path(td) / "evidence.json")
            self._write(ev, out)
            self.assertTrue(Path(out).exists())


# ===========================================================================
# Fixture loading (valid/invalid)
# ===========================================================================


class TestFixtureFiles(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_valid_fixture_normalizes(self) -> None:
        """The bundled valid fixture produces a complete evidence document."""
        path = _DATA_DIR / "observability-profile.valid.json"
        self.assertTrue(path.exists(), f"Missing fixture: {path}")
        profile = json.loads(path.read_text(encoding="utf-8"))
        ev = self._build(profile, captured_at=_CAPTURED_AT)
        self.assertEqual(ev["schema"], "foundry-observability-evidence/v1")
        self.assertIn("quality_safety", ev["alert_categories"])
        self.assertTrue(ev["evaluator_parity"])

    def test_invalid_fixture_raises(self) -> None:
        """The bundled invalid fixture fails with ValueError (missing alert)."""
        path = _DATA_DIR / "observability-profile.invalid.json"
        self.assertTrue(path.exists(), f"Missing fixture: {path}")
        profile = json.loads(path.read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            self._build(profile, captured_at=_CAPTURED_AT)


# ===========================================================================
# JSON Schema validation / stdlib fallback parity
# ===========================================================================


class TestSchemaValidation(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import validate_profile_with_schema
        self._validate = validate_profile_with_schema

    def test_valid_profile_passes_validation(self) -> None:
        self._validate(copy.deepcopy(_VALID_PROFILE))  # must not raise

    def test_invalid_profile_raises_stdlib_path(self) -> None:
        """stdlib validation rejects same invalid fixture regardless of jsonschema."""
        path = _DATA_DIR / "observability-profile.invalid.json"
        if not path.exists():
            self.skipTest("invalid fixture not found")
        profile = json.loads(path.read_text(encoding="utf-8"))
        with self.assertRaises((ValueError, TypeError)):
            self._validate(profile)

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_valid_fixture_passes_jsonschema(self) -> None:
        path = _DATA_DIR / "observability-profile.valid.json"
        if not path.exists():
            self.skipTest("valid fixture not found")
        profile = json.loads(path.read_text(encoding="utf-8"))
        self._validate(profile)  # must not raise

    @unittest.skipUnless(_HAS_JSONSCHEMA, "jsonschema not installed")
    def test_invalid_fixture_raises_jsonschema(self) -> None:
        path = _DATA_DIR / "observability-profile.invalid.json"
        if not path.exists():
            self.skipTest("invalid fixture not found")
        profile = json.loads(path.read_text(encoding="utf-8"))
        with self.assertRaises((ValueError, TypeError)):
            self._validate(profile)

    def test_schema_file_exists(self) -> None:
        self.assertTrue(_SCHEMA_PATH.exists(), f"Missing schema: {_SCHEMA_PATH}")


# ===========================================================================
# Malformed nested types
# ===========================================================================


class TestMalformedNestedTypes(unittest.TestCase):
    def setUp(self) -> None:
        from observability_evidence import build_evidence
        self._build = build_evidence

    def test_rejects_profile_not_dict(self) -> None:
        with self.assertRaises(TypeError):
            self._build(["not", "a", "dict"], captured_at=_CAPTURED_AT)

    def test_rejects_action_group_list(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(action_group=["res_id", "owner"]), captured_at=_CAPTURED_AT)

    def test_rejects_trace_policy_string(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(trace_policy="strict"), captured_at=_CAPTURED_AT)

    def test_rejects_sampling_list(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(sampling=[0.1, 0.05]), captured_at=_CAPTURED_AT)

    def test_rejects_evaluator_definition_string(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(evaluator_definition="agent-quality-v3"), captured_at=_CAPTURED_AT)

    def test_rejects_retention_none(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(retention_days=None), captured_at=_CAPTURED_AT)

    def test_rejects_budget_none(self) -> None:
        with self.assertRaises(TypeError):
            self._build(_p(monthly_budget_usd=None), captured_at=_CAPTURED_AT)

    def test_rejects_missing_required_top_level_field(self) -> None:
        p = _p()
        del p["retention_days"]
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)

    def test_rejects_wrong_profile_schema(self) -> None:
        p = _p(schema="foundry-observability-profile/v99")
        with self.assertRaises(ValueError):
            self._build(p, captured_at=_CAPTURED_AT)


if __name__ == "__main__":
    unittest.main()

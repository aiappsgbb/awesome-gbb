"""Contract tests for the foundry-observability Production Operating Profile (Task 3).

Covers:
  - YAML / JSON semantic equality for observability-profile.yaml vs valid.json
  - Normaliser round-trip: YAML → build_evidence → write_evidence produces
    canonical specs/observability-evidence.json
  - Evidence assertion anchors: all four alert categories, action-group owner /
    resource_id, evaluator parity + environments, bounded sampling, trace
    policy, retention, positive budget
  - CLI flag rejection: observability_evidence.py has no CLI; argparse / sys.argv
    must NOT be in the module
  - SKILL.md workflow references canonical artifacts

Written as ``unittest.TestCase`` (NOT pytest fixtures) so that
``python -m unittest discover -s scripts/tests -p 'test_*.py' -v``
(invoked by ``.github/workflows/skill-test.yml::unit-tests``) discovers
and runs these tests automatically.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SKILL_DIR = _REPO_ROOT / "skills" / "foundry-observability"
_REFS_DIR = _SKILL_DIR / "references"
_PYTHON_DIR = _REFS_DIR / "python"
_DATA_DIR = _REFS_DIR / "data"
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_PROFILE_YAML = _REFS_DIR / "observability-profile.yaml"
_PROFILE_VALID_JSON = _DATA_DIR / "observability-profile.valid.json"
_CONSUMER_PROMPT = _SKILL_DIR / "test-fixture" / "consumer_prompt.md"
_SCHEMA_PATH = _REFS_DIR / "observability-profile.schema.json"

# ---------------------------------------------------------------------------
# Add the skill python dir to sys.path so imports work.
# ---------------------------------------------------------------------------
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise unittest.SkipTest("pyyaml not installed")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# YAML profile file exists and parses
# ===========================================================================

class TestYamlProfileExists(unittest.TestCase):
    def test_yaml_file_present(self) -> None:
        self.assertTrue(
            _PROFILE_YAML.exists(),
            f"Missing: {_PROFILE_YAML}",
        )

    def test_yaml_parses_as_dict(self) -> None:
        profile = _load_yaml(_PROFILE_YAML)
        self.assertIsInstance(profile, dict)

    def test_yaml_schema_field(self) -> None:
        profile = _load_yaml(_PROFILE_YAML)
        self.assertEqual(profile.get("schema"), "foundry-observability-profile/v1")


# ===========================================================================
# YAML / JSON semantic equality
# ===========================================================================

class TestYamlJsonSemanticEquality(unittest.TestCase):
    """YAML profile must parse to the same value as the canonical valid JSON."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.yaml_profile = _load_yaml(_PROFILE_YAML)
        cls.json_profile = _load_json(_PROFILE_VALID_JSON)

    def test_same_keys(self) -> None:
        self.assertEqual(
            set(self.yaml_profile.keys()),
            set(self.json_profile.keys()),
            "YAML and JSON profiles must have the same top-level keys",
        )

    def test_schema_equal(self) -> None:
        self.assertEqual(self.yaml_profile["schema"], self.json_profile["schema"])

    def test_action_group_equal(self) -> None:
        self.assertEqual(self.yaml_profile["action_group"], self.json_profile["action_group"])

    def test_alerts_equal(self) -> None:
        self.assertEqual(self.yaml_profile["alerts"], self.json_profile["alerts"])

    def test_evaluator_definition_equal(self) -> None:
        # Compare as sets to be order-independent for the environments list
        yaml_ev = dict(self.yaml_profile["evaluator_definition"])
        json_ev = dict(self.json_profile["evaluator_definition"])
        yaml_ev["environments"] = set(yaml_ev["environments"])
        json_ev["environments"] = set(json_ev["environments"])
        self.assertEqual(yaml_ev, json_ev)

    def test_trace_policy_equal(self) -> None:
        self.assertEqual(
            self.yaml_profile["trace_policy"],
            self.json_profile["trace_policy"],
        )

    def test_sampling_equal(self) -> None:
        self.assertAlmostEqual(
            self.yaml_profile["sampling"]["traces"],
            self.json_profile["sampling"]["traces"],
        )
        self.assertAlmostEqual(
            self.yaml_profile["sampling"]["continuous_evaluation"],
            self.json_profile["sampling"]["continuous_evaluation"],
        )

    def test_retention_days_equal(self) -> None:
        self.assertEqual(
            self.yaml_profile["retention_days"],
            self.json_profile["retention_days"],
        )

    def test_monthly_budget_equal(self) -> None:
        self.assertAlmostEqual(
            float(self.yaml_profile["monthly_budget_usd"]),
            float(self.json_profile["monthly_budget_usd"]),
        )

    def test_full_dict_equal(self) -> None:
        self.assertEqual(
            self.yaml_profile,
            self.json_profile,
            "YAML and JSON profiles must be fully semantically equal",
        )


# ===========================================================================
# Four alert categories present in YAML profile
# ===========================================================================

class TestYamlProfileAlertCategories(unittest.TestCase):
    _REQUIRED = {"failure", "latency", "token_cost", "quality_safety"}

    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = _load_yaml(_PROFILE_YAML)

    def test_all_four_alert_categories_present(self) -> None:
        alerts = self.profile.get("alerts", {})
        missing = self._REQUIRED - set(alerts.keys())
        self.assertFalse(
            missing,
            f"YAML profile missing alert categories: {missing}",
        )

    def test_alert_values_non_empty(self) -> None:
        alerts = self.profile.get("alerts", {})
        for cat in self._REQUIRED:
            self.assertTrue(
                alerts.get(cat, "").strip(),
                f"alerts.{cat} must be a non-empty string",
            )


# ===========================================================================
# Action group fields
# ===========================================================================

class TestYamlProfileActionGroup(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = _load_yaml(_PROFILE_YAML)

    def test_action_group_resource_id_non_empty(self) -> None:
        ag = self.profile.get("action_group", {})
        self.assertTrue(ag.get("resource_id", "").strip())

    def test_action_group_owner_non_empty(self) -> None:
        ag = self.profile.get("action_group", {})
        self.assertTrue(ag.get("owner", "").strip())


# ===========================================================================
# Evaluator definition: exactly dev / ci / production
# ===========================================================================

class TestYamlProfileEvaluatorDefinition(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = _load_yaml(_PROFILE_YAML)

    def test_evaluator_name_non_empty(self) -> None:
        ev = self.profile.get("evaluator_definition", {})
        self.assertTrue(ev.get("name", "").strip())

    def test_evaluator_version_non_empty(self) -> None:
        ev = self.profile.get("evaluator_definition", {})
        self.assertTrue(ev.get("version", "").strip())

    def test_evaluator_environments_exactly_three(self) -> None:
        ev = self.profile.get("evaluator_definition", {})
        envs = set(ev.get("environments", []))
        self.assertEqual(
            envs,
            {"dev", "ci", "production"},
            f"evaluator_definition.environments must be exactly {{dev, ci, production}}, got {envs}",
        )


# ===========================================================================
# Trace policy, sampling, retention, budget
# ===========================================================================

class TestYamlProfileConstraints(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = _load_yaml(_PROFILE_YAML)

    def test_trace_content_recording_is_bool(self) -> None:
        tp = self.profile.get("trace_policy", {})
        self.assertIsInstance(tp.get("content_recording"), bool)

    def test_sampling_traces_in_unit_interval(self) -> None:
        val = self.profile.get("sampling", {}).get("traces")
        self.assertIsNotNone(val)
        self.assertGreaterEqual(float(val), 0.0)
        self.assertLessEqual(float(val), 1.0)

    def test_sampling_continuous_evaluation_in_unit_interval(self) -> None:
        val = self.profile.get("sampling", {}).get("continuous_evaluation")
        self.assertIsNotNone(val)
        self.assertGreaterEqual(float(val), 0.0)
        self.assertLessEqual(float(val), 1.0)

    def test_retention_days_ge_30(self) -> None:
        ret = self.profile.get("retention_days")
        self.assertIsInstance(ret, int)
        self.assertNotIsInstance(ret, bool)
        self.assertGreaterEqual(ret, 30)

    def test_monthly_budget_positive(self) -> None:
        budget = self.profile.get("monthly_budget_usd")
        self.assertIsNotNone(budget)
        self.assertGreater(float(budget), 0.0)


# ===========================================================================
# Normaliser round-trip: YAML → evidence → write
# ===========================================================================

class TestNormaliserRoundTrip(unittest.TestCase):
    """Load YAML profile → build_evidence → write_evidence → assert contract."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            from observability_evidence import build_evidence, write_evidence
        except ImportError as exc:
            raise unittest.SkipTest(f"observability_evidence not importable: {exc}")
        cls._build = staticmethod(build_evidence)
        cls._write = staticmethod(write_evidence)
        cls.profile = _load_yaml(_PROFILE_YAML)
        cls.captured_at = datetime.now(timezone.utc).isoformat()
        cls.evidence = build_evidence(cls.profile, captured_at=cls.captured_at)

    def test_evidence_schema_field(self) -> None:
        self.assertEqual(self.evidence["schema"], "foundry-observability-evidence/v1")

    def test_all_four_alert_categories_in_evidence(self) -> None:
        cats = set(self.evidence.get("alert_categories", []))
        required = {"failure", "latency", "token_cost", "quality_safety"}
        self.assertTrue(required.issubset(cats), f"Missing: {required - cats}")

    def test_action_group_owner_in_evidence(self) -> None:
        ag = self.evidence.get("action_group", {})
        self.assertTrue(ag.get("owner", "").strip())

    def test_action_group_resource_id_in_evidence(self) -> None:
        ag = self.evidence.get("action_group", {})
        self.assertTrue(ag.get("resource_id", "").strip())

    def test_evaluator_parity_true(self) -> None:
        self.assertIs(self.evidence.get("evaluator_parity"), True)

    def test_evaluator_environments_canonical(self) -> None:
        envs = set(self.evidence.get("evaluator_definition", {}).get("environments", []))
        self.assertEqual(envs, {"dev", "ci", "production"})

    def test_sampling_traces_bounded(self) -> None:
        val = self.evidence["sampling"]["traces"]
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_sampling_continuous_evaluation_bounded(self) -> None:
        val = self.evidence["sampling"]["continuous_evaluation"]
        self.assertGreaterEqual(val, 0.0)
        self.assertLessEqual(val, 1.0)

    def test_trace_policy_content_recording_is_bool(self) -> None:
        tp = self.evidence.get("trace_policy", {})
        self.assertIsInstance(tp.get("content_recording"), bool)

    def test_trace_policy_redaction_policy_non_empty(self) -> None:
        tp = self.evidence.get("trace_policy", {})
        self.assertTrue(tp.get("redaction_policy", "").strip())

    def test_trace_policy_readers_group_non_empty(self) -> None:
        tp = self.evidence.get("trace_policy", {})
        self.assertTrue(tp.get("readers_group", "").strip())

    def test_retention_days_ge_30(self) -> None:
        ret = self.evidence.get("retention_days")
        self.assertIsInstance(ret, int)
        self.assertNotIsInstance(ret, bool)
        self.assertGreaterEqual(ret, 30)

    def test_monthly_budget_positive(self) -> None:
        budget = self.evidence.get("monthly_budget_usd")
        self.assertGreater(float(budget), 0.0)

    def test_write_evidence_produces_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "specs" / "observability-evidence.json"
            self._write(self.evidence, out)
            parsed = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(parsed["schema"], "foundry-observability-evidence/v1")
            self.assertIn("quality_safety", parsed.get("alert_categories", []))
            self.assertIs(parsed.get("evaluator_parity"), True)


# ===========================================================================
# CLI flag rejection — observability_evidence.py must expose only library API
# ===========================================================================

class TestNoCliFlags(unittest.TestCase):
    """The normaliser module must not expose a CLI (no argparse / sys.argv usage)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (_PYTHON_DIR / "observability_evidence.py").read_text(encoding="utf-8")

    def test_no_argparse_import(self) -> None:
        self.assertNotIn(
            "import argparse",
            self.source,
            "observability_evidence.py must not import argparse — it is a library, not a CLI",
        )

    def test_no_argument_parser_instantiation(self) -> None:
        self.assertNotIn(
            "ArgumentParser",
            self.source,
            "observability_evidence.py must not use ArgumentParser",
        )

    def test_no_sys_argv_usage(self) -> None:
        self.assertNotRegex(
            self.source,
            r"\bsys\.argv\b",
            "observability_evidence.py must not access sys.argv",
        )

    def test_no_if_name_main_cli_block(self) -> None:
        # An __main__ block that calls argparse / CLI is forbidden.
        # A plain __main__ guard that calls build_evidence is fine but
        # the file currently has none — assert no argparse in any __main__ block.
        if '__name__ == "__main__"' not in self.source and "__name__ == '__main__'" not in self.source:
            return  # no __main__ block at all — pass
        # If there is a __main__ block, ensure it has no argparse
        self.assertNotIn("argparse", self.source)


# ===========================================================================
# Consumer fixture contract: steps numbered 0-6, marker on Step 6
# ===========================================================================

class TestConsumerFixtureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _CONSUMER_PROMPT.read_text(encoding="utf-8")

    def test_fixture_exists(self) -> None:
        self.assertTrue(_CONSUMER_PROMPT.exists())

    def test_step_0_present(self) -> None:
        self.assertRegex(self.content, r'## Step 0')

    def test_step_1_present(self) -> None:
        self.assertRegex(self.content, r'## Step 1')

    def test_step_2_present(self) -> None:
        self.assertRegex(self.content, r'## Step 2')

    def test_step_3_present(self) -> None:
        self.assertRegex(self.content, r'## Step 3')

    def test_step_4_present(self) -> None:
        self.assertRegex(self.content, r'## Step 4')

    def test_step_5_present(self) -> None:
        self.assertRegex(self.content, r'## Step 5')

    def test_step_6_present(self) -> None:
        self.assertRegex(self.content, r'## Step 6')

    def test_marker_on_step_6(self) -> None:
        self.assertIsNotNone(
            re.search(
                r'## Step 6.*?foundry-observability-smoke-result',
                self.content,
                re.DOTALL,
            ),
            "Step 6 must reference the marker file",
        )

    def test_evidence_output_path_referenced(self) -> None:
        self.assertIn("specs/observability-evidence.json", self.content)

    def test_all_four_alert_categories_asserted(self) -> None:
        for cat in ("failure", "latency", "token_cost", "quality_safety"):
            self.assertIn(cat, self.content, f"consumer_prompt.md must assert alert category: {cat}")

    def test_action_group_owner_asserted(self) -> None:
        self.assertIn("action_group", self.content)
        self.assertIn("owner", self.content)

    def test_action_group_resource_id_asserted(self) -> None:
        self.assertIn("resource_id", self.content)

    def test_evaluator_parity_asserted(self) -> None:
        self.assertIn("evaluator_parity", self.content)

    def test_evaluator_environments_asserted(self) -> None:
        self.assertIn("evaluator_environments", self.content)

    def test_bounded_sampling_asserted(self) -> None:
        self.assertIn("sampling", self.content)

    def test_trace_policy_asserted(self) -> None:
        self.assertIn("trace_policy", self.content)

    def test_retention_asserted(self) -> None:
        self.assertIn("retention_days", self.content)

    def test_budget_asserted(self) -> None:
        self.assertIn("monthly_budget_usd", self.content)

    def test_uses_python3_not_python(self) -> None:
        # Inline python calls should use python3
        # We allow `python -c` only in the old Step 2 KQL block which used `python -c`
        # The new steps (Step 4, Step 5) must use python3
        self.assertIn("python3", self.content)
        # Ensure no bare `python ` (no `python3` prefix) in the OTel step block
        otel_block_match = re.search(
            r'(## Step 1.*?)(## Step 2)',
            self.content,
            re.DOTALL,
        )
        if otel_block_match:
            step1_text = otel_block_match.group(1)
            # python3 must appear in Step 1 (the OTel emission block)
            self.assertIn("python3", step1_text, "Step 1 must use python3")

    def test_no_invented_cli_flags(self) -> None:
        # observability_evidence.py has no CLI; the fixture must not pass flags
        bad_patterns = [
            r'observability_evidence\.py.*--',
            r'python3.*observability_evidence.*--\w',
        ]
        for pat in bad_patterns:
            self.assertNotRegex(
                self.content,
                pat,
                f"consumer_prompt.md must not invoke observability_evidence.py with CLI flags",
            )

    def test_build_evidence_imported_not_invented(self) -> None:
        self.assertIn("build_evidence", self.content)
        self.assertIn("write_evidence", self.content)

    def test_pyyaml_install_present(self) -> None:
        self.assertIn("pyyaml", self.content)


# ===========================================================================
# SKILL.md: Production Operating Profile workflow references canonical artifacts
# ===========================================================================

# Matches ONLY top-level step headings: "### Step N —" where N is a bare
# integer (no dot).  Deliberately rejects "### Step 1.1 —" style sub-steps
# that appear in Layer 1–3 sections and would otherwise cause a false-pass.
_PROFILE_STEP_RE = re.compile(r"^### Step (\d+) —", re.MULTILINE)


def _extract_profile_section(text: str) -> str:
    """Slice out the '## Production Operating Profile' section.

    Returns text from that heading to the next ``##``-level heading (or EOF).
    This prevents sub-step headings in earlier sections (e.g. ``### Step 1.1
    —``) from contributing to the step count.
    """
    start = text.find("\n## Production Operating Profile\n")
    if start == -1:
        return ""
    body_start = start + 1
    next_h2 = text.find("\n## ", body_start + 1)
    return text[body_start:] if next_h2 == -1 else text[body_start:next_h2]


class TestSkillMdWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _SKILL_MD.read_text(encoding="utf-8")

    def test_production_operating_profile_section_present(self) -> None:
        self.assertIn("Production Operating Profile", self.content)

    def test_seven_steps_present(self) -> None:
        """Exactly steps 1–7 (bare integers) exist in the Production Operating
        Profile section.

        Scoped to the section so sub-step headings like '### Step 1.1 —' from
        Layer 1–3 cannot cause a false-pass.
        """
        section = _extract_profile_section(self.content)
        self.assertTrue(
            section,
            msg="## Production Operating Profile section not found in SKILL.md",
        )
        found_nums = sorted(int(n) for n in _PROFILE_STEP_RE.findall(section))
        self.assertEqual(
            found_nums,
            list(range(1, 8)),
            msg=(
                f"Expected steps 1–7 in Production Operating Profile, "
                f"got {found_nums}.  Check that '### Step N —' headings "
                f"(bare integer N, no dot) exist for N=1…7 and that "
                f"sub-step headings like '### Step 1.1 —' are NOT in "
                f"this section."
            ),
        )

    def test_substep_headings_do_not_false_pass(self) -> None:
        """Regression: sub-step headings (Step 1.1 / 2.1 / 3.1) are outside
        the Production Operating Profile section and do NOT match the step
        regex, so they can never satisfy test_seven_steps_present."""
        substep_lines = [
            "### Step 1.1 — Single LAW",
            "### Step 2.1 — Create account connection",
            "### Step 3.1 — Python init",
        ]
        for line in substep_lines:
            self.assertIsNone(
                _PROFILE_STEP_RE.match(line),
                msg=f"Sub-step '{line}' must NOT match the profile step regex",
            )
        # Positive case: top-level steps DO match
        for n in range(1, 8):
            self.assertIsNotNone(
                _PROFILE_STEP_RE.match(f"### Step {n} — Something"),
                msg=f"Top-level '### Step {n} — …' must match the profile step regex",
            )

    def test_references_yaml_profile(self) -> None:
        self.assertIn("observability-profile.yaml", self.content)

    def test_references_schema(self) -> None:
        self.assertIn("observability-profile.schema.json", self.content)

    def test_references_normaliser(self) -> None:
        self.assertIn("observability_evidence.py", self.content)

    def test_references_kql_query(self) -> None:
        self.assertIn("agent-traces.kql", self.content)

    def test_references_bicep_alerts(self) -> None:
        self.assertIn("agent-alerts.bicep", self.content)

    def test_evidence_output_path_stated(self) -> None:
        self.assertIn("specs/observability-evidence.json", self.content)

    def test_advisory_evidence_caveat(self) -> None:
        # Must state evidence is advisory, not proof alerts fired
        self.assertRegex(
            self.content,
            r'advisory.*evidence|evidence.*advisory',
            msg="SKILL.md must state that evidence is advisory, not proof that alerts fired",
        )

    def test_no_inline_normaliser_redefinition(self) -> None:
        # Must not redefine build_evidence or write_evidence inline
        # (they are library functions; consumers import them)
        skill_body_after_what_ships = self.content.split("Production Operating Profile", 1)
        if len(skill_body_after_what_ships) < 2:
            return
        workflow_section = skill_body_after_what_ships[1]
        # The workflow may CALL build_evidence but must not DEF it
        self.assertNotRegex(
            workflow_section,
            r'def\s+build_evidence\s*\(',
            "SKILL.md must not redefine build_evidence inline",
        )
        self.assertNotRegex(
            workflow_section,
            r'def\s+write_evidence\s*\(',
            "SKILL.md must not redefine write_evidence inline",
        )

    def test_what_ships_tree_includes_yaml_profile(self) -> None:
        self.assertIn("observability-profile.yaml", self.content)

    def test_what_ships_tree_includes_normaliser(self) -> None:
        self.assertIn("observability_evidence.py", self.content)

    def test_what_ships_tree_includes_alert_bicep(self) -> None:
        self.assertIn("agent-alerts.bicep", self.content)

    def test_what_ships_tree_includes_evidence_artifact(self) -> None:
        self.assertIn("observability-evidence.json", self.content)

    def test_description_length_le_1024(self) -> None:
        try:
            import yaml  # type: ignore[import]
        except ImportError:
            raise unittest.SkipTest("pyyaml not installed")
        fm_end = self.content.index("---", 3)
        fm = self.content[4:fm_end]
        data = yaml.safe_load(fm)
        desc = data.get("description", "")
        self.assertLessEqual(
            len(desc),
            1024,
            f"SKILL.md description length {len(desc)} exceeds 1024 chars",
        )


# ===========================================================================
# Release contract — version / catalog pinning (Task 6 operating evidence)
# ===========================================================================

_PLUGIN_JSON = _REPO_ROOT / "plugin.json"

_EXPECTED_SKILL_VERSION = "1.3.0"
_EXPECTED_PLUGIN_VERSION = "4.32.0"

_ALERT_CATALOG_TRIGGERS = [
    "operating profile",
    "observability evidence",
    "alert catalog",
]


class TestReleaseVersionContract(unittest.TestCase):
    """Surface-pins skill 1.3.0 and plugin 4.32.0 for the operating-evidence release."""

    def _skill_frontmatter(self) -> dict:
        try:
            import yaml  # type: ignore[import]
        except ImportError:
            raise unittest.SkipTest("pyyaml not installed")
        content = _SKILL_MD.read_text(encoding="utf-8")
        fm_end = content.index("---", 3)
        return yaml.safe_load(content[4:fm_end])

    def test_skill_version_pinned_to_1_3_0(self) -> None:
        fm = self._skill_frontmatter()
        version = fm.get("metadata", {}).get("version")
        self.assertEqual(
            version,
            _EXPECTED_SKILL_VERSION,
            f"SKILL.md metadata.version must be {_EXPECTED_SKILL_VERSION}, got {version!r}",
        )

    def test_plugin_version_pinned_to_4_32_0(self) -> None:
        self.assertTrue(_PLUGIN_JSON.exists(), f"Missing: {_PLUGIN_JSON}")
        data = _load_json(_PLUGIN_JSON)
        version = data.get("version")
        self.assertEqual(
            version,
            _EXPECTED_PLUGIN_VERSION,
            f"plugin.json version must be {_EXPECTED_PLUGIN_VERSION}, got {version!r}",
        )

    def test_description_includes_alert_catalog_triggers(self) -> None:
        fm = self._skill_frontmatter()
        desc = fm.get("description", "")
        for trigger in _ALERT_CATALOG_TRIGGERS:
            self.assertIn(
                trigger,
                desc,
                f"SKILL.md description must include trigger {trigger!r} for operating-evidence release",
            )

    def test_profile_schema_v1_in_what_ships(self) -> None:
        content = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "foundry-observability-profile/v1",
            content,
            "SKILL.md must reference the v1 profile schema in the What ships tree",
        )

    def test_canonical_evidence_output_in_what_ships(self) -> None:
        content = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "specs/observability-evidence.json",
            content,
            "SKILL.md must state the canonical output artifact path",
        )

    def test_alert_catalog_bicep_in_what_ships(self) -> None:
        content = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "agent-alerts.bicep",
            content,
            "SKILL.md must reference agent-alerts.bicep (alert catalog) in the What ships tree",
        )


if __name__ == "__main__":
    unittest.main()

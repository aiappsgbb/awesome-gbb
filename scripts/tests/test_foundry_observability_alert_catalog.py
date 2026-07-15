"""Unit tests for the foundry-observability agent alert catalog (Task 2).

Validates static invariants across the three new artifact files:

  references/queries/agt-denial-rate.kql
  references/queries/eval-quality-drift.kql
  references/bicep/agent-alerts.bicep

Tests pin KQL semantic anchors, exactly-four Bicep resources, action-group
and scopes wiring, API version, query category mapping, and absence of an
implicit actionGroups resource creation.

Convention: ``unittest.TestCase`` (NOT pytest fixtures) so that
``python -m unittest discover -s scripts/tests -p 'test_*.py' -v``
(invoked by ``.github/workflows/skill-test.yml::unit-tests``) discovers
and runs these tests automatically.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve file paths relative to repo root.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_QUERIES_DIR = _REPO_ROOT / "skills" / "foundry-observability" / "references" / "queries"
_BICEP_DIR   = _REPO_ROOT / "skills" / "foundry-observability" / "references" / "bicep"

_AGT_DENIAL_KQL  = _QUERIES_DIR / "agt-denial-rate.kql"
_EVAL_DRIFT_KQL  = _QUERIES_DIR / "eval-quality-drift.kql"
_AGENT_ALERTS_BICEP = _BICEP_DIR / "agent-alerts.bicep"


# ===========================================================================
# agt-denial-rate.kql
# ===========================================================================

class TestAgtDenialRateKql(unittest.TestCase):
    """Semantic anchors for the AGT governance denial-rate query."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGT_DENIAL_KQL.read_text(encoding="utf-8")

    def test_file_exists(self) -> None:
        self.assertTrue(_AGT_DENIAL_KQL.exists(), f"Missing: {_AGT_DENIAL_KQL}")

    def test_targets_app_metrics_table(self) -> None:
        self.assertIn("AppMetrics", self.content)

    def test_filters_agent_governance_prefix(self) -> None:
        # Must match metrics whose Name starts with "agent_governance."
        self.assertIn("agent_governance.", self.content)

    def test_filters_decision_deny(self) -> None:
        # Must identify "deny" decisions
        self.assertIn("deny", self.content)

    def test_uses_five_minute_bins(self) -> None:
        # 5m binning per plan
        self.assertRegex(self.content, r'bin\s*\(.*,\s*5m\s*\)')

    def test_uses_window_of_15m(self) -> None:
        # 15-minute rolling window
        self.assertIn("15m", self.content)

    def test_divide_by_zero_guard(self) -> None:
        # Must filter out zero-total bins before dividing
        # Acceptable patterns: "where total > 0" or "where isnotempty" etc.
        self.assertTrue(
            "total > 0" in self.content or "count() > 0" in self.content,
            "agt-denial-rate.kql must guard against divide-by-zero (e.g. 'where total > 0')"
        )

    def test_safe_float_division(self) -> None:
        # todouble() ensures float division, avoiding integer truncation
        self.assertIn("todouble", self.content)

    def test_denial_rate_threshold_present(self) -> None:
        # The default 0.20 threshold must be declared
        self.assertIn("0.20", self.content)


# ===========================================================================
# eval-quality-drift.kql
# ===========================================================================

class TestEvalQualityDriftKql(unittest.TestCase):
    """Semantic anchors for the evaluation pass-rate drift query."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _EVAL_DRIFT_KQL.read_text(encoding="utf-8")

    def test_file_exists(self) -> None:
        self.assertTrue(_EVAL_DRIFT_KQL.exists(), f"Missing: {_EVAL_DRIFT_KQL}")

    def test_targets_app_metrics_table(self) -> None:
        self.assertIn("AppMetrics", self.content)

    def test_filters_eval_pass_rate_metric(self) -> None:
        self.assertIn("agent_eval.pass_rate", self.content)

    def test_recent_window_is_1h(self) -> None:
        self.assertIn("ago(1h)", self.content)

    def test_baseline_starts_at_8d(self) -> None:
        self.assertIn("ago(8d)", self.content)

    def test_baseline_ends_at_1d(self) -> None:
        self.assertIn("ago(1d)", self.content)

    def test_delta_threshold_is_minus_5pct(self) -> None:
        # Default threshold must be -0.05 (5 percentage-point drop)
        self.assertIn("-0.05", self.content)

    def test_missing_data_guard_isfinite(self) -> None:
        # isfinite() must be present to suppress alerts when data is absent
        self.assertIn("isfinite", self.content)

    def test_no_division_without_count_guard(self) -> None:
        # Any division (/) must be guarded by a Count > 0 filter upstream.
        # Check that every division is accompanied by a count guard in the file.
        has_division = "/" in self.content
        has_count_guard = "Count > 0" in self.content or "count() > 0" in self.content.lower()
        if has_division:
            self.assertTrue(
                has_count_guard,
                "eval-quality-drift.kql divides but lacks a Count > 0 guard"
            )


# ===========================================================================
# agent-alerts.bicep — structural invariants
# ===========================================================================

class TestAgentAlertsBicepStructure(unittest.TestCase):
    """Structural invariants checked against the raw Bicep source text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGENT_ALERTS_BICEP.read_text(encoding="utf-8")

    def test_file_exists(self) -> None:
        self.assertTrue(_AGENT_ALERTS_BICEP.exists(), f"Missing: {_AGENT_ALERTS_BICEP}")

    def test_api_version_is_2023_12_01(self) -> None:
        self.assertIn("scheduledQueryRules@2023-12-01", self.content)

    def test_exactly_four_scheduled_query_rules_resources(self) -> None:
        # Count resource *declarations* only (match "scheduledQueryRules@2023-12-01' =")
        # to exclude comment lines that also mention the API version.
        count = len(re.findall(r"scheduledQueryRules@2023-12-01'\s*=", self.content))
        self.assertEqual(count, 4, f"Expected 4 scheduledQueryRules resource declarations, found {count}")

    def test_no_action_group_resource_created(self) -> None:
        # The module must NOT declare a Microsoft.Insights/actionGroups resource.
        self.assertNotIn(
            "Microsoft.Insights/actionGroups",
            self.content,
            "agent-alerts.bicep must NOT create an actionGroups resource"
        )

    def test_action_group_is_parameterized(self) -> None:
        # Must accept actionGroupResourceId as a parameter
        self.assertIn("actionGroupResourceId", self.content)

    def test_scopes_use_telemetry_scope_param(self) -> None:
        self.assertIn("telemetryScopeResourceId", self.content)

    def test_action_groups_wired_to_param(self) -> None:
        # The actionGroups var must be defined from actionGroupResourceId …
        self.assertRegex(
            self.content,
            r"var actionGroups\s*=\s*\[actionGroupResourceId\]"
        )
        # … and the resources must use that var in their actions block.
        self.assertIn("actionGroups: actionGroups", self.content)


class TestAgentAlertsBicepCategories(unittest.TestCase):
    """One resource per required operating-profile alert category."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGENT_ALERTS_BICEP.read_text(encoding="utf-8")

    def test_failure_alert_resource_present(self) -> None:
        self.assertIn("-failure'", self.content)

    def test_latency_alert_resource_present(self) -> None:
        self.assertIn("-latency'", self.content)

    def test_token_cost_alert_resource_present(self) -> None:
        self.assertIn("-token-cost'", self.content)

    def test_quality_safety_alert_resource_present(self) -> None:
        self.assertIn("-quality-safety'", self.content)

    def test_failure_uses_app_requests(self) -> None:
        self.assertIn("AppRequests", self.content)

    def test_latency_uses_app_dependencies(self) -> None:
        self.assertIn("AppDependencies", self.content)

    def test_token_cost_uses_app_metrics(self) -> None:
        self.assertIn("AppMetrics", self.content)

    def test_quality_safety_uses_eval_pass_rate(self) -> None:
        self.assertIn("agent_eval.pass_rate", self.content)

    def test_quality_safety_uses_8d_baseline(self) -> None:
        self.assertIn("ago(8d)", self.content)


class TestAgentAlertsBicepOutputs(unittest.TestCase):
    """All four alert IDs and names must be exposed as outputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGENT_ALERTS_BICEP.read_text(encoding="utf-8")

    def test_output_failure_alert_id(self) -> None:
        self.assertIn("failureAlertId", self.content)

    def test_output_failure_alert_name(self) -> None:
        self.assertIn("failureAlertName", self.content)

    def test_output_latency_alert_id(self) -> None:
        self.assertIn("latencyAlertId", self.content)

    def test_output_latency_alert_name(self) -> None:
        self.assertIn("latencyAlertName", self.content)

    def test_output_token_cost_alert_id(self) -> None:
        self.assertIn("tokenCostAlertId", self.content)

    def test_output_token_cost_alert_name(self) -> None:
        self.assertIn("tokenCostAlertName", self.content)

    def test_output_quality_safety_alert_id(self) -> None:
        self.assertIn("qualitySafetyAlertId", self.content)

    def test_output_quality_safety_alert_name(self) -> None:
        self.assertIn("qualitySafetyAlertName", self.content)

    def test_no_secrets_in_outputs(self) -> None:
        # Outputs block must not reference keys/secrets/connectionString
        output_section = self.content[self.content.rfind("// Outputs"):]
        for forbidden in ("connectionString", "primaryKey", "secondaryKey", "@secure"):
            self.assertNotIn(
                forbidden, output_section,
                f"Output section must not expose secret '{forbidden}'"
            )


class TestAgentAlertsBicepParameters(unittest.TestCase):
    """Severity and ISO-duration parameters must have Bicep validation decorators."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGENT_ALERTS_BICEP.read_text(encoding="utf-8")

    def test_severity_has_min_value_decorator(self) -> None:
        self.assertIn("@minValue(0)", self.content)

    def test_severity_has_max_value_decorator(self) -> None:
        self.assertIn("@maxValue(4)", self.content)

    def test_evaluation_frequency_has_allowed_decorator(self) -> None:
        # The @allowed decorator must constrain evaluationFrequency
        self.assertRegex(
            self.content,
            r"@allowed\(\[.*'PT5M'.*\]\)\s*param evaluationFrequency",
            msg="evaluationFrequency must have an @allowed([...]) decorator"
        )

    def test_window_size_has_allowed_decorator(self) -> None:
        self.assertRegex(
            self.content,
            r"@allowed\(\[.*'PT15M'.*\]\)\s*param windowSize",
            msg="windowSize must have an @allowed([...]) decorator"
        )

    def test_quality_window_size_has_allowed_decorator(self) -> None:
        self.assertRegex(
            self.content,
            r"@allowed\(\[.*'P9D'.*\]\)\s*param qualityWindowSize",
            msg="qualityWindowSize must have an @allowed([...]) decorator"
        )

    def test_failure_threshold_has_min_value_decorator(self) -> None:
        self.assertIn("@minValue(0)\nparam failureCountThreshold", self.content)

    def test_latency_threshold_has_min_value_decorator(self) -> None:
        self.assertIn("@minValue(100)\nparam latencyP95ThresholdMs", self.content)

    def test_token_budget_has_min_value_decorator(self) -> None:
        self.assertIn("@minValue(1)\nparam tokenBudgetThreshold", self.content)


if __name__ == "__main__":
    unittest.main()

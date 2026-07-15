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
        self.assertTrue(
            "total > 0" in self.content,
            "agt-denial-rate.kql must guard against divide-by-zero ('where total > 0')"
        )

    def test_safe_float_division(self) -> None:
        # todouble() ensures float division, avoiding integer truncation
        self.assertIn("todouble", self.content)

    def test_denial_rate_threshold_present(self) -> None:
        # The default 0.20 threshold must be declared
        self.assertIn("0.20", self.content)

    # Task 2: metric-value aggregation — reject row-count operators ----------------

    def test_uses_sum_Sum_for_total(self) -> None:
        """total must aggregate metric values via sum(Sum), not row counts."""
        self.assertRegex(
            self.content,
            r'total\s*=\s*sum\s*\(\s*Sum\s*\)',
            "agt-denial-rate.kql must use sum(Sum) for total, not count()",
        )

    def test_uses_sumif_for_denied(self) -> None:
        """denied must aggregate metric values via sumif(Sum, ...), not countif."""
        self.assertRegex(
            self.content,
            r'denied\s*=\s*sumif\s*\(\s*Sum\s*,',
            "agt-denial-rate.kql must use sumif(Sum, ...) for denied, not countif(...)",
        )

    def test_does_not_use_count_row_aggregation(self) -> None:
        """count() row-count aggregation must not appear in the summarize block."""
        # Remove comment lines before checking to avoid false positives in comments.
        non_comment_lines = [
            ln for ln in self.content.splitlines()
            if not ln.lstrip().startswith("//")
        ]
        non_comment = "\n".join(non_comment_lines)
        self.assertNotRegex(
            non_comment,
            r'\bcount\s*\(\s*\)',
            "agt-denial-rate.kql must not use count() — use sum(Sum) instead",
        )

    def test_does_not_use_countif_row_aggregation(self) -> None:
        """countif() row-count aggregation must not appear in the summarize block."""
        non_comment_lines = [
            ln for ln in self.content.splitlines()
            if not ln.lstrip().startswith("//")
        ]
        non_comment = "\n".join(non_comment_lines)
        self.assertNotRegex(
            non_comment,
            r'\bcountif\s*\(',
            "agt-denial-rate.kql must not use countif() — use sumif(Sum, ...) instead",
        )


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
        # Every division must be guarded by Count > 0 upstream.
        has_division = "/" in self.content
        has_count_guard = "Count > 0" in self.content or "count() > 0" in self.content.lower()
        if has_division:
            self.assertTrue(
                has_count_guard,
                "eval-quality-drift.kql divides but lacks a Count > 0 guard"
            )

    def test_two_independent_count_guards(self) -> None:
        """Both recent and baseline sub-queries must have independent Count > 0 guards.

        A single Count > 0 is insufficient — the guard must appear in BOTH the
        recent window and the baseline window sub-queries so that each is
        individually protected against empty aggregation buckets.
        """
        count_guard_occurrences = self.content.count("Count > 0")
        self.assertGreaterEqual(
            count_guard_occurrences,
            2,
            f"eval-quality-drift.kql must contain at least 2 independent 'Count > 0' "
            f"guards (one for recent, one for baseline); found {count_guard_occurrences}",
        )

    def test_division_operator_is_real_not_comment_slash(self) -> None:
        """The division operator must be a genuine KQL operator, not a comment double-slash.

        Strip comment lines (starting with //) and verify that at least one real
        division expression remains (sum(Sum) / sum(Count) pattern).
        """
        non_comment_lines = [
            ln for ln in self.content.splitlines()
            if not ln.lstrip().startswith("//")
        ]
        non_comment = "\n".join(non_comment_lines)
        self.assertRegex(
            non_comment,
            r'sum\s*\(\s*Sum\s*\)\s*/\s*sum\s*\(\s*Count\s*\)',
            "eval-quality-drift.kql must contain a real division expression "
            "'sum(Sum) / sum(Count)' outside of comment lines",
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

    # Task 1: token alert must not double-count metrics ----------------------------

    def test_token_cost_uses_conditional_fallback(self) -> None:
        """Token KQL must use iff() to choose combined vs split — never sums all three."""
        self.assertRegex(
            self.content,
            r'\biff\s*\(\s*combined\s*>\s*0\s*,\s*combined\s*,\s*split\s*\)',
            "kqlTokenCost must use iff(combined > 0, combined, split) to avoid double-counting",
        )

    def test_token_cost_uses_sumif_for_combined_metric(self) -> None:
        """combined must aggregate only gen_ai.client.token.usage via sumif."""
        self.assertRegex(
            self.content,
            r"combined\s*=\s*sumif\s*\(\s*Sum\s*,\s*Name\s*==\s*'gen_ai\.client\.token\.usage'\s*\)",
            "kqlTokenCost must assign combined = sumif(Sum, Name == 'gen_ai.client.token.usage')",
        )

    def test_token_cost_uses_sumif_for_split_metrics(self) -> None:
        """split must aggregate only input+output metrics via sumif."""
        self.assertRegex(
            self.content,
            r"split\s*=\s*sumif\s*\(\s*Sum\s*,\s*Name\s*in\s*\(",
            "kqlTokenCost must assign split = sumif(Sum, Name in (...))",
        )

    def test_token_cost_does_not_sum_all_three_at_once(self) -> None:
        """A naked sum(Sum) over all three metric names must not appear in kqlTokenCost.

        Summing all three at once double-counts when combined and split metrics coexist.
        """
        # Locate the kqlTokenCost variable block in the bicep file.
        # The var block starts at 'var kqlTokenCost' and ends before the next 'var kql'.
        start = self.content.find("var kqlTokenCost")
        self.assertGreater(start, 0, "kqlTokenCost var not found")
        # Find the next 'var kql' occurrence after kqlTokenCost to delimit the block.
        next_var = self.content.find("var kql", start + len("var kqlTokenCost"))
        token_block = self.content[start:next_var] if next_var > 0 else self.content[start:]
        self.assertNotRegex(
            token_block,
            r"\|\s*summarize\s+total_tokens\s*=\s*sum\s*\(\s*Sum\s*\)",
            "kqlTokenCost must not use a single sum(Sum) over all metric names — "
            "that double-counts when combined and split metrics coexist",
        )


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


# ===========================================================================
# agent-alerts.bicep — windowSize >= evaluationFrequency invariant (Task 3)
# ===========================================================================


def _iso8601_to_seconds(duration: str) -> int:
    """Parse a subset of ISO 8601 duration strings to seconds.

    Supports: P<n>D, PT<n>H, PT<n>M, and combinations such as 'PT5M', 'P9D'.
    Sufficient for the allowed values in agent-alerts.bicep.
    """
    pattern = re.compile(
        r'^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$'
    )
    m = pattern.match(duration)
    if not m:
        raise ValueError(f"Unsupported ISO 8601 duration: {duration!r}")
    days    = int(m.group(1) or 0)
    hours   = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    seconds = int(m.group(4) or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


class TestAgentAlertsBicepWindowInvariant(unittest.TestCase):
    """Azure invariant: windowSize >= evaluationFrequency for scheduled query alerts.

    Azure rejects deployments where windowSize < evaluationFrequency at the API
    level.  These tests parse the default parameter values from the Bicep source
    and assert that both parameter pairs (standard and quality) satisfy the
    invariant so that a deployment with all defaults is guaranteed to succeed.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _AGENT_ALERTS_BICEP.read_text(encoding="utf-8")

    def _extract_default(self, param_name: str) -> str:
        """Return the default value string for a Bicep param (e.g. 'PT15M')."""
        m = re.search(
            rf"param\s+{re.escape(param_name)}\s+string\s*=\s*'([^']+)'",
            self.content,
        )
        self.assertIsNotNone(m, f"Could not find default for param {param_name!r}")
        return m.group(1)  # type: ignore[union-attr]

    def test_parse_iso8601_pt5m(self) -> None:
        self.assertEqual(_iso8601_to_seconds("PT5M"), 300)

    def test_parse_iso8601_pt15m(self) -> None:
        self.assertEqual(_iso8601_to_seconds("PT15M"), 900)

    def test_parse_iso8601_pt1h(self) -> None:
        self.assertEqual(_iso8601_to_seconds("PT1H"), 3600)

    def test_parse_iso8601_p9d(self) -> None:
        self.assertEqual(_iso8601_to_seconds("P9D"), 9 * 86400)

    def test_default_evaluation_frequency_extractable(self) -> None:
        default = self._extract_default("evaluationFrequency")
        self.assertIsNotNone(_iso8601_to_seconds(default))

    def test_default_window_size_extractable(self) -> None:
        default = self._extract_default("windowSize")
        self.assertIsNotNone(_iso8601_to_seconds(default))

    def test_default_window_size_ge_evaluation_frequency(self) -> None:
        """Default windowSize must be >= default evaluationFrequency."""
        window_s = _iso8601_to_seconds(self._extract_default("windowSize"))
        freq_s   = _iso8601_to_seconds(self._extract_default("evaluationFrequency"))
        self.assertGreaterEqual(
            window_s,
            freq_s,
            f"Default windowSize ({self._extract_default('windowSize')}) must be "
            f">= evaluationFrequency ({self._extract_default('evaluationFrequency')}) "
            "— Azure enforces this invariant at deployment time",
        )

    def test_default_quality_window_size_ge_quality_evaluation_frequency(self) -> None:
        """Default qualityWindowSize must be >= default qualityEvaluationFrequency."""
        window_s = _iso8601_to_seconds(self._extract_default("qualityWindowSize"))
        freq_s   = _iso8601_to_seconds(self._extract_default("qualityEvaluationFrequency"))
        self.assertGreaterEqual(
            window_s,
            freq_s,
            f"Default qualityWindowSize ({self._extract_default('qualityWindowSize')}) must be "
            f">= qualityEvaluationFrequency ({self._extract_default('qualityEvaluationFrequency')}) "
            "— Azure enforces this invariant at deployment time",
        )

    def test_invariant_documented_adjacent_to_window_size_param(self) -> None:
        """The Azure windowSize >= evaluationFrequency invariant must be documented
        adjacent to the windowSize parameter in the Bicep file."""
        self.assertIn(
            "windowSize",
            self.content,
            "windowSize param must be present",
        )
        # Check that the invariant comment appears in the bicep near the param block.
        self.assertRegex(
            self.content,
            r"windowSize\s*>=\s*evaluationFrequency",
            "agent-alerts.bicep must document the Azure invariant "
            "'windowSize >= evaluationFrequency' adjacent to the params",
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parents[1] / "check-freshness.py"
_SPEC = importlib.util.spec_from_file_location("check_freshness_issue_mode", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
CF = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = CF
_SPEC.loader.exec_module(CF)


class ExecutionModeLabelsTest(unittest.TestCase):
    def test_manual_mode_adds_manual_review_and_replaces_old_impact(self) -> None:
        signal = CF.Signal(
            skill="fresh-skill",
            signal_type="consolidated",
            severity="warn",
            title="🔄 Refresh `fresh-skill` — consolidated drift",
            body="body",
            automation_tier="auto",
            impact="medium",
        )

        labels = CF.labels_for_execution_mode(
            ["freshness", "automation", "impact:high"],
            signal,
            "manual",
        )

        self.assertEqual(
            labels,
            ["freshness", "automation", "manual-review", "impact:medium"],
        )

    def test_copilot_mode_removes_manual_review(self) -> None:
        signal = CF.Signal(
            skill="fresh-skill",
            signal_type="consolidated",
            severity="warn",
            title="🔄 Refresh `fresh-skill` — consolidated drift",
            body="body",
            automation_tier="auto",
            impact="high",
        )

        labels = CF.labels_for_execution_mode(
            ["freshness", "automation", "manual-review"],
            signal,
            "copilot",
        )

        self.assertEqual(
            labels,
            ["freshness", "automation", "impact:high"],
        )

    def test_manual_report_never_claims_copilot_assignment(self) -> None:
        signal = CF.Signal(
            skill="fresh-skill",
            signal_type="consolidated",
            severity="warn",
            title="🔄 Refresh `fresh-skill` — consolidated drift",
            body="body",
            automation_tier="auto",
            impact="medium",
        )

        report = CF.render_report(
            [signal],
            pin_count=1,
            consolidated=True,
            execution_mode="manual",
        )

        self.assertIn("manual review required", report)
        self.assertNotIn("assigned to @Copilot", report)


class RemoveCopilotAssignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_graphql = CF._graphql

    def tearDown(self) -> None:
        CF._graphql = self._orig_graphql

    def test_removal_preserves_human_assignees(self) -> None:
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"login": "copilot-swe-agent"},
                                    {"login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 2:
                self.assertEqual(variables["actors"], ["HUMAN"])
                return {
                    "replaceActorsForAssignable": {
                        "assignable": {
                            "assignees": {
                                "nodes": [
                                    {"login": "maintainer"},
                                ]
                            }
                        }
                    }
                }
            self.fail(f"unexpected GraphQL call #{len(calls)}")

        CF._graphql = fake_graphql

        self.assertTrue(CF.remove_copilot_from_issue("aiappsgbb/awesome-gbb", 42, "token"))
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()

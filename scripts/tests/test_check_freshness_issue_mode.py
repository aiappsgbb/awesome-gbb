from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any


_SCRIPT = Path(__file__).resolve().parents[1] / "check-freshness.py"
_SPEC = importlib.util.spec_from_file_location("check_freshness_issue_mode", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
CF = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = CF
_SPEC.loader.exec_module(CF)


class FakeResponse:
    """Minimal stand-in for `requests.Response` used by the fake HTTP layer."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


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
                # Removal must resolve the bot's canonical node ID via
                # suggestedActors first — the same lookup assignment uses.
                return {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"id": "COPILOT", "login": "copilot-swe-agent"},
                            ]
                        }
                    }
                }
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "COPILOT", "login": "copilot-swe-agent"},
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
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
        self.assertEqual(len(calls), 3)

    def test_removal_matches_by_actor_id_despite_differing_login_alias(self) -> None:
        """GraphQL can return the SAME actor node ID as Bot/login=copilot-swe-agent
        in suggestedActors and User/login=Copilot in issue.assignees.
        Matching by login alone made remove_copilot_from_issue a silent
        no-op that returned True before any mutation ran. This must match
        by canonical node ID.
        """
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                return {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"id": "BOT", "login": "copilot-swe-agent"},
                            ]
                        }
                    }
                }
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "BOT", "login": "Copilot"},
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
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
        self.assertEqual(len(calls), 3)

    def test_removal_falls_back_to_login_alias_when_bot_id_unresolved(self) -> None:
        """When `suggestedActors` cannot resolve a canonical bot node ID
        (degraded manual mode — e.g. the lookup returns no Copilot actor
        at all), the shared identity check must still recognize the bot
        by login, accepting either `copilot-swe-agent` or `Copilot`, so
        removal still fires a mutation instead of silently no-op'ing.
        """
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                # No Copilot actor present — bot_id resolves to None.
                return {"repository": {"suggestedActors": {"nodes": []}}}
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "BOT", "login": "Copilot"},
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
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
        self.assertEqual(len(calls), 3)


class AssignCopilotAssignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_graphql = CF._graphql

    def tearDown(self) -> None:
        CF._graphql = self._orig_graphql

    def test_assignment_preserves_existing_human_assignees(self) -> None:
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                return {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"id": "BOT", "login": "copilot-swe-agent"},
                            ]
                        }
                    }
                }
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
                self.assertEqual(variables["actors"], ["HUMAN", "BOT"])
                return {
                    "replaceActorsForAssignable": {
                        "assignable": {
                            "assignees": {
                                "nodes": [
                                    {"login": "maintainer"},
                                    {"login": "copilot-swe-agent"},
                                ]
                            }
                        }
                    }
                }
            self.fail(f"unexpected GraphQL call #{len(calls)}")

        CF._graphql = fake_graphql

        self.assertTrue(CF.assign_copilot_to_issue("aiappsgbb/awesome-gbb", 42, "token"))
        self.assertEqual(len(calls), 3)

    def test_assignment_matches_existing_copilot_alias_by_id_no_duplicate(self) -> None:
        """Preserving existing assignees must use the same identity rule
        as removal (canonical node-ID comparison) so a login-based filter
        can't fail to exclude an aliased `Copilot` entry.
        """
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                return {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"id": "BOT", "login": "copilot-swe-agent"},
                            ]
                        }
                    }
                }
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "BOT", "login": "Copilot"},
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
                self.assertEqual(variables["actors"], ["HUMAN", "BOT"])
                return {
                    "replaceActorsForAssignable": {
                        "assignable": {
                            "assignees": {
                                "nodes": [
                                    {"login": "maintainer"},
                                    {"login": "copilot-swe-agent"},
                                ]
                            }
                        }
                    }
                }
            self.fail(f"unexpected GraphQL call #{len(calls)}")

        CF._graphql = fake_graphql

        self.assertTrue(CF.assign_copilot_to_issue("aiappsgbb/awesome-gbb", 42, "token"))
        self.assertEqual(len(calls), 3)


class CloseResolvedIssuesManualModeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_get = CF.requests.get
        self._orig_patch = CF.requests.patch
        self._orig_remove = CF.remove_copilot_from_issue

    def tearDown(self) -> None:
        CF.requests.get = self._orig_get
        CF.requests.patch = self._orig_patch
        CF.remove_copilot_from_issue = self._orig_remove

    def _search_response(self, labels: list[str], number: int = 7, skill: str = "resolved-skill") -> FakeResponse:
        return FakeResponse(
            200,
            {
                "items": [
                    {
                        "number": number,
                        "url": f"https://api.github.com/repos/aiappsgbb/awesome-gbb/issues/{number}",
                        "title": f"🔄 Refresh `{skill}` — consolidated drift",
                        "body": "old body",
                        "labels": [{"name": label} for label in labels],
                    }
                ]
            },
        )

    def test_manual_mode_removes_copilot_strips_manual_review_then_closes(self) -> None:
        CF.requests.get = lambda *a, **k: self._search_response(
            ["freshness", "automation", "manual-review", "impact:high"]
        )

        removal_calls: list[tuple[str, int, str]] = []

        def fake_remove(repo: str, issue_number: int, gh_token: str) -> bool:
            removal_calls.append((repo, issue_number, gh_token))
            return True

        CF.remove_copilot_from_issue = fake_remove

        patch_calls: list[tuple[str, dict[str, object]]] = []

        def fake_patch(url: str, json: dict[str, object] | None = None, headers: Any = None, timeout: Any = None):
            patch_calls.append((url, json or {}))
            return FakeResponse(200, {})

        CF.requests.patch = fake_patch

        ok = CF.close_resolved_issues(
            skills_with_signals=set(),
            repo="aiappsgbb/awesome-gbb",
            gh_token="token",
            labels=["freshness", "automation"],
            dry_run=False,
            execution_mode="manual",
        )

        self.assertTrue(ok)
        self.assertEqual(removal_calls, [("aiappsgbb/awesome-gbb", 7, "token")])
        self.assertEqual(len(patch_calls), 1)
        _, payload = patch_calls[0]
        self.assertEqual(payload["state"], "closed")
        self.assertNotIn("manual-review", payload["labels"])
        self.assertIn("impact:high", payload["labels"])
        self.assertIn("freshness", payload["labels"])
        self.assertIn("automation", payload["labels"])

    def test_manual_mode_removal_failure_keeps_issue_open_and_returns_false(self) -> None:
        CF.requests.get = lambda *a, **k: self._search_response(["freshness"], number=9, skill="stuck-skill")
        CF.remove_copilot_from_issue = lambda repo, issue_number, gh_token: False

        patch_calls: list[tuple[str, dict[str, object]]] = []

        def fake_patch(url: str, json: dict[str, object] | None = None, headers: Any = None, timeout: Any = None):
            patch_calls.append((url, json or {}))
            return FakeResponse(200, {})

        CF.requests.patch = fake_patch

        ok = CF.close_resolved_issues(
            skills_with_signals=set(),
            repo="aiappsgbb/awesome-gbb",
            gh_token="token",
            labels=["freshness"],
            dry_run=False,
            execution_mode="manual",
        )

        self.assertFalse(ok)
        self.assertEqual(patch_calls, [])

    def test_manual_mode_dry_run_prints_intent_without_mutating(self) -> None:
        CF.requests.get = lambda *a, **k: self._search_response(["freshness"], number=11, skill="dry-skill")

        remove_calls: list[tuple[Any, ...]] = []
        CF.remove_copilot_from_issue = lambda *a, **k: remove_calls.append(a) or True

        patch_calls: list[tuple[str, dict[str, object]]] = []

        def fake_patch(url: str, json: dict[str, object] | None = None, headers: Any = None, timeout: Any = None):
            patch_calls.append((url, json or {}))
            return FakeResponse(200, {})

        CF.requests.patch = fake_patch

        ok = CF.close_resolved_issues(
            skills_with_signals=set(),
            repo="aiappsgbb/awesome-gbb",
            gh_token="token",
            labels=["freshness"],
            dry_run=True,
            execution_mode="manual",
        )

        self.assertTrue(ok)
        self.assertEqual(remove_calls, [])
        self.assertEqual(patch_calls, [])

    def test_missing_labels_key_logs_error_and_still_closes_later_valid_issue(self) -> None:
        """A search result item with no `labels` key at all must not abort
        the whole close loop: it should log a clear ERROR, mark the run as
        failed, skip mutation for that one malformed item, and still
        reconcile/close a later valid resolved issue in the same search
        result — proving one bad item can't hide every other item behind it.
        """
        response = FakeResponse(
            200,
            {
                "items": [
                    {
                        "number": 13,
                        "url": "https://api.github.com/repos/aiappsgbb/awesome-gbb/issues/13",
                        "title": "🔄 Refresh `label-less-skill` — consolidated drift",
                        "body": "old body",
                        # no "labels" key present — malformed shape
                    },
                    {
                        "number": 14,
                        "url": "https://api.github.com/repos/aiappsgbb/awesome-gbb/issues/14",
                        "title": "🔄 Refresh `valid-skill` — consolidated drift",
                        "body": "old body",
                        "labels": [{"name": "freshness"}, {"name": "automation"}],
                    },
                ]
            },
        )
        CF.requests.get = lambda *a, **k: response

        removal_calls: list[tuple[str, int, str]] = []

        def fake_remove(repo: str, issue_number: int, gh_token: str) -> bool:
            removal_calls.append((repo, issue_number, gh_token))
            return True

        CF.remove_copilot_from_issue = fake_remove

        patch_calls: list[tuple[str, dict[str, object]]] = []

        def fake_patch(url: str, json: dict[str, object] | None = None, headers: Any = None, timeout: Any = None):
            patch_calls.append((url, json or {}))
            return FakeResponse(200, {})

        CF.requests.patch = fake_patch

        ok = CF.close_resolved_issues(
            skills_with_signals=set(),
            repo="aiappsgbb/awesome-gbb",
            gh_token="token",
            labels=["freshness"],
            dry_run=False,
            execution_mode="manual",
        )

        self.assertFalse(ok)
        # only the valid second item (#14) is reconciled — the malformed
        # first item (#13) must never reach removal or the close PATCH.
        self.assertEqual(removal_calls, [("aiappsgbb/awesome-gbb", 14, "token")])
        self.assertEqual(len(patch_calls), 1)
        url, payload = patch_calls[0]
        self.assertTrue(url.endswith("/issues/14"))
        self.assertEqual(payload["state"], "closed")

    def test_missing_labels_key_dry_run_reports_failure_without_mutations(self) -> None:
        """Dry-run must behave the same way as a live run when a search
        item has malformed labels: still report the run as failed, but
        make zero mutating calls (no Copilot removal, no PATCH) for
        either the malformed item or the later valid one.
        """
        response = FakeResponse(
            200,
            {
                "items": [
                    {
                        "number": 15,
                        "url": "https://api.github.com/repos/aiappsgbb/awesome-gbb/issues/15",
                        "title": "🔄 Refresh `label-less-skill-2` — consolidated drift",
                        "body": "old body",
                        # no "labels" key present — malformed shape
                    },
                    {
                        "number": 16,
                        "url": "https://api.github.com/repos/aiappsgbb/awesome-gbb/issues/16",
                        "title": "🔄 Refresh `valid-skill-2` — consolidated drift",
                        "body": "old body",
                        "labels": [{"name": "freshness"}],
                    },
                ]
            },
        )
        CF.requests.get = lambda *a, **k: response

        remove_calls: list[tuple[Any, ...]] = []
        CF.remove_copilot_from_issue = lambda *a, **k: remove_calls.append(a) or True

        patch_calls: list[tuple[str, dict[str, object]]] = []

        def fake_patch(url: str, json: dict[str, object] | None = None, headers: Any = None, timeout: Any = None):
            patch_calls.append((url, json or {}))
            return FakeResponse(200, {})

        CF.requests.patch = fake_patch

        ok = CF.close_resolved_issues(
            skills_with_signals=set(),
            repo="aiappsgbb/awesome-gbb",
            gh_token="token",
            labels=["freshness"],
            dry_run=True,
            execution_mode="manual",
        )

        self.assertFalse(ok)
        self.assertEqual(remove_calls, [])
        self.assertEqual(patch_calls, [])


class MainWiringTest(unittest.TestCase):
    """Verifies main()'s own return-code wiring, not close_resolved_issues
    itself (already covered above) — stubs argv/env plus the expensive
    pin-discovery/signal-collection helpers so this only exercises the
    exit-code plumbing.
    """

    def setUp(self) -> None:
        self._orig_argv = sys.argv
        self._orig_discover = CF.discover_pin_files
        self._orig_collect = CF.collect_signals
        self._orig_close = CF.close_resolved_issues

    def tearDown(self) -> None:
        sys.argv = self._orig_argv
        CF.discover_pin_files = self._orig_discover
        CF.collect_signals = self._orig_collect
        CF.close_resolved_issues = self._orig_close

    def test_main_returns_1_when_close_resolved_issues_reports_failure(self) -> None:
        sys.argv = [
            "check-freshness.py",
            "--upsert-issues",
            "--dry-run",
            "--execution-mode",
            "manual",
        ]
        CF.discover_pin_files = lambda: []
        CF.collect_signals = lambda pins, gh_token: []
        CF.close_resolved_issues = lambda *a, **k: False

        self.assertEqual(CF.main(), 1)


class AssignCopilotAssignmentTest(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_graphql = CF._graphql

    def tearDown(self) -> None:
        CF._graphql = self._orig_graphql

    def test_assignment_preserves_existing_human_assignees(self) -> None:
        calls: list[tuple[str, dict[str, object], str]] = []

        def fake_graphql(query: str, variables: dict[str, object], gh_token: str):
            calls.append((query, variables, gh_token))
            if len(calls) == 1:
                return {
                    "repository": {
                        "suggestedActors": {
                            "nodes": [
                                {"id": "BOT", "login": "copilot-swe-agent"},
                            ]
                        }
                    }
                }
            if len(calls) == 2:
                return {
                    "repository": {
                        "issue": {
                            "id": "ISSUE",
                            "assignees": {
                                "nodes": [
                                    {"id": "HUMAN", "login": "maintainer"},
                                ]
                            },
                        }
                    }
                }
            if len(calls) == 3:
                self.assertEqual(variables["actors"], ["HUMAN", "BOT"])
                return {
                    "replaceActorsForAssignable": {
                        "assignable": {
                            "assignees": {
                                "nodes": [
                                    {"login": "maintainer"},
                                    {"login": "copilot-swe-agent"},
                                ]
                            }
                        }
                    }
                }
            self.fail(f"unexpected GraphQL call #{len(calls)}")

        CF._graphql = fake_graphql

        self.assertTrue(CF.assign_copilot_to_issue("aiappsgbb/awesome-gbb", 42, "token"))
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()

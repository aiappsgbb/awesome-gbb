"""Behavioral regressions for the canonical evaluation runner and citation graders."""
from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from openai import APIStatusError, OpenAI
import yaml


ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "skills/foundry-evals/references/python"


def load_reference(name):
    spec = importlib.util.spec_from_file_location(name, REFERENCES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load_reference("eval_runner")
graders = load_reference("url_citation_grader")


class CitationGraderTests(unittest.TestCase):
    def test_resolves_urls_not_markdown_labels(self):
        requested = []

        def handle(request):
            requested.append(str(request.url))
            return httpx.Response(200)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(graders.grade_citation_resolves({
                "agent_output": "[First](https://learn.microsoft.com/a) "
                                "[Second](https://learn.microsoft.com/b)"
            }))
        self.assertEqual(requested, [
            "https://learn.microsoft.com/a", "https://learn.microsoft.com/b"
        ])
        self.assertTrue(result["pass"])

    def test_missing_and_unreachable_citations_do_not_pass(self):
        self.assertFalse(asyncio.run(graders.grade_citation_resolves({
            "agent_output": "No citations."
        }))["pass"])
        client = httpx.AsyncClient(transport=httpx.MockTransport(
            lambda request: httpx.Response(404)
        ))
        with patch("httpx.AsyncClient", return_value=client):
            result = asyncio.run(graders.grade_citation_resolves({
                "agent_output": "[Missing](https://learn.microsoft.com/missing)"
            }))
        self.assertFalse(result["pass"])
        self.assertEqual(result["score"], 0.0)

    def test_presence_retains_public_shape(self):
        self.assertEqual(graders.grade_citation_present({
            "agent_output": "[A](https://learn.microsoft.com/a) "
                            "[B](https://learn.microsoft.com/b)"
        }), {"pass": True, "score": 1.0, "citation_count": 2})


class EvalUnitEnvironmentTests(unittest.TestCase):
    def test_unit_job_installs_the_real_transport_client_dependencies(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/skill-test.yml").read_text())
        install = next(
            step["run"] for step in workflow["jobs"]["unit-tests"]["steps"]
            if step.get("name") == "Install deps"
        )
        self.assertIn("azure-ai-projects~=2.6.0", install)
        self.assertIn("openai~=3.8.0", install)


class EvalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.status = "completed"
        self.items = [{
            "id": "item-one", "object": "eval.run.output_item",
            "datasource_item": {
                "query": "Capital?", "response": "Paris.", "sample.output_text": "Paris.",
            },
            "results": [{"name": "coherence", "score": 5, "passed": True}],
        }]

        def handle(request):
            body = json.loads(request.content) if request.content else None
            self.requests.append((request.method, request.url.path, body))
            if request.method == "DELETE":
                return httpx.Response(200, json={"id": "eval-one", "deleted": True})
            if request.url.path.endswith("/output_items"):
                return httpx.Response(200, content=json.dumps({
                    "object": "list", "data": self.items, "has_more": False,
                }), headers={"content-type": "application/json"})
            if request.url.path.endswith("/evals"):
                return httpx.Response(200, json={"id": "eval-one", "object": "eval"})
            return httpx.Response(200, json={
                "id": "run-one", "object": "eval.run", "status": self.status,
            })

        self.client = OpenAI(
            api_key="unit-test-only", base_url="https://unit.test/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
            max_retries=0,
        )
        self.project = SimpleNamespace(get_openai_client=lambda **kwargs: self.client)
        self.patches = [
            patch.object(runner, "AIProjectClient", return_value=self.project),
            patch.dict(os.environ, {
                "FOUNDRY_PROJECT_ENDPOINT": "https://unit.test/api/projects/test",
                "AZURE_AI_PROJECT_ENDPOINT": "https://unit.test/api/projects/test",
                "JUDGE_MODEL_DEPLOYMENT": "judge",
            }),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.client.close)

    def score(self, **kwargs):
        try:
            return runner.smoke_score("Capital?", "Paris.", **kwargs)
        except (AttributeError, TypeError) as exc:
            self.fail(f"Runner must support the documented evaluation contract: {exc}")

    def test_scores_the_captured_response_and_downloads_real_items(self):
        result = self.score()
        posts = [body for method, _, body in self.requests if method == "POST"]
        self.assertEqual(posts[1]["data_source"]["source"]["content"][0]["item"],
                         {"query": "Capital?", "response": "Paris."})
        self.assertEqual(result["coherence"], 5.0)
        self.assertTrue(any(path.endswith("/output_items") for _, path, _ in self.requests))
        self.assertTrue(any(method == "DELETE" for method, _, _ in self.requests))

    def test_failed_run_is_not_a_quality_pass_and_is_cleaned_up(self):
        self.status = "failed"
        with self.assertRaisesRegex(RuntimeError, "failed"):
            self.score()
        self.assertTrue(any(method == "DELETE" for method, _, _ in self.requests))

    def test_empty_output_is_not_success(self):
        self.items = []
        with self.assertRaisesRegex(RuntimeError, "output|score"):
            self.score()

    def test_zero_score_is_preserved(self):
        self.items[0]["results"][0]["score"] = 0.0
        self.assertEqual(self.score()["coherence"], 0.0)

    def test_agent_target_uses_queries_and_sample_output_mapping(self):
        result = self.score(agent_name="agent-one", agent_version="1")
        posts = [body for method, _, body in self.requests if method == "POST"]
        source = posts[1]["data_source"]
        self.assertEqual(source["type"], "azure_ai_target_completions")
        self.assertEqual(source["target"], {
            "type": "azure_ai_agent", "name": "agent-one", "version": "1"
        })
        self.assertEqual(source["source"]["content"][0]["item"], {"query": "Capital?"})
        self.assertEqual(posts[0]["testing_criteria"][0]["data_mapping"]["response"],
                         "{{sample.output_text}}")
        self.assertEqual(result["coherence"], 5.0)

    def test_timeout_is_bounded_and_does_not_read_unfinished_scores(self):
        self.status = "running"
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            self.score(timeout_seconds=0)
        self.assertFalse(any(path.endswith("/output_items") for _, path, _ in self.requests))

    def test_agent_target_requires_actual_generated_response(self):
        self.items[0]["datasource_item"]["sample.output_text"] = ""
        with self.assertRaisesRegex(RuntimeError, "response"):
            self.score(agent_name="agent-one")

    def test_item_execution_error_cannot_be_hidden_by_a_numeric_score(self):
        self.items[0]["sample"] = {"error": {"code": "server_error"}}
        with self.assertRaisesRegex(RuntimeError, "error"):
            self.score()

    def test_failed_evaluator_status_cannot_pass_with_stale_score(self):
        self.items[0]["results"][0]["status"] = "failed"
        with self.assertRaisesRegex(RuntimeError, "score|error"):
            self.score()

    def test_nonfinite_and_missing_scores_are_not_success(self):
        for value in (float("nan"), None):
            with self.subTest(value=value):
                self.items[0]["results"][0]["score"] = value
                with self.assertRaisesRegex(RuntimeError, "score"):
                    self.score()

    def test_invoke_captures_text_not_run_id(self):
        project = SimpleNamespace(get_openai_client=lambda **kwargs: SimpleNamespace(
            responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
                status="completed", output_text="Paris.",
            ))
        ))
        self.assertEqual(runner.invoke_and_capture(
            "Capital?", "agent-one", project_client=project
        ), "Paris.")

    def test_invoke_rejects_failed_or_empty_response(self):
        for status, output in (("failed", "Paris."), ("completed", "")):
            with self.subTest(status=status, output=output):
                project = SimpleNamespace(get_openai_client=lambda **kwargs: SimpleNamespace(
                    responses=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(
                        status=status, output_text=output,
                    ))
                ))
                with self.assertRaisesRegex(RuntimeError, "failed or empty"):
                    runner.invoke_and_capture("Capital?", "agent-one", project_client=project)

    def test_decision_uses_coherence_scale_not_tool_selection_percentage(self):
        self.assertEqual(runner.decide({"coherence": 3.0}, threshold=3.0), 0)
        self.assertEqual(runner.decide({"coherence": 2.0}, threshold=3.0), 1)
        with self.assertRaises(ValueError):
            runner.decide({"coherence": None})
        with self.assertRaises(ValueError):
            runner.decide({"coherence": True})

    def test_no_unconditional_agent_target_ban_in_skill(self):
        text = (REFERENCES.parents[1] / "SKILL.md").read_text()
        self.assertFalse("target type does **NOT** correctly route" in text,
                         "The universal agent-target ban is obsolete.")


class EvalBudgetTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.delays = {}
        self.requests = []
        self.pages = 0
        self.paginate = False
        self.fail_stage = None

        def handle(request):
            if request.method == "DELETE":
                stage = "cleanup"
            elif request.url.path.endswith("/output_items"):
                self.pages += 1
                stage = f"page-{self.pages}"
            elif request.method == "POST":
                stage = "definition" if request.url.path.endswith("/evals") else "run"
            else:
                stage = "retrieve"
            self.requests.append((stage, dict(request.extensions["timeout"]), request.url))
            self.now += self.delays.get(stage, 0)
            if self.fail_stage == stage:
                return httpx.Response(503, json={"error": {"message": "unavailable"}})
            if stage == "definition":
                return httpx.Response(200, json={"id": "eval-budget", "object": "eval"})
            if stage == "cleanup":
                return httpx.Response(200, json={"id": "eval-budget", "deleted": True})
            if stage.startswith("page-"):
                return httpx.Response(200, json={
                    "object": "list",
                    "data": [{
                        "id": "item-one", "object": "eval.run.output_item",
                        "datasource_item": {"query": "Capital?", "response": "Paris."},
                        "results": [{"name": "coherence", "score": 5.0}],
                    }] if stage == "page-1" else [],
                    "has_more": self.paginate and stage == "page-1",
                })
            return httpx.Response(200, json={
                "id": "run-budget", "object": "eval.run", "status": "completed",
            })

        # Deliberately retain the SDK's default retries and request timeout.
        self.client = OpenAI(
            api_key="unit-test-only", base_url="https://unit.test/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handle)),
        )
        self.addCleanup(self.client.close)
        self.project = SimpleNamespace(get_openai_client=lambda: self.client)
        clock = patch.object(runner.time, "monotonic", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)

    def score(self, **kwargs):
        return runner.smoke_score(
            "Capital?", "Paris.", project_client=self.project, judge_model="judge",
            timeout_seconds=kwargs.pop("timeout_seconds", 300), **kwargs,
        )

    def test_completed_retrieve_after_601_seconds_cannot_pass_300_second_budget(self):
        self.delays["retrieve"] = 601
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            self.score()
        self.assertEqual([stage for stage, _, _ in self.requests],
                         ["definition", "run", "retrieve", "cleanup"])

    def test_definition_and_run_creation_are_inside_the_same_budget(self):
        for stage in ("definition", "run"):
            with self.subTest(stage=stage):
                self.now = 0
                self.pages = 0
                self.requests.clear()
                self.delays = {stage: 301}
                with self.assertRaisesRegex(TimeoutError, "timed out"):
                    self.score()
                self.assertEqual(self.requests[-1][0], "cleanup")
                self.assertFalse(any(s == "retrieve" for s, _, _ in self.requests))

    def test_first_and_subsequent_output_pages_cannot_return_late_scores(self):
        self.paginate = True
        for stage in ("page-1", "page-2"):
            with self.subTest(stage=stage):
                self.now = 0
                self.pages = 0
                self.requests.clear()
                self.delays = {stage: 301}
                with self.assertRaisesRegex(TimeoutError, "timed out"):
                    self.score()

    def test_every_page_uses_remaining_budget_and_cleanup_has_separate_budget(self):
        self.paginate = True
        self.delays = dict.fromkeys(["definition", "run", "retrieve", "page-1", "page-2"], 1)
        self.assertEqual(self.score(timeout_seconds=10), {"coherence": 5.0})
        evaluation_calls = [(stage, timeouts, url) for stage, timeouts, url in self.requests
                            if stage != "cleanup"]
        self.assertEqual([s for s, _, _ in evaluation_calls],
                         ["definition", "run", "retrieve", "page-1", "page-2"])
        for (_, timeouts, _), remaining in zip(evaluation_calls, [10, 9, 8, 7, 6]):
            self.assertTrue(all(0 < value <= remaining for value in timeouts.values()), timeouts)
        self.assertEqual(evaluation_calls[-1][2].params["after"], "item-one")
        cleanup_timeouts = self.requests[-1][1]
        self.assertTrue(all(0 < value <= 30 for value in cleanup_timeouts.values()))

    def test_sdk_retries_are_disabled_for_evaluation_requests(self):
        self.fail_stage = "retrieve"
        with patch("openai._base_client.time.sleep"):
            with self.assertRaises(APIStatusError):
                self.score()
        self.assertEqual(sum(stage == "retrieve" for stage, _, _ in self.requests), 1)

    def test_cleanup_does_not_retry_or_change_the_score_interface(self):
        self.fail_stage = "cleanup"
        with patch("openai._base_client.time.sleep"), patch("sys.stderr", io.StringIO()):
            self.assertEqual(self.score(), {"coherence": 5.0})
        self.assertEqual(sum(stage == "cleanup" for stage, _, _ in self.requests), 1)

    def test_late_cleanup_is_recorded_as_unverified_not_deleted(self):
        self.delays["cleanup"] = 31
        with tempfile.TemporaryDirectory(prefix="eval-budget-", dir=ROOT) as directory:
            artifact = Path(directory) / "evidence.json"
            with patch("sys.stderr", io.StringIO()):
                self.assertEqual(self.score(artifact_path=artifact), {"coherence": 5.0})
            report = json.loads(artifact.read_text())
        self.assertEqual(report["cleanup"], "unverified: TimeoutError")


if __name__ == "__main__":
    unittest.main()

"""Local regression contracts; not a substitute for live tool acceptance."""

import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
SPEC = importlib.util.spec_from_file_location(
    "search_citations", SKILLS / "foundry-toolbox/references/python/search_citations.py"
)
citations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(citations)


class SearchCitationTests(unittest.TestCase):
    def result(self, documents):
        return {"structuredContent": {"documents": documents}}

    def test_extracts_citations_without_dropping_zero_score(self):
        raw = self.result([{"title": "Guide", "url": "https://example.org/guide", "score": 0}])
        self.assertEqual(
            citations.extract_search_citations(raw),
            [{"title": "Guide", "url": "https://example.org/guide"}],
        )
        self.assertEqual(raw["structuredContent"]["documents"][0]["score"], 0)

    def test_empty_documents_are_explicitly_empty(self):
        self.assertEqual(citations.extract_search_citations(self.result([])), [])

    def test_rejects_error_and_missing_or_wrong_schema(self):
        for raw in ({}, {"isError": True}, {"structuredContent": {"documents": {}}}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                citations.extract_search_citations(raw)

    def test_rejects_partial_malformed_documents(self):
        for document in (None, {}, {"title": "", "url": "https://example.org"},
                         {"title": "Source", "url": None}):
            with self.subTest(document=document), self.assertRaises(ValueError):
                citations.extract_search_citations(self.result([document]))

    def test_rejects_unsafe_urls(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "/relative",
                    "https://user:password@example.org", "https://", "https://example.org/a b",
                    "https://example.org/\nspoof", "https://[invalid",
                    "https://example.org/\x00spoof", "https://example.org\\@elsewhere.org"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                citations.extract_search_citations(self.result([{"title": "Source", "url": url}]))


class FoundationDocumentationTests(unittest.TestCase):
    def body(self, skill):
        return (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")

    def test_enriched_example_and_nested_outputs_are_json(self):
        body = self.body("foundry-evals").split("### Enriched dataset shape", 1)[1]
        data = json.loads(re.search(r"```json\n(.*?)```", body, re.S).group(1))
        self.assertEqual(len(data["tool_calls"]), len(data["tool_outputs"]))
        for output in data["tool_outputs"]:
            self.assertIsInstance(json.loads(output["output"]), dict)
        for definition in data["tool_definitions"]:
            self.assertEqual(definition["parameters"]["type"], "object")

    def test_eval_handoffs_have_real_targets_and_honest_scope(self):
        body = self.body("foundry-evals")
        for broken in ("../foundry-assert/", "../foundry-agent-optimizer/",
                       "from .sources import fetch_spans", '"type": "telemetry"'):
            self.assertNotIn(broken, body)
        self.assertIn("Bounded implementation handoff, not a shipped job scaffold", body)
        self.assertIn("not demonstrated by current", body)
        self.assertIn("threadlight-evals-manifest/v1", body)
        self.assertIn("one-item coherence", (SKILLS / "foundry-evals/references/native-lifecycle.md").read_text())

    def test_skill_updates_keep_history_and_staging(self):
        body = self.body("foundry-skill-catalog")
        self.assertIn("default=False", body)
        self.assertIn("delete-first", body)
        self.assertIn("not an unpromoted staging", body)
        for command in re.findall(r"```bash\n(.*?)```", body, re.S):
            self.assertNotIn("--force", command)

    def test_toolbox_preserves_stable_paths(self):
        body = self.body("foundry-toolbox")
        self.assertNotIn("**`azd` only supports CREATE**", body)
        self.assertIn("ToolSearchToolboxTool", body)
        self.assertIn("A2A 1.0 management without a runtime upgrade", body)
        self.assertIn("connection add --from-file", body)
        self.assertIn("structuredContent.documents[]", body)


if __name__ == "__main__":
    unittest.main()

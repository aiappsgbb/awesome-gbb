"""Packaging and instruction regressions, not evidence of audience comprehension."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "gbb-pptx"


def read(relative: str) -> str:
    return (SKILL / relative).read_text(encoding="utf-8")


class GbbPptxContractTests(unittest.TestCase):
    def test_frontmatter_and_existing_triggers(self) -> None:
        text = read("SKILL.md")
        self.assertTrue(text.startswith("---\nname: gbb-pptx\ndescription: >\n"))
        data = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(set(data), {"name", "description", "metadata"})
        self.assertEqual(data["name"], SKILL.name)
        self.assertEqual(data["metadata"]["version"], "2.1.0")
        description = data["description"]
        self.assertGreaterEqual(len(description), 200)
        self.assertLessEqual(len(description), 1024)
        for trigger in (
            "create PowerPoint", "generate PPTX", "make slide deck",
            "build presentation", "convert markdown to slides", "pitch deck",
            "report as PPTX", "create slides", "gbb-pptx", "gbb deck",
            "dark-themed deck",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, description)
        self.assertIn("DO NOT USE FOR:", description)

    def test_local_links_and_anchors_resolve(self) -> None:
        for path in SKILL.rglob("*.md"):
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in link:
                    continue
                target, _, anchor = link.partition("#")
                destination = (path.parent / target).resolve() if target else path
                with self.subTest(path=path.name, link=link):
                    self.assertTrue(destination.exists(), str(destination))
                    if destination.is_dir():
                        destination /= "SKILL.md"
                    self.assertTrue(destination.is_file(), str(destination))
                    if anchor:
                        headings = re.findall(
                            r"^#{1,6} (.+)$", destination.read_text(encoding="utf-8"),
                            re.MULTILINE,
                        )
                        slugs = {
                            re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
                            for heading in headings
                        }
                        self.assertIn(anchor, slugs)

    def test_editorial_work_precedes_generation(self) -> None:
        text = read("SKILL.md")
        headings = (
            "### Establish the brief", "### Build the argument",
            "### Draft the storyboard", "### Review before rendering",
            "### Generate and verify", "## Core Patterns",
        )
        offsets = [text.index(heading) for heading in headings]
        self.assertEqual(offsets, sorted(offsets))
        for reference in ("content", "evidence", "examples", "review"):
            self.assertIn(f"(references/{reference}.md)", text)
        self.assertIn("(templates/storyboard.md)", text)
        self.assertIn("Load only the relevant reference", text)

    def test_small_edits_and_approved_content_do_not_restart_planning(self) -> None:
        text = read("SKILL.md")
        for path in ("Audit or plan only", "Targeted revision", "Render approved content"):
            self.assertIn(path, text)
        self.assertIn("do not rewrite files or render", text)
        self.assertIn("Preserve unaffected slides", text)
        self.assertIn("second routine approval gate", text)
        self.assertIn("Do not run two generators", text)

    def test_evidence_rules_preserve_scope_and_uncertainty(self) -> None:
        text = read("references/evidence.md")
        for term in (
            "Source-reported claim", "Interpretation", "Estimate or hypothesis",
            "Synthetic illustration", "Missing or conflicting evidence",
            "denominator", "formula", "contradictory evidence",
            "nor automatically a 25% cost saving", "Correlation",
            "Never send confidential", "not the full chapter",
        ):
            self.assertIn(term, text)
        self.assertIn("A source\nlink in notes does not repair", text)

    def test_storyboard_carries_content_through_delivery(self) -> None:
        text = read("templates/storyboard.md")
        for field in (
            "Audience and prior knowledge", "Intended understanding",
            "Delivery:", "Central message", "Title-only storyline",
            "Visible content:", "Implication and reasoning",
            "Material caveat", "Source IDs", "Sources and gaps",
            "Required facts and caveats", "actual output",
        ):
            self.assertIn(field, text)
        self.assertIn("omit fields that genuinely do not apply", text)

    def test_structures_are_purpose_specific_not_universal(self) -> None:
        text = read("references/content.md")
        for purpose in (
            "Executive decision", "Technical explanation", "Persuasive proposal",
            "Training", "Progress update", "Exploratory discussion",
        ):
            self.assertIn(purpose, text)
        self.assertIn("not mandatory sequences or slide counts", text)
        self.assertIn("Do not assume exported PDFs include notes", text)
        self.assertIn("not slide count", text)
        self.assertIn("do not enforce three bullets", read("SKILL.md"))

    def test_examples_distinguish_observation_from_unsupported_inference(self) -> None:
        text = read("references/examples.md")
        self.assertIn("**synthetic**", text)
        for title in (
            "Decision:", "Technical explanation:", "Training:",
            "Update:", "Revision scope:",
        ):
            self.assertIn(f"## {title}", text)
        self.assertIn("cost, quality, scale and causality", text.lower())
        self.assertIn("uncontrolled sample", text)
        self.assertIn("proposed design", text)
        self.assertIn("No completion forecast", text)

    def test_review_rejects_false_quality_certification(self) -> None:
        text = read("references/review.md")
        self.assertIn("**Blocking:**", text)
        self.assertIn("beside the claim", text)
        self.assertIn("not proof that every text box is visible", text)
        self.assertIn("representative reader", text)
        self.assertIn("same input, audience, purpose", text)
        self.assertIn("synthetic example cannot replace", text)

    def test_renderer_blocks_compile_and_preserve_interfaces(self) -> None:
        blocks = re.findall(r"```python\n(.*?)\n```", read("SKILL.md"), re.DOTALL)
        self.assertEqual(len(blocks), 11)
        functions = {}
        for index, block in enumerate(blocks):
            tree = ast.parse(block)
            compile(tree, f"gbb-pptx-block-{index}", "exec")
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    functions[node.name] = [argument.arg for argument in node.args.args]
        self.assertEqual(functions, {
            "set_bg": ["slide", "color"],
            "text_box": ["slide", "left", "top", "width", "height", "text",
                         "font_size", "color", "bold", "align", "font"],
            "bullet_list": ["slide", "left", "top", "width", "height", "items",
                            "font_size", "color"],
            "card": ["slide", "left", "top", "width", "height", "fill", "border"],
            "accent_bar": ["slide", "left", "top", "width", "height", "color"],
            "add_notes": ["slide", "text"],
        })

    def test_scenarios_have_observable_expectations_without_pass_claims(self) -> None:
        text = read("tests/scenarios.md")
        self.assertEqual(len(re.findall(r"^## Case \d+:", text, re.MULTILINE)), 7)
        self.assertEqual(text.count("**Reject:**"), 7)
        self.assertIn("not passing results", text)
        self.assertIn("actual file", text)
        self.assertIn("remain separate", text)

    def test_catalog_describes_editorial_and_generation_paths(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("content planning and editorial review", text)
        self.assertIn("storyline, evidence, storyboard and editorial checks", text)
        self.assertFalse((SKILL / "test-fixture" / "consumer_prompt.md").exists())


if __name__ == "__main__":
    unittest.main()

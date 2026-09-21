"""Packaging and instruction contracts, not generated-interface acceptance."""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "web-experience-design"
RECORD = ROOT / "docs" / "maintenance" / "web-experience-design-validation.md"


def read(relative: str) -> str:
    return (SKILL / relative).read_text(encoding="utf-8")


class WebExperienceDesignContractTests(unittest.TestCase):
    def test_frontmatter_has_catalog_shape_and_bounded_description(self) -> None:
        text = read("SKILL.md")
        self.assertTrue(text.startswith("---\nname: web-experience-design\ndescription: >\n"))
        metadata = yaml.safe_load(text.split("---", 2)[1])
        self.assertEqual(set(metadata), {"name", "description", "metadata"})
        self.assertEqual(metadata["name"], SKILL.name)
        self.assertEqual(metadata["metadata"]["version"], "1.0.0")
        self.assertGreaterEqual(len(metadata["description"]), 200)
        self.assertLessEqual(len(metadata["description"]), 1024)
        self.assertIn("USE FOR:", metadata["description"])
        self.assertIn("DO NOT USE FOR:", metadata["description"])

    def test_entrypoint_is_bounded_and_routes_to_specialist_references(self) -> None:
        text = read("SKILL.md")
        # A package context budget, not a universal UX word-count rule.
        self.assertLessEqual(len(text.split()), 1800)
        for name in ("architecture", "contracts", "craft", "verification", "integrations", "evidence"):
            with self.subTest(reference=name):
                self.assertIn(f"(references/{name}.md)", text)
        self.assertIn("Load only the relevant", text)
        self.assertIn("Small refinement", text)
        self.assertIn("Audit or plan only", text)

    def test_local_markdown_links_and_anchors_resolve(self) -> None:
        for path in list(SKILL.rglob("*.md")) + [RECORD]:
            for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in link:
                    continue
                target, _, anchor = link.partition("#")
                destination = (path.parent / target).resolve() if target else path
                with self.subTest(file=path.relative_to(ROOT), link=link):
                    self.assertTrue(destination.is_file(), str(destination))
                    if path.is_relative_to(SKILL):
                        self.assertTrue(destination.is_relative_to(SKILL), str(destination))
                    if anchor:
                        headings = re.findall(
                            r"^#{1,6} (.+)$",
                            destination.read_text(encoding="utf-8"),
                            re.MULTILINE,
                        )
                        slugs = {
                            re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
                            for heading in headings
                        }
                        self.assertIn(anchor, slugs)

    def test_structure_precedes_visual_implementation_and_requires_approval(self) -> None:
        text = read("SKILL.md")
        self.assertLess(text.index("## 2. Decide the structure"), text.index("## 3. Give"))
        self.assertIn("Obtain explicit direction approval", text)
        self.assertIn("monochrome wireframe", text)
        self.assertIn("real content", text.lower())
        self.assertIn("Do not default to a long all-open page", text)
        self.assertIn("unless the user has already authorized", text)

    def test_architecture_covers_state_across_entry_points(self) -> None:
        text = read("references/architecture.md")
        for token in ("Dynamic addressable views", "Multiple pages", "Hybrid", "Linear reading"):
            self.assertIn(token, text)
        self.assertIn("origin -> destination -> state carried -> URL -> focus -> return", text)
        self.assertIn("footer CTAs", text)
        self.assertIn("reload and browser Back/Forward", text)
        self.assertIn("A header link and a footer CTA", read("SKILL.md"))

    def test_visual_fragment_parses_and_resolves_its_token_references(self) -> None:
        text = read("references/contracts.md")
        self.assertIn("illustrative fragment", text)
        fragment = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
        self.assertIsNotNone(fragment)
        data = yaml.safe_load(fragment.group(1))
        for component in data["components"].values():
            for value in component.values():
                if not isinstance(value, str) or not re.fullmatch(r"\{[\w.-]+\}", value):
                    continue
                resolved = data
                for part in value[1:-1].split("."):
                    resolved = resolved[part]
                self.assertIsInstance(resolved, str)
        self.assertIn("existing design tokens and components", text)

    def test_craft_includes_semantic_icons_visual_explanation_and_reduced_motion(self) -> None:
        text = read("references/craft.md")
        for heading in ("## Visual explanations", "## Icons", "## Motion", "## Typography and space"):
            self.assertIn(heading, text)
        self.assertIn("visible labels", text)
        self.assertIn("There is no icon quota", text)
        self.assertIn("reduced motion", text)
        self.assertIn("No universal ban", text)
        self.assertIn("must not imply", text)

    def test_verification_distinguishes_observation_from_certification(self) -> None:
        text = read("references/verification.md")
        self.assertIn("Automation timings are not human", text)
        self.assertIn("A narrow viewport check alone", text)
        self.assertIn("44 by 44 enhanced AAA", text)
        self.assertIn("virtualized rows", text)
        self.assertIn("file://", text)
        self.assertIn("Do not claim \"all verified\"", text)
        for state in ("observed", "source-inferred", "not checked", "blocked"):
            self.assertIn(state, read("references/contracts.md"))

    def test_optional_integrations_preserve_privacy_scope_and_loading_boundaries(self) -> None:
        text = read("references/integrations.md")
        self.assertIn("without an external generator", text)
        self.assertIn("No factories, global hooks", text)
        self.assertIn("exact non-sensitive payload", text)
        self.assertIn("Do not send confidential content", text)
        self.assertIn("limits and cost", text)
        self.assertIn("invocation successful", text)
        self.assertIn("resulting experience accepted", text)

    def test_three_scenarios_are_explicitly_unexecuted_and_task_based(self) -> None:
        text = read("tests/scenarios.md")
        self.assertIn("unexecuted, synthetic guardrail probes", text)
        cases = re.findall(r"^## Case \d+: (.+)$", text, re.MULTILINE)
        self.assertEqual(len(cases), 3)
        self.assertEqual(text.count("**Tasks:**"), 3)
        self.assertEqual(text.count("**Required evidence:**"), 3)
        for phrase in ("offline", "footer", "existing identity", "owner"):
            self.assertIn(phrase, text)
        self.assertIn("never replace, the user's real disappointing case", text)

    def test_no_cloud_fixture_or_upstream_runtime_is_claimed(self) -> None:
        self.assertFalse((SKILL / "test-fixture" / "consumer_prompt.md").exists())
        self.assertFalse((SKILL / "references" / "upstream-pin.md").exists())
        freshness = yaml.safe_load(read("references/last_validated.yaml"))
        self.assertIn("remain unexecuted", freshness["validation_notes"])
        self.assertIn("does not certify", freshness["validation_notes"])
        deps = yaml.safe_load((ROOT / ".github" / "skill-deps.yml").read_text())
        self.assertNotIn(SKILL.name, deps.get("skills", deps))

    def test_catalog_marks_candidate_and_publishes_its_validation_record(self) -> None:
        tree = ast.parse((ROOT / "scripts" / "build-site.py").read_text(encoding="utf-8"))
        declarations = {
            node.target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in {"CATEGORIES", "DRAFT_SKILLS"}
        }
        self.assertIn(SKILL.name, declarations["CATEGORIES"]["📊 Content Generation"])
        status = declarations["DRAFT_SKILLS"][SKILL.name]
        self.assertEqual(status["source_status"], "candidate")
        self.assertEqual(status["release_status"], "pending")
        self.assertEqual(status["record"], "maintenance/web-experience-design-validation.md")
        self.assertIn("not certify", status["summary"])
        self.assertTrue(RECORD.is_file())
        self.assertIn("not yet recorded", RECORD.read_text().lower())

    def test_catalog_versions_and_source_counts_remain_consistent(self) -> None:
        plugin = json.loads((ROOT / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".github" / "plugin" / "marketplace.json").read_text())
        self.assertEqual(plugin["version"], marketplace["metadata"]["version"])
        self.assertEqual(plugin["version"], marketplace["plugins"][0]["version"])
        count = len(list((ROOT / "skills").glob("*/SKILL.md")))
        self.assertIn(f"{count} reusable building blocks", plugin["description"])
        self.assertIn(SKILL.name, plugin["description"])
        self.assertIn(f"skills-{count}-blue", (ROOT / "README.md").read_text())
        self.assertIn("web-design", plugin["keywords"])


if __name__ == "__main__":
    unittest.main()

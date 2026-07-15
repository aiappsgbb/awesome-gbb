#!/usr/bin/env python3
"""Contract tests for the conservative GPT-5.6 GA catalog update.

RED evidence (base 442e08cb, 2026-07-15): the initial six-test run reported
30 missing-contract failures; a follow-up source-discrepancy check failed two
targeted tests. GREEN evidence: all six tests pass with the catalog update.
"""

from __future__ import annotations

import pathlib
import re
import unittest

import yaml


ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "foundry-hosted-agents"

MODEL_IDS = (
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
)


class Gpt56GaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        cls.selection = (SKILL_DIR / "references" / "model-selection.md").read_text(
            encoding="utf-8"
        )
        cls.skill_flat = " ".join(cls.skill.replace("\n> ", " ").split())
        cls.selection_flat = " ".join(cls.selection.replace("\n> ", " ").split())

    def test_skill_version_is_minor_bump(self) -> None:
        frontmatter = yaml.safe_load(self.skill.split("---")[1])
        self.assertEqual(frontmatter["metadata"]["version"], "2.1.0")
        self.assertLessEqual(len(frontmatter["description"]), 1024)

    def test_version_lookup_has_only_exact_gpt56_ids(self) -> None:
        lookup = self.skill.split("### Model Version Lookup", 1)[1].split(
            "\n---\n", 1
        )[0]
        rows = dict(
            re.findall(
                r"^\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|$",
                lookup,
                flags=re.MULTILINE,
            )
        )
        for model_id in MODEL_IDS:
            with self.subTest(model_id=model_id):
                self.assertEqual(rows.get(model_id), "2026-07-09")
        self.assertEqual(
            {model_id for model_id in rows if model_id.startswith("gpt-5.6")},
            set(MODEL_IDS),
        )
        self.assertNotIn("gpt-5.6", rows)
        self.assertNotIn("gpt-5.6-mini", rows)

    def test_shared_ga_lifecycle_and_capability_envelope_is_explicit(self) -> None:
        required = (
            "GPT-5.6 GA boundary",
            "GA",
            "2027-07-09",
            "1,050,000",
            "922,000 input",
            "128,000 output",
            "text and image input",
            "text output",
            "Responses API",
            "Chat Completions API",
            "`gpt-5.6` and `gpt-5.6-mini` are not documented Azure model IDs",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.skill_flat)

        for model_id in MODEL_IDS:
            with self.subTest(model_id=model_id):
                self.assertIn(f"`{model_id}`", self.skill)

    def test_first_party_sources_are_cited(self) -> None:
        required_urls = (
            "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/"
            "concepts/models-sold-directly-by-azure",
            "https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/"
            "model-retirement-schedule",
            "https://learn.microsoft.com/en-us/azure/foundry/foundry-models/"
            "concepts/models-sold-directly-by-azure-region-availability",
            "https://learn.microsoft.com/en-us/azure/foundry/openai/quotas-limits",
            "https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/"
            "limits-quotas-regions",
            "https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reasoning",
        )
        combined = f"{self.skill}\n{self.selection}"
        for url in required_urls:
            with self.subTest(url=url):
                self.assertIn(url, combined)

    def test_model_selection_preserves_defaults_and_distinguishes_skus(self) -> None:
        unchanged_defaults = (
            "| Deep multi-step reasoning / agentic planning | `gpt-5.4` |",
            "| Balanced general + tool/function calling | `gpt-5.4-mini` |",
            "| High-volume classify / extract / route | `gpt-5.4-nano` |",
        )
        for row in unchanged_defaults:
            with self.subTest(row=row):
                self.assertIn(row, self.selection)

        expected_rows = (
            "| `gpt-5.6-sol` | Yes | Yes | Yes | 1,000 | 333 | 15 / 5 |",
            "| `gpt-5.6-terra` | Yes | Yes | No | 1,000 | 333 | N/A |",
            "| `gpt-5.6-luna` | Yes | Yes | No | 1,000 | 333 | N/A |",
        )
        for row in expected_rows:
            with self.subTest(row=row):
                self.assertIn(row, self.selection)

        self.assertIn("distinct SKUs, not aliases", self.selection_flat)
        self.assertIn("no comparative ranking", self.selection_flat)
        self.assertIn("still showed `2026-06-25`", self.selection_flat)
        self.assertIn(
            "deployable catalog and live control plane reported `2026-07-09`",
            self.selection_flat,
        )

    def test_agent_service_and_pricing_gaps_are_not_overstated(self) -> None:
        required = (
            "currently stops at `gpt-5.5`",
            "does not establish GPT-5.6 Agent Service compatibility",
            "Do not change an agent default",
            "pricing tables do not yet publish GPT-5.6 rates",
        )
        for value in required:
            with self.subTest(value=value):
                self.assertIn(value, self.selection_flat)


if __name__ == "__main__":
    unittest.main()

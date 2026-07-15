#!/usr/bin/env python3
"""Contract tests for the foundry-evals live fixture."""

from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills" / "foundry-evals" / "test-fixture" / "consumer_prompt.md"


class FoundryEvalsFixtureContractTests(unittest.TestCase):
    def test_fixture_preserves_step_heading_order(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        headings = (
            "## Step 0 — Auth context (show, do not assert)",
            "## Step 0b — Trust Workflow Scaffold (no Azure required)",
            "## Step 1 — The goal",
            "## Step 2 — Marker contract (deterministic, MANDATORY)",
        )

        last_index = -1
        for heading in headings:
            with self.subTest(heading=heading):
                index = fixture.index(heading)
                self.assertGreater(index, last_index)
                last_index = index

        self.assertIn(
            "Using the `foundry-evals` skill, score one real assistant response",
            fixture[fixture.index(headings[2]) : fixture.index(headings[3])],
        )


if __name__ == "__main__":
    unittest.main()

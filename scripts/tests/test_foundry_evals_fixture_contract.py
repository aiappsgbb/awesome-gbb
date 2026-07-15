#!/usr/bin/env python3
"""Contract tests for the foundry-evals live fixture."""

from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills" / "foundry-evals" / "test-fixture" / "consumer_prompt.md"
SKILL_MD = ROOT / "skills" / "foundry-evals" / "SKILL.md"
WORKFLOW_MD = ROOT / "skills" / "foundry-evals" / "references" / "eval-trust-workflow.md"

# Matches write_trust_evidence calls whose second argument targets evals/runs/
_CLOBBER_RE = re.compile(
    r'write_trust_evidence\s*\([^,]+,\s*["\']evals/runs/[^"\']*["\']'
)


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


class TrustEvidenceOutputContractTests(unittest.TestCase):
    """Assert that docs never direct write_trust_evidence at evals/runs/ targets.

    The calibration record in evals/runs/ is a read-only input artifact.
    Normalized trust evidence must only be written to specs/evals-trust-evidence.json.
    """

    def _check_no_clobber(self, path: pathlib.Path) -> None:
        text = path.read_text(encoding="utf-8")
        match = _CLOBBER_RE.search(text)
        found = match.group(0) if match else ""
        self.assertIsNone(
            match,
            f"{path.relative_to(ROOT)}: write_trust_evidence must not target "
            f"evals/runs/ (found: {found!r}). "
            "The calibration record is a read-only input; normalized output must "
            "go to specs/evals-trust-evidence.json.",
        )

    def test_skill_md_no_evals_runs_write(self) -> None:
        self._check_no_clobber(SKILL_MD)

    def test_workflow_md_no_evals_runs_write(self) -> None:
        self._check_no_clobber(WORKFLOW_MD)

    def test_skill_md_canonical_output_present(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "specs/evals-trust-evidence.json",
            text,
            "SKILL.md must reference specs/evals-trust-evidence.json as the canonical output.",
        )

    def test_workflow_md_canonical_output_present(self) -> None:
        text = WORKFLOW_MD.read_text(encoding="utf-8")
        self.assertIn(
            "specs/evals-trust-evidence.json",
            text,
            "eval-trust-workflow.md must reference specs/evals-trust-evidence.json as canonical output.",
        )


if __name__ == "__main__":
    unittest.main()

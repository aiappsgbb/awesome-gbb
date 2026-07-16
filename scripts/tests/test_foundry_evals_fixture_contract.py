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

# Matches write_trust_evidence calls that target a -calibration.json path.
# Uses [^)]* so the pattern covers both plain strings and f-strings.
_CLOBBER_RE = re.compile(r'write_trust_evidence\s*\([^)]*-calibration\.json')


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

    def test_fixture_patch_version_is_bumped(self) -> None:
        frontmatter = SKILL_MD.read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn('version: "1.4.1"', frontmatter)


class TrustEvidenceOutputContractTests(unittest.TestCase):
    """Guard against write_trust_evidence clobbering the calibration input.

    The calibration record evals/runs/<timestamp>-calibration.json is a
    read-only input artifact.  Neither SKILL.md nor the final workflow
    emission snippet may call write_trust_evidence with a path that ends in
    -calibration.json.  Per-run intermediate evidence files with unique names
    (e.g. evals/runs/run-N-evidence.json written via f-string) are intentional
    and must not be prohibited.  The sole canonical output is
    specs/evals-trust-evidence.json.
    """

    def _assert_no_calibration_clobber(self, path: pathlib.Path) -> None:
        text = path.read_text(encoding="utf-8")
        match = _CLOBBER_RE.search(text)
        found = match.group(0) if match else ""
        self.assertIsNone(
            match,
            f"{path.relative_to(ROOT)}: write_trust_evidence must not target "
            f"the calibration input path (*-calibration.json) (found: {found!r}). "
            "The calibration record is a read-only input; the sole canonical "
            "output is specs/evals-trust-evidence.json.",
        )

    def test_skill_md_no_calibration_clobber(self) -> None:
        self._assert_no_calibration_clobber(SKILL_MD)

    def test_workflow_md_no_calibration_clobber(self) -> None:
        self._assert_no_calibration_clobber(WORKFLOW_MD)

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

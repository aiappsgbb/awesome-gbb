"""Unit tests for the foundry-agt canonical capability detector.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/248
Implements the threadlight AGT-V4-001..007 self-verify path.

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:
    python -m unittest discover -s scripts/tests -p 'test_*.py' -v
`unittest discover` cannot resolve pytest's `tmp_path` fixture.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Add the skill's reference dir to sys.path
SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from capability_detector import detect  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


class TestCapabilityDetector(unittest.TestCase):
    def test_empty_repo_returns_default_shape(self) -> None:
        """A repo with no AGT artifacts returns every flag False / list empty."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            result = detect(repo_root=str(tmp_path))

            self.assertIsNone(result["version_detected"])
            self.assertEqual(result["detection_confidence"], 0.0)
            self.assertEqual(result["package_pins"], {})
            self.assertFalse(result["intervention_points_present"])
            self.assertIsNone(result["policy_yaml_path"])
            self.assertFalse(result["deny_path_present"])
            self.assertEqual(result["audit_fields_in_verifier_json"], [])
            self.assertFalse(result["ci_action_pinned"])
            self.assertIsInstance(result["evidence_globs_scanned"], list)

    def test_full_v4_repo_returns_high_confidence(self) -> None:
        """A repo with pinned v4 + intervention points + policy YAML + pinned CI action returns full confidence."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            _write(tmp_path / "pyproject.toml", """
                [project]
                dependencies = ["foundry-agt==4.0.0"]
                """)
            _write(tmp_path / "src" / "agent.py", """
                from foundry_agt.intervention import V4_DIST_REGEX  # noqa
                from foundry_agt.intervention import V4_POLICY_REGEX  # noqa
                from foundry_agt.intervention import V4_DYNAMIC_REGEX  # noqa
                """)
            _write(tmp_path / "policies" / "agt.yaml", """
                version: 4
                deny:
                  - "*.exfiltration"
                intervention_points:
                  input:
                    - block_pii
                  output:
                    - redact_pii
                """)
            _write(tmp_path / "verifiers" / "audit.json", """
                {"audit_fields": ["actor", "tool", "outcome", "policy_version"]}
                """)
            _write(tmp_path / ".github" / "workflows" / "agt.yml", """
                jobs:
                  verify:
                    steps:
                      - uses: foundry-agt/verify@a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
                """)

            result = detect(repo_root=str(tmp_path))

            self.assertEqual(result["version_detected"], "4.0.0")
            self.assertEqual(result["detection_confidence"], 1.0)
            self.assertIn("foundry-agt", result["package_pins"])
            self.assertTrue(result["intervention_points_present"])
            self.assertIsNotNone(result["policy_yaml_path"])
            self.assertTrue(result["deny_path_present"])
            self.assertIn("actor", result["audit_fields_in_verifier_json"])
            self.assertTrue(result["ci_action_pinned"])

    def test_missing_policy_yaml_returns_none_path(self) -> None:
        """Pinned v4 package but no AGT policy YAML returns policy_yaml_path: None."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            _write(tmp_path / "pyproject.toml", """
                [project]
                dependencies = ["foundry-agt==4.0.0"]
                """)
            result = detect(repo_root=str(tmp_path))
            self.assertEqual(result["version_detected"], "4.0.0")
            self.assertIsNone(result["policy_yaml_path"])
            self.assertFalse(result["deny_path_present"])

    def test_ci_action_unpinned_returns_false(self) -> None:
        """GitHub Action referenced by tag (not SHA) flags as unpinned."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            _write(tmp_path / ".github" / "workflows" / "agt.yml", """
                jobs:
                  verify:
                    steps:
                      - uses: foundry-agt/verify@v4
                """)
            result = detect(repo_root=str(tmp_path))
            self.assertFalse(result["ci_action_pinned"])

    def test_returns_all_required_keys(self) -> None:
        """The contract requires every key always present, even on empty input."""
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp_path = Path(tmp_str)
            result = detect(repo_root=str(tmp_path))
            required_keys = {
                "version_detected", "detection_confidence", "package_pins",
                "intervention_points_present", "policy_yaml_path", "deny_path_present",
                "audit_fields_in_verifier_json", "ci_action_pinned",
                "evidence_globs_scanned",
            }
            self.assertTrue(required_keys.issubset(result.keys()))


if __name__ == "__main__":
    unittest.main()

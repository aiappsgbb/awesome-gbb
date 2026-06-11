"""Unit tests for the foundry-agt canonical capability detector.

Source contract: https://github.com/aiappsgbb/awesome-gbb/issues/248
Implements the threadlight AGT-V4-001..007 self-verify path.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Add the skill's reference dir to sys.path
SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-agt" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

from capability_detector import detect  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def test_empty_repo_returns_default_shape(tmp_path: Path) -> None:
    """A repo with no AGT artifacts returns every flag False / list empty."""
    result = detect(repo_root=str(tmp_path))

    assert result["version_detected"] is None
    assert result["detection_confidence"] == 0.0
    assert result["package_pins"] == {}
    assert result["intervention_points_present"] is False
    assert result["policy_yaml_path"] is None
    assert result["deny_path_present"] is False
    assert result["audit_fields_in_verifier_json"] == []
    assert result["ci_action_pinned"] is False
    assert isinstance(result["evidence_globs_scanned"], list)


def test_full_v4_repo_returns_high_confidence(tmp_path: Path) -> None:
    """A repo with pinned v4 + intervention points + policy YAML + pinned CI action returns full confidence."""
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

    assert result["version_detected"] == "4.0.0"
    assert result["detection_confidence"] == 1.0
    assert "foundry-agt" in result["package_pins"]
    assert result["intervention_points_present"] is True
    assert result["policy_yaml_path"] is not None
    assert result["deny_path_present"] is True
    assert "actor" in result["audit_fields_in_verifier_json"]
    assert result["ci_action_pinned"] is True


def test_missing_policy_yaml_returns_none_path(tmp_path: Path) -> None:
    """Pinned v4 package but no AGT policy YAML returns policy_yaml_path: None."""
    _write(tmp_path / "pyproject.toml", """
        [project]
        dependencies = ["foundry-agt==4.0.0"]
        """)
    result = detect(repo_root=str(tmp_path))
    assert result["version_detected"] == "4.0.0"
    assert result["policy_yaml_path"] is None
    assert result["deny_path_present"] is False


def test_ci_action_unpinned_returns_false(tmp_path: Path) -> None:
    """GitHub Action referenced by tag (not SHA) flags as unpinned."""
    _write(tmp_path / ".github" / "workflows" / "agt.yml", """
        jobs:
          verify:
            steps:
              - uses: foundry-agt/verify@v4
        """)
    result = detect(repo_root=str(tmp_path))
    assert result["ci_action_pinned"] is False


def test_returns_all_required_keys(tmp_path: Path) -> None:
    """The contract requires every key always present, even on empty input."""
    result = detect(repo_root=str(tmp_path))
    required_keys = {
        "version_detected", "detection_confidence", "package_pins",
        "intervention_points_present", "policy_yaml_path", "deny_path_present",
        "audit_fields_in_verifier_json", "ci_action_pinned",
        "evidence_globs_scanned",
    }
    assert required_keys.issubset(result.keys())

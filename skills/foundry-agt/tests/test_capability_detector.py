"""Unit tests for foundry_agt.capability_detector.

All filesystem fixtures are built inline via tmp_path. No on-disk
fixture directory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest
from capability_detector import detect


def _write(p: Path, body: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


def test_detect_v3_7_only(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["agt~=3.7.0"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] in {"3.7", "3.7.0", "3.x"}
    assert caps["intervention_points_present"] is False
    assert caps["policy_yaml_path"] is None


def test_detect_v4_1_with_policy_and_intervention(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["agt~=4.1.0"]\n')
    _write(tmp_path / "agt.policy.yaml",
           "deny:\n  - rule: pii_egress\n    deny_path: data.pii\n")
    _write(tmp_path / "src/agent.py",
           "from agt.intervention import enforce\nenforce(...)\n")
    _write(tmp_path / "verifier.json",
           '{"audit_fields": ["timestamp", "principal", "action"]}\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] in {"4.1", "4.1.0", "4.x"}
    assert caps["intervention_points_present"] is True
    assert caps["policy_yaml_path"] is not None
    assert caps["policy_yaml_path"].endswith("agt.policy.yaml")
    assert caps["deny_path_present"] is True
    assert caps["audit_fields_in_verifier_json"] is True


def test_detect_mixed_v3_and_v4(tmp_path):
    _write(tmp_path / "pyproject.toml",
           'dependencies = ["agt~=3.7.0", "agt-v4-dynamic~=0.1.0"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] == "mixed"


def test_detect_no_agt(tmp_path):
    _write(tmp_path / "pyproject.toml", 'dependencies = ["fastapi"]\n')
    caps = detect(repo_root=str(tmp_path))
    assert caps["version_detected"] is None
    assert caps["intervention_points_present"] is False
    assert caps["policy_yaml_path"] is None
    assert caps["deny_path_present"] is False
    assert caps["audit_fields_in_verifier_json"] is False
    assert caps["ci_action_pinned"] is False


def test_detect_ci_action_pinned(tmp_path):
    _write(tmp_path / ".github/workflows/agt.yml",
           "uses: microsoft/agt-action@v1.2.3\n")
    caps = detect(repo_root=str(tmp_path))
    assert caps["ci_action_pinned"] is True


def test_detect_evidence_globs_scanned(tmp_path):
    """The returned dict MUST include the list of globs that were inspected
    so the caller can report 'we looked at these places and found nothing'."""
    caps = detect(repo_root=str(tmp_path))
    assert "evidence_globs_scanned" in caps
    assert isinstance(caps["evidence_globs_scanned"], list)
    assert len(caps["evidence_globs_scanned"]) > 0

# scripts/tests/test_build_test_matrix.py
"""Unit tests for scripts/build-test-matrix.py.

The matrix builder emits a JSON list of skill names that have a
`test-fixture/consumer_prompt.md` and are NOT listed in
`.github/quarantine.yml`. The GHA `copilot-cli-matrix` job consumes
this list as its `matrix.skill` axis.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build-test-matrix.py"


def run(repo_root: Path) -> list[str]:
    out = subprocess.check_output(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root)],
        text=True,
    )
    payload = json.loads(out)
    assert isinstance(payload, dict) and "skill" in payload, payload
    return payload["skill"]


def test_includes_skill_with_fixture(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == ["alpha"]


def test_excludes_quarantined_skill(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / "skills" / "beta" / "test-fixture").mkdir(parents=True)
    (tmp_path / "skills" / "beta" / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text(
        "skills:\n  - name: beta\n    since: 2026-01-01\n    issue: x\n    reason: y\n"
    )

    assert run(tmp_path) == ["alpha"]


def test_skips_skill_without_fixture(tmp_path: Path) -> None:
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == []


def test_output_is_sorted(tmp_path: Path) -> None:
    for name in ("zeta", "alpha", "mu"):
        (tmp_path / "skills" / name / "test-fixture").mkdir(parents=True)
        (tmp_path / "skills" / name / "test-fixture" / "consumer_prompt.md").write_text("hi")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "quarantine.yml").write_text("skills: []\n")

    assert run(tmp_path) == ["alpha", "mu", "zeta"]

# scripts/tests/test_build_test_matrix.py
"""Unit tests for scripts/build-test-matrix.py.

The matrix builder emits a JSON list of skill names that have a
`test-fixture/consumer_prompt.md` and are NOT listed in
`.github/quarantine.yml`. The GHA `copilot-cli-matrix` job consumes
this list as its `matrix.skill` axis.

Written as `unittest.TestCase` (NOT pytest fixtures) because
`.github/workflows/skill-test.yml::unit-tests` invokes:

    python -m unittest discover -s scripts/tests -p 'test_*.py' -v

`unittest discover` cannot resolve pytest's `tmp_path` fixture and
silently emits 0 tests. Keep this file unittest-native so CI actually
runs the assertions.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build-test-matrix.py"


def _run(repo_root: Path) -> list[str]:
    out = subprocess.check_output(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root)],
        text=True,
    )
    payload = json.loads(out)
    assert isinstance(payload, dict) and "skill" in payload, payload
    return payload["skill"]


def _run_changed_only(repo_root: Path, base_ref: str) -> list[str]:
    out = subprocess.check_output(
        [
            sys.executable,
            str(SCRIPT),
            "--repo-root",
            str(repo_root),
            "--changed-only",
            "--base-ref",
            base_ref,
        ],
        text=True,
    )
    payload = json.loads(out)
    assert isinstance(payload, dict) and "skill" in payload, payload
    return payload["skill"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def _init_repo(repo: Path) -> None:
    """git init + identity + initial empty commit. Returns nothing; caller
    captures HEAD via `_git(repo, 'rev-parse', 'HEAD')`."""
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "init")


def _write_fixture(repo: Path, name: str) -> None:
    d = repo / "skills" / name / "test-fixture"
    d.mkdir(parents=True, exist_ok=True)
    (d / "consumer_prompt.md").write_text("hi\n")


def _write_quarantine(repo: Path, skills: list[str] | None = None) -> None:
    (repo / ".github").mkdir(exist_ok=True)
    if not skills:
        (repo / ".github" / "quarantine.yml").write_text("skills: []\n")
        return
    lines = ["skills:"]
    for s in skills:
        lines += [
            f"  - name: {s}",
            "    since: 2026-01-01",
            "    issue: x",
            "    reason: y",
        ]
    (repo / ".github" / "quarantine.yml").write_text("\n".join(lines) + "\n")


def _write_deps(repo: Path, mapping: dict[str, list[str]]) -> None:
    (repo / ".github").mkdir(exist_ok=True)
    lines = ["skills:"]
    for name, deps in mapping.items():
        lines.append(f"  {name}:")
        if deps:
            lines.append("    depends_on:")
            for d in deps:
                lines.append(f"      - {d}")
        else:
            lines.append("    depends_on: []")
    (repo / ".github" / "skill-deps.yml").write_text("\n".join(lines) + "\n")


class TestFullMatrix(unittest.TestCase):
    """Behaviour without `--changed-only`: emit every fixtured,
    non-quarantined skill in sorted order."""

    def test_includes_skill_with_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write_fixture(repo, "alpha")
            _write_quarantine(repo)
            self.assertEqual(_run(repo), ["alpha"])

    def test_excludes_quarantined_skill(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write_fixture(repo, "alpha")
            _write_fixture(repo, "beta")
            _write_quarantine(repo, ["beta"])
            self.assertEqual(_run(repo), ["alpha"])

    def test_skips_skill_without_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "skills" / "alpha").mkdir(parents=True)
            (repo / "skills" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
            _write_quarantine(repo)
            self.assertEqual(_run(repo), [])

    def test_output_is_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            for name in ("zeta", "alpha", "mu"):
                _write_fixture(repo, name)
            _write_quarantine(repo)
            self.assertEqual(_run(repo), ["alpha", "mu", "zeta"])


class TestChangedOnly(unittest.TestCase):
    """Behaviour with `--changed-only --base-ref <sha>`: emit only the
    skills affected by `git diff base_ref..HEAD`, expanded via the
    skill-deps map and force-full-matrix paths."""

    def _setup(self, td: str) -> tuple[Path, str]:
        """Init a repo with 3 fixtured skills + empty quarantine + a deps
        map (beta depends on alpha). Returns (repo_path, base_sha) where
        `base_sha` is HEAD AFTER the baseline commit. Any subsequent
        modifications committed after this call are what gets diffed."""
        repo = Path(td)
        for name in ("alpha", "beta", "gamma"):
            _write_fixture(repo, name)
        _write_quarantine(repo)
        _write_deps(repo, {"alpha": [], "beta": ["alpha"], "gamma": []})
        _init_repo(repo)
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "baseline")
        return repo, _git(repo, "rev-parse", "HEAD")

    def test_changed_only_returns_only_touched_skills(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            # Touch gamma only (gamma has no upstream and no dependants).
            (repo / "skills" / "gamma" / "SKILL.md").write_text("body\n")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit gamma")
            self.assertEqual(_run_changed_only(repo, base), ["gamma"])

    def test_changed_only_transitive_fanout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            # Touch alpha; beta declares depends_on:[alpha] so beta MUST
            # also re-validate. Forward fanout = single hop.
            (repo / "skills" / "alpha" / "SKILL.md").write_text("body\n")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit alpha")
            self.assertEqual(_run_changed_only(repo, base), ["alpha", "beta"])

    def test_changed_only_force_full_on_infra_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            # Touching the workflow file forces the full fixtured set
            # even though no skill/* path changed.
            workflow = repo / ".github" / "workflows" / "skill-test.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text("name: test\n")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit workflow")
            self.assertEqual(
                _run_changed_only(repo, base), ["alpha", "beta", "gamma"]
            )

    def test_changed_only_force_full_on_project_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            resolver = repo / "scripts" / "resolve-foundry-project.py"
            resolver.parent.mkdir(parents=True, exist_ok=True)
            resolver.write_text("print('project')\n")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit project resolver")
            self.assertEqual(
                _run_changed_only(repo, base), ["alpha", "beta", "gamma"]
            )

    def test_changed_only_plugin_json_is_metadata_no_fanout(self) -> None:
        # plugin.json and marketplace.json are metadata manifests — a
        # bare version bump (or new-skill registration) must NOT trigger
        # a full-matrix fan-out. The new skill's own skills/<name>/
        # paths in the diff drive natural detection.
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            (repo / "plugin.json").write_text('{"x": 1}\n')
            (repo / ".github" / "plugin").mkdir(parents=True, exist_ok=True)
            (repo / ".github" / "plugin" / "marketplace.json").write_text(
                '{"x": 1}\n'
            )
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "bump plugin metadata")
            # No skill folders changed → empty matrix.
            self.assertEqual(_run_changed_only(repo, base), [])

    def test_changed_only_matrix_builder_change_no_fanout(self) -> None:
        # The matrix builder itself is NOT in FORCE_FULL_MATRIX_PATHS:
        # the unit tests in this file + the push:main full-matrix canary
        # cover regression risk, so a pure logic edit must NOT spend
        # a full Azure fan-out per PR. Only paths that affect what runs
        # IN each leg (workflow, quarantine, shared preamble) force full.
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            scripts = repo / "scripts"
            scripts.mkdir(exist_ok=True)
            (scripts / "build-test-matrix.py").write_text(
                "# pretend edit\n", encoding="utf-8"
            )
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit matrix builder")
            # No skill folders changed → empty matrix.
            self.assertEqual(_run_changed_only(repo, base), [])

    def test_changed_only_skill_deps_yml_change_no_fanout(self) -> None:
        # skill-deps.yml is read live by _load_dep_map for forward fanout.
        # Adding a NEW entry (the common case when registering a new
        # skill) is purely additive — it doesn't change existing fanout
        # edges. So a pure skill-deps edit must NOT trigger full matrix.
        # Removals/renames are rare and caught by validate-skills.py +
        # the push:main canary.
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            (repo / ".github").mkdir(exist_ok=True)
            (repo / ".github" / "skill-deps.yml").write_text(
                "new-skill:\n  depends_on: []\n", encoding="utf-8"
            )
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "edit skill-deps")
            # No skill folders changed → empty matrix.
            self.assertEqual(_run_changed_only(repo, base), [])

    def test_changed_only_empty_diff_returns_empty_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo, base = self._setup(td)
            # Empty-commit -> diff base..HEAD is empty -> no skills.
            _git(repo, "commit", "--allow-empty", "-q", "-m", "empty")
            self.assertEqual(_run_changed_only(repo, base), [])

    def test_changed_only_without_base_ref_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _write_fixture(repo, "alpha")
            _write_quarantine(repo)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--repo-root", str(repo), "--changed-only"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("--base-ref", result.stderr)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for Git repository metadata that CI depends on."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _tracked_gitlinks() -> set[str]:
    result = _git("ls-files", "--stage")
    return {
        line.split("\t", 1)[1]
        for line in result.stdout.splitlines()
        if line.startswith("160000 ")
    }


def _declared_submodule_paths() -> set[str]:
    gitmodules = REPO_ROOT / ".gitmodules"
    if not gitmodules.exists():
        return set()

    result = _git(
        "config",
        "-f",
        str(gitmodules),
        "--get-regexp",
        r"^submodule\..*\.path$",
        check=False,
    )
    if result.returncode == 1:
        return set()
    result.check_returncode()
    return {
        line.split(maxsplit=1)[1]
        for line in result.stdout.splitlines()
    }


class RepositoryIntegrityTests(unittest.TestCase):
    def test_every_tracked_gitlink_has_a_declared_submodule(self) -> None:
        undeclared = _tracked_gitlinks() - _declared_submodule_paths()

        self.assertEqual(
            undeclared,
            set(),
            "mode-160000 gitlinks without matching .gitmodules entries break "
            f"recursive checkout: {sorted(undeclared)}",
        )

    def test_upstream_pin_smoke_clones_are_ignored(self) -> None:
        probe = ".upstream-pin-smoke/test-skill/repo"
        result = _git("check-ignore", "--quiet", "--no-index", probe, check=False)

        self.assertEqual(
            result.returncode,
            0,
            ".upstream-pin-smoke/ must be ignored so validation clones cannot be staged",
        )


if __name__ == "__main__":
    unittest.main()

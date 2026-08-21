"""Contract tests for fixture checkout-integrity enforcement."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "skill-test.yml"


class SkillTestFixtureMutationGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.steps = workflow["jobs"]["copilot-cli-matrix"]["steps"]
        cls.primary = next(step for step in cls.steps if step.get("id") == "run")
        cls.retry = next(
            step
            for step in cls.steps
            if step.get("name") == "Retry once on classified-transient failure"
        )

    @staticmethod
    def extract_guard(script: str) -> str:
        match = re.search(
            r"# BEGIN tracked-checkout guard\n(.*?)"
            r"\n# END tracked-checkout guard",
            script,
            flags=re.DOTALL,
        )
        if match is None:
            raise AssertionError("tracked-checkout guard block is missing")
        return match.group(1)

    def run_guard(self, repo: Path) -> subprocess.CompletedProcess[str]:
        guard = self.extract_guard(self.primary["run"])
        env = os.environ.copy()
        env["GITHUB_SHA"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        env["GITHUB_WORKSPACE"] = str(repo)
        return subprocess.run(
            ["bash", "-c", f'{guard}\nassert_tracked_checkout_clean "during test"'],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    @staticmethod
    def git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )

    def create_repo(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        repo = root / "repo"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        self.git(repo, "config", "user.name", "Fixture Guard Test")
        self.git(repo, "config", "user.email", "fixture-guard@example.invalid")
        (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
        self.git(repo, "add", "tracked.txt")
        self.git(repo, "commit", "--quiet", "-m", "initial")
        return repo

    def add_submodule(self, parent: Path, child: Path) -> None:
        self.git(
            parent,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "--quiet",
            str(child),
            "dependency",
        )
        self.git(parent, "commit", "--quiet", "-am", "add submodule")

    def test_primary_and_retry_reject_tracked_checkout_mutations(self) -> None:
        guards = []
        for step in (self.primary, self.retry):
            with self.subTest(step=step["name"]):
                script = step["run"]
                self.assertIn(
                    "GIT_NO_REPLACE_OBJECTS=1",
                    script,
                )
                self.assertIn(
                    'git -C "$repo" read-tree "$expected_commit"',
                    script,
                )
                self.assertIn(
                    'trusted_git -C "$repo" write-tree',
                    script,
                )
                self.assertIn(
                    'git -C "$repo" diff-files --quiet',
                    script,
                )
                self.assertIn(
                    "--ignore-submodules=untracked --",
                    script,
                )
                self.assertIn(
                    'trusted_git -C "$repo" '
                    'hash-object --no-filters -- "$path"',
                    script,
                )
                self.assertIn(
                    'trusted_git -C "$repo" ls-tree -rz -r "$expected_commit"',
                    script,
                )
                self.assertIn(
                    "status --short --untracked-files=no",
                    script,
                )
                self.assertIn(
                    'assert_tracked_checkout_clean "before Copilot"',
                    script,
                )
                self.assertIn(
                    'assert_tracked_checkout_clean "after Copilot"',
                    script,
                )

                before = script.index(
                    'assert_tracked_checkout_clean "before Copilot"'
                )
                invocation = script.index("copilot -p")
                after = script.index(
                    'assert_tracked_checkout_clean "after Copilot"'
                )
                marker_eval = script.index('if [ -f "$MARKER" ]')
                self.assertLess(before, invocation)
                self.assertLess(invocation, after)
                self.assertLess(after, marker_eval)
                guards.append(self.extract_guard(script))

        self.assertEqual(guards[0], guards[1])
        retry_script = self.retry["run"]
        self.assertLess(
            retry_script.index('sleep "${COOLDOWN}"'),
            retry_script.index('assert_tracked_checkout_clean "before Copilot"'),
        )

    def test_guard_rejects_staged_and_unstaged_tracked_changes(self) -> None:
        for staged in (False, True):
            with self.subTest(staged=staged), tempfile.TemporaryDirectory() as tmp:
                repo = self.create_repo(Path(tmp))
                (repo / "tracked.txt").write_text("modified\n", encoding="utf-8")
                if staged:
                    self.git(repo, "add", "tracked.txt")

                result = self.run_guard(repo)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tracked-file mutations", result.stdout)
                self.assertNotIn("modified", result.stdout)

    def test_guard_rejects_committed_tracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.create_repo(Path(tmp))
            original_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (repo / "tracked.txt").write_text("committed mutation\n", encoding="utf-8")
            self.git(repo, "commit", "--quiet", "-am", "mutate tracked file")
            guard = self.extract_guard(self.primary["run"])
            env = os.environ.copy()
            env["GITHUB_SHA"] = original_head
            env["GITHUB_WORKSPACE"] = str(repo)

            result = subprocess.run(
                ["bash", "-c", f'{guard}\nassert_tracked_checkout_clean "during test"'],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_rejects_replacement_ref_baseline_redefinition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.create_repo(Path(tmp))
            original_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            (repo / "tracked.txt").write_text("replacement tree\n", encoding="utf-8")
            self.git(repo, "commit", "--quiet", "-am", "replacement commit")
            replacement_head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.git(repo, "reset", "--quiet", "--hard", original_head)
            (repo / "tracked.txt").write_text("replacement tree\n", encoding="utf-8")
            self.git(repo, "replace", original_head, replacement_head)

            result = self.run_guard(repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_rejects_hidden_tracked_changes(self) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                repo = self.create_repo(Path(tmp))
                self.git(repo, "update-index", flag, "tracked.txt")
                (repo / "tracked.txt").write_text("hidden mutation\n", encoding="utf-8")

                result = self.run_guard(repo)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_rejects_clean_filter_poisoning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.create_repo(Path(tmp))
            info = repo / ".git" / "info"
            info.mkdir(parents=True, exist_ok=True)
            (info / "attributes").write_text(
                "tracked.txt filter=hide-mutation\n",
                encoding="utf-8",
            )
            self.git(
                repo,
                "config",
                "filter.hide-mutation.clean",
                "printf 'original\\n'",
            )
            (repo / "tracked.txt").write_text("filtered mutation\n", encoding="utf-8")

            result = self.run_guard(repo)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_ignores_untracked_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = self.create_repo(Path(tmp))
            (repo / "artifact.txt").write_text("runtime artifact\n", encoding="utf-8")

            result = self.run_guard(repo)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guard_rejects_tracked_changes_inside_submodule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = self.create_repo(root / "child-root")
            parent = self.create_repo(root / "parent-root")
            self.add_submodule(parent, child)
            (parent / "dependency" / "tracked.txt").write_text(
                "modified in submodule\n",
                encoding="utf-8",
            )

            result = self.run_guard(parent)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_rejects_hidden_tracked_changes_inside_submodule(self) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                child = self.create_repo(root / "child-root")
                parent = self.create_repo(root / "parent-root")
                self.add_submodule(parent, child)
                dependency = parent / "dependency"
                self.git(dependency, "update-index", flag, "tracked.txt")
                (dependency / "tracked.txt").write_text(
                    "hidden mutation in submodule\n",
                    encoding="utf-8",
                )

                result = self.run_guard(parent)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tracked-file mutations", result.stdout)

    def test_guard_ignores_untracked_artifacts_inside_submodule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = self.create_repo(root / "child-root")
            parent = self.create_repo(root / "parent-root")
            self.add_submodule(parent, child)
            (parent / "dependency" / "artifact.txt").write_text(
                "runtime artifact\n",
                encoding="utf-8",
            )

            result = self.run_guard(parent)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_guard_accepts_clean_uninitialized_submodule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = self.create_repo(root / "child-root")
            parent = self.create_repo(root / "parent-root")
            self.add_submodule(parent, child)
            self.git(parent, "submodule", "deinit", "--quiet", "-f", "dependency")

            result = self.run_guard(parent)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

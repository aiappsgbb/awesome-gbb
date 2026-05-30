#!/usr/bin/env python3
"""
test_automation_pr_gate.py — unit tests for the AGENTS.md § 4 enforcer.

Tests the gate logic in isolation (no git required). Each test
constructs a synthetic file list + commit messages + repo state and
verifies the gate accepts or rejects as expected.

Run:
    python scripts/tests/test_automation_pr_gate.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


HERE = pathlib.Path(__file__).resolve().parent
GATE_PATH = HERE.parent / "automation-pr-gate.py"

spec = importlib.util.spec_from_file_location("gate", GATE_PATH)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
assert spec.loader is not None
spec.loader.exec_module(gate)


def make_skill_md(version: str = "1.0.0", description: str = "Short desc") -> str:
    return (
        f"---\n"
        f"name: my-skill\n"
        f"description: >\n"
        f"  {description}\n"
        f"metadata:\n"
        f'  version: "{version}"\n'
        f"---\n\n"
        f"# My skill\n\n"
        f"Body content.\n"
    )


class GateGatesTests(unittest.TestCase):
    def test_collect_opt_ins(self):
        msgs = [
            "chore(skill-a): bump\n\n[multi-skill]",
            "fix(skill-b): typo",
        ]
        opts = gate.collect_opt_ins(msgs)
        self.assertIn("[multi-skill]", opts)
        self.assertNotIn("[scrub-canon]", opts)

    def test_one_skill_per_pr_ok(self):
        files = ["skills/foundry-agt/SKILL.md", "skills/foundry-agt/references/upstream-pin.md"]
        errs = gate.gate_one_skill_per_pr(files, set())
        self.assertEqual(errs, [])

    def test_one_skill_per_pr_fail(self):
        files = ["skills/foundry-agt/SKILL.md", "skills/citadel-hub-deploy/SKILL.md"]
        errs = gate.gate_one_skill_per_pr(files, set())
        self.assertEqual(len(errs), 1)
        self.assertIn("Multi-skill PR", errs[0])

    def test_one_skill_per_pr_opt_in(self):
        files = ["skills/foundry-agt/SKILL.md", "skills/citadel-hub-deploy/SKILL.md"]
        errs = gate.gate_one_skill_per_pr(files, {"[multi-skill]"})
        self.assertEqual(errs, [])

    def test_no_canon_edits_blocks(self):
        files = ["skills/threadlight-design/references/data-realism/fsi.md"]
        errs = gate.gate_no_canon_edits(files, set())
        self.assertEqual(len(errs), 1)
        self.assertIn("canon", errs[0].lower())

    def test_no_canon_edits_opt_in(self):
        files = ["skills/threadlight-design/references/data-realism/fsi.md"]
        errs = gate.gate_no_canon_edits(files, {"[scrub-canon]"})
        self.assertEqual(errs, [])

    def test_no_canon_edits_allows_non_canon_references(self):
        files = ["skills/threadlight-design/references/something-else.md"]
        errs = gate.gate_no_canon_edits(files, set())
        self.assertEqual(errs, [])


class FrontmatterTests(unittest.TestCase):
    def test_description_length(self):
        text = make_skill_md(description="abc")
        n = gate.description_length(text)
        # YAML folded scalar includes a trailing newline; both 3 (just abc)
        # and 4 (abc\n) are acceptable here — assert it's small.
        self.assertIsNotNone(n)
        self.assertLessEqual(n, 10)

    def test_description_too_long(self):
        long = "x" * 1100
        text = make_skill_md(description=long)
        n = gate.description_length(text)
        self.assertIsNotNone(n)
        self.assertGreater(n, 1024)

    def test_version_tuple_valid(self):
        text = make_skill_md(version="1.2.3")
        self.assertEqual(gate.version_tuple(text), (1, 2, 3))

    def test_version_tuple_invalid(self):
        text = make_skill_md(version="not-a-version")
        self.assertIsNone(gate.version_tuple(text))

    def test_split_frontmatter_missing(self):
        self.assertIsNone(gate.split_frontmatter("no frontmatter here"))

    def test_split_frontmatter_ok(self):
        text = make_skill_md()
        split = gate.split_frontmatter(text)
        self.assertIsNotNone(split)
        pre, fm, post = split  # type: ignore[misc]
        self.assertEqual(pre, "")
        self.assertIn("name: my-skill", fm)
        self.assertIn("# My skill", post)


class IntegrationTests(unittest.TestCase):
    """Patch git access to simulate before/after states."""

    def _mock_file_at_revision(self, mapping: dict[str, str]):
        def fake(rev, path):
            return mapping.get(path)
        return fake

    def test_metadata_only_patch_bump_passes(self):
        old = make_skill_md(version="1.0.0")
        new = make_skill_md(version="1.0.1")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(new, encoding="utf-8")
            pin = tmp_path / "skills" / "x" / "references" / "upstream-pin.md"
            pin.parent.mkdir(parents=True)
            pin.write_text("---\n---\n", encoding="utf-8")

            with mock.patch.object(gate, "REPO_ROOT", tmp_path), \
                 mock.patch.object(gate, "file_at_revision",
                                   side_effect=self._mock_file_at_revision({
                                       "skills/x/SKILL.md": old,
                                       "skills/x/references/upstream-pin.md": "",
                                   })):
                errs = gate.gate_patch_only_for_metadata_diff(
                    files=["skills/x/SKILL.md", "skills/x/references/upstream-pin.md"],
                    opts=set(),
                    base="origin/main",
                )
            self.assertEqual(errs, [], msg=f"Unexpected errors: {errs}")

    def test_metadata_only_minor_bump_fails(self):
        old = make_skill_md(version="1.0.0")
        new = make_skill_md(version="1.1.0")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(new, encoding="utf-8")
            pin = tmp_path / "skills" / "x" / "references" / "upstream-pin.md"
            pin.parent.mkdir(parents=True)
            pin.write_text("---\n---\n", encoding="utf-8")

            with mock.patch.object(gate, "REPO_ROOT", tmp_path), \
                 mock.patch.object(gate, "file_at_revision",
                                   side_effect=self._mock_file_at_revision({
                                       "skills/x/SKILL.md": old,
                                       "skills/x/references/upstream-pin.md": "",
                                   })):
                errs = gate.gate_patch_only_for_metadata_diff(
                    files=["skills/x/SKILL.md", "skills/x/references/upstream-pin.md"],
                    opts=set(),
                    base="origin/main",
                )
            self.assertEqual(len(errs), 1)
            self.assertIn("MAJOR/MINOR", errs[0])

    def test_skill_md_body_change_blocked(self):
        old = make_skill_md()
        new_with_body_edit = old.replace("Body content.", "Body content CHANGED.")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(new_with_body_edit, encoding="utf-8")

            with mock.patch.object(gate, "REPO_ROOT", tmp_path), \
                 mock.patch.object(gate, "file_at_revision",
                                   side_effect=self._mock_file_at_revision({
                                       "skills/x/SKILL.md": old,
                                   })):
                errs = gate.gate_skill_md_body(
                    files=["skills/x/SKILL.md"],
                    opts=set(),
                    base="origin/main",
                )
            self.assertEqual(len(errs), 1)
            self.assertIn("body changed", errs[0])

    def test_skill_md_body_change_with_opt_in_passes(self):
        old = make_skill_md()
        new_with_body_edit = old.replace("Body content.", "Body content CHANGED.")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(new_with_body_edit, encoding="utf-8")

            with mock.patch.object(gate, "REPO_ROOT", tmp_path), \
                 mock.patch.object(gate, "file_at_revision",
                                   side_effect=self._mock_file_at_revision({
                                       "skills/x/SKILL.md": old,
                                   })):
                errs = gate.gate_skill_md_body(
                    files=["skills/x/SKILL.md"],
                    opts={"[skill-rewrite]"},
                    base="origin/main",
                )
            self.assertEqual(errs, [])

    def test_description_length_regression_blocked(self):
        long = "x" * 1100
        text = make_skill_md(description=long)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(text, encoding="utf-8")
            with mock.patch.object(gate, "REPO_ROOT", tmp_path):
                errs = gate.gate_description_length(
                    files=["skills/x/SKILL.md"],
                    base="origin/main",
                )
            self.assertEqual(len(errs), 1)
            self.assertIn("chars", errs[0])


class AuditTagTests(unittest.TestCase):
    """Spec 2026-05-30 §9.2: [audit-2026-Q2] tag enables multi-skill +
    body-rewrite edits in exchange for a docs/audit/<name>-audit-trail.md
    per touched skill."""

    def test_collect_opt_ins_recognizes_audit_tag(self):
        msgs = ["audit(foo): fix MID-I credential\n\n[audit-2026-Q2]"]
        opts = gate.collect_opt_ins(msgs)
        self.assertIn("[audit-2026-Q2]", opts)

    def test_audit_tag_requires_audit_trail_file(self):
        files = [
            "skills/foo/SKILL.md",
            "skills/foo/test-fixture/consumer_prompt.md",
        ]
        errs = gate.gate_audit_tag_requires_audit_trail(
            files, {"[audit-2026-Q2]"}
        )
        self.assertEqual(len(errs), 1)
        self.assertIn("audit-trail", errs[0].lower())
        self.assertIn("foo", errs[0])

    def test_audit_tag_passes_when_audit_trail_present(self):
        files = [
            "skills/foo/SKILL.md",
            "skills/foo/test-fixture/consumer_prompt.md",
            "docs/audit/foo-audit-trail.md",
        ]
        errs = gate.gate_audit_tag_requires_audit_trail(
            files, {"[audit-2026-Q2]"}
        )
        self.assertEqual(errs, [])

    def test_audit_tag_passes_multi_skill_with_all_trails(self):
        files = [
            "skills/foo/SKILL.md",
            "docs/audit/foo-audit-trail.md",
            "skills/bar/SKILL.md",
            "docs/audit/bar-audit-trail.md",
        ]
        errs = gate.gate_audit_tag_requires_audit_trail(
            files, {"[audit-2026-Q2]"}
        )
        self.assertEqual(errs, [])

    def test_audit_tag_no_op_when_tag_absent(self):
        files = ["skills/foo/SKILL.md"]
        errs = gate.gate_audit_tag_requires_audit_trail(files, set())
        self.assertEqual(errs, [])

    def test_audit_tag_bypasses_one_skill_per_pr(self):
        files = [
            "skills/foo/SKILL.md",
            "skills/bar/SKILL.md",
        ]
        errs = gate.gate_one_skill_per_pr(files, {"[audit-2026-Q2]"})
        self.assertEqual(errs, [])

    def test_skill_md_body_change_with_audit_tag_passes(self):
        old = make_skill_md()
        new_with_body_edit = old.replace("Body content.", "Body content CHANGED.")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            skill_md = tmp_path / "skills" / "x" / "SKILL.md"
            skill_md.parent.mkdir(parents=True)
            skill_md.write_text(new_with_body_edit, encoding="utf-8")

            with mock.patch.object(gate, "REPO_ROOT", tmp_path), \
                mock.patch.object(gate, "file_at_revision",
                                  side_effect=lambda rev, path: old):
               errs = gate.gate_skill_md_body(
                   files=["skills/x/SKILL.md"],
                   opts={"[audit-2026-Q2]"},
                   base="origin/main",
               )
            self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

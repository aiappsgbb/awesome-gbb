#!/usr/bin/env python3
"""
test_validate_skills.py — unit tests for validate-skills.py (AGENTS.md § 8).

Tests the validation logic in isolation using synthetic SKILL.md, pin,
and plugin.json data. No git or real files required.

Run:
    python -m pytest scripts/tests/test_validate_skills.py -v
    python scripts/tests/test_validate_skills.py
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
VS_PATH = HERE.parent / "validate-skills.py"

spec = importlib.util.spec_from_file_location("vs", VS_PATH)
vs = importlib.util.module_from_spec(spec)
sys.modules["vs"] = vs
assert spec.loader is not None
spec.loader.exec_module(vs)


# ── helpers ──────────────────────────────────────────────────────────

def _skill_md(
    name: str = "test-skill",
    description: str = "Short desc for testing",
    version: str = "1.0.0",
    body: str = "# Test skill\n\nBody content.\n",
) -> str:
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: >\n"
        f"  {description}\n"
        f"metadata:\n"
        f'  version: "{version}"\n'
        f"---\n\n"
        f"{body}"
    )


def _pin_md(
    schema_version: int = 2,
    freshness_tier: str = "A",
    automation_tier: str = "auto",
    requires: list[str] | None = None,
    runnable: bool = True,
    last_validated: str = "2026-05-26",
) -> str:
    req = requires or ["github_only"]
    req_str = ", ".join(req)
    return (
        f"---\n"
        f"schema_version: {schema_version}\n"
        f"freshness_tier: {freshness_tier}\n"
        f"automation_tier: {automation_tier}\n"
        f"validation:\n"
        f"  requires: [{req_str}]\n"
        f"  runnable: {str(runnable).lower()}\n"
        f"  script: echo ok\n"
        f"  expected_output:\n"
        f"    - ok\n"
        f"last_validated: {last_validated}\n"
        f"---\n\n"
        f"# Audit trail\n"
    )


def _plugin_json(
    name: str = "awesome-gbb",
    version: str = "4.2.0",
    description: str = "GBB skill catalog",
    skills: str = "skills/",
) -> str:
    return json.dumps({
        "name": name,
        "version": version,
        "description": description,
        "skills": skills,
    })


def _marketplace_json(
    name: str = "awesome-gbb",
    plugin_name: str = "awesome-gbb",
    plugin_version: str = "4.2.0",
) -> str:
    return json.dumps({
        "name": name,
        "owner": {"name": "GBB", "url": "https://github.com/aiappsgbb"},
        "plugins": [{
            "name": plugin_name,
            "version": plugin_version,
            "description": "GBB skill catalog",
            "source": ".",
        }],
    })


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── SKILL.md validation ─────────────────────────────────────────────

class TestValidateSkillMd(unittest.TestCase):
    def test_valid_skill_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md())
            errs = vs.validate_skill_md(p)
            self.assertEqual(errs, [])

    def test_missing_name_fails(self):
        md = "---\ndescription: >\n  test\nmetadata:\n  version: '1.0.0'\n---\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, md)
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("missing `name`" in e for e in errs))

    def test_name_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "wrong-dir" / "SKILL.md"
            _write(p, _skill_md(name="test-skill"))
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("does not match directory" in e for e in errs))

    def test_missing_description_fails(self):
        md = "---\nname: test-skill\nmetadata:\n  version: '1.0.0'\n---\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, md)
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("missing `description`" in e for e in errs))

    def test_description_too_long_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(description="x" * 1100))
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("1024" in e for e in errs))

    def test_description_at_limit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(description="x" * 1020))
            errs = vs.validate_skill_md(p)
            self.assertEqual(errs, [])

    def test_missing_version_fails(self):
        md = "---\nname: test-skill\ndescription: >\n  test\nmetadata: {}\n---\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, md)
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("missing `metadata.version`" in e for e in errs))

    def test_invalid_semver_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(version="not.a.version"))
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("SemVer" in e for e in errs))

    def test_forbidden_string_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(body="See kyc-poc for details.\n"))
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("forbidden string" in e for e in errs))

    def test_deprecated_api_in_code_block_detected(self):
        body = (
            "# Skill\n\n"
            "```python\n"
            "client.get_toolbox()\n"
            "```\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(body=body))
            errs = vs.validate_skill_md(p)
            self.assertTrue(any("deprecated API" in e for e in errs))

    def test_deprecated_api_in_old_block_ignored(self):
        body = (
            "# Skill\n\n"
            "```python\n"
            "# OLD — do not use\n"
            "client.get_toolbox()\n"
            "```\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, _skill_md(body=body))
            errs = vs.validate_skill_md(p)
            self.assertFalse(any("deprecated API" in e for e in errs))

    def test_no_frontmatter_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "skills" / "test-skill" / "SKILL.md"
            _write(p, "# No frontmatter\nBody.\n")
            errs = vs.validate_skill_md(p)
            self.assertTrue(len(errs) >= 1)


# ── Pin file validation ──────────────────────────────────────────────

class TestValidatePinFile(unittest.TestCase):
    def test_valid_pin_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md())
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])

    def test_wrong_schema_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(schema_version=1))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("schema_version" in e for e in errs))

    def test_invalid_freshness_tier_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(freshness_tier="X"))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("freshness_tier" in e for e in errs))

    def test_auto_tier_with_azure_requires_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(
                automation_tier="auto",
                requires=["azure_subscription"],
                runnable=True,
            ))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("automation_tier=auto" in e for e in errs))

    def test_runnable_with_azure_requires_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(
                automation_tier="issue_only",
                requires=["azure_subscription"],
                runnable=True,
            ))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("runnable=true" in e.lower() or "runnable" in e for e in errs))

    def test_issue_only_with_azure_not_runnable_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(
                automation_tier="issue_only",
                requires=["azure_subscription"],
                runnable=False,
            ))
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])

    def test_missing_last_validated_fails(self):
        pin = (
            "---\n"
            "schema_version: 2\n"
            "freshness_tier: A\n"
            "automation_tier: auto\n"
            "validation:\n"
            "  requires: [github_only]\n"
            "  runnable: true\n"
            "  script: echo ok\n"
            "---\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, pin)
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("last_validated" in e for e in errs))


# ── Plugin & marketplace validation ──────────────────────────────────

class TestValidatePluginJson(unittest.TestCase):
    def test_valid_plugin_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            pj = tmp_path / "plugin.json"
            _write(pj, _plugin_json())
            skills_dir = tmp_path / "skills" / "test-skill"
            _write(skills_dir / "SKILL.md", _skill_md())
            import unittest.mock as _mock
            with _mock.patch.object(vs, "SKILLS_DIR", tmp_path / "skills"), \
                 _mock.patch.object(vs, "PLUGIN_JSON", pj):
                errs = vs.validate_plugin_json(pj)
            self.assertEqual(errs, [])

    def test_missing_name_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pj = pathlib.Path(tmp) / "plugin.json"
            _write(pj, json.dumps({"version": "1.0.0", "description": "x", "skills": "skills/"}))
            errs = vs.validate_plugin_json(pj)
            self.assertTrue(any("missing `name`" in e for e in errs))

    def test_missing_version_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pj = pathlib.Path(tmp) / "plugin.json"
            _write(pj, json.dumps({"name": "test", "description": "x", "skills": "skills/"}))
            errs = vs.validate_plugin_json(pj)
            self.assertTrue(any("missing `version`" in e for e in errs))

    def test_invalid_semver_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            pj = pathlib.Path(tmp) / "plugin.json"
            _write(pj, json.dumps({"name": "test", "version": "bad", "description": "x"}))
            errs = vs.validate_plugin_json(pj)
            self.assertTrue(any("SemVer" in e for e in errs))


# ── Frontmatter parser ───────────────────────────────────────────────

class TestParseFrontmatter(unittest.TestCase):
    def test_valid_frontmatter(self):
        text = "---\nname: x\n---\n"
        fm = vs.parse_frontmatter_text(text, "test")
        self.assertEqual(fm["name"], "x")

    def test_no_frontmatter_raises(self):
        with self.assertRaises(vs.ValidationError):
            vs.parse_frontmatter_text("no frontmatter", "test")

    def test_bad_yaml_raises(self):
        with self.assertRaises(vs.ValidationError):
            vs.parse_frontmatter_text("---\n  bad:\nyaml: [unclosed\n---\n", "test")


# ── run-pin-validation should_run ────────────────────────────────────

class TestShouldRun(unittest.TestCase):
    """Test the should_run() filter in run-pin-validation.py."""

    @classmethod
    def setUpClass(cls):
        rpv_path = HERE.parent / "run-pin-validation.py"
        rpv_spec = importlib.util.spec_from_file_location("rpv", rpv_path)
        cls.rpv = importlib.util.module_from_spec(rpv_spec)
        assert rpv_spec.loader is not None
        rpv_spec.loader.exec_module(cls.rpv)

    def _pin(self, **overrides) -> dict:
        base = {
            "automation_tier": "auto",
            "validation": {
                "requires": ["github_only"],
                "runnable": True,
                "script": "echo ok",
            },
        }
        for k, v in overrides.items():
            if k in ("requires", "runnable", "script"):
                base["validation"][k] = v
            else:
                base[k] = v
        return base

    def test_standard_auto_pin_runs(self):
        ok, _ = self.rpv.should_run(self._pin(), pathlib.Path("x"))
        self.assertTrue(ok)

    def test_no_script_skips(self):
        ok, reason = self.rpv.should_run(self._pin(script=""), pathlib.Path("x"))
        self.assertFalse(ok)
        self.assertIn("no validation.script", reason)

    def test_not_runnable_skips(self):
        ok, reason = self.rpv.should_run(self._pin(runnable=False), pathlib.Path("x"))
        self.assertFalse(ok)
        self.assertIn("runnable", reason)

    def test_issue_only_skips(self):
        ok, reason = self.rpv.should_run(
            self._pin(automation_tier="issue_only"), pathlib.Path("x"))
        self.assertFalse(ok)
        self.assertIn("issue_only", reason)

    def test_azure_requires_skips_without_flag(self):
        ok, reason = self.rpv.should_run(
            self._pin(requires=["azure_subscription"], runnable=False,
                      automation_tier="issue_only"),
            pathlib.Path("x"),
        )
        self.assertFalse(ok)

    def test_azure_requires_runs_with_flag_and_env(self):
        import os
        old = os.environ.get("AZURE_SUBSCRIPTION_ID")
        os.environ["AZURE_SUBSCRIPTION_ID"] = "test-sub"
        try:
            ok, _ = self.rpv.should_run(
                self._pin(requires=["azure_subscription"], runnable=False,
                          automation_tier="issue_only"),
                pathlib.Path("x"),
                include_azure=True,
            )
            self.assertTrue(ok)
        finally:
            if old is None:
                os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
            else:
                os.environ["AZURE_SUBSCRIPTION_ID"] = old

    def test_azure_requires_skips_without_env(self):
        import os
        old = os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
        try:
            ok, reason = self.rpv.should_run(
                self._pin(requires=["azure_subscription"], runnable=False,
                          automation_tier="issue_only"),
                pathlib.Path("x"),
                include_azure=True,
            )
            self.assertFalse(ok)
            self.assertIn("missing env vars", reason)
        finally:
            if old is not None:
                os.environ["AZURE_SUBSCRIPTION_ID"] = old


# ── Integration: run-pin-validation as subprocess ────────────────────

class TestRunPinCLI(unittest.TestCase):
    """Integration tests that invoke run-pin-validation.py as a subprocess."""

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, str(HERE.parent / "run-pin-validation.py"), "--help"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("--all", result.stdout)
        self.assertIn("--include-azure", result.stdout)
        self.assertIn("--base", result.stdout)

    def test_changed_only_no_changes(self):
        """changed-only mode with HEAD as base → 0 files → fast exit."""
        result = subprocess.run(
            [sys.executable, str(HERE.parent / "run-pin-validation.py"),
             "--base", "HEAD", "--skip-install"],
            capture_output=True, text=True, timeout=15,
            cwd=str(HERE.parent.parent),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("pin files", result.stdout)


# ── Regex matching in expected_output ────────────────────────────────

class TestRegexMatching(unittest.TestCase):
    """Test that run_one supports regex patterns in expected_output."""

    @classmethod
    def setUpClass(cls):
        rpv_path = HERE.parent / "run-pin-validation.py"
        rpv_spec = importlib.util.spec_from_file_location("rpv2", rpv_path)
        cls.rpv = importlib.util.module_from_spec(rpv_spec)
        assert rpv_spec.loader is not None
        rpv_spec.loader.exec_module(cls.rpv)

    def test_substring_match(self):
        pin = {
            "validation": {
                "script": "echo 'version 1.2.3 installed'",
                "expected_output": ["version 1.2.3"],
                "failure_signatures": [],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "skills" / "test" / "references" / "upstream-pin.md"
            path.parent.mkdir(parents=True)
            path.touch()
            ok, msg = self.rpv.run_one(path, pin)
            self.assertTrue(ok, msg)

    def test_regex_match(self):
        pin = {
            "validation": {
                "script": "echo 'version 1.2.3 installed'",
                "expected_output": [r"version \d+\.\d+\.\d+"],
                "failure_signatures": [],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "skills" / "test" / "references" / "upstream-pin.md"
            path.parent.mkdir(parents=True)
            path.touch()
            ok, msg = self.rpv.run_one(path, pin)
            self.assertTrue(ok, msg)

    def test_failure_signature_regex(self):
        pin = {
            "validation": {
                "script": "echo 'ERROR: connection failed with code 500'",
                "expected_output": [],
                "failure_signatures": [r"ERROR:.*code \d{3}"],
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "skills" / "test" / "references" / "upstream-pin.md"
            path.parent.mkdir(parents=True)
            path.touch()
            ok, msg = self.rpv.run_one(path, pin)
            self.assertFalse(ok)
            self.assertIn("failure_signature", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)

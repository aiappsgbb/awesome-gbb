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
    script: str = "echo ok",
) -> str:
    req = requires or ["github_only"]
    req_str = ", ".join(req)
    # Use YAML block scalar for multi-line scripts
    if "\n" in script:
        script_yaml = f"  script: |\n" + "\n".join(f"    {line}" for line in script.split("\n"))
    else:
        script_yaml = f"  script: {script}"
    return (
        f"---\n"
        f"schema_version: {schema_version}\n"
        f"freshness_tier: {freshness_tier}\n"
        f"automation_tier: {automation_tier}\n"
        f"validation:\n"
        f"  requires: [{req_str}]\n"
        f"  runnable: {str(runnable).lower()}\n"
        f"{script_yaml}\n"
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

    def test_auto_tier_with_azure_requires_and_runnable_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(
                automation_tier="auto",
                requires=["azure_subscription"],
                runnable=True,
            ))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("runnable=true" in e.lower() or "auto" in e for e in errs))

    def test_auto_tier_with_azure_not_runnable_passes(self):
        """auto + creds + runnable=false is valid: agent edits pin, CI validates."""
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(
                automation_tier="auto",
                requires=["azure_subscription"],
                runnable=False,
            ))
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])

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

    def test_pip_compat_release_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(script='pip install --quiet "some-pkg~=1.2.3"'))
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])

    def test_pip_prerelease_exact_pin_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(script='pip install --quiet "agent-hosting==1.0.0a260521"'))
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])

    def test_pip_bare_stable_eq_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(script='pip install --quiet "some-pkg==1.2.3"'))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("pip cap policy" in e and "bare `==`" in e for e in errs))

    def test_pip_unbounded_gte_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(script='pip install --quiet "some-pkg>=1.2.3"'))
            errs = vs.validate_pin_file(p)
            self.assertTrue(any("pip cap policy" in e and "unbounded" in e for e in errs))

    def test_pip_shell_var_with_default_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "upstream-pin.md"
            _write(p, _pin_md(script='pip install --quiet "some-pkg~=${PINNED:-1.2.3}"'))
            errs = vs.validate_pin_file(p)
            self.assertEqual(errs, [])


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
                      automation_tier="auto"),
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
                          automation_tier="auto"),
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
                          automation_tier="auto"),
                pathlib.Path("x"),
                include_azure=True,
            )
            self.assertFalse(ok)
            self.assertIn("missing env vars", reason)
        finally:
            if old is not None:
                os.environ["AZURE_SUBSCRIPTION_ID"] = old

    def test_issue_only_skips_even_with_azure_flag(self):
        """issue_only pins are human-only — never auto-run, even under
        --include-azure with creds present (AGENTS.md § 12.3)."""
        import os
        old = os.environ.get("AZURE_SUBSCRIPTION_ID")
        os.environ["AZURE_SUBSCRIPTION_ID"] = "test-sub"
        try:
            ok, reason = self.rpv.should_run(
                self._pin(requires=["azure_subscription"], runnable=False,
                          automation_tier="issue_only"),
                pathlib.Path("x"),
                include_azure=True,
            )
            self.assertFalse(ok)
            self.assertIn("issue_only", reason)
        finally:
            if old is None:
                os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
            else:
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


# ── MID-I lint: sync azure.identity creds in FoundryChatClient ───────

class TestNoSyncCredInFoundryChatClient(unittest.TestCase):
    """Lint added after PR #184 — encodes the MID-I async-credential rule
    so the same regression cannot land again. Covers direct calls,
    variable-hop assignments, alias imports, wildcard imports, and the
    documented carve-outs.
    """

    def _scan(self, src: str) -> list[str]:
        return vs._scan_source_for_sync_creds(src, "fixture.py")

    def test_direct_sync_default_credential_flags(self) -> None:
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DefaultAzureCredential(), agent_name='x')\n"
        )
        errors = self._scan(src)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("DefaultAzureCredential", errors[0])
        self.assertIn("MID-I", errors[0])

    def test_async_default_credential_passes(self) -> None:
        src = (
            "from azure.identity.aio import DefaultAzureCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DefaultAzureCredential(), agent_name='x')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_variable_hop_sync_flags(self) -> None:
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "cred = DefaultAzureCredential()\n"
            "c = FoundryChatClient(credential=cred, agent_name='x')\n"
        )
        errors = self._scan(src)
        self.assertEqual(len(errors), 1, errors)

    def test_variable_reassign_to_async_passes(self) -> None:
        """Last-write-wins: if cred is reassigned to an async credential
        before reaching FoundryChatClient, no flag. Documents the
        last-write-wins behavior of _collect_credential_assignments.
        """
        src = (
            "from azure.identity import DefaultAzureCredential as SyncDAC\n"
            "from azure.identity.aio import DefaultAzureCredential as AsyncDAC\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "cred = SyncDAC()\n"
            "cred = AsyncDAC()\n"
            "c = FoundryChatClient(credential=cred, agent_name='x')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_aliased_sync_import_still_flags(self) -> None:
        src = (
            "from azure.identity import DefaultAzureCredential as DAC\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DAC(), agent_name='x')\n"
        )
        errors = self._scan(src)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("`DAC`", errors[0])

    def test_sync_azure_cli_credential_flags(self) -> None:
        """The lint covers every credential class imported from
        azure.identity, not just DefaultAzureCredential. Documents the
        broadened scope beyond what PR #184 originally surfaced.
        """
        src = (
            "from azure.identity import AzureCliCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=AzureCliCredential(), agent_name='x')\n"
        )
        errors = self._scan(src)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("AzureCliCredential", errors[0])

    def test_open_ai_chat_client_carve_out_passes(self) -> None:
        """OpenAIChatClient takes sync creds per SKILL.md L484 — NOT
        flagged. Documents the FoundryChatClient-only scope.
        """
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "from agent_framework.openai import OpenAIChatClient\n"
            "c = OpenAIChatClient(credential=DefaultAzureCredential(), model='gpt-4o-mini')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_get_bearer_token_provider_carve_out_passes(self) -> None:
        """get_bearer_token_provider REQUIRES sync credentials — NOT
        flagged because it isn't a FoundryChatClient(credential=...) call.
        """
        src = (
            "from azure.identity import DefaultAzureCredential, get_bearer_token_provider\n"
            "p = get_bearer_token_provider(DefaultAzureCredential(), 'https://x/.default')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_no_credential_kwarg_passes(self) -> None:
        """FoundryChatClient() with no `credential=` defers to the
        default chain — NOT flagged.
        """
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(agent_name='x')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_wildcard_import_skips_silently(self) -> None:
        """Wildcard import — can't classify symbols, skip
        conservatively rather than false-positive.
        """
        src = (
            "from azure.identity import *\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DefaultAzureCredential(), agent_name='x')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_no_azure_identity_import_skips_silently(self) -> None:
        """Code block with no azure.identity[.aio] import — bare
        `DefaultAzureCredential()` may have been imported in a sibling
        block we can't see. Skip rather than false-positive.
        """
        src = (
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DefaultAzureCredential(), agent_name='x')\n"
        )
        self.assertEqual(self._scan(src), [])

    def test_syntax_error_block_skips_silently(self) -> None:
        """Shape-variant snippets that don't parse as full Python should
        not crash the gate.
        """
        src = "credential=DefaultAzureCredential(),\n"  # fragment
        self.assertEqual(self._scan(src), [])

    def test_qualified_call_flags(self) -> None:
        """`agent_framework.foundry.FoundryChatClient(credential=...)`
        is matched the same as the unqualified import.
        """
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "import agent_framework.foundry as f\n"
            "c = f.FoundryChatClient(credential=DefaultAzureCredential(), agent_name='x')\n"
        )
        errors = self._scan(src)
        self.assertEqual(len(errors), 1, errors)

    def test_line_offset_applied(self) -> None:
        """For SKILL.md fenced blocks, line_offset shifts ast.lineno into
        the enclosing-file coordinate. Documents the contract used by
        validate_no_sync_cred_in_foundry_chat_client.
        """
        src = (
            "from azure.identity import DefaultAzureCredential\n"
            "from agent_framework.foundry import FoundryChatClient\n"
            "c = FoundryChatClient(credential=DefaultAzureCredential())\n"
        )
        errors = vs._scan_source_for_sync_creds(src, "SKILL.md", line_offset=100)
        self.assertEqual(len(errors), 1)
        # The offending FoundryChatClient call is on src line 3, so reported
        # line should be 3 + 100 = 103.
        self.assertIn("SKILL.md:103", errors[0])

    def test_extract_python_blocks(self) -> None:
        """Verifies that the SKILL.md fenced-block extractor returns
        correct (start_line, source) tuples — the offset contract that
        keeps line numbers stable across edits.
        """
        text = (
            "# Heading\n"          # line 1
            "\n"                    # line 2
            "Some prose.\n"         # line 3
            "\n"                    # line 4
            "```python\n"           # line 5 (fence)
            "import os\n"           # line 6 (block code line 1)
            "x = 1\n"               # line 7 (block code line 2)
            "```\n"                 # line 8 (closing fence)
            "\n"                    # line 9
            "More prose.\n"         # line 10
            "\n"                    # line 11
            "```python\n"           # line 12
            "y = 2\n"               # line 13
            "```\n"                 # line 14
        )
        blocks = vs._extract_python_blocks(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0], (6, "import os\nx = 1"))
        self.assertEqual(blocks[1], (13, "y = 2"))

    def test_no_sync_cred_lint_clean_on_live_catalog(self) -> None:
        """Integration smoke: running the lint against the actual catalog
        on disk must return ZERO errors. This is the regression gate — if
        anyone adds a sync-cred-into-FoundryChatClient site, this fails.
        """
        errors = vs.validate_no_sync_cred_in_foundry_chat_client()
        self.assertEqual(errors, [], f"Catalog regression: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)

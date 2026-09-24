import importlib.util
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "doctor_inventory", Path(__file__).resolve().parents[1] / "scripts/inventory.py")
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)
PROBE_SPEC = importlib.util.spec_from_file_location(
    "doctor_probe", Path(__file__).resolve().parents[1] / "scripts/probe_cli.py")
probe_cli = importlib.util.module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(probe_cli)


class InventoryTests(unittest.TestCase):
    def test_json_comments_preserve_url(self):
        self.assertEqual(inventory.parse_json('// comment\n{"url":"https://x//y", /* c */ "a":1}'),
                         {"url": "https://x//y", "a": 1})

    def test_invalid_json_is_not_silently_accepted(self):
        for text in ('{"a": }', '{"a":1,"a":2}', '{"x":/*'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                inventory.parse_json(text)

    def test_json_escaped_quotes_preserved(self):
        text = json.dumps({"value": 'a\\"//not-comment/*still-string*/'})
        self.assertEqual(inventory.parse_json(text), json.loads(text))

    def test_missing_launcher_and_offline_dynamic_dependencies(self):
        report = inventory.inspect_server("test", {
            "command": "/nonexistent/uv", "args": ["run", "--with", "pkg", "python"],
            "env": {"UV_OFFLINE": "1", "API_KEY": "secret-never-output"}}, "source")
        self.assertIn("missing-launcher", report["signals"])
        self.assertIn("offline-dynamic-resolution", report["signals"])
        self.assertNotIn("secret-never-output", json.dumps(report))

    def test_url_credentials_and_args_not_emitted(self):
        report = inventory.inspect_server("test", {
            "url": "https://user:secret@example.org/mcp?apiKey=secret",
            "args": ["--token", "secret"], "headers": {"Authorization": "secret"}}, "source")
        self.assertNotIn("secret", json.dumps(report))
        self.assertNotIn("example.org", json.dumps(report))
        self.assertEqual(report["transport"], "remote")
        for key in ("handshake", "authentication", "useful_tool"):
            self.assertEqual(report[key], "not-tested")

    def test_direct_python_offline_is_not_resolution_failure(self):
        for args in (["-m", "module"], ["server.py"]):
            report = inventory.inspect_server("mem0", {
                "command": "/usr/bin/python3", "args": args,
                "env": {"UV_OFFLINE": "1"}}, "source")
            self.assertNotIn("offline-dynamic-resolution", report["signals"])

    def test_uv_run_without_dynamic_dependencies_not_flagged(self):
        report = inventory.inspect_server("pinned", {
            "command": "uv", "args": ["run", "--locked", "server"],
            "env": {"UV_OFFLINE": "true"}}, "source")
        self.assertNotIn("offline-dynamic-resolution", report["signals"])

    def test_intentional_tool_exclusions_and_credential_provider(self):
        config = {"command": "npx", "args": ["--isolated"],
                  "tools": ["monitor", "storage"],
                  "env": {"AZURE_TOKEN_CREDENTIALS": "AzureCliCredential"}}
        original = json.dumps(config)
        report = inventory.inspect_server("Azure", config, "source")
        self.assertEqual(json.dumps(config), original)
        self.assertEqual(report["tools_policy"], "explicit")
        self.assertEqual(report["credential_provider"], "AzureCliCredential")
        self.assertTrue(report["isolated_browser"])
        self.assertNotIn("get_azure_bestpractices", json.dumps(report))
        self.assertNotIn("pricing", json.dumps(report))

    def test_bad_server_shapes_are_findings(self):
        for config in ([], {"env": []}, {"args": {}}, {"command": 5}):
            self.assertTrue(inventory.inspect_server("test", config, "source")["signals"])

    def test_yaml_unavailable_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.skill(Path(tmp), "one")
            with patch.object(inventory, "yaml", None):
                self.assertIn("yaml-check-unavailable", inventory.inspect_skill(f, "user")["signals"])

    @staticmethod
    def skill(root, name, description="Valid", frontmatter=None):
        p = root / name / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(frontmatter or f"---\nname: {name}\ndescription: {description}\n---\nBody")
        return p

    def test_invalid_skill_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.skill(Path(tmp), "test-skill", "x" * 1025)
            self.assertIn("invalid-description", inventory.inspect_skill(f, "user")["signals"])

    def test_yaml_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.skill(Path(tmp), "one", frontmatter="---\nname: one\nname: two\ndescription: valid\n---\n")
            self.assertIn("invalid-frontmatter", inventory.inspect_skill(f, "user")["signals"])

    def test_malformed_yaml_does_not_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.skill(Path(tmp), "one", frontmatter="---\nname: [secret-never-output\n---\n")
            report = inventory.inspect_skill(f, "user")
            self.assertIn("invalid-frontmatter", report["signals"])
            self.assertNotIn("secret-never-output", json.dumps(report))

    def test_identical_symlink_not_a_second_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            self.skill(p, "one")
            (p / "two").symlink_to(p / "one", target_is_directory=True)
            self.assertEqual(len(inventory.collect_skills([(p, "user")])), 1)

    def test_description_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self.skill(Path(tmp), "one", "x" * 1024)
            self.assertNotIn("invalid-description", inventory.inspect_skill(f, "user")["signals"])


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / ".copilot"
        self.config.mkdir()

    def write(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))

    def scan(self, **kwargs):
        return inventory.inventory(self.home, **kwargs)

    def plugin(self, name="enabled", enabled=True, manifest=None):
        root = self.config / "installed-plugins" / name
        self.write(root / "plugin.json", manifest or {"name": name, "skills": "skills"})
        InventoryTests.skill(root / "skills", name)
        return {"name": name, "marketplace": "market", "enabled": enabled, "cache_path": str(root)}

    def test_default_scan_never_spawns_or_writes(self):
        InventoryTests.skill(self.config / "skills", "one")
        before = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        with patch("subprocess.run", side_effect=AssertionError("must not execute")):
            self.scan()
        after = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_only_enabled_registered_plugins_count(self):
        entries = [self.plugin(), self.plugin("disabled", False)]
        self.plugin("unregistered")
        self.write(self.config / "config.json", {"installedPlugins": entries})
        report = self.scan()
        self.assertEqual([s["name"] for s in report["skills"]], ["enabled"])

    def test_project_override_disables_plugin(self):
        self.write(self.config / "config.json", {"installedPlugins": [self.plugin()]})
        project = self.home / "project"
        self.write(project / ".github/copilot/settings.json", {"enabledPlugins": {"enabled@market": False}})
        self.assertEqual(self.scan(project=project)["skills"], [])

    def test_plugin_mcp_defaults_and_portable_paths(self):
        legacy = self.plugin()
        root = Path(legacy["cache_path"])
        self.write(root / ".mcp.json", {"mcpServers": {"legacy": {"url": "https://hidden.example"}}})
        portable = self.plugin("portable", manifest={
            "name": "portable", "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "skills": "wrong-ignored"})
        self.write(Path(portable["cache_path"]) / "mcp.json",
                   {"mcpServers": {"portable": {"command": "python3", "args": ["-m", "server"]}}})
        self.write(self.config / "config.json", {"installedPlugins": [legacy, portable]})
        report = self.scan()
        self.assertEqual({s["name"] for s in report["servers"]}, {"legacy", "portable"})
        self.assertEqual({s["name"] for s in report["skills"]}, {"enabled", "portable"})

    def test_inline_plugin_mcp_and_escape_rejected(self):
        entry = self.plugin(manifest={"name": "enabled", "skills": "../../outside",
                                     "mcpServers": {"inline": {"url": "https://private.example"}}})
        self.write(self.config / "config.json", {"installedPlugins": [entry]})
        report = self.scan()
        self.assertIn("plugin-component-outside-root", report["plugins"][0]["signals"])
        self.assertEqual(report["servers"][0]["name"], "inline")

    def test_missing_cache_reports_not_healthy(self):
        self.write(self.config / "config.json", {"installedPlugins": [
            {"name": "missing", "enabled": True, "cache_path": str(self.home / "absent")}]})
        self.assertIn("missing-plugin-manifest", [f["code"] for f in self.scan()["findings"]])

    def test_distinct_copies_and_disabled_skill(self):
        InventoryTests.skill(self.config / "skills", "one")
        InventoryTests.skill(self.home / ".agents/skills", "one")
        self.assertIn("duplicate-skill-name", [f["code"] for f in self.scan()["findings"]])
        self.write(self.config / "settings.json", {"disabledSkills": ["one"]})
        self.assertNotIn("duplicate-skill-name", [f["code"] for f in self.scan()["findings"]])

    def test_trigger_overlap_is_only_candidate(self):
        description = "'USE FOR: exact phrase, another phrase. DO NOT USE FOR: deployment'"
        InventoryTests.skill(self.config / "skills", "one", description)
        InventoryTests.skill(self.config / "skills", "two", description)
        findings = [f for f in self.scan()["findings"] if f["code"] == "trigger-overlap-candidate"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["impact"], "informational")

    def test_project_mcp_and_instruction_sources(self):
        project = self.home / "project"
        self.write(project / ".github/mcp.json", {"mcpServers": {"p": {"url": "https://secret.example"}}})
        (project / "AGENTS.md").write_text("confidential instruction")
        report = self.scan(project=project)
        self.assertEqual(report["servers"][0]["name"], "p")
        self.assertNotIn("confidential", json.dumps(report))
        self.assertEqual(len(report["instructions"]), 1)

    def test_config_secrets_and_parse_errors_never_echo(self):
        self.write(self.config / "config.json", {"token": "secret-never-output", "installedPlugins": []})
        (self.config / "settings.json").write_text('{"secret-never-output": nope}')
        report = self.scan()
        self.assertNotIn("secret-never-output", json.dumps(report))
        self.assertIn("config-unreadable-or-invalid", [f["code"] for f in report["findings"]])

    def test_config_home_override(self):
        alternate = self.home / "alternate"
        InventoryTests.skill(alternate / "skills", "one")
        report = self.scan(copilot_home=alternate)
        self.assertEqual([s["name"] for s in report["skills"]], ["one"])

    def test_history_first_unchanged_and_drift(self):
        path = self.home / "private/history.sqlite"
        first = self.scan()
        self.assertEqual(inventory.record_snapshot(path, first)["status"], "no-baseline")
        unchanged = inventory.record_snapshot(path, self.scan())["delta"]
        self.assertEqual(unchanged, {"added": [], "removed": [], "changed": []})
        InventoryTests.skill(self.config / "skills", "one")
        changed = inventory.record_snapshot(path, self.scan())["delta"]
        self.assertTrue(changed["added"])
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("select count(*) from snapshots").fetchone()[0], 3)

    def test_history_scope_and_secret_rotation(self):
        path = self.home / "private/history.sqlite"
        self.write(self.config / "mcp-config.json", {"mcpServers": {"s": {
            "command": "python3", "env": {"KEY": "old-secret"}}}})
        inventory.record_snapshot(path, self.scan())
        self.write(self.config / "mcp-config.json", {"mcpServers": {"s": {
            "command": "python3", "env": {"KEY": "new-secret"}}}})
        self.assertEqual(inventory.record_snapshot(path, self.scan())["delta"],
                         {"added": [], "removed": [], "changed": []})
        self.assertEqual(inventory.record_snapshot(path, self.scan(project=self.home))["status"], "no-baseline")
        self.assertNotIn(b"old-secret", path.read_bytes())
        self.assertNotIn(b"new-secret", path.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX permission assertion")
    def test_shared_history_and_symlink_refused(self):
        path = self.home / "history.sqlite"
        path.touch(mode=0o644)
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            inventory.record_snapshot(path, self.scan())
        link = self.home / "link"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            inventory.record_snapshot(link, self.scan())

    def test_size_limit(self):
        path = self.config / "settings.json"
        path.write_text(" " * (inventory.MAX_BYTES + 1))
        self.assertIn("config-unreadable-or-invalid", [f["code"] for f in self.scan()["findings"]])

    def test_arbitrary_metadata_values_suppressed(self):
        self.write(self.config / "settings.json", {"autoUpdatesChannel": "secret-never-output"})
        self.write(self.config / "mcp-config.json", {"mcpServers": {"s": {
            "type": "secret-never-output", "command": "python3"}}})
        self.assertNotIn("secret-never-output", json.dumps(self.scan()))


class ProbeTests(unittest.TestCase):
    def test_bounded_help_and_version(self):
        import sys
        responses = [
            subprocess.CompletedProcess([], 0, "GitHub Copilot CLI 1.0.88\n", ""),
            subprocess.CompletedProcess([], 0, "options: --no-auto-update --other", ""),
        ]
        with patch.object(probe_cli.subprocess, "run", side_effect=responses) as run:
            result = probe_cli.probe(Path(sys.executable), flag="--no-auto-update")
        self.assertEqual(result["version"], "1.0.88")
        self.assertEqual(result["flag_status"], "documented")
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 15)
            self.assertFalse(call.kwargs.get("shell", False))
            self.assertEqual(call.kwargs["env"]["COPILOT_AUTO_UPDATE"], "false")

    def test_failures_never_echo_stderr(self):
        import sys
        with patch.object(probe_cli.subprocess, "run", return_value=
                          subprocess.CompletedProcess([], 1, "", "secret-never-output")):
            result = probe_cli.probe(Path(sys.executable))
        self.assertEqual(result["version"], "exit-1")
        self.assertEqual(result["help"], "not-tested")
        self.assertNotIn("secret-never-output", json.dumps(result))

    def test_timeout_does_not_retry(self):
        import sys
        with patch.object(probe_cli.subprocess, "run", side_effect=
                          subprocess.TimeoutExpired("private-command", 15)) as run:
            result = probe_cli.probe(Path(sys.executable))
        self.assertEqual(result["version"], "timeout")
        self.assertEqual(run.call_count, 1)

    def test_unlisted_flag_not_proven_unsupported(self):
        import sys
        with patch.object(probe_cli.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], 0, "GitHub Copilot CLI 1.0.88", ""),
            subprocess.CompletedProcess([], 0, "--flag-longer", "")]):
            result = probe_cli.probe(Path(sys.executable), flag="--flag")
        self.assertEqual(result["flag_status"], "not-listed")

    def test_config_commands_cannot_be_executed(self):
        import sys
        for topic, flag in (("update", None), ("root", "--flag;rm"), ("root", "anything")):
            with self.assertRaises(ValueError):
                probe_cli.probe(Path(sys.executable), topic, flag)


if __name__ == "__main__":
    unittest.main()

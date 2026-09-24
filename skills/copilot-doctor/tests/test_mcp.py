from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import inventory
import probe_mcp


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        (self.home / ".copilot").mkdir()
        self.path = self.home / ".copilot/mcp-config.json"
        self.store = self.home / "history.sqlite"
        self.write(["--extension", "--browser", "msedge"])

    def write(self, args):
        self.path.write_text(json.dumps({"mcpServers": {"Playwright": {"command": sys.executable, "args": args}}}))

    def test_extension_is_accepted_without_isolation_dogma(self):
        with patch.object(inventory.shutil, "which", return_value=sys.executable):
            report = inventory.inventory(self.home)
        inventory.apply_preferences(self.store, report, ["Playwright:browser_mode"])
        self.assertEqual(report["servers"][0]["browser_mode"], "extension")
        self.assertEqual(report["servers"][0]["preferences"]["browser_mode"], "accepted")
        self.assertFalse(report["findings"])

    def test_changed_preference_is_review_not_restore(self):
        report = inventory.inventory(self.home)
        inventory.apply_preferences(self.store, report, ["Playwright:browser_mode"])
        self.write(["--isolated"])
        report = inventory.inventory(self.home)
        inventory.apply_preferences(self.store, report)
        finding = next(f for f in report["findings"] if f["code"] == "changed-from-accepted")
        self.assertEqual(finding["impact"], "review")
        self.assertIn("ask before restoring", finding["evidence"])
        self.assertIn("--isolated", self.path.read_text())

    def test_accept_does_not_suppress_broken_launcher(self):
        self.path.write_text(json.dumps({"mcpServers": {"Playwright": {
            "command": "/nonexistent/python", "args": ["--extension"]}}}))
        report = inventory.inventory(self.home)
        inventory.apply_preferences(self.store, report, ["Playwright:browser_mode"])
        self.assertIn("missing-launcher", [f["code"] for f in report["findings"]])

    def test_preference_scope_is_not_global(self):
        report = inventory.inventory(self.home)
        inventory.apply_preferences(self.store, report, ["Playwright:browser_mode"])
        another = inventory.inventory(self.home, project=self.home)
        inventory.apply_preferences(self.store, another)
        self.assertNotIn("preferences", another["servers"][0])

    def test_invalid_accept_rejected(self):
        for selector in ("Playwright:env", "missing:browser_mode", "Playwright"):
            with self.assertRaises(ValueError):
                inventory.apply_preferences(self.store, inventory.inventory(self.home), [selector])


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"command": sys.executable, "args": []}
        self.path = self.root / "config.json"
        self.path.write_text(json.dumps({"mcpServers": {"test": self.config}}))
        self.plan = {"config_path": str(self.path), "server": "test",
                     "config_fingerprint": probe_mcp.fingerprint(self.config),
                     "approved_read_only": True, "authentication": "not-tested",
                     "launcher": {"command": sys.executable, "args": []}, "deadline_seconds": 5}

    def test_plan_requires_approval(self):
        self.plan["approved_read_only"] = False
        with self.assertRaises(ValueError):
            probe_mcp.validate_plan(self.plan)

    def test_configuration_drift_blocks_execution(self):
        self.plan["config_fingerprint"] = "wrong"
        with self.assertRaises(ValueError):
            probe_mcp.validate_plan(self.plan)

    def test_no_implicit_launcher(self):
        del self.plan["launcher"]
        with self.assertRaises(ValueError):
            probe_mcp.validate_plan(self.plan)

    def test_deadline_is_bounded(self):
        for value in (0, 61, True, "30"):
            self.plan["deadline_seconds"] = value
            with self.assertRaises(ValueError):
                probe_mcp.validate_plan(self.plan)

    def test_tool_allowlist_enforced(self):
        self.config["tools"] = ["safe"]
        self.path.write_text(json.dumps({"mcpServers": {"test": self.config}}))
        self.plan["config_fingerprint"] = probe_mcp.fingerprint(self.config)
        self.plan["tool"] = {"name": "excluded", "arguments": {}, "expect": {"kind": "nonempty-text"}}
        with self.assertRaises(ValueError):
            probe_mcp.validate_plan(self.plan)

    def test_malformed_allowlist_fails_closed(self):
        for policy in ("safe", {"safe": True}, [1], None):
            with self.subTest(policy=policy):
                self.config["tools"] = policy
                self.path.write_text(json.dumps({"mcpServers": {"test": self.config}}))
                self.plan["config_fingerprint"] = probe_mcp.fingerprint(self.config)
                self.plan["tool"] = {"name": "excluded", "arguments": {},
                                     "expect": {"kind": "nonempty-text"}}
                with self.assertRaises(ValueError):
                    probe_mcp.validate_plan(self.plan)

    def test_invalid_expectation_rejected_before_execution(self):
        for expectation in ({"kind": "json-keys", "keys": "status"},
                            {"kind": "json-keys", "keys": [1]},
                            {"kind": "text-contains", "value": 1}):
            with self.subTest(expectation=expectation):
                self.plan["tool"] = {"name": "ping", "arguments": {}, "expect": expectation}
                with self.assertRaises(ValueError):
                    probe_mcp.validate_plan(self.plan)

    def test_schema_types_are_structural_not_raw_metadata(self):
        self.assertEqual(probe_mcp.schema_type({"type": "string"}), "string")
        self.assertEqual(probe_mcp.schema_type({"type": ["string", "null"]}), ["string", "null"])
        for value in ("secret-never-output", {"private": "secret-never-output"},
                      ["string", "secret-never-output"]):
            self.assertEqual(probe_mcp.schema_type({"type": value}), "unspecified")

    def test_shape_validation_and_nonempty_are_distinct(self):
        response = SimpleNamespace(isError=False, content=[
            SimpleNamespace(type="text", text='{"status":"ready"}')], structuredContent=None)
        self.assertEqual(probe_mcp.check_result(response, {"kind": "json-keys", "keys": ["status"]}), "pass")
        self.assertEqual(probe_mcp.check_result(response, {"kind": "json-keys", "keys": ["other"]}), "unexpected-shape")
        self.assertEqual(probe_mcp.check_result(response, {"kind": "nonempty-text"}), "response-received-unvalidated")
        response.isError = True
        self.assertEqual(probe_mcp.check_result(response, {"kind": "nonempty-text"}), "tool-error")

    def test_errors_never_echo_values(self):
        exc = ValueError("secret-never-output https://user:password@example.test")
        self.assertNotIn("secret", probe_mcp.safe_error(exc))
        self.assertEqual(probe_mcp.safe_error(ImportError("private module")),
                         "missing-or-incompatible-dependency")

    def test_fastmcp_string_wrapper_not_mistaken_for_api_shape(self):
        response = SimpleNamespace(isError=False, content=[
            SimpleNamespace(type="text", text='{"results":[],"count":0}')],
            structuredContent={"result": '{"results":[],"count":0}'})
        self.assertEqual(probe_mcp.check_result(response, {"kind": "json-keys", "keys": ["results"]}), "pass")
        response.content[0].text = '{"error":"private error","results":[]}'
        self.assertEqual(probe_mcp.check_result(response, {"kind": "json-keys", "keys": ["results"]}), "tool-error")

    def test_health_history_retains_status_only(self):
        path = self.root / "history.sqlite"
        self.plan["tool"] = {"name": "test", "arguments": {"private": "secret-never-output"}}
        result = {"server": "test", "initialization": "pass", "useful_result": "pass"}
        self.assertEqual(probe_mcp.save_result(path, self.plan, result)["status"], "no-baseline")
        self.assertEqual(probe_mcp.save_result(path, self.plan, result)["changed_statuses"], [])
        self.assertNotIn(b"secret-never-output", path.read_bytes())

    def test_imported_receipts_compare_by_observation_time(self):
        path = self.root / "history.sqlite"
        newer = {"server": "test", "useful_result": "pass", "scanned_at": "2026-09-24T12:01:00+00:00"}
        older = {"server": "test", "useful_result": "unexpected-shape", "scanned_at": "2026-09-24T12:00:00+00:00"}
        probe_mcp.save_result(path, self.plan, newer)
        probe_mcp.save_result(path, self.plan, older)
        self.assertEqual(probe_mcp.save_result(path, self.plan, newer)["changed_statuses"], [])

    @unittest.skipUnless(os.name == "posix", "POSIX owned-process-group probe")
    def test_live_synthetic_protocol_and_cleanup(self):
        script = self.root / "server.py"
        script.write_text(
            "import sys,json\n"
            "for line in sys.stdin:\n"
            " r=json.loads(line)\n"
            " if 'id' not in r: continue\n"
            " m=r['method']\n"
            " if m=='initialize': v={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'test','version':'1'}}\n"
            " elif m=='tools/list': v={'tools':[{'name':'ping','inputSchema':{'type':'object','properties':{'flag':{'type':'secret-never-output'}}}}]}\n"
            " else: v={'content':[{'type':'text','text':'{\"status\":\"ready\"}'}],'isError':False}\n"
            " print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':v}),flush=True)\n")
        self.plan["launcher"]["args"] = [str(script)]
        self.plan["tool"] = {"name": "ping", "arguments": {}, "expect": {"kind": "json-keys", "keys": ["status"]}}
        self.plan["authentication"] = "public"
        self.plan["deadline_seconds"] = 10
        result = probe_mcp.run_probe(self.plan)
        self.assertNotIn("error", result)
        self.assertEqual(result["initialization"], "pass")
        self.assertEqual(result["useful_result"], "pass")
        self.assertEqual(result["authentication"], "not-required")
        self.assertTrue(result["worker_stopped"])
        self.assertNotIn("ready", json.dumps(result))
        self.assertNotIn("secret-never-output", json.dumps(result))
        self.assertEqual(result["tools"][0]["parameters"]["flag"], "unspecified")

    @unittest.skipUnless(os.name == "posix", "POSIX owned-process-group probe")
    def test_hung_server_is_stopped_at_deadline(self):
        self.plan["launcher"]["args"] = ["-c", "import time;time.sleep(30)"]
        result = probe_mcp.run_probe(self.plan)
        self.assertEqual(result["error"], "deadline-exceeded")
        self.assertTrue(result["worker_stopped"])

    @unittest.skipUnless(os.name == "posix", "POSIX owned-process-group probe")
    def test_deadline_stops_descendant_ignoring_term(self):
        pidfile = self.root / "descendant.pid"
        child = "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
        launcher = (
            "import subprocess,sys,time\n"
            f"p=subprocess.Popen([sys.executable,'-c',{child!r}])\n"
            f"open({str(pidfile)!r},'w').write(str(p.pid))\n"
            "time.sleep(30)\n"
        )
        self.plan["launcher"]["args"] = ["-c", launcher]
        started = time.monotonic()
        try:
            result = probe_mcp.run_probe(self.plan)
            self.assertEqual(result["error"], "deadline-exceeded")
            self.assertTrue(result["worker_stopped"])
            self.assertLess(time.monotonic() - started, 8)
            self.assertTrue(pidfile.exists())
            import subprocess
            state = subprocess.run(["ps", "-o", "stat=", "-p", pidfile.read_text()],
                                   capture_output=True, text=True, timeout=2).stdout.strip()
            self.assertTrue(not state or state.startswith("Z"), state)
        finally:
            if pidfile.exists():
                try:
                    os.kill(int(pidfile.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()

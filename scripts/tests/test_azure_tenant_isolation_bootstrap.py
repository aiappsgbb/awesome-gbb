"""Offline bootstrap regressions: synthetic index, HOME and fail-closed CLI stubs."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "skills/azure-tenant-isolation/references/bash/bootstrap.sh"
LIVE_FIXTURE = BOOTSTRAP.parents[2] / "test-fixture/read_only_validation.py"
TENANT = "00000000-0000-0000-0000-000000000001"
SUB_ID = "00000000-0000-0000-0000-000000000002"
OTHER_ID = "00000000-0000-0000-0000-000000000003"

STUB = """#!{python}
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps({{
        "tool": pathlib.Path(sys.argv[0]).name, "args": args,
        "azure": os.environ.get("AZURE_CONFIG_DIR"),
        "azd": os.environ.get("AZD_CONFIG_DIR"),
    }}) + "\\n")
if pathlib.Path(sys.argv[0]).name == "az" and args[:2] == ["group", "show"] and os.environ.get("STUB_ALLOW_GROUP"):
    subscription = args[args.index("--subscription") + 1]
    group = args[args.index("--name") + 1]
    print(json.dumps({{"name": group, "id": "/subscriptions/" + subscription + "/resourceGroups/" + group}}))
    sys.exit(0)
if pathlib.Path(sys.argv[0]).name != "az" or args[:2] != ["account", "show"]:
    sys.exit("Forbidden CLI operation")
if os.environ.get("STUB_NO_SESSION"):
    sys.exit("Synthetic session unavailable")
account = json.loads(os.environ["STUB_ACCOUNT"])
query = args[args.index("--query") + 1]
if query == os.environ.get("STUB_FAIL_QUERY"):
    sys.exit("Synthetic query failure")
print(account.get(query, ""))
"""


class TenantBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        # PATH contains only stubs and the bootstrap's offline dependencies.
        for name, target in (("python3", sys.executable), ("mkdir", shutil.which("mkdir"))):
            (self.bin / name).symlink_to(target)
        for name in ("az", "azd"):
            stub = self.bin / name
            stub.write_text(STUB.format(python=sys.executable))
            stub.chmod(0o755)
        self.index = self.home / "index.json"
        self.log = self.root / "calls.jsonl"
        self.alias = "example"
        self.config = {
            "tenant_id": TENANT,
            "default_subscription": "example-1",
            "allowed_subscriptions": ["example-1", "example-2"],
            "config_dir": None,
            "azd_config_dir": None,
        }
        self.account = {"tenantId": TENANT, "name": "example-2", "id": SUB_ID}

    def run_bootstrap(self, *, extra_env=None, after="", alias_argument=True):
        self.index.write_text(json.dumps({"tenants": {self.alias: self.config}}))
        environment = {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            "AZURE_TENANT_INDEX": str(self.index),
            "AZURE_TENANT_ALIAS": self.alias,
            "STUB_ACCOUNT": json.dumps(self.account),
            "STUB_LOG": str(self.log),
            **(extra_env or {}),
        }
        command = (
            'source "$1" "$2"; ' if alias_argument
            else 'bootstrap=$1; shift 2; source "$bootstrap"; '
        )
        command += after + '\npython3 -c \'import os; print("CHILD=" + os.environ["AZURE_CONFIG_DIR"] + "|" + os.environ["AZD_CONFIG_DIR"])\''
        result = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-c", command, "test",
             str(BOOTSTRAP), self.alias],
            env=environment, cwd=self.home, capture_output=True, text=True, timeout=10,
        )
        calls = [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []
        for call in calls:
            self.assertEqual(call["tool"], "az", call)
            self.assertEqual(call["args"][:2], ["account", "show"], call)
            for key, config_key, directory in (
                ("azure", "config_dir", ".azure-tenants"),
                ("azd", "azd_config_dir", ".azd-tenants"),
            ):
                expected = self.config.get(config_key) or str(self.home / directory / self.alias)
                if expected.startswith("~/"):
                    expected = str(self.home / expected[2:])
                self.assertEqual(call[key], expected)
                self.assertTrue(Path(expected).is_dir())
        return result

    def assert_accepted(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sub=" + self.account["name"], result.stdout)
        self.assertIn("CHILD=", result.stdout)

    def assert_rejected(self, result, reason):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(reason, result.stderr)
        self.assertNotIn("CHILD=", result.stdout)
        self.assertNotIn("Tenant isolation verified", result.stdout)

    def test_allowed_non_default_is_preserved(self):
        self.assert_accepted(self.run_bootstrap())

    def test_default_is_accepted(self):
        self.account["name"] = "example-1"
        self.assert_accepted(self.run_bootstrap())

    def test_disallowed_is_rejected_without_mutation(self):
        self.account["name"] = "outside"
        result = self.run_bootstrap()
        self.assert_rejected(result, "not in allowed")
        self.assertIn("example-1", result.stderr)
        self.assertIn("example-2", result.stderr)

    def test_tenant_mismatch_is_rejected(self):
        self.account["tenantId"] = OTHER_ID
        self.assert_rejected(self.run_bootstrap(), "Tenant mismatch")

    def test_absent_session_is_rejected(self):
        self.assert_rejected(
            self.run_bootstrap(extra_env={"STUB_NO_SESSION": "1"}), "No active az session"
        )

    def test_empty_account_fields_fail_closed(self):
        for field in ("tenantId", "name", "id"):
            with self.subTest(field=field):
                original = self.account[field]
                self.account[field] = ""
                self.assert_rejected(self.run_bootstrap(), "No active az session")
                self.account[field] = original

    def test_subscription_read_failure_fails_closed(self):
        self.assert_rejected(
            self.run_bootstrap(extra_env={"STUB_FAIL_QUERY": "id"}), "No active az session"
        )

    def test_missing_or_empty_allowlist_accepts_only_default(self):
        for allowed in (None, []):
            for active in ("example-1", "example-2"):
                with self.subTest(allowed=allowed, active=active):
                    self.config.pop("allowed_subscriptions", None)
                    if allowed is not None:
                        self.config["allowed_subscriptions"] = allowed
                    self.account["name"] = active
                    result = self.run_bootstrap()
                    if active == "example-1":
                        self.assert_accepted(result)
                    else:
                        self.assert_rejected(result, "not in allowed")

    def test_guid_allowlist_and_default_fallback(self):
        self.config["allowed_subscriptions"] = [SUB_ID]
        self.assert_accepted(self.run_bootstrap())
        self.config["allowed_subscriptions"] = []
        self.config["default_subscription"] = SUB_ID
        self.assert_accepted(self.run_bootstrap())

    def test_default_is_not_implicitly_added_to_nonempty_allowlist(self):
        self.config["allowed_subscriptions"] = ["example-2"]
        self.account["name"] = "example-1"
        self.assert_rejected(self.run_bootstrap(), "not in allowed")

    def test_names_are_literal_not_regexes_or_substrings(self):
        self.config["allowed_subscriptions"] = ["example.[2] team's subscription"]
        self.account["name"] = "example.[2] team's subscription"
        self.assert_accepted(self.run_bootstrap())
        for name in ("exampleX2 team's subscription", "example", "team's subscription"):
            self.account["name"] = name
            self.assert_rejected(self.run_bootstrap(), "not in allowed")

    def test_invalid_allowlist_fails_closed(self):
        for allowed in ("example-2", [""], [2], None):
            with self.subTest(allowed=allowed):
                self.config["allowed_subscriptions"] = allowed
                self.assert_rejected(self.run_bootstrap(), "allowed_subscriptions")

    def test_tilde_index_and_both_config_overrides_expand(self):
        self.index = self.home / "team's index.json"
        self.config["config_dir"] = "~/custom azure"
        self.config["azd_config_dir"] = "~/custom azd"
        result = self.run_bootstrap(extra_env={"AZURE_TENANT_INDEX": "~/team's index.json"})
        self.assert_accepted(result)
        self.assertIn(f"CHILD={self.home}/custom azure|{self.home}/custom azd", result.stdout)

    def test_null_and_missing_paths_are_inherited_by_child(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    self.config.pop("config_dir")
                    self.config.pop("azd_config_dir")
                result = self.run_bootstrap(alias_argument=False)
                self.assert_accepted(result)
                self.assertIn(
                    f"CHILD={self.home}/.azure-tenants/example|{self.home}/.azd-tenants/example",
                    result.stdout,
                )

    def test_explicit_guid_assertion_still_rejects_another_allowed_target(self):
        self.config["allowed_subscriptions"] = [SUB_ID, OTHER_ID]
        assertion = (
            'test "$(az account show --query id -o tsv)" = "$EXPECTED_SUB_ID" '
            '|| { echo "Explicit target mismatch" >&2; exit 1; }'
        )
        self.assert_accepted(self.run_bootstrap(extra_env={"EXPECTED_SUB_ID": SUB_ID}, after=assertion))
        result = self.run_bootstrap(extra_env={"EXPECTED_SUB_ID": OTHER_ID}, after=assertion)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Explicit target mismatch", result.stderr)
        self.assertNotIn("CHILD=", result.stdout)

    def run_live_fixture_with_stubs(self, *, missing_dir=False, wrong_target=False):
        self.index.write_text(json.dumps({"tenants": {self.alias: self.config}}))
        azure = self.home / ".azure-tenants" / self.alias
        azd = self.home / ".azd-tenants" / self.alias
        azure.mkdir(parents=True)
        if not missing_dir:
            azd.mkdir(parents=True)
        environment = {
            "HOME": str(self.home), "PATH": str(self.bin),
            "AZURE_TENANT_INDEX": str(self.index),
            "AZURE_CONFIG_DIR": str(azure), "AZD_CONFIG_DIR": str(azd),
            "STUB_ACCOUNT": json.dumps(self.account), "STUB_LOG": str(self.log),
            "STUB_ALLOW_GROUP": "1",
        }
        return subprocess.run(
            [sys.executable, str(LIVE_FIXTURE), "--alias", self.alias,
             "--tenant-id", TENANT, "--subscription-id", OTHER_ID if wrong_target else SUB_ID,
             "--subscription-name", self.account["name"], "--resource-group", "example-rg",
             "--evidence-dir", str(self.root)],
            env=environment, cwd=self.home, capture_output=True, text=True, timeout=15,
        )

    def test_manual_fixture_reads_once_and_separates_evidence(self):
        result = self.run_live_fixture_with_stubs()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"], "PASS")
        self.assertNotIn(TENANT, result.stdout)
        self.assertNotIn(SUB_ID, result.stdout)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([call["args"][:2] for call in calls],
                         [["account", "show"]] * 3 + [["group", "show"]])
        private = self.root / "tenant-isolation-private.json"
        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(private.read_text())["target"]["subscription_id"], SUB_ID)

    def test_manual_fixture_missing_dir_stops_before_cli(self):
        result = self.run_live_fixture_with_stubs(missing_dir=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.home / ".azd-tenants" / self.alias).exists())

    def test_manual_fixture_wrong_target_stops_before_group_read(self):
        result = self.run_live_fixture_with_stubs(wrong_target=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["result"], "FAIL")
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(all(call["args"][:2] == ["account", "show"] for call in calls))


if __name__ == "__main__":
    unittest.main()

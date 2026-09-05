"""Task 3 workflow and pinned age installer contracts (offline only)."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import unittest
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/skill-test.yml"
FIXTURE = ROOT / "skills/foundry-agentops/test-fixture/consumer_prompt.md"
RUNBOOK = ROOT / "skills/foundry-agentops/references/day2-runbook.md"
README = ROOT / "README.md"
INSTALLER = ROOT / "scripts/setup-agentops-age.sh"
REPORTER = ROOT / "scripts/agentops-ci-report.py"
DIAGNOSTIC = ROOT / "scripts/agentops-ci-diagnostic.py"


class AgentOpsTask3WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow_text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.workflow_text)
        cls.build = cls.workflow["jobs"]["build-matrix"]
        cls.unit_steps = cls.workflow["jobs"]["unit-tests"]["steps"]
        cls.steps = cls.workflow["jobs"]["copilot-cli-matrix"]["steps"]
        cls.primary = next(step for step in cls.steps if step.get("id") == "run")
        cls.retry = next(
            step for step in cls.steps
            if step.get("name") == "Retry once on classified-transient failure"
        )

    def step(self, name: str) -> dict:
        return next(step for step in self.steps if step.get("name") == name)

    def test_pull_request_has_no_label_trigger(self) -> None:
        pull_request = self.workflow[True]["pull_request"]
        self.assertIsInstance(pull_request, dict)
        self.assertNotIn("types", pull_request)
        self.assertIn("scripts/setup-agentops-age.sh", pull_request["paths"])

    def test_build_job_selects_only_agentops_for_approved_diagnostic(self) -> None:
        self.assertEqual(
            self.build["outputs"]["agentops_diagnostic"],
            "${{ steps.build.outputs.agentops_diagnostic }}",
        )
        build = next(step for step in self.build["steps"] if step.get("id") == "build")
        self.assertEqual(
            build["env"]["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"],
            "${{ secrets.AGENTOPS_CI_TELEMETRY_APPROVAL_JSON }}",
        )
        script = build["run"]
        self.assertIn("python3 -I scripts/build-test-matrix.py --agentops-diagnostic-mode", script)
        self.assertIn('MATRIX=\'{"skill":["foundry-agentops"]}\'', script)
        self.assertIn('echo "agentops_diagnostic=$DIAGNOSTIC"', script)
        self.assertIn("--changed-only", script)
        self.assertIn("python3 -I scripts/build-test-matrix.py --repo-root .", script)
        self.assertLess(script.index("--agentops-diagnostic-mode"), script.index("--changed-only"))

    def test_age_installed_for_units_and_only_diagnostic_runtime(self) -> None:
        unit = next(
            step for step in self.unit_steps
            if step.get("name") == "Install pinned age for AgentOps unit tests"
        )
        self.assertIn("scripts/setup-agentops-age.sh", unit["run"])
        self.assertIn("$GITHUB_PATH", unit["run"])

        runtime = self.step("Install pinned age for AgentOps diagnostic")
        self.assertEqual(
            runtime["if"],
            "matrix.skill == 'foundry-agentops' && needs.build-matrix.outputs.agentops_diagnostic == 'true'",
        )
        self.assertIn('"$AGENTOPS_CI_ROOT/tools"', runtime["run"])
        self.assertIn('>> "$GITHUB_ENV"', runtime["run"])

    def test_host_check_is_after_preflight_and_before_paid_process(self) -> None:
        preflight = self.step("Validate dedicated AgentOps CI authorization")
        check = self.step("Validate encrypted AgentOps diagnostic transport")
        self.assertLess(self.steps.index(preflight), self.steps.index(check))
        self.assertLess(self.steps.index(check), self.steps.index(self.primary))
        self.assertEqual(
            check["if"],
            "matrix.skill == 'foundry-agentops' && needs.build-matrix.outputs.agentops_diagnostic == 'true'",
        )
        self.assertIn("scripts/agentops-ci-diagnostic.py check", check["run"])
        self.assertEqual(
            check["env"]["AGENTOPS_CI_TELEMETRY_APPROVAL_JSON"],
            "${{ secrets.AGENTOPS_CI_TELEMETRY_APPROVAL_JSON }}",
        )

    def test_trusted_host_python_invocations_are_isolated(self) -> None:
        required = (
            "python3 -I scripts/build-test-matrix.py --agentops-diagnostic-mode",
            "python3 -I scripts/agentops-ci-report.py init",
            "python3 -I scripts/agentops-ci-preflight.py --write-approval",
            "python3 -I scripts/agentops-ci-diagnostic.py check",
            "python3 -I scripts/agentops-ci-report.py prepare primary",
            "python3 -I scripts/agentops-ci-preflight.py --approval-file",
            "python3 -I scripts/agentops-ci-report.py report primary",
            "python3 -I scripts/agentops-ci-diagnostic.py export",
            'python3 -I - cleanup',
        )
        for command in required:
            with self.subTest(command=command):
                self.assertIn(command, self.workflow_text)

    def test_exact_host_command_ignores_untracked_stdlib_shadows(self) -> None:
        scratch = ROOT / ".artifacts"
        scratch.mkdir(exist_ok=True)
        workspace = scratch / ("agentops-python-isolated-" + uuid.uuid4().hex)
        scripts = workspace / "scripts"
        scripts.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, workspace)
        shutil.copyfile(REPORTER, scripts / REPORTER.name)
        canary = workspace / "shadow-imported"
        shadow = (
            "import os\n"
            "open(os.environ['SHADOW_CANARY'], 'w').write(__file__)\n"
            "raise RuntimeError('untracked shadow imported')\n"
        )
        for name in ("hashlib.py", "json.py"):
            (scripts / name).write_text(shadow, encoding="utf-8")
        runner = workspace / "runner"
        runner.mkdir(mode=0o700)
        env = {
            "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            "RUNNER_TEMP": str(runner),
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1",
            "SHADOW_CANARY": str(canary),
        }

        result = subprocess.run(
            ["bash", "-c", "python3 -I scripts/agentops-ci-report.py init"],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(canary.exists(), "isolated host command imported an untracked shadow")

    def test_paid_process_gets_indicator_but_never_canonical_approval(self) -> None:
        self.assertEqual(
            self.primary["env"]["AGENTOPS_CI_DIAGNOSTIC_MODE"],
            "${{ needs.build-matrix.outputs.agentops_diagnostic == 'true' && 'doctor-encrypted' || '' }}",
        )
        for step in (self.primary, self.retry):
            self.assertNotIn("AGENTOPS_CI_TELEMETRY_APPROVAL_JSON", step["env"])
            self.assertNotIn("secrets.AGENTOPS_CI_TELEMETRY_APPROVAL_JSON", step["run"])

    def test_diagnostic_disables_agentops_retry_only(self) -> None:
        self.assertEqual(
            self.retry["if"],
            "steps.run.outcome == 'failure' && (matrix.skill != 'foundry-agentops' || needs.build-matrix.outputs.agentops_diagnostic != 'true')",
        )

    def test_export_and_fixed_upload_precede_unconditional_cleanup(self) -> None:
        export = self.step("Export encrypted AgentOps diagnostic")
        upload = self.step("Upload encrypted AgentOps diagnostic")
        outcome = self.step("Enforce AgentOps diagnostic execution outcome")
        cleanup = self.step("Remove private AgentOps runner files")
        self.assertLess(self.steps.index(self.primary), self.steps.index(export))
        self.assertLess(self.steps.index(export), self.steps.index(upload))
        self.assertLess(self.steps.index(upload), self.steps.index(outcome))
        self.assertLess(self.steps.index(outcome), self.steps.index(cleanup))
        self.assertIn("steps.run.outputs.agentops_summary == 'verified'", export["if"])
        self.assertIn("scripts/agentops-ci-diagnostic.py export", export["run"])
        self.assertIn('echo "diagnostic_ready=true"', export["run"])
        self.assertIn("steps.agentops-diagnostic-export.outputs.diagnostic_ready == 'true'", upload["if"])
        self.assertEqual(upload["with"]["retention-days"], 1)
        self.assertEqual(
            upload["with"]["path"],
            "${{ runner.temp }}/agentops-ci-public-${{ github.run_id }}-${{ github.run_attempt }}/doctor-log.age\n"
            "${{ runner.temp }}/agentops-ci-public-${{ github.run_id }}-${{ github.run_attempt }}/diagnostic.json\n",
        )
        self.assertNotIn("*", upload["with"]["path"])
        self.assertIn("${{ github.run_id }}", upload["with"]["name"])
        self.assertEqual(cleanup["if"], "always() && matrix.skill == 'foundry-agentops'")

    def test_export_rechecks_fixed_tracked_sources_before_secret_bearing_python(self) -> None:
        export = self.step("Export encrypted AgentOps diagnostic")
        script = export["run"]
        for source in (
            "scripts/agentops-ci-diagnostic.py",
            "scripts/agentops-ci-preflight.py",
            "scripts/agentops-ci-report.py",
        ):
            self.assertIn(source, script)
        self.assertIn("GIT_NO_REPLACE_OBJECTS=1", script)
        self.assertIn('show "$GITHUB_SHA:$source"', script)
        self.assertLess(
            script.index('show "$GITHUB_SHA:$source"'),
            script.index("python3 -I scripts/agentops-ci-diagnostic.py export"),
        )
        diagnostic = DIAGNOSTIC.read_text(encoding="utf-8")
        self.assertIn('Path(__file__).resolve().with_name(filename)', diagnostic)
        self.assertIn('_load_sibling("agentops-ci-preflight.py"', diagnostic)
        self.assertIn('_load_sibling("agentops-ci-report.py"', diagnostic)

    def test_diagnostic_paid_process_group_is_bounded_and_preserves_status(self) -> None:
        script = self.primary["run"]
        begin = "# BEGIN AgentOps diagnostic process supervision"
        end = "# END AgentOps diagnostic process supervision"
        self.assertEqual(script.count(begin), 1)
        self.assertEqual(script.count(end), 1)
        supervision = script.split(begin, 1)[1].split(end, 1)[0]
        self.assertIn("setsid", supervision)
        self.assertIn("kill -TERM --", supervision)
        self.assertIn("kill -KILL --", supervision)
        self.assertNotIn("pkill", supervision)
        self.assertNotIn("killall", supervision)
        diagnostic_gate = (
            'if [ "$AGENTOPS_CI_DIAGNOSTIC_MODE" = "doctor-encrypted" ]; then'
        )
        supervised_call = 'run_agentops_copilot_group "$TRANSCRIPT"'
        self.assertIn(diagnostic_gate, script)
        self.assertEqual(script.count(supervised_call), 1)
        self.assertLess(script.index(diagnostic_gate), script.index(supervised_call))
        self.assertLess(
            script.index(supervised_call),
            script.index('assert_tracked_checkout_clean "after Copilot"'),
        )

        scratch = ROOT / ".artifacts"
        scratch.mkdir(exist_ok=True)
        workspace = scratch / ("agentops-process-group-" + uuid.uuid4().hex)
        workspace.mkdir(mode=0o700)
        self.addCleanup(shutil.rmtree, workspace)
        setsid = workspace / "setsid"
        setsid.write_text(
            f"#!{sys.executable}\n"
            "import os, sys\n"
            "os.setsid()\n"
            "os.execvp(sys.argv[1], sys.argv[1:])\n",
            encoding="utf-8",
        )
        setsid.chmod(0o700)
        child = workspace / "child.py"
        child.write_text(
            "import os, pathlib, signal, sys, time\n"
            "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\n"
            "def stopped(_signum, _frame):\n"
            "    pathlib.Path(sys.argv[2]).write_text('TERM')\n"
            "    raise SystemExit(0)\n"
            "signal.signal(signal.SIGTERM, stopped)\n"
            "while True:\n"
            "    time.sleep(0.05)\n",
            encoding="utf-8",
        )
        parent = workspace / "paid-parent.py"
        parent.write_text(
            "import pathlib, subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, sys.argv[1], sys.argv[2], sys.argv[3]])\n"
            "for _ in range(100):\n"
            "    if pathlib.Path(sys.argv[2]).exists():\n"
            "        break\n"
            "    time.sleep(0.01)\n"
            "raise SystemExit(7)\n",
            encoding="utf-8",
        )
        pid_file = workspace / "child.pid"
        term_file = workspace / "child.term"
        log = workspace / "private.log"
        status_file = workspace / "status"
        harness = (
            "set -euo pipefail\n"
            f"{supervision}\n"
            "set +e\n"
            'run_agentops_copilot_group "$LOG" "$PYTHON" "$PARENT" '
            '"$CHILD" "$PID_FILE" "$TERM_FILE"\n'
            "status=$?\n"
            "set -e\n"
            'printf "%s\\n" "$status" > "$STATUS_FILE"\n'
        )
        env = {
            "PATH": str(workspace) + os.pathsep + os.environ["PATH"],
            "PYTHON": sys.executable,
            "PARENT": str(parent),
            "CHILD": str(child),
            "PID_FILE": str(pid_file),
            "TERM_FILE": str(term_file),
            "LOG": str(log),
            "STATUS_FILE": str(status_file),
        }

        result = subprocess.run(
            ["bash", "-c", harness],
            cwd=workspace,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(status_file.read_text().strip(), "7")
        self.assertEqual(term_file.read_text().strip(), "TERM")
        child_pid = int(pid_file.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(child_pid, 0)

    def test_export_host_env_contains_known_redaction_values(self) -> None:
        export = self.step("Export encrypted AgentOps diagnostic")
        for name in (
            "AGENTOPS_CI_TELEMETRY_APPROVAL_JSON",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_APPLICATIONINSIGHTS_CONNECTION_STRING",
            "AGENTOPS_CI_APPLICATIONINSIGHTS_CONNECTION_STRING",
            "GITHUB_TOKEN",
        ):
            self.assertIn(name, export["env"])
        self.assertIn('ACTIONS_ID_TOKEN_REQUEST_TOKEN', export["run"])
        self.assertIn('COPILOT_PROVIDER_BEARER_TOKEN', export["run"])

    def test_native_failure_remains_failed_after_successful_export(self) -> None:
        outcome = self.step("Enforce AgentOps diagnostic execution outcome")
        self.assertEqual(
            outcome["if"],
            "always() && matrix.skill == 'foundry-agentops' && needs.build-matrix.outputs.agentops_diagnostic == 'true'",
        )
        self.assertIn("steps.run.outcome", outcome["run"])
        self.assertIn("exit 1", outcome["run"])

    def test_docs_bound_diagnostic_authorization_transport_and_retention(self) -> None:
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        for required in (
            "strict v2",
            "`agentops-diagnostic`",
            "attempt 1",
            "head SHA",
            "standard `age` 1.3.2",
            "Linux x86_64",
            "helper installer and export runtime are Linux-only",
            "standard age v1 X25519 ciphertext is portable",
            "decrypted locally on macOS",
            "30-day telemetry",
            "1-day ciphertext",
            "operator private key",
            "never enters the runner",
            "plaintext is never public",
            "raw Doctor log",
            "not full 23-fixture acceptance",
            "technical negative path",
            "unknown exception",
            "not a sandbox",
            "same CI identity",
            "background or detached processes",
        ):
            with self.subTest(required=required):
                self.assertIn(required, runbook)
        fixture = " ".join(FIXTURE.read_text(encoding="utf-8").split())
        self.assertIn("background or detached processes", fixture)
        self.assertIn("python3 -I", fixture)
        readme = " ".join(README.read_text(encoding="utf-8").split())
        self.assertIn("owner-authorized encrypted Doctor diagnostic", readme)
        self.assertIn("not full-matrix acceptance", readme)


class AgentOpsDoctorArgvTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = ROOT / ".artifacts"
        scratch.mkdir(exist_ok=True)
        self.workspace = scratch / ("agentops-doctor-argv-" + uuid.uuid4().hex)
        self.workspace.mkdir(mode=0o700)
        self.addCleanup(shutil.rmtree, self.workspace)
        text = FIXTURE.read_text(encoding="utf-8")
        step = text.split("## Step 7", 1)[1].split("\n## Step 8", 1)[0]
        self.block = step.split("```bash\n", 1)[1].split("```", 1)[0]
        self.argv_file = self.workspace / "argv.json"
        self.fake = self.workspace / "agentops"
        self.fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "pathlib.Path(os.environ['ARGV_FILE']).write_text(json.dumps(sys.argv[1:]))\n"
            "print('synthetic private doctor output')\n"
            "raise SystemExit(int(os.environ['FAKE_EXIT']))\n",
            encoding="utf-8",
        )
        self.fake.chmod(0o700)

    def run_block(self, mode: str, exit_code: int) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ["PATH"],
            "AGENTOPS_BIN": str(self.fake),
            "AGENTOPS_CI_DIAGNOSTIC_MODE": mode,
            "ARGV_FILE": str(self.argv_file),
            "FAKE_EXIT": str(exit_code),
        }
        return subprocess.run(
            ["bash", "-c", self.block],
            cwd=self.workspace,
            env=env,
            text=True,
            capture_output=True,
        )

    def test_verbose_is_global_and_only_in_diagnostic_mode(self) -> None:
        result = self.run_block("doctor-encrypted", 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.argv_file.read_text()), ["--verbose", "doctor", "--evidence-pack"])

        result = self.run_block("", 0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(self.argv_file.read_text()), ["doctor", "--evidence-pack"])

    def test_native_exit_one_is_preserved_with_private_log(self) -> None:
        result = self.run_block("doctor-encrypted", 1)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            (self.workspace / ".agentops/agent/doctor-exit-code").read_text().strip(),
            "1",
        )
        self.assertIn(
            "synthetic private doctor output",
            (self.workspace / ".agentops/agent/doctor-command.log").read_text(),
        )


class AgentOpsAgeInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = ROOT / ".artifacts"
        scratch.mkdir(exist_ok=True)
        self.workspace = scratch / ("agentops-age-installer-" + uuid.uuid4().hex)
        self.workspace.mkdir(mode=0o700)
        self.addCleanup(shutil.rmtree, self.workspace)
        self.archive = self.workspace / "fake-age.tar.gz"
        with tarfile.open(self.archive, "w:gz") as bundle:
            for name in ("age", "age-keygen"):
                payload = f"#!/bin/sh\nprintf '{name} fake\\n'\n".encode()
                member = tarfile.TarInfo(f"age/{name}")
                member.mode = 0o755
                member.size = len(payload)
                bundle.addfile(member, io.BytesIO(payload))
        self.archive_hash = hashlib.sha256(self.archive.read_bytes()).hexdigest()

    def invoke(self, expected_hash: str, *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
        destination = self.workspace / "installed"
        shell = """
set -euo pipefail
source "$1"
validate_platform() { :; }
download_archive() { cp "$FAKE_ARCHIVE" "$1"; }
AGE_ARCHIVE_SHA256="$3"
install_age "$4"
"""
        return subprocess.run(
            ["bash", "-c", shell, "installer-test", str(INSTALLER),
             str(self.archive), expected_hash, str(destination)],
            cwd=cwd,
            env={"PATH": os.environ["PATH"], "FAKE_ARCHIVE": str(self.archive)},
            text=True,
            capture_output=True,
        )

    def test_fake_archive_installs_only_age_binaries_with_private_modes(self) -> None:
        for name in ("hashlib.py", "pathlib.py", "tarfile.py"):
            (self.workspace / name).write_text(
                "raise RuntimeError('untrusted installer import')\n", encoding="utf-8"
            )
        result = self.invoke(self.archive_hash, cwd=self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        destination = self.workspace / "installed"
        self.assertEqual(sorted(path.name for path in destination.iterdir()), ["age", "age-keygen"])
        for name in ("age", "age-keygen"):
            path = destination / name
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines())
        self.assertEqual(values["AGENTOPS_CI_AGE_BIN"], str(destination / "age"))
        self.assertEqual(
            values["AGENTOPS_CI_AGE_SHA256"],
            hashlib.sha256((destination / "age").read_bytes()).hexdigest(),
        )

    def test_hash_mismatch_fails_without_installing_binaries(self) -> None:
        result = self.invoke("0" * 64)
        self.assertNotEqual(result.returncode, 0)
        destination = self.workspace / "installed"
        self.assertFalse((destination / "age").exists())
        self.assertFalse((destination / "age-keygen").exists())
        self.assertNotIn("AGENTOPS_CI_AGE_BIN=", result.stdout)

    def test_installer_pins_official_linux_amd64_archive_and_hash(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn(
            "https://github.com/FiloSottile/age/releases/download/v1.3.2/"
            "age-v1.3.2-linux-amd64.tar.gz",
            text,
        )
        self.assertIn(
            "cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10",
            text,
        )
        self.assertNotIn("/latest/", text)


if __name__ == "__main__":
    unittest.main()

"""Driver readiness is not consumer acceptance; probe failures reveal no payloads."""

import importlib.util
from pathlib import Path
import signal
import subprocess
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_driver_probe", ROOT / "scripts/probe-ci-driver.py")
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class DriverProbeTests(unittest.TestCase):
    def run_probe(self, stdout="PONG\n", stderr="", status=0):
        process = Mock(returncode=status, pid=12345)
        process.communicate.return_value = (stdout, stderr)
        with patch.object(PROBE.subprocess, "Popen", return_value=process) as launch:
            result = PROBE.probe()
        return result, process, launch

    def test_exact_response_and_zero_exit_required(self):
        self.assertEqual(self.run_probe()[0], "PASS")
        for text in ("", "PONG\nextra", "I say PONG", "PONG\nPONG"):
            with self.subTest(text=text):
                self.assertEqual(self.run_probe(stdout=text)[0], "FAIL RESPONSE_CONTRACT")
        self.assertEqual(self.run_probe(status=1)[0], "FAIL CLI_RESPONSE")

    def test_fixed_failure_codes_do_not_echo_credentials(self):
        for text, expected in (
            ("Authentication failed HTTP 403 SECRET", "AUTH"),
            ("HTTP 401 SECRET", "AUTH"),
            ("429 SECRET", "THROTTLED"),
            ("Too Many Requests SECRET", "THROTTLED"),
            ("error: unknown option SECRET", "CLI_ARGUMENTS"),
            ("unexpected SECRET", "CLI_RESPONSE"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.run_probe(stderr=text, status=1)[0], f"FAIL {expected}")

    def test_probe_disallows_tools_and_has_finite_deadline(self):
        _, process, launch = self.run_probe()
        self.assertIn("--no-custom-instructions", PROBE.COMMAND)
        self.assertIn("--no-ask-user", PROBE.COMMAND)
        self.assertIn("--disable-builtin-mcps", PROBE.COMMAND)
        self.assertNotIn("--allow-all-tools", PROBE.COMMAND)
        process.communicate.assert_called_once_with(timeout=90)
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        env = launch.call_args.kwargs["env"]
        self.assertEqual(env["COPILOT_PROVIDER_MAX_OUTPUT_TOKENS"], "512")

    def test_missing_cli_fails(self):
        with patch.object(PROBE.subprocess, "Popen", side_effect=FileNotFoundError):
            self.assertEqual(PROBE.probe(), "FAIL CLI_START")

    def test_timeout_terminates_only_owned_process_group(self):
        process = Mock(pid=12345)
        process.communicate.side_effect = [subprocess.TimeoutExpired(PROBE.COMMAND, 90), ("", "")]
        with patch.object(PROBE.subprocess, "Popen", return_value=process), \
                patch.object(PROBE.os, "killpg") as kill:
            self.assertEqual(PROBE.probe(), "FAIL TIMEOUT")
        kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_stubborn_timeout_is_reaped(self):
        process = Mock(pid=12345)
        process.communicate.side_effect = [
            subprocess.TimeoutExpired(PROBE.COMMAND, 90),
            subprocess.TimeoutExpired(PROBE.COMMAND, 5), ("", ""),
        ]
        with patch.object(PROBE.subprocess, "Popen", return_value=process), \
                patch.object(PROBE.os, "killpg") as kill:
            self.assertEqual(PROBE.probe(), "FAIL TIMEOUT")
        self.assertEqual([call.args for call in kill.call_args_list],
                         [(12345, signal.SIGTERM), (12345, signal.SIGKILL)])


if __name__ == "__main__":
    unittest.main()

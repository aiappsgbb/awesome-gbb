"""Unit tests for the foundry-observability Insights monitor teardown helper.

Live create/get/delete is exercised by the foundry-observability
copilot-cli-matrix fixture (Step 1b). These tests pin the teardown order
that prevents a monitor schedule or run from being left behind.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

SKILL_DIR = Path(__file__).resolve().parents[1].parent / "skills" / "foundry-observability" / "references" / "python"
sys.path.insert(0, str(SKILL_DIR))

try:
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError  # noqa: E402
    import insights_monitors  # noqa: E402
except ImportError as exc:
    raise unittest.SkipTest(f"azure-core not installed at unit-test tier: {exc.name}")


def _run(run_id: str, status: str) -> SimpleNamespace:
    return SimpleNamespace(id=run_id, status=status)


class StopAndDeleteMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = MagicMock()
        self.ops.get.side_effect = ResourceNotFoundError("gone")
        patcher = patch.object(insights_monitors.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_disables_before_cancelling_and_deleting(self) -> None:
        self.ops.list_runs.side_effect = [[_run("r1", "in_progress"), _run("r0", "succeeded")], []]
        insights_monitors.stop_and_delete_monitor(self.ops, "m1")
        names = [c[0] for c in self.ops.method_calls]
        self.assertEqual(names[0], "update")
        self.assertEqual(self.ops.update.call_args.kwargs, {"enabled": False})
        self.ops.cancel_run.assert_called_once_with("m1", "r1")
        self.ops.delete.assert_called_once_with("m1")
        self.assertLess(names.index("cancel_run"), names.index("delete"))

    def test_retries_delete_conflict(self) -> None:
        self.ops.list_runs.return_value = []
        self.ops.delete.side_effect = [ResourceExistsError("run started"), None]
        insights_monitors.stop_and_delete_monitor(self.ops, "m1")
        self.assertEqual(self.ops.delete.call_count, 2)

    def test_fails_when_monitor_still_readable(self) -> None:
        self.ops.list_runs.return_value = []
        self.ops.get.side_effect = None
        with self.assertRaises(RuntimeError):
            insights_monitors.stop_and_delete_monitor(self.ops, "m1")

    def test_times_out_when_runs_never_settle(self) -> None:
        self.ops.list_runs.return_value = [_run("r1", "queued")]
        with self.assertRaises(TimeoutError):
            insights_monitors.stop_and_delete_monitor(self.ops, "m1", attempts=3)
        self.ops.delete.assert_not_called()


if __name__ == "__main__":
    unittest.main()

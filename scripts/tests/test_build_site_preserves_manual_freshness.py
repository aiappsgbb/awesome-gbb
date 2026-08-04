"""Regression tests for scripts/build-site.py output preservation."""

from __future__ import annotations

import html
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build-site.py"
REPO_ROOT = Path(__file__).resolve().parents[2]


class BuildSitePreservesMaintenanceDocsTests(unittest.TestCase):
    def test_preserves_manual_skill_freshness_runbook(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as td:
            out_dir = Path(td)
            hand_authored = out_dir / "maintenance" / "manual-skill-freshness.md"
            hand_authored.parent.mkdir(parents=True, exist_ok=True)
            hand_authored.write_text("manual runbook\n", encoding="utf-8")

            subprocess.run(
                [sys.executable, str(SCRIPT), "--out", str(out_dir)],
                cwd=REPO_ROOT,
                check=True,
            )

            self.assertTrue(hand_authored.exists())
            self.assertEqual(hand_authored.read_text(encoding="utf-8"), "manual runbook\n")

    def test_engineering_and_homepage_freshness_sections_stay_truthful(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as td:
            out_dir = Path(td)

            subprocess.run(
                [sys.executable, str(SCRIPT), "--out", str(out_dir)],
                cwd=REPO_ROOT,
                check=True,
            )

            engineering = html.unescape(
                (out_dir / "engineering" / "index.html").read_text(encoding="utf-8")
            )
            home = html.unescape((out_dir / "index.html").read_text(encoding="utf-8"))

            for haystack, expected in (
                (engineering, "weekly cron"),
                (engineering, "auto-tier issues are assigned to @Copilot"),
                (engineering, "auto-PR by Copilot coding agent"),
                (home, "weekly / freshness checks / CI-gated, auto-refresh"),
                (home, "weekly / drift checks / auto-PR by Copilot coding agent"),
            ):
                self.assertNotIn(expected, haystack)

            self.assertIn("Monday 07:00 UTC", engineering)
            self.assertIn("Thursday 07:00 UTC", engineering)
            self.assertIn("FRESHNESS_EXECUTION_MODE", engineering)
            self.assertIn("manual-review", engineering)
            self.assertIn("manual-review or Copilot assignment", engineering)
            self.assertIn("twice weekly", engineering)
            self.assertIn("manual mode", engineering)
            self.assertIn("copilot mode", engineering)
            self.assertIn("in copilot mode", engineering)
            self.assertIn("issue_only stays human-owned", engineering)
            self.assertIn("closed end-to-end in copilot mode", engineering)


if __name__ == "__main__":
    unittest.main()

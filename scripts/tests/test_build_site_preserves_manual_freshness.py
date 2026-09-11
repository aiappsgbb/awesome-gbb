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
    def assert_unambiguous_freshness_routing(self, engineering: str) -> None:
        self.assertIn("manual mode routes auto-tier issues to manual-review", engineering)
        self.assertIn("copilot mode assigns auto-tier issues to Copilot", engineering)

    def test_preserves_manual_skill_freshness_runbook(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as td:
            out_dir = Path(td)
            hand_authored = {
                "maintenance/manual-skill-freshness.md": "manual runbook\n",
                "maintenance/foundry-agentops-validation.md": "existing validation record\n",
                "audit/review.md": "hand-authored review\n",
                "superpowers/plan.md": "hand-authored plan\n",
            }
            for relative_path, content in hand_authored.items():
                path = out_dir / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            subprocess.run(
                [sys.executable, str(SCRIPT), "--out", str(out_dir)],
                cwd=REPO_ROOT,
                check=True,
            )

            for relative_path, content in hand_authored.items():
                with self.subTest(path=relative_path):
                    self.assertEqual(
                        (out_dir / relative_path).read_text(encoding="utf-8"), content
                    )

    def test_fresh_build_copies_only_published_validation_records_and_validates_links(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as td:
            out_dir = Path(td) / "site"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--out", str(out_dir), "--validate"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("0 broken root-relative links", result.stdout)
            records = {
                Path("maintenance/foundry-agentops-validation.md"),
                Path("maintenance/foundry-mcp-auth-validation.md"),
            }
            for record in records:
                self.assertEqual(
                    (out_dir / record).read_bytes(),
                    (REPO_ROOT / "docs" / record).read_bytes(),
                )
            self.assertEqual(
                {path.relative_to(out_dir) for path in (out_dir / "maintenance").rglob("*")
                 if path.is_file()},
                records,
            )
            for directory in ("audit", "superpowers"):
                self.assertFalse((out_dir / directory).exists())

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
            legacy_engineering = (
                "The detector runs twice weekly on Monday and Thursday 07:00 UTC. "
                "Execution mode comes from FRESHNESS_EXECUTION_MODE: manual is the "
                "safe default, while copilot keeps auto-tier routing on manual-review "
                "or Copilot assignment. Manual mode keeps auto-tier issues human-owned "
                "with manual-review; issue_only stays human-owned in every mode. Only "
                "copilot mode closes the delivery loop end-to-end by opening refresh PRs "
                "and running auto-merge in copilot mode."
            )

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
            self.assertIn("twice weekly", engineering)
            self.assertIn("manual mode", engineering)
            self.assertIn("copilot mode", engineering)
            self.assertIn("in copilot mode", engineering)
            self.assertIn("issue_only stays human-owned", engineering)
            self.assertIn("closed end-to-end in copilot mode", engineering)
            self.assert_unambiguous_freshness_routing(engineering)

            with self.assertRaises(AssertionError):
                self.assert_unambiguous_freshness_routing(legacy_engineering)


if __name__ == "__main__":
    unittest.main()

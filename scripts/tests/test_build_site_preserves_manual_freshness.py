"""Regression tests for scripts/build-site.py output preservation."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()

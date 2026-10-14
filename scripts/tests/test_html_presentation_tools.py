"""Run the canonical stdlib tooling suite in an isolated module namespace."""

from pathlib import Path
import subprocess
import sys
import unittest


class HtmlPresentationToolsTests(unittest.TestCase):
    def test_canonical_tool_suite(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s",
             "skills/html-presentation/scripts", "-p", "test_*.py"],
            cwd=root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Ran 15 tests", result.stderr)

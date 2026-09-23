"""Regression checks for the historical-document redaction subset."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PublicContentRedactionTests(unittest.TestCase):
    def test_historical_docs_have_no_personal_home_or_session_ids(self):
        paths = [
            ROOT / "AGENTS.md",
            *(ROOT / "docs/audit").glob("*.md"),
            *(ROOT / "docs/superpowers").rglob("*.md"),
        ]
        uuid = r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text()
                self.assertNotRegex(text, r"/Users/[A-Za-z0-9_.-]+/")
                self.assertNotRegex(text, rf"session-state/{uuid}")
                self.assertNotRegex(
                    text, rf"(?:project session|project_session_id)\s+`{uuid}`"
                )

    def test_documented_project_identity_is_a_placeholder(self):
        text = (ROOT / "AGENTS.md").read_text()
        self.assertIn('PROJECT_MI_OBJECT_ID="<project-mi-object-id>"', text)
        text = (
            ROOT / "docs/audit/foundry-hosted-agents-audit-trail.md"
        ).read_text()
        self.assertIn('PROJ_MI="<project-mi-object-id>"', text)
        self.assertIn("principalId=<project-mi-object-id>", text)


if __name__ == "__main__":
    unittest.main()

"""Navigation linkification must not hide operational changes from live CI."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("navigation_matrix", ROOT / "scripts/build-test-matrix.py")
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)
URL = "https://github.com/microsoft/azure-skills/blob/main/skills/official/references/memory.md"
LINK = f"[`memory`]({URL})"
FRONT = "---\nname: alpha\ndescription: An existing skill.\nmetadata:\n  version: '1.0.0'\n---\n"


class NavigationClassificationTests(unittest.TestCase):
    def test_quote_and_related_table_linkification(self):
        for body in (
            "> See `memory` for details.\n",
            ">   (`memory`) for details.\n",
            "### Related skills\n| Memory | `memory` |\n",
            "## 10 · Cross-skill references\n| Need | `memory` |\n",
            "## See Also\n| Need | `memory` |\n",
        ):
            with self.subTest(body=body):
                self.assertTrue(MATRIX._linkified_navigation_only(
                    body, body.replace("`memory`", LINK), {"memory"}
                ))

    def test_operational_prose_labels_targets_and_code_stay_live(self):
        cases = [
            ("Run `memory` before deploying.\n", f"Run {LINK} before deploying.\n"),
            ("> See `memory`.\n", f"> Always deploy through {LINK}.\n"),
            ("> See `memory`.\n", f"> See [Memory]({URL}).\n"),
            (f"> See {LINK}.\n", f"> See [`memory`]({URL.replace('memory.md', 'other.md')}).\n"),
            ("## Deploy\n| Command | `memory` |\n", f"## Deploy\n| Command | {LINK} |\n"),
            ("## Related skills\n| Memory | `unknown` |\n", f"## Related skills\n| Memory | [`unknown`]({URL}) |\n"),
            ("    > See `memory`.\n", f"    > See {LINK}.\n"),
            (">     See `memory`.\n", f">     See {LINK}.\n"),
            ("> See `memory`.\n", "> See [`memory`](https://example.com/deploy.sh).\n"),
        ]
        for before, after in cases:
            with self.subTest(after=after):
                self.assertFalse(MATRIX._linkified_navigation_only(before, after, {"memory"}))

    def test_fenced_code_including_quotes_stays_live(self):
        for opening, closing in (("```bash", "```"), ("~~~sh", "~~~"),
                                 ("> ```bash", "> ```"), ("> > ~~~", "> > ~~~")):
            body = f"{opening}\n> See `memory`.\n{closing}\n"
            with self.subTest(opening=opening):
                self.assertFalse(MATRIX._linkified_navigation_only(
                    body, body.replace("`memory`", LINK), {"memory"}
                ))

    def test_unclosed_fence_and_new_code_are_not_editorial(self):
        self.assertFalse(MATRIX._linkified_navigation_only(
            "> See `memory`.\n```\n", f"> See {LINK}.\n```\n", {"memory"}
        ))
        self.assertFalse(MATRIX._linkified_navigation_only(
            "> See `memory`.\n", f"> See {LINK}.\nazd up\n", {"memory"}
        ))
        body = "```text\n```not-a-closing-fence\n> See `memory`.\n```\n"
        self.assertFalse(MATRIX._linkified_navigation_only(
            body, body.replace("`memory`", LINK), {"memory"}
        ))
        body = "<pre>\n> See `memory`.\n</pre>\n"
        self.assertFalse(MATRIX._linkified_navigation_only(
            body, body.replace("`memory`", LINK), {"memory"}
        ))

    def test_heading_inside_code_cannot_open_navigation_scope(self):
        body = "```\n## Related skills\n```\n| Need | `memory` |\n"
        self.assertFalse(MATRIX._linkified_navigation_only(
            body, body.replace("`memory`", LINK), {"memory"}
        ))

    def test_unchanged_html_literal_inside_code_does_not_mask_navigation(self):
        body = '```python\npattern = "<style[^>]*>.*?</style>"\n```\n> See `memory`.\n'
        self.assertTrue(MATRIX._linkified_navigation_only(
            body, body.replace("`memory`", LINK), {"memory"}
        ))

    def test_existing_links_remain_byte_identical(self):
        body = f"> Existing {LINK}.\n> Another `memory`.\n"
        # Conservative when an identical link already exists: do not guess which
        # occurrence was added or reinterpret existing linked instructions.
        self.assertFalse(MATRIX._linkified_navigation_only(
            body, body.replace("Another `memory`", f"Another {LINK}"), {"memory"}
        ))

    def test_git_selection_preserves_runtime_and_fixture_fanout(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            def git(*args):
                return subprocess.check_output(["git", "-C", directory, *args], text=True).strip()

            def write(relative, text):
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)

            git("init", "-q")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            for name in ("alpha", "beta", "memory"):
                write(f"skills/{name}/test-fixture/consumer_prompt.md", "Run existing smoke.\n")
            body = "> See `memory` for details.\n\n## Run\n```bash\nazd deploy\n```\n"
            write("skills/alpha/SKILL.md", FRONT + body)
            write(".github/skill-deps.yml", "skills:\n  alpha:\n    depends_on: []\n  beta:\n    depends_on: [alpha]\n  memory:\n    depends_on: []\n")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            after = (FRONT + body).replace("'1.0.0'", "'1.0.1'").replace("`memory`", LINK)
            write("skills/alpha/SKILL.md", after)
            (repo / "skills/memory/test-fixture/consumer_prompt.md").unlink()
            write(".github/skill-deps.yml", "skills:\n  alpha:\n    depends_on: []\n  beta:\n    depends_on: [alpha]\n")
            git("add", "-A")
            git("commit", "-qm", "retire memory and link replacement")
            self.assertEqual(MATRIX._skill_change_kind(repo, base, "skills/alpha/SKILL.md"), "local")
            self.assertEqual(MATRIX.build(repo, changed_only=True, base_ref=base), {"skill": []})
            self.assertEqual(MATRIX.build(repo), {"skill": ["alpha", "beta"]})
            for path in ("references/run.py", "templates/main.bicep", "requirements.txt"):
                self.assertEqual(MATRIX._skill_change_kind(repo, base, f"skills/alpha/{path}"), "operational")
            self.assertEqual(MATRIX._skill_change_kind(repo, base, "skills/alpha/test-fixture/probe.py"), "fixture")
            write("skills/alpha/SKILL.md", after.replace("azd deploy", "azd up"))
            git("add", ".")
            git("commit", "-qm", "change command")
            self.assertEqual(MATRIX.build(repo, changed_only=True, base_ref=base), {"skill": ["alpha", "beta"]})

    def test_metadata_and_parse_failure_stay_operational(self):
        base = FRONT + "> See `memory`.\n"
        for after in (
            base.replace("name: alpha", "name: renamed").replace("`memory`", LINK),
            base.replace("metadata:", "extra: value\nmetadata:").replace("`memory`", LINK),
            "not frontmatter\n" + LINK,
        ):
            with self.subTest(after=after), patch.object(
                MATRIX.subprocess, "check_output", side_effect=[base, after, "memory\n"]
            ):
                self.assertFalse(MATRIX._local_only_skill_markdown(ROOT, "base", "skills/alpha/SKILL.md"))
        with patch.object(MATRIX.subprocess, "check_output", side_effect=OSError("unavailable")):
            self.assertFalse(MATRIX._local_only_skill_markdown(ROOT, "base", "skills/alpha/SKILL.md"))


if __name__ == "__main__":
    unittest.main()

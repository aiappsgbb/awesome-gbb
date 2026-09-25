"""Verify the canonical source accepts the frozen provider's context argument."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "references"))
from foundry_skills_source import FoundrySkillsSource
from agent_framework import SkillsSourceContext


class ProviderContextTests(unittest.TestCase):
    def test_provider_context_and_original_no_argument_call(self):
        source = FoundrySkillsSource("https://example.test/project", object(), skill_versions={})
        context = SkillsSourceContext(agent=object())
        with patch.object(source, "_collect", return_value=[]) as collect:
            self.assertEqual(asyncio.run(source.get_skills(context)), [])
            self.assertEqual(asyncio.run(source.get_skills()), [])
        self.assertEqual(collect.call_count, 2)


if __name__ == "__main__":
    unittest.main()

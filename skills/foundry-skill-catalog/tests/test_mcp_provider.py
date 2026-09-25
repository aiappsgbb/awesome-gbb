"""Keep native source composition and approval boundaries explicit."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "references"))
import mcp_skills_provider


class MCPProviderTests(unittest.TestCase):
    def test_loading_requires_approval_by_default(self):
        session = Mock()
        with patch.object(mcp_skills_provider, "MCPSkillsSource") as source:
            with patch.object(mcp_skills_provider, "SkillsProvider") as provider:
                result = mcp_skills_provider.toolbox_skills_provider(session)
        source.assert_called_once_with(client=session)
        provider.assert_called_once_with(source.return_value, disable_load_skill_approval=False)
        self.assertIs(result, provider.return_value)

    def test_trusted_loading_does_not_disable_resource_or_script_approval(self):
        with patch.object(mcp_skills_provider, "MCPSkillsSource") as source:
            with patch.object(mcp_skills_provider, "SkillsProvider") as provider:
                mcp_skills_provider.toolbox_skills_provider(Mock(), trusted_skill_loading=True)
        provider.assert_called_once_with(source.return_value, disable_load_skill_approval=True)

    def test_string_false_cannot_disable_approval(self):
        with self.assertRaises(TypeError):
            mcp_skills_provider.toolbox_skills_provider(Mock(), trusted_skill_loading="false")


if __name__ == "__main__":
    unittest.main()

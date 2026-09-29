"""Execute documented tool constructors against the exact SDK 2.4 exports."""

import ast
import re
import unittest
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from azure.ai.projects import models


SKILL = Path(__file__).resolve().parents[1]
BODY = (SKILL / "SKILL.md").read_text(encoding="utf-8")


def execute_example(heading, next_heading):
    section = BODY.split(heading + "\n", 1)[1].split(next_heading + "\n", 1)[0]
    code = re.search(r"```python\n(.*?)```", section, re.S).group(1)
    namespace = {}
    exec(compile(code, "<documented tool constructor>", "exec"), namespace)
    return namespace["definition"].as_dict()["tools"][0]


class ToolModelTests(unittest.TestCase):
    def test_exact_declared_sdk(self):
        self.assertEqual(version("azure-ai-projects"), "2.4.0")

    def test_fabric_wire_shape(self):
        self.assertEqual(
            execute_example("#### FabricIQTool", "#### WorkIQTool"),
            {
                "type": "fabric_iq_preview",
                "project_connection_id": "<fabric-connection-id>",
                "require_approval": "always",
            },
        )

    def test_work_wire_shape(self):
        self.assertEqual(
            execute_example("#### WorkIQTool", "#### ToolSearchTool"),
            {"type": "work_iq_preview", "project_connection_id": "<work-iq-connection-id>"},
        )

    def test_browser_wire_shape(self):
        self.assertEqual(
            execute_example("#### BrowserAutomationTool", "## 3 · Chat with the agent"),
            {
                "type": "browser_automation_preview",
                "browser_automation_preview": {
                    "connection": {"project_connection_id": "<browser-connection-id>"}
                },
            },
        )

    def test_search_uses_resolved_connection(self):
        guide = (SKILL / "references/tool-prerequisites.md").read_text(encoding="utf-8")
        code = re.search(r"```python\n(.*?)```", guide, re.S).group(1)
        project = SimpleNamespace(connections=Mock())
        project.connections.get.return_value = SimpleNamespace(id="resolved-connection")
        namespace = {"project": project}
        exec(compile(code, "<documented search constructor>", "exec"), namespace)
        project.connections.get.assert_called_once_with("search-connection")
        self.assertEqual(
            namespace["search_tool"].as_dict(),
            {
                "type": "azure_ai_search",
                "azure_ai_search": {
                    "indexes": [
                        {"project_connection_id": "resolved-connection", "index_name": "documents"}
                    ]
                },
            },
        )

    def test_all_documented_model_imports_exist(self):
        for code in re.findall(r"```python\n(.*?)```", BODY, re.S):
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.ImportFrom) and node.module == "azure.ai.projects.models":
                    for name in node.names:
                        with self.subTest(model=name.name):
                            self.assertTrue(hasattr(models, name.name), name.name)

    def test_invalid_historical_names_have_no_alias(self):
        for name in ("FabricIQTool", "WorkIQTool", "GuardrailTool", "BrowserAutomationTool"):
            self.assertFalse(hasattr(models, name))

    def test_structured_inputs_survive_serialization(self):
        definition = models.PromptAgentDefinition(
            model="test-model",
            tools=[models.FileSearchTool(vector_store_ids=["{{customer_kb}}"])],
            structured_inputs={
                "customer_kb": {
                    "description": "Approved vector store",
                    "required": True,
                    "schema": {"type": "string"},
                }
            },
        ).as_dict()
        self.assertEqual(definition["tools"][0]["vector_store_ids"], ["{{customer_kb}}"])
        self.assertTrue(definition["structured_inputs"]["customer_kb"]["required"])


if __name__ == "__main__":
    unittest.main()

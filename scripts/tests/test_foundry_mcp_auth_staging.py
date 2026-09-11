"""The Hosted extension requires sources inside its project, never '..' paths."""

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/foundry-mcp-auth"


class HostedStagingTests(unittest.TestCase):
    def test_stage_contains_only_canonical_build_inputs_and_local_paths(self):
        path = SKILL / "references/python/stage_hosted.py"
        self.assertTrue(path.is_file(), "Canonical Hosted staging helper is missing")
        spec = importlib.util.spec_from_file_location("auth_stage", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "hosted"
            module.stage_hosted(destination)
            self.assertIn("project: app", (destination / "azure.yaml").read_text())
            self.assertEqual(
                (destination / "app/references/python/hosted_agent.py").read_bytes(),
                (SKILL / "references/python/hosted_agent.py").read_bytes(),
            )
            self.assertEqual(
                (destination / "app/templates/hosted/Dockerfile").read_bytes(),
                (SKILL / "templates/hosted/Dockerfile").read_bytes(),
            )
            self.assertEqual(
                (destination / "app/references/python/agent_instructions.py").read_bytes(),
                (SKILL / "references/python/agent_instructions.py").read_bytes(),
            )
            with self.assertRaises(FileExistsError):
                module.stage_hosted(destination)


if __name__ == "__main__":
    unittest.main()

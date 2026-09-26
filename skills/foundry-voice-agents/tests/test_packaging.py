import importlib.util
from importlib import metadata
from pathlib import Path
import re
import socket
import sys
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "references/python"))
from definition import build_definition


class PackagingTests(unittest.TestCase):
    def test_manifests_match_installed_versions_and_pin(self):
        requirements = (ROOT / "requirements.txt").read_text()
        pins = yaml.safe_load((ROOT / "references/upstream-pin.md").read_text().split("---", 2)[1])
        constraints = {}
        for line in (ROOT / "constraints.txt").read_text().splitlines():
            name, version = line.split("==")
            constraints[name.lower().replace("_", "-")] = version
            self.assertEqual(metadata.version(name), version)
        for package in pins["packages"]:
            self.assertEqual(metadata.version(package["name"]), package["version"])
            self.assertEqual(constraints[package["name"]], package["version"])
        self.assertIn("azure-ai-projects[voice]==2.7.0", requirements)
        self.assertNotIn("agent-framework", requirements)
        self.assertEqual(metadata.version("PyYAML"), "6.0.3")

    def test_azd_fragment_matches_sdk_model_and_storage(self):
        fragment = yaml.safe_load((ROOT / "references/voice-service.yaml").read_text())
        definition = build_definition(fragment["model"]["id"], model_type=fragment["modelType"])
        self.assertEqual(fragment["host"], "azure.ai.agent")
        self.assertEqual(fragment["kind"], "prompt-voice")
        self.assertEqual(definition.kind, "voice")
        self.assertEqual(fragment["store"], definition.store)
        self.assertNotIn("telephony", fragment)

    def test_local_markdown_links_resolve(self):
        skill = ROOT / "SKILL.md"
        for link in re.findall(r"\]\(([^)]+)\)", skill.read_text()):
            if not link.startswith("https://"):
                self.assertTrue((skill.parent / link.split("#")[0]).exists(), link)

    def test_existing_catalog_t0_functions_for_owned_tree(self):
        spec = importlib.util.spec_from_file_location("validate_voice_candidate", REPO / "scripts/validate-skills.py")
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        errors = validator.validate_skill_md(ROOT / "SKILL.md")
        errors += validator.validate_pin_file(ROOT / "references/upstream-pin.md")
        # Restrict whole-tree validators to the owned draft, not existing skills.
        with patch.object(validator, "SKILLS_DIR", ROOT.parent):
            original_iterdir = Path.iterdir
            def only_owned(path):
                return iter([ROOT]) if path == ROOT.parent else original_iterdir(path)
            with patch.object(Path, "iterdir", only_owned):
                errors += validator.validate_reference_section_anchors()
        self.assertEqual(errors, [])

    def test_cli_render_does_not_create_credentials_or_network(self):
        spec = importlib.util.spec_from_file_location("voice_main", ROOT / "references/python/main.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(sys, "argv", ["main.py", "definition", "--model", "gpt-realtime"]), \
             patch.object(module, "AzureCliCredential", side_effect=AssertionError("credential forbidden")), \
             patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")), \
             patch("builtins.print") as output:
            module.main()
        self.assertIn('"store": false', output.call_args.args[0])

    def test_live_cli_refuses_missing_approval_before_credentials(self):
        spec = importlib.util.spec_from_file_location("voice_main", ROOT / "references/python/main.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for arguments in [
            ["create", "--endpoint", "https://example.services.ai.azure.com/api/projects/example",
             "--model", "gpt-realtime"],
            ["talk", "--endpoint", "https://example.services.ai.azure.com/api/projects/example",
             "--name", "agent", "--version", "1", "--input", "does-not-exist.wav"],
        ]:
            with patch.object(sys, "argv", ["main.py", *arguments]), \
                 patch.object(module, "AzureCliCredential", side_effect=AssertionError("credential forbidden")):
                with self.assertRaises(PermissionError):
                    module.main()


if __name__ == "__main__":
    unittest.main()

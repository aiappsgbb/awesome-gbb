"""Exact ownership, image binding and independent deletion readback."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from azure.core.exceptions import ResourceNotFoundError

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_owned", ROOT / "skills/foundry-hosted-agents/test-fixture/owned_resources.py")
owned = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owned)


class HostedFixtureOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.name = "ci-smoke-ha-abcdef12"
        self.owner = {"name": self.name, "registry": "test.azurecr.io",
                      "endpoint": "https://test.services.ai.azure.com/api/projects/ci", "absent_at": 10}
        self.repository = self.name + "/" + self.name + "-environment"
        self.reference = self.repository + ":azd-deploy-123"
        self.version = {"name": self.name, "version": "1", "created_at": 12,
                        "definition": {"container_configuration": {"image": "test.azurecr.io/" + self.reference}}}
        self.created = {"version_fingerprint": owned.version_fingerprint(self.version),
                        "reference": self.reference, "repository": self.repository,
                        "digest": "sha256:" + "a" * 64}
        self.client = Mock()

    def test_image_uses_native_nested_repository_not_agent_name(self):
        self.assertEqual(owned.image_binding(self.version["definition"], "test.azurecr.io", self.name),
                         (self.reference, self.repository))
        for image in ("other.azurecr.io/" + self.reference, "test.azurecr.io/shared:v1",
                      "test.azurecr.io/" + self.name + "-other:v1"):
            with self.subTest(image=image), self.assertRaises(ValueError):
                owned.image_binding({"container_configuration": {"image": image}}, "test.azurecr.io", self.name)

    def test_prepare_rejects_existing_agent_before_any_registry_or_write(self):
        with tempfile.TemporaryDirectory() as work, patch.object(owned, "acr") as acr, self.assertRaises(ValueError):
            owned.prepare(self.client, Path(work) / "state.json", self.name, self.owner["registry"], self.owner["endpoint"])
        acr.assert_not_called()

    def test_prepare_rejects_existing_nested_image_namespace(self):
        self.client.agents.get.side_effect = ResourceNotFoundError("missing")
        with tempfile.TemporaryDirectory() as work, patch.object(owned, "acr", return_value=[self.repository]), self.assertRaises(ValueError):
            owned.prepare(self.client, Path(work) / "state.json", self.name, self.owner["registry"], self.owner["endpoint"])

    def test_record_rejects_native_creation_before_intent(self):
        version = {**self.version, "created_at": 9}
        with tempfile.TemporaryDirectory() as work, patch.object(owned, "get_version", return_value=version), patch.object(owned, "acr") as acr, self.assertRaises(ValueError):
            owned.record(self.client, Path(work) / "created.json", self.owner)
        acr.assert_not_called()

    def test_changed_version_is_not_deleted(self):
        with patch.object(owned, "get_version", return_value={**self.version, "created_at": 13}), self.assertRaises(ValueError):
            owned.cleanup(self.client, self.owner, self.created)
        self.client.agents.delete_version.assert_not_called()
        self.client.agents.delete.assert_not_called()

    def test_added_version_blocks_agent_and_image_cleanup(self):
        self.client.agents.list_versions.return_value = [{"version": "2"}]
        with patch.object(owned, "get_version", side_effect=[self.version, None]), patch.object(owned, "acr") as acr, self.assertRaises(ValueError):
            owned.cleanup(self.client, self.owner, self.created)
        self.client.agents.delete.assert_not_called()
        acr.assert_not_called()

    def test_exact_version_then_agent_then_manifest_with_absence_readbacks(self):
        self.client.agents.list_versions.return_value = []
        self.client.agents.get.side_effect = [Mock(), ResourceNotFoundError("missing")]
        with patch.object(owned, "get_version", side_effect=[self.version, None]), patch.object(
            owned, "acr", side_effect=[[self.repository], [{"digest": self.created["digest"]}], None, []]
        ) as acr:
            owned.cleanup(self.client, self.owner, self.created)
        self.client.agents.delete_version.assert_called_once_with(agent_name=self.name, agent_version="1")
        self.client.agents.delete.assert_called_once_with(agent_name=self.name)
        self.assertEqual(acr.call_args_list[2].args[1],
                         ["repository", "delete", "--image", self.repository + "@" + self.created["digest"], "--yes"])

    def test_changed_registry_contents_preserve_image(self):
        self.client.agents.list_versions.return_value = []
        self.client.agents.get.side_effect = ResourceNotFoundError("missing")
        with patch.object(owned, "get_version", return_value=None), patch.object(
            owned, "acr", side_effect=[[self.repository], [{"digest": self.created["digest"]}, {"digest": "sha256:" + "b" * 64}]]
        ) as acr, self.assertRaises(ValueError):
            owned.cleanup(self.client, self.owner, self.created)
        self.assertEqual(acr.call_count, 2)

"""Producer cleanup only removes verified run-owned app/image objects."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("producer_resources", ROOT / "skills/foundry-mcp-aca/test-fixture/run_resources.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ProducerCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        group = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/ci"
        self.config = {
            "name": "ci-smoke-mcp-abcdef12", "registry": "ciregistry",
            "identity": group + "/providers/Microsoft.ManagedIdentity/userAssignedIdentities/standing",
            "id": group + "/providers/Microsoft.App/containerApps/ci-smoke-mcp-abcdef12",
            "absent_at": "2026-01-01T00:00:00+00:00",
        }
        self.config["url"] = "https://management.azure.com" + self.config["id"] + "?api-version=2025-01-01"
        self.app = {"id": self.config["id"], "systemData": {"createdAt": "2026-01-02T00:00:00Z"},
                    "tags": {"ci-run-id": self.config["name"]},
                    "identity": {"userAssignedIdentities": {self.config["identity"]: {}}}}
        self.image = {"digest": "sha256:" + "a" * 64, "tags": ["run"]}
        self.save()

    def save(self):
        (self.path / "run-owned.json").write_text(json.dumps(self.config))
        (self.path / "run-created.json").write_text(json.dumps({"app": self.app, "image": self.image}))

    def test_shared_scope_or_changed_url_never_reaches_azure(self):
        for key, value in (("id", self.config["identity"]), ("url", "https://management.azure.com/shared"),
                           ("name", "standing-shared-app")):
            original = self.config[key]
            self.config[key] = value
            self.save()
            with self.subTest(key=key), patch.object(module, "cli") as cli, self.assertRaises(ValueError):
                module.cleanup(self.path)
            cli.assert_not_called()
            self.config[key] = original

    def test_replaced_app_is_not_deleted(self):
        changed = copy.deepcopy(self.app)
        changed["systemData"]["createdAt"] = "2026-01-03T00:00:00Z"
        with patch.object(module, "app_read", return_value=changed), patch.object(module, "cli") as cli, self.assertRaises(ValueError):
            module.cleanup(self.path)
        cli.assert_not_called()

    def test_changed_or_shared_image_is_not_deleted(self):
        for image in ({**self.image, "tags": ["run", "shared"]}, {**self.image, "digest": "sha256:" + "b" * 64}):
            with patch.object(module, "app_read", return_value=None), patch.object(module, "image_read", return_value=image), patch.object(module, "cli") as cli, self.assertRaises(ValueError):
                module.cleanup(self.path)
            cli.assert_not_called()

    def test_owned_targets_deleted_and_absence_observed(self):
        with patch.object(module, "app_read", side_effect=[self.app, None]) as apps, patch.object(module, "image_read", side_effect=[self.image, None]) as images, patch.object(module, "cli") as cli:
            module.cleanup(self.path)
        self.assertEqual(apps.call_count, 2)
        self.assertEqual(images.call_count, 2)
        self.assertEqual(cli.call_args_list[0].args[0], ["rest", "--method", "delete", "--url", self.config["url"]])
        self.assertEqual(cli.call_args_list[1].args[0], ["acr", "repository", "delete",
            "--name", self.config["registry"], "--image", self.config["name"] + "@" + self.image["digest"], "--yes"])
        self.assertNotIn("group", cli.call_args_list[0].args[0])

    def test_record_requires_native_creation_and_run_bindings(self):
        for app in ({**self.app, "systemData": {}}, {**self.app, "tags": {}}, {**self.app, "identity": {}}):
            with patch.object(module, "app_read", return_value=app), patch.object(module, "image_read", return_value=self.image), self.assertRaises(ValueError):
                module.record(self.path)

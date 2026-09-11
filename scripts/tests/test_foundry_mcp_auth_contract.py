"""Publication boundaries and complete artifact checks for the local auth candidate."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/foundry-mcp-auth"


class AuthRecipeContractTests(unittest.TestCase):
    def test_hosted_image_preserves_platform_session_storage_identity(self):
        hosted = (SKILL / "templates/hosted/Dockerfile").read_text()
        self.assertFalse(any(line.startswith("USER ") for line in hosted.splitlines()),
                         "A fixed UID cannot write the Foundry-mounted session home")
        server = (SKILL / "templates/Dockerfile").read_text()
        self.assertIn("USER 65532:65532", server, "Do not change the separate ACA server identity")

    def test_skill_has_canonical_local_recipe_and_explicit_release_gates(self):
        self.assertTrue((SKILL / "SKILL.md").is_file(), "Generic auth skill is missing")
        text = (SKILL / "SKILL.md").read_text()
        for phrase in (
            "LOCAL ONLY", "NOT DEMONSTRATED", "Prompt -> direct MCP",
            "Hosted -> Toolbox", "Gate B", "oauth_consent_request",
            "UserEntraToken", "not proof of Entra OBO", "two independent users",
        ):
            self.assertIn(phrase, text)
        for path in (
            "references/python/authorization.py",
            "references/python/delegated_server.py",
            "references/python/configure_foundry.py",
            "references/connection-contract.md",
            "references/yaml/connection.yaml",
            "references/upstream-pin.md",
            "templates/azure.yaml", "templates/infra/main.bicep",
            "templates/Dockerfile", "templates/pyproject.toml",
            "test-fixture/consumer_prompt.md", "test-fixture/playground.md",
        ):
            self.assertTrue((SKILL / path).is_file(), path)

    def test_oauth_definition_uses_env_credentials_not_secret_argv(self):
        path = SKILL / "references/yaml/connection.yaml"
        self.assertTrue(path.is_file(), "Safe OAuth definition is missing")
        text = path.read_text()
        self.assertIn("clientId:", text)
        self.assertIn("${MCP_OAUTH_CLIENT_SECRET}", text)
        self.assertIn("offline_access", text)
        self.assertNotIn("clientID:", text)
        self.assertNotIn("audience:", text)

    def test_noninteractive_fixture_cannot_certify_delegation(self):
        path = SKILL / "test-fixture/consumer_prompt.md"
        self.assertTrue(path.is_file(), "CI fixture is missing")
        text = path.read_text()
        for phrase in ("NOT delegated E2E", "Gate B", "SMOKE_RESULT=FAIL", "never invoke `copilot` recursively"):
            self.assertIn(phrase, text)

    def test_live_status_preserves_history_and_limits_scope_of_success(self):
        text = (SKILL / "SKILL.md").read_text()
        for phrase in (
            "THREE LIVE DELEGATED PATHS VERIFIED",
            "ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3",
            "2026-05-01",
            "2026-05-15-preview",
            "registered ARM API is not a proven fix",
            "not four-path compatibility",
        ):
            self.assertIn(phrase, text)
        manifest = (SKILL / "templates/azure.yaml").read_text()
        self.assertIn("language: docker", manifest)
        self.assertIn("remoteBuild: true", manifest)


if __name__ == "__main__":
    unittest.main()

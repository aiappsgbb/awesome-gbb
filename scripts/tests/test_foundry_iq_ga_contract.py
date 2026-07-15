"""Regression tests for the Foundry IQ GA-versus-preview contract."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-iq" / "SKILL.md"
PRD = ROOT / "skills" / "foundry-iq" / "PRD.md"
ENV_SAMPLE = ROOT / "skills" / "foundry-iq" / ".env.sample"
CI_ENV_SAMPLE = ROOT / ".env.ci.example"
REQUIREMENTS = ROOT / "skills" / "foundry-iq" / "requirements.txt"
PIN = ROOT / "skills" / "foundry-iq" / "references" / "upstream-pin.md"
KNOWLEDGE_AGENT_MANAGER = (
    ROOT / "skills" / "foundry-iq" / "scripts" / "knowledge_agent_manager.py"
)
FIXTURE = ROOT / "skills" / "foundry-iq" / "test-fixture" / "consumer_prompt.md"
AZURE_YAML = ROOT / "skills" / "foundry-iq" / "test-fixture" / "azure.yaml"
INFRA = ROOT / "skills" / "foundry-iq" / "test-fixture" / "infra" / "main.bicep"
SEARCH_MODULE = (
    ROOT / "skills" / "foundry-iq" / "test-fixture" / "infra" / "search.bicep"
)
DEPS = ROOT / ".github" / "skill-deps.yml"

GA_KINDS = {"searchIndex", "azureBlob", "indexedOneLake", "web"}
PREVIEW_KINDS = {
    "indexedSql",
    "file",
    "indexedSharePoint",
    "remoteSharePoint",
    "fabricDataAgent",
    "fabricOntology",
    "mcpServer",
    "workIQ",
}


def _frontmatter(text: str) -> dict:
    return yaml.safe_load(text.split("---", 2)[1])


def _availability_rows(skill: str) -> dict[str, str]:
    match = re.search(
        r"<!-- GA_KNOWLEDGE_SOURCE_MATRIX_START -->"
        r"(.*?)"
        r"<!-- GA_KNOWLEDGE_SOURCE_MATRIX_END -->",
        skill,
        re.DOTALL,
    )
    if not match:
        raise AssertionError("Foundry IQ availability matrix markers are missing")

    rows: dict[str, str] = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0] not in {"Wire kind", "---"}:
            rows[cells[0]] = cells[1]
    return rows


class FoundryIqGaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.prd = PRD.read_text(encoding="utf-8")
        cls.env_sample = ENV_SAMPLE.read_text(encoding="utf-8")
        cls.requirements = REQUIREMENTS.read_text(encoding="utf-8")
        cls.pin = PIN.read_text(encoding="utf-8")

    def test_skill_declares_stable_api_and_exact_ga_kinds(self) -> None:
        rows = _availability_rows(self.skill)
        ga = {kind for kind, status in rows.items() if status == "GA"}
        preview = {kind for kind, status in rows.items() if status == "Preview"}

        self.assertEqual(ga, GA_KINDS)
        self.assertEqual(preview, PREVIEW_KINDS)
        self.assertIn("`2026-04-01`", self.skill)
        self.assertNotRegex(
            self.skill,
            r"general availability on the \*\*`2026-05-01-preview`\*\*",
        )

    def test_skill_preserves_portal_and_iq_preview_boundaries(self) -> None:
        self.assertIn(
            "portal access to all agentic retrieval features remains preview",
            self.skill,
        )
        self.assertIn(
            "Foundry IQ, Work IQ, Fabric IQ, and Web IQ are standalone",
            self.skill,
        )

    def test_supporting_artifacts_pin_the_ga_surface(self) -> None:
        self.assertIn("2026-04-01", self.prd)
        self.assertIn(
            "AI_SEARCH_KNOWLEDGE_SOURCE_API_VERSION=2026-04-01",
            self.env_sample,
        )
        self.assertIn("azure-search-documents~=12.0.0", self.requirements)
        self.assertIn(
            "https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate",
            self.pin,
        )
        self.assertIn(
            "https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01",
            self.pin,
        )
        self.assertNotIn(
            "2025-11-01-preview",
            KNOWLEDGE_AGENT_MANAGER.read_text(encoding="utf-8"),
        )
        self.assertIn("Bearer {token}", FIXTURE.read_text(encoding="utf-8"))
        self.assertIn(
            "Bearer {token}",
            KNOWLEDGE_AGENT_MANAGER.read_text(encoding="utf-8"),
        )

        pin_frontmatter = _frontmatter(self.pin)
        pinned_sha = pin_frontmatter["upstream"]["pinned_sha"]
        self.assertIn(
            f'PINNED_SHA="${{PINNED_SHA:-{pinned_sha}}}"',
            self.pin,
        )
        self.assertIn(f"| **Pinned SHA** | `{pinned_sha}` |", self.pin)

    def test_live_fixture_exercises_only_a_ga_kind(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertIn("api-version=2026-04-01", fixture)
        self.assertIn('"kind": "searchIndex"', fixture)
        self.assertIn("preview-only", fixture)
        self.assertIn("/tmp/foundry-iq-smoke-result", fixture)
        step_zero = fixture.split("## Step 0", 1)[1].split("---", 1)[0]
        self.assertIn(
            'echo "Loading skill contract: skills/foundry-iq/SKILL.md',
            step_zero,
        )

        deps = yaml.safe_load(DEPS.read_text(encoding="utf-8"))
        self.assertIn("foundry-iq", deps["skills"])

    def test_standing_search_is_provisioned_through_azd(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        azure_yaml = yaml.safe_load(AZURE_YAML.read_text(encoding="utf-8"))
        infra = (
            INFRA.read_text(encoding="utf-8")
            + SEARCH_MODULE.read_text(encoding="utf-8")
        )
        workflow = (ROOT / ".github" / "workflows" / "skill-test.yml").read_text(
            encoding="utf-8"
        )

        self.assertEqual(azure_yaml["infra"]["provider"], "bicep")
        self.assertNotIn("azd provision", fixture)
        self.assertNotIn("azd down", fixture)
        self.assertNotIn("az search service create", fixture)
        self.assertIn("Microsoft.ResourceGraph/resources", fixture)
        self.assertIn("tags.workload =~ 'foundry-iq'", fixture)
        self.assertNotIn("AZURE_SEARCH_ENDPOINT:", workflow)
        ci_env = CI_ENV_SAMPLE.read_text(encoding="utf-8")
        self.assertIn("AZURE_PRINCIPAL_ID=<provisioner-object-id>", ci_env)
        self.assertIn("CI_PRINCIPAL_ID=<ci-uami-object-id>", ci_env)
        self.assertIn("targetScope = 'subscription'", infra)
        self.assertIn("Microsoft.Search/searchServices", infra)
        self.assertIn("disableLocalAuth: true", infra)
        self.assertIn("Search Service Contributor", infra)
        self.assertIn("Reader permits tag-based Resource Graph discovery", infra)
        self.assertIn("Microsoft.Search/searchServices@2026-03-01-preview", infra)
        self.assertIn("knowledgeRetrieval: 'standard'", infra)

    def test_live_fixture_enforces_rest_response_contract(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        self.assertIn(
            'f"{endpoint}/indexes(\'{index_name}\')?api-version={api_version}"',
            fixture,
        )
        self.assertIn(
            'f"{endpoint}/knowledgesources(\'{source_name}\')'
            '?api-version={api_version}"',
            fixture,
        )
        self.assertIn('"Prefer": "return=representation"', fixture)
        self.assertGreaterEqual(
            fixture.count("assert response.status_code == 201"),
            2,
        )
        self.assertIn("assert response.status_code == 200", fixture)

    def test_stable_sdk_and_mcp_examples_match_current_surfaces(self) -> None:
        self.assertIn(
            "from azure.search.documents.knowledgebases import "
            "KnowledgeBaseRetrievalClient",
            self.skill,
        )
        self.assertIn("KnowledgeBaseRetrievalRequest(", self.skill)
        self.assertIn("_kb_client.retrieve(request)", self.skill)
        self.assertNotIn(
            "from azure.search.documents.indexes import KnowledgeBaseRetrievalClient",
            self.skill,
        )
        self.assertNotIn("retrieve(query=query)", self.skill)
        self.assertIn("**C. Toolbox MCP wrapping the KB (preview)**", self.skill)
        self.assertIn(
            "Foundry Agent Service integration uses `2026-05-01-preview`",
            self.skill,
        )
        self.assertIn(
            'pip install "azure-search-documents~=12.0.0"',
            self.skill,
        )
        self.assertNotIn(
            "pip install azure-search-documents>=11.7.0b1",
            self.skill,
        )

    def test_minor_version_records_new_availability_contract(self) -> None:
        self.assertEqual(_frontmatter(self.skill)["metadata"]["version"], "1.4.0")


if __name__ == "__main__":
    unittest.main()

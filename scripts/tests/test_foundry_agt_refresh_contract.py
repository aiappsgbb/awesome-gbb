"""Contract tests for the foundry-agt 2.0 manual-hygiene refresh."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "foundry-agt"


def frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    _, fm, body = raw.split("---", 2)
    return yaml.safe_load(fm), body


class FoundryAgtRefreshContractTests(unittest.TestCase):
    def test_skill_is_major_and_path_a_only(self) -> None:
        meta, body = frontmatter(SKILL / "SKILL.md")
        self.assertEqual(meta["metadata"]["version"], "2.0.0")

        description = meta["description"].lower()
        for forbidden in ("aca sidecar", "citadel adapter", "26.67", "0.00%"):
            self.assertNotIn(forbidden, description)

        changelog_index = body.find("## GBB Changelog")
        self.assertNotEqual(changelog_index, -1, "GBB Changelog heading not found")
        active_body = body[:changelog_index].lower()
        for forbidden in (
            "## path b",
            "## path c",
            "mcr.microsoft.com/agentmesh/enforcer",
            "26.67% policy-violation rate",
            "0.00% violation",
            "hitl-gate",
            "outbound text",
        ):
            self.assertNotIn(forbidden, active_body)

    def test_compliance_wording_is_precise(self) -> None:
        _, body = frontmatter(SKILL / "SKILL.md")
        changelog_index = body.find("## GBB Changelog")
        self.assertNotEqual(changelog_index, -1, "GBB Changelog heading not found")
        active_body = body[:changelog_index]

        self.assertIn("self-assessment", active_body)
        self.assertIn("not certification", active_body)
        self.assertIn("live_t3_probe.py", active_body)
        for forbidden in (
            "certifies compliance",
            "certification proof",
            "independent audit proof",
            "ci-gateable proof of compliance",
            "guarantees owasp compliance",
            "not yet proved at this pin",
            "pending a live probe run",
        ):
            self.assertNotIn(forbidden, active_body.lower())

    def test_pin_uses_released_source_and_selective_set(self) -> None:
        pin_meta, _ = frontmatter(SKILL / "references" / "upstream-pin.md")

        self.assertEqual(pin_meta["automation_tier"], "issue_only")
        self.assertEqual(pin_meta["upstream"]["ref"], "v4.1.0")
        self.assertEqual(
            pin_meta["upstream"]["pinned_sha"],
            "0de71ca6c95cf8b9b975ac96f48eaa7826bbe258",
        )

        expected_packages = {
            "agent-governance-toolkit": "4.1.0",
            "agent-framework-core": "1.13.0",
            "agent-framework-foundry": "1.10.4",
            "agent-framework-openai": "1.12.0",
            "azure-identity": "1.25.3",
        }
        actual_packages = {
            package["name"]: str(package["version"])
            for package in pin_meta["packages"]
        }
        self.assertEqual(actual_packages, expected_packages)

        validation_script = pin_meta["validation"]["script"]
        for expected_substring in (
            "agent-governance-toolkit[full]~=${PINNED_AGT_VERSION:-4.1.0}",
            "agent-framework-core~=${PINNED_AF_CORE_VERSION:-1.13.0}",
            "agent-framework-foundry~=${PINNED_AF_FOUNDRY_VERSION:-1.10.4}",
            "agent-framework-openai~=${PINNED_AF_OPENAI_VERSION:-1.12.0}",
            "azure-identity~=${PINNED_IDENTITY_VERSION:-1.25.3}",
            "references/python/contract_probe.py",
        ):
            self.assertIn(expected_substring, validation_script)
        self.assertNotIn("HITL_POLICY=PASS", validation_script)

        expected_output = pin_meta["validation"]["expected_output"]
        self.assertIn("POLICY_MIDDLEWARE=PASS", expected_output)
        self.assertNotIn("HITL_POLICY=PASS", expected_output)

        known_issues = pin_meta["known_issues"]
        self.assertEqual(len(known_issues), 2)
        self.assertEqual(pin_meta["known_issues_count"], 2)
        for issue in known_issues:
            self.assertIsNone(issue.get("upstream_url"))
            self.assertNotEqual(issue["id"], "KI-001")

    def test_probes_cover_shapes_hook_and_live_inference(self) -> None:
        local_probe_path = SKILL / "references" / "python" / "contract_probe.py"
        live_probe_path = SKILL / "references" / "python" / "live_t3_probe.py"
        snippet_path = SKILL / "references" / "maf-middleware-snippet.py"

        self.assertTrue(local_probe_path.is_file())
        self.assertTrue(live_probe_path.is_file())
        self.assertTrue(snippet_path.is_file())

        local_probe = local_probe_path.read_text(encoding="utf-8")
        live_probe = live_probe_path.read_text(encoding="utf-8")
        snippet = snippet_path.read_text(encoding="utf-8")

        for expected_substring in (
            "FoundryChatClient",
            "StubCredential",
            "StubChatClient",
            "STUB_FOUNDRY_CONSTRUCTION=PASS",
            "STUB_RESPONSE_SHAPE=PASS",
            "FunctionInvocationContext",
            "FunctionTool",
            "CapabilityGuardMiddleware",
            "CAPABILITY_HOOK_ALLOW_EXECUTIONS=1",
            "CAPABILITY_HOOK_DENY_EXECUTIONS=0",
            "CONTRACT_PROBE=PASS",
            "AgentContext",
            "POLICY_MIDDLEWARE=PASS",
            ".invoke(arguments={}, context=",
        ):
            self.assertIn(expected_substring, local_probe)

        self.assertNotIn("HITL_POLICY=PASS", local_probe)
        self.assertNotIn("tool_args.amount", local_probe)

        for expected_substring in (
            "FoundryChatClient",
            "DefaultAzureCredential",
            "https://ai.azure.com/.default",
            "LIVE_RESPONSE_NONEMPTY=1",
            "LIVE_RESPONSE_ID_PRESENT=1",
            "ALLOWED_TOOL_EXECUTIONS=1",
            "DENIED_TOOL_EXECUTIONS=0",
            "CAPABILITY_DENY_OBSERVED=1",
            "T3_PROBE=PASS",
        ):
            self.assertIn(expected_substring, live_probe)

        self.assertNotIn('agent.run("DROP TABLE users")', live_probe)

        for expected_substring in (
            "allowed_tools=allowed_tools",
            "denied_tools=denied_tools",
        ):
            self.assertIn(expected_substring, snippet)
        for forbidden_substring in (
            "allowed_tools or []",
            "denied_tools or []",
        ):
            self.assertNotIn(forbidden_substring, snippet)

    def test_unsupported_sidecar_is_removed(self) -> None:
        sidecar_path = SKILL / "references" / "aca-sidecar-snippet.bicep"
        self.assertFalse(sidecar_path.exists())

        hitl_gate_path = SKILL / "references" / "policies" / "hitl-gate.yaml"
        self.assertFalse(hitl_gate_path.exists())

    def test_fixture_is_live_and_marker_safe(self) -> None:
        fixture = (SKILL / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )

        for expected_substring in (
            "FOUNDRY_PROJECT_ENDPOINT",
            "FOUNDRY_MODEL_DEPLOYMENT",
            "references/python/contract_probe.py",
            "references/python/live_t3_probe.py",
            "/tmp/foundry-agt-smoke-evidence",
            "_MOKE_RESULT=PASS",
            "SKILL_CONTRACT=OK",
            "sed -n",
            r'"agent-governance-toolkit\[full\]~=4\.1\.0"',
        ):
            self.assertIn(expected_substring, fixture)

        self.assertNotIn("SMOKE_RESULT=PASS", fixture)
        lowered = fixture.lower()
        self.assertNotIn("no dataplane calls", lowered)
        self.assertNotIn("no model deployments", lowered)

    def test_workflow_uploads_marker_artifact(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "skill-test.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("/tmp/${{ matrix.skill }}-smoke-result", workflow)

    def test_dependency_graph_has_one_key(self) -> None:
        deps = (ROOT / ".github" / "skill-deps.yml").read_text(encoding="utf-8")
        matches = re.findall(r"^  foundry-agt:\s*$", deps, flags=re.MULTILINE)
        self.assertEqual(len(matches), 1)

    def test_readme_drops_removed_contract_and_overclaim(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_line = next(
            (line for line in readme.splitlines() if "[**foundry-agt**]" in line),
            None,
        )
        self.assertIsNotNone(readme_line, "foundry-agt README line not found")

        for forbidden in (
            "v3.6.0",
            "Path B",
            "Path C",
            "26.67%",
            "5 field-tested Known Issues",
            "HITL-gate",
        ):
            self.assertNotIn(forbidden, readme_line)

    def test_ssn_policy_exact_yaml_bytes(self) -> None:
        policy = (
            SKILL / "references" / "policies" / "pii-deny.yaml"
        ).read_text(encoding="utf-8")

        expected = r"value: '\b\d{3}[\s.-]?\d{2}[\s.-]?\d{4}\b'"
        self.assertEqual(policy.count(expected), 1)
        self.assertNotIn("field: response", policy)


if __name__ == "__main__":
    unittest.main()

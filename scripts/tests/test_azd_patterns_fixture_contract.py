"""Contract tests for the azd-patterns live fixture."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "skills" / "azd-patterns" / "test-fixture" / "consumer_prompt.md"
SKILL = ROOT / "skills" / "azd-patterns" / "SKILL.md"
ACA_JOB = ROOT / "skills" / "azd-patterns" / "references" / "bicep" / "aca-job.bicep"


class AzdPatternsFixtureContractTests(unittest.TestCase):
    def test_aca_job_reference_module_is_canonical(self) -> None:
        self.assertTrue(ACA_JOB.exists(), "missing skills/azd-patterns/references/bicep/aca-job.bicep")
        module = ACA_JOB.read_text(encoding="utf-8")
        for snippet in (
            "Microsoft.App/jobs@2026-01-01",
            "param name string",
            "param location string",
            "param environmentId string",
            "param imageDigest string",
            "param containerName string",
            "param command array",
            "param args array = []",
            "param environmentVariables array = []",
            "param uamiResourceId string",
            "param acrServer string",
            "param replicaTimeout int = 300",
            "param replicaRetryLimit int = 1",
            "triggerType: 'Manual'",
            "imageDigest",
            "@sha256:",
            "output id string",
            "output name string",
        ):
            self.assertIn(snippet, module)

        self.assertIn("assert digestFormat =", module)
        self.assertIn("@sha256:", module)
        self.assertIn("length(split(imageDigest, '@sha256:')[1]) == 64", module)
        self.assertNotIn("Microsoft.Authorization/roleAssignments", module)
        self.assertNotIn("Foundry", module)
        self.assertNotIn("secrets", module.lower())

    def test_skill_bicep_job_pattern_references_canonical_module(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn(
            "> **MUST:** Copy verbatim from [`references/bicep/aca-job.bicep`](references/bicep/aca-job.bicep).",
            skill,
        )
        self.assertIn("immutable digest", skill)
        self.assertIn("azd deploy` does **not** deploy ACA Jobs", skill)
        self.assertIn("postdeploy", skill)
        self.assertIn("az containerapp job start", skill)
        self.assertNotIn("Microsoft.App/jobs@2024-03-01", skill)
        self.assertNotIn("fetchLatestImage", skill)
        self.assertNotIn("scheduleTriggerConfig", skill)
        excerpt = re.search(
            r"## Bicep: ACA Job Pattern.*?```bicep\n(.*?)```",
            skill,
            re.DOTALL,
        )
        self.assertIsNotNone(excerpt)
        lines = [line for line in excerpt.group(1).splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 20)

    def test_first_action_is_standalone_skill_breadcrumb(self) -> None:
        fixture = FIXTURE.read_text(encoding="utf-8")
        bash_blocks = re.findall(r"```bash\n(.*?)```", fixture, re.DOTALL)

        self.assertTrue(bash_blocks)
        self.assertEqual(
            bash_blocks[0].strip(),
            'echo "skills/azd-patterns/SKILL.md"',
        )
        self.assertIn(
            "Your first action must be a separate Bash tool call containing only",
            fixture,
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Contract tests for the azd-patterns ACA Job reference module."""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
ACA_JOB = ROOT / "skills" / "azd-patterns" / "references" / "bicep" / "aca-job.bicep"
SKILL = ROOT / "skills" / "azd-patterns" / "SKILL.md"


class AzdPatternsFixtureContractTests(unittest.TestCase):
    def test_reference_module_has_portable_digest_contract_and_exact_defaults(self) -> None:
        module = ACA_JOB.read_text(encoding="utf-8")
        self.assertIn(
            "@description('registry/repo@sha256:<64 lowercase hex>.')",
            module,
        )
        self.assertNotIn("assert digestFormat", module)
        self.assertIn("param imageDigest string", module)
        self.assertIn("cpu: json('0.5')", module)
        self.assertIn("memory: '1Gi'", module)

    def test_image_digest_regex_contract_samples(self) -> None:
        pattern = re.compile(r"^[^@\s]+(?:/[^@\s]+)+@sha256:[0-9a-f]{64}$")
        valid = [
            "acr.example.io/repo@sha256:" + "a" * 64,
            "acr.example.io/team/image@sha256:" + "0123456789abcdef" * 4,
        ]
        invalid = [
            "acr.example.io/repo@sha256:" + "A" * 64,
            "acr.example.io/repo@sha256:" + "g" * 64,
            "acr.example.io/repo:latest",
            "repo@sha256:" + "a" * 64,
        ]

        for sample in valid:
            self.assertRegex(sample, pattern)
        for sample in invalid:
            self.assertNotRegex(sample, pattern)

    def test_reference_module_builds_without_repo_bicepconfig(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workdir = pathlib.Path(temp_dir)
            self.assertFalse(ROOT in workdir.resolve().parents)
            copied = workdir / ACA_JOB.name
            shutil.copy2(ACA_JOB, copied)

            result = subprocess.run(
                [
                    "az",
                    "bicep",
                    "build",
                    "--file",
                    copied.name,
                    "--outfile",
                    "aca-job.json",
                ],
                cwd=workdir,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=(
                    "az bicep build failed without repo bicepconfig\n"
                    f"stdout:\n{result.stdout}\n"
                    f"stderr:\n{result.stderr}"
                ),
            )
            self.assertNotIn("assertions feature", result.stderr.lower())
            self.assertTrue((workdir / "aca-job.json").exists())

    def test_skill_module_catalog_aca_job_row_matches_canonical_contract(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        expected_row = (
            "| **aca-job** | `infra/modules/aca-job.bicep` | `aca-job: yes` "
            "(params: `[{ name, imageDigest, containerName, command, args, "
            "environmentVariables, uamiResourceId, acrServer, environmentId }]`) | "
            "`id`, `name` | Manual only; `threadlight-event-triggers` owns the "
            "cron/event variant |"
        )

        self.assertIn(expected_row, skill)
        selector_excerpt = skill[skill.index("```markdown"): skill.index("```", skill.index("```markdown") + 1)]
        self.assertNotIn("trigger: cron", selector_excerpt)
        self.assertNotIn("trigger: schedule", selector_excerpt)
        self.assertIn("imageDigest", selector_excerpt)
        self.assertIn("command", selector_excerpt)

    def test_skill_bicep_job_pattern_references_canonical_module(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn(
            "> **MUST:** Copy verbatim from [`references/bicep/aca-job.bicep`](references/bicep/aca-job.bicep).",
            skill,
        )
        self.assertIn("immutable `imageDigest` contract", skill)
        self.assertIn("compiles copy-verbatim without repo `bicepconfig`", skill)
        self.assertIn("azd deploy` does **not** deploy ACA Jobs", skill)
        self.assertIn("postdeploy", skill)
        self.assertIn("az containerapp job start", skill)
        self.assertNotIn("assert digestFormat", skill)
        excerpt = re.search(
            r"## Bicep: ACA Job Pattern.*?```bicep\n(.*?)```",
            skill,
            re.DOTALL,
        )
        self.assertIsNotNone(excerpt)
        lines = [line for line in excerpt.group(1).splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 20)

    def test_foundry_observability_uses_scheduled_aca_job_module(self) -> None:
        skill = (ROOT / "skills" / "foundry-observability" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("// infra/modules/aca-scheduled-job.bicep", skill)
        self.assertIn(
            "The scheduled/event-trigger module family is owned by `threadlight-event-triggers`",
            skill,
        )
        self.assertIn("azd-patterns/references/bicep/aca-job.bicep", skill)
        self.assertNotIn("// infra/modules/aca-job.bicep", skill)

    def test_fixture_frames_canonical_coverage_as_legacy_debug_playbook(self) -> None:
        fixture = (ROOT / "skills" / "azd-patterns" / "test-fixture" / "consumer_prompt.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("legacy debug-playbook coverage for the **ACA Job**", fixture)
        self.assertIn("canonical module's live Azure coverage is", fixture)
        self.assertIn("exercised by the separate `foundry-mcp-aca-jobs` fixture", fixture)
        self.assertIn("deliberate minimal legacy debug-playbook variant", fixture)
        self.assertNotIn("proves the canonical `Microsoft.App/jobs@2024-03-01` resource shape", fixture)

    def test_no_skill_other_than_azd_patterns_describes_schedule_on_aca_job_bicep(self) -> None:
        offenders = []
        for skill_path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            if skill_path.parent.name in {"azd-patterns", "foundry-observability"}:
                continue
            text = skill_path.read_text(encoding="utf-8")
            if "aca-job.bicep" in text and "Schedule" in text:
                offenders.append(skill_path.parent.name)

        self.assertEqual(
            offenders,
            [],
            msg=f"Unexpected schedule-era aca-job.bicep references: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()

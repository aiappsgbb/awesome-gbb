"""Contract tests for Citadel's foundry-agt composition guidance."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CITADEL_SKILL = ROOT / "skills" / "citadel-hub-deploy" / "SKILL.md"


def _frontmatter_and_body() -> tuple[dict, str]:
    raw = CITADEL_SKILL.read_text(encoding="utf-8")
    _, frontmatter, body = raw.split("---", 2)
    return yaml.safe_load(frontmatter), body


def _platform_section(body: str) -> str:
    match = re.search(
        r"^## 9\. The 4-layer Citadel Platform\n(?P<section>.*?)(?=^---$)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError("Citadel platform section not found")
    return match.group("section")


def _composition_guidance(body: str) -> str:
    section = _platform_section(body)
    marker = "Defence in depth"
    if marker not in section:
        raise AssertionError("Citadel defence-in-depth guidance not found")
    return marker + section.split(marker, 1)[1]


class CitadelHubAgtCrossSkillContractTests(unittest.TestCase):
    def test_version_includes_corrected_guidance_patch(self) -> None:
        metadata, _ = _frontmatter_and_body()
        version = tuple(int(part) for part in metadata["metadata"]["version"].split("."))
        self.assertGreaterEqual(version, (1, 1, 1))

    def test_cites_current_agt_contract_without_withdrawn_metrics(self) -> None:
        _, body = _frontmatter_and_body()
        guidance = _composition_guidance(body)

        self.assertIn(
            "[`foundry-agt`](../foundry-agt/SKILL.md#why-action-governance-matters)",
            guidance,
        )
        self.assertIn("Why action governance matters", guidance)

        for withdrawn_claim in ("Why this matters", "26.67%", "0.00%"):
            with self.subTest(withdrawn_claim=withdrawn_claim):
                self.assertNotIn(withdrawn_claim, guidance)

    def test_distinguishes_agt_action_plane_from_apim_edge_plane(self) -> None:
        _, body = _frontmatter_and_body()
        guidance = _composition_guidance(body)

        self.assertRegex(
            guidance,
            re.compile(
                r"AGT.{0,220}deterministic.{0,160}"
                r"(allow/deny|allow-or-deny).{0,100}tool name.{0,180}"
                r"(before|pre-execution).{0,100}(tool body|call_next)",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            guidance,
            re.compile(
                r"APIM.{0,160}edge.{0,120}"
                r"(auth|authentication).{0,120}rate limiting.{0,120}"
                r"(product policy|product policies)",
                re.IGNORECASE | re.DOTALL,
            ),
        )


if __name__ == "__main__":
    unittest.main()

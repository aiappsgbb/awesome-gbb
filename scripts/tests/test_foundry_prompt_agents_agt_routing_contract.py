"""Contract tests for prompt-agent guardrail routing ownership."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
PROMPT_AGENTS_SKILL = ROOT / "skills" / "foundry-prompt-agents" / "SKILL.md"


def _frontmatter_and_body() -> tuple[dict, str]:
    raw = PROMPT_AGENTS_SKILL.read_text(encoding="utf-8")
    _, frontmatter, body = raw.split("---", 2)
    return yaml.safe_load(frontmatter), body


def _section(body: str, start: str, end: str | None = None) -> str:
    end_pattern = rf"^{re.escape(end)}\n" if end is not None else r"\Z"
    match = re.search(
        rf"^{re.escape(start)}\n(?P<section>.*?)(?={end_pattern})",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Section not found: {start}")
    return match.group("section")


class FoundryPromptAgentsAgtRoutingContractTests(unittest.TestCase):
    def test_version_includes_local_guardrail_routing_patch(self) -> None:
        metadata, _ = _frontmatter_and_body()
        version = tuple(int(part) for part in metadata["metadata"]["version"].split("."))
        self.assertGreaterEqual(version, (1, 1, 6))

    def test_guardrail_routing_is_local_and_plane_specific(self) -> None:
        _, body = _frontmatter_and_body()
        section = _section(body, "#### GuardrailTool", "#### A2ATool")

        self.assertNotIn("canonical decision table", section)
        self.assertIn(
            "[`foundry-agt`](../foundry-agt/SKILL.md#why-action-governance-matters)",
            section,
        )
        self.assertRegex(
            section,
            re.compile(
                r"GuardrailTool.{0,260}(prompt agent|PromptAgentDefinition).{0,260}"
                r"(Azure Content Safety|ACS).{0,160}(connection|server-side)",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            section,
            re.compile(
                r"(raw|direct).{0,80}(Azure Content Safety|ACS).{0,120}"
                r"(classifier|threshold).{0,120}(application|handling)",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            section,
            re.compile(
                r"foundry-agt.{0,180}MAF.{0,100}hosted.{0,180}"
                r"deterministic.{0,120}tool name.{0,160}(before|pre-execution)",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_agt_is_not_presented_as_prompt_agent_content_safety(self) -> None:
        _, body = _frontmatter_and_body()
        section = _section(body, "#### GuardrailTool", "#### A2ATool")
        related = _section(body, "### Related skills")

        self.assertRegex(
            section,
            re.compile(
                r"AGT.{0,100}(does not|is not).{0,80}"
                r"(replace|substitute).{0,80}(Content Safety|ACS)",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            section,
            re.compile(
                r"(cannot|can't).{0,120}(add|insert|wire).{0,120}"
                r"(AGT|middleware).{0,120}PromptAgentDefinition",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertNotIn("incl. GuardrailTool decision", related)
        self.assertRegex(
            related,
            re.compile(
                r"MAF.{0,100}hosted-agent.{0,120}action governance.{0,100}"
                r"`foundry-agt`",
                re.IGNORECASE | re.DOTALL,
            ),
        )


if __name__ == "__main__":
    unittest.main()

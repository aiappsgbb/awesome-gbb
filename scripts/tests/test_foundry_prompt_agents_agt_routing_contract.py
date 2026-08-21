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
        self.assertGreaterEqual(version, (1, 1, 7))

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

    def test_generated_docs_show_the_current_version_everywhere(self) -> None:
        metadata, _ = _frontmatter_and_body()
        expected = f"v{metadata['metadata']['version']}"
        detail = (
            ROOT / "docs" / "skills" / "foundry-prompt-agents" / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn(f'<span class="badge ver">{expected}</span>', detail)

        card_pattern = re.compile(
            r'href="/awesome-gbb/skills/foundry-prompt-agents/">'
            r"foundry-prompt-agents</a>.{0,1600}"
            rf'<span class="badge ver">{re.escape(expected)}</span>',
            re.DOTALL,
        )
        listing_pages = (
            ROOT / "docs" / "skills" / "index.html",
            ROOT / "docs" / "plugins" / "awesome-gbb" / "index.html",
        )
        for page in listing_pages:
            with self.subTest(page=page.relative_to(ROOT)):
                self.assertRegex(page.read_text(encoding="utf-8"), card_pattern)


if __name__ == "__main__":
    unittest.main()

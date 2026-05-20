"""FoundrySkillsSource — verified-working SkillsSource for the
Foundry Skills REST API.

Drop this file into your hosted agent's source tree and wire it into
`SkillsProvider(source=FoundrySkillsSource(...))`. See
`skills/foundry-skill-catalog/SKILL.md` § "Pattern B" for the full wiring.

Verified against:
- azure-ai-projects 2.1.0
- agent-framework  1.3.0
- azure-identity   1.26.0b2

JSON-mode skills (`has_blob: false`) are write-only at the API level — their
`instructions` body is never returned by GET / list / download. This source
returns a placeholder InlineSkill for them so the agent at least sees the
skill exists; recommend re-importing those skills as ZIP-mode for full
runtime use.
"""

from __future__ import annotations

import asyncio
import io
import zipfile

from agent_framework import InlineSkill, Skill, SkillsSource
from azure.ai.projects import AIProjectClient


class FoundrySkillsSource(SkillsSource):
    """Pull skills from a Foundry project's Skills REST API."""

    def __init__(self, project_endpoint: str, credential) -> None:
        self._endpoint = project_endpoint
        self._credential = credential

    async def get_skills(self) -> list[Skill]:
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> list[Skill]:
        out: list[Skill] = []
        with AIProjectClient(
            endpoint=self._endpoint,
            credential=self._credential,
            allow_preview=True,
        ) as project:
            for summary in project.beta.skills.list():
                if summary.has_blob:
                    out.append(self._from_zip(project, summary))
                else:
                    out.append(self._from_json_placeholder(summary))
        return out

    def _from_zip(self, project, summary) -> InlineSkill:
        zip_bytes = b"".join(project.beta.skills.download(summary.name))
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            md_name = next(
                (n for n in z.namelist() if n.lower().endswith("skill.md")),
                None,
            )
            if md_name is None:
                raise RuntimeError(
                    f"Skill '{summary.name}' downloaded ZIP has no SKILL.md"
                )
            raw = z.read(md_name).decode("utf-8")
        return InlineSkill(
            name=summary.name,
            description=summary.description or "",
            instructions=self._strip_frontmatter(raw),
        )

    def _from_json_placeholder(self, summary) -> InlineSkill:
        return InlineSkill(
            name=summary.name,
            description=summary.description or "",
            instructions=(
                summary.description
                or f"[Foundry JSON-mode skill '{summary.name}' — body not "
                f"retrievable from the API. Re-import as a ZIP to fix.]"
            ),
        )

    @staticmethod
    def _strip_frontmatter(raw: str) -> str:
        if not raw.startswith("---"):
            return raw
        parts = raw.split("---", 2)
        return parts[2].lstrip("\n") if len(parts) >= 3 else raw

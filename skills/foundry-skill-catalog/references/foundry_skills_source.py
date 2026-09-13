"""Canonical version-aware Foundry Skills consumer.

Source of truth for `../SKILL.md § Pattern B — Runtime fetch via `FoundrySkillsSource` (recommended for shared catalogs)`.

The original two-argument constructor and async get_skills interface remain.
Native catalogs resolve default_version once, then download that immutable
version. Optional skill_versions selects only named skills and pins versions.
Only explicitly legacy has_blob metadata enables the old download/placeholder
behavior; provider failures never trigger a downgrade.
Copy skill_packages.py beside this adapter.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping

import agent_framework
from agent_framework import InlineSkill, Skill, SkillsSource
from azure.ai.projects import AIProjectClient

from skill_packages import SkillPackage, download_catalog, skill_archive, validate_selection


class FoundrySkillsSource(SkillsSource):
    """Pull skills from a Foundry project's Skills REST API."""

    def __init__(
        self, project_endpoint: str, credential, *,
        skill_versions: Mapping[str, str | None] | None = None,
    ) -> None:
        validate_selection(skill_versions)
        self._endpoint = project_endpoint
        self._credential = credential
        self._skill_versions = None if skill_versions is None else dict(skill_versions)

    async def get_skills(self) -> list[Skill]:
        return await asyncio.to_thread(self._collect)

    def _collect(self) -> list[Skill]:
        out: list[Skill] = []
        with AIProjectClient(
            endpoint=self._endpoint,
            credential=self._credential,
            allow_preview=True,
        ) as project:
            for package in download_catalog(project, self._skill_versions):
                if package.content is not None:
                    raw, _ = skill_archive(package.content)
                    instructions = self._strip_frontmatter(raw)
                else:
                    instructions = package.description or (
                        f"[Foundry legacy JSON-mode skill '{package.name}' — body not retrievable. "
                        "Republish through the native versioned API.]"
                    )
                out.append(self._inline_skill(package.name, package.description, instructions))
        return out

    @staticmethod
    def _inline_skill(name: str, description: str, instructions: str) -> InlineSkill:
        if "frontmatter" in inspect.signature(InlineSkill).parameters:
            return InlineSkill(
                frontmatter=agent_framework.SkillFrontmatter(name=name, description=description),
                instructions=instructions,
            )
        return InlineSkill(name=name, description=description, instructions=instructions)

    @staticmethod
    def _strip_frontmatter(raw: str) -> str:
        if not raw.startswith("---"):
            return raw
        parts = raw.split("---", 2)
        return parts[2].lstrip("\n") if len(parts) >= 3 else raw

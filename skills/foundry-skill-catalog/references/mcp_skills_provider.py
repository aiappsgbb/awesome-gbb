"""Canonical native MCP Skills provider for the existing MAF 1.17 line.

Source of truth for `../SKILL.md § Progressive loading is a separate capability`.
The caller owns the authenticated MCP session and must keep it open while the
provider is used. This path is experimental and does not download via Pattern B.
"""

from agent_framework import MCPSkillsSource, SkillsProvider
from mcp import ClientSession


def toolbox_skills_provider(
    session: ClientSession, *, trusted_skill_loading: bool = False
) -> SkillsProvider:
    if not isinstance(trusted_skill_loading, bool):
        raise TypeError("trusted_skill_loading must be an explicit boolean")
    return SkillsProvider(
        MCPSkillsSource(client=session),
        disable_load_skill_approval=trusted_skill_loading,
    )

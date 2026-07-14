# Canonical hosted-agent container.py — MAF + FoundryChatClient + SkillsProvider.
#
# This is the field-validated reference shape for a Foundry hosted agent that
# bundles multiple business SKILLs (the threadlight-style multi-SKILL composition
# pattern). It is the SOURCE OF TRUTH for the prose example in
# `../../SKILL.md § Skill Loading — SkillsProvider (recommended)`.
#
# When to use this vs ../python/main.py:
#   - main.py: single-purpose agent, 0-1 business SKILLs, simple tool list
#   - container.py (this file): multi-SKILL agent, business logic in markdown
#     files under ./skills/<name>/SKILL.md, MAF loads them as context providers
#
# Validated in 2026-05-29 smb-credit-memo run (agentic-loop SKILL Validation
# history row 8): 6 business SKILLs loaded into the system prompt at container
# start, all 4 demo scenarios passed live. The `loaded SKILL: <name>` log line
# per SKILL is the smoke test — verify in `azd ai agent monitor` after first
# cold start; if you see only 1 line, the loader is wrong.

import logging
import os
from pathlib import Path
from typing import Annotated

from agent_framework import (
    Agent,
    MCPStreamableHTTPTool,
    SkillsProvider,
    tool,
)
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity.aio import DefaultAzureCredential  # async — see ../python/main.py § MID-I
from pydantic import Field

log = logging.getLogger(__name__)


def _init_telemetry() -> None:
    """Guarded OTel init — never crashes the container.

    The platform auto-injects APPLICATIONINSIGHTS_CONNECTION_STRING. On
    O-012 affected accounts (see foundry-observability SKILL § Common
    silent-failure modes) the injection silently fails OR injects a
    malformed value missing the '=' separator. Either way, calling
    configure_azure_monitor() raw at module/main scope crashes the
    container at import → 'session_not_ready' / 'server_error'.

    This wrapper validates the env var, catches ImportError on the SDK,
    and catches any SDK exception. The agent runs fine without telemetry
    — don't let telemetry init kill the startup.
    """
    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn.startswith("InstrumentationKey="):
        log.info("AppIn connection string missing or malformed; OTel disabled.")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=conn)
        log.info("OTel wired to App Insights.")
    except ImportError:
        log.warning("azure-monitor-opentelemetry not installed; OTel disabled.")
    except Exception as exc:  # noqa: BLE001 — never crash on telemetry init
        log.warning("OTel init failed (%s); continuing without telemetry.", exc)


def _build_skills_provider() -> SkillsProvider | None:
    """Wire SKILL.md playbooks via MAF's progressive-disclosure provider.

    Returns None if the skills directory is missing or empty so the
    agent stays runnable with context_providers=[] instead of crashing
    at startup on a corrupt or absent skill folder.

    DO use SkillsProvider.from_paths(skills_dir) — MAF 1.6.0 recommended,
    works on 1.4.0+.
    DO NOT use the legacy SkillsProvider(skill_paths=skills_dir) constructor
    — it was removed in MAF 1.4.0 with no alias. If you see
    `TypeError: SkillsProvider.__init__() got an unexpected keyword argument
    'skill_paths'` at container startup, replace with SkillsProvider.from_paths(...)
    immediately.
    """
    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.exists():
        log.warning("Skills directory missing at %s; SkillsProvider disabled.", skills_dir)
        return None
    skill_subdirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    ]
    if not skill_subdirs:
        log.warning("No SKILL.md files found under %s; SkillsProvider disabled.", skills_dir)
        return None
    try:
        provider = SkillsProvider.from_paths(skills_dir)
        log.info(
            "SkillsProvider wired with %d skill(s): %s",
            len(skill_subdirs),
            ", ".join(sorted(d.name for d in skill_subdirs)),
        )
        return provider
    except Exception as exc:  # never crash on a corrupt skill folder
        log.warning("SkillsProvider init failed (%s); falling back to no-op.", exc)
        return None


@tool(approval_mode="never_require")
def my_tool(query: Annotated[str, Field(description="Input")]) -> str:
    """Replace with your domain tool(s). See ../python/main.py for the
    single-purpose-agent shape."""
    return "result"


def main() -> None:
    _init_telemetry()

    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    skills_provider = _build_skills_provider()
    context_providers = [skills_provider] if skills_provider else []

    agent = Agent(
        client=client,
        instructions="You are a helpful assistant.",
        tools=[my_tool],
        context_providers=context_providers,
        default_options={"store": False},  # Platform manages history
    )

    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()

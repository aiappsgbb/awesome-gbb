"""Build a MAF Agent that consumes a discovered PoC.

This is the canonical Pattern 0 wiring — same shape as the
``SkillsProvider`` snippet documented in ``foundry-hosted-agents``
§ Skill Loading, but with:

  * **Stub Python tools** (from ``stub_tools.build_stub_tools``) in
    place of ``MCPStreamableHTTPTool`` instances → no live MCP server.
  * **In-memory store** in place of Cosmos / Search → no Docker, no
    emulator.
  * **One LLM dep** — either ``FoundryChatClient`` (default) or
    ``AzureOpenAIChatClient`` — toggled via ``LLM_BACKEND``.

PoC-side overrides:

  * If the PoC ships ``tests/quickstart_tools.py`` exposing
    ``register(tools: list, stores: dict) -> list`` the wiring calls
    it and appends whatever it returns. Use this for richer tools
    (cross-entity joins, derived fields, business rules).
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .discover import PoCLayout
from .stub_tools import InMemoryStore, build_stub_tools

log = logging.getLogger(__name__)

_DEFAULT_INSTRUCTIONS = """\
You are the Pattern 0 quickstart agent for a Threadlight-designed
proof-of-concept. The skills loaded by SkillsProvider describe each
process you can run; consult them before answering. You have a small
set of CRUD-shaped tools backed by an in-memory store of the PoC's
sample data — never invent record IDs, always list or get first.

When you mutate data with `update_*`, mention what changed so the
operator can see the demo land. Reply concisely.
"""


def build_chat_client():
    """Return a MAF ChatClient based on ``LLM_BACKEND`` (foundry|aoai)."""
    backend = os.environ.get("LLM_BACKEND", "foundry").lower()
    if backend == "foundry":
        return _build_foundry_client()
    if backend in {"aoai", "azure_openai", "azureopenai"}:
        return _build_aoai_client()
    raise ValueError(
        f"Unknown LLM_BACKEND={backend!r}. Use 'foundry' (default) or 'aoai'."
    )


def _build_foundry_client():
    from agent_framework.foundry import FoundryChatClient  # type: ignore[import-not-found]
    from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]

    endpoint = _require_env(
        "FOUNDRY_PROJECT_ENDPOINT",
        "Set FOUNDRY_PROJECT_ENDPOINT to your Foundry project URL "
        "(https://<account>.services.ai.azure.com/api/projects/<project>).",
    )
    model = _require_env(
        "MODEL_DEPLOYMENT_NAME",
        "Set MODEL_DEPLOYMENT_NAME to the deployed model (e.g. gpt-5.4-mini).",
    )
    return FoundryChatClient(
        project_endpoint=endpoint,
        model=model,
        credential=DefaultAzureCredential(),
    )


def _build_aoai_client():
    from agent_framework.openai import AzureOpenAIChatClient  # type: ignore[import-not-found]
    from azure.identity import DefaultAzureCredential  # type: ignore[import-not-found]

    endpoint = _require_env(
        "AZURE_OPENAI_ENDPOINT",
        "Set AZURE_OPENAI_ENDPOINT to your AOAI account URL.",
    )
    deployment = _require_env(
        "AZURE_OPENAI_DEPLOYMENT",
        "Set AZURE_OPENAI_DEPLOYMENT to a deployed model name.",
    )
    return AzureOpenAIChatClient(
        endpoint=endpoint,
        deployment_name=deployment,
        credential=DefaultAzureCredential(),
    )


def _require_env(name: str, hint: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is unset. {hint}")
    return value


def _build_skills_provider(skills_dir: Path | None):
    """Defensive SkillsProvider init.

    Returns ``(provider, skill_count)``. ``provider`` is ``None`` when the
    skills dir is missing/empty or import fails; the agent stays runnable
    with ``context_providers=[]``.
    """
    if skills_dir is None or not skills_dir.is_dir():
        log.warning("Skills dir not found; SkillsProvider disabled.")
        return None, 0
    skill_subdirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
    ]
    if not skill_subdirs:
        log.warning("No SKILL.md under %s; SkillsProvider disabled.", skills_dir)
        return None, 0
    try:
        from agent_framework import SkillsProvider  # type: ignore[import-not-found]

        provider = SkillsProvider.from_paths(skills_dir)
        log.info(
            "SkillsProvider wired with %d skill(s): %s",
            len(skill_subdirs),
            ", ".join(sorted(d.name for d in skill_subdirs)),
        )
        return provider, len(skill_subdirs)
    except Exception as exc:  # noqa: BLE001 - never crash on corrupt skills
        log.warning("SkillsProvider init failed (%s); continuing without it.", exc)
        return None, 0


def _apply_overrides(
    layout: PoCLayout,
    tools: list[Callable[..., Any]],
    stores: dict[str, InMemoryStore],
) -> list[Callable[..., Any]]:
    """Load and call ``tests/quickstart_tools.register(tools, stores)`` if present."""
    override_path = layout.root / "tests" / "quickstart_tools.py"
    if not override_path.exists():
        return tools
    spec = importlib.util.spec_from_file_location(
        "quickstart_tools_override", override_path
    )
    if spec is None or spec.loader is None:
        log.warning("Could not load override at %s", override_path)
        return tools
    module = importlib.util.module_from_spec(spec)
    sys.modules["quickstart_tools_override"] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        log.warning("Override module raised at import time (%s); ignoring.", exc)
        return tools
    register = getattr(module, "register", None)
    if not callable(register):
        log.warning("Override at %s has no register(tools, stores); skipping.", override_path)
        return tools
    try:
        added = register(list(tools), stores) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("Override register() raised (%s); skipping.", exc)
        return tools
    if not isinstance(added, list):
        log.warning("Override register() must return a list of tools; got %r", type(added))
        return tools
    log.info("Override added %d extra tool(s) from %s", len(added), override_path)
    return [*tools, *added]


def build_agent(
    layout: PoCLayout,
    *,
    instructions: str | None = None,
    chat_client: Any | None = None,
) -> tuple[Any, dict[str, InMemoryStore]]:
    """Build a Pattern 0 Agent for the given PoC layout.

    Returns ``(agent, stores)`` so callers (UI, --check, tests) can
    introspect or reset the in-memory state.
    """
    from agent_framework import Agent  # type: ignore[import-not-found]

    client = chat_client if chat_client is not None else build_chat_client()
    tools, stores = build_stub_tools(layout.sample_data_files)
    tools = _apply_overrides(layout, tools, stores)
    skills_provider, skill_count = _build_skills_provider(layout.skills_dir)
    context_providers = [skills_provider] if skills_provider is not None else []

    agent = Agent(
        client=client,
        instructions=instructions or _DEFAULT_INSTRUCTIONS,
        tools=tools,
        context_providers=context_providers,
    )
    log.info(
        "Pattern 0 agent ready · entities=%d skills=%d tools=%d",
        len(stores),
        skill_count,
        len(tools),
    )
    return agent, stores

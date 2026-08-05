"""Canonical offline contract smoke for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Offline contract and pin validation`.
"""

from __future__ import annotations

import inspect
import os
import py_compile
import sys
import tempfile
from contextlib import contextmanager
from collections.abc import Awaitable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_framework import (
    Agent,
    AgentLoopMiddleware,
    AgentModeProvider,
    BaseChatClient,
    ChatOptions,
    ChatResponse,
    ChatResponseUpdate,
    CompactionProvider,
    ContextWindowCompactionStrategy,
    FileAccessProvider,
    FileMemoryProvider,
    InMemoryAgentFileStore,
    InMemoryHistoryProvider,
    Message,
    MessageInjectionMiddleware,
    ResponseStream,
    SkillsProvider,
    TodoProvider,
    ToolApprovalMiddleware,
    ToolResultCompactionStrategy,
    create_harness_agent,
)
from agent_framework_foundry_hosting import ResponsesHostServer


class NeverCalledChatClient(BaseChatClient[ChatOptions[Any]]):
    """Minimal client used only to prove construction never calls a model."""

    model = "offline-construction-only"

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        raise AssertionError("offline construction called the model")


@contextmanager
def isolated_working_directory() -> Iterator[Path]:
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="harness-contract-") as directory:
        target = Path(directory)
        os.chdir(target)
        try:
            yield target
        finally:
            os.chdir(previous)


def provider_types(agent: Agent) -> list[type[Any]]:
    return [type(provider) for provider in agent.context_providers or []]


def middleware_types(agent: Agent) -> list[type[Any]]:
    return [type(middleware) for middleware in agent.middleware or []]


def assert_signature() -> None:
    signature = inspect.signature(create_harness_agent)
    for name in (
        "disable_compaction",
        "disable_todo",
        "disable_mode",
        "disable_file_memory",
        "disable_web_search",
        "disable_tool_auto_approval",
    ):
        assert signature.parameters[name].default is False
    for name in (
        "file_access_store",
        "skills_provider",
        "skills_paths",
        "background_agents",
        "shell_executor",
        "loop_should_continue",
    ):
        assert signature.parameters[name].default is None
    assert signature.parameters["loop_max_iterations"].default == 10
    return_annotation = signature.return_annotation
    assert (
        return_annotation is Agent
        or str(return_annotation).startswith("Agent")
        or getattr(return_annotation, "__origin__", None) is Agent
    )


def assert_defaults(client: NeverCalledChatClient) -> None:
    agent = create_harness_agent(
        client=client,
        disable_web_search=True,
    )
    assert isinstance(agent, Agent)
    providers = provider_types(agent)
    middleware = middleware_types(agent)
    assert providers == [
        InMemoryHistoryProvider,
        TodoProvider,
        AgentModeProvider,
        FileMemoryProvider,
    ]
    assert FileAccessProvider not in providers
    assert SkillsProvider not in providers
    assert CompactionProvider not in providers
    provider_names = {provider.__name__ for provider in providers}
    assert "BackgroundAgentsProvider" not in provider_names
    assert "ShellEnvironmentProvider" not in provider_names
    assert middleware == [ToolApprovalMiddleware, MessageInjectionMiddleware]
    approval = next(
        item
        for item in agent.middleware or []
        if isinstance(item, ToolApprovalMiddleware)
    )
    assert approval.auto_approval_rules == ()


def assert_compaction(client: NeverCalledChatClient) -> None:
    complete = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_web_search=True,
    )
    assert isinstance(
        complete.compaction_strategy,
        ContextWindowCompactionStrategy,
    )
    assert complete.compaction_strategy.max_context_window_tokens == 128_000
    assert complete.compaction_strategy.max_output_tokens == 16_384
    complete_provider = next(
        provider
        for provider in complete.context_providers or []
        if isinstance(provider, CompactionProvider)
    )
    assert complete_provider.before_strategy is None
    assert complete_provider.after_strategy is complete.compaction_strategy
    assert complete.default_options["max_tokens"] == 16_384

    context_only = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        disable_web_search=True,
    )
    assert context_only.compaction_strategy is None
    assert CompactionProvider not in provider_types(context_only)
    output_only = create_harness_agent(
        client=client,
        max_output_tokens=16_384,
        disable_web_search=True,
    )
    assert output_only.compaction_strategy is None
    assert CompactionProvider not in provider_types(output_only)
    assert output_only.default_options["max_tokens"] == 16_384

    before = ToolResultCompactionStrategy()
    after = ToolResultCompactionStrategy()
    before_only = create_harness_agent(
        client=client,
        before_compaction_strategy=before,
        disable_web_search=True,
    )
    assert before_only.compaction_strategy is before
    assert CompactionProvider not in provider_types(before_only)
    after_only = create_harness_agent(
        client=client,
        after_compaction_strategy=after,
        disable_web_search=True,
    )
    assert after_only.compaction_strategy is None
    after_provider = next(
        provider
        for provider in after_only.context_providers or []
        if isinstance(provider, CompactionProvider)
    )
    assert after_provider.before_strategy is None
    assert after_provider.after_strategy is after
    disabled = create_harness_agent(
        client=client,
        before_compaction_strategy=before,
        after_compaction_strategy=after,
        disable_compaction=True,
        disable_web_search=True,
    )
    assert disabled.compaction_strategy is None
    assert CompactionProvider not in provider_types(disabled)


def assert_construction(client: NeverCalledChatClient) -> None:
    file_access = create_harness_agent(
        client=client,
        file_access_store=InMemoryAgentFileStore(),
        disable_web_search=True,
    )
    assert FileAccessProvider in provider_types(file_access)

    skills = create_harness_agent(
        client=client,
        skills_paths=["./offline-skills"],
        disable_web_search=True,
    )
    assert SkillsProvider in provider_types(skills)

    async def stop_loop(**kwargs: Any) -> bool:
        return False

    looped = create_harness_agent(
        client=client,
        loop_should_continue=stop_loop,
        loop_max_iterations=3,
        disable_web_search=True,
    )
    assert middleware_types(looped) == [
        AgentLoopMiddleware,
        ToolApprovalMiddleware,
        MessageInjectionMiddleware,
    ]
    loop = (looped.middleware or [])[0]
    assert isinstance(loop, AgentLoopMiddleware)
    assert loop.max_iterations == 3

    hosted_options = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_web_search=True,
        default_options={"store": False, "max_tokens": 8_192},
    )
    assert hosted_options.default_options["store"] is False
    assert hosted_options.default_options["max_tokens"] == 8_192

    for context_tokens, output_tokens in (
        (0, 100),
        (100, 0),
        (100, -1),
        (100, 100),
    ):
        try:
            create_harness_agent(
                client=client,
                max_context_window_tokens=context_tokens,
                max_output_tokens=output_tokens,
                disable_web_search=True,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("invalid token budgets were accepted")


def assert_reference_imports(compile_dir: Path) -> None:
    reference_dir = Path(__file__).parent
    for name in (
        "local_harness.py",
        "hosted_harness.py",
        "plan_execute.py",
        "session_recovery.py",
    ):
        py_compile.compile(
            str(reference_dir / name),
            cfile=str(compile_dir / f"{Path(name).stem}.pyc"),
            doraise=True,
        )
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        from hosted_harness import build_agent, build_server
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode

    assert callable(build_agent)
    assert callable(build_server)
    assert ResponsesHostServer


def main() -> None:
    if not __debug__:
        raise RuntimeError(
            "offline contract smoke requires assertions; Python optimization is unsupported"
        )
    with isolated_working_directory() as working_directory:
        client = NeverCalledChatClient()
        assert_signature()
        print("HARNESS_SIGNATURE_OK")
        assert_defaults(client)
        print("HARNESS_DEFAULTS_OK")
        assert_compaction(client)
        print("HARNESS_COMPACTION_OK")
        assert_construction(client)
        print("HARNESS_CONSTRUCTION_OK")
        assert_reference_imports(working_directory)
        print("HOSTING_IMPORT_OK")


if __name__ == "__main__":
    main()

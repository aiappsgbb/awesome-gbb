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
    AgentResponse,
    BaseChatClient,
    ChatOptions,
    ChatResponse,
    ChatResponseUpdate,
    CompactionProvider,
    Content,
    ContextProvider,
    ContextWindowCompactionStrategy,
    FileAccessProvider,
    FileMemoryProvider,
    InMemoryAgentFileStore,
    InMemoryHistoryProvider,
    Message,
    MessageInjectionMiddleware,
    ResponseStream,
    SkillsProvider,
    SupportsWebSearchTool,
    TodoProvider,
    ToolApprovalMiddleware,
    ToolResultCompactionStrategy,
    create_harness_agent,
)
from agent_framework_foundry_hosting import ResponsesHostServer
from plan_execute import (
    ToolApprovalRequired,
    build_plan_execute_agents,
    has_pending_tool_approval,
)


class NeverCalledChatClient(BaseChatClient[ChatOptions[Any]]):
    """Minimal client used only to prove construction never calls a model."""

    model = "offline-construction-only"
    web_search_requested = False

    def _inner_get_response(
        self,
        *,
        messages: Sequence[Message],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Awaitable[ChatResponse] | ResponseStream[ChatResponseUpdate, ChatResponse]:
        raise AssertionError("offline construction called the model")

    def get_web_search_tool(self) -> Any:
        self.web_search_requested = True
        raise AssertionError("offline construction enabled web search")


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
    caller_provider = ContextProvider("caller-contract")
    full_pipeline = create_harness_agent(
        client=client,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        file_access_store=InMemoryAgentFileStore(),
        skills_paths=["./offline-skills"],
        context_providers=[caller_provider],
        disable_web_search=True,
    )
    assert provider_types(full_pipeline) == [
        InMemoryHistoryProvider,
        CompactionProvider,
        TodoProvider,
        AgentModeProvider,
        FileMemoryProvider,
        FileAccessProvider,
        SkillsProvider,
        ContextProvider,
    ]
    assert (full_pipeline.context_providers or [])[-1] is caller_provider

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


def assert_plan_execute_construction(client: NeverCalledChatClient) -> None:
    assert isinstance(client, SupportsWebSearchTool)
    agents = build_plan_execute_agents(client)
    assert isinstance(agents.plan, Agent)
    assert isinstance(agents.execute, Agent)

    plan_providers = agents.plan.context_providers or []
    execute_providers = agents.execute.context_providers or []
    assert not any(isinstance(item, AgentModeProvider) for item in plan_providers)
    assert AgentLoopMiddleware not in middleware_types(agents.plan)
    assert any(isinstance(item, AgentModeProvider) for item in execute_providers)
    assert middleware_types(agents.execute) == [
        AgentLoopMiddleware,
        ToolApprovalMiddleware,
        MessageInjectionMiddleware,
    ]
    loop = (agents.execute.middleware or [])[0]
    assert isinstance(loop, AgentLoopMiddleware)
    assert loop.max_iterations == 10

    for provider_type in (InMemoryHistoryProvider, TodoProvider):
        plan_provider = next(
            item for item in plan_providers if isinstance(item, provider_type)
        )
        execute_provider = next(
            item for item in execute_providers if isinstance(item, provider_type)
        )
        assert plan_provider is execute_provider

    plan_memory = next(
        item for item in plan_providers if isinstance(item, FileMemoryProvider)
    )
    execute_memory = next(
        item for item in execute_providers if isinstance(item, FileMemoryProvider)
    )
    assert plan_memory.store is execute_memory.store

    for agent in (agents.plan, agents.execute):
        assert isinstance(agent.compaction_strategy, ContextWindowCompactionStrategy)
        assert agent.compaction_strategy.max_context_window_tokens == 128_000
        assert agent.compaction_strategy.max_output_tokens == 16_384
        compaction_provider = next(
            item
            for item in agent.context_providers or []
            if isinstance(item, CompactionProvider)
        )
        assert compaction_provider.before_strategy is None
        assert compaction_provider.after_strategy is agent.compaction_strategy
        assert agent.default_options["max_tokens"] == 16_384
        assert agent.default_options["tools"] == []
    assert client.web_search_requested is False

    plan_instructions = agents.plan.default_options["instructions"].lower()
    assert "keep todos current" in plan_instructions
    assert "do not execute" in plan_instructions


def assert_pending_approval_contract() -> None:
    approval_response = AgentResponse(
        messages=[
            Message(
                "assistant",
                [Content(type="function_approval_request")],
            )
        ]
    )
    assert approval_response.text == ""
    assert has_pending_tool_approval(approval_response)
    error = ToolApprovalRequired(approval_response)
    assert error.response is approval_response

    text_response = AgentResponse(
        messages=[Message("assistant", [Content(type="text", text="ready")])]
    )
    assert not has_pending_tool_approval(text_response)


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
        assert_plan_execute_construction(client)
        assert_pending_approval_contract()
        print("HARNESS_CONSTRUCTION_OK")
        assert_reference_imports(working_directory)
        print("HOSTING_IMPORT_OK")


if __name__ == "__main__":
    main()

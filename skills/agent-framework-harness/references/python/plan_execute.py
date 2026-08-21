"""Canonical bounded plan-to-execute flow for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Safe plan-to-execute pattern`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agent_framework import (
    Agent,
    AgentResponse,
    InMemoryAgentFileStore,
    InMemoryHistoryProvider,
    TodoProvider,
    create_harness_agent,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
)

from session_recovery import serialize_session

ApprovePlan = Callable[[str], Awaitable[bool]]
PersistSession = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class PlanExecuteAgents:
    plan: Agent
    execute: Agent


class ToolApprovalRequired(RuntimeError):
    def __init__(self, response: AgentResponse) -> None:
        super().__init__("A tool approval response requires host review.")
        self.response = response


def has_pending_tool_approval(response: AgentResponse) -> bool:
    return any(
        content.type == "function_approval_request"
        for message in response.messages
        for content in message.contents
    )


def build_plan_execute_agents(client: Any) -> PlanExecuteAgents:
    history_provider = InMemoryHistoryProvider()
    todo_provider = TodoProvider()
    file_memory_store = InMemoryAgentFileStore()
    plan = create_harness_agent(
        client=client,
        name="bounded-plan-harness",
        agent_instructions=(
            "Plan the requested work, keep todos current, and do not execute the "
            "requested work. Return the plan for host approval."
        ),
        history_provider=history_provider,
        todo_provider=todo_provider,
        file_memory_store=file_memory_store,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_mode=True,
        disable_web_search=True,
    )
    execute = create_harness_agent(
        client=client,
        name="bounded-execute-harness",
        agent_instructions=(
            "Execute only the host-approved plan, keep todos current, and verify "
            "tool results."
        ),
        history_provider=history_provider,
        todo_provider=todo_provider,
        file_memory_store=file_memory_store,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=10,
        disable_web_search=True,
    )
    return PlanExecuteAgents(plan=plan, execute=execute)


async def run_approved_plan(
    *,
    agents: PlanExecuteAgents,
    request: str,
    approve_plan: ApprovePlan,
    persist_session: PersistSession,
) -> str:
    session = agents.plan.create_session()
    set_agent_mode(session, "plan")
    plan_response = await agents.plan.run(
        f"Plan this request without executing it: {request}",
        session=session,
    )
    await persist_session(serialize_session(session))
    if has_pending_tool_approval(plan_response):
        raise ToolApprovalRequired(plan_response)

    if not await approve_plan(plan_response.text):
        return "Plan rejected; execution did not start."

    set_agent_mode(session, "execute")
    await persist_session(serialize_session(session))
    result = await agents.execute.run(
        "Execute the approved plan and complete the remaining todos.",
        session=session,
    )
    await persist_session(serialize_session(session))
    if has_pending_tool_approval(result):
        raise ToolApprovalRequired(result)
    return result.text

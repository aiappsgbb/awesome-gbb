"""Canonical bounded plan-to-execute flow for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Safe plan-to-execute pattern`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from agent_framework import (
    Agent,
    create_harness_agent,
    set_agent_mode,
    todos_remaining,
    todos_remaining_message,
)

from session_recovery import serialize_session

ApprovePlan = Callable[[str], Awaitable[bool]]
PersistSession = Callable[[dict[str, Any]], Awaitable[None]]


def build_plan_execute_agent(client: Any) -> Agent:
    return create_harness_agent(
        client=client,
        name="bounded-plan-execute-harness",
        agent_instructions=(
            "Plan before execution, keep todos current, and verify tool results."
        ),
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        loop_should_continue=todos_remaining(looping_modes=["execute"]),
        loop_next_message=todos_remaining_message,
        loop_max_iterations=10,
        disable_web_search=True,
    )


async def run_approved_plan(
    *,
    agent: Agent,
    request: str,
    approve_plan: ApprovePlan,
    persist_session: PersistSession,
) -> str:
    session = agent.create_session()
    set_agent_mode(session, "plan")
    plan_response = await agent.run(
        f"Plan this request without executing it: {request}",
        session=session,
    )
    await persist_session(serialize_session(session))

    if not await approve_plan(plan_response.text):
        return "Plan rejected; execution did not start."

    set_agent_mode(session, "execute")
    await persist_session(serialize_session(session))
    result = await agent.run(
        "Execute the approved plan and complete the remaining todos.",
        session=session,
    )
    await persist_session(serialize_session(session))
    return result.text

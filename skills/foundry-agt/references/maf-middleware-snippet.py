"""Canonical MAF middleware wiring for Agent Governance Toolkit 4.1.0
with Agent Framework Core 1.13.0.

Source of truth for the prose example in `../../SKILL.md § Wiring snippet`.

The pin validation probe imports this module and constructs an Agent from it
on every refresh.
"""
from __future__ import annotations

from pathlib import Path

from agent_framework import Agent
from agent_os.integrations.maf_adapter import (
    GovernancePolicyMiddleware,
    create_governance_middleware,
)
from agent_os.policies import PolicyEvaluator
from agentmesh.governance import AuditLog


def build_governed_agent(
    *,
    name: str,
    instructions: str,
    chat_client,                                  # your OpenAIChatClient / FoundryChatClient / ...
    policy_dir: str | Path = "policies",
    allowed_tools: list[str] | None = None,
    denied_tools: list[str] | None = None,
    audit_log: AuditLog | None = None,
    tools=None,
) -> Agent:
    """
    Wire AGT governance middleware onto a MAF Agent.

    Returns a ready-to-run Agent with the default two-middleware stack
    (``AuditTrailMiddleware`` + ``GovernancePolicyMiddleware``) assembled
    by ``create_governance_middleware``, plus an explicit
    ``GovernancePolicyMiddleware`` bound to a YAML-loaded
    ``PolicyEvaluator``. ``create_governance_middleware`` adds a third,
    ``CapabilityGuardMiddleware``, only when ``allowed_tools`` or
    ``denied_tools`` is not ``None`` — pass both as ``None`` (this
    function's default) to get the two-middleware stack with no
    capability guard at all.

    Parameters
    ----------
    name, instructions, chat_client, tools : standard MAF Agent ctor args
    policy_dir : path to a directory of ``*.yaml`` policy files
                 (e.g., ``references/policies/`` from this skill)
    allowed_tools / denied_tools : passed to CapabilityGuardMiddleware
    audit_log : optional shared AuditLog; omit to get a fresh in-memory log

    Notes
    -----
    - ``enable_rogue_detection=False`` by default: RogueDetectionMiddleware
      is most useful once the agent has a baselined capability profile
      (see upstream-pin.md for current rogue-detection guidance). Switch
      to True after baselining the agent.
    - The factory's auto-built GovernancePolicyMiddleware is replaced with
      one bound to a PolicyEvaluator we control, so we can inspect
      decisions in tests and CI.
    """
    audit_log = audit_log or AuditLog()

    evaluator = PolicyEvaluator()
    evaluator.load_policies(str(policy_dir))

    stack = create_governance_middleware(
        policy_directory=str(policy_dir),          # factory builds its own evaluator
                                                   # bound to this dir; replaced below
                                                   # with OUR evaluator instance so
                                                   # callers can inspect decisions
        allowed_tools=allowed_tools,               # None means no allowlist (allow
                                                   # every tool not on denied_tools);
                                                   # do NOT coerce to [] — [] means
                                                   # deny-all to CapabilityGuardMiddleware
        denied_tools=denied_tools,
        agent_id=name,
        enable_rogue_detection=False,             # rogue detection is most useful
                                                   # once the agent has a baselined
                                                   # capability profile — see
                                                   # upstream-pin.md
        audit_log=audit_log,
    )

    # Replace the factory's own GovernancePolicyMiddleware with one bound to OUR
    # evaluator instance, IN PLACE at its original factory index. Do NOT
    # filter-then-insert(0, ...) — that would place GovernancePolicyMiddleware
    # ahead of AuditTrailMiddleware and break the documented
    # AuditTrail -> GovernancePolicy -> CapabilityGuard factory order.
    stack = [
        # No agent_id= kwarg here: v4's audit writer reads agent_did from
        # context.agent.name at call time, not from anything passed to
        # this constructor, so an agent_id kwarg would be accepted but
        # silently ignored on this path.
        GovernancePolicyMiddleware(evaluator=evaluator, audit_log=audit_log)
        if isinstance(m, GovernancePolicyMiddleware)
        else m
        for m in stack
    ]

    return Agent(
        chat_client,                              # NB: first positional is `client`, NOT `chat_client=`
        instructions,
        name=name,
        tools=tools,
        middleware=stack,
    )


# ----------------------------------------------------------------------
# Example wiring (Foundry hosted-agent shape)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # Replace with your project's Foundry chat client, e.g.:
    #   from agent_framework.openai import OpenAIChatClient
    #   chat_client = OpenAIChatClient(azure_endpoint=..., model=..., credential=...)
    raise SystemExit(
        "This file is a snippet, not a runnable demo. "
        "Drop build_governed_agent into your hosted-agent module "
        "and pass the FoundryChatClient your azd-deployed project provides."
    )

"""
GBB-verified MAF middleware wiring for the Microsoft Agent Governance
Toolkit (AGT v3.6.0) on top of agent-framework v1.3.0.

This is the **working** version — the upstream Foundry deployment doc
(`docs/deployment/azure-foundry-agent-service.md`) shows manual
construction with kwargs that no longer exist in 3.6.0. Use this
factory instead.

References:
  - upstream-pin.md (this skill) — full API surface + Known Issues
  - https://github.com/microsoft/agent-governance-toolkit/blob/main/
      agent-governance-python/agent-os/src/agent_os/integrations/maf_adapter.py
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
    chat_client,                                  # your AzureOpenAIChatClient / FoundryChatClient / ...
    policy_dir: str | Path = "policies",
    allowed_tools: list[str] | None = None,
    denied_tools: list[str] | None = None,
    audit_log: AuditLog | None = None,
    tools=None,
) -> Agent:
    """
    Wire AGT governance middleware onto a MAF Agent.

    Returns a ready-to-run Agent with the four-layer stack assembled
    by ``create_governance_middleware`` plus an explicit
    ``GovernancePolicyMiddleware`` bound to a YAML-loaded
    ``PolicyEvaluator``.

    Parameters
    ----------
    name, instructions, chat_client, tools : standard MAF Agent ctor args
    policy_dir : path to a directory of ``*.yaml`` policy files
                 (e.g., ``references/policies/`` from this skill)
    allowed_tools / denied_tools : passed to CapabilityGuardMiddleware
    audit_log : optional shared AuditLog; omit to get a fresh in-memory log

    Notes
    -----
    - ``enable_rogue_detection=False`` because RogueDetectionMiddleware
      requires a pre-built capability profile (see Known Issue #4 in
      upstream-pin.md). Switch to True after baselining the agent.
    - The factory's auto-built GovernancePolicyMiddleware is replaced with
      one bound to a PolicyEvaluator we control, so we can inspect
      decisions in tests and CI.
    """
    audit_log = audit_log or AuditLog()

    evaluator = PolicyEvaluator()
    evaluator.load_policies(str(policy_dir))

    stack = create_governance_middleware(
        policy_directory=None,                    # we attach our own evaluator below
        allowed_tools=allowed_tools or [],
        denied_tools=denied_tools or [],
        agent_id=name,
        enable_rogue_detection=False,             # see upstream-pin.md Known Issue #4
        audit_log=audit_log,
    )

    # Replace the factory's policy mw with one bound to OUR evaluator
    stack = [m for m in stack if not isinstance(m, GovernancePolicyMiddleware)]
    stack.insert(0, GovernancePolicyMiddleware(evaluator=evaluator, audit_log=audit_log))

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
    #   from agent_framework.azure import AzureOpenAIChatClient
    #   chat_client = AzureOpenAIChatClient(...)
    raise SystemExit(
        "This file is a snippet, not a runnable demo. "
        "Drop build_governed_agent into your hosted-agent module "
        "and pass the FoundryChatClient your azd-deployed project provides."
    )

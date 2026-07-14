"""Canonical FoundryAgent timeout parameter usage (MAF 1.8.0).

Source of truth for the prose example in
`../../SKILL.md § FoundryAgent timeout parameter (MAF 1.8.0)`.

Demonstrates the new `timeout: float | None = None` kwarg on
`agent_framework.foundry.FoundryAgent` (added in MAF 1.8.0). Per the
upstream docstring this is the HTTP transport timeout — it overrides
the OpenAI-SDK default of connect: 5s, total: 600s. It is NOT a
run-loop / per-invocation envelope; it is the underlying request
timeout the OpenAI client uses.

This kwarg lives on the CALLER-side `FoundryAgent` class (orchestrator
code calling a hosted agent). The CONTAINER-side runtime for hosted
agents (covered in SKILL.md § Runtime Pattern) uses `FoundryChatClient`
directly and does NOT accept `timeout=` in 1.8.0 — apply HTTP-layer
transport timeouts on the underlying client instead.

Requires:
- agent-framework-core ~= 1.11.0
- agent-framework-foundry ~= 1.10.1
- azure-ai-projects ~= 2.3.0
- azure-identity ~= 1.25.3
- Environment variables: FOUNDRY_PROJECT_ENDPOINT, AGENT_NAME

Usage:
    export FOUNDRY_PROJECT_ENDPOINT=https://<acct>.services.ai.azure.com/api/projects/<proj>
    export AGENT_NAME=my-agent
    python foundry_agent_timeout.py
"""

from __future__ import annotations

import asyncio
import os

from agent_framework.foundry import FoundryAgent
from azure.identity import DefaultAzureCredential


async def main() -> None:
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    agent_name = os.environ["AGENT_NAME"]

    # The MAF 1.8.0 `timeout` kwarg overrides the OpenAI-SDK transport
    # default (connect: 5s, total: 600s). 30s is a reasonable ceiling
    # for user-facing chat budgets; tune to your p99 + headroom.
    agent = FoundryAgent(
        project_endpoint=endpoint,
        agent_name=agent_name,
        credential=DefaultAzureCredential(),
        timeout=30.0,  # NEW in MAF 1.8.0
    )

    try:
        response = await agent.run("What is the current order status?")
        print(response.text)
    except (TimeoutError, asyncio.TimeoutError):
        # Surface to the caller as a 504 / retry signal rather than
        # letting the underlying HTTP call hang up to the default 600s.
        print("agent run exceeded 30s envelope; failing fast")
        raise


if __name__ == "__main__":
    asyncio.run(main())

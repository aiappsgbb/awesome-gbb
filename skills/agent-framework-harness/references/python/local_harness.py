"""Canonical local Agent Framework Harness construction.

Source of truth for the prose example in
`../../SKILL.md § Canonical local Python recipe`.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from agent_framework import FileSystemAgentFileStore, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from azure.identity.aio import AzureCliCredential


async def main() -> None:
    async with AzureCliCredential() as credential:
        client = FoundryChatClient(
            project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            credential=credential,
        )
        agent = create_harness_agent(
            client=client,
            name="local-harness",
            agent_instructions=(
                "Plan carefully, verify tool results, and report the final outcome."
            ),
            max_context_window_tokens=128_000,
            max_output_tokens=16_384,
            file_memory_store=FileSystemAgentFileStore(
                (Path.cwd() / ".agent-memory").resolve()
            ),
            disable_web_search=True,
        )
        session = agent.create_session()
        response = await agent.run(
            "Create a short plan for validating this harness configuration.",
            session=session,
        )
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())

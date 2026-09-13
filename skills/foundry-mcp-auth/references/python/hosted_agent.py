"""Canonical minimal consumer of the upstream Foundry Toolbox wrapper.

Source of truth for `../../SKILL.md § Agent integration`.
No token broker, custom transport, or speculative late-consent adapter.
"""

import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import FoundryToolbox, ResponsesHostServer
from azure.identity.aio import ManagedIdentityCredential

from .agent_instructions import INSTRUCTIONS


async def main():
    # This credential authenticates only to Foundry, NEVER directly to the custom MCP.
    async with ManagedIdentityCredential() as credential:
        toolbox = FoundryToolbox(credential)
        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
                credential=credential,
            ),
            tools=[toolbox],
            instructions=INSTRUCTIONS,
            default_options={"store": False},
        )
        await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())

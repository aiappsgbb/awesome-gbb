"""Canonical no-tools Responses BASIC runtime.

Source of truth for `../../SKILL.md § Private BASIC consumer`.
Adapted from the official 01-basic sample pinned in ../private-basic.md.
"""

import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential


def main():
    model = os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"]
    if not model.strip():
        raise ValueError("AZURE_AI_MODEL_DEPLOYMENT_NAME must name an existing deployment")
    with DefaultAzureCredential() as credential:
        agent = Agent(
            client=FoundryChatClient(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                model=model,
                credential=credential,
            ),
            instructions="You are a friendly assistant. Keep your answers brief.",
            default_options={"store": False},
        )
        ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()

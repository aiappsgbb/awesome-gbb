"""Canonical Agent Framework Harness wiring for Foundry Hosted Agents.

Source of truth for the prose example in
`../../SKILL.md § Canonical Foundry Hosted recipe`.
"""

from __future__ import annotations

import os

from agent_framework import Agent, InMemoryHistoryProvider, create_harness_agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import DefaultAzureCredential


def build_agent(
    *,
    project_endpoint: str | None = None,
    model: str | None = None,
    credential: AsyncTokenCredential | None = None,
) -> Agent:
    client = FoundryChatClient(
        project_endpoint=project_endpoint or os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=model or os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=credential or DefaultAzureCredential(),
    )
    # ResponsesHostServer owns transcript history, so the harness must not load or persist it.
    history_provider = InMemoryHistoryProvider(
        load_messages=False,
        store_inputs=False,
        store_outputs=False,
    )
    return create_harness_agent(
        client=client,
        name="hosted-harness",
        agent_instructions="Complete the caller's task and return a concise result.",
        history_provider=history_provider,
        max_context_window_tokens=128_000,
        max_output_tokens=16_384,
        disable_mode=True,
        disable_file_memory=True,
        disable_web_search=True,
        default_options={"store": False},
    )


def build_server(agent: Agent | None = None) -> ResponsesHostServer:
    return ResponsesHostServer(agent or build_agent())


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()

# Canonical hosted-agent main.py — MAF + FoundryChatClient pattern.
#
# This is the field-validated reference shape for a Foundry hosted agent on
# the GA container-deploy path. It is the SOURCE OF TRUTH for the prose
# example in `../../SKILL.md § Runtime Pattern (MAF Variant)`. When the SKILL
# prose drifts from this file (or vice-versa), update both in the same commit.
#
# Pre-conditions consumed from the platform-injected environment:
#   FOUNDRY_PROJECT_ENDPOINT          (platform-injected at container start; NEVER declare in azure.yaml)
#   AZURE_AI_MODEL_DEPLOYMENT_NAME     (declared in azure.yaml's env map — see ../yaml/azure.yaml)
#
# Why each line matters:
#   - `model=` MUST be passed explicitly to FoundryChatClient. The runtime
#     injects the agent's Entra identity into the container but the SDK does
#     NOT auto-pick a model unless `model=` is supplied — agent boot fails at
#     import otherwise.
#   - `credential=DefaultAzureCredential()` MUST be passed explicitly for the
#     same reason — runtime identity injection != SDK auto-detection.
#   - `@tool(approval_mode="never_require")` is what registers a Python function
#     as a tool. Bare `def my_tool` will not get called.
#   - `default_options={"store": False}` — platform manages session history; if
#     you leave the default, you get duplicate-history bugs in long sessions.

import os
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity.aio import DefaultAzureCredential
from pydantic import Field

client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
    credential=DefaultAzureCredential(),
)


@tool(approval_mode="never_require")
def my_tool(query: Annotated[str, Field(description="Input")]) -> str:
    """Tool description — the model reads this to decide when to invoke."""
    return "result"


agent = Agent(
    client=client,
    instructions="You are a helpful assistant.",
    tools=[my_tool],
    default_options={"store": False},  # Platform manages history
)

server = ResponsesHostServer(agent)
server.run()  # Serves on port 8088

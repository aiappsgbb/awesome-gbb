"""Hosted half of the Jobs CI protocol smoke; not a deployment orchestrator."""
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential as SyncCredential
from azure.identity.aio import DefaultAzureCredential as AsyncCredential


def main():
    credential = SyncCredential()
    token = credential.get_token(os.environ["MCP_AUTH_AUDIENCE"]).token
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=AsyncCredential(),
    )
    tool = client.get_mcp_tool(
        name="ACA Jobs", url=os.environ["MCP_SERVER_URL"],
        headers={"Authorization": "Bearer " + token}, approval_mode="never_require",
    )
    agent = Agent(
        client=client,
        instructions="Call start_aca_job once, then get_aca_job_status with its taskId. "
                     "Use the requested inputRef exactly. Do not emit the verification marker as assistant text.",
        tools=[tool], default_options={"store": False},
    )
    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()

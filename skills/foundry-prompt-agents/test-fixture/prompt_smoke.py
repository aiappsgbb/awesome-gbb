"""Canonical SDK 2.4 classifier fixture; called by the Copilot consumer."""

import os
from pathlib import Path
import uuid

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from openai import NotFoundError


def smoke(project, openai):
    name = f"ci-smoke-pa-{uuid.uuid4().hex[:8]}"
    created = None
    conversation = None
    try:
        created = project.agents.create_version(
            agent_name=name,
            definition=PromptAgentDefinition(
                model="gpt-5.4-mini",
                instructions="Return exactly one label: billing, technical, or account.",
            ),
        )
        print(f"AGENT_CREATED name={created.name} version={created.version}", flush=True)
        conversation = openai.conversations.create()
        response = openai.responses.create(
            conversation=conversation.id,
            extra_body={"agent_reference": {
                "name": created.name, "version": created.version, "type": "agent_reference",
            }},
            input="I was charged twice for this month's subscription.",
        )
        label = response.output_text.strip().lower()
        if label not in {"billing", "technical", "account"}:
            raise ValueError("Invalid classifier label")
        print(f"CLASSIFIER_LABEL={label}", flush=True)
    finally:
        try:
            if conversation is not None:
                openai.conversations.delete(conversation.id)
                try:
                    openai.conversations.retrieve(conversation.id)
                except NotFoundError:
                    print("CONVERSATION_ABSENT_VERIFIED", flush=True)
                else:
                    raise RuntimeError("Conversation deletion not verified")
        finally:
            if created is not None:
                project.agents.delete_version(created.name, created.version)
                try:
                    project.agents.get_version(created.name, created.version)
                except ResourceNotFoundError:
                    print(f"AGENT_VERSION_ABSENT_VERIFIED name={created.name} version={created.version}", flush=True)
                else:
                    raise RuntimeError("Agent version deletion not verified")


def main():
    marker = Path("/tmp/foundry-prompt-agents-smoke-result")
    marker.write_text("SMOKE_RESULT=FAIL execution incomplete\n", encoding="utf-8")
    try:
        with (
            DefaultAzureCredential() as credential,
            AIProjectClient(endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                            credential=credential) as project,
            project.get_openai_client() as openai,
        ):
            smoke(project, openai)
    except Exception as error:
        # Never print SDK exception text: it can include URLs, headers or payloads.
        code = type(error).__name__
        marker.write_text(f"SMOKE_RESULT=FAIL {code}\n", encoding="utf-8")
        print(f"PROMPT_SMOKE_FAILED error_type={code}", flush=True)
        return 1
    marker.write_text("SMOKE_RESULT=PASS\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

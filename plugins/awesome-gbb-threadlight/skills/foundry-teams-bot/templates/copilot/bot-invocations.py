"""Teams bot that streams from a Foundry Hosted Agent via Invocations SSE protocol.

Use this variant when your agent uses GHCP SDK with InvocationAgentServerHost.
The standard oai.responses.create() pattern does NOT work with Invocations agents —
the Responses API endpoint returns 400 ("responses protocol not declared").

This bot calls the Invocations SSE endpoint directly and parses streaming events.
"""

import json
import logging
import os
import asyncio
import traceback

import aiohttp
from dotenv import load_dotenv
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient

from microsoft_agents.hosting.core import (
    Authorization,
    AgentApplication,
    TurnState,
    TurnContext,
    MemoryStorage,
)
from microsoft_agents.hosting.aiohttp import CloudAdapter
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.activity import load_configuration_from_env

agents_sdk_config = load_configuration_from_env(os.environ)

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_NAME = os.environ.get("AGENT_NAME", "__PROJECT_NAME__")
PROJECT_ENDPOINT = os.environ.get("PROJECT_ENDPOINT", "")

if not PROJECT_ENDPOINT or PROJECT_ENDPOINT == "":
    raise ValueError("PROJECT_ENDPOINT env var is required")
if AGENT_NAME == "__PROJECT_NAME__":
    logger.warning("AGENT_NAME still has placeholder value — update agent.yaml or env var")


async def _invoke_invocations(endpoint: str, credential, agent_name: str, query: str) -> str:
    """Invoke agent via Invocations SSE endpoint and return response text.

    Parses both assistant.message (complete) and assistant.message_delta
    (streaming chunks) events. Prefers complete message when available.

    This is the ONLY way to call an agent that uses Invocations protocol
    (GHCP SDK + InvocationAgentServerHost). The Responses API
    (oai.responses.create) returns 400 for such agents.
    """
    token = await credential.get_token("https://ai.azure.com/.default")
    url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"

    message_text = ""
    delta_text = ""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"input": query},
            headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
                "Foundry-Features": "HostedAgents=V1Preview",
            },
            timeout=aiohttp.ClientTimeout(total=600),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Invocations endpoint returned {resp.status}: {body[:500]}")

            async for line_bytes in resp.content:
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                    event_type = event.get("type", "")
                    content = event.get("data", {}).get("content", "")

                    if event_type == "assistant.message" and content:
                        message_text += content
                    elif event_type == "assistant.message_delta" and content:
                        delta_text += content
                except json.JSONDecodeError:
                    continue

    return message_text if message_text else delta_text


def _friendly_error(raw: str) -> str:
    """Convert raw agent errors into user-friendly messages."""
    lower = raw.lower()
    if "content_filter" in lower or "content management policy" in lower:
        return "⚠️ Your message was flagged by the content safety filter. Please try rephrasing."
    if "permissiondenied" in lower or "401" in lower or "403" in lower:
        return "🔒 The agent doesn't have the right permissions yet. Please contact the administrator."
    if "timeout" in lower or "timed out" in lower:
        return "⏱️ The request timed out. The agent may be warming up — please try again in a moment."
    if "rate limit" in lower or "429" in lower:
        return "⏳ Too many requests — please wait a moment and try again."
    if len(raw) > 300:
        return f"⚠️ An error occurred: {raw[:250]}…"
    return f"⚠️ An error occurred: {raw}"


async def setup() -> tuple[AgentApplication[TurnState], MsalConnectionManager]:
    """Create bot app that calls agent via Invocations SSE endpoint."""
    STORAGE = MemoryStorage()
    CONNECTION_MANAGER = MsalConnectionManager(**agents_sdk_config)
    ADAPTER = CloudAdapter(connection_manager=CONNECTION_MANAGER)
    AUTHORIZATION = Authorization(STORAGE, CONNECTION_MANAGER, **agents_sdk_config)

    credential = DefaultAzureCredential()
    project_client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
        allow_preview=True,
    )

    # Verify agent exists (retry — RBAC may still be propagating)
    agent = None
    for attempt in range(5):
        try:
            agent = await project_client.agents.get(agent_name=AGENT_NAME)
            break
        except Exception as exc:
            logger.warning("Agent lookup attempt %d/5 failed: %s", attempt + 1, exc)
            if attempt < 4:
                await asyncio.sleep(min(10 * (attempt + 1), 30))
    if agent is None:
        raise RuntimeError(f"Agent '{AGENT_NAME}' not reachable after 5 attempts")

    AGENT_APP = AgentApplication[TurnState](
        storage=STORAGE,
        adapter=ADAPTER,
        authorization=AUTHORIZATION,
        **agents_sdk_config,
    )

    @AGENT_APP.activity("message")
    async def on_message(context: TurnContext, state: TurnState):
        user_message = (context.activity.text or "").strip()
        if not user_message:
            return
        logger.info("Received message: %s", user_message)

        if user_message.lower() == "!reset":
            await context.send_activity("🔄 Conversation reset.")
            return

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response_text = await _invoke_invocations(
                    PROJECT_ENDPOINT, credential, AGENT_NAME, user_message,
                )

                if response_text:
                    await context.send_activity(response_text)
                else:
                    await context.send_activity(
                        "🤔 I processed your request but didn't receive a text response."
                    )
                break

            except Exception as e:
                logger.error("Error (attempt %d): %s\n%s", attempt + 1, e, traceback.format_exc())
                if attempt < max_retries - 1:
                    continue
                await context.send_activity(_friendly_error(str(e)))
                break

    return AGENT_APP, CONNECTION_MANAGER

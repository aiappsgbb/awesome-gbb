"""Teams bot that streams from a Foundry Hosted Agent."""

import logging
import os
import asyncio
import aiohttp
import traceback

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

# Fail fast on missing critical config
if not PROJECT_ENDPOINT or PROJECT_ENDPOINT == "":
    raise ValueError("PROJECT_ENDPOINT env var is required")
if AGENT_NAME == "__PROJECT_NAME__":
    logger.warning("AGENT_NAME still has placeholder value — update agent.yaml or env var")
REPORT_EXTENSIONS = {".html", ".csv", ".md", ".json"}


async def _send_session_files(context: TurnContext, session_id: str):
    """Check for report files in the agent session and send to Teams."""
    try:
        cred = DefaultAzureCredential()
        token = await cred.get_token("https://ai.azure.com/.default")
        await cred.close()

        headers = {
            "Authorization": f"Bearer {token.token}",
            "Foundry-Features": "HostedAgents=V1Preview",
        }

        async with aiohttp.ClientSession() as http:
            list_url = f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions/{session_id}/files?api-version=v1&path=."
            async with http.get(list_url, headers=headers) as resp:
                if resp.status != 200:
                    return
                files_data = await resp.json()

            for entry in files_data.get("entries", []):
                name = entry.get("name", "")
                ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
                if ext not in REPORT_EXTENSIONS:
                    continue

                dl_url = f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions/{session_id}/files/content?api-version=v1&path={name}"
                async with http.get(dl_url, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.read()

                if len(content) < 28000:
                    text = content.decode("utf-8", errors="replace")
                    if ext == ".html":
                        await context.send_activity(
                            f"📎 **{name}** ({len(content):,} bytes)\n\n"
                            f"Copy the content below and save as `{name}` to open in your browser:\n\n"
                            f"```html\n{text[:20000]}\n```"
                        )
                    else:
                        await context.send_activity(
                            f"📎 **{name}** ({len(content):,} bytes)\n\n```\n{text[:20000]}\n```"
                        )
                else:
                    await context.send_activity(
                        f"📎 **{name}** ({len(content):,} bytes) — too large for inline display. "
                        f"Download via: `azd ai agent files download --file {name}`"
                    )
                logger.info("Sent file: %s (%d bytes)", name, len(content))
    except Exception as exc:
        logger.warning("Could not send session files: %s", exc)


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
    """Create bot app with Foundry agent client."""
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

    oai_client = project_client.get_openai_client(agent_name=AGENT_NAME)

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

        # !reset — clear conversation
        if user_message.lower() == "!reset":
            state.set_value("ConversationState.thread_id", "")
            await context.send_activity("🔄 Conversation reset. Send a new message to start fresh.")
            return

        max_retries = 2
        for attempt in range(max_retries):
            thread_id = state.get_value(
                "ConversationState.thread_id", lambda: "", target_cls=str
            )

            if not thread_id:
                thread = await oai_client.conversations.create()
                thread_id = thread.id
                state.set_value("ConversationState.thread_id", thread_id)

            try:
                stream = await oai_client.responses.create(
                    conversation=thread_id,
                    input=user_message,
                    stream=True,
                )

                collected_text: list[str] = []
                error_msg = None
                session_id = None
                server_error = False

                async for event in stream:
                    event_type = getattr(event, "type", None)

                    if event_type == "response.output_text.delta":
                        chunk = getattr(event, "delta", "")
                        if chunk:
                            collected_text.append(chunk)
                    elif event_type == "response.output_text.done":
                        text = getattr(event, "text", "")
                        if text and not collected_text:
                            collected_text.append(text)
                    elif event_type == "error":
                        error_msg = getattr(event, "message", None) or str(event)
                        logger.error("Agent error: %s", error_msg)
                    elif event_type == "response.failed":
                        if not error_msg:
                            resp = getattr(event, "response", None)
                            if resp:
                                err = getattr(resp, "error", None)
                                if err and getattr(err, "code", "") == "server_error":
                                    server_error = True
                                error_msg = getattr(resp, "status_details", None) or str(resp)
                            else:
                                error_msg = str(event)
                        logger.error("Response failed: %s", error_msg)
                        break
                    elif event_type == "response.completed":
                        response = getattr(event, "response", None)
                        if response:
                            session_id = getattr(response, "agent_session_id", None)
                            if not collected_text:
                                for item in getattr(response, "output", []):
                                    for content in getattr(item, "content", []):
                                        t = getattr(content, "text", "")
                                        if t:
                                            collected_text.append(t)
                        break

                final_text = "".join(collected_text).strip()

                # On server_error, reset conversation and retry
                if server_error and not final_text and attempt < max_retries - 1:
                    logger.warning("Server error — resetting conversation (attempt %d)", attempt + 1)
                    state.set_value("ConversationState.thread_id", "")
                    continue

                if final_text:
                    await context.send_activity(final_text)
                elif error_msg:
                    await context.send_activity(_friendly_error(error_msg))
                else:
                    await context.send_activity(
                        "🤔 I processed your request but didn't receive a text response."
                    )

                # Send session files if any
                if session_id and final_text:
                    await _send_session_files(context, session_id)
                break

            except Exception as e:
                logger.error("Error: %s\n%s", e, traceback.format_exc())
                if attempt < max_retries - 1:
                    state.set_value("ConversationState.thread_id", "")
                    continue
                await context.send_activity(_friendly_error(str(e)))
                break

    return AGENT_APP, CONNECTION_MANAGER

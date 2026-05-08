"""Teams bot that streams from a Foundry Hosted Agent."""

import json
import logging
import os
import traceback

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from microsoft_agents.activity import Activity, ActivityTypes
from microsoft_agents.hosting.core import (
    AgentApplication,
    ConversationState,
    MemoryStorage,
    TurnContext,
    TurnState,
)

logger = logging.getLogger(__name__)

AGENT_NAME = os.getenv("AGENT_NAME", "__PROJECT_NAME__")
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")


class AgentBot(AgentApplication):
    """Teams bot that forwards messages to a Foundry Hosted Agent."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._storage = MemoryStorage()
        self._conversation_state = ConversationState(self._storage)
        self.on_activity(ActivityTypes.message, self._on_message)

    async def _on_message(self, context: TurnContext, state: TurnState) -> bool:
        """Handle incoming Teams message."""
        user_message = context.activity.text or ""
        if not user_message.strip():
            return True

        # Extract user identity from Teams activity
        user = context.activity.from_property
        user_name = user.name if user else "Unknown"
        agent_input = f"[User: {user_name}] {user_message}"

        # Handle reset command
        if user_message.strip().lower() == "!reset":
            state["thread_id"] = None
            await context.send_activity(
                "🔄 Conversation reset. Send a new message to start fresh."
            )
            return True

        try:
            async with DefaultAzureCredential() as credential:
                async with AIProjectClient(
                    endpoint=PROJECT_ENDPOINT,
                    credential=credential,
                    allow_preview=True,  # REQUIRED for agent_name
                ) as project_client:
                    # Agent-bound client — routes to dedicated endpoint
                    oai = project_client.get_openai_client(
                        agent_name=AGENT_NAME
                    )

                    # Stream response from Foundry Hosted Agent
                    collected_text = []
                    stream = oai.responses.create(
                        input=agent_input,
                        stream=True,
                    )

                    async for event in await stream:
                        if hasattr(event, "type"):
                            if event.type == "response.output_text.delta":
                                collected_text.append(event.delta)
                            elif event.type == "response.failed":
                                error = getattr(event.response, "error", None)
                                msg = _friendly_error(error)
                                await context.send_activity(msg)
                                return True

                    # Send collected response as single message
                    full_response = "".join(collected_text).strip()
                    if full_response:
                        await context.send_activity(full_response)
                    else:
                        await context.send_activity(
                            "🤔 I processed your request but didn't "
                            "generate a text response."
                        )

        except Exception as e:
            error_code = getattr(e, "code", "") or ""
            if "server_error" in str(error_code).lower():
                # Stale conversation — reset and retry
                state["thread_id"] = None
                logger.warning("server_error — resetting conversation")
                return await self._on_message(context, state)

            logger.error(
                "Error processing message: %s\n%s", e, traceback.format_exc()
            )
            await context.send_activity(
                "⚠️ Something went wrong. Please try again, "
                "or type **!reset** to start a fresh conversation."
            )

        return True


def _friendly_error(error) -> str:
    """Convert Foundry error to user-friendly message."""
    if not error:
        return "⚠️ An unexpected error occurred. Please try again."

    code = getattr(error, "code", "")
    msg = getattr(error, "message", str(error))

    if "content_filter" in code.lower() or "content_filter" in msg.lower():
        return "🚫 Your message was filtered by content safety policies. Please rephrase."
    if "rate_limit" in code.lower() or "429" in msg:
        return "⏳ The service is currently busy. Please wait a moment and try again."
    if "timeout" in code.lower():
        return "⏰ The request timed out. Please try a shorter question."

    return f"⚠️ Error: {msg}"

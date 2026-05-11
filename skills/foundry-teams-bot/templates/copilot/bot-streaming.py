"""Teams bot with progressive streaming for Foundry Hosted Agents.

Supports both agent protocols:
  - Responses API (MAF agents using ResponsesHostServer)
  - Invocations SSE (GHCP SDK agents using InvocationAgentServerHost)

Features:
  - Teams-native streaming via context.streaming_response
  - Tool call status updates (🔧 Browsing, 🔍 Searching, etc.)
  - FileConsentCard flow for agent-generated reports (OneDrive upload)
  - Dual protocol support via AGENT_PROTOCOL env var

Set AGENT_PROTOCOL env var to "responses" or "invocations" (default: "invocations").
"""

import json
import logging
import os
import asyncio
import traceback
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator, Union

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
from microsoft_agents.activity import (
    load_configuration_from_env,
    Activity,
    ActivityTypes,
    Attachment,
    InvokeResponse,
)

agents_sdk_config = load_configuration_from_env(os.environ)

load_dotenv()

logger = logging.getLogger(__name__)

AGENT_NAME = os.environ.get("AGENT_NAME", "bat-scraper")
PROJECT_ENDPOINT = os.environ.get("PROJECT_ENDPOINT", "")
AGENT_PROTOCOL = os.environ.get("AGENT_PROTOCOL", "responses").lower()
REPORT_EXTENSIONS = {".xlsx", ".csv", ".html", ".json", ".md", ".txt", ".pdf"}

if AGENT_NAME == "__PROJECT_NAME__":
    logger.warning("AGENT_NAME still has placeholder value")

if not PROJECT_ENDPOINT:
    raise ValueError("PROJECT_ENDPOINT env var is required")

# Pending files awaiting user consent (file_id → (filename, bytes))
_pending_files: dict[str, tuple[str, bytes]] = {}


# ---------------------------------------------------------------------------
# Stream event types
# ---------------------------------------------------------------------------

@dataclass
class TextChunk:
    """Text content to stream to Teams."""
    text: str

@dataclass
class StatusUpdate:
    """Informative status update (shown as typing indicator)."""
    text: str

@dataclass
class SessionComplete:
    """Signal that the agent session has a session_id for file retrieval."""
    session_id: str

StreamEvent = Union[TextChunk, StatusUpdate, SessionComplete]


# ---------------------------------------------------------------------------
# Protocol-specific streaming generators
# ---------------------------------------------------------------------------

async def _stream_responses(oai_client, thread_id: str, query: str) -> AsyncGenerator[StreamEvent, None]:
    """Yield events from Responses API streaming (MAF agents)."""
    stream = await oai_client.responses.create(
        conversation=thread_id,
        input=query,
        stream=True,
    )

    tool_count = 0
    async for event in stream:
        event_type = getattr(event, "type", None)

        if event_type == "response.output_text.delta":
            chunk = getattr(event, "delta", "")
            if chunk:
                yield TextChunk(chunk)
        elif event_type == "response.output_text.done":
            text = getattr(event, "text", "")
            if text:
                yield TextChunk(text)
        elif event_type == "response.function_call_arguments.start":
            tool_count += 1
            name = getattr(event, "name", "tool")
            yield StatusUpdate(f"🔧 Calling {name}... ({tool_count})")
        elif event_type == "response.mcp_call.in_progress":
            tool_count += 1
            name = getattr(event, "name", None) or "tool"
            yield StatusUpdate(f"🔧 Using {name}... ({tool_count})")
        elif event_type == "response.mcp_call.completed":
            yield StatusUpdate(f"✅ Done ({tool_count})")
        elif event_type == "response.completed":
            resp = getattr(event, "response", None)
            if resp:
                sid = getattr(resp, "agent_session_id", None)
                if sid:
                    yield SessionComplete(sid)
        elif event_type == "response.failed":
            resp = getattr(event, "response", None)
            err = getattr(resp, "error", None) if resp else None
            code = getattr(err, "code", "") if err else ""
            if code == "server_error":
                raise RuntimeError("server_error")
            msg = getattr(resp, "status_details", None) or str(resp) if resp else str(event)
            raise RuntimeError(msg)


async def _stream_invocations(
    endpoint: str, credential, agent_name: str, query: str
) -> AsyncGenerator[StreamEvent, None]:
    """Yield events from Invocations SSE endpoint (GHCP SDK agents).

    Emits StatusUpdate for tool calls so Teams shows progress during
    long tool loops (web search, Playwright browsing, etc.).
    """
    token = await credential.get_token("https://ai.azure.com/.default")
    url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"

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
                raise RuntimeError(f"Invocations returned {resp.status}: {body[:500]}")

            tool_count = 0
            async for line_bytes in resp.content:
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                    event_type = event.get("type", "")
                    data = event.get("data", {})
                    content = data.get("content", "")

                    if event_type == "assistant.message_delta" and content:
                        yield TextChunk(content)
                    elif event_type == "assistant.message" and content:
                        yield TextChunk(content)
                    elif event_type == "tool.execution_start":
                        tool_count += 1
                        tool_name = data.get("toolName", "tool")
                        args = data.get("arguments", {})
                        if tool_name in ("web_fetch", "browser_navigate") and args.get("url"):
                            domain = args["url"].split("//")[-1].split("/")[0]
                            label = f"🌐 Browsing {domain}"
                        elif tool_name == "web_search" and args.get("query"):
                            label = f"🔍 Searching: {args['query'][:60]}"
                        elif tool_name == "browser_snapshot":
                            label = "📸 Reading page content"
                        elif tool_name == "browser_click":
                            label = "🖱️ Clicking element"
                        elif tool_name == "report_intent":
                            label = f"📋 {args.get('intent', 'Planning')}"
                        else:
                            label = f"🔧 {tool_name}"
                        yield StatusUpdate(f"{label} ({tool_count})")
                    elif event_type == "tool.execution_complete":
                        ok = "✅" if data.get("success") else "⚠️"
                        yield StatusUpdate(f"{ok} Done ({tool_count})")
                    elif event_type == "permission.requested":
                        yield StatusUpdate(f"🔐 Requesting permission... ({tool_count})")
                    elif event_type == "permission.completed":
                        yield StatusUpdate(f"✅ Permission granted ({tool_count})")
                    elif event_type == "assistant.turn_start":
                        yield StatusUpdate("🤔 Thinking...")
                    elif event_type == "assistant.reasoning_delta":
                        if content and tool_count == 0:
                            yield StatusUpdate("🤔 Analyzing...")
                except json.JSONDecodeError:
                    continue


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------

def _friendly_error(raw: str) -> str:
    lower = raw.lower()
    if "content_filter" in lower or "content management policy" in lower:
        return "⚠️ Your message was flagged by the content safety filter. Please try rephrasing."
    if "permissiondenied" in lower or "401" in lower or "403" in lower:
        return "🔒 The agent doesn't have the right permissions yet. Please contact the administrator."
    if "timeout" in lower or "timed out" in lower:
        return "⏱️ The request timed out. The agent may be warming up — please try again."
    if "rate limit" in lower or "429" in lower:
        return "⏳ Too many requests — please wait and try again."
    if len(raw) > 300:
        return f"⚠️ An error occurred: {raw[:250]}…"
    return f"⚠️ An error occurred: {raw}"


# ---------------------------------------------------------------------------
# File delivery via FileConsentCard
# ---------------------------------------------------------------------------

async def _send_session_files(context: TurnContext, session_id: str):
    """Download agent-generated files and offer via FileConsentCard."""
    try:
        cred = DefaultAzureCredential()
        token = await cred.get_token("https://ai.azure.com/.default")
        await cred.close()

        headers = {
            "Authorization": f"Bearer {token.token}",
            "Foundry-Features": "HostedAgents=V1Preview",
        }

        async with aiohttp.ClientSession() as http:
            list_url = (
                f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions"
                f"/{session_id}/files?api-version=v1&path=."
            )
            async with http.get(list_url, headers=headers) as resp:
                if resp.status != 200:
                    return
                files_data = await resp.json()

            for entry in files_data.get("entries", []):
                name = entry.get("name", "")
                ext = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
                if ext not in REPORT_EXTENSIONS:
                    continue

                dl_url = (
                    f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions"
                    f"/{session_id}/files/content?api-version=v1&path={name}"
                )
                async with http.get(dl_url, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    content = await resp.read()

                file_id = str(uuid.uuid4())
                _pending_files[file_id] = (name, content)

                consent_card = Attachment(
                    content_type="application/vnd.microsoft.teams.card.file.consent",
                    name=name,
                    content={
                        "description": f"Agent-generated report ({len(content):,} bytes)",
                        "sizeInBytes": len(content),
                        "acceptContext": {"file_id": file_id, "filename": name},
                        "declineContext": {"file_id": file_id},
                    },
                )
                await context.send_activity(
                    Activity(type=ActivityTypes.message, attachments=[consent_card])
                )
                logger.info("Sent FileConsentCard for: %s (%d bytes)", name, len(content))

    except Exception as exc:
        logger.warning("Could not send session files: %s", exc)


async def _handle_file_consent(context: TurnContext):
    """Handle fileConsent/invoke — upload to OneDrive on accept."""
    value = context.activity.value or {}
    action = value.get("action", "")
    accept_ctx = value.get("context") or value.get("acceptContext") or {}
    file_id = accept_ctx.get("file_id", "")
    upload_info = value.get("uploadInfo") or value.get("upload_info") or {}

    if action == "accept":
        if file_id not in _pending_files:
            await context.send_activity("⚠️ File expired — please regenerate the report.")
            return

        filename, content = _pending_files.pop(file_id)
        upload_url = upload_info.get("uploadUrl") or upload_info.get("upload_url", "")

        if not upload_url:
            await context.send_activity("⚠️ No upload URL received from Teams.")
            return

        async with aiohttp.ClientSession() as http:
            put_headers = {
                "Content-Type": "application/octet-stream",
                "Content-Range": f"bytes 0-{len(content) - 1}/{len(content)}",
            }
            async with http.put(upload_url, data=content, headers=put_headers) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    logger.error("File upload failed %d: %s", resp.status, body[:300])
                    await context.send_activity(f"⚠️ Upload failed ({resp.status}).")
                    return

        ext = filename.rsplit(".", 1)[-1] if "." in filename else "file"
        file_card = Attachment(
            content_type="application/vnd.microsoft.teams.card.file.info",
            name=filename,
            content_url=upload_info.get("contentUrl") or upload_info.get("content_url", ""),
            content={
                "uniqueId": upload_info.get("uniqueId") or upload_info.get("unique_id", ""),
                "fileType": ext,
            },
        )
        await context.send_activity(
            Activity(type=ActivityTypes.message, attachments=[file_card])
        )
        logger.info("File uploaded to OneDrive: %s", filename)

    elif action == "decline":
        _pending_files.pop(file_id, None)
        await context.send_activity("File upload cancelled.")

    await context.send_activity(
        Activity(type=ActivityTypes.invoke_response, value=InvokeResponse(status=200))
    )


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

async def setup() -> tuple[AgentApplication[TurnState], MsalConnectionManager]:
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

    # Verify agent exists
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

    # Responses API client (only used for responses protocol)
    oai_client = None
    if AGENT_PROTOCOL == "responses":
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

        if user_message.lower() == "!reset":
            state.set_value("ConversationState.thread_id", "")
            await context.send_activity("🔄 Conversation reset.")
            return

        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Start streaming to Teams
                sr = context.streaming_response
                sr.queue_informative_update("⏳ Working on your request...")
                sr.set_generated_by_ai_label(True)

                # Get protocol-specific generator
                if AGENT_PROTOCOL == "invocations":
                    gen = _stream_invocations(
                        PROJECT_ENDPOINT, credential, AGENT_NAME, user_message,
                    )
                else:
                    # Responses protocol — manage conversation thread
                    thread_id = state.get_value(
                        "ConversationState.thread_id", lambda: "", target_cls=str,
                    )
                    if not thread_id:
                        thread = await oai_client.conversations.create()
                        thread_id = thread.id
                        state.set_value("ConversationState.thread_id", thread_id)
                    gen = _stream_responses(oai_client, thread_id, user_message)

                # Stream events to Teams (with 403 cancellation fallback)
                accumulated_text = ""
                has_content = False
                stream_cancelled = False
                courtesy_sent = False
                session_id = None

                async for event in gen:
                    # Check for Teams stream cancellation on EVERY event
                    # (not just text chunks — tool calls have long gaps)
                    if not stream_cancelled and sr._cancelled:
                        stream_cancelled = True
                        logger.warning("Teams cancelled stream — collecting remaining response")
                        try:
                            await context.send_activity(
                                "⏳ The response is taking longer than expected. "
                                "Still working — full answer coming shortly..."
                            )
                            courtesy_sent = True
                        except Exception:
                            logger.warning("Could not send courtesy message")

                    if isinstance(event, TextChunk) and event.text:
                        accumulated_text += event.text
                        has_content = True
                        if not stream_cancelled:
                            sr.queue_text_chunk(event.text)
                    elif isinstance(event, StatusUpdate) and event.text:
                        if not stream_cancelled:
                            sr.queue_informative_update(event.text)
                    elif isinstance(event, SessionComplete) and event.session_id:
                        session_id = event.session_id

                if has_content:
                    if stream_cancelled:
                        await context.send_activity(accumulated_text)
                        logger.info("Sent full response after stream cancel (%d chars)", len(accumulated_text))
                    else:
                        await sr.end_stream()
                else:
                    if not stream_cancelled:
                        await sr.end_stream()
                    await context.send_activity(
                        "🤔 I processed your request but didn't receive a text response."
                    )

                # Deliver agent-generated files via FileConsentCard
                if session_id and has_content:
                    await _send_session_files(context, session_id)
                break

            except RuntimeError as e:
                if str(e) == "server_error" and attempt < max_retries - 1:
                    logger.warning("Server error — resetting conversation (attempt %d)", attempt + 1)
                    state.set_value("ConversationState.thread_id", "")
                    continue
                logger.error("Error: %s\n%s", e, traceback.format_exc())
                await context.send_activity(_friendly_error(str(e)))
                break
            except Exception as e:
                logger.error("Error: %s\n%s", e, traceback.format_exc())
                if attempt < max_retries - 1:
                    state.set_value("ConversationState.thread_id", "")
                    continue
                await context.send_activity(_friendly_error(str(e)))
                break

    @AGENT_APP.activity("invoke")
    async def on_invoke(context: TurnContext, state: TurnState):
        if context.activity.name == "fileConsent/invoke":
            await _handle_file_consent(context)
        else:
            logger.debug("Unhandled invoke: %s", context.activity.name)
            await context.send_activity(
                Activity(
                    type=ActivityTypes.invoke_response,
                    value=InvokeResponse(status=200),
                )
            )

    return AGENT_APP, CONNECTION_MANAGER

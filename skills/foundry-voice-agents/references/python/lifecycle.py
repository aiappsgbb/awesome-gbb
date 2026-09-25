"""Canonical version, realtime, and separately authorized conversation operations.

Source of truth for `../../SKILL.md § Versioning and conversation privacy`.
Call only within an explicitly approved live scope; importing does no I/O.
"""

from azure.ai.projects import AIProjectClient, models
from azure.ai.projects.aio import AIProjectClient as AsyncAIProjectClient
from azure.ai.projects.aio.operations import AsyncBetaRealtimeConnectionManager
from azure.core.exceptions import ResourceNotFoundError

from definition import Consent, require_consent


def require_version(client: AIProjectClient, name: str, version: str) -> models.VoiceAgentDefinition:
    latest = client.agents.get(agent_name=name).versions.latest
    if latest.version != version:
        raise RuntimeError("Agent latest version changed; do not invoke a moving target")
    if not isinstance(latest.definition, models.VoiceAgentDefinition):
        raise TypeError("Expected a new voice agent, not an existing text agent")
    return latest.definition


def connect(
    client: AsyncAIProjectClient, name: str, session_id: str, consent: Consent
) -> AsyncBetaRealtimeConnectionManager:
    # The SDK has no explicit version argument here. Use an isolated agent name
    # with no concurrent writers and check the latest version before AND after.
    return client.beta.voice_agents.realtime.connect(
        agent_name=name,
        agent_session_id=session_id,
        extra_query={"store": "true" if consent.store else "false"},
    )


def read_transcript(
    client: AIProjectClient, name: str, conversation: str, consent: Consent
) -> list[models.RealtimeConversationItem]:
    require_consent(consent.read_transcript, "stored transcript readback")
    return list(client.beta.voice_agents.conversations.list_items(name, conversation, order="asc"))


def read_audio(
    client: AIProjectClient, name: str, conversation: str, consent: Consent
) -> bytes:
    require_consent(consent.read_audio, "stored audio readback")
    recording = client.beta.voice_agents.conversations.get_audio(name, conversation)
    if recording.blob_uri:
        raise RuntimeError("BYO storage URI requires a separately approved storage download path")
    audio = bytearray()
    for chunk in client.beta.voice_agents.conversations.download_audio(name, conversation):
        audio.extend(chunk)
        if len(audio) > 24_000 * 2 * 2 * 120:
            raise RuntimeError("Stored audio exceeds the two-minute stereo readback limit")
    if not audio:
        raise RuntimeError("No stored audio returned")
    return bytes(audio)


def delete_conversation(client: AIProjectClient, name: str, conversation: str, consent: Consent) -> None:
    require_consent(consent.delete, "delete the inventoried conversation and audio")
    client.beta.voice_agents.conversations.delete(name, conversation)
    try:
        client.beta.voice_agents.conversations.get(name, conversation)
    except ResourceNotFoundError:
        return
    raise RuntimeError("Conversation deletion has not been verified")


def delete_version(client: AIProjectClient, name: str, version: str, consent: Consent) -> None:
    require_consent(consent.delete, "delete the inventoried agent version")
    client.agents.delete_version(name, version)
    try:
        client.agents.get_version(name, version)
    except ResourceNotFoundError:
        return
    raise RuntimeError("Agent version deletion has not been verified")


def delete_empty_agent(client: AIProjectClient, name: str, consent: Consent) -> None:
    require_consent(consent.delete, "delete the inventoried empty agent")
    try:
        client.agents.get(agent_name=name)
    except ResourceNotFoundError:
        return
    if next(iter(client.agents.list_versions(agent_name=name)), None) is not None:
        raise RuntimeError("Agent still has versions; do not delete another owner's work")
    client.agents.delete(agent_name=name)
    try:
        client.agents.get(agent_name=name)
    except ResourceNotFoundError:
        return
    raise RuntimeError("Empty agent deletion has not been verified")

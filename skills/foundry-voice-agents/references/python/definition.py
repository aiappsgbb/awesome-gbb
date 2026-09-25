"""Canonical voice definition and local safety checks.

Source of truth for `../../SKILL.md § Definition and model selection`.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from azure.ai.projects import models


@dataclass(frozen=True)
class Consent:
    store: bool = False
    read_transcript: bool = False
    read_audio: bool = False
    save_local_audio: bool = False
    delete: bool = False


def require_consent(approved: bool, action: str) -> None:
    if not approved:
        raise PermissionError(f"Explicit authorization required: {action}")


def check_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.port not in (None, 443)
        or not parsed.path.startswith("/api/projects/")
        or len(parsed.path.removeprefix("/api/projects/").strip("/").split("/")) != 1
        or not parsed.path.removeprefix("/api/projects/").strip("/")
    ):
        raise ValueError("Use an HTTPS project endpoint without credentials, query or fragment")
    return endpoint.rstrip("/")


def build_definition(
    model: str,
    *,
    model_type: str = "managed",
    consent: Consent = Consent(),
) -> models.VoiceAgentDefinition:
    if not model.strip() or model != model.strip():
        raise ValueError("An explicit model name or existing deployment name is required")
    if model_type not in ("managed", "self_deployed"):
        raise ValueError("model_type must be managed or self_deployed")
    return models.VoiceAgentDefinition(
        model_type=models.VoiceModelType(model_type),
        model=model,
        instructions=(
            "You are a synthetic voice test assistant. Speak without markdown. Be brief "
            "unless the caller explicitly requests a longer explanation. "
            "For the demo opening hours, always call get_demo_hours and use its result. "
            "Never invent a successful tool result. If interrupted, stop the previous "
            "answer and follow the new request. Do not request personal information."
        ),
        greeting=models.VoiceAgentTemplateGreetingConfig(
            text="Hello. I can tell you the fictional demo opening hours."
        ),
        audio=models.VoiceAgentAudioConfig(
            input=models.VoiceAgentAudioInputConfig(
                format=models.RealtimeAudioFormatsAudioPcm(rate=24000),
                turn_detection=models.VoiceAgentServerVadTurnDetection(
                    threshold=0.5,
                    prefix_padding_ms=300,
                    silence_duration_ms=500,
                    create_response=True,
                    interrupt_response=True,
                ),
            ),
            output=models.VoiceAgentAudioOutputConfig(
                format=models.RealtimeAudioFormatsAudioPcm(rate=24000),
                voice="en-US-AvaNeural",
                voice_type=models.VoiceType.AZURE_STANDARD,
            ),
        ),
        output_modalities=[models.VoiceOutputModality.AUDIO],
        tools=[
            models.VoiceAgentFunctionTool(
                name="get_demo_hours",
                description="Return fictional opening hours; no lookup or side effect.",
                parameters=models.RealtimeFunctionToolParameters(
                    {
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    }
                ),
            )
        ],
        store=consent.store,
    )

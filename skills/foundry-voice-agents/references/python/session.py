"""Canonical synthetic PCM client with server VAD and client-side tool handling.

Source of truth for `../../SKILL.md § Audio session and interruption`.
No microphone, speaker device, transcript logging, or automatic file capture.
"""

import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import time
import wave

from azure.ai.projects.aio.operations import AsyncBetaRealtimeConnection
from azure.ai.projects import models

from definition import Consent, require_consent

RATE = 24000
FRAME_BYTES = 2400  # 50 ms, mono PCM16.
MAX_INPUT_BYTES = RATE * 2 * 30
MAX_OUTPUT_BYTES = RATE * 2 * 120


def error_diagnostic(event: models.RealtimeServerEventError) -> dict[str, str]:
    """Retain protocol identifiers, never the service's free-form message."""
    values = {
        "event_id": event.get("event_id"),
        "error_type": event.error.get("type"),
        "error_code": event.error.get("code"),
        "parameter": event.error.get("param"),
        "request_id": event.error.get("request_id") or event.get("request_id"),
    }
    return {
        key: value for key, value in values.items()
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,128}", value)
    }


class VoiceServiceError(RuntimeError):
    def __init__(self, diagnostic: dict[str, str]):
        self.diagnostic = diagnostic
        super().__init__("Voice service error: " + json.dumps(diagnostic, sort_keys=True))


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, RATE):
            raise ValueError("Expected mono PCM16 WAV at 24000 Hz; no implicit resampling")
        if source.getcomptype() != "NONE":
            raise ValueError("Compressed WAV is not supported")
        if not 0 < source.getnframes() * 2 <= MAX_INPUT_BYTES:
            raise ValueError("Input must contain at most 30 seconds of synthetic audio")
        pcm = source.readframes(source.getnframes())
        if len(pcm) != source.getnframes() * 2:
            raise ValueError("Truncated WAV data")
        return pcm


def save_pcm(path: Path, pcm: bytes, consent: Consent) -> None:
    require_consent(consent.save_local_audio, "local audio capture")
    if not pcm or len(pcm) % 2:
        raise ValueError("Expected nonempty PCM16 output")
    # Refuse overwrite; the caller owns the explicit output path and its retention.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        with wave.open(output, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(RATE)
            target.writeframes(pcm)


def tool_result(name: str, arguments: str) -> str:
    if name != "get_demo_hours":
        raise ValueError("Unexpected function tool")
    if len(arguments) > 1024:
        raise ValueError("Tool arguments exceed the permitted size")
    parsed = json.loads(arguments)
    if parsed != {}:
        raise ValueError("get_demo_hours accepts only an empty object")
    return json.dumps({"fictional": True, "opening_hours": "09:00 to 17:00 UTC"})


@dataclass
class SessionEvidence:
    session_id: str | None = None
    conversation_id: str | None = None
    input_item_ids: list[str] = field(default_factory=list)
    output_item_ids: list[str] = field(default_factory=list)
    completed_turns: int = 0
    tool_calls: int = 0
    interruptions: int = 0
    greeting_bytes: int = 0
    output_bytes: int = 0
    vad_end_to_first_audio_ms: list[float] = field(default_factory=list)
    output_transcripts: list[str] = field(default_factory=list, repr=False)
    reply_transcript: str = field(default="", repr=False)
    usage: list[dict[str, object]] = field(default_factory=list)
    response_statuses: list[dict[str, str | None]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    audio: bytes = field(default=b"", repr=False)


class TurnCollector:
    """Reduce typed events; wire response IDs are internal, never trace IDs."""

    def __init__(self) -> None:
        self.evidence = SessionEvidence()
        self.active: str | None = None
        self.interrupted: set[str] = set()
        self.pending: dict[str, list[tuple[str, str]]] = {}
        self.seen_calls: set[str] = set()
        self.audio: dict[str, bytearray] = {}
        self.turns: dict[str, int] = {}
        self.vad_end: float | None = None
        self.first_audio: set[str] = set()
        self.transcripts: dict[str, str] = {}

    async def accept(
        self,
        event: models.RealtimeServerEvent | dict[str, object],
        conn: AsyncBetaRealtimeConnection,
    ) -> bool:
        if isinstance(event, models.RealtimeServerEventError):
            diagnostic = error_diagnostic(event)
            self.evidence.errors.append(diagnostic)
            raise VoiceServiceError(diagnostic)
        if isinstance(event, models.RealtimeServerEventSessionCreated):
            session_id = event.session.get("id")
            if not isinstance(session_id, str) or not session_id:
                raise RuntimeError("Missing service session ID")
            self.evidence.session_id = session_id
            self.evidence.conversation_id = event.conversation_id
        elif isinstance(event, models.RealtimeServerEventInputAudioBufferSpeechStarted):
            if event.item_id not in self.evidence.input_item_ids:
                self.evidence.input_item_ids.append(event.item_id)
            if self.active and self.audio.get(self.active) and self.active not in self.interrupted:
                self.interrupted.add(self.active)
                self.audio[self.active].clear()
                self.evidence.interruptions += 1
        elif isinstance(event, models.RealtimeServerEventInputAudioBufferSpeechStopped):
            self.vad_end = time.monotonic()
        elif isinstance(event, models.RealtimeServerEventResponseCreated):
            if self.active is not None:
                raise RuntimeError("Unexpected concurrent voice responses")
            self.active = event.response.id
            self.audio[self.active] = bytearray()
            self.turns[self.active] = len(self.evidence.input_item_ids)
        elif isinstance(event, models.RealtimeServerEventResponseAudioDelta):
            if event.response_id not in self.audio:
                raise RuntimeError("Audio arrived without response.created")
            self.evidence.output_bytes += len(event.delta)
            if self.evidence.output_bytes > MAX_OUTPUT_BYTES:
                raise RuntimeError("Audio output exceeds the client memory limit")
            if len(event.delta) % 2:
                raise RuntimeError("Malformed PCM16 audio delta")
            if event.item_id not in self.evidence.output_item_ids:
                self.evidence.output_item_ids.append(event.item_id)
            if event.response_id not in self.interrupted:
                self.audio[event.response_id].extend(event.delta)
                if event.response_id not in self.first_audio:
                    self.first_audio.add(event.response_id)
                    if self.vad_end is not None:
                        self.evidence.vad_end_to_first_audio_ms.append(
                            (time.monotonic() - self.vad_end) * 1000
                        )
                        self.vad_end = None
        elif isinstance(event, models.RealtimeServerEventResponseFunctionCallArgumentsDone):
            if event.response_id != self.active or event.call_id in self.seen_calls:
                raise RuntimeError("Unexpected or duplicate tool call")
            if len(self.seen_calls) >= 4:
                raise RuntimeError("Tool call limit reached")
            result = tool_result(event.name, event.arguments)
            self.seen_calls.add(event.call_id)
            self.pending.setdefault(event.response_id, []).append((event.call_id, result))
        elif isinstance(event, models.RealtimeServerEventResponseAudioTranscriptDone):
            self.evidence.output_transcripts.append(event.transcript)
            self.transcripts[event.response_id] = event.transcript
        elif isinstance(event, models.RealtimeServerEventResponseDone):
            usage = event.response.get("usage")
            if usage is not None:
                self.evidence.usage.append(usage.as_dict())
            details = event.response.get("status_details") or {}
            self.evidence.response_statuses.append({
                "status": event.response.status,
                "reason": details.get("reason"),
                "code": (details.get("error") or {}).get("code"),
            })
            rid = event.response.id
            if rid != self.active:
                raise RuntimeError("response.done does not match the active response")
            self.active = None
            pending = self.pending.pop(rid, [])
            if rid in self.interrupted:
                if event.response.status not in ("cancelled", "completed"):
                    raise RuntimeError("Interrupted response failed")
                self.audio.pop(rid)
                return False
            if event.response.status != "completed":
                raise RuntimeError("Voice response did not complete")
            if pending:
                # Wait for response.done before requesting the tool's follow-up.
                for call_id, result in pending:
                    await conn.conversation.item.create(
                        item=models.RealtimeConversationItemFunctionCallOutput(
                            call_id=call_id, output=result
                        )
                    )
                    self.evidence.tool_calls += 1
                await conn.response.create()
                self.audio.pop(rid)
                return False
            if any(item.get("type") == "function_call" for item in event.response.output or []):
                raise RuntimeError("Missing function arguments/output")
            pcm = bytes(self.audio.pop(rid))
            if not pcm:
                raise RuntimeError("Completed response contained no audio")
            if self.turns[rid] == 0:
                self.evidence.greeting_bytes += len(pcm)
            else:
                self.evidence.completed_turns += 1
                self.evidence.audio = pcm
                self.evidence.reply_transcript = self.transcripts.get(rid, "")
            return True
        return False


async def send_pcm(conn: AsyncBetaRealtimeConnection, pcm: bytes) -> None:
    if not pcm or len(pcm) % 2 or len(pcm) > MAX_INPUT_BYTES:
        raise ValueError("Invalid PCM16 input")
    # Trailing silence closes the server-VAD turn; never also commit/create it.
    data = pcm + bytes(RATE * 2 * 7 // 10)
    for offset in range(0, len(data), FRAME_BYTES):
        await conn.input_audio_buffer.append(audio=data[offset:offset + FRAME_BYTES])
        await asyncio.sleep(0.05)


async def exchange(
    conn: AsyncBetaRealtimeConnection,
    pcm: bytes,
    *,
    interruption: bytes | None = None,
    timeout: float = 120,
    collector: TurnCollector | None = None,
) -> SessionEvidence:
    async def run() -> SessionEvidence:
        current = collector if collector is not None else TurnCollector()
        while not await current.accept(await conn.recv(), conn):
            pass
        if current.evidence.greeting_bytes == 0:
            raise RuntimeError("Expected the configured spoken greeting")
        async with asyncio.TaskGroup() as group:
            sender = group.create_task(send_pcm(conn, pcm))
            interruption_sent = False
            while True:
                event = await conn.recv()
                complete = await current.accept(event, conn)
                if (
                    interruption is not None
                    and not interruption_sent
                    and isinstance(event, models.RealtimeServerEventResponseAudioDelta)
                ):
                    await sender
                    group.create_task(send_pcm(conn, interruption))
                    interruption_sent = True
                expected_inputs = 2 if interruption is not None else 1
                if complete and len(current.evidence.input_item_ids) >= expected_inputs:
                    if interruption is not None and current.evidence.interruptions == 0:
                        raise RuntimeError("No barge-in observed during an active audio response")
                    if not current.evidence.session_id:
                        raise RuntimeError("Missing service session ID")
                    return current.evidence

    return await asyncio.wait_for(run(), timeout=timeout)

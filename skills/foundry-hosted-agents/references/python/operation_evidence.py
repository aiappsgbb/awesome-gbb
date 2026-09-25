"""Canonical response/effect custody primitives, without dispatch or replay.

Source of truth for `../../SKILL.md § Operation recovery`.
The caller supplies a durable private record sink. Metadata is an allowlisted
projection, never a response body, bearer, signed URL or exception string.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping


def safe_id(value: object) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:~-]{1,256}", value):
        return value
    return None


def value(source, key):
    return source.get(key) if isinstance(source, Mapping) else getattr(source, key, None)


def begin_operation(record, *, target: str, intent: dict) -> str:
    """Persist intent before dispatch; a failed sink prevents the caller's send."""
    correlation = uuid.uuid4().hex
    digest = hashlib.sha256(json.dumps(
        {"target": target, "intent": intent}, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    record("operation-intent", {"client_correlation_id": correlation, "intent_sha256": digest,
                                "service_id": None, "effect": "UNKNOWN"})
    return correlation


def response_metadata(response) -> dict:
    extra = getattr(response, "model_extra", None) or {}
    session_id = value(response, "agent_session_id") or extra.get("agent_session_id")
    status = value(response, "status")
    if status not in ("queued", "in_progress", "completed", "failed", "cancelled", "incomplete"):
        status = "unknown"
    error = value(response, "error")
    return {
        "response_id": safe_id(value(response, "id")),
        "session_id": safe_id(session_id),
        "response_status": status,
        "error_code": safe_id(value(error, "code")) if error is not None else None,
        "classification": ("PENDING_OPERATION" if status in ("queued", "in_progress")
                           else "COMPLETED_RESPONSE" if status == "completed"
                           else "UNCERTAIN_EFFECT"),
        "effect": "UNKNOWN",
    }


def capture_response(raw, record, *, raw_capture=None):
    """Save transport and service identity before SDK or application parsing."""
    response = raw.http_response
    record("http-response", {
        "status_code": response.status_code,
        "request_id": safe_id(response.headers.get("x-request-id") or response.headers.get("apim-request-id")),
        "body_sha256": hashlib.sha256(response.content).hexdigest(),
        "raw_capture": "requested" if raw_capture is not None else "not-recorded",
    })
    try:
        envelope = json.loads(response.content)
    except (ValueError, UnicodeError):
        if raw_capture is not None:
            raw_capture(response.content)
            record("raw-response-captured", {"location": "private"})
        record("response-envelope-invalid", {"classification": "UNCERTAIN_EFFECT", "effect": "UNKNOWN"})
        raise
    if not isinstance(envelope, dict):
        record("response-envelope-invalid", {"classification": "UNCERTAIN_EFFECT", "effect": "UNKNOWN"})
        raise ValueError("Response envelope must be an object; reconcile the original operation")
    record("response-received", response_metadata(envelope))
    if raw_capture is not None:
        raw_capture(response.content)
        record("raw-response-captured", {"location": "private"})
    return raw.parse()


def error_metadata(error: BaseException) -> dict:
    status = getattr(error, "status_code", None)
    return {
        "error_type": type(error).__name__,
        "status_code": status if isinstance(status, int) else None,
        "request_id": safe_id(getattr(error, "request_id", None)),
        "error_code": safe_id(getattr(error, "code", None)),
        "classification": "UNCERTAIN_EFFECT",
        "effect": "UNKNOWN",
    }


def verified_effect(*, response_id: str, observed_response_id: str, reader: str,
                    consistency: str, evidence: str) -> dict:
    if (safe_id(response_id) is None or response_id != observed_response_id
            or not all(isinstance(v, str) and v.strip() for v in (reader, consistency, evidence))):
        raise ValueError("Effect readback needs the original service ID, reader, consistency and evidence")
    return {"response_id": response_id, "reader": reader, "consistency": consistency,
            "evidence": evidence, "classification": "VERIFIED_EFFECT"}


class SSEFrames:
    """Decode complete JSON SSE frames, never ignore malformed JSON as success."""
    def __init__(self):
        self.event = ""
        self.data = []

    def feed(self, line: str):
        if line.startswith("event:"):
            self.event = line[6:].strip()
        elif line.startswith("data:"):
            self.data.append(line[5:].lstrip())
        elif not line and self.data:
            body = json.loads("\n".join(self.data))
            if not isinstance(body, dict):
                raise ValueError("Invalid event object; original effect remains unknown")
            result = (self.event, body)
            self.event, self.data = "", []
            return result
        return None

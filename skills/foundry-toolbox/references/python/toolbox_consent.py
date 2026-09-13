"""Canonical extraction of actionable Toolbox OAuth consent requests.

Source of truth for the prose example in `../../SKILL.md § MCP auth flavors
(deeper)`. Accepts the JSON-RPC error object, not a successful tools result.
Unknown, malformed and mixed-source failures are raised, never downgraded
to successful discovery. No browser, token exchange or network I/O occurs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class ToolboxConsentError(RuntimeError):
    """The error cannot be handled solely by requesting user consent."""


@dataclass(frozen=True)
class ConsentRequest:
    source: str
    url: str = field(repr=False)


def _request(source: str, value: object) -> ConsentRequest:
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise ToolboxConsentError("consent URL is missing or malformed")
    try:
        parts = urlsplit(value)
        valid = (
            parts.scheme == "https"
            and bool(parts.hostname)
            and parts.username is None
            and parts.password is None
        )
    except ValueError:
        raise ToolboxConsentError("consent URL is malformed") from None
    if not valid:
        raise ToolboxConsentError("consent URL must be an HTTPS URL without credentials")
    return ConsentRequest(source=source, url=value)


def extract_consent_requests(error: Mapping[str, object]) -> tuple[ConsentRequest, ...]:
    """Read direct or nested consent errors without losing other failures.

    The caller must show the returned URLs only to the intended user, wait
    for explicit consent, and retry the failed operation. Do not log URLs
    or automatically open them. Propagate ToolboxConsentError as a failure.
    """
    if error.get("code") != -32006:
        raise ToolboxConsentError("JSON-RPC error is not a consent envelope")
    message = error.get("message")
    if not isinstance(message, str):
        raise ToolboxConsentError("JSON-RPC error message is missing")

    direct_prefix = "User consent is required. Please visit: "
    if message.startswith(direct_prefix):
        return (_request("toolbox", message[len(direct_prefix):].strip()),)

    start = message.find("{")
    if start < 0:
        raise ToolboxConsentError("source error payload is missing")
    try:
        payload = json.loads(message[start:])
    except json.JSONDecodeError:
        raise ToolboxConsentError("source error payload is malformed") from None
    if not isinstance(payload, Mapping):
        raise ToolboxConsentError("source error payload must be an object")
    entries = payload.get("errors")
    if not isinstance(entries, list) or not entries:
        raise ToolboxConsentError("source error list is missing or empty")

    requests: list[ConsentRequest] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ToolboxConsentError("source error entry must be an object")
        source = entry.get("name")
        nested = entry.get("error")
        if not isinstance(source, str) or not source or not isinstance(nested, Mapping):
            raise ToolboxConsentError("source error entry is incomplete")
        if nested.get("code") != "CONSENT_REQUIRED":
            raise ToolboxConsentError("Toolbox contains non-consent source failures")
        requests.append(_request(source, nested.get("message")))
    return tuple(requests)

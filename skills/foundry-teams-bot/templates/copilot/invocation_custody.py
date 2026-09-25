"""Private per-activity custody shared by the three bot templates.

Copy operation_evidence.py from foundry-hosted-agents/references/python beside
this file. Set BOT_OPERATION_DIR to an existing owner-private directory. A
durable volume/application store is required for recovery across replacement.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from datetime import datetime, timezone

from operation_evidence import SSEFrames, error_metadata, response_metadata, safe_id


class ExistingInvocation(RuntimeError):
    pass


class InvocationJournal:
    def __init__(self, activity):
        root = Path(os.environ["BOT_OPERATION_DIR"])
        if (not root.is_absolute() or not root.is_dir() or root.is_symlink()
                or stat.S_IMODE(root.stat().st_mode) & 0o077):
            raise ValueError("BOT_OPERATION_DIR must be an existing owner-private absolute directory")
        identity = [getattr(activity, "channel_id", None),
                    getattr(getattr(activity, "conversation", None), "id", None),
                    getattr(activity, "id", None)]
        if not all(isinstance(part, str) and part for part in identity):
            raise ValueError("Activity channel, conversation and ID are required before dispatch")
        self.correlation = hashlib.sha256(json.dumps(identity).encode()).hexdigest()
        self.path = root / (self.correlation + ".jsonl")
        try:
            descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise ExistingInvocation("Original activity already recorded; reconcile it without another invocation")
        self._file = os.fdopen(descriptor, "w", encoding="utf-8")
        try:
            self.record("intent", {"client_correlation_id": self.correlation, "effect": "UNKNOWN"})
        except OSError:
            self.close()
            raise

    def record(self, event: str, metadata: dict):
        self._file.write(json.dumps({"event": event, "observed_at": datetime.now(timezone.utc).isoformat(),
                                    **metadata}) + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def response(self, response):
        self.record("response", response_metadata(response))

    def error(self, error: BaseException):
        self.record("unresolved", error_metadata(error))

    def close(self):
        self._file.close()


async def invocation_events(response, journal):
    """Read the template's SSE protocol; partial text is not terminal success."""
    journal.record("http-response", {"status_code": response.status,
                                     "request_id": safe_id(response.headers.get("x-request-id"))})
    if response.status != 200:
        raise RuntimeError(f"Invocations HTTP {response.status}; reconcile original operation")
    frames = SSEFrames()
    completed = False
    async for line_bytes in response.content:
        line = line_bytes.decode("utf-8").rstrip("\r\n")
        frame = frames.feed(line)
        if frame is not None:
            event_name, event = frame
            if event_name == "done":
                journal.record("runtime-completed", {
                    "runtime_invocation_id": safe_id(event.get("invocation_id")),
                    "native_retrievable_id": False, "effect": "UNKNOWN",
                })
                completed = True
                break
            if event.get("type") in ("error", "session.error"):
                raise RuntimeError("Invocations runtime error; original effect remains unknown")
            yield event
    if not completed:
        raise RuntimeError("Invocations stream ended without completion; reconcile original operation")

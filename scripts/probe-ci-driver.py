#!/usr/bin/env python3
"""Check the configured Copilot driver before starting consumer fixtures."""

from __future__ import annotations

import os
import json
import signal
import subprocess
import sys


COMMAND = (
    "copilot", "-s", "--output-format", "json", "-p",
    "Reply with the single word PONG and nothing else. Do not call tools.",
    "--no-custom-instructions", "--no-ask-user", "--no-auto-update",
    "--deny-tool", "shell", "--deny-tool", "write", "--disable-builtin-mcps",
)


def failure_reason(text: str) -> str | None:
    if "HTTP 401" in text or "HTTP 403" in text:
        return "AUTH"
    if "429" in text or "Too Many Requests" in text:
        return "THROTTLED"
    lower = text.lower()
    if "unknown option" in lower or "unrecognized option" in lower:
        return "CLI_ARGUMENTS"
    if "unable to get resource information" in lower:
        return "BACKEND_RESOURCE"
    if any(code in text for code in ("CAPIError: 500", "HTTP 500", "HTTP 502", "HTTP 503")):
        return "BACKEND_5XX"
    if any(code in text for code in ("ECONNRESET", "ENOTFOUND", "ETIMEDOUT", "CERT_HAS_EXPIRED")):
        return "NETWORK"
    if "Cannot find module" in text or "ERR_MODULE_NOT_FOUND" in text:
        return "CLI_RUNTIME"
    return None


def captured_text(value: str | bytes | None) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""


def events(text: str, *, partial: bool = False) -> list[dict]:
    result = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            if partial:
                continue
            return []
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            if partial:
                continue
            return []
        result.append(event)
    return result


def timeout_phase(text: str) -> str:
    observed = events(text, partial=True)
    if any(e["type"] == "session.info" and
           isinstance(e.get("data"), dict) and e["data"].get("infoType") == "model_retry"
           for e in observed):
        return "MODEL_RETRY"
    if any(e["type"] in {"assistant.message", "assistant.message_delta"} for e in observed):
        return "RESPONSE_STARTED"
    if any(e["type"] == "assistant.turn_start" for e in observed):
        return "MODEL_TURN_STARTED"
    if observed:
        return "SESSION_STARTED"
    return "OUTPUT_PRESENT" if text.strip() else "NO_OUTPUT"


def exact_pong(text: str) -> bool:
    observed = events(text)
    if (not observed or observed[-1]["type"] != "result"
            or type(observed[-1].get("exitCode")) is not int or observed[-1]["exitCode"] != 0):
        return False
    if sum(e["type"] == "result" for e in observed) != 1:
        return False
    if any(e["type"] == "session.error" or e["type"].startswith("tool.") for e in observed):
        return False
    messages = [e.get("data") for e in observed if e["type"] == "assistant.message"]
    return (len(messages) == 1 and isinstance(messages[0], dict)
            and messages[0].get("content") == "PONG" and not messages[0].get("toolRequests"))


def probe() -> str:
    env = {
        **os.environ,
        "COPILOT_AUTO_UPDATE": "false",
        "COPILOT_PROVIDER_MAX_PROMPT_TOKENS": "128000",
        "COPILOT_PROVIDER_MAX_OUTPUT_TOKENS": "512",
    }
    try:
        process = subprocess.Popen(
            COMMAND, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env, start_new_session=True,
        )
    except OSError:
        return "FAIL CLI_START"
    try:
        stdout, stderr = process.communicate(timeout=90)
    except subprocess.TimeoutExpired as timeout:
        partial = captured_text(timeout.output) + captured_text(timeout.stderr)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired as cleanup_timeout:
            partial += captured_text(cleanup_timeout.output) + captured_text(cleanup_timeout.stderr)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
        # Classify in memory only; even truncated CLI output can contain secrets.
        partial += captured_text(stdout) + captured_text(stderr)
        reason = failure_reason(partial) or timeout_phase(partial)
        return f"FAIL TIMEOUT {reason}"
    if process.returncode:
        return f"FAIL {failure_reason(stdout + stderr) or 'CLI_RESPONSE'}"
    if not exact_pong(stdout):
        return "FAIL RESPONSE_CONTRACT"
    return "PASS"


if __name__ == "__main__":
    result = probe()
    print(f"CI_DRIVER_PREFLIGHT={result}")
    sys.exit(0 if result == "PASS" else 1)

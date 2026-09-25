#!/usr/bin/env python3
"""Check the configured Copilot driver before starting consumer fixtures."""

from __future__ import annotations

import os
import signal
import subprocess
import sys


COMMAND = (
    "copilot", "-s", "-p",
    "Reply with the single word PONG and nothing else. Do not call tools.",
    "--no-custom-instructions", "--no-ask-user", "--no-auto-update",
    "--deny-tool", "shell", "--deny-tool", "write", "--disable-builtin-mcps",
)


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
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
        return "FAIL TIMEOUT"
    if process.returncode:
        text = stdout + stderr
        if "HTTP 401" in text or "HTTP 403" in text:
            return "FAIL AUTH"
        if "429" in text or "Too Many Requests" in text:
            return "FAIL THROTTLED"
        if "unknown option" in text.lower() or "unrecognized option" in text.lower():
            return "FAIL CLI_ARGUMENTS"
        return "FAIL CLI_RESPONSE"
    if stdout.strip() != "PONG":
        return "FAIL RESPONSE_CONTRACT"
    return "PASS"


if __name__ == "__main__":
    result = probe()
    print(f"CI_DRIVER_PREFLIGHT={result}")
    sys.exit(0 if result == "PASS" else 1)

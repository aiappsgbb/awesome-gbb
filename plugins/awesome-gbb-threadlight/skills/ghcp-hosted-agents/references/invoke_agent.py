"""Invoke a GHCP SDK hosted agent via Invocations SSE endpoint.

Parses both assistant.message and assistant.message_delta events.
Use as a library or run directly to test an agent.

Usage:
    export AZURE_AI_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
    python invoke_agent.py "What is the capital of France?"
"""

from __future__ import annotations

import json
import sys
import time

import requests
from azure.identity import DefaultAzureCredential


def invoke_invocations(
    endpoint: str,
    token: str,
    agent_name: str,
    query: str,
    timeout: int = 600,
) -> str:
    """Invoke via Invocations SSE endpoint and extract response text.

    Parses both event types:
      - assistant.message: full final message (preferred)
      - assistant.message_delta: streaming content chunks (fallback)
    """
    url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"
    resp = requests.post(
        url,
        json={"input": query},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Foundry-Features": "HostedAgents=V1Preview",
        },
        stream=True,
        timeout=timeout,
    )
    resp.raise_for_status()

    message_text = ""
    delta_text = ""
    tool_count = 0

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            event = json.loads(line[6:])
            event_type = event.get("type", "")
            content = event.get("data", {}).get("content", "")

            if event_type == "assistant.message" and content:
                message_text += content
            elif event_type == "assistant.message_delta" and content:
                delta_text += content
            elif event_type == "tool.execution_start":
                tool_count += 1
        except json.JSONDecodeError:
            continue

    return message_text if message_text else delta_text


def main():
    import os

    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
    agent_name = os.environ.get("AGENT_NAME", "my-agent")

    if not endpoint:
        print("ERROR: Set AZURE_AI_PROJECT_ENDPOINT")
        sys.exit(1)

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello"

    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default").token

    print(f"Invoking {agent_name}: {query[:80]}...")
    t0 = time.time()
    response = invoke_invocations(endpoint, token, agent_name, query)
    elapsed = time.time() - t0

    print(f"\n--- Response ({len(response)} chars, {elapsed:.1f}s) ---")
    print(response)


if __name__ == "__main__":
    main()

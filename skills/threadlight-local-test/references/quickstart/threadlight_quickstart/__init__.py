"""threadlight_quickstart — Pattern 0 for threadlight-local-test.

A zero-Docker, zero-MCP-server runtime that drops into any
threadlight-designed PoC and gives a screen-shareable demo in minutes.

Public surface:
    python -m threadlight_quickstart          # full Streamlit UI on :8501
    python -m threadlight_quickstart --check  # wire + one tool call, no UI
    python -m threadlight_quickstart --simulator  # auto-pump demo prompts

See SKILL.md § Pattern 0 — Quickstart for the full walkthrough.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .discover import PoCLayout, discover
from .agent_wiring import build_agent, build_chat_client
from .stub_tools import InMemoryStore, build_stub_tools

__all__ = [
    "PoCLayout",
    "discover",
    "build_agent",
    "build_chat_client",
    "InMemoryStore",
    "build_stub_tools",
]

"""Canonical full-session persistence helpers for Agent Framework Harness.

Source of truth for the prose example in
`../../SKILL.md § Session persistence and recovery`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent_framework import AgentSession


def serialize_session(session: AgentSession) -> dict[str, Any]:
    """Serialize the full opaque session, including provider-owned state."""
    return session.to_dict()


def restore_session(payload: Mapping[str, Any]) -> AgentSession:
    """Restore a session without reaching into provider-specific state."""
    return AgentSession.from_dict(dict(payload))

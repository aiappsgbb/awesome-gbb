"""Placeholder build_agent factory — Pattern 0 does NOT call this.

Pattern 0's `agent_wiring.py` builds its own MAF Agent from the SPEC's
declared entities + skills, and never imports a PoC-side factory. This
file exists only so Pattern 1/2 (live MCP server, smoke-client) have a
target to import; for Pattern 0 it is intentionally a no-op.
"""

from __future__ import annotations


def build_agent():  # pragma: no cover - not used by Pattern 0
    raise NotImplementedError(
        "Pattern 0 (Quickstart) does not call container.build_agent. "
        "Use `python -m threadlight_quickstart` from the PoC root. "
        "For Patterns 1/2 see the threadlight-local-test SKILL.md."
    )

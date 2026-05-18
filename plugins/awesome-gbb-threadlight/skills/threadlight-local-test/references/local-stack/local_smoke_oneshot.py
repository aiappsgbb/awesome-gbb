"""One-shot smoke client — for scripting from Copilot CLI / shell.

Usage (from PoC root):
    uv run python tests/local_smoke_oneshot.py "investigate case dc001"

Prints the final assistant message and exits. Suitable for piping
into other tools or for a CLI agent to script a smoke session.

Exit code:
    0 — assistant returned text
    1 — error (import / runtime / empty response)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _load_env_local() -> None:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        env = parent / ".env.local"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
            return


async def go(prompt: str) -> int:
    _load_env_local()
    sys.path.insert(0, str(Path.cwd() / "src"))
    try:
        from agent.container import build_agent  # noqa: WPS433
    except ImportError as exc:
        print(f"FATAL: cannot import build_agent: {exc}", file=sys.stderr)
        return 1

    agent = build_agent()
    try:
        result = await agent.run_async(prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    text = ""
    if getattr(result, "messages", None):
        last = result.messages[-1]
        text = getattr(last, "text", None) or getattr(last, "content", "")
    if not text:
        print("FATAL: agent returned no text", file=sys.stderr)
        return 1

    print(text)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: local_smoke_oneshot.py <prompt>", file=sys.stderr)
        sys.exit(2)
    sys.exit(asyncio.run(go(" ".join(sys.argv[1:]))))

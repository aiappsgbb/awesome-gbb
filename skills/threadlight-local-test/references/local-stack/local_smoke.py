"""Interactive local smoke REPL — Pattern 2.

Drops the ResponsesHostServer wrapper and invokes agent.run_async()
directly. Streams output token-by-token. Reads env from .env.local.

Usage (from PoC root):
    uv run python tests/local_smoke.py

Then type prompts; Ctrl+C or `quit` to exit.

Adapt the import to match the PoC's agent factory location:
    from agent.container import build_agent      # card-dispute style
    from src.agent.container import build_agent  # if `src` is on path
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


def _load_env_local() -> None:
    """Load .env.local from PoC root if present (no python-dotenv dep)."""
    for parent in [Path.cwd(), *Path.cwd().parents]:
        env = parent / ".env.local"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
            print(f"[smoke] loaded {env}")
            return
    print("[smoke] no .env.local found — using existing process env")


async def main() -> None:
    _load_env_local()

    # --- import the PoC's agent factory ---
    # Adjust this import to match your PoC layout. The contract: a
    # callable that returns an agent_framework.Agent instance.
    sys.path.insert(0, str(Path.cwd() / "src"))
    try:
        from agent.container import build_agent  # noqa: WPS433
    except ImportError as exc:
        print(f"[smoke] FATAL — cannot import build_agent: {exc}")
        print("[smoke] Edit this file's import to match your PoC layout.")
        sys.exit(1)

    agent = build_agent()
    print(f"[smoke] agent ready · model={os.environ.get('MODEL_DEPLOYMENT_NAME')} · mcp={os.environ.get('MCP_SERVER_URL')}")
    print("[smoke] Ctrl+C or 'quit' to exit.\n")

    while True:
        try:
            prompt = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not prompt:
            continue
        if prompt.lower() in {"quit", "exit", ":q"}:
            break

        try:
            async for event in agent.run_streaming(prompt):
                text = getattr(event, "text", None) or getattr(event, "content", "")
                if text:
                    sys.stdout.write(text)
                    sys.stdout.flush()
            print("\n")
        except Exception as exc:  # noqa: BLE001
            print(f"\n[smoke] error: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())

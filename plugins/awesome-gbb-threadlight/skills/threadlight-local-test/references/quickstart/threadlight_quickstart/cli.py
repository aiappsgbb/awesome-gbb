"""CLI for ``python -m threadlight_quickstart``.

Subcommands (positional + flags):

  (default)            launch the Streamlit UI on localhost:8501
  --check              wire discover → agent → 1 tool call; no UI; exit
  --simulator          start with the prompt simulator pre-loaded
  --info               print the discovered layout and exit (no LLM)

All commands honour ``--root <path>`` to override discover start dir.

Auto-loads ``<poc-root>/.env.local`` so users don't have to ``source`` it
themselves. Existing process env always wins (so an explicit ``export``
in the shell overrides the file).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .discover import PoCLayoutError, discover


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="threadlight_quickstart",
        description=(
            "Pattern 0 quickstart for a threadlight-designed PoC: "
            "MAF Agent + SkillsProvider + JSON stub tools + Streamlit UI."
        ),
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="PoC root (default: walk up from cwd looking for specs/sample-data/).",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help=(
            "Wire everything, call one stub tool, exit. No Streamlit. "
            "CI-friendly sanity check that .env.local + Azure auth work."
        ),
    )
    p.add_argument(
        "--info",
        action="store_true",
        help="Print the discovered PoC layout and exit. No LLM call.",
    )
    p.add_argument(
        "--simulator",
        action="store_true",
        help="Pre-load the demo-script prompt simulator in the UI.",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port for the Streamlit UI (default: 8501).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _setup_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# Match KEY=VALUE lines in a .env file. Tolerant of:
#   * leading "export " (so a file that doubles as a shell `source` works)
#   * blank lines and "#" comments
#   * surrounding single/double quotes on the value
_ENV_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<val>.*?)\s*$"
)


def _load_env_local(root: Path, filename: str = ".env.local") -> int:
    """Load ``<root>/<filename>`` into ``os.environ`` (existing keys win).

    Stdlib-only parser — no python-dotenv dependency. Returns the number
    of variables actually injected (skipping ones already set in the
    process env so that an explicit ``export`` can always override the
    file).
    """
    path = root / filename
    if not path.is_file():
        return 0
    injected = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key")
        val = m.group("val")
        # Strip a single matched pair of quotes around the value.
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key in os.environ:
            continue
        os.environ[key] = val
        injected += 1
    if injected:
        logging.getLogger(__name__).info(
            "Loaded %d var(s) from %s", injected, path
        )
    return injected


def _info(layout) -> int:
    print(layout.summary())
    return 0


def _check(layout) -> int:
    """SDK-free sanity: discover + stub-tools + a real CRUD round-trip.

    Deliberately does NOT instantiate ``Agent`` / ``ChatClient`` — those
    require ``agent-framework`` + LLM credentials, which CI runs don't
    have. ``--check`` proves the *wiring shape* (the bits that almost
    always break first); ``python -m threadlight_quickstart`` is the
    full live verification.
    """
    print("Discovered layout:")
    print(layout.summary())
    print()

    from .stub_tools import build_stub_tools

    try:
        tools, stores = build_stub_tools(layout.sample_data_files)
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: stub-tool wiring failed — {type(exc).__name__}: {exc}")
        return 3

    if not stores:
        print("WARNING: no entities loaded. --check has nothing to assert against.")
        return 0

    first_name = next(iter(stores))
    store = stores[first_name]
    rows = store.list_all()
    print(f"✅ Stub tools wired — {len(tools)} tool(s) registered across {len(stores)} entity store(s).")
    print(f"   store '{first_name}' has {len(rows)} record(s).")
    if rows:
        sample = rows[0]
        keys = ", ".join(sorted(sample.keys())[:6])
        suffix = "…" if len(sample) > 6 else ""
        print(f"   first record id={sample.get('id')!r} fields=[{keys}{suffix}]")

    # Exercise update + reset so the snapshot semantics are verified.
    first_id = next(iter(store.records))
    store.update(first_id, _quickstart_check="touched")
    assert store.records[first_id]["_quickstart_check"] == "touched"
    store.reset()
    assert "_quickstart_check" not in store.records[first_id]
    print("✅ Update + reset round-trip works (in-memory snapshot ok).")

    # Try to import agent_framework — informational only.
    try:
        import agent_framework  # type: ignore[import-not-found]  # noqa: F401
        print("✅ agent_framework importable — full --check + UI ready.")
    except ImportError:
        print(
            "ℹ️  agent_framework not installed yet — install with "
            "`pip install -e <quickstart-dir>` before launching the UI."
        )
    return 0


def _streamlit(layout, *, port: int, simulator: bool) -> int:
    streamlit_bin = shutil.which("streamlit")
    if streamlit_bin is None:
        print("FATAL: streamlit not on PATH. Install with `pip install streamlit~=1.40`.")
        return 2
    ui = Path(__file__).parent / "ui_streamlit.py"
    env = os.environ.copy()
    env["THREADLIGHT_QUICKSTART_ROOT"] = str(layout.root)
    env["THREADLIGHT_QUICKSTART_SIMULATOR"] = "1" if simulator else "0"
    cmd = [
        streamlit_bin,
        "run",
        str(ui),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, env=env)


def main(argv: Sequence[str] | None = None) -> int:
    _setup_logging()
    args = _build_parser().parse_args(argv)

    try:
        layout = discover(args.root)
    except PoCLayoutError as exc:
        print(f"❌ Layout error:\n{exc}")
        return 2

    # Load <poc-root>/.env.local so users don't have to source it.
    _load_env_local(layout.root)

    if args.info:
        return _info(layout)
    if args.check:
        return _check(layout)
    return _streamlit(layout, port=args.port, simulator=args.simulator)


if __name__ == "__main__":
    sys.exit(main())

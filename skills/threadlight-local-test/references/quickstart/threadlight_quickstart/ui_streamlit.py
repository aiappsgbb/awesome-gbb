"""Minimal Streamlit UI for Pattern 0.

Runs via ``streamlit run ui_streamlit.py``; the CLI sets two env vars
to wire the page to a specific PoC root:

  THREADLIGHT_QUICKSTART_ROOT       absolute path to the PoC root
  THREADLIGHT_QUICKSTART_SIMULATOR  "1" to enable the prompt simulator

Deliberately stays single-file — no extra dirs, no theme, no auth.
The PoC's own ``src/workspace/`` React UI keeps working unchanged
for prod-parity demos; this page is the "I just want to see it work"
fallback.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import streamlit as st

from threadlight_quickstart.agent_wiring import build_agent
from threadlight_quickstart.discover import PoCLayoutError, discover
from threadlight_quickstart.simulator import PromptCursor, load_simulator_prompts


st.set_page_config(
    page_title="Threadlight — Pattern 0 Quickstart",
    page_icon="🧵",
    layout="wide",
)


@st.cache_resource(show_spinner="Wiring agent…")
def _build(root: str):
    layout = discover(Path(root))
    agent, stores = build_agent(layout)
    prompts = load_simulator_prompts(layout)
    return layout, agent, stores, prompts


def _format_tool(name: str) -> str:
    return f"`{name}`"


async def _stream_response(agent, prompt: str, placeholder) -> str:
    chunks: list[str] = []
    try:
        async for event in agent.run_streaming(prompt):
            text = getattr(event, "text", None) or getattr(event, "content", "")
            if text:
                chunks.append(text)
                placeholder.markdown("".join(chunks))
        return "".join(chunks)
    except Exception as exc:  # noqa: BLE001
        msg = f"\n\n_error: {type(exc).__name__}: {exc}_"
        chunks.append(msg)
        placeholder.markdown("".join(chunks))
        return "".join(chunks)


def _sidebar(layout, stores, prompts, simulator_on: bool):
    st.sidebar.title("PoC")
    st.sidebar.code(str(layout.root), language="bash")

    st.sidebar.subheader("Entities (in-memory stores)")
    if stores:
        for name, store in stores.items():
            st.sidebar.markdown(f"- **{name}** — {len(store.records)} record(s)")
    else:
        st.sidebar.markdown("_(none — Pattern 0 needs at least one)_")

    st.sidebar.subheader("Skills (SkillsProvider)")
    if layout.skill_names:
        for name in layout.skill_names:
            st.sidebar.markdown(f"- {name}")
    else:
        st.sidebar.markdown("_(none — agent runs without progressive disclosure)_")

    backend = os.environ.get("LLM_BACKEND", "foundry")
    st.sidebar.subheader("LLM backend")
    st.sidebar.markdown(f"`LLM_BACKEND={backend}`")

    st.sidebar.subheader("Simulator")
    if not simulator_on:
        st.sidebar.markdown("_(off — start with `--simulator`)_")
    elif not prompts:
        st.sidebar.markdown("_(on, but no prompts found)_")
    else:
        st.sidebar.markdown(f"loaded **{len(prompts)}** prompt(s)")


def main():
    root = os.environ.get("THREADLIGHT_QUICKSTART_ROOT")
    simulator_on = os.environ.get("THREADLIGHT_QUICKSTART_SIMULATOR", "0") == "1"

    if not root:
        st.error(
            "THREADLIGHT_QUICKSTART_ROOT is unset. Launch via "
            "`python -m threadlight_quickstart` so the CLI configures the page."
        )
        return

    try:
        layout, agent, stores, prompts = _build(root)
    except PoCLayoutError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        st.error(f"Agent wiring failed: {type(exc).__name__}: {exc}")
        return

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "cursor" not in st.session_state:
        st.session_state.cursor = PromptCursor(prompts if simulator_on else [])

    cursor: PromptCursor = st.session_state.cursor

    _sidebar(layout, stores, prompts, simulator_on)

    st.title("🧵 Threadlight — Pattern 0")
    st.caption("MAF Agent + SkillsProvider + JSON stub tools — no Docker, no MCP server.")

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Simulator next-prompt button
    queued: str | None = None
    if simulator_on and cursor.remaining > 0:
        nxt = cursor.peek()
        if st.button(f"▶️ Next demo prompt ({cursor.remaining} left) — {nxt!s:.80}", use_container_width=True):
            queued = cursor.advance()
    elif simulator_on:
        st.info("Simulator finished. Click reset to replay.")
        if st.button("🔁 Reset simulator"):
            cursor.reset()
            st.rerun()

    typed = st.chat_input("Ask the agent something…")
    prompt = queued or typed

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            response = asyncio.run(_stream_response(agent, prompt, placeholder))
        st.session_state.messages.append({"role": "assistant", "content": response})


main()

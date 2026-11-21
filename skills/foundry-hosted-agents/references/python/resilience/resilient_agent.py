"""Canonical crash-resilient Responses handler (framework checkpoints + fenced side effects).

Source of truth for the handler template in `../../long-running-resilience.md`
and for the reference summary in `../../../SKILL.md § Long-running and crash-resilient agents`.

Pinned stack: azure-ai-agentserver-core==2.3.0, azure-ai-agentserver-responses==2.4.0
(see requirements.txt next to this file). No model calls: each phase is a timed
placeholder for real work (LLM call, tool run, document analysis).

Pattern (adapted from the SDK's sample_19_resilient_streaming.py):

* Host opts in with ``ResponsesServerOptions(resilient_background=True)``.
  Recovery applies only to requests sent with ``store=true`` and ``background=true``.
* One output item per phase, then ``yield stream.checkpoint()``.
* On recovery (``context.is_recovery``) the stream is seeded from
  ``context.persisted_response`` and resumes at ``len(output)``.
* A non-idempotent side effect per phase is fenced with a ``FoundryStateStore``
  watermark keyed by ``context.conversation_chain_id``: the recovered attempt skips
  effects that already committed.

Environment (all optional):

* ``RESILIENCE_PHASE_SECONDS`` — duration of each phase (default 2.0).
* ``RESILIENCE_JOURNAL`` — path of a JSON-lines journal used by the local test
  as the "external system" receiving side effects and handler-entry records.
"""

from __future__ import annotations

import asyncio
import json
import os
import time

from azure.ai.agentserver.core.storage import FoundryStateStore
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)

PHASES: tuple[str, ...] = ("analyze", "generate", "refine")
PHASE_SECONDS = float(os.environ.get("RESILIENCE_PHASE_SECONDS", "2.0"))
JOURNAL = os.environ.get("RESILIENCE_JOURNAL", "")

app = ResponsesAgentServerHost(options=ResponsesServerOptions(resilient_background=True))


def _journal(record: dict) -> None:
    if not JOURNAL:
        return
    record["ts"] = time.time()
    record["pid"] = os.getpid()
    with open(JOURNAL, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


async def _apply_side_effect(store: FoundryStateStore, response_id: str, phase: str) -> None:
    """Issue a non-idempotent effect at most once per (response, phase)."""
    key = "effects"
    item = await store.get_item(key)
    done = dict(item.value) if item else {}
    if done.get(phase) == "committed":
        _journal({"event": "effect_skipped", "phase": phase, "response_id": response_id})
        return
    done[phase] = "issued"
    await store.set_item(key, done)
    _journal({"event": "effect", "phase": phase, "response_id": response_id,
              "idempotency_key": f"{response_id}:{phase}"})
    done[phase] = "committed"
    await store.set_item(key, done)


@app.response_handler
async def handler(request: CreateResponse, context: ResponseContext, cancellation_signal: asyncio.Event):
    if context.is_recovery and context.persisted_response is not None:
        stream = ResponseEventStream(response_id=context.response_id, response=context.persisted_response)
        start = len(stream.response.get("output") or [])
    else:
        stream = ResponseEventStream(response_id=context.response_id, request=request)
        start = 0
    _journal({"event": "enter", "is_recovery": context.is_recovery, "start": start,
              "response_id": context.response_id})

    yield stream.emit_created()
    if context.shutdown.is_set():
        await context.exit_for_recovery()
    if cancellation_signal.is_set():
        return
    yield stream.emit_in_progress()

    store = await FoundryStateStore.get_or_create(f"resilience/{context.conversation_chain_id}")
    prompt = await context.get_input_text()

    for phase in PHASES[start:]:
        _journal({"event": "phase_start", "phase": phase, "response_id": context.response_id})
        message = stream.add_output_item_message()
        yield message.emit_added()
        text = message.add_text_content()
        yield text.emit_added()
        await asyncio.sleep(PHASE_SECONDS)
        body = f"[{phase}] done for: {prompt}"
        yield text.emit_delta(body)
        await _apply_side_effect(store, context.response_id, phase)
        yield text.emit_text_done(body)
        yield text.emit_done()
        yield message.emit_done()
        if cancellation_signal.is_set() or context.shutdown.is_set():
            break
        yield stream.checkpoint()
        _journal({"event": "checkpoint", "phase": phase, "response_id": context.response_id})

    if context.shutdown.is_set():
        await context.exit_for_recovery()
    yield stream.emit_completed()
    _journal({"event": "completed", "response_id": context.response_id})


if __name__ == "__main__":
    app.run()

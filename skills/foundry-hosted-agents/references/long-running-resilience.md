# Long-running and crash-resilient hosted agents

Use this reference when a hosted agent turn can run for minutes or longer, or
when a crash, out-of-memory kill, redeploy or session stop must not lose the
work. It covers the Responses protocol path with the Agent Server SDK directly
(no Microsoft Agent Framework hosting adapter).

Labels: **Documented** = an official page says it (URL given). **Tested** = we
observed it; the conditions are stated. **Analysis** = our reasoning.

## Pinned stack

```text
azure-ai-agentserver-core==2.3.0
azure-ai-agentserver-responses==2.4.0
```

**Documented**: both are GA releases on PyPI
([core](https://pypi.org/project/azure-ai-agentserver-core/),
[responses](https://pypi.org/project/azure-ai-agentserver-responses/)); responses
2.4.0 requires `azure-ai-agentserver-core>=2.3.0,<3`.

This is a separate profile from the MAF container profile in SKILL.md
(`agent-framework-foundry-hosting==1.0.0b260813` with Agent Server 2.1.0b1).
Do not raise those MAF pins to get resilience: refresh the MAF profile on its own
when the hosting adapter is validated against Agent Server 2.3/2.4.

## Background is not resilience

**Documented**
([Learn: resilience concept](https://learn.microsoft.com/azure/foundry/agents/concepts/long-running-agent-resilience)):
background execution lets work continue without the original HTTP connection;
resilience lets a later process lifetime recover the work. Recovery re-enters the
handler from the top. It is not deterministic replay and does not restore local
variables.

## Opt-in matrix

**Documented**
([Learn: recover long-running work](https://learn.microsoft.com/azure/foundry/agents/how-to/recover-long-running-work),
[SDK resilient Responses guide](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/agentserver/azure-ai-agentserver-responses/docs/resilient-responses-developer-guide.md)):
crash recovery is off by default and applies only when all three hold.

| `store` | `background` | Host `resilient_background` | On crash |
|---|---|---|---|
| `true` | `true` | `True` | Handler re-invoked with `context.is_recovery=True`; persisted events replay to reconnecting clients. |
| `true` | `true` | `False` (default) | Not re-invoked. See the conflict note below. |
| `true` | `false` | any | Never re-invoked (the client connection is gone). |
| `false` | any | any | No persistence; `background=true, store=false` is rejected with HTTP 400. |

> **Doc conflict, row 2.** Learn says a crashed background response without the
> opt-in "is marked `failed` with `error.code="server_error"`". The SDK guide says
> that with both `resilient_background` and `steerable_conversations` off, work
> is non-durable and "no restart action runs".
> **Tested** (local, file-backed stores, core 2.3.0 / responses 2.4.0, Python 3.12,
> Nov 2026, one run): after `SIGKILL` and restart the response stayed
> `in_progress` with 0 output items 20 s later and was never marked failed. The
> #563 hosted run (Sweden Central, one run) saw the same after 6 minutes. A
> polling client waits forever. Treat row 2 as a **ghost response**: always opt
> in, or give clients a deadline after which they stop polling.

Core/Invocations code uses a different switch: call
`set_resilient_tasks_enabled(True)` before host startup and declare `@task` /
`@multi_turn_task` handlers (**Documented**, Learn page above). The Responses
options do not read or change that process-wide switch (**Documented**, SDK guide).

## Handler template

Copy [`python/resilience/resilient_agent.py`](python/resilience/resilient_agent.py)
(adapted from SDK
[sample_19](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/agentserver/azure-ai-agentserver-responses/samples/sample_19_resilient_streaming.py);
for LangGraph composition see
[sample_21](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/agentserver/azure-ai-agentserver-responses/samples/sample_21_resilient_langgraph.py)).
Its shape:

1. `ResponsesAgentServerHost(options=ResponsesServerOptions(resilient_background=True))`.
2. One output item per phase, then `yield stream.checkpoint()`. The framework
   persists the response snapshot at `response.created`, each checkpoint and the
   terminal event (**Documented**, SDK guide).
3. On `context.is_recovery`, seed `ResponseEventStream(response_id=...,
   response=context.persisted_response)` and resume at
   `len(stream.response["output"])`. Checkpointed phases are skipped; the
   interrupted phase re-runs from its start.
4. On `context.shutdown.is_set()`, close the open builders, do not checkpoint,
   and `await context.exit_for_recovery()`; this leaves the response
   `in_progress` for a later lifetime.

**Tested** (local, `tests/test_resilient_recovery.py`, five consecutive passes,
Nov 2026): `SIGKILL` during phase 2 of 3; on restart the handler re-entered once
with `is_recovery=True` and `start=1`, phase order was
`analyze, generate, generate, refine`, each side effect was issued once, the
response completed with 3 items, and the full SSE replay had exactly one
`response.created`, one `response.completed` and two `response.in_progress`.

### API drift in the Learn snippets

**Tested** (Nov 2026, against the installed core 2.3.0 / responses 2.4.0 wheels):
these names in the Python snippets on
[Learn: recover long-running work](https://learn.microsoft.com/azure/foundry/agents/how-to/recover-long-running-work)
and the
[API reference](https://learn.microsoft.com/azure/foundry/agents/concepts/long-running-agent-reference)
do not exist.

| Learn snippet | Use instead |
|---|---|
| `ResponseEventStream.from_snapshot(...)` | `ResponseEventStream(response_id=..., response=context.persisted_response)` |
| `context.conversation_chain_metadata` (+ `.flush()`) | `FoundryStateStore.get_or_create(f".../{context.conversation_chain_id}")` |
| `context.is_shutting_down` | `context.shutdown.is_set()` |
| `TaskContext.metadata` (`ctx.metadata`) | `FoundryStateStore` keyed by `ctx.task_id` |

The SDK guide uses the same replacements.

## Side-effect fencing

**Documented** (Learn concept page, SDK guide): persist a watermark before an
operation that cannot be repeated safely and mark it after the operation
commits. Keep metadata small; store bulk data in your own storage.
`FoundryStateStore` is marked experimental in core 2.3.0; keys starting with `_`
are rejected. Locally it falls back to a JSON file under
`${AGENTSERVER_STATE_ROOT:-~/.agentserver}/state_stores/`.

The template marks each phase `issued` then `committed` and skips `committed`
effects on recovery. **Analysis**: a crash between `issued` and `committed`
leaves the outcome unknown, so the effect may run again. Send the idempotency key
(`{response_id}:{phase}` in the template) so the downstream system can
deduplicate, or reconcile with it before re-issuing. This is at-least-once, not
exactly-once.

## Client contract

1. Create with `store=true, background=true, stream=true`.
   **Tested** (#563 hosted run): replay requires `stream=true` at creation;
   otherwise `GET` returns HTTP 400 "This response cannot be streamed because it
   was not created with stream=true".
2. Persist `response.id`, `agent_session_id` (both on `response.created`) and the
   last `sequence_number` you processed.
3. Reconnect with `GET {endpoint}/responses/{id}?api-version=v1&stream=true&starting_after=<seq>`
   (**Documented**,
   [Learn: stream with reconnect](https://learn.microsoft.com/azure/foundry/agents/how-to/stream-with-reconnect)).
4. Any `response.in_progress` after the first is a **snapshot reset**: replace
   your local output with the event's snapshot, drop partial content, then apply
   later events. Output indexes are slot IDs, not counters (**Documented**, same page).
5. Keep a reconciler that polls `GET {endpoint}/responses/{id}?api-version=v1`
   until a terminal status, with your own deadline. Do not rely on the SSE stream
   alone (see the session-stop result below).

**Tested** (hosted, Sweden Central, Nov 2026, one run each, 0.5 vCPU / 1 GiB,
`azd up` with `docker.remoteBuild`, the template with 20 s phases):

| Scenario | Result |
|---|---|
| Client drops the SSE after phase 1 (last seq 7), reconnects with `starting_after=7` | First replayed event seq 8; stream ended with `response.completed`; final 3 items; full replay had one `response.created`, one `response.completed`, unique ordered sequence numbers. |
| `azd ai agent sessions stop <agent_session_id>` during phase 2 | Phase 2 had not checkpointed. The next client `GET` 33 s later woke the session; phase 2 was re-run and the response completed about 40 s later with 3 items. The SSE replay stayed at the pre-stop events (seq 0-13, no reset, no `response.completed`), also after completion. Polling `GET` returned the final result. |

## Recovery triggers

| Trigger | Recovery starts | Label |
|---|---|---|
| Process crash (`os._exit`, OOM) in a running session | Platform restarts the process in the same sandbox; the startup scan re-enters the handler (about 86 s after the crash in one run) | Tested (#563 hosted run) |
| Session stop, idle suspend or replaced session | Only when a later request reaches that session; nothing happens while it is idle | Tested (this PR, #563 run) |
| Local restart | Startup scan (and every 300 s), once the 60 s lease of the dead process has expired or belongs to the same owner | Tested (local) / SDK code `_manager.py` |

**Tested** (core 2.3.0 startup log `TaskManager starting (owner=<agent>|session:<id>, ...)`):
the lease owner is the agent name plus session ID, so recovery happens in a later
process of the same session. **Analysis**: a
stopped session therefore needs a client-side reconciler that sends a request to
it (step 5 above); otherwise the work waits until someone calls.

## Limits

**Documented**
([SDK tasks guide](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/agentserver/azure-ai-agentserver-core/docs/tasks-guide.md),
confirmed in core 2.3.0 `_decorator.py` / `_validation.py`):

- Per-turn task timeout defaults to 1 day; 7 days is the hard ceiling. A crash
  recovery does not reset it.
- Retries are off by default; crash recovery does not consume retry budget.
- Inputs are limited to about 10 MiB after JSON serialization; put large data in
  external storage.
- Stream events are kept at least 10 minutes after the stream closes (SDK guide:
  "auto-expire after 10 minutes").

**Not documented**: how the platform keeps an active background run alive past
the instance idle timeout. The #563 hosted run saw an 8-minute run finish with
the idle timeout lowered to 120 s; treat that as an observation, not a guarantee.

## Local test

```bash
python3.12 -m venv .venv-resilience
.venv-resilience/bin/pip install -r skills/foundry-hosted-agents/references/python/resilience/requirements.txt
.venv-resilience/bin/python -m unittest discover -s skills/foundry-hosted-agents/tests -v
```

The test sets `AGENTSERVER_STATE_ROOT` to a temporary directory and
`AGENTSERVER_TASKS_BACKEND=local`, so task, response, stream and state stores are
file-backed and nothing calls Azure.

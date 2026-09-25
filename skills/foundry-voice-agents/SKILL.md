---
name: foundry-voice-agents
description: >
  Unreleased draft for service-native voice-based prompt agents in Microsoft
  Foundry Agent Service public preview. Uses a standalone Azure AI Projects
  voice client, not a hosted speech pipeline. USE FOR: Foundry voice agent,
  kind voice, prompt-voice, managed voice model, voice agent greeting, synthetic
  audio turn, voice function tool, barge-in, voice conversation storage.
  DO NOT USE FOR: Azure Voice Live API migration (use foundry-voice-live),
  custom hosted voice pipelines, telephony, WebRTC implementation, batch
  speech, or existing Agent Framework dependency upgrades.
metadata:
  version: "1.0.0"
---

# Foundry voice agents

**UNRELEASED SOURCE CANDIDATE.** Manual synthetic greeting, audio input/output,
function call, interruption and stored readback/cleanup passed on 2026-09-25.
Manual service-trace correlation also passed, but **metadata-only tracing
failed**: server-side message/tool content was emitted without a client toggle.
Existing synthetic traces have a one-run, owner-accepted 30-day retention
exception; new trace capture is not authorized by that exception. Targeted CI
remains pending; see the
[validation record](../../docs/maintenance/foundry-voice-agents-validation.md).
Do not represent this candidate as production-ready. The service
capability is public preview, with no preview SLA; the SDK's stable package
version does not make the service GA. Each live run requires an authorized
scope, synthetic data controls and owned-resource cleanup.

## Scope and prerequisites

This is a new Agent Service agent with `kind: voice`, managed voice orchestration
and a name/version lifecycle. It is **not** a new default API version for the
GA Voice Live API, whose existing `foundry-voice-live` recipe remains unchanged.
Text interaction mode cannot be changed to voice in place; create a new agent.
No Agent Framework, Pipecat, LiveKit, container rebuild, custom WebRTC stack,
phone binding, outbound call, phone number or telephony licensing is included.

For an authorized live test, establish the exact project, tenant, identity,
region, model availability, network path, audio source, any user-declared spending
limit, owner, expiry and deletion authority. Public preview documentation is
not evidence of tenant rollout. The documented author/invoker prerequisite is
Foundry User on the project; this skill does not grant roles or authenticate
automatically. An already approved credential chain is required for live commands.
Never print access tokens, connection URLs, raw SDK payloads, transcripts or
protected audio URLs. Use private run artifacts for identifiers and failures.

The supported candidate environment is **Python 3.12** (structured concurrency); the upstream
SDK itself supports 3.10+. Keep this dedicated management/client environment
separate from existing agent runtimes. `requirements.txt` fixes Projects **2.7.0**
with the `voice` extra and Identity **1.25.3**. `constraints.txt` records the exact
resolved closure, including OpenAI 3.16.1 and httpx2 2.13.0, for this candidate.
These are enabling dependencies only, not approval to upgrade another skill.
No microphone package is installed.

## Canonical references

Copy/import the real modules below; do not restate their function bodies inline.

| File | Canonical section |
|---|---|
| [`references/python/definition.py`](references/python/definition.py) | Definition and model selection |
| [`references/python/session.py`](references/python/session.py) | Audio session and interruption |
| [`references/python/lifecycle.py`](references/python/lifecycle.py) | Versioning and conversation privacy |
| [`references/python/main.py`](references/python/main.py) | Run the candidate |
| [`references/voice-service.yaml`](references/voice-service.yaml) | Infrastructure boundary |
| [`references/upstream-pin.md`](references/upstream-pin.md) | Sources and validation status |

## Definition and model selection

`build_definition` is the complete SDK definition: explicit model, deterministic
template greeting, mono PCM16 at 24 kHz in both directions, server VAD with
automatic response and interruption enabled, Azure standard Ava voice, a single
harmless local function, and **`store=False`**. It does not set
`parallel_tool_calls`: the SDK exposes that field, but the dedicated current
configuration guide says prompt voice agents do not support it.

Choose `managed` plus a service model name (for example `gpt-realtime`) or
`self_deployed` plus an existing compatible deployment name. No model is deployed
by this function. Model availability and the voice/audio combination require
live validation for each chosen mode; a pass on managed does not certify BYOM.
The service derives realtime versus cascaded architecture from model selection.

The greeting is a normal response, received before any user input; do not create
a second response to trigger it. The function `get_demo_hours` takes exactly
`{}` and returns fictional hours, with no network, data lookup or side effect.
Unknown names, extra arguments, duplicates and excessive calls fail explicitly.
This proves local tool handling, not MCP, Toolbox or remote tool authorization.

## Run the candidate

From this skill directory, create a **private** Python environment. Set `PYTHON`
to its interpreter path. Install using `requirements-dev.txt` and
`constraints.txt` for offline checks, or `requirements.txt` and `constraints.txt`
for later runtime use. Do not install globally or into an existing agent runtime.

These commands are offline:

```bash
"$PYTHON" -m pip install -r requirements-dev.txt -c constraints.txt
"$PYTHON" -m unittest discover -s tests -v
"$PYTHON" references/python/main.py definition --model gpt-realtime
```

The live fixture imports the same definition, session and lifecycle modules.
CLI orchestration is locally contract-tested, not permission to invoke Azure.
After explicit live scope approval only, use `create`
with `--endpoint`, `--model` and `--approve-create`. It emits the unique
`ci-smoke-voice-<suffix>` intent before creation and returns the version.
Capture both lines in the private run inventory. An interrupted create is an
unknown outcome: inspect that exact name before retrying or creating a replacement.

Then use `talk` with `--endpoint`, `--name`, `--version`, `--input` (an approved
synthetic PCM WAV) and `--approve-send`. Optional `--interrupt` supplies a second
synthetic WAV during the first spoken answer. `--output` requires the separate
`--approve-local-audio` gate; without it audio is only buffered in process memory.
No microphone is accessed, no audio plays automatically, and transcripts stay
in memory without being logged or saved. Review the saved synthetic WAV only
in the approved client environment.
This buffered test client is not a production realtime speaker implementation.

For consented persistence, both creation and talk require `--approve-store`.
No flag implies permission for readback, deletion, telemetry content capture or
local audio capture. The CLI approval flags document the caller's already-obtained
authorization; they do not obtain consent on the caller's behalf.

## Audio session and interruption

`exchange` uses the Projects async realtime connection. `send_pcm` streams
50-ms PCM chunks at approximately wall-clock rate and ends each input with
700 ms of silence. Server VAD owns commit/response creation; the client must not
also commit or issue `response.create` for that audio turn. Function follow-up
is different: return `function_call_output` and request the next response
**only after** the tool response's `response.done`, avoiding concurrent responses.

For barge-in, start the second input after receiving the first answer's audio.
Require `speech_started` while that answer is active, discard its buffered
audio, accept cancellation only for an observed interrupted response, and obtain
a completed spoken reply to the new turn. A setting being `true`, an empty
response, or a generic cancellation alone is not successful interruption.
An interactive speaker client must also flush queued playback immediately;
this client has no speaker queue to validate. Playground human acceptance is
separate and requires approved microphone/audio access.

The client limits each input WAV to 30 seconds and the session/output buffer to
120 seconds. These are sample operation/memory bounds, not platform limits or
latency acceptance thresholds. Timeouts, malformed PCM, transport closure, tool
errors and incomplete responses fail. Partial audio is not success.

## Versioning and conversation privacy

`AIProjectClient(..., allow_preview=True)` enables voice definitions through
`.agents`; voice sessions/conversations use `.beta.voice_agents`. Let Projects
2.7.0 use its `v1` route and voice feature header. Do not copy a Voice Live
date-based API version, hand-build a token-bearing WebSocket URL or pass secrets
through `extra_query`.

Each create/update produces an immutable version. Review and record its full
definition. This SDK's realtime connect signature has no explicit agent-version
argument. Use a unique run-owned name with no concurrent writers; compare
`versions.latest.version` before and after the session. This is drift detection,
not an atomic version-pinning guarantee. Version rollback means creating a new
version from an approved prior definition, not rewriting the old version.

The CLI uses only `AzureCliCredential`, with both isolated configuration paths
and expected tenant/subscription exported. It checks the actual CLI account
before acting and never falls back to another credential source or switches
subscriptions. Reuse the canonical
[`azure-tenant-isolation` bootstrap](../azure-tenant-isolation/references/bash/bootstrap.sh)
for local environment selection.

The canonical `connect` always overrides session `store` to the explicit consent
value, so an agent default cannot silently turn persistence on. `store=True`
persists the transcript, event timeline **and raw audio together**, not just text.
The returned conversation ID is captured from `session.created`; with storage off
its absence is not a failed audio session.

`read_transcript` requires its own approval and reads items in chronological
order. `read_audio` requires separate approval, obtains recording metadata,
then downloads bounded recording bytes through the SDK. A BYO-storage URI is
**not** downloaded or logged; that needs a separately approved storage-access
path. Metadata alone is not an audio readback pass. Returned data remains in
memory unless the caller explicitly approves local persistence.

`delete_conversation` deletes the inventoried conversation and verifies a
supported not-found response. According to the service contract, that deletes
its responses, items and audio. Verify those surfaces in the live fixture too.
It does not delete already-captured Application Insights content, downloaded
copies, or an agent. `delete_version` verifies the exact inventoried version is
absent. `delete_empty_agent` removes the empty run-owned name separately, refuses
remaining versions and verifies absence. Keep all writers stopped during cleanup;
the check is not an atomic lock. Never delete a shared agent, project, resource group
or account. Authorization/network failure is not proof of deletion.

If cleanup cannot be verified, record residual IDs privately, cost exposure,
responsible owner and a bounded retention decision. No replacement runs until
the lifecycle is reconciled. Functional success and cleanup status are separate.

## Trace correlation and evaluation boundary

Use [`foundry-observability`](../foundry-observability/SKILL.md) for approved
connection/access setup and [`foundry-evals`](../foundry-evals/SKILL.md) for
evaluation setup. Do not duplicate their infrastructure, modify a shared binding
or apply a hosted-agent environment-variable workaround to managed voice.

Use the existing project-connected Application Insights pipeline, not a new
voice exporter. **Do not assume server-side content capture is off because
the client did not enable it.** The manual test emitted nonempty message and
tool-result attributes despite no client content toggle. Before connecting
managed voice to telemetry, obtain independent, informed content-capture,
retention and access approval. This candidate does not provide a working
metadata-only server-tracing recipe. Conversation storage and trace
content capture are independent. Audio stays in voice-owned storage;
Application Insights holds its telemetry reference, not the recording.

Record agent name/version, session ID, input/output item IDs and, when authorized,
conversation ID with the UTC session interval. Resolve the real service trace
and turn spans through the existing observability owner. The client sets
`trace_verified=False`: it does not invent a trace ID. Wire events contain
`response_id`, but voice **traces have no Responses API response ID**; never join
them as if they did. Require an actual trace/session/turn link.

The client reports observed `speech_stopped` receipt to first audio receipt in
milliseconds using a monotonic clock. This includes network effects and differs
from caller-turn-start TTFA, service VAD-end TTFA, model TTFT/TTLT and TTS TTFA/TTLA.
Record measurement boundaries and an approved threshold before judging latency.
No samples or `NaN` means unavailable, not zero. Trace ingestion may lag; if no
trace arrives within the agreed window, report the trace acceptance gate blocked,
not a fabricated correlation or a failed audio transport.

The dedicated voice observability article checked on 2026-09-24 documents
dataset, trace and simulation evaluation, including synthesized user voice,
audio effects and interruption simulation. This newer voice-specific guidance
supersedes conflicting older broad overview wording; tenant availability has
not been tested. Transcript scoring does **not** measure pronunciation, prosody,
echo, noise resilience or interruption timing. Insights/ROI tabs are unavailable.
Do not create evaluations, simulations, recurring scans or monitors implicitly.
Their operational recipes remain with `foundry-evals`/`foundry-observability`;
voice simulation needs its own approved live evidence before publication.

## Infrastructure boundary

The initial SDK path reuses an approved existing project; it creates no Azure
infrastructure. If infrastructure is needed, preserve **azd** as the deployment
model: use the official prompt-voice initializer with azd 1.32.0+ and a Foundry
agent extension whose help exposes `--kind prompt-voice` and `--voice`.
Record the exact extension release used. Do not guess that any extension
version has the capability or enable private-preview environment switches.

[`references/voice-service.yaml`](references/voice-service.yaml) is explicitly
an **agent-service fragment**, not a complete deployable project or Bicep fork.
Merge it into the official generated `azure.yaml` only after approval, retaining
the generated project `uses` wiring and approved infrastructure configuration.
Use `azd provision` / `azd deploy` in that project. Do not deploy this fragment
alone. New prompt-voice initialization rejects `--model-deployment`; BYOM uses
`modelType: self_deployed` and `model.id` pointing to an existing deployment.

Do not use `azd ai agent invoke` for voice; the documented workflow directs
voice services to the Foundry playground. The portal's Voice interaction mode
provides the minimal browser path. The Python SDK client is the deterministic
synthetic-audio path. No generic Responses invocation, hosted protocol flags,
container image, or global Voice Live migration is involved.

## Sources and validation status

Authoritative sources checked 2026-09-24:

- [Create a voice-based prompt agent](https://learn.microsoft.com/azure/foundry/agents/quickstarts/prompt-voice-agent).
- [Configure a voice agent](https://learn.microsoft.com/azure/foundry/agents/how-to/configure-voice-agent).
- [Voice tracing, monitoring and evaluation](https://learn.microsoft.com/azure/foundry/agents/concepts/voice-agent-observability).
- [azure.yaml voice-service reference](https://learn.microsoft.com/azure/foundry/agents/concepts/azure-yaml-reference#voice-agents).
- [Projects 2.7.0 release source](https://github.com/Azure/azure-sdk-for-python/tree/azure-ai-projects_2.7.0/sdk/ai/azure-ai-projects).

Offline checks exercise SDK serialization, typed event reduction, WAV handling,
tool sequencing, consent gates, version drift and deletion verification using
fake transports/clients. They do not prove Azure authentication, preview rollout,
audio quality, latency, trace correlation, live cleanup or azd deployment.
The canonical [`live_acceptance.py`](test-fixture/live_acceptance.py) completed
the synthetic audio/tool/interruption/storage lifecycle on the supported SDK
cohort. Automated execution refuses configured telemetry, does not create a
binding or role, and reports tracing as outside its coverage. The separate
manual trace correlation PASS and metadata-only FAIL remain in the validation
record; they are not relabeled by automated results.
[`test-fixture/consumer_prompt.md`](test-fixture/consumer_prompt.md) defines those
functional, privacy-preflight and cleanup gates. Registration is not evidence of a
passing CI execution. Browser hardware, BYOM, BYO recording downloads, azd
infrastructure and simulation are not certified by this managed-client run.

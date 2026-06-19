---
name: foundry-voice-live
description: >
  Build real-time voice agents on Azure AI Foundry Voice Live (GA 2026-04-10).
  Four-rung migration ladder: Azure OpenAI Realtime → Voice Live → Voice Live
  + Foundry Agent → native azure-ai-voicelive SDK. Covers semantic VAD, AEC,
  Neural HD voices, agent routing triplet, TTFA/TTFT benchmark, Gradio +
  FastRTC UI, plus 2026-04-10 GA deltas: proactive turn control, MCP tools
  mid-turn, OpenTelemetry via diagnostic settings, auto-truncate.
  USE FOR: voice live, realtime voice, voice agent, speech to speech, semantic
  VAD, Neural HD voices, FastRTC, Gradio voice, TTFA, gpt-realtime, byo wss,
  voice avatar, azure-ai-voicelive, voice live sdk, voice live mcp, mcp
  mid-turn, voice live proactive turn, voice live auto-truncate, voice live
  otel.
  DO NOT USE FOR: batch STT/TTS (use foundry-doc-vision-speech), non-voice
  agents (use foundry-hosted-agents / foundry-prompt-agents), App Insights
  ingestion (use foundry-observability), authoring an MCP server (use
  foundry-mcp-aca or ui-widget-developer).
metadata:
  version: "1.3.0"
---

# Foundry Voice Live

Build **real-time voice agents** on Azure AI Foundry using Voice Live —
the GA (2026-04-10) server-side voice pipeline that adds semantic VAD,
echo cancellation, noise reduction, and Azure Neural HD voices on top of
the standard Azure OpenAI Realtime API.

The migration from Realtime to Voice Live is **three small code changes**;
the migration from `openai`-shim to the native `azure-ai-voicelive` SDK
is one additional step (Rung 4). This skill walks through both ladders,
the session config that unlocks Voice Live features, and the four
2026-04-10 GA deltas — proactive turn control, MCP tools mid-turn,
OpenTelemetry via diagnostic settings, and auto-truncate governance.

## When to Use

Use this skill when the task involves ANY of:

- Real-time speech-to-speech interaction with a model
- Migrating from Azure OpenAI Realtime to Voice Live
- Adding voice to a Foundry hosted or prompt agent
- Building a voice demo with Gradio / FastRTC / WebRTC
- Benchmarking realtime voice latency (TTFA, TTFT)
- Comparing Azure Neural HD voices vs OpenAI voices

Do NOT use for batch STT/TTS (`foundry-doc-vision-speech`), non-voice
agents (`foundry-hosted-agents`, `foundry-prompt-agents`), or document
extraction.

---

## 1 · The Four Rungs

The entire migration from "plain Realtime" to "native Voice Live SDK
on a Foundry Agent" is a **diff ladder** — each rung changes only the
connection-setup block.

```
Rung 1: Azure OpenAI Realtime              ← the "before"
  │
  ▼  diff = 3 small lines (api_version, websocket_base_url, extra_query)
Rung 2: Azure Voice Live                   ← the punchline
  │
  ▼  diff = 1 line (extra_query gains agent-id / -project-name / -access-token)
Rung 3: Voice Live + Foundry Agent         ← the endgame on `openai` SDK
  │
  ▼  swap `openai.AsyncAzureOpenAI` → `azure.ai.voicelive.aio.connect`
Rung 4: native `azure-ai-voicelive` SDK    ← the GA path
```

Everything else — the audio pipe, transcript fan-out, status events,
voice picker, UI — is **identical across all four rungs**.

---

## 2 · Connection Code (Copy-Paste Ready)

### Rung 1 — Azure OpenAI Realtime

```python
from contextlib import asynccontextmanager
from openai import AsyncAzureOpenAI

@asynccontextmanager
async def connect_realtime(*, settings, token_provider):
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,              # https://<resource>.openai.azure.com
        api_version="2025-04-01-preview",                    # Realtime preview
        azure_ad_token_provider=token_provider,
    )
    try:
        async with client.realtime.connect(
            model=settings.azure_deployment_name,
        ) as conn:
            yield conn
    finally:
        await client.close()
```

### Rung 2 — Azure Voice Live (3 changed lines)

```python
@asynccontextmanager
async def connect_voicelive(*, settings, token_provider):
    actual_model = settings.azure_deployment_name
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version="2026-04-10",                                       # ← GA
        azure_ad_token_provider=token_provider,
        websocket_base_url=settings.azure_voice_live_endpoint,          # ← wss://.../voice-live
    )
    try:
        async with client.realtime.connect(
            model=actual_model,
            extra_query={"model": actual_model},                        # ← &model= not &deployment=
        ) as conn:
            yield conn
    finally:
        await client.close()
```

### Rung 3 — Voice Live + Foundry Agent (extra_query extends)

```python
@asynccontextmanager
async def connect_agent(*, settings, token_provider, agent_token_provider):
    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_endpoint,
        api_version="2026-04-10",
        azure_ad_token_provider=token_provider,
        websocket_base_url=settings.azure_voice_live_endpoint,
    )
    try:
        async with client.realtime.connect(
            model=settings.azure_deployment_name,
            extra_query={
                "agent-id":           settings.agent_id,
                "agent-project-name": settings.agent_project_name,
                "agent-access-token": await agent_token_provider(),   # ai.azure.com scope
            },
        ) as conn:
            yield conn
    finally:
        await client.close()
```

### Why 3 lines, not 1

1. **`websocket_base_url`** — the headline change; redirects the WSS
   connection to `/voice-live` on `services.ai.azure.com`.
2. **`api_version`** — Realtime is still on `2025-04-01-preview`
   (the `openai 2.x` SDK emits `/openai/realtime`; when it adopts the
   GA `/openai/v1/realtime` URL this difference collapses). Voice Live
   is GA — the latest stable version is `2026-04-10` (was `2025-10-01`
   pre-//build 2026).
3. **`extra_query={"model": ...}`** — the SDK adds `&deployment=…` to
   the WSS URL by default; Voice Live keys off `&model=…`, so we add
   it explicitly.

### Rung 4 — native `azure-ai-voicelive` SDK

The `azure-ai-voicelive` Python SDK (stable `1.2.0`; latest preview
`1.3.0b1`) is the **first-party path** for Voice Live. It speaks the
same wire protocol as Rungs 2–3 (so the event-handling code in §9
still works verbatim), but replaces the `openai`-shim plumbing with
a typed, Voice-Live-native client.

```python
from contextlib import asynccontextmanager

from azure.ai.voicelive.aio import connect       # async client
from azure.ai.voicelive.models import (
    AzureSemanticVad,
    AzureStandardVoice,
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
)
from azure.identity.aio import DefaultAzureCredential


@asynccontextmanager
async def connect_voicelive_sdk(*, settings):
    credential = DefaultAzureCredential()
    try:
        # SDK reshapes https://<resource>.services.ai.azure.com/ →
        # wss://<resource>.services.ai.azure.com/voice-live/realtime
        # ?api-version=2026-04-10&model=<model>
        async with connect(
            credential=credential,
            endpoint=settings.azure_voice_live_endpoint,   # https://, NOT wss://
            api_version="2026-04-10",                       # default in 1.2.0
            model=settings.azure_deployment_name,           # e.g. "gpt-realtime"
            # credential_scopes default = ["https://ai.azure.com/.default"]
        ) as conn:
            await conn.session.update(session=RequestSession(
                modalities=[Modality.TEXT, Modality.AUDIO],
                instructions="You are a friendly assistant.",
                voice=AzureStandardVoice(name="en-US-Ava:DragonHDLatestNeural"),
                input_audio_format=InputAudioFormat.PCM16,
                output_audio_format=OutputAudioFormat.PCM16,
                turn_detection=AzureSemanticVad(
                    create_response=True,        # §12.1 proactive
                    auto_truncate=True,          # §12.4 token governance
                ),
            ))
            yield conn
    finally:
        await credential.close()
```

### Why move to Rung 4

| Concern | Rungs 1–3 (`openai` shim) | Rung 4 (`azure-ai-voicelive`) |
|---------|---------------------------|-------------------------------|
| Typed session config | dict literals | `RequestSession` + typed models |
| Endpoint shape | `wss://…/voice-live` + base override | `https://…services.ai.azure.com` (SDK derives) |
| Auth scope default | manual `https://ai.azure.com/.default` | SDK default `https://ai.azure.com/.default` |
| MCP tools mid-turn | manual JSON | `MCPServer` + `MCPTool` typed |
| Avatar / custom voice | manual JSON | `AvatarConfig`, `AzureCustomVoice` |
| Interim response | not exposed | `LlmInterimResponseConfig` |
| API version pin | env var | SDK constant (override via kwarg) |

The native SDK is the **recommended path for new code** as of GA
`2026-04-10`. Migrate Rungs 1–3 incrementally — the wire protocol is
identical, so the audio pipe and event handler can stay as-is.

### Endpoint hostname (services.ai vs cognitiveservices)

Voice Live lives on the `services.ai.azure.com` subdomain of your
Foundry resource — the SAME resource that serves chat models on
`cognitiveservices.azure.com`. Map your CI/prod env var like:

```python
endpoint = os.environ["AZURE_AI_ENDPOINT"].replace(
    "cognitiveservices.azure.com", "services.ai.azure.com"
)
# Or set AZURE_VOICELIVE_ENDPOINT directly to the services.ai host.
```

> **Install:** `pip install "azure-ai-voicelive[aiohttp]~=1.2.0"`.
> The `[aiohttp]` extra is **required** for the async `connect`
> path — without it the import raises `RuntimeError: aiohttp not
> installed`.

---

## 3 · Session Configuration

Voice Live sessions expose capabilities that plain Realtime doesn't.
Send these in `conn.session.update(session={...})` after connection.

### Realtime session (Rung 1)

```python
{
    "turn_detection": {"type": "server_vad"},
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "voice": "alloy",                              # OpenAI voice set only
    "instructions": "You are a friendly assistant.",
    "modalities": ["text", "audio"],
    "input_audio_transcription": {
        "model": "whisper-1",
        "language": "en",
    },
}
```

### Voice Live session (Rung 2)

```python
{
    "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "voice": {"name": "en-US-Ava:DragonHDLatestNeural", "type": "azure-standard"},
    "instructions": "You are a friendly assistant.",
    "modalities": ["text", "audio"],
    "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
    "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
    "input_audio_transcription": {
        "model": "azure-fast-transcription",        # faster than whisper-1
        "language": "en",
    },
}
```

### Voice Live + Agent session (Rung 3)

The agent owns instructions and tools — omit `instructions` from the
session config:

```python
{
    "turn_detection": {"type": "azure_semantic_vad", "remove_filler_words": False},
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "voice": {"name": "en-US-Ava:DragonHDLatestNeural", "type": "azure-standard"},
    "modalities": ["text", "audio"],
    "input_audio_echo_cancellation": {"type": "server_echo_cancellation"},
    "input_audio_noise_reduction": {"type": "azure_deep_noise_suppression"},
    "input_audio_transcription": {
        "model": "azure-fast-transcription",
        "language": "en",
    },
}
```

### Non-English semantic VAD

`azure_semantic_vad` is English-tuned. For other languages, the endpointer can
fire **mid-utterance** on natural hesitations ("uhm…", a pause before an ID),
clipping the user. Two fixes:

- Use the **multilingual** VAD variant and a **multilingual end-of-utterance**
  detection model for non-English locales.
- `silence_duration_ms` is the lever that **bridges mid-sentence pauses** —
  `threshold` and `timeout_ms` alone don't. Raising it tolerates longer pauses at
  the cost of a little latency per turn (≈ the extra silence you wait for), so tune
  it to the locale's natural pausing, not lower.

### Feature comparison

| Feature | Realtime | Voice Live |
|---------|----------|------------|
| VAD | `server_vad` | `azure_semantic_vad` (understands pauses vs hesitation) |
| Echo cancellation | ❌ | `server_echo_cancellation` (built-in AEC) |
| Noise reduction | ❌ | `azure_deep_noise_suppression` |
| Transcription | `whisper-1` | `azure-fast-transcription` (lower latency) |
| Voice set | OpenAI only (10 voices) | Azure Neural HD + OpenAI (per locale) |
| Voice format | bare string `"alloy"` | `{"name": "...", "type": "azure-standard"}` |
| Filler word removal | ❌ | Optional (`remove_filler_words: true`) |

### Cascade vs native realtime — latency facts

A **native realtime** model (`gpt-realtime*`) speaks directly. A **text model on
Voice Live** (`gpt-4o`, `gpt-5*`, …) runs as a **cascade**: the model emits text,
then a managed Azure TTS overlay speaks it. Two consequences worth designing for:

- **First-audio floor.** Audio can't start before the model's first token, so the
  cascade has an inherent first-audio floor that no client tuning removes. Native
  realtime has no overlay and starts sooner. Pick native realtime when first-audio
  latency is the priority; pick the cascade when you need a specific text model's
  reasoning or a managed model with no deployment.
- **`reasoning_effort` is not monotonic for *perceived* latency.** Lower effort
  can change behavior, not just speed: `minimal` may reduce orchestration quality
  or make a model **skip** a preamble/acknowledgment turn. A middle setting is a
  reasonable starting point, but the effect is model-, prompt-, and tool-flow-
  dependent — **measure per scenario** with the two-track method in §7 rather than
  assuming "lower effort = faster experience".

---

## 4 · Voice Catalog

### OpenAI voices (all rungs)

All 10 are locale-independent: `alloy`, `ash`, `ballad`, `coral`,
`echo`, `sage`, `shimmer`, `verse`, `marin`, `cedar`.

On **Realtime** (Rung 1), send as a bare string: `"voice": "alloy"`.
On **Voice Live** (Rung 2–3), wrap with type:
`"voice": {"name": "alloy", "type": "azure-standard"}`.

### Azure Neural HD voices (Voice Live only)

Per-locale catalog. The `type` field is always `"azure-standard"`.

**English:**

| Voice | Name string |
|-------|-------------|
| Ava (default) | `en-US-Ava:DragonHDLatestNeural` |
| Jenny | `en-US-Jenny:DragonHDLatestNeural` |
| Davis | `en-US-Davis:DragonHDLatestNeural` |
| Guy | `en-US-GuyNeural` |
| Brian | `en-US-BrianNeural` |

**Italian:**

| Voice | Name string |
|-------|-------------|
| Isabella (default) | `it-IT-IsabellaMultilingualNeural` |
| Giuseppe | `it-IT-GiuseppeMultilingualNeural` |
| Alessio | `it-IT-AlessioMultilingualNeural` |
| Marta | `it-IT-MartaNeural` |
| Diego | `it-IT-DiegoNeural` |
| Elsa | `it-IT-ElsaNeural` |

> **Localization note:** The upstream demo ships English (en) and Italian
> (it) locale packs. Other locales follow the same pattern — one entry
> per dict in `i18n.py`.

### Voice fallback on rung switch

When switching from Voice Live → Realtime at runtime, HD voice names
are **not** valid for the Realtime API. The handler falls back to
`alloy` if the current voice isn't in the OpenAI set — the UI also
snaps the picker to a valid value (belt-and-braces).

### Avatars + custom voice

> 🆕 //build 2026 — public preview.

Voice Live now ships **avatar rendering** (lip-sync video over the
audio stream) and **custom voice** (BYO speaker model registered via
Azure Speech Studio). Both surfaces live behind the same WSS
connection — no new SDK; toggle via `session.update` extensions.
Configure in the [Foundry portal](https://aka.ms/speech_build2026)
under your Voice Live resource. The STT/TTS locale catalog grew to
**140+ STT / 600+ TTS** at GA, so the existing voice picker in
[`ui/voice_picker.py`](https://github.com/aiappsgbb/voice-live-gradio/blob/main/voice-live-gradio/ui/voice_picker.py)
will auto-populate any new options surfaced by `/voices`.

---

## 5 · Foundry Agent Routing

Rung 3 routes the Voice Live WebSocket to a **Foundry Agent**. The
agent can be a hosted agent (MAF container) or a prompt agent
(declarative). The routing is done via `extra_query`:

```python
extra_query={
    "agent-id":           "<agent-id>",            # from Foundry portal
    "agent-project-name": "<project-name>",        # Foundry project name
    "agent-access-token": await token_provider(),  # ai.azure.com scope
}
```

### Two token scopes

| Scope | Used for |
|-------|----------|
| `https://cognitiveservices.azure.com/.default` | Model access (Realtime + Voice Live) |
| `https://ai.azure.com/.default` | Foundry Agent routing (Rung 3 only) |

```python
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

credential = DefaultAzureCredential()

# Model scope — all rungs
model_token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# Agent scope — Rung 3 only
agent_token_provider = get_bearer_token_provider(
    credential, "https://ai.azure.com/.default"
)
```

For **sovereign clouds** (Gov, China, Germany), override these scopes
via environment variables.

### RBAC

The identity running the app needs `Cognitive Services User` on the
Foundry resource. No additional role is needed for Voice Live — it's
the same resource.

### One-click hosted-agent integration

> 🆕 //build 2026 — public preview.

The Foundry portal now wires Voice Live into any hosted agent's
Responses endpoint with a **single toggle** — no `extra_query`
triplet required. Pick this path when you don't need client-side
custom orchestration; pick the `extra_query` triplet above (or the
BYO WSS path in §6) when you do.

| Path | When to use |
|------|-------------|
| Portal one-click | Standard call/response, no custom client-side state machine |
| `extra_query` triplet | Custom Python client (Rung 3 sample above) |
| BYO WSS endpoint (§6) | Pipecat / LiveKit / your own broker |

---

## 6 · Environment Setup

All configuration is environment-driven. Use a `.env` file:

```bash
# ── Mode selector ─────────────────────────────────────────────────────
# realtime  → Rung 1    voicelive → Rung 2    agent → Rung 3
# demo      → unified switcher — all rungs in one UI (default)
MODE=demo

# ── Endpoints (same Foundry resource, different subdomains) ──────────
AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com"
AZURE_VOICELIVE_ENDPOINT="wss://<resource>.services.ai.azure.com/voice-live"

# ── Model ─────────────────────────────────────────────────────────────
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-realtime-1.5"

# ── API versions ──────────────────────────────────────────────────────
AZURE_OPENAI_API_VERSION="2025-04-01-preview"    # Realtime (preview)
AZURE_VOICELIVE_API_VERSION="2026-04-10"         # Voice Live (GA)

# ── Agent (Rung 3 only — leave blank for Rung 1 & 2) ─────────────────
AGENT_PROJECT_NAME=""
AGENT_ID=""

# ── Sovereign clouds (override for non-public) ───────────────────────
# AZURE_COGNITIVE_SERVICES_SCOPE="https://cognitiveservices.azure.com/.default"
# AZURE_AI_SCOPE="https://ai.azure.com/.default"

# ── Server bind (uncomment to override) ───────────────────────────────
# HOST="127.0.0.1"      # default: 0.0.0.0
# PORT="7860"            # default: 7860
```

### Endpoints explained

Both endpoints point at the **same Foundry resource** — they differ
only in subdomain:

| Endpoint | Subdomain | Used by |
|----------|-----------|---------|
| `AZURE_OPENAI_ENDPOINT` | `<resource>.openai.azure.com` | Realtime API + SDK base URL |
| `AZURE_VOICELIVE_ENDPOINT` | `<resource>.services.ai.azure.com/voice-live` | Voice Live WSS redirect |

### Managed models (no deployment needed)

Voice Live hosts a curated allow-list of **managed models** you don't
need to deploy yourself:

- `gpt-realtime-1.5`, `gpt-realtime`, `gpt-realtime-mini` — native realtime
- `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano` — text + Azure TTS
- `gpt-5`, `gpt-5-mini`, `gpt-5-nano` — text + Azure TTS
- `gpt-5.1`, `gpt-5.1-chat`, `gpt-5.2`, `gpt-5.2-chat`, `gpt-5.3-chat`, `gpt-5.4` — text + Azure TTS (🆕 //build 2026)
- `phi4-mm-realtime`, `phi4-mini`, `azure-realtime` — open / hosted models

Pass the managed model name in `extra_query={"model": "<name>"}` — no
Foundry-side deployment required.

**BYOM path** (bring-your-own-model via the BYO WSS endpoint below):
`gpt-5.5`, `gpt-5.4-mini`, `gpt-5.4-nano`.

### BYO WSS endpoint

> 🆕 //build 2026 — public preview. Direct WS pass-through for custom
> orchestrators (Pipecat, LiveKit, your own broker).

For BYO orchestrators, connect to the **Invocations-WS** endpoint
directly — bypassing the managed-model allow-list — and the hosted
agent's Responses endpoint duplexes the audio:

```text
wss://<account>.services.ai.azure.com/api/projects/agents/endpoint/protocols/invocations_ws?project_name=<project>&agent_name=<agent>
```

Reference samples (4 client variants) live in the Foundry samples tree
under `samples/python/hosted-agents/bring-your-own/invocations_ws/`:
`hello-world`, `livekit-server`, `pipecat-webrtc`, `pipecat-ws-server`.

> NCUS-only at GA. Other regions follow as the Invocations-WS endpoint
> light up — track via `aka.ms/speech_build2026`.

---

## 7 · Benchmark Pattern

Measure real latency across rungs using a **scenario matrix**:

```bash
# Default 5-scenario matrix, 3 iterations × 4 turns
uv run python -m benchmark.run

# More iterations for tighter noise absorption
uv run python -m benchmark.run --iterations 5

# Specific scenarios (including agent rung)
uv run python -m benchmark.run --scenarios voicelive:gpt-5-mini agent:gpt-5-mini

# Custom prompts, 6 turns, output to specific dir
uv run python -m benchmark.run --prompts prompts.txt --turns 6 --out results/

# Metrics only (skip WAV recordings)
uv run python -m benchmark.run --no-wav
```

> **Important:** The benchmark sends **text-only** prompts via the
> Realtime API. It measures TTFA/TTFT/total latency from the model's
> perspective but does **NOT** measure VAD, STT, or AEC latency
> (there's no real microphone input). For end-to-end voice latency,
> use the live UI.

### Output files

| File | Content |
|------|---------|
| `metrics.json` | Raw per-turn + per-iteration metrics for all scenarios |
| `comparison.md` | Markdown report with aggregated stats per scenario |
| `*.wav` | Per-turn audio recordings (omit with `--no-wav`) |

### Metrics collected per turn

| Metric | What it measures |
|--------|-----------------|
| `ttfa_ms` | Request → first audio chunk (time to first audio) |
| `ttft_ms` | Request → first text/transcript token |
| `total_response_ms` | Request → `response.done` event |
| `audio_duration_ms` | Wall-clock duration of generated audio |
| `audio_bytes` / `audio_chunks` | Audio payload size |

### Default scenario matrix

| Scenario | What it shows |
|----------|---------------|
| `realtime:gpt-realtime-1.5` | Rung 1 — own deployment via Realtime API |
| `voicelive:gpt-realtime` | Rung 2 — hosted realtime (no deployment) |
| `voicelive:gpt-realtime-mini` | Rung 2 — smaller hosted realtime |
| `voicelive:gpt-5-mini` | Rung 2 — text model + Azure TTS overlay |
| `voicelive:gpt-4o-mini` | Rung 2 — text model + Azure TTS overlay |

The report emits `min`, `p50`, `mean`, `p95`, `max`, and **CoV%**
(coefficient of variation — a noise indicator). Always read p50/p95,
never single samples — LLM + PAYG latency is non-deterministic.

> **Text models via Voice Live** include a TTS overlay, so audio
> duration tracks text length more loosely. Compare TTFA/TTFT for the
> closest apples-to-apples comparison with native realtime models.

### Measuring a fair latency gap (native realtime vs cascade)

When you compare a native realtime model against a text-model-on-Voice-Live
cascade, measure **two separate tracks** — collapsing them is the most common
benchmarking mistake:

| Track | How | What it isolates |
|-------|-----|------------------|
| **Model-isolated** | text input, no mic/VAD/STT | the true model gap (model TTFB + first audio) |
| **End-to-end** | real audio through each rung's native gate | the *experienced* latency, incl. endpointing |

> **Symmetry trap:** if rung A uses `server_vad` and rung B uses
> `azure_semantic_vad` with a longer silence window, an end-to-end comparison is
> measuring **endpointing config**, not the models. Always report the
> model-isolated track as the headline gap, and label the end-to-end track as
> "experience (includes endpointing)".

Decompose the perceived turn into **legs** so you know *which* stage to optimize:

```
[end of user speech] ─▶ speech_stopped ─▶ committed ─▶ first model token ─▶ first audio ─▶ response done
        └──── endpointing/EOU ────┘   └─ model TTFB ─┘   └─ TTS overlay ─┘
```

Anchor each leg on **server events** (plus one client timestamp for the *known*
end of user audio — server events alone can't see when the user actually stopped)
and read the socket **concurrently** with sending audio — a sequential
send-then-read collapses every event that fired during the trailing-silence send
into one burst, zeroing the legs on the fast rung. Always aggregate **p50/p95 +
CoV over ≥5 iterations** and count 429s; a single sample of a PAYG voice pipeline
tells you nothing.

> Tip: a text-model cascade has a **first-audio floor** — the managed TTS overlay
> can't start before the model emits its first token, and that floor is **not
> cuttable client-side**. Spend optimization effort on the legs you *can* move
> (endpointing, retrieval, proactive acks), not on the TTS floor.

### Proactive acknowledgment (perceived-latency lever)

On a turn that triggers a slow tool call or an agent handoff, the model is often
**silent** until the grounded answer is ready — which feels like multiple seconds
of dead air even when total latency is fine. Have the model speak a short
**verification bridge** *before* the slow call:

> "One moment, let me check that." → `tool_call` → grounded answer.

This cuts the **perceived** silence (time-to-first-audio) dramatically. Total
grounded-answer latency is unchanged only if the slow work starts while the ack
is being spoken — so kick off the tool call right after (or concurrently with)
the bridge. It's a pure prompt technique (rung-agnostic). Two rules keep it clean:

- **One filler per turn** — never stack ("One sec. Let me check. Looking now.").
- **Don't ack right after another ack** — if an upstream agent already said it's
  checking, the downstream agent should answer directly.

---

## 8 · UI Plumbing (Gradio + FastRTC)

The demo UI is a **Gradio Blocks** app with a **FastRTC** WebRTC
audio pipe. The architecture is mode-agnostic:

```
Browser mic ──WebRTC──→ FastRTC VoiceHandler ──→ OpenAI Realtime WSS
                              ↕                        ↕
Browser speaker ←─WebRTC─── output_queue ←──── audio delta events
                              ↕
                     AdditionalOutputs ──→ Gradio chatbot (transcript)
```

### Key components

| Component | Role |
|-----------|------|
| `VoiceHandler(AsyncStreamHandler)` | Pipes mic frames into `conn.input_audio_buffer.append()`, receives audio deltas, pushes status events |
| `connect_factory` | Per-rung `@asynccontextmanager` — the ONLY code that differs between rungs |
| `make_session(shared)` | Returns the session config dict per rung |
| `SharedState` | Mutable dataclass: locale, voice, instructions, reset flag |
| `build_ui(rungs, ...)` | Gradio Blocks layout: header, mic, chatbot, voice picker, status |

### Runtime mode switching

The unified demo (`MODE=demo`) registers all rungs and lets the user
swap at runtime from a segmented control — no restart needed:

```python
from voicelive_demo.rungs import REGISTRY
from voicelive_demo.config import Mode

target = REGISTRY[Mode.VOICELIVE]

# Mutate the live handler — next mic click dials the new destination
handler.connect_factory = target.connect_factory
handler.make_session    = target.make_session
handler.name            = target.mode.value
shared.mode             = target.mode

# Snap voice to the new catalog if the current voice is invalid
valid = {name for (_, name, _) in voices_for_mode(target.mode, shared.locale)}
if shared.voice not in valid:
    shared.voice, shared.voice_type = default_voice_for(target.mode, shared.locale)
```

### Localization

All UI strings flow through `i18n.py`. A language switcher toggles:
- UI labels + buttons
- Voice catalog defaults (HD voices per locale)
- System instructions language
- Transcription language (`input_audio_transcription.language`)

Adding a locale = one entry per dict in `i18n.py`.

---

## 9 · Event Handling

All four rungs speak the **same OpenAI Realtime event schema**. Voice
Live exposes identical wire format, event names, and payload shapes.
No mode-specific branching in the handler:

```python
async def handle_event(event):
    etype = event.type

    if etype == "session.created":
        # Session ready — log session_id + model
        pass

    elif etype == "input_audio_buffer.speech_started":
        # User started speaking → clear output queue
        pass

    elif etype == "input_audio_buffer.speech_stopped":
        # User stopped → model is thinking
        pass

    elif etype == "conversation.item.input_audio_transcription.completed":
        # User transcript ready
        pass

    elif etype in ("response.audio.delta", "response.output_audio.delta"):
        # Audio chunk from model → push to speaker
        audio = np.frombuffer(base64.b64decode(event.delta), dtype=np.int16)
        pass

    elif etype in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
        # Assistant transcript complete
        pass

    elif etype in ("response.done", "response.audio.done", "response.output_audio.done"):
        # Turn complete → idle (handler clears status)
        pass

    elif etype == "error":
        # Server error
        pass
```

> The dual event names (`response.audio.*` / `response.output_audio.*`)
> are an SDK preview→GA migration shim. `openai ≥ 2.x` emits only the
> GA names; the legacy names stay as a zero-cost safety net.

### Backend-owned greeting (without polluting transcript history)

To make the assistant greet **before** the user speaks, don't send the greeting
prompt as a user message — that injects a synthetic user turn that leaks into
transcript history and KB/context. Drive a response whose **per-response
`instructions`** carry the greeting instead, so no user-role item is created:

```python
# Typed SDK
await conn.response.create(
    response={
        "instructions": "Greet the caller and ask how you can help. Keep it short.",
        "metadata": {"origin": "backend_initial_greeting"},
    }
)

# Raw JSON (Rungs 2–3)
await conn.send({
    "type": "response.create",
    "response": {
        "instructions": "Greet the caller and ask how you can help. Keep it short.",
        "metadata": {"origin": "backend_initial_greeting"},
    },
})
```

The model speaks the greeting, but no user-role item is ever added — the
transcript starts clean with the assistant's turn. (Per-response `instructions`
augment the session instructions for just that one response.)

---

## 10 · Prerequisites

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) and `ffmpeg` (for FastRTC's
  WebRTC pipe via PyAV)
- Azure AI Foundry resource in a
  [Voice-Live-supported region](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
- A realtime model deployed (e.g., `gpt-realtime-1.5`) — or use
  Voice Live's managed models (no deployment needed)
- Entra ID identity with `Cognitive Services User` on the resource
- (Optional, Rung 3) A Foundry Agent provisioned in the same project

### Quickstart

```bash
git clone https://github.com/unsafecode/voice-live-gradio
cd voice-live-gradio
cp .env.example .env                    # fill endpoints
uv sync
az login --tenant <tenant-id>
uv run app.py                           # http://localhost:7860
```

### Dependencies

```toml
[project]
requires-python = ">=3.13"
dependencies = [
    "openai>=2.0.0",
    "azure-identity>=1.24.0",
    "fastrtc>=0.0.34",
    "gradio>=5.42.0",
    "av>=16.0.0,<17.0.0",
    "pydantic-settings>=2.10.1",
    "aiohttp>=3.12.15",
    "fastapi>=0.116.1",
    "uvicorn>=0.35.0",
]
```

---

## 11 · Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Missing required environment variables` on launch | `.env` not copied | `cp .env.example .env` and set `AZURE_OPENAI_ENDPOINT` + `AZURE_VOICELIVE_ENDPOINT` |
| `401` / `403` on first mic click | Missing `Cognitive Services User` role | Grant the role on the Foundry resource, then re-login |
| `429` on every other turn | PAYG TPM throttling | Bump deployment capacity or lower benchmark iterations |
| WebRTC widget stuck on "Click to Access Microphone" | Browser blocked mic | Allow microphone for `localhost:7860` in browser settings |
| Port 7860 in use | Previous run still bound | `PORT=7861 uv run app.py` or kill the old process |
| Connection timeout to `*.services.ai.azure.com` | Corporate egress filter | Whitelist `*.openai.azure.com`, `*.services.ai.azure.com`, `login.microsoftonline.com` |
| Agent rung greyed out in switcher | `AGENT_ID` / `AGENT_PROJECT_NAME` blank | Provision a Foundry Agent, paste IDs into `.env`, restart |
| Voice quality dips in non-English | Multilingual Neural vs DragonHD | Expected — DragonHD (English) is newer. Try standard Neural voices for crisper output |
| Sovereign cloud `401` | Wrong token scope | Set `AZURE_COGNITIVE_SERVICES_SCOPE` / `AZURE_AI_SCOPE` in `.env` |
| `"Model … is not supported in this region"` | Region doesn't serve that managed model | Check the [Voice Live region/model matrix](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live#supported-models-and-regions) |
| User gets cut off mid-sentence in a non-English call | English-tuned `azure_semantic_vad` ends the turn early on a hesitation/pause | Use the multilingual VAD + multilingual end-of-utterance model; raise `silence_duration_ms` to the locale's pausing (see §3) |
| A tool/KB turn takes several seconds | The **agentic KB planner** (query decomposition / multi-hop reasoning LLM) can dominate — not necessarily the store | Measure the retrieval legs (planner vs search/store vs model vs TTS) separately first. For single-intent lookups, query the index **directly** (semantic search, no planner); reserve the agentic planner for genuine multi-hop |
| `RuntimeError: aiohttp not installed` from `azure-ai-voicelive` | Missing `[aiohttp]` extra | `pip install "azure-ai-voicelive[aiohttp]~=1.2.0"` (async path requires it) |
| `MCPToolApprovalRequest` event mid-turn but no approval reply | `require_approval` set on `MCPServer` | Send `mcp_tool_approval_response` event back; see §12.2 |

---

## 12 · 2026-04-10 GA Deltas

Four features that **only exist on the `2026-04-10` API version** —
all reachable from Rung 4's `azure-ai-voicelive` SDK, all surfaceable
in `session.update` payloads on Rungs 2–3 (typed in SDK, raw JSON in
the openai shim).

### 12.1 · Proactive turn control

The server can **initiate a response without waiting for user audio**
— useful for assistants that need to greet, follow up on silence, or
chase a clarification. Configured on the VAD object via
`create_response: bool` (default `True` — let the server decide when
to respond) and `interrupt_response: bool` (default `True` — barge-in
support).

**Native SDK (Rung 4):**

```python
from azure.ai.voicelive.models import AzureSemanticVad, RequestSession

session = RequestSession(
    turn_detection=AzureSemanticVad(
        threshold=0.5,
        prefix_padding_ms=300,
        silence_duration_ms=500,
        create_response=True,        # ← proactive (server may start a turn)
        interrupt_response=True,     # ← barge-in (server cuts itself off on user speech)
        remove_filler_words=False,
    ),
    modalities=["text", "audio"],
)
await conn.session.update(session=session)

# Manually drive a proactive turn (e.g., after a long silence):
await conn.response.create()
```

**Raw JSON (Rungs 2–3):**

```python
await conn.session.update(session={
    "turn_detection": {
        "type": "azure_semantic_vad",
        "create_response": True,
        "interrupt_response": True,
    },
    "modalities": ["text", "audio"],
})

# Force a proactive turn from the client:
await conn.send({"type": "response.create"})
```

> **Wire impact:** when `create_response: false`, the client owns
> turn-taking — the server emits `input_audio_buffer.speech_stopped`
> events but waits for an explicit `response.create` to speak.

### 12.2 · MCP server tools mid-turn

Voice Live agents can call **MCP servers** during a turn — the model
emits an `mcp_call` event, the server invokes the MCP tool, and the
response flows back into the same turn (no client round-trip).

**Native SDK:**

```python
from azure.ai.voicelive.models import (
    MCPServer,
    MCPApprovalMode,
    RequestSession,
)

mcp_inventory = MCPServer(
    server_label="inventory",
    server_url="https://ca-inventory-mcp.<region>.azurecontainerapps.io/mcp",
    authorization="Bearer <token-from-aca-managed-identity>",   # or Entra
    allowed_tools=["check_stock", "list_skus"],
    require_approval=MCPApprovalMode.NEVER,                     # auto-execute
)

session = RequestSession(
    modalities=["text", "audio"],
    tools=[mcp_inventory],
    instructions="When asked about stock, call inventory.check_stock.",
)
await conn.session.update(session=session)
```

**Approval flow.** When `require_approval=MCPApprovalMode.ALWAYS`,
the server emits `mcp_tool_approval_request`. Reply with an
`mcp_tool_approval_response` event carrying `approve: true|false`
before the turn continues. Cache approvals in the client to avoid
re-prompting per turn.

**Cross-refs:**

- Hosting the MCP server itself on Azure Container Apps → `foundry-mcp-aca`
- Authoring an MCP server with widget rendering for Copilot Chat → `ui-widget-developer`
- The MCP server's RBAC / Entra token plumbing → `foundry-mcp-aca` (Auth section)

### 12.3 · OpenTelemetry instrumentation

Voice Live emits **service-side OTLP traces** for every session —
turn-by-turn spans (`session.created`, `response.created`,
`response.done`) with `gen_ai.*` semantic attributes. The traces
flow through **Foundry diagnostic settings** to App Insights or a
Log Analytics workspace (LAW) — no in-process SDK instrumentation
needed for the WSS pipeline itself.

**Enable on the Foundry resource (one-time, Bicep):**

```bicep
resource voicelive_diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'voicelive-otel'
  scope: foundry_account
  properties: {
    workspaceId: law.id
    logs: [
      { category: 'VoiceLiveSession',  enabled: true }
      { category: 'VoiceLiveAudit',    enabled: true }
      { category: 'RequestResponse',   enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}
```

**Query traces in LAW (KQL):**

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where Category in ("VoiceLiveSession", "RequestResponse")
| extend session_id = tostring(properties_session_id_s)
| extend model = tostring(properties_model_s)
| extend ttfa_ms = todouble(properties_ttfa_ms_d)
| summarize p50_ttfa=percentile(ttfa_ms, 50), p95_ttfa=percentile(ttfa_ms, 95) by model
```

**Client-side OTLP correlation.** If your client (Gradio / FastRTC
process) is already OTel-instrumented (per `foundry-observability`),
pass the W3C `traceparent` header on the WSS handshake via the
SDK's `headers` kwarg. The service stitches client spans into the
same trace ID:

```python
async with connect(
    credential=credential,
    endpoint=endpoint,
    model="gpt-realtime",
    headers={"traceparent": current_traceparent()},
) as conn:
    ...
```

**Cross-ref:** App Insights / LAW ingestion setup, sampler config,
Distro vs vanilla OTel choices → `foundry-observability`.

### 12.4 · Auto-truncation + token-budget governance

Long voice sessions accumulate transcript context that bloats every
turn's prompt → cost and latency creep upward. The 2026-04-10 GA
adds two governance knobs:

1. **`auto_truncate: bool`** on the VAD object — server drops the
   oldest turns from the active context window when the rolling
   token budget would exceed the model's limit. Transparent to the
   client; transcript events are preserved (only the model's input
   context shrinks).
2. **`max_response_output_tokens: int`** on the session — hard cap
   per assistant turn, after which `response.done` fires even if
   the model wanted to keep speaking.

**Native SDK:**

```python
from azure.ai.voicelive.models import (
    AzureSemanticVad,
    RequestSession,
)

session = RequestSession(
    modalities=["text", "audio"],
    max_response_output_tokens=400,           # ~30s of speech at avg rate
    turn_detection=AzureSemanticVad(
        auto_truncate=True,                   # ← drop oldest turns under pressure
    ),
)
await conn.session.update(session=session)
```

**Raw JSON (Rungs 2–3):**

```python
await conn.session.update(session={
    "turn_detection": {"type": "azure_semantic_vad", "auto_truncate": True},
    "max_response_output_tokens": 400,
})
```

**When to use which:**

| Situation | Knob |
|-----------|------|
| Long-running kiosk / phone-bank session | `auto_truncate: true` |
| Cost cap per turn for a paid demo | `max_response_output_tokens: 200` |
| Greeting-only proactive agent (one-shot) | both `auto_truncate: false`, `max_response_output_tokens: 100` |
| Telephony hand-off with strict latency SLA | `max_response_output_tokens: 150` (lower TTFT tail) |

> **Cost observability:** the `usage` payload on `response.done`
> reports `total_tokens_in_context` and `tokens_truncated`. Log
> both to App Insights to right-size the budget per scenario.

---

## References

- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [Voice Live how-to](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to)
- [Voice Live API reference (2026-04-10)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2026-04-10)
- [`azure-ai-voicelive` on PyPI](https://pypi.org/project/azure-ai-voicelive/) · [SDK source](https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/voicelive/azure-ai-voicelive)
- [Azure OpenAI Realtime — concepts](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/audio) · [how-to](https://learn.microsoft.com/azure/ai-services/openai/how-to/realtime-audio)
- [Voice Live quickstart (models)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-quickstart?pivots=programming-language-python)
- [Voice Live quickstart (agents)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart?pivots=programming-language-python)
- [Regional availability](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
- [Demo repo](https://github.com/unsafecode/voice-live-gradio) — running three-rung side-by-side demo with benchmark
- Related skills: `foundry-hosted-agents`, `foundry-prompt-agents`, `foundry-doc-vision-speech`, `foundry-mcp-aca`, `ui-widget-developer`, `foundry-observability`, `azure-tenant-isolation`

---
name: foundry-voice-live
description: >
  Build real-time voice agents with Azure AI Foundry Voice Live (GA 2025-10-01).
  Three-rung migration ladder from Azure OpenAI Realtime to Voice Live to
  Voice Live + Foundry Agent — 3 lines of code change. Covers connection code,
  session config (semantic VAD, echo cancellation, noise reduction, Azure Neural
  HD voices, fast transcription), agent routing triplet, benchmark pattern
  (TTFA/TTFT metrics), and Gradio + FastRTC WebRTC UI plumbing.
  USE FOR: voice live, realtime voice, voice agent, real-time audio, speech to
  speech, voice assistant, Azure Voice Live, websocket voice, realtime API
  migration, semantic VAD, echo cancellation, noise reduction, Neural HD voices,
  FastRTC, Gradio voice, voice benchmark, TTFA, TTFT, voice live agent,
  gpt-realtime, voice-live-gradio.
  DO NOT USE FOR: batch STT/TTS (use foundry-doc-vision-speech), document
  extraction (use foundry-doc-vision-speech), deploying hosted agents without
  voice (use foundry-hosted-agents), prompt agents without voice (use
  foundry-prompt-agents).
metadata:
  version: "1.0.2"
---

# Foundry Voice Live

Build **real-time voice agents** on Azure AI Foundry using Voice Live —
the GA (2025-10-01) server-side voice pipeline that adds semantic VAD,
echo cancellation, noise reduction, and Azure Neural HD voices on top of
the standard Azure OpenAI Realtime API.

The migration from Realtime to Voice Live is **three small code changes**.
This skill walks through those changes, the session config that unlocks
Voice Live features, and the extra routing needed for a Foundry Agent.

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

## 1 · The Three Rungs

The entire migration from "plain Realtime" to "Voice Live + Agent" is a
**diff ladder** — each rung changes only the connection-setup block.

```
Rung 1: Azure OpenAI Realtime        ← the "before"
  │
  ▼  diff = 3 small lines (api_version, websocket_base_url, extra_query)
Rung 2: Azure Voice Live             ← the punchline
  │
  ▼  diff = 1 line (extra_query gains agent-id / -project-name / -access-token)
Rung 3: Voice Live + Foundry Agent   ← the endgame
```

Everything else — the audio pipe, transcript fan-out, status events,
voice picker, UI — is **identical across all three rungs**.

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
        api_version="2025-10-01",                                       # ← GA
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
        api_version="2025-10-01",
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
   is GA on `2025-10-01`.
3. **`extra_query={"model": ...}`** — the SDK adds `&deployment=…` to
   the WSS URL by default; Voice Live keys off `&model=…`, so we add
   it explicitly.

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
AZURE_VOICELIVE_API_VERSION="2025-10-01"         # Voice Live (GA)

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

- `gpt-realtime`, `gpt-realtime-mini` — native realtime
- `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-5-chat` — text + Azure TTS
- `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini` — text + Azure TTS
- `phi4-mm-realtime`, `phi4-mini` — open models

Pass the managed model name in `extra_query={"model": "<name>"}` — no
Foundry-side deployment required.

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

All three rungs speak the **same OpenAI Realtime event schema**. Voice
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

---

## References

- [Voice Live overview](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live)
- [Voice Live how-to](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-how-to)
- [Voice Live API reference (2025-10-01)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-api-reference-2025-10-01)
- [Azure OpenAI Realtime — concepts](https://learn.microsoft.com/azure/foundry/openai/how-to/realtime-audio) · [how-to](https://learn.microsoft.com/azure/ai-services/openai/how-to/realtime-audio)
- [Voice Live quickstart (models)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-quickstart?pivots=programming-language-python)
- [Voice Live quickstart (agents)](https://learn.microsoft.com/azure/ai-services/speech-service/voice-live-agents-quickstart?pivots=programming-language-python)
- [Regional availability](https://learn.microsoft.com/azure/ai-services/speech-service/regions?tabs=voice-live#regions)
- [Demo repo](https://github.com/unsafecode/voice-live-gradio) — running three-rung side-by-side demo with benchmark
- Related skills: `foundry-hosted-agents`, `foundry-prompt-agents`, `foundry-doc-vision-speech`, `azure-tenant-isolation`

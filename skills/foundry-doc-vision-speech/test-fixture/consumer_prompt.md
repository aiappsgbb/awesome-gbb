# Customer goal — `foundry-doc-vision-speech` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-doc-vision-speech`
skill's three documented modalities — Document Intelligence, Speech
(TTS + STT), and vision — all work end-to-end against your CI AI Services
account using **keyless managed-identity auth**.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run every
Bash code block below in order. Do NOT inspect repo files, do NOT run
`validate-skills.py`, do NOT rebuild docs, do NOT `git status` — those are
catalog-author concerns, not consumer-smoke concerns. Your only acceptable
terminal state is a Bash tool call that writes a marker file to
`/tmp/foundry-doc-vision-speech-smoke-result` (Step 5). If you find yourself
reading `skill-deps.yml`, `upstream-pin.md`, or anything under `docs/`, you
are off-script — stop and execute Step 0.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You
ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Doing so spawns
a nested CLI process WITHOUT GitHub auth (the workflow only sets
`COPILOT_PROVIDER_BEARER_TOKEN` for our Foundry routing, NOT
`COPILOT_GITHUB_TOKEN`), which will (a) crash with "No authentication
information found" and (b) overwrite this run's transcript at
`/tmp/foundry-doc-vision-speech-transcript.log`, defeating the workflow's
retry classifier (AGENTS.md § 9.7 Pattern 19 addendum). The workflow
ALREADY captures your output via the outer `tee` — your job is to
EXECUTE Steps 0-5 directly in Bash tool calls, not to "run the smoke".

**This smoke creates NO Azure resources.** Every probe is read-only against
the shared CI AI Services account. There is nothing to tear down beyond the
temp files you write under `/tmp`. Do not create, modify, or delete any
Azure resource.

---

## Step -1 — Acknowledge the skill contract (mandatory FIRST action)

Your first action must be a **separate Bash tool call containing only this
command**. Do not combine it with Step 0 or any later work — the Copilot CLI
transcript collapses each tool call to roughly its first five lines, so a
breadcrumb buried inside a larger block never reaches the text the workflow's
post-hoc audit step greps, and the leg fails even when every probe passes.

It is a cheap audit breadcrumb — do NOT `view` or `cat` the SKILL.md, which
is ~47 KB and would blow the per-turn token budget (AGENTS.md § 9.7
Pattern 19 addendum v2).

```bash
echo "Executing consumer smoke for skills/foundry-doc-vision-speech/SKILL.md"
```

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on the `az` cache
check — copilot subprocesses inherit env vars but NOT `~/.azure/`
(AGENTS.md § 9.7 Pattern 17), so its absence is expected and harmless.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "AZURE_AI_ENDPOINT=${AZURE_AI_ENDPOINT:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

Every `echo` MUST print `...=set`. If any prints empty, the workflow's `env:`
block is broken (AGENTS.md § 9.7 Pattern 11) — that is a workflow bug, not a
skill bug. Write the FAIL marker (Step 5) with reason
`auth context missing: <var-name>` and stop.

Never print the value of `AZURE_AI_ENDPOINT` itself — it is a repository
secret. The `:+set` form above is the only permitted way to reference it in
output.

**CI environment fact you need:** `aif-awesome-gbb-ci` is a multi-service
Azure AI Services account, so Document Intelligence, Speech, and Azure
OpenAI all share the single `$AZURE_AI_ENDPOINT` custom-subdomain endpoint.
There are no separate `DOC_INTEL_ENDPOINT` / `SPEECH_ENDPOINT` secrets — do
not go hunting for them.

---

## Step 1 — Install the pinned SDKs

These are the versions pinned in the skill's `references/upstream-pin.md`.
Use them exactly — the point of this smoke is to prove the pinned versions
work against live Azure.

```bash
python -m pip install --quiet \
  "azure-identity~=1.25.3" \
  "azure-ai-documentintelligence~=1.0.2" \
  "azure-cognitiveservices-speech~=1.51.0" \
  "Pillow~=11.3.0" \
  "requests~=2.32.0" \
  && echo "STEP1_INSTALL=OK"
```

If pip fails, write the FAIL marker with reason `pinned SDK install failed`.

---

## Step 2 — Document Intelligence `prebuilt-read` (keyless)

The skill documents `DocumentIntelligenceClient` +
`DefaultAzureCredential` + `begin_analyze_document("prebuilt-read", ...)`.
Prove it round-trips: render a nonce into a PNG, analyze it, assert the
nonce comes back in the extracted content.

```bash
python - <<'PY'
import io, os, sys
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.identity import DefaultAzureCredential
from PIL import Image, ImageDraw

NONCE = "FDVS smoke nonce 4417"
img = Image.new("RGB", (900, 180), "white")
ImageDraw.Draw(img).text((40, 70), NONCE, fill="black")
buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)

with DocumentIntelligenceClient(
    endpoint=os.environ["AZURE_AI_ENDPOINT"],
    credential=DefaultAzureCredential(),
) as client:
    result = client.begin_analyze_document(
        "prebuilt-read", body=buf, content_type="image/png"
    ).result()

if NONCE not in (result.content or ""):
    print("STEP2_DOCINTEL=FAIL nonce not found in extracted content")
    sys.exit(1)
print("STEP2_DOCINTEL=OK")
PY
```

A 401 here means the UAMI is missing `Cognitive Services User` on the
account scope. A 403 or `AuthenticationFailed` referencing the subdomain
means the account lost its custom subdomain. Either is a real finding —
report it verbatim in the FAIL reason.

---

## Step 3 — Speech TTS to STT round-trip (keyless)

The skill documents `SpeechConfig(token_credential=..., endpoint=...)` — the
modern AAD pattern, **not** the deprecated `auth_token="aad#..."` form.
Synthesize a phrase to a WAV, then recognize that WAV back and compare.

Compare transcripts by order-preserving alphanumeric canonicalization, not
by raw equality — the STT display form inserts punctuation and capitalization
that the synthesized input never had.

```bash
python - <<'PY'
import os, sys, tempfile, pathlib
import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential

PHRASE = "The quick brown fox jumps over the lazy dog"
canon = lambda s: "".join(c for c in s.casefold() if c.isalnum())

wav = pathlib.Path(tempfile.mkdtemp()) / "probe.wav"
cfg = speechsdk.SpeechConfig(
    token_credential=DefaultAzureCredential(),
    endpoint=os.environ["AZURE_AI_ENDPOINT"],
)

synth = speechsdk.SpeechSynthesizer(
    speech_config=cfg,
    audio_config=speechsdk.audio.AudioOutputConfig(filename=str(wav)),
).speak_text_async(PHRASE).get()

if (synth.reason != speechsdk.ResultReason.SynthesizingAudioCompleted
        or not wav.is_file() or wav.stat().st_size == 0):
    print(f"STEP3_SPEECH=FAIL tts reason={synth.reason}")
    sys.exit(1)
print("STEP3_SPEECH_TTS=OK")

rec = speechsdk.SpeechRecognizer(
    speech_config=cfg,
    language="en-US",
    audio_config=speechsdk.audio.AudioConfig(filename=str(wav)),
).recognize_once_async().get()

if rec.reason != speechsdk.ResultReason.RecognizedSpeech:
    detail = getattr(rec, "cancellation_details", None)
    print(f"STEP3_SPEECH=FAIL stt reason={rec.reason} "
          f"code={getattr(detail, 'code', None)}")
    sys.exit(1)
if canon(rec.text) != canon(PHRASE):
    print("STEP3_SPEECH=FAIL stt transcript mismatch")
    sys.exit(1)
print("STEP3_SPEECH_STT=OK")
PY
```

Do NOT print the recognized transcript itself — compare it in memory only.

A 401 here means the UAMI is missing `Cognitive Services Speech User`
(role ID `f2dc8367-1007-4938-bd23-fe263f013447`) on the account scope.
`Cognitive Services User` alone does NOT grant Speech data-plane access.

---

## Step 4 — Vision on `gpt-5.4-mini` (keyless)

The skill documents a raw chat-completions call with a base64 `image_url`
content part and `max_completion_tokens` (**not** `max_tokens`). Prove it:
render a nonce into a PNG and ask the model to read it back.

```bash
python - <<'PY'
import base64, io, os, sys, requests
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from PIL import Image, ImageDraw

NONCE = "8213"
img = Image.new("RGB", (600, 200), "white")
ImageDraw.Draw(img).text((40, 80), f"CODE {NONCE}", fill="black")
buf = io.BytesIO(); img.save(buf, format="PNG")
b64 = base64.b64encode(buf.getvalue()).decode("ascii")

token = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)()
url = (f"{os.environ['AZURE_AI_ENDPOINT'].rstrip('/')}"
       "/openai/deployments/gpt-5.4-mini/chat/completions"
       "?api-version=2024-12-01-preview")

r = requests.post(url, timeout=180,
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    json={"messages": [
        {"role": "system", "content": "You are a precise visual extractor. Output digits only."},
        {"role": "user", "content": [
            {"type": "text", "text": "What is the 4-digit code in this image? Digits only."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ], "max_completion_tokens": 1500})

if r.status_code != 200:
    print(f"STEP4_VISION=FAIL http={r.status_code}")
    sys.exit(1)
answer = r.json()["choices"][0]["message"]["content"] or ""
if NONCE not in answer:
    print("STEP4_VISION=FAIL model did not read the code back")
    sys.exit(1)
print("STEP4_VISION=OK")
PY
```

Never print the bearer token or the endpoint. A 401 means the UAMI is
missing `Cognitive Services OpenAI User` on the account scope.

---

## Step 5 — Marker contract (deterministic, MANDATORY)

Your FINAL action is to invoke the Bash tool to write the marker file. The
file's literal byte content is what CI grades; your assistant-text reply is
NOT graded.

On success — all four of `STEP1_INSTALL=OK`, `STEP2_DOCINTEL=OK`,
`STEP3_SPEECH_STT=OK`, `STEP4_VISION=OK` observed:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-doc-vision-speech-smoke-result
```

On ANY failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-doc-vision-speech-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code blocks
containing the literal string. The Bash tool write is the only legitimate
emission path.

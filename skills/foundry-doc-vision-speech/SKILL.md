---
name: foundry-doc-vision-speech
description: >
  Wire vision (gpt-5.4 family), Document Intelligence v4, and Azure Speech (STT/TTS)
  into a Foundry hosted agent. Reads SPEC § 7b model selection and produces tool
  contracts, Bicep modules, and runtime client code. Replaces all GPT-4o references
  (legacy as of 2025) with gpt-5.4 family models.
  USE FOR: vision tool, image analysis, damage photo analysis, blueprint annotation,
  document extraction, structured doc parsing, OCR, voice intake, FNOL voice claim,
  STT, TTS, gpt-5.4-mini vision, gpt-5.4 vision, Document Intelligence prebuilt,
  custom doc model, Azure Speech, transcription.
  DO NOT USE FOR: deploying the agent itself (use threadlight-deploy), MCP server
  deployment (use foundry-mcp-aca), Foundry IQ knowledge retrieval (use foundry-iq).
---

# Foundry Doc / Vision / Speech

This skill wires the **non-chat AI services** every threadlight process eventually
needs — image understanding, document parsing, voice — into the agent runtime.

It reads SPEC § 7b (AI Services & Model Selection) from `threadlight-design`,
selects the right Azure resource per modality, generates the tool contracts,
and emits the Bicep module selectors that `threadlight-deploy` Phase 6 + 
`azd-patterns` consume.

## When to Use

Use this skill when the SPEC declares ANY of:
- Image / photo / video frame analysis (returns triage damage photos, KYC selfie,
  blueprint annotation, supplier facility photos)
- Structured-document extraction (invoices, claim forms, KYC IDs, quotes, BOMs)
- Voice / audio (FNOL voice intake, call recording transcription, IVR responses)

If the SPEC only needs chat (text-in, text-out), you do NOT need this skill —
the default `gpt-5.4-mini` model from `threadlight-deploy` is sufficient.

## When NOT to Use

- **Pure chat agents** — `threadlight-deploy` handles the chat model
- **Knowledge retrieval over documents** — that's `foundry-iq` (semantic search
  over already-indexed content). Use this skill for the **extraction step that
  produces searchable text from unstructured docs**, then hand off to `foundry-iq`
  for retrieval.
- **MCP server deployment** — that's `foundry-mcp-aca`

---

## ⚠️ GPT-4o is LEGACY (May 2026)

GPT-4o and GPT-4o Vision are explicitly **forbidden** as defaults. SPEC § 7b
hardcodes the modern decision tree:

| Use case | Model | Notes |
|----------|-------|-------|
| Default chat reasoning | `gpt-5.4-mini` (2026-03-17) | 400K context, vision-capable, fastest, cheapest |
| Vision (default) | `gpt-5.4-mini` | Multimodal in same model — usually no separate vision deployment |
| Vision (high-stakes, large frames) | `gpt-5.4` (2026-03-05) | 1M context, more accurate on dense visual content |
| Vision + reasoning premium | `gpt-5.4-pro` | When the answer must reason about the image (e.g., "is this a structural defect?") |
| Bulk/cheap vision | `gpt-5.4-nano` | Background batch jobs, throwaway analysis |
| Code multimodal | `gpt-5.3-codex` | Screenshot → code, error UI → diagnosis |
| Structured docs | Document Intelligence v4 prebuilt | Field extraction with confidence scores; faster than vision LLM for known forms |
| Custom forms | Document Intelligence v4 custom | Train on 5+ samples of customer-specific forms |
| Voice → text | Azure Speech-to-Text (Whisper option) | Fast, batch, real-time options |
| Text → voice | Azure Speech-to-Text (neural voices) | For IVR, audio briefings |

If anyone proposes `gpt-4o`, push back: it doesn't support encrypted content,
has a 128K context vs 400K-1M, and is on a deprecation glide path. There is no
business case for new processes on legacy models.

---

## Decision Tree: Vision vs Document Intelligence vs Speech

```
What kind of unstructured input?
├── IMAGE
│   ├── Known structured form (invoice, ID, claim form, BOM page)
│   │   → Document Intelligence (prebuilt or custom)
│   ├── Free-form photo (damage, facility, blueprint, screenshot, selfie)
│   │   → gpt-5.4-mini vision (or gpt-5.4 if dense / high-stakes)
│   └── Bulk batch (1000s of images, low-stakes)
│       → gpt-5.4-nano vision
│
├── DOCUMENT (PDF / DOCX / scanned)
│   ├── Structured (forms, tables, key-value)
│   │   → Document Intelligence v4 prebuilt
│   ├── Customer-specific (their proprietary form)
│   │   → Document Intelligence v4 custom (train on 5+ samples)
│   └── Free-form / mixed → render page-by-page + gpt-5.4 vision
│
└── AUDIO
    ├── Real-time stream (live call, IVR turn) → Azure Speech-to-Text streaming
    ├── Recorded file (FNOL voicemail, recording)
    │   → Azure Speech-to-Text batch (or Whisper-equivalent endpoint)
    └── TTS for response → Azure Speech neural voices
```

---

## Pattern 0 — Foundry Toolbox (recommended starting point, May 2026)

Before wiring SDK calls per modality, **check whether a Foundry Toolbox can
do the job**. The Foundry Toolbox is a server-side, versioned bundle of
hosted tool configurations curated in the Foundry portal and exposed as a
single MCP-compatible endpoint. As of May 2026, the catalog includes
**Speech, Document Intelligence, Vision, Content Understanding, Translator,
Language, Content Safety, Custom Vision, Azure AI Search**, plus generic
hosted tools (web search, code interpreter, file search, image generation).

**Why prefer Toolbox over per-modality SDK code:**

- **Centralized config**: connection strings, SAS containers, model IDs all
  live in the portal — no env-var fan-out across containers
- **Versioning**: change toolbox config, test with `version="v3"`, promote
  to default — no agent redeploy
- **Auth handled server-side** for the upstream services (e.g. Speech account
  key or Foundry MI scope is configured once at toolbox creation)
- **MCP-compatible consumption**: works with any agent runtime (MAF, GHCP
  SDK, LangGraph, custom code)
- **Same code across processes**: a healthcare KYC and an FSI claim agent
  can both consume the same `vision_doc_speech_toolbox`

**When NOT to use Toolbox** (fall back to direct SDK in Pattern A/B):

- You need fine-grained control over a SDK feature not exposed by the toolbox
  tool wrapper (e.g., DocIntel custom-trained model, Speech batch transcription
  with diarization, real-time streaming audio frames)
- Network-secured Foundry: **Azure Speech MCP doesn't support network-secured
  Foundry projects** as of May 2026 — you must use direct SDK in Pattern A/B
- Toolbox is preview (`azure-ai-projects>=2.1.0`); customer policy may forbid
  preview-tier features in prod
- High-volume batch (e.g., 100k invoices/night) — toolbox introduces a network
  hop the SDK doesn't

**Consumption — Pattern 0a: native (FoundryAgent / FoundryChatClient)**

For a Foundry hosted agent, attach the toolbox in the **portal** when defining
the agent — zero client-side wiring needed. For a `FoundryChatClient` (your
app owns the agent loop), fetch and pass:

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient, select_toolbox_tools
from azure.identity.aio import AzureCliCredential

async with AzureCliCredential() as credential:
    client = FoundryChatClient(credential=credential)
    # Pin the version explicitly to avoid the default-resolve round-trip
    toolbox = await client.get_toolbox("vision_doc_speech_toolbox", version="v3")

    # Optionally narrow: only expose Speech + DocIntel to this agent
    tools = select_toolbox_tools(toolbox, include_names=["azure_speech", "document_intelligence"])

    async with Agent(client=client, name="ClaimsIntake", tools=tools) as agent:
        result = await agent.run("Transcribe the attached call and extract claim details.")
```

**Consumption — Pattern 0b: MCP (any agent runtime, including non-MAF)**

```python
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import Agent, MCPStreamableHTTPTool

credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

# MCP endpoint URL is shown in the Foundry portal; format:
# https://<account>.services.ai.azure.com/api/projects/<project>/toolsets/<name>/mcp?api-version=v1
mcp_tool = MCPStreamableHTTPTool(
    name="vision_doc_speech_mcp",
    url=os.environ["TOOLBOX_MCP_ENDPOINT"],
    header_provider=lambda: {"Authorization": f"Bearer {token_provider()}"},
)

async with Agent(client=client, name="ClaimsIntake", tools=[mcp_tool]) as agent:
    ...
```

> **SDK version pins**: `agent-framework-foundry` (consumption) +
> `azure-ai-projects>=2.1.0` (creation/update). Toolbox APIs are flagged
> **experimental** — surface may change. Caching of `get_toolbox()` is
> caller-owned (no framework cache, because portal-side default version
> can rotate).

**Toolbox catalog reference**: [Foundry tool catalog](https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog)
· [Toolbox how-to (Python)](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
· [Azure Speech MCP](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-ai-speech)

If Toolbox doesn't fit (network-secured project, custom model, high-volume
batch), continue with Pattern A/B per modality below.

---

## Per-Modality Wiring (direct SDK — fallback when Toolbox doesn't fit)

### Vision (default `gpt-5.4-mini` via the Foundry Responses endpoint)

The Foundry Responses endpoint handles vision input as content parts in the
message. No separate model deployment unless SPEC § 7b explicitly upgrades.

There are two equally-valid client patterns — pick by **who owns the agent
loop**:

**Pattern A — Foundry-hosted agent calling vision as a tool** (recommended for
threadlight processes; the agent definition lives in Foundry):

```python
# src/agent/skills/<skill>/handler.py
from typing import Annotated
from agent_framework import tool

@tool(approval_mode="never_require")
async def analyze_damage_photo(
    image_url: Annotated[str, "Public/SAS URL of the damaged-product photo"],
    claim_id: Annotated[str, "Claim case_id this photo belongs to"],
) -> dict:
    """Score damage 1-10 and extract visible fields from the photo."""
    # The hosted agent's chat model handles the vision content part;
    # this tool just preps the input and returns a structured result.
    from openai import AsyncAzureOpenAI
    # The Foundry Responses endpoint accepts standard OpenAI client calls
    response = await openai_client.responses.create(
        model="gpt-5.4-mini",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Score the damage 1-10 and extract visible fields. Return JSON."},
                {"type": "input_image", "image_url": image_url},
            ],
        }],
        response_format={"type": "json_object"},
    )
    return json.loads(response.output_text)
```

The `openai_client` is obtained at agent startup. The Foundry Responses endpoint
exposes Async OpenAI client calls; create it with the async AIProjectClient and
pass `agent_name=` so calls are routed to the bound hosted agent:

```python
from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential

async with (
    DefaultAzureCredential() as cred,
    AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=cred,
        allow_preview=True,   # required when using agent_name on get_openai_client
    ) as project,
):
    openai_client = project.get_openai_client(agent_name=AGENT_NAME)
    # Inject openai_client into the agent runtime / tool registry
    ...
```

**Pattern B — Standalone agent with `FoundryChatClient`** (when your app owns
the agent loop, instructions, tools — e.g., from a receiver scaffold or batch
job):

```python
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import AzureCliCredential

agent = Agent(
    client=FoundryChatClient(
        project_endpoint=PROJECT_ENDPOINT,
        model="gpt-5.4-mini",
        credential=AzureCliCredential(),
    ),
    name="DamageAnalyzer",
    instructions="You score photos for damage and extract visible fields.",
)
response = await agent.run([
    {"type": "input_text", "text": "Score 1-10 and extract."},
    {"type": "input_image", "image_url": image_url},
])
```

For the high-stakes path (e.g., medical, structural defect, fraud-detect),
swap the model to `gpt-5.4-pro` — same API shape, different deployment name.

> **SDK version pin (May 2026)**: `agent-framework`, `agent-framework-foundry`,
> `azure-ai-projects>=2.0.0`. Imports moved out of the legacy `agent_framework.azure`
> namespace — use `from agent_framework.foundry import FoundryChatClient` (not the
> old `AzureAIAgentClient`).

### Document Intelligence v4 (prebuilt)

Use prebuilt models for ID, invoice, receipt, business card, contract,
W-2, tax forms, layout. Returns structured JSON + confidence scores.

```python
# src/agent/skills/<skill>/handler.py
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.identity.aio import DefaultAzureCredential

async def extract_invoice(blob_url: str) -> dict:
    async with (
        DefaultAzureCredential() as cred,
        DocumentIntelligenceClient(endpoint=DOC_INTEL_ENDPOINT, credential=cred) as client,
    ):
        # NOTE: the modern SDK uses positional `body=` (not `analyze_request=`)
        poller = await client.begin_analyze_document(
            model_id="prebuilt-invoice",
            body=AnalyzeDocumentRequest(url_source=blob_url),
        )
        result = await poller.result()
    fields = result.documents[0].fields
    return {
        "invoice_number": fields["InvoiceId"].value_string,
        "vendor": fields["VendorName"].value_string,
        "total": float(fields["InvoiceTotal"].value_currency.amount),
        "_confidence": min((f.confidence for f in fields.values() if f.confidence), default=0.0),
    }
```

> **SDK version pin**: `azure-ai-documentintelligence>=1.0.2`. The v4 REST surface is
> `2024-11-30 (GA)`. The package was renamed from `azure-ai-formrecognizer` —
> do NOT pull the legacy package.

Threshold rule: if `_confidence < 0.85`, escalate to vision LLM for double-check
(exposes the field to the human action gate via `request-info`).

### Document Intelligence v4 (custom)

For customer-specific forms (their proprietary KYC questionnaire, their PIM
attribute sheet, their FNOL incident report). Requires training:

```bash
# scripts/train_custom_doc_model.py
az cognitiveservices document-intelligence model build \
  --resource-group <rg> \
  --account-name <docintel-account> \
  --model-id customer-kyc-form-v1 \
  --description "ContosoBank KYC questionnaire" \
  --build-mode template \
  --azure-blob-source <sas-url-to-training-set>
```

Training set: ≥ 5 samples of the form, labeled via Document Intelligence
Studio. Output is a custom model ID you reference in `prebuilt-invoice`'s slot.

### Azure Speech-to-Text

For voice-driven processes (FNOL, call center QA, IVR). Two patterns:

```python
# Real-time streaming (inside an MCP tool that proxies audio)
import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential

# Modern AAD pattern: pass token_credential directly + custom-domain endpoint
# (NOT the older auth_token="aad#..." pattern, which is still supported but deprecated).
# Speech resource MUST have a custom subdomain enabled (one-time:
#   az cognitiveservices account update --custom-domain <name>).
credential = DefaultAzureCredential()
speech_config = speechsdk.SpeechConfig(
    token_credential=credential,
    endpoint=os.environ["SPEECH_ENDPOINT"],  # https://<custom-name>.cognitiveservices.azure.com/
)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, language="en-US")
result = await asyncio.to_thread(recognizer.recognize_once)
transcript = result.text
```

> **RBAC pin**: assign `Cognitive Services Speech User` (or `Speech Contributor`)
> to the UAMI on the Speech account scope.
> **SDK version pin**: `azure-cognitiveservices-speech>=1.40.0` for `token_credential`
> support on `SpeechConfig`. Older versions silently ignore it.

For batch (e.g., a 5-minute FNOL voicemail), use the Speech Batch Transcription
API — submits a job, returns transcript JSON when complete.

---

## SPEC § 7b decision rules (what this skill expects to read)

The spec template forbids GPT-4o and prescribes the May-2026 model lineup.
This skill assumes those rules are followed; if SPEC § 7b says `gpt-4o`,
**fail loudly** and ask the spec author to update.

```yaml
# specs/SPEC.md § 7b (excerpted)
ai_services:
  chat: { model: gpt-5.4-mini, deployment: chat-default }
  vision:
    model: gpt-5.4-mini    # OR gpt-5.4 / gpt-5.4-pro / gpt-5.4-nano per use case
    use_case: free-form-photo
  doc_intel:
    tier: S0
    models: [prebuilt-invoice, prebuilt-id-document]
  speech:
    tier: S0
    region: eastus      # match Foundry region for low latency
    capabilities: [stt, tts]
```

---

## Bicep modules emitted (delegates to `azd-patterns`)

This skill does NOT own Bicep module shapes — those live in
`azd-patterns/SKILL.md` → "Composable Bicep Module Library". This skill
selects which modules `threadlight-deploy` Phase 6 includes:

| If SPEC § 7b includes... | Module included | Owner |
|--------------------------|-----------------|-------|
| `vision` with non-default model | `infra/modules/vision.bicep` (separate model deployment in the Foundry account) | this skill |
| `doc_intel` | `infra/modules/doc-intel.bicep` | this skill |
| `speech` | `infra/modules/speech.bicep` | this skill |

If `vision.model == gpt-5.4-mini` (the chat default), no separate vision module
is needed — the chat deployment handles vision content parts natively.

---

## Tool Contracts (template)

Generated tools always follow this shape, so they compose cleanly with the
agent's other tool-using skills:

```python
@tool(approval_mode="never_require")
async def analyze_damage_photo(image_url: str, claim_id: str) -> dict:
    """Score damage 1-10 and extract visible fields from a damaged-product photo.
    Use ONLY when the SPEC business rule requires visual evidence.
    Returns: { score: int 1-10, severity: str, visible_fields: dict, confidence: float }
    """
    ...
```

Tool naming: verb_noun snake_case, prefixed by modality
(`analyze_*`, `extract_*`, `transcribe_*`, `synthesize_*`).

---

## Input contract / Output artifacts

| Reads | From |
|-------|------|
| **SPEC.md § 7b AI Services & Model Selection** | `threadlight-design` |
| **SPEC.md § 6 Tool Contracts** (where the consuming tool is declared) | `threadlight-design` |
| **SPEC.md § 11d Demo Data** (which sample images / docs / audio to ship) | `threadlight-design` (via `threadlight-demo-data-factory`) |

| Produces | At |
|----------|-----|
| `src/agent/skills/<skill>/handler.py` | One handler per declared visual / doc / voice tool |
| `src/agent/skills/<skill>/SKILL.md` | Skill definition; lists the tool contracts |
| Module selectors for `infra/main.bicep` | `vision`, `doc_intel`, `speech` keys consumed by Phase 6 |
| `agent.yaml` env vars | `VISION_DEPLOYMENT_NAME`, `DOC_INTEL_ENDPOINT`, `SPEECH_ENDPOINT`, `SPEECH_REGION` |
| `tests/eval-scenarios.yaml` additions | Per-tool eval scenarios (happy / boundary / negative) |
| Training scripts | `scripts/train_custom_doc_model.py` if `doc_intel.models` includes a `customer-*` ID |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](../threadlight-design/) | Generates SPEC.md § 7b — the input contract |
| [**threadlight-deploy**](../threadlight-deploy/) | Phase 6 (Module Composer) wires the Bicep modules this skill selects |
| [**azd-patterns**](../azd-patterns/) | Owns the Bicep module shapes (`vision.bicep`, `doc-intel.bicep`, `speech.bicep`) |
| [**foundry-iq**](../foundry-iq/) | Pairs with this skill: extract structured text from docs (this skill) → index it for retrieval (foundry-iq) |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | If the vision / doc / speech tool needs to wrap a mocked external system |
| [**threadlight-demo-data-factory**](../threadlight-demo-data-factory/) | Generates the sample images / docs / audio for the demo |
| [**foundry-evals**](../foundry-evals/) | Evaluates per-tool accuracy (extraction precision, vision-score correlation, transcription WER) |

---

## Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Vision tool returns gibberish | Wrong content-part type | Use `input_image` not `image` for the Responses API |
| Document Intelligence times out | Large PDF (>500 pages) | Pre-split into chunks of ≤100 pages |
| Custom doc model accuracy < 80% | Training set < 5 samples or labels inconsistent | Add 10+ samples; re-label in Studio for consistency |
| Speech 401 with managed identity | Speech needs `Cognitive Services User` role assignment | Assign UAMI to Speech account scope |
| `gpt-4o` referenced in SPEC | Legacy model | **Fail loudly** — ask spec author to update to `gpt-5.4-mini` per SPEC template § 7b rules |
| Vision response slow (>30s) | Image too large (>4MP) | Pre-resize to 2048px max edge before passing to vision |
| TTS audio file too large | Default WAV format | Use compressed `audio-24khz-48kbitrate-mono-mp3` output format |
| Document Intelligence cost spike | Calling per-page on multi-page docs | Single API call handles whole doc — don't loop |

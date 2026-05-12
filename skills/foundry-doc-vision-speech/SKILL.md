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
metadata:
  version: "1.0.0"
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
- **Auth handled server-side** for the upstream services (Speech / DocIntel
  account credentials are configured **once** at toolbox creation; the
  consumer only needs an Entra token to the Toolbox endpoint itself)
- **MCP-compatible consumption**: works with any agent runtime (MAF, GHCP
  SDK via bridge, LangGraph, custom code)
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

### Pattern 0a — DEFAULT: MCP consumption (works with ALL runtimes)

**Always start here.** `MCPStreamableHTTPTool` (or your runtime's equivalent
MCP client) talks to the Toolbox endpoint over HTTPS. This is the path the
Foundry team officially documents for MAF, GHCP (via bridge), LangGraph,
and custom code.

**Working sample (MAF — direct, with mandatory workarounds):**

```python
import os, asyncio
from typing import Any
# Use the SYNC azure.identity here — get_bearer_token_provider in the sync
# module returns a callable that returns a string when invoked. Using the
# .aio variant here returns a coroutine that gets f-string-formatted as
# "Bearer <coroutine object _provider at 0x...>" and the server returns 401.
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from agent_framework import Agent, MCPStreamableHTTPTool
from agent_framework.foundry import FoundryChatClient

# 1. Build a refreshing Entra token provider for the Toolbox MCP endpoint.
#    Scope MUST be https://ai.azure.com/.default — wrong scope = 401.
credential = DefaultAzureCredential()  # reads AZURE_CLIENT_ID for UAMI
token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

# 2. Build the MCP tool.
#    Endpoint format (note the "toolboxes/.../versions/.../mcp" shape — pin a version):
#    https://<account>.services.ai.azure.com/api/projects/<project>/toolboxes/<name>/versions/<version>/mcp?api-version=v1
mcp_tool = MCPStreamableHTTPTool(
    name="vision_doc_speech_mcp",
    url=os.environ["TOOLBOX_MCP_ENDPOINT"],
    # GOTCHA: MAF calls header_provider(kwargs) — it MUST accept one positional
    # arg, not zero. Verified against agent_framework/_mcp.py in 1.x.
    # Use header_provider (NOT static `headers=`) so tokens refresh on expiry.
    header_provider=lambda kwargs: {"Authorization": f"Bearer {token_provider()}"},
    load_prompts=False,         # GOTCHA: Foundry MCP returns 500 on prompts/list
)

# 3. GOTCHA: MAF's MCPStreamableHTTPTool._ensure_connected() calls send_ping(),
#    which the Foundry MCP server rejects with 500. Override to a no-op.
async def _no_ping(*args: Any, **kwargs: Any) -> None: return None
mcp_tool._ensure_connected = _no_ping  # type: ignore[assignment]

async def main() -> None:
    async with mcp_tool, Agent(
        client=FoundryChatClient(credential=credential, model="gpt-5.4-mini"),
        name="ClaimsIntake",
        tools=[mcp_tool],
    ) as agent:
        # GOTCHA: Toolbox MCP requires stream=True on tools/call.
        # MAF Agent.run streams by default — explicitly avoid stream=False overrides.
        result = await agent.run("Transcribe the call and extract claim details.")
        print(result.text)

asyncio.run(main())
```

**Working sample (GHCP — via the official MCP bridge):**

GHCP rejects dots in tool names; Foundry MCP returns names as
`{server_label}.{tool_name}`. The official sample at
`https://aka.ms/foundry-toolbox-copilotsdk` provides an MCP bridge that
replaces `.` → `_` automatically. Use that bridge — do NOT roll your own.

> **GHCP cannot use Pattern 0b (native).** Native toolbox attachment
> (`tools=toolbox` directly) is a MAF-specific surface that has no
> equivalent in the GitHub Copilot SDK. For GHCP, **Pattern 0a is the
> only option** — and you must use the published bridge.

**MCP gotcha cheat-sheet** (from official troubleshoot, all confirmed
May 2026 — these WILL bite if ignored):

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401` on MCP calls | Wrong/expired token | Scope MUST be `https://ai.azure.com/.default`; use `header_provider` (refreshes), not static `headers` |
| `500` on `send_ping()` | Foundry MCP doesn't implement `ping` | Override `MCPStreamableHTTPTool._ensure_connected` to a no-op (see sample) |
| `500` on `prompts/list` | Foundry MCP doesn't implement prompts | Pass `load_prompts=False` |
| `500` on `tools/call` | Non-streaming not supported | Use `stream=True` (MAF default; explicitly verify if you override) |
| `400 Multiple tools without identifiers` | Two unnamed tools of same type in toolbox | Toolbox creator must add `server_label`/`name` to each MCP tool |
| Tool name not found / GHCP error | Foundry returns `{server_label}.{tool_name}`; GHCP rejects dots | GHCP: use the bridge that swaps `.` → `_`. MAF: use the dotted name as-is |
| Custom env var silently overwritten | Platform reserves `FOUNDRY_*` prefix | Rename your env vars (e.g. `TOOLBOX_MCP_ENDPOINT`, NOT `FOUNDRY_TOOLBOX_ENDPOINT`) |

### Pattern 0b — Native (MAF-only, **EXPERIMENTAL — verify before shipping**)

Pass the toolbox object directly as `tools=` to a MAF `FoundryChatClient`
or attach it server-side to a `FoundryAgent` in the Foundry portal. This
path is cleaner code-wise but:

- **GHCP SDK does NOT support this** — use Pattern 0a with the bridge instead
- **MAF support is preview** — `agent-framework-foundry` Toolbox APIs are
  flagged experimental; surface may change between releases
- **Behaviour drift between native and MCP** has been observed in preview
  builds — always smoke-test the agent before declaring the pilot ready

If you're on MAF and want to try it:

```python
# MAF only — preview, verify in your env before committing
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient, select_toolbox_tools
from azure.identity.aio import AzureCliCredential

async with AzureCliCredential() as credential:
    client = FoundryChatClient(credential=credential)
    toolbox = await client.get_toolbox("vision_doc_speech_toolbox", version="v3")
    tools = select_toolbox_tools(toolbox, include_names=["azure_speech", "document_intelligence"])
    async with Agent(client=client, name="ClaimsIntake", tools=tools) as agent:
        result = await agent.run("Transcribe and extract claim details.")
```

If something silently misbehaves (tools listed but never invoked, partial
schemas, schema-inference errors), **fall back to Pattern 0a (MCP)** — it
exercises the same upstream Toolbox endpoint with strictly fewer SDK
abstractions in between.

### Keyless RBAC for Toolbox consumption

Everything below assumes **keyless** auth — no API keys are passed anywhere
in the threadlight chain (we set `disableLocalAuth: true` on every Cognitive
Services resource at provisioning time per `azd-patterns`).

| Identity | Role | Scope | Why |
|----------|------|-------|-----|
| **Consuming agent's UAMI** | `Azure AI User` | Foundry project | Required to mint tokens for `https://ai.azure.com/.default` and read the toolbox MCP endpoint |
| **Toolbox creator (one-time, not runtime)** | `Azure AI Project Manager` | Foundry project | Needed to create/update toolbox versions and assign `Azure AI User` to consumers |
| **Foundry project's own MI** | `Azure AI User` | Foundry account | Project proxies inference + reads upstream tool credentials configured in toolbox |
| **Upstream service identities** (Speech / DocIntel / Vision MI) | per-service role (see Pattern A/B below) | each Cognitive Services resource | Configured ONCE at toolbox creation — consumers never see these |

> **Why `Azure AI User` and not `Azure AI Developer`?** `Azure AI Developer`
> is scoped to the legacy AML / Foundry-hub world; hosted-agent + toolbox
> resources need `Azure AI User` (or higher: `Azure AI Project Manager`).

**Toolbox catalog reference**: [Foundry tool catalog](https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog)
· [Toolbox how-to (Python)](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
· [Toolbox troubleshoot](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox#troubleshoot)
· [Hosted-agent permissions](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agent-permissions)
· [Azure Speech MCP](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/azure-ai-speech)
· [GHCP toolbox bridge sample](https://aka.ms/foundry-toolbox-copilotsdk)
· [MAF toolbox MCP sample](https://aka.ms/foundry-toolbox-maf)

If Toolbox doesn't fit (network-secured project, custom model, high-volume
batch), continue with Pattern A/B per modality below.

---

## ⚠️ Keyless / RBAC Matrix (every modality, every pattern)

Threadlight pilots are **keyless by default**. Every Cognitive Services
resource (`AIServices`, `DocumentIntelligence`, `SpeechServices`) is
provisioned with `properties.disableLocalAuth: true` per `azd-patterns`,
and runtime auth is via UAMI + Entra token. **No `KEY1` / `subscription_key`
appears anywhere in the chain.** When a customer needs to roll back to keyed
auth (rare — typically air-gapped lab), they explicitly opt in.

### The matrix

| Modality | Identity | Role assignment | Token scope | Notes |
|----------|----------|-----------------|-------------|-------|
| **Foundry chat (Responses endpoint)** | Agent's UAMI | `Azure AI User` on the **Foundry project** | `https://ai.azure.com/.default` | Project proxies inference using its own MI; this is the threadlight default |
| **Direct AOAI account endpoint** (bypassing project) | Agent's UAMI | `Cognitive Services OpenAI User` on the **Foundry account** | `https://cognitiveservices.azure.com/.default` | Only when you must hit the account endpoint — rare |
| **Foundry Toolbox via MCP** | Agent's UAMI | `Azure AI User` on Foundry project | `https://ai.azure.com/.default` | Toolbox creator (one-time) needs `Azure AI Project Manager` |
| **Vision via Foundry Responses** | Same as chat | Same as chat | Same as chat | Vision is a content-part on the chat call — no extra role |
| **Document Intelligence (direct SDK)** | Agent's UAMI | `Cognitive Services User` on the **DocIntel resource** | `https://cognitiveservices.azure.com/.default` | **NOT `Cognitive Services Contributor`** — Contributor only allows listing keys, and is denied at runtime when `disableLocalAuth: true`. Verified May 2026. |
| **Azure Speech (direct SDK)** | Agent's UAMI | `Cognitive Services Speech User` (or `Speech Contributor`) on the **Speech resource** | `https://cognitiveservices.azure.com/.default` | **REQUIRES custom subdomain** (one-time, **IRREVERSIBLE** — see Speech section) |
| **Azure AI Search (foundry-iq RAG)** | Agent's UAMI | `Search Index Data Reader` on Search service | `https://search.azure.com/.default` | Add `Search Service Contributor` for index management roles only |
| **Foundry continuous-eval** (Plan A built-in) | **Foundry project's own MI** (NOT the agent's UAMI) | `Azure AI User` on the project | n/a (server-side) | Project MI runs the scheduled evaluators against the agent — no consumer code |
| **Continuous-eval (Plan B ACA Job)** | Job's UAMI | `Azure AI User` on project + `Storage Blob Data Contributor` on results container | `https://ai.azure.com/.default` | Only if Plan A doesn't yet support your hosted-agent type |

### Why these specific roles (don't substitute)

- **`Azure AI Developer` is INSUFFICIENT** for hosted agents — it's scoped to
  the legacy AML/Foundry-hub world, not Foundry-project resources used by
  hosted agents. Use `Azure AI User` instead.
- **`Cognitive Services Contributor` does NOT work for keyless data-plane**:
  Contributor lists/regenerates keys; when `disableLocalAuth: true`, the
  data-plane explicitly rejects requests authenticated via Contributor.
  You need the `*User` data-plane role.
- **`Azure AI Project Manager` and `Azure AI Account Owner`** can ONLY assign
  `Azure AI User` to other principals (Microsoft-imposed constraint). They
  CANNOT grant arbitrary custom roles. If your customer needs a custom role,
  use `Owner` or `User Access Administrator` for the role-assignment step.

### Bicep wiring (pattern, per `azd-patterns`)

```bicep
// infra/modules/rbac.bicep — assign UAMI to each Cognitive Services resource
resource docIntelUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: docIntelAccount  // resource symbolic name
  name: guid(docIntelAccount.id, agentUami.id, cognitiveServicesUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'a97b65f3-24c7-4388-baec-2e87135dc908'  // Cognitive Services User
    )
    principalId: agentUami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource speechUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: speechAccount
  name: guid(speechAccount.id, agentUami.id, speechUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'f2dc8367-1007-4938-bd23-fe263f013447'  // Cognitive Services Speech User
    )
    principalId: agentUami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectAiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundryProject
  name: guid(foundryProject.id, agentUami.id, azureAiUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '53ca6127-db72-4b80-b1b0-d745d6d5456d'  // Azure AI User
    )
    principalId: agentUami.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
```

> **Verification step (always run before declaring the pilot ready):**
> from inside the running container, `az login --identity --client-id $AZURE_CLIENT_ID`
> then `az rest --method GET --uri "<resource-endpoint>/health"` to confirm
> the token works against each Cognitive Services data-plane. Don't ship a
> pilot where you've never proven RBAC end-to-end.

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
    # The Foundry Responses endpoint accepts standard OpenAI client calls.
    # Vision JSON-mode on the Responses API uses `text={"format": {...}}`,
    # NOT the Chat-Completions `response_format=` kwarg. Verified against
    # openai-python (responses.py) — passing response_format silently degrades
    # to free-form text and breaks json.loads downstream.
    response = await openai_client.responses.create(
        model="gpt-5.4-mini",
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Score the damage 1-10 and extract visible fields. Return JSON."},
                {"type": "input_image", "image_url": image_url},
            ],
        }],
        text={"format": {"type": "json_object"}},
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
> **Keyless RBAC pin**: assign `Cognitive Services User` (NOT Contributor — see
> matrix above) to the agent UAMI on the DocIntel resource scope. `DefaultAzureCredential`
> picks up the UAMI via `AZURE_CLIENT_ID` env var injected by ACA.

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

> ### ⚠️ ONE-WAY DOOR: Custom subdomain is IRREVERSIBLE
>
> Keyless auth on Speech resources **requires a custom subdomain**. The
> only way to set one is:
>
> ```bash
> az cognitiveservices account update \
>   --name <speech-acct> --resource-group <rg> \
>   --custom-domain <unique-subdomain-name>
> ```
>
> **Once set, you cannot remove it.** The regional endpoint
> (`eastus.api.cognitive.microsoft.com`) is permanently disabled for that
> account — only the custom endpoint (`<your-name>.cognitiveservices.azure.com`)
> works. To revert, you must **delete the resource and re-create it**
> (which is destructive — costs include re-training custom voice models,
> re-issuing client SDK endpoints, etc.).
>
> Surface this warning in the deploy script and force a `--confirm-irreversible`
> flag before running it. Don't bury it in docs the operator will skim past.

```python
# Real-time streaming (inside an MCP tool that proxies audio)
import azure.cognitiveservices.speech as speechsdk
from azure.identity import DefaultAzureCredential

# Modern AAD pattern: pass token_credential directly + custom-domain endpoint
# (NOT the older auth_token="aad#..." pattern, which is still supported but deprecated).
# Speech resource MUST have a custom subdomain enabled (see warning above).
credential = DefaultAzureCredential()
speech_config = speechsdk.SpeechConfig(
    token_credential=credential,
    endpoint=os.environ["SPEECH_ENDPOINT"],  # https://<custom-name>.cognitiveservices.azure.com/
)
recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, language="en-US")
result = await asyncio.to_thread(recognizer.recognize_once)
transcript = result.text
```

> **Keyless RBAC pin**: assign `Cognitive Services Speech User`
> (role ID `f2dc8367-1007-4938-bd23-fe263f013447`) to the UAMI on the
> Speech account scope. `Speech Contributor` also works but is broader —
> prefer least privilege.
> **SDK version pin**: `azure-cognitiveservices-speech>=1.40.0` for `token_credential`
> support on `SpeechConfig`. Older versions silently ignore it and fall back to
> key auth, which then fails with `disableLocalAuth: true`.
> **Custom subdomain**: see one-way-door warning above.

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

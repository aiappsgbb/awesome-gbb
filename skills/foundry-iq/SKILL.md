---
name: foundry-iq
description: >
  Build enterprise RAG into every threadlight process via Foundry IQ — Azure AI Search
  Knowledge Bases with agentic retrieval (multi-hop reasoning, query planning,
  citation-backed responses). DEFAULT knowledge retrieval pattern for every
  threadlight process; SPEC § 7 must declare a Knowledge Base for the process domain.
  USE FOR: knowledge base, RAG, agentic retrieval, policy assistant, citations,
  multi-hop QA, Knowledge Agent, AI Search Knowledge Base, document grounding,
  semantic retrieval, foundry-iq, knowledge index, hybrid search, vector search.
  DO NOT USE FOR: structured-document extraction (use foundry-doc-vision-speech),
  MCP server deployment (use foundry-mcp-aca), agent runtime (use threadlight-deploy).
metadata:
  version: "1.2.2"
---

# Foundry IQ Agent Framework Integration Skill

> **Default knowledge retrieval pattern for EVERY threadlight process.**
> SPEC § 7 (Knowledge Sources) must declare at least one Knowledge Base per process,
> with `Backing service: foundry-iq` (the default — alternatives are `mcp-search`
> or `inline-context` only when foundry-iq is genuinely overkill, e.g., a process
> with literally zero domain documents).
>
> See `threadlight-design/SKILL.md` → "Knowledge sources (default = foundry-iq)"
> for the rule. This skill is the implementation of that default.

## Input contract / Output artifacts

| Reads | From |
|-------|------|
| **SPEC.md § 7 Knowledge Sources** (Backing service, sources list, expected query patterns) | `threadlight-design` |
| Documents from blob storage / SharePoint / GitHub (sources declared in § 7) | Customer / `threadlight-demo-data-factory` for demo seed corpus |

| Produces | At |
|----------|-----|
| Azure AI Search index | One per Knowledge Base in SPEC § 7 |
| Knowledge Agent (in Foundry project) | One per Knowledge Base; reasoning effort per § 7 spec |
| `infra/modules/foundry-iq-index.bicep` | Composed by `azd-patterns` Bicep library; included by `threadlight-deploy` Phase 6 when SPEC § 7 declares foundry-iq |
| `infra/scripts/bootstrap_foundry_iq.py` | Postprovision hook that creates the index + uploads documents + creates the Knowledge Agent |
| `src/agent/skills/<knowledge-skill>/SKILL.md` | Skill that wraps the Knowledge Agent retrieval call as a tool |
| `agent.yaml` env vars | `FOUNDRY_IQ_INDEX`, `FOUNDRY_IQ_AGENT_NAME`, `AI_SEARCH_ENDPOINT` |

---

## Folder Contents

| File | Type | Description |
|------|------|-------------|
| `SKILL.md` | Documentation | Main skill documentation with architecture, API reference, and agentic retrieval deep dive |
| `PRD.md` | Documentation | Product Requirements Document for the skill |
| `.env.sample` | Configuration | Sample environment variables for Azure OpenAI and AI Search |
| `requirements.txt` | Dependencies | Python package dependencies (azure-search-documents, azure-ai-projects, fastapi) |
| **scripts/** | | |
| `scripts/__init__.py` | Module | Package initializer with exports |
| `scripts/search_index_manager.py` | Index Manager | Creates and manages Azure AI Search indexes with vector search and HNSW configuration |
| `scripts/document_indexer.py` | Indexer | Document chunking with sentence boundary detection and batch upload to search index |
| `scripts/knowledge_agent_manager.py` | Agent Manager | Creates Knowledge Agents with configurable reasoning effort; KnowledgeAgentRetriever for multi-turn retrieval |
| `scripts/azure_openai_client.py` | LLM Client | Azure OpenAI client for chat completions; PolicyBot combining retrieval + generation |

---

## Overview

Foundry IQ is Microsoft's enterprise-grade RAG solution that treats retrieval as a reasoning task. It uses Azure AI Search Knowledge Bases with agentic retrieval to enable multi-hop reasoning, query planning, and citation-backed responses.

> ### Knowledge Bases migration callout (May 2026)
>
> Two control-plane surfaces exist side by side; **they are NOT
> interchangeable** and you must pin to one consciously:
>
> | Surface | api-version | Endpoint shape | Wire shape |
> |---------|-------------|----------------|------------|
> | **Legacy "Knowledge Agents"** | `2025-01-01-preview` | `PUT /agents/<name>` | `configuration: { reasoningEffort, outputMode }` (nested) |
> | **New "Knowledge Bases"** | `2025-11-01-preview` | `PUT /knowledgebases/<name>` | top-level `retrievalReasoningEffort` + `outputConfiguration: { modality }` (flat) |
>
> The scripts in this skill are pinned to the legacy `/agents/` surface
> for compatibility with tenants that haven't yet been migrated. To opt
> into Knowledge Bases:
> 1. Bump `AI_SEARCH_API_VERSION` to `2025-11-01-preview`.
> 2. Replace the `/agents/<name>` path with `/knowledgebases/<name>` in
>    `KnowledgeAgentManager._make_request` callers and
>    `KnowledgeAgentRetriever.retrieve`.
> 3. The wire shape change in step 1 is already implemented in
>    `knowledge_agent_manager.create_agent` (see the wire-format note
>    inline in the function), but the legacy endpoint will reject the
>    flat shape — the two MUST move together.
>
> Output mode values are also camelCase on the wire — `extractiveData`,
> NOT `extractive_data`. The previous snake_case form was a docs typo
> that the legacy endpoint silently ignored.

---

## Architecture

```
+---------------------------------------------------------------------+
|                    Foundry IQ Architecture                           |
+---------------------------------------------------------------------+
|                                                                      |
|  +----------------+    +------------------+    +-----------------+   |
|  |   Documents    |--->|  Azure AI Search |--->| Knowledge       |   |
|  |   (Blob)       |    |     Index        |    | Agent           |   |
|  +----------------+    +------------------+    +-----------------+   |
|                                                        |             |
|                                                        v             |
|  +----------------+    +------------------+    +-----------------+   |
|  |   FastAPI      |<-->|  Agent Framework |<-->| Agentic         |   |
|  |   Endpoint     |    |  (ChatAgent)     |    | Retrieval       |   |
|  +----------------+    +------------------+    +-----------------+   |
|                              |                                       |
|                              v                                       |
|                     +------------------+                             |
|                     |  Azure OpenAI    |                             |
|                     |  (Configurable)  |                             |
|                     +------------------+                             |
|                                                                      |
+---------------------------------------------------------------------+
```

---

## Key Components

### 1. Azure AI Search Knowledge Agent

The Knowledge Agent provides:
- **Query Planning**: LLM-powered decomposition of complex queries
- **Multi-hop Reasoning**: Following chains of information across documents
- **Answer Synthesis**: Comprehensive context with citations
- **Retrieval Modes**: `semantic` (fast) vs `agentic` (intelligent)

### 2. Retrieval Modes

| Mode | Speed | Use Case |
|------|-------|----------|
| `semantic` | ~100-300ms | Simple Q&A, speed-critical apps |
| `agentic` | ~1-3s | Complex questions, multi-hop reasoning |

### 3. Reasoning Effort Levels

- `minimal`: Basic retrieval
- `low`: Light query planning
- `medium`: Full query planning and multi-hop reasoning

---

## Project Structure

The recommended project structure for a Foundry IQ implementation:

```
project-root/
|
+-- .env                           # All configuration (never hardcode!)
|
+-- src/
|   +-- foundry-iq/
|       +-- app/
|       |   +-- __init__.py
|       |   +-- main.py            # FastAPI application & endpoints
|       |   +-- models.py          # Pydantic request/response models
|       |   +-- services.py        # Service layer (all business logic)
|       |
|       +-- requirements.txt       # Python dependencies
|       +-- Dockerfile             # Container configuration
|       +-- docker-compose.yml     # Docker orchestration
|
+-- notebooks/
|   +-- foundry_iq_demo.ipynb      # Interactive demonstration
|
+-- .github/
|   +-- skills/
|       +-- foundry-iq/
|           +-- SKILL.md           # This documentation
|           +-- scripts/           # Reusable building blocks
|               +-- __init__.py
|               +-- search_index_manager.py
|               +-- document_indexer.py
|               +-- knowledge_agent_manager.py
|               +-- azure_openai_client.py
|
+-- research.md                    # Training materials & micro-hack design
```

---

## Environment Variables

All configuration should be externalized to `.env`.
**Keyless auth (DefaultAzureCredential) is the default** — only set API keys if
you cannot use managed identity or `az login`.

> ### ⚠️ Threadlight pilots: keyless is MANDATORY (not optional)
>
> For threadlight processes deployed via `threadlight-deploy`, the keyed
> fallback path **must not ship** in production:
>
> - Provision Azure AI Search with `disableLocalAuth: true`
> - Provision AOAI with `disableLocalAuth: true`
> - Assign UAMI roles per the matrix below — NOT keys, NOT shared admin keys
> - Strip `AZURE_OPENAI_API_KEY` and `AI_SEARCH_KEY` from the deployed `.env` (they're for local dev only)
>
> Required RBAC for foundry-iq runtime (assign to the agent's UAMI):
>
> | Resource | Role | Role ID |
> |----------|------|---------|
> | Azure AI Search service | `Search Index Data Reader` | `1407120a-92aa-4202-b7e9-c0e197c71c8f` |
> | Azure AI Search service | `Search Index Data Contributor` (only for indexer/builder UAMI) | `8ebe5a00-799e-43f5-93ac-243d3dce84a7` |
> | Azure OpenAI account | `Cognitive Services OpenAI User` | `5e0bd9bd-7b93-4f28-af87-19fc36ad61bd` |
> | Foundry project (if using Knowledge Agent) | `Azure AI User` | `53ca6127-db72-4b80-b1b0-d745d6d5456d` |
>
> Plus: `Search Service Contributor` (`7ca78c08-252a-4471-8644-bb5ff32d4ba0`)
> on the Search service for the **deploy-time** identity that creates indexes,
> indexers, and knowledge agents (separate from the runtime UAMI; least
> privilege at runtime).
>
> #### Hosted-agent runtime identity (the gotcha that breaks `corpus_query`)
>
> If the consumer is a **Foundry hosted agent** (`foundry-hosted-agents` /
> `threadlight-deploy` Phase 5), the agent does **NOT** make outbound calls
> under the Foundry **project** managed identity or the AI Services
> **account** managed identity — even if you've granted those `Search
> Index Data Reader`. Granting only those will leave you with a confidently
> wrong "RBAC is set, why am I getting 403?" debug session.
>
> Each hosted-agent **version** has its own identities:
>
> | Identity | Stable across versions? | Granted via | Grant `Search Index Data Reader`? |
> |---|---|---|---|
> | `blueprint.principal_id` | ✅ Yes (stable per agent name) | Bicep post-deploy script (read after first agent create) | **YES** |
> | `instance_identity.principal_id` | ❌ No (changes every `azd deploy agent`) | Postdeploy script that re-reads after each version create | **YES** |
> | Foundry project SystemAssigned MI | ✅ | Bicep `principalId` output | No (not used for outbound tool calls) |
> | AI Services account SystemAssigned MI | ✅ | Bicep `principalId` output | No (not used for outbound tool calls) |
>
> Read the version's identities via:
> ```bash
> az rest --method GET \
>   --url "https://<account>.cognitiveservices.azure.com/api/projects/<project>/agents/<agent-name>/versions/<version>?api-version=2025-11-15-preview" \
>   --resource "https://ai.azure.com" \
>   --query "{blueprint:blueprint.principal_id, instance:instance_identity.principal_id}"
> ```
>
> Then `az role assignment create --assignee-object-id <id> --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope <search-service-id>` for each.
>
> Persist this in IaC as a `postdeploy_grant_agent_search_rbac.py` hook
> wired into `azure.yaml` after `azd deploy agent` — otherwise every new
> agent version regresses the grant for the new `instance_identity`.
>
> **RBAC propagation on AI Search is slow** — up to 5-10 minutes (vs 30-60s
> for most resources). If the first `corpus_query` after a fresh grant
> 403s, wait, don't re-grant.
>
> See `foundry-doc-vision-speech` for the full keyless RBAC matrix across
> all Cognitive Services.

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
# AZURE_OPENAI_API_KEY=            # Optional — omit for keyless auth (REQUIRED to omit for threadlight pilots)
AZURE_OPENAI_API_VERSION=2025-04-01-preview

# Azure AI Search Configuration
AI_SEARCH_ENDPOINT=https://<service>.search.windows.net
# AI_SEARCH_KEY=                    # Optional — omit for keyless auth (REQUIRED to omit for threadlight pilots)
# Pin to match the endpoint surface you use:
#   2025-01-01-preview → /agents/<name>             (legacy; configuration-nested)
#   2025-11-01-preview → /knowledgebases/<name>     (new; flat retrievalReasoningEffort)
AI_SEARCH_API_VERSION=2025-01-01-preview

# PolicyBot Configuration
POLICY_INDEX_NAME=policy-documents
POLICY_AGENT_NAME=policy-agent
POLICY_CHAT_MODEL=gpt-5.4-mini

# Document Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Agentic Retrieval — wire format is camelCase (NOT snake_case)
REASONING_EFFORT=medium       # minimal | low | medium
OUTPUT_MODE=extractiveData    # extractiveData | answerSynthesis

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8001
```

---

## Required Packages

```bash
pip install azure-search-documents>=11.7.0b1
pip install azure-ai-projects
pip install azure-identity
pip install openai
pip install fastapi uvicorn
pip install python-dotenv
pip install requests aiohttp
```

---

## Building Block Scripts

### 1. `search_index_manager.py`
Creates and manages Azure AI Search indexes with vector search configuration.

**Key Class**: `SearchIndexManager`
- Creates indexes with semantic search configuration
- Configures vector search with HNSW algorithm
- Manages index lifecycle (create, list, delete)

### 2. `document_indexer.py`
Indexes documents into Azure AI Search with smart chunking.

**Key Class**: `DocumentIndexer`
- Chunking with configurable size and overlap
- Smart sentence boundary detection
- Batch document upload
- Sample policy documents included

### 3. `knowledge_agent_manager.py`
Creates and manages Knowledge Agents for agentic retrieval.

**Key Classes**:
- `KnowledgeAgentManager`: Creates agents with configurable reasoning effort
- `KnowledgeAgentRetriever`: Performs retrieval with multi-turn history

### 4. `azure_openai_client.py`
Azure OpenAI client for chat completions and embeddings.

**Key Classes**:
- `AzureOpenAIClient`: Low-level chat completions
- `PolicyBot`: High-level Q&A combining retrieval + generation

---

## Agentic Retrieval Deep Dive

### What is Agentic Retrieval?

Traditional RAG follows a simple pattern:
```
Query -> Single Search -> Return Top K Results -> LLM Synthesizes
```

Agentic retrieval treats retrieval as a **reasoning task**:
```
Query -> LLM Plans Sub-queries -> Multiple Searches -> Reflection -> Synthesis
```

### How It Works

1. **Query Analysis**: The Knowledge Agent analyzes the user's question
2. **Query Planning**: Decomposes complex queries into sub-queries
3. **Iterative Search**: Executes sub-queries, following information chains
4. **Result Aggregation**: Combines results from multiple searches
5. **Citation Tracking**: Maintains source references throughout

### Example: Multi-hop Query

**User Question**: "Can I work remotely from another country while using PTO?"

**Traditional RAG** might search once and miss the connection.

**Agentic Retrieval** decomposes:
1. Sub-query 1: "What is the remote work policy for international work?"
2. Sub-query 2: "What are the PTO policy restrictions?"
3. Sub-query 3: "Are there rules about combining remote work with PTO?"

Then synthesizes an answer spanning multiple documents.

### Implementation Location

Agentic retrieval is implemented in `services.py`:

```python
# KnowledgeAgentService.retrieve() - Line 433-455
def retrieve(self, query: str) -> Dict[str, Any]:
    """Perform agentic retrieval."""
    self.messages.append({"role": "user", "content": query})

    request_body = {
        "messages": [
            {"role": msg["role"], "content": [{"text": msg["content"]}]}
            for msg in self.messages if msg["role"] != "system"
        ]
    }

    url = f"{self.endpoint}/agents/{self.agent_name}/retrieve?api-version={self.api_version}"
    response = requests.post(url=url, headers=self.headers, json=request_body)
    # ... response handling
```

### Configuration Options

| Parameter | Values | Description |
|-----------|--------|-------------|
| `reasoningEffort` | minimal, low, medium | Query planning depth |
| `outputMode` | extractive_data, generated_text | How results are returned |

---

## KB access from a hosted MAF agent — three routes

When a hosted MAF agent (`Agent + FoundryChatClient + ResponsesHostServer`)
needs to call a Knowledge Base, you have three transport choices. All
three implement the **same** agentic retrieval semantics (planner +
multi-hop + answer synthesis); only the auth + lifecycle differ.

| Route | What it is | Auth flavor | When to pick |
|---|---|---|---|
| **A. Direct SDK `@tool`** | `KnowledgeBaseRetrievalClient.retrieve()` wrapped in an `@tool` function | `DefaultAzureCredential` native, transparent token refresh | Fewest moving parts; no MCP transport. Pick when you don't need a uniform MCP surface across multiple backends. |
| **B. Direct KB MCP via `httpx.Auth` (CANONICAL DEFAULT)** | `MCPStreamableHTTPTool` against `<search>/knowledgebases/<n>/mcp?api-version=2025-11-01-preview` | AAD bearer (`https://search.azure.com/.default`) injected by an `httpx.AsyncClient(auth=httpx.Auth-subclass)` passed via `http_client=` | Default when you want one MCP surface and per-call AAD refresh. **Do NOT use `header_provider=`** — see Common Errors row on bootstrap 401. |
| **C. Toolbox MCP wrapping the KB** | Foundry Toolbox `mcp` tool with `project_connection_id` pointing at a `RemoteTool` connection of `authType: ProjectManagedIdentity` (audience `https://search.azure.com`) | Toolbox handles transport + token refresh centrally; agent only knows the Toolbox endpoint | Pick when multiple MCP backends need centralized auth / policy / versioning. See `foundry-toolbox` SKILL § "azure_ai_search — INDEX, not Knowledge Base" for connection wiring. |

### Route A — Direct SDK `@tool` (minimal)

```python
import os
from agent_framework import tool
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import KnowledgeBaseRetrievalClient

_credential = DefaultAzureCredential()
_kb_client = KnowledgeBaseRetrievalClient(
    endpoint=os.environ["AI_SEARCH_ENDPOINT"],
    knowledge_base_name=os.environ["KB_NAME"],
    credential=_credential,
    api_version="2025-11-01-preview",
)

@tool(approval_mode="never_require")
async def my_kb_tool(query: str) -> dict:
    """Retrieve a grounded answer with citations from the knowledge base."""
    result = _kb_client.retrieve(query=query)
    return {"answer": result.answer, "references": result.references}
```

### Route B — Direct KB MCP via `httpx.Auth` (CANONICAL DEFAULT)

```python
import os, httpx
from agent_framework import MCPStreamableHTTPTool
from azure.identity import DefaultAzureCredential

_credential = DefaultAzureCredential()

class _KBSearchAuth(httpx.Auth):
    """Mints AAD bearer on EVERY request — covers MCP bootstrap (initialize + tools/list)."""
    def auth_flow(self, request: httpx.Request):
        token = _credential.get_token("https://search.azure.com/.default").token
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

_http = httpx.AsyncClient(auth=_KBSearchAuth(), timeout=120.0)

kb_mcp = MCPStreamableHTTPTool(
    name="my_kb_mcp",
    url=(f"{os.environ['AI_SEARCH_ENDPOINT'].rstrip('/')}"
         f"/knowledgebases/{os.environ['KB_NAME']}/mcp?api-version=2025-11-01-preview"),
    http_client=_http,        # 🔑 auth covers BOOTSTRAP, not just call_tool
    load_prompts=False,       # avoid prompts/list 500s on KB MCP
    request_timeout=120,
)
```

> **Why `httpx.Auth` and NOT `header_provider=`.** MAF's `header_provider`
> only fires inside `call_tool()` (via the `_mcp_call_headers` ContextVar
> set in `agent_framework/_mcp.py` ~line 1589). The MCP bootstrap
> (`initialize` + `tools/list`) runs FIRST during `_ensure_connected`,
> when the ContextVar is still empty → no `Authorization` header → 401 →
> agent registration fails → every Responses request returns
> `server_error` with no useful log signal. `httpx.Auth.auth_flow()` is
> invoked on every outbound request INCLUDING the bootstrap pair,
> sidestepping the trap. See `foundry-hosted-agents` SKILL §
> "MCP with per-call AAD bearer" → ⚠️ Bootstrap caveat.

### Route C — Toolbox MCP wrapping the KB

See `foundry-toolbox` SKILL § "azure_ai_search — INDEX, not Knowledge
Base" for the connection (declarative YAML or ARM REST PUT) and toolbox
shape. Consumed from the agent as a single `MCPStreamableHTTPTool`
against the Toolbox consumer endpoint. **Tool name flattens** to
`<tool_name_prefix>_<tool_name>` — `server_label` is dropped (validated
MAF 1.3.0 + Toolbox v1, May 2026).

---

## API Reference

### Knowledge Agent Retrieval

```python
from azure.search.documents.agent import KnowledgeAgentRetrievalClient
from azure.search.documents.agent.models import (
    KnowledgeAgentRetrievalRequest,
    KnowledgeAgentMessage,
    KnowledgeAgentMessageTextContent,
    SearchIndexKnowledgeSourceParams
)

agent_client = KnowledgeAgentRetrievalClient(
    endpoint=search_endpoint,
    agent_name=knowledge_agent_name,
    credential=credential
)

req = KnowledgeAgentRetrievalRequest(
    messages=[
        KnowledgeAgentMessage(
            role="user",
            content=[KnowledgeAgentMessageTextContent(text=query)]
        )
    ],
    knowledge_source_params=[
        SearchIndexKnowledgeSourceParams(
            knowledge_source_name=index_name,
            kind="searchIndex"
        )
    ]
)

result = agent_client.retrieve(retrieval_request=req)
```

### Direct REST API (Alternative)

```python
# Used in KnowledgeAgentService — keyless with DefaultAzureCredential
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://search.azure.com/.default").token

url = f"{endpoint}/agents/{agent_name}/retrieve?api-version=2025-01-01-preview"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

request_body = {
    "messages": [
        {"role": "user", "content": [{"text": "What is the PTO policy?"}]}
    ]
}

response = requests.post(url, headers=headers, json=request_body)
```

---

## Bootstrap script: hardening checklist

> **The single biggest unforced quality regression in foundry-iq deploys is
> a bootstrap script that *says* it succeeded while leaving the index empty
> or partially populated.** Every item below has been observed in the wild
> at least once. Treat the checklist as mandatory for any
> `bootstrap_foundry_iq.py` you (or a sub-agent) generate.

### 1. Don't shell out to `az rest` for the document upload step

The `az rest --method POST .../docs/index?api-version=...` path tokenizes
against `az login`'s cached credential, which on a deploy host is often
"Reader on the search service" (or worse, the wrong tenant). When it
returns `rc=1: ERROR: Forbidden`, the bootstrap will move on and log
success unless you check rc.

**Do this instead** — direct SDK upload via `azure-search-documents`:

```python
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

client = SearchClient(
    endpoint=os.environ["AI_SEARCH_ENDPOINT"],
    index_name=os.environ["FOUNDRY_IQ_INDEX"],
    credential=DefaultAzureCredential(),
)
results = client.upload_documents(documents=docs)
ok = sum(1 for r in results if r.succeeded)
fail = [(r.key, r.status_code, r.error_message) for r in results if not r.succeeded]
if fail:
    raise RuntimeError(f"Search upload partial: ok={ok} failed={len(fail)} first_fail={fail[0]}")
print(f"Seeded {ok} docs into '{os.environ['FOUNDRY_IQ_INDEX']}'")
```

### 2. Fail-fast on every shell-out

If you *must* shell out to `az rest` (e.g., for the `/agents/<name>` PUT
when creating a Knowledge Agent — there's no first-party SDK path for
that yet), check rc explicitly and **never** log success unconditionally:

```python
proc = subprocess.run(["az", "rest", "--method", "PUT", ...], capture_output=True, text=True)
if proc.returncode != 0:
    raise RuntimeError(f"az rest failed rc={proc.returncode}: {proc.stderr[:500]}")
print("Knowledge Agent created")
```

The unconditional-success log pattern that caused the silent-empty-index
incident:

```python
# ANTI-PATTERN — DO NOT DO THIS
sh(["az", "rest", "--method", "POST", ...], check=False)
print("[seeded 19 docs]")  # <-- ALWAYS prints, even on rc=1
```

### 3. Sanitize document keys to AI Search's allowed character set

AI Search keys MUST match `[A-Za-z0-9_\-=]`. A naive
`f.stem.replace(" ", "_").replace(".", "_")` leaves parentheses, brackets,
quotes, accented chars, and unicode through — they all return
`InvalidDocumentKey` 400 at upload time, which on a multi-doc upload
shows up as a 207 multi-status that's easy to miss.

```python
import re

def sanitize_key(name: str) -> str:
    """AI Search keys allow only [A-Za-z0-9_\-=]. Replace anything else with _ and trim."""
    s = re.sub(r"[^A-Za-z0-9_\-=]", "_", name)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:128] or "doc"
```

### 4. Chunk content to dodge the 32766-byte term limit

AI Search rejects any single token > 32766 bytes (UTF-8). `text[:60000]`
truncation does NOT fix this — it only caps the field length. If a
source doc has one long unbroken token (a URL, a base64 blob, a long
table row with no whitespace), upload fails with:

> Field 'content' contains a term that is too large to process. The max length for UTF-8 encoded terms is 32766 bytes.

Chunk before upload, splitting at paragraph / line / whitespace
boundaries with a hard-cap fallback:

```python
def chunk_content(text: str, max_chars: int = 25000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, pos = [], 0
    while pos < len(text):
        end = min(pos + max_chars, len(text))
        if end < len(text):
            cut = text.rfind("\n\n", pos, end)
            if cut == -1: cut = text.rfind("\n", pos, end)
            if cut == -1: cut = text.rfind(" ", pos, end)
            if cut == -1 or cut <= pos: cut = end
            else: cut = cut + 1
        else:
            cut = end
        chunks.append(text[pos:cut])
        pos = cut
    return chunks

# Then for each source doc, emit one record per chunk:
for i, chunk in enumerate(chunks):
    docs.append({
        "id": f"{base_id}_p{i}" if len(chunks) > 1 else base_id,
        "title": f"{name} (part {i+1}/{len(chunks)})" if len(chunks) > 1 else name,
        "content": chunk,
        ...
    })
```

### 5. Wait for AI Search RBAC propagation before the first upload

Most Azure resources propagate role assignments in 30-60s. **AI Search
propagates in 5-10 minutes.** A bootstrap that grants `Search Index Data
Contributor` and immediately uploads will 403 even though `az role
assignment list` shows the grant exists.

Add an explicit wait + probe loop:

```python
import time
def wait_for_search_rbac(client, max_wait_s=600):
    start = time.time()
    while time.time() - start < max_wait_s:
        try:
            client.get_document_count()
            return
        except Exception as e:
            if "403" not in str(e) and "Forbidden" not in str(e):
                raise
            print(f"[wait] RBAC not yet propagated ({int(time.time()-start)}s)...")
            time.sleep(30)
    raise RuntimeError(f"RBAC never propagated after {max_wait_s}s")
```

### 6. Verify after upload — never trust the upload log alone

After upload, fetch `/docs/$count` and assert it matches expected:

```python
expected = len(docs)
actual = client.get_document_count()
if actual < expected:
    raise RuntimeError(f"Index has {actual} docs, expected {expected}. Check upload errors above.")
print(f"Verified {actual} docs in index '{index_name}'")
```

This is the cheapest insurance against "deploy looks green, agent
silently returns no results" — one HTTP call.

### 7. Recovery: a one-shot manual seed script

When bootstrap leaves you with an empty/partial index in a deployed
environment, ship a `manual_seed.py` next to the bootstrap that you can
re-run interactively without re-provisioning. It should be idempotent
(uses `MergeOrUpload` semantics, not `Upload`) so you can re-run after
each fix without `az search index data delete` cycles.

### 8. Content-gated bootstrap (don't re-ingest on routine `azd provision`)

Postprovision MUST NOT rebuild the KB just because someone tweaked a
network rule or bumped a SKU. Re-ingesting wipes the KB temporarily
AND burns LLM tokens on per-source vision/extraction calls — both
unacceptable for an unrelated infra change. Three-mode gate:

```python
# infra/scripts/postprovision.py (excerpt)
import os, subprocess, sys
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

def kb_doc_count() -> int:
    sc = SearchClient(
        endpoint=os.environ["AI_SEARCH_ENDPOINT"],
        index_name=os.environ["FOUNDRY_IQ_INDEX"],
        credential=DefaultAzureCredential(),
    )
    return sc.get_document_count()

force = os.getenv("PILOT_REINGEST_KB", "").lower() in ("1", "true", "yes")
count = kb_doc_count()

if count == 0 or force:
    reason = "empty KB" if count == 0 else "PILOT_REINGEST_KB set"
    print(f"[ingest] {reason} -> running refresh_kb.py")
    subprocess.run([sys.executable, "refresh_kb.py"], check=True)
else:
    print(f"[skip] KB has {count} docs; set PILOT_REINGEST_KB=1 to force refresh")
```

Pair with a `--no-seed` flag on your `bootstrap_foundry_iq.py` so the
index + Knowledge Agent / Knowledge Base are still created and
idempotently ensured every postprovision, but the legacy text seed
never overwrites the real ingest output.

The operator-facing manual override is `PILOT_REINGEST_KB=1 python
postprovision.py`, or wrap it as a tiny `refresh_kb.py` (~40 lines)
that always runs the ingest chain unconditionally for hand-driven
content refreshes.

### 9. Visual chunks with `page_ref` and `visual_kind`

When the corpus contains diagrams, flowcharts, or visual customer
comms, extract them at INGEST time (see `foundry-doc-vision-speech`
SKILL § Pattern X) and land the structured text as additional KB
chunks alongside text chunks — same index, same retrieval path, **no
runtime vision tool**. The chunk schema needs four extra fields:

```jsonl
{
  "id": "vis_blueprint_p06",
  "source_file": "journey-blueprint-v1.3.pdf",
  "source_type": "journey",
  "page_ref": "page:6",
  "visual_kind": "flowchart",
  "content_sha256": "abc123...",
  "content": "PAGE SUMMARY\n...\nDIAGRAM STRUCTURE\n[START] ...\n[STEP] ...\n[DECIDE] ...",
  "title": "Assisted journey — vulnerability branch (p.6)"
}
```

`page_ref` flows into the cited answer as `[..., page 6]`; `visual_kind`
helps the planner bias retrieval; `content_sha256` enables byte-identical
duplicate detection across source files (real-world export bugs produce
duplicate documents with different IDs but identical bodies — flag
those for the customer's content-management team).

### 10. `BOLD_PARA_RE` heading lift for mammoth-converted DOCX

`mammoth.convert_to_html(...)` (or any pure-DOCX-to-Markdown path)
emits section titles as `**Bold paragraph**\n\n`, NOT `## Heading\n`.
A heading-aware chunker therefore puts the entire 24KB doc in ONE
"Introduction" chunk before paragraph fallback fires, and ALL chunks
inherit the same vague title. Pre-process bold-then-blank patterns to
`##` BEFORE chunking:

```python
import re

BOLD_PARA_RE = re.compile(r"^\*\*([^*\n]{3,120})\*\*\s*$", re.MULTILINE)

def lift_bold_to_h2(md: str) -> str:
    """Promote standalone **Bold** paragraphs to ## H2 so the chunker splits properly."""
    return BOLD_PARA_RE.sub(r"## \1", md)
```

Validated on a 19-document corpus: ~140 bold paragraphs lifted; one
24KB article went from 1 "Introduction" chunk → 30 properly-titled
chunks; end-to-end retrieval precision on title-grounded queries jumped
from ~30% to ~80%+ on the same eval dataset.

### 11. Per-source manifest for cheap-skip-if-unchanged

Long-running ingest pipelines (vision extraction, Document Intelligence
calls, embedding) should consult a per-source manifest BEFORE re-extracting.
Schema:

```json
{
  "<source_path>": {
    "sha256": "<content hash>",
    "mtime": 1715600000.0,
    "size": 569123,
    "chunks": 12,
    "extracted_at": "2026-05-13T14:22:01Z"
  }
}
```

Atomic write (`tmp + os.replace`) so a crash mid-rewrite doesn't leave
a partial file. Cheap-skip at the top of the per-source loop:

```python
def source_unchanged(path, manifest):
    cur_mtime = path.stat().st_mtime
    cur_size = path.stat().st_size
    entry = manifest.get(str(path))
    if not entry or entry["mtime"] != cur_mtime or entry["size"] != cur_size:
        return False
    # mtime+size match — only THEN compute sha256 to confirm content equality
    return entry["sha256"] == _sha256_file(path)
```

Skip-rewrites-prior-chunks: when source IS unchanged, leave the prior
JSONL chunks for that source intact in the merged ingest output (don't
re-emit). When source HAS changed, re-extract AND remove all prior
chunks keyed to that source BEFORE appending the new ones.

Cross-link: see `foundry-doc-vision-speech` SKILL § Pattern X for the
matching extraction pipeline that this manifest skips against.

---

## Sample Use Cases

### PolicyBot - Enterprise Policy Assistant
Answer questions about HR policies, PTO, expenses, etc. with citations.

```python
query = "What's the approval process for expenses over $5000?"
# Returns: Cited answer from policy documents with source annotations
```

### Multi-hop Reasoning
```python
query = "Can I work remotely from another country while using PTO?"
# Agent decomposes into:
# 1. What is the remote work policy?
# 2. What is the PTO policy?
# 3. Are there restrictions on combining them?
```

---

## Citations Format

Responses include annotations in the format:
```
[message_idx:search_idx+source_name]
```

Example: "Employees receive 15 PTO days [0:1+pto_policy.md]"

---

## Lessons Learned

### 1. Configuration Management
- **Always externalize config** to environment variables
- Never hardcode model names, API versions, or endpoints
- Use sensible defaults with env var overrides

### 2. Chunking Strategy
- **1000 characters with 200 overlap** works well for policy documents
- Smart sentence boundary detection prevents mid-sentence splits
- Overlap ensures context continuity across chunks

### 3. Reasoning Effort Selection
- Use `minimal` for simple factual queries
- Use `medium` for complex multi-hop questions
- Higher effort = more tokens = more cost + latency

### 4. Error Handling
- Knowledge Agents may not exist on first run - handle gracefully
- Index creation is idempotent - "already exists" is OK
- API version mismatches are common - use preview versions for new features

### 5. Service Architecture
- Separate concerns: Index management, Document indexing, Agent retrieval, LLM generation
- Use service classes for testability and reusability
- Keep FastAPI endpoints thin - delegate to services

### 6. Multi-turn Conversations
- Track message history for context continuity
- Allow conversation reset for fresh starts
- Store conversations in-memory or external cache

---

## Best Practices

1. **Use appropriate retrieval mode**: `semantic` for simple queries, `agentic` for complex
2. **Set reasoning effort based on query complexity**: `medium` for multi-hop
3. **Include clear agent instructions** for citation format
4. **Handle gracefully when KB lacks relevant content**
5. **Log all configuration at startup** for debugging
6. **Use health checks** to verify all services are operational

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| API Version mismatch | Using old version | Pin `AI_SEARCH_API_VERSION=2025-01-01-preview` for legacy `/agents/` endpoint OR `2025-11-01-preview` for the new `/knowledgebases/` endpoint. The two are NOT interchangeable — see Knowledge Bases migration callout above. |
| Missing index | Index not created | Run `/setup` endpoint first |
| Authentication failed | 401 / 403 from Search or AOAI | Threadlight pilots are **keyless-by-mandate** — verify the agent's UAMI has the required Entra roles (Search Index Data Reader, Cognitive Services OpenAI User, Azure AI User on the Foundry project) AND that `AZURE_CLIENT_ID` is exported into the container so DefaultAzureCredential picks the UAMI (not the dev-loop user). Do NOT bypass by setting `AI_SEARCH_KEY` or `AZURE_OPENAI_API_KEY`. |
| 403 from `corpus_query` after RBAC grant on Foundry hosted agent | Granted only to project / account MI; hosted-agent runtime uses `blueprint.principal_id` + `instance_identity.principal_id` instead | Grant `Search Index Data Reader` to BOTH MIs (see Hosted-agent runtime identity callout in § Environment Variables). Wait 5-10 min for AI Search RBAC propagation. |
| `'search.in' invalid expression` from corpus filter | Wrong OData syntax — separate quoted args instead of single CSV string | Use `search.in(field, 'a,b,c', ',')` — single quoted CSV string + delimiter, NOT `search.in(field, 'a','b','c')`. Common copy-paste error. |
| `KnowledgeAgent` PUT returns 500 (`Internal Server Error`) | Tenant not yet migrated to Knowledge Bases AND legacy Knowledge Agents path is preview-fluid | Bypass the Knowledge Agent surface entirely — use plain `SearchClient.search(query_type="semantic", semantic_configuration_name=...)`. You lose multi-hop query planning but get GA-stable retrieval. Migrate to `/knowledgebases/<name>` (api-version `2025-11-01-preview`) when the tenant supports it. |
| Index doc count = 0 after "successful" bootstrap | Bootstrap script silently swallowed an `az rest` error (rc != 0 then `[seeded N]` logged unconditionally) | See § Bootstrap script: hardening checklist. Replace `az rest` with direct `SearchClient.upload_documents(...)`, fail-fast on rc != 0, and inspect per-doc result.succeeded. |
| `InvalidDocumentKey` 400 on upload | Document key contains illegal chars (parens, brackets, dots, spaces) | Sanitize keys: `re.sub(r"[^A-Za-z0-9_\-=]", "_", name)` then collapse runs of `_` and trim to 128 chars. AI Search only accepts `[A-Za-z0-9_\-=]`. |
| `Field 'content' contains a term that is too large to process. The max length for UTF-8 encoded terms is 32766 bytes.` | Source doc has a long unbroken token (URL, base64 blob, no whitespace) > 32k bytes | Chunk content > ~25k chars at paragraph / sentence / whitespace boundaries with a hard-cap fallback. Don't rely on `[:60000]` truncation — that doesn't fix the term length, only the field length. |
| Hosted MAF agent returns `server_error` after wiring `MCPStreamableHTTPTool` against `/knowledgebases/<n>/mcp` | Suspected: MAF's `MCPStreamableHTTPTool._ensure_connected()` issues an MCP `ping` request during agent registration. The Foundry Toolbox MCP endpoint is documented to return HTTP 500 on `ping`; the same failure mode is **suspected but not yet confirmed upstream** for direct KB MCP wiring. Either way, the agent fails to register and every invoke returns `server_error` from the responses endpoint with no useful log signal | Either (a) override `MCPStreamableHTTPTool._ensure_connected` with a no-op subclass to skip the ping, OR (b) wrap the KB MCP behind a Foundry Toolbox MCP tool with `project_connection_id` so the Toolbox handles transport. See `foundry-hosted-agents` SKILL § "MCP `ping` trap on Foundry-hosted MCP servers". |
| `401` from KB MCP endpoint on hosted MAF agent (despite agent identity having `Search Index Data Reader`) | `MCPStreamableHTTPTool(header_provider=...)` does NOT cover the MCP bootstrap exchange. The `_mcp_call_headers` ContextVar is only set inside `call_tool()` (`agent_framework/_mcp.py` ~line 1589); `_ensure_connected` runs `initialize` + `tools/list` BEFORE the first `call_tool`, with the ContextVar still empty → no `Authorization` header → 401 → agent boot fails. The `server_error` surfaced to the responses endpoint has no useful log signal. | **Use `httpx.AsyncClient(auth=httpx.Auth)` via `http_client=`** instead of `header_provider=`. The `auth.auth_flow()` method runs on EVERY outbound request including bootstrap. See `foundry-hosted-agents` SKILL § "MCP with per-call AAD bearer (`header_provider`)" → ⚠️ Bootstrap caveat for the worked `httpx.Auth` example, and § KB access from a hosted MAF agent → Route B above. |
| `references[].source_data` is `null` on KB MCP / SDK responses | Default `KnowledgeSource` definition omits `includeReferenceSourceData: true`; the KB returns reference IDs only — no title / version / effective_date / source_type metadata for programmatic citation rendering | When provisioning the searchIndex `KnowledgeSource`, set `"includeReferenceSourceData": true` in the body (`PUT {search}/knowledgesources/<n>?api-version=2025-11-01-preview`). Citations EMBEDDED in the synthesized answer (`[<source_label>]` markers) still render without this — only structured `references[i].source_data` field access requires it. |
| `client.get_mcp_tool()` accepts only static `headers: dict[str, str]` — no `header_provider` | The hosted-MCP shape is designed for static API keys / unauthenticated MCPs; the static dict is pinned at agent build time | For MCP servers that need short-lived AAD tokens (e.g. KB MCP, Storage MCP behind PMI), do NOT use `client.get_mcp_tool()` — switch to `MCPStreamableHTTPTool + header_provider`. Static `Bearer` tokens in the dict will expire after ~1h and break the agent until container restart. Bug-009/014 itself is FIXED in `agent-framework-core` 1.3.0 ([PR #5581](https://github.com/microsoft/agent-framework/pull/5581)) — the static-headers limitation is a separate design constraint. |
| Foundry Toolbox `azure_ai_search` tool type wraps an INDEX, not a Knowledge Base | The built-in Toolbox tool only exposes `index_name` + `query_type=vector_semantic_hybrid` — no agentic query planning or answer synthesis | If you need KB planning + synthesis from a Toolbox, use the `mcp` tool type (not `azure_ai_search`) with `server_url=<search>/knowledgebases/<n>/mcp?api-version=2025-11-01-preview` + a `project_connection_id` that authenticates with PMI to `https://search.azure.com`. The trade-off: extra hop, inherits the `ping` trap, but Toolbox handles token refresh centrally. |
| No results | Empty index | Index sample documents first |
| Timeout | Large retrieval | Reduce reasoning effort or chunk size |

### Debug Checklist

1. Check environment variables are loaded
2. Verify Azure services are accessible (health endpoint)
3. Confirm index exists and has documents
4. Test simple queries before complex ones
5. Check API response codes and error messages

---

## Extension Ideas

1. **Add SharePoint source**: Connect document libraries as knowledge sources
2. **Skill-based orchestration**: Wrap the Knowledge Agent retrieval in a dedicated `src/agent/skills/<knowledge-skill>/SKILL.md` so the threadlight agent (single-agent, skill-based pattern) can call it as a tool — this is the orchestration model `threadlight-design` uses, NOT a separate retrieval agent
3. **Streaming responses**: Real-time token streaming with Gradio UI
4. **Custom functions**: Email escalation, ticket creation, etc.
5. **Caching layer**: Redis for conversation history and frequent queries
6. **Observability**: OpenTelemetry tracing for request flow visibility

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Generates SPEC.md § 7 Knowledge Sources — the input contract for this skill |
| [**threadlight-deploy**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy/) | Phase 6 (Module Composer) wires `foundry-iq-index.bicep` when SPEC § 7 declares `Backing service: foundry-iq` |
| [**azd-patterns**](../azd-patterns/) | Owns the `foundry-iq-index.bicep` module shape |
| [**foundry-doc-vision-speech**](../foundry-doc-vision-speech/) | Pairs with this skill: extract structured text from raw docs (foundry-doc-vision-speech) → index it for retrieval (foundry-iq) |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Alternative knowledge backing (`mcp-search`) when foundry-iq is genuinely overkill — prefer foundry-iq by default |
| [**foundry-evals**](../foundry-evals/) | Evaluates retrieval precision, citation accuracy, multi-hop reasoning quality |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | The hosted agent that calls this Knowledge Agent as a tool |

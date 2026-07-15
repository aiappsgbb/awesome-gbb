---
name: foundry-iq
description: >
  Build enterprise RAG with Foundry IQ and Azure AI Search Knowledge Bases using
  agentic retrieval, multi-hop reasoning, query planning, and citation-backed
  responses. Distinguishes the stable 2026-04-01 programmatic API from preview
  portal experiences and preview-only knowledge-source integrations.
  USE FOR: knowledge base, RAG, agentic retrieval, policy assistant, citations,
  multi-hop QA, Knowledge Agent, AI Search Knowledge Base, document grounding,
  semantic retrieval, foundry-iq, knowledge index, hybrid search, vector search,
  kb-mcp, web iq boundary, serverless knowledge base boundary, purview acl knowledge.
  DO NOT USE FOR: structured-document extraction (use foundry-doc-vision-speech),
  standalone Work IQ, Fabric IQ, or Web IQ workloads, MCP server deployment (use
  foundry-mcp-aca), agent runtime (use foundry-hosted-agents).
metadata:
  version: "1.4.0"
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
| `test-fixture/consumer_prompt.md` | Live smoke | Creates and reads a GA `searchIndex` knowledge source on REST `2026-04-01` |
| `test-fixture/azure.yaml` + `infra/` | CI infrastructure | azd+Bicep source for the standing keyless Azure AI Search service |

---

## Overview

Foundry IQ is Microsoft's enterprise-grade RAG solution that treats retrieval as a reasoning task. It uses Azure AI Search Knowledge Bases with agentic retrieval to enable multi-hop reasoning, query planning, and citation-backed responses.

> ### Agentic retrieval API surface map (July 2026)
>
> Three data-plane surfaces exist side by side. They are **not
> interchangeable**:
>
> | Surface | API version | Status | Endpoint shape |
> |---------|-------------|--------|----------------|
> | Legacy Knowledge Agents used by this skill's scripts | `2025-01-01-preview` | Preview | `/agents/<name>` |
> | Knowledge sources and Knowledge Bases | `2026-04-01` | Narrow GA programmatic slice | `/knowledgesources('<name>')`, `/knowledgebases('<name>')` |
> | Expanded knowledge-source kinds and options | `2026-05-01-preview` | Preview | Same resource families with preview-only wire values |
>
> The scripts in this skill are pinned to the legacy `/agents/` surface
> for compatibility only. New production code should use the `2026-04-01`
> Knowledge Source and Knowledge Base REST resources directly and should
> opt into `2026-05-01-preview` only when it needs a capability explicitly
> marked preview in the matrix below. Do not migrate by changing only the
> API-version string; endpoint paths and wire shapes also differ.

---

## Foundry IQ availability: GA vs preview

Foundry IQ has a narrow GA programmatic slice on the stable Azure AI
Search REST API `2026-04-01`. The Azure portal and Microsoft Foundry
portal access to all agentic retrieval features remains preview. The
latest `2026-05-01-preview` API adds source kinds and options that are
not covered by the GA service contract.

<!-- GA_KNOWLEDGE_SOURCE_MATRIX_START -->
| Wire kind | Status on `2026-04-01` | Knowledge source | Indexed or remote |
|-----------|-------------------------|------------------|-------------------|
| `searchIndex` | GA | [Existing Azure AI Search index](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index) | Indexed |
| `azureBlob` | GA | [Azure Blob Storage or ADLS Gen2](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob) | Indexed |
| `indexedOneLake` | GA | [OneLake](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-onelake) | Indexed |
| `web` | GA | [Bing-grounded public web](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-web) | Remote |
| `indexedSql` | Preview | [Azure SQL](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-azure-sql) | Indexed |
| `file` | Preview | [Direct file upload](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file) | Indexed |
| `indexedSharePoint` | Preview | [Indexed SharePoint](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-sharepoint-indexed) | Indexed |
| `remoteSharePoint` | Preview | [Remote SharePoint](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-sharepoint-remote) | Remote |
| `fabricDataAgent` | Preview | [Fabric Data Agent](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-data-agent) | Remote |
| `fabricOntology` | Preview | [Fabric Ontology](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology) | Remote |
| `mcpServer` | Preview | [External MCP server](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server) | Remote |
| `workIQ` | Preview | [Work IQ](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-work-iq) | Remote |
<!-- GA_KNOWLEDGE_SOURCE_MATRIX_END -->

The GA `web` kind is Bing-backed web grounding. It is not the separate
Web IQ capability, and `mcpServer` is not GA. Foundry IQ, Work IQ, Fabric IQ, and Web IQ are standalone Microsoft IQ capabilities that can be
combined; they are not one merged GA layer. Work IQ and Fabric IQ integrations
into Foundry remain preview.

Use [the migration guide](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate)
before moving code between stable and preview versions. Use the
[`2026-04-01` create-or-update reference](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01)
for the stable wire contract.

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

### 4. Knowledge Sources

For production code on stable `2026-04-01`, choose exactly one or more
of `searchIndex`, `azureBlob`, `indexedOneLake`, and `web`. The first
three use indexed content; `web` queries Bing at retrieval time.

All other kinds in the availability matrix require
`2026-05-01-preview`. In particular, direct `file` upload and external
`mcpServer` connections are preview-only. Never describe those kinds as
GA or treat the GA `web` wire value as Web IQ.

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
>
> **Purview ACL passthrough (2026-05-01-preview).** Knowledge Bases
> now honor **document-level Purview sensitivity labels** at query
> time. When the KB ingests Files (or queries a Search index whose
> documents carry Purview labels), each retrieved chunk is filtered
> against the **calling user's** Purview permissions before the
> agent ever sees it — meaning two users running the same query
> against the same KB get different citations based on what they're
> cleared to read. The filter is enforced server-side; no code
> change in the agent. Requires Purview to be configured on the
> source documents AND the caller's identity to flow through
> (works out-of-the-box with hosted agents using user-on-behalf
> tokens; for agent-as-service identity, the agent's MI permissions
> are evaluated instead — beware of over-privileged agent identities
> defeating the filter).

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
#   2026-04-01         → GA /knowledgesources + /knowledgebases programmatic slice
#   2026-05-01-preview → expanded preview kinds and options
AI_SEARCH_API_VERSION=2025-01-01-preview
AI_SEARCH_KNOWLEDGE_SOURCE_API_VERSION=2026-04-01

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
pip install "azure-search-documents~=12.0.0"
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
needs to call a Knowledge Base, you have three transport choices. Routes A
and B can use stable `2026-04-01`. The stable KB MCP endpoint returns
minimal, extractive grounding data; synthesized answers and configurable
reasoning require `2026-05-01-preview`. This KB-as-MCP endpoint is distinct
from the preview-only `mcpServer` knowledge-source kind. Foundry Agent Service integration uses `2026-05-01-preview`; don't infer its preview
integration status from the generic Azure AI Search MCP endpoint.

| Route | What it is | Auth flavor | When to pick |
|---|---|---|---|
| **A. Direct SDK `@tool` (GA default)** | `KnowledgeBaseRetrievalClient.retrieve()` wrapped in an `@tool` function on `2026-04-01` | `DefaultAzureCredential` native, transparent token refresh | Production default. Fewest moving parts and no preview MCP transport. |
| **B. Direct KB MCP via `httpx.Auth` (GA extractive)** | `MCPStreamableHTTPTool` against `<search>/knowledgebases/<n>/mcp?api-version=2026-04-01` | AAD bearer (`https://search.azure.com/.default`) injected by an `httpx.AsyncClient(auth=httpx.Auth-subclass)` passed via `http_client=` | Use for a uniform MCP surface with stable minimal/extractive retrieval. **Do NOT use `header_provider=`** — see Common Errors row on bootstrap 401. |
| **C. Toolbox MCP wrapping the KB (preview)** | Foundry Toolbox `mcp` tool with `project_connection_id` pointing at a `RemoteTool` connection of `authType: ProjectManagedIdentity` (audience `https://search.azure.com`) and a `2026-05-01-preview` KB endpoint | Toolbox handles transport + token refresh centrally; agent only knows the Toolbox endpoint | Use only when the Foundry Agent Service preview integration is acceptable. |

### Route A — Direct SDK `@tool` (minimal)

```python
import os
from agent_framework import tool
from azure.identity import DefaultAzureCredential
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalSemanticIntent,
)

_credential = DefaultAzureCredential()
_kb_client = KnowledgeBaseRetrievalClient(
    endpoint=os.environ["AI_SEARCH_ENDPOINT"],
    knowledge_base_name=os.environ["KB_NAME"],
    credential=_credential,
    api_version="2026-04-01",
)

@tool(approval_mode="never_require")
def my_kb_tool(query: str) -> dict:
    """Retrieve a grounded answer with citations from the knowledge base."""
    request = KnowledgeBaseRetrievalRequest(
        intents=[KnowledgeRetrievalSemanticIntent(search=query)]
    )
    result = _kb_client.retrieve(request)
    return {
        "response": result.response,
        "activity": result.activity,
        "references": result.references,
    }
```

### Route B — Direct KB MCP via `httpx.Auth`

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
         f"/knowledgebases/{os.environ['KB_NAME']}/mcp?api-version=2026-04-01"),
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
| API Version mismatch | Mixing stable, expanded-preview, and legacy wire contracts | Use `AI_SEARCH_KNOWLEDGE_SOURCE_API_VERSION=2026-04-01` for the GA programmatic slice, `2026-05-01-preview` only for preview-only kinds/options, or `AI_SEARCH_API_VERSION=2025-01-01-preview` for this skill's legacy `/agents/` scripts. Do not change only the version string; endpoint paths and payloads differ. |
| Missing index | Index not created | Run `/setup` endpoint first |
| Authentication failed | 401 / 403 from Search or AOAI | Threadlight pilots are **keyless-by-mandate** — verify the agent's UAMI has the required Entra roles (Search Index Data Reader, Cognitive Services OpenAI User, Azure AI User on the Foundry project) AND that `AZURE_CLIENT_ID` is exported into the container so DefaultAzureCredential picks the UAMI (not the dev-loop user). Do NOT bypass by setting `AI_SEARCH_KEY` or `AZURE_OPENAI_API_KEY`. |
| 403 from `corpus_query` after RBAC grant on Foundry hosted agent | Granted only to project / account MI; hosted-agent runtime uses `blueprint.principal_id` + `instance_identity.principal_id` instead | Grant `Search Index Data Reader` to BOTH MIs (see Hosted-agent runtime identity callout in § Environment Variables). Wait 5-10 min for AI Search RBAC propagation. |
| `'search.in' invalid expression` from corpus filter | Wrong OData syntax — separate quoted args instead of single CSV string | Use `search.in(field, 'a,b,c', ',')` — single quoted CSV string + delimiter, NOT `search.in(field, 'a','b','c')`. Common copy-paste error. |
| `KnowledgeAgent` PUT returns 500 (`Internal Server Error`) | Legacy Knowledge Agents path is preview-fluid | Use the stable `/knowledgebases('<name>')` surface on `2026-04-01`, or plain `SearchClient.search(query_type="semantic", semantic_configuration_name=...)` when you don't need agentic planning. |
| Index doc count = 0 after "successful" bootstrap | Bootstrap script silently swallowed an `az rest` error (rc != 0 then `[seeded N]` logged unconditionally) | See § Bootstrap script: hardening checklist. Replace `az rest` with direct `SearchClient.upload_documents(...)`, fail-fast on rc != 0, and inspect per-doc result.succeeded. |
| `InvalidDocumentKey` 400 on upload | Document key contains illegal chars (parens, brackets, dots, spaces) | Sanitize keys: `re.sub(r"[^A-Za-z0-9_\-=]", "_", name)` then collapse runs of `_` and trim to 128 chars. AI Search only accepts `[A-Za-z0-9_\-=]`. |
| `Field 'content' contains a term that is too large to process. The max length for UTF-8 encoded terms is 32766 bytes.` | Source doc has a long unbroken token (URL, base64 blob, no whitespace) > 32k bytes | Chunk content > ~25k chars at paragraph / sentence / whitespace boundaries with a hard-cap fallback. Don't rely on `[:60000]` truncation — that doesn't fix the term length, only the field length. |
| Hosted MAF agent returns `server_error` after wiring `MCPStreamableHTTPTool` against `/knowledgebases/<n>/mcp` | **Confirmed (May 2026):** MAF's `MCPStreamableHTTPTool._ensure_connected()` issues an MCP `ping` request during agent registration. KB MCP returns HTTP 500 on `ping`. The agent fails to register and every invoke returns `server_error` with no useful log signal. On MAF 1.6.0, overriding `_ensure_connected` with a `self._client` reference causes `AttributeError` (attribute renamed to `self.client`) — container starts, readiness passes, but every request returns empty `output: []` / `model: ""` | **Recommended (MAF 1.6.0+):** subclass with `_ping_available = False` in `__init__` — MAF's base respects this flag natively: `class _PingSkipMCPTool(MCPStreamableHTTPTool): def __init__(self, **kwargs): super().__init__(**kwargs); self._ping_available = False`. This is cleaner than overriding `_ensure_connected` and survives internal attribute renames. See `foundry-hosted-agents` SKILL § "MCP `ping` trap". |
| `401` from KB MCP endpoint on hosted MAF agent (despite agent identity having `Search Index Data Reader`) | `MCPStreamableHTTPTool(header_provider=...)` does NOT cover the MCP bootstrap exchange. The `_mcp_call_headers` ContextVar is only set inside `call_tool()` (`agent_framework/_mcp.py` ~line 1589); `_ensure_connected` runs `initialize` + `tools/list` BEFORE the first `call_tool`, with the ContextVar still empty → no `Authorization` header → 401 → agent boot fails. The `server_error` surfaced to the responses endpoint has no useful log signal. | **Use `httpx.AsyncClient(auth=httpx.Auth)` via `http_client=`** instead of `header_provider=`. The `auth.auth_flow()` method runs on EVERY outbound request including bootstrap. See `foundry-hosted-agents` SKILL § "MCP with per-call AAD bearer (`header_provider`)" → ⚠️ Bootstrap caveat for the worked `httpx.Auth` example, and § KB access from a hosted MAF agent → Route B above. |
| `references[].source_data` is `null` on KB MCP / SDK responses | Default `KnowledgeSource` definition omits `includeReferenceSourceData: true`; the KB returns reference IDs only — no title / version / effective_date / source_type metadata for programmatic citation rendering | This option is preview-only. On `2026-05-01-preview`, set `"includeReferenceSourceData": true` when provisioning the `searchIndex` knowledge source. Do not add the property to a stable `2026-04-01` request unless the stable reference documents it. |
| `client.get_mcp_tool()` accepts only static `headers: dict[str, str]` — no `header_provider` | The hosted-MCP shape is designed for static API keys / unauthenticated MCPs; the static dict is pinned at agent build time | For MCP servers that need short-lived AAD tokens (e.g. KB MCP, Storage MCP behind PMI), do NOT use `client.get_mcp_tool()` — switch to `MCPStreamableHTTPTool + header_provider`. Static `Bearer` tokens in the dict will expire after ~1h and break the agent until container restart. Bug-009/014 itself is FIXED in `agent-framework-core` 1.3.0 ([PR #5581](https://github.com/microsoft/agent-framework/pull/5581)) — the static-headers limitation is a separate design constraint. |
| Foundry Toolbox `azure_ai_search` tool type wraps an INDEX, not a Knowledge Base | The built-in Toolbox tool only exposes `index_name` + `query_type=vector_semantic_hybrid` — no agentic query planning or answer synthesis | The Foundry Agent Service / Toolbox MCP integration is preview. Use `server_url=<search>/knowledgebases/<n>/mcp?api-version=2026-05-01-preview` with a project connection only when preview terms are acceptable; otherwise call stable Route A directly. |
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

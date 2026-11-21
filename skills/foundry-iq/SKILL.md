---
name: foundry-iq
description: >
  Build enterprise RAG with Foundry IQ (Azure AI Search) knowledge sources and
  knowledge bases: agentic retrieval with minimal, low or medium reasoning effort
  on GA REST 2026-10-01, citations, the KB MCP endpoint (2026-11-01-preview),
  Foundry Agent Service wiring (RemoteTool connection, ProjectManagedIdentity,
  knowledge_base_retrieve), knowledgeRetrieval billing and query-time permission
  trimming. Separates GA, preview and legacy 2025-05 agents.
  USE FOR: knowledge base, RAG, agentic retrieval, policy assistant, citations,
  multi-hop QA, AI Search Knowledge Base, document grounding, foundry-iq, kb-mcp,
  knowledge_base_retrieve, reasoning effort, Microsoft Retriever 1, permission
  trimming, x-ms-query-source-authorization, knowledgeRetrieval 402, hybrid
  search, web iq boundary.
  DO NOT USE FOR: structured-document extraction (use foundry-doc-vision-speech),
  standalone Work IQ, Fabric IQ, or Web IQ workloads, MCP server deployment (use
  foundry-mcp-aca), agent runtime (use foundry-hosted-agents).
metadata:
  version: "2.1.0"
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
| Knowledge source + knowledge base | One per Knowledge Base in SPEC § 7; GA REST `2026-10-01` by default (see [API surface map](#overview)) |
| `infra/modules/foundry-iq-index.bicep` | Composed by `azd-patterns` Bicep library; included by `threadlight-deploy` Phase 6 when SPEC § 7 declares foundry-iq |
| `infra/scripts/bootstrap_foundry_iq.py` | Postprovision hook that creates the index + uploads documents + creates the knowledge source and knowledge base |
| `src/agent/skills/<knowledge-skill>/SKILL.md` | Skill that wraps the knowledge base retrieve call (or the KB MCP tool) |
| User env in the [selected hosted profile](../foundry-hosted-agents/references/hosted-contract.json) | `APP_IQ_INDEX`, `APP_IQ_AGENT_NAME`, `AI_SEARCH_ENDPOINT`. In 2.0, migrate the former `FOUNDRY_IQ_*` keys: the hosted platform reserves `FOUNDRY_*`; do not declare those old names in a container. |

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
| `scripts/knowledge_base_manager.py` | KB Manager (default) | Creates `searchIndex` knowledge sources and knowledge bases and retrieves on GA `2026-10-01`; builds the KB MCP URL |
| `scripts/knowledge_agent_manager.py` | Legacy Agent Manager | Creates first-generation `2025-05-01-preview` Knowledge Agents; existing deployments only |
| `scripts/azure_openai_client.py` | LLM Client | Azure OpenAI client for chat completions; PolicyBot combining retrieval + generation |
| `test-fixture/consumer_prompt.md` + `live_smoke.py` | Live smoke | KS + KB + `low` retrieve on REST `2026-10-01`, then a prompt agent answering through the KB MCP tool (`2026-11-01-preview`) |
| `test-fixture/azure.yaml` + `infra/` | CI infrastructure | azd+Bicep source for the standing keyless Azure AI Search service, its managed identity and data-plane roles |

---

## Overview

Foundry IQ is Microsoft's enterprise-grade RAG solution that treats retrieval as a reasoning task. It uses Azure AI Search Knowledge Bases with agentic retrieval to enable multi-hop reasoning, query planning, and citation-backed responses.

> ### Agentic retrieval API surface map (November 2026)
>
> Four data-plane contracts exist side by side. They are **not
> interchangeable**:
>
> | Surface | API version | Status | Use it for |
> |---------|-------------|--------|------------|
> | Knowledge sources + knowledge bases | `2026-10-01` | **GA (default)** | `minimal`, `low`, `medium` effort, model query planning, answer synthesis, citations, SSE, per-request source controls |
> | Knowledge sources + knowledge bases | `2026-04-01` | GA, narrow | `minimal` extractive retrieval only; keep only for existing code |
> | Preview extensions | `2026-11-01-preview` | Preview | KB MCP endpoint for Foundry Agent Service, Microsoft Retriever 1, `auto` effort, named KB tools, GPT-6 profiles, graphs |
> | First-generation Knowledge Agents | `2025-05-01-preview` | Legacy preview | `/agents('<name>')`; the bundled `knowledge_agent_manager.py` only |
>
> Default to `2026-10-01` through
> [`scripts/knowledge_base_manager.py`](scripts/knowledge_base_manager.py).
> Opt into `2026-11-01-preview` only for a capability listed above. Do not
> migrate by changing only the API-version string; endpoint paths and wire
> shapes differ. Sources:
> [feature availability](https://learn.microsoft.com/azure/search/agentic-retrieval-overview#feature-availability),
> [create a knowledge base](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base),
> [migration guide](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate).

---

## Foundry IQ availability: GA vs preview

Foundry IQ's programmatic GA contract is the Azure AI Search REST API
`2026-10-01`. The older `2026-04-01` GA contract stays narrower (minimal,
extractive retrieval and four source kinds). The Azure portal and Microsoft
Foundry portal access to all agentic retrieval features remains preview, and
`2026-11-01-preview` adds the preview-only capabilities in the surface map.

<!-- GA_KNOWLEDGE_SOURCE_MATRIX_START -->
| Wire kind | `2026-10-01` | `2026-04-01` | Knowledge source | Indexed or remote |
|-----------|--------------|--------------|------------------|-------------------|
| `searchIndex` | GA | GA | [Existing Azure AI Search index](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-search-index) | Indexed |
| `azureBlob` | GA | GA | [Azure Blob Storage or ADLS Gen2](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob) | Indexed |
| `indexedOneLake` | GA | GA | [OneLake](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-onelake) | Indexed |
| `web` | GA | GA | [Bing-grounded public web](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-web) | Remote |
| `indexedSql` | GA | Preview | [Azure SQL](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-azure-sql) | Indexed |
| `file` | GA | Preview | [Direct file upload](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file) | Indexed |
| `indexedSharePoint` | GA | Preview | [Indexed SharePoint](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-sharepoint-indexed) | Indexed |
| `remoteSharePoint` | Preview | Preview | [Remote SharePoint](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-sharepoint-remote) | Remote |
| `fabricDataAgent` | Preview | Preview | [Fabric Data Agent](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-data-agent) | Remote |
| `fabricOntology` | Preview | Preview | [Fabric Ontology](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-fabric-ontology) | Remote |
| `mcpServer` | Preview | Preview | [External MCP server](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-mcp-server) | Remote |
| `workIQ` | Preview | Preview | [Work IQ](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-work-iq) | Remote |
<!-- GA_KNOWLEDGE_SOURCE_MATRIX_END -->

Source: [supported knowledge sources](https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview#supported-knowledge-sources)
and each source page (Azure SQL and indexed SharePoint state GA on
`2026-10-01` explicitly). A knowledge base that mixes kinds must use an API
version that supports every one of them; remote SharePoint still needs a
preview version.

The GA `web` kind is Bing-backed web grounding. It is not the separate
Web IQ capability, and `mcpServer` is not GA. Foundry IQ, Work IQ, Fabric IQ, and Web IQ are standalone Microsoft IQ capabilities that can be
combined; they are not one merged GA layer. Work IQ and Fabric IQ integrations
into Foundry remain preview.

Use [the migration guide](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate)
before moving code between stable and preview versions. Use the
[`2026-04-01` create-or-update reference](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01)
only for existing narrow-GA code; new code follows the
[`2026-10-01` knowledge base how-to](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base).

---

## Architecture

```
+---------------------------------------------------------------------+
|                    Foundry IQ Architecture                           |
+---------------------------------------------------------------------+
|                                                                      |
|  +----------------+    +------------------+    +-----------------+   |
|  |   Documents    |--->|  Azure AI Search |--->| Knowledge       |   |
|  |   (Blob)       |    |     Index        |    | Base            |   |
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

### 1. Knowledge sources and knowledge bases

A **knowledge source** describes where content lives (an index, a blob
container, a SharePoint site, the web). A **knowledge base** groups one or
more knowledge sources and optionally an Azure OpenAI model. It provides:
- **Query planning**: LLM-based decomposition at `low` or `medium` effort
- **Multi-hop retrieval**: `medium` adds one evaluated follow-up iteration
- **Extractive data or answer synthesis**: `outputMode` on the KB or request
- **References and activity**: citations plus per-step activity records

### 2. Retrieval reasoning effort

| Effort | `2026-10-01` | Needs a model | Behaviour |
|--------|--------------|---------------|-----------|
| `minimal` | GA | No | No LLM planning; one semantic intent per query; rejects `messages` |
| `low` | GA | Yes | One pass of LLM planning and source selection |
| `medium` | GA | Yes | Adds an evaluated follow-up iteration; select regions only |
| `auto` | Not accepted (400) | Yes | Preview (`2026-08-01-preview`, `2026-11-01-preview`) |

Set it on the KB as the default and override per retrieve request. Source:
[set the retrieval reasoning effort](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort).

### 3. API-generation-specific retrieval controls

Reasoning and answer-synthesis controls are API-generation-specific.
`2026-10-01` defines `retrievalReasoningEffort` (`minimal | low | medium`),
`outputMode`, `includeActivity`, `maxRuntimeInSeconds`,
`maxOutputSizeInTokens` and per-source `knowledgeSourceParams`.
`2026-04-01` accepts only intents with minimal, extractive retrieval.
`auto`, `retrieveDefaults`, query hints and `resultsProcessing` exist only in
preview versions. The legacy `2025-05-01-preview` helper sends none of these
fields; never copy them into a 2025-05 agent request.

### 4. Knowledge Sources

For production code on GA `2026-10-01`, use the kinds marked GA in the
matrix above. `remoteSharePoint`, `fabricDataAgent`, `fabricOntology`,
`mcpServer` and `workIQ` need a preview version. Never describe the GA `web`
wire value as Web IQ.

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
|               +-- knowledge_base_manager.py   # default, GA 2026-10-01
|               +-- knowledge_agent_manager.py  # legacy 2025-05-01-preview
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
> | Foundry account (agents, model deployments) | `Foundry User` (formerly Azure AI User) | `53ca6127-db72-4b80-b1b0-d745d6d5456d` |
>
> Plus: `Search Service Contributor` (`7ca78c08-252a-4471-8644-bb5ff32d4ba0`)
> on the Search service for the **deploy-time** identity that creates indexes,
> indexers, knowledge sources and knowledge bases (separate from the runtime
> UAMI; least privilege at runtime).
>
> The Foundry roles were renamed: **Foundry User**, **Foundry Owner**,
> **Foundry Account Owner** and **Foundry Project Manager** were previously
> Azure AI User, Azure AI Owner, Azure AI Account Owner and Azure AI Project
> Manager; role IDs are unchanged
> ([source](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect#authentication-and-permissions)).
> Tested (Nov 2026): `az role assignment create --role "Azure AI User"` fails
> with `Role 'Azure AI User' doesn't exist`; use `Foundry User` or the role ID.
>
> Two more identities need roles when the KB uses a model or an agent calls it:
>
> | Identity | Resource | Role | Why |
> |----------|----------|------|-----|
> | Search service system-assigned MI | Parent Foundry / Azure OpenAI account of the KB model | `Cognitive Services OpenAI User` (`5e0bd9bd-7b93-4f28-af87-19fc36ad61bd`) | Query planning and answer synthesis at `low`/`medium` |
> | Foundry project MI | Search service | `Search Index Data Reader` | Agent Service calls the KB MCP endpoint as the project (RemoteTool connection) |
>
> Docs conflict on the Search-MI model role: the knowledge base how-to names
> `Cognitive Services OpenAI User` in its prerequisites but `Cognitive
> Services User` in "Configure access", and the Agent Service connect page
> names `Cognitive Services User`. Tested (Nov 2026): `Cognitive Services
> OpenAI User` on the parent account is enough for `low` planning. Assign it
> on the account that matches `resourceUri`, never on a project or deployment.
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
> **Document-level permissions (ACL, RBAC scope, Purview labels).**
> Results are filtered per user only when a user token reaches the
> retrieve call. What a hosted agent or prompt agent actually forwards,
> the fail-closed behaviour without the token and the propagation lag
> are in [Permission trimming](#permission-trimming).

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
# AZURE_OPENAI_API_KEY=            # Optional — omit for keyless auth (REQUIRED to omit for threadlight pilots)
AZURE_OPENAI_API_VERSION=2025-04-01-preview

# Azure AI Search Configuration
AI_SEARCH_ENDPOINT=https://<service>.search.windows.net
# AI_SEARCH_KEY=                    # Optional — omit for keyless auth (REQUIRED to omit for threadlight pilots)
# Pin to match the endpoint surface you use:
#   2026-10-01         → GA /knowledgesources + /knowledgebases (default)
#   2026-11-01-preview → KB MCP endpoint for Agent Service, MSR1, auto effort
#   2026-04-01         → narrow GA (minimal, extractive) — existing code only
#   2025-05-01-preview → /agents('<name>') legacy Knowledge Agents only
AI_SEARCH_KNOWLEDGE_SOURCE_API_VERSION=2026-10-01
KNOWLEDGE_BASE_NAME=policy-kb
KNOWLEDGE_SOURCE_NAME=policy-ks
# minimal | low | medium (auto is preview-only)
KNOWLEDGE_BASE_REASONING_EFFORT=low

# Planning model for low/medium. Omit apiKey and authIdentity so Azure AI
# Search uses its system-assigned managed identity.
KNOWLEDGE_BASE_MODEL_RESOURCE_URI=https://<resource>.openai.azure.com
KNOWLEDGE_BASE_MODEL_DEPLOYMENT_ID=<deployment-name>
KNOWLEDGE_BASE_MODEL_NAME=gpt-5.4-mini

# Legacy only — scripts/knowledge_agent_manager.py (2025-05-01-preview)
# AI_SEARCH_API_VERSION=2025-05-01-preview
# KNOWLEDGE_AGENT_MODEL_RESOURCE_URI=https://<resource>.openai.azure.com/
# KNOWLEDGE_AGENT_MODEL_DEPLOYMENT_ID=<deployment-name>
# KNOWLEDGE_AGENT_MODEL_NAME=gpt-4.1-mini

# PolicyBot Configuration
POLICY_INDEX_NAME=policy-documents
POLICY_AGENT_NAME=policy-agent
POLICY_CHAT_MODEL=gpt-5.4-mini

# Document Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8001
```

---

## Required Packages

```bash
pip install "azure-search-documents~=12.1.0"   # 12.1.0 targets GA 2026-10-01
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

### 3. `knowledge_agent_manager.py` (legacy)
Creates and manages first-generation `2025-05-01-preview` Knowledge Agents.
Keep it only for deployments that already use `/agents('<name>')`; new work
uses `knowledge_base_manager.py`.

**Key Classes**:
- `KnowledgeAgentManager`: Creates first-generation agents with an explicit Azure OpenAI model and target indexes
- `KnowledgeAgentRetriever`: Performs retrieval with multi-turn history

### 4. `azure_openai_client.py`
Azure OpenAI client for chat completions and embeddings.

**Key Classes**:
- `AzureOpenAIClient`: Low-level chat completions
- `PolicyBot`: High-level Q&A combining retrieval + generation (defaults to `KnowledgeBaseRetriever`)

### 5. `knowledge_base_manager.py` (default)
Creates knowledge sources and knowledge bases and retrieves on GA `2026-10-01`.

**Key Classes and helpers**:
- `KnowledgeBaseManager`: `create_search_index_knowledge_source()`, `create_knowledge_base()` (rejects `auto`; requires the model triple for `low`/`medium`), deletes
- `KnowledgeBaseRetriever`: `retrieve()` with multi-turn history; sends one semantic intent at `minimal` and `messages` at `low`/`medium`; optional `query_source_authorization` for permission trimming
- `kb_mcp_endpoint()`: the `2026-11-01-preview` KB MCP URL for Agent Service connections

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

1. **Query Analysis**: The knowledge base planning model analyzes the user's question
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

> **MUST:** Use [`scripts/knowledge_base_manager.py`](scripts/knowledge_base_manager.py)
> (`KnowledgeBaseRetriever.retrieve()`). It keeps the `2026-10-01` path, the
> effort-specific body (`intents` at `minimal`, `messages` at `low`/`medium`)
> and the optional permission header together. Do not redefine it inline.

### Configuration Options

Knowledge base (`PUT /knowledgebases('<name>')?api-version=2026-10-01`):

| Property | Values | Description |
|-----------|--------|-------------|
| `knowledgeSources[].name` | Existing knowledge source names | Membership entries carry only `name`; source settings live on the knowledge source |
| `models[].azureOpenAIParameters` | `resourceUri`, `deploymentId`, `modelName` | Required for `low`/`medium`; omit `apiKey`/`authIdentity` to use the Search system MI |
| `retrievalReasoningEffort.kind` | `minimal` / `low` / `medium` | KB default; a request can override it |
| `outputMode` | `extractiveData` / `answerSynthesis` | Synthesis needs a model |
| `Prefer: return=representation` | HTTP header | Return the created definition |

Retrieve (`POST /knowledgebases('<name>')/retrieve?api-version=2026-10-01`):

| Property | Values | Description |
|-----------|--------|-------------|
| `intents` or `messages` | One or the other | `minimal` rejects `messages` |
| `knowledgeSourceParams[]` | `knowledgeSourceName`, matching `kind`, `alwaysQuerySource`, `failOnError`, `includeReferences`, `includeReferenceSourceData`, `maxOutputDocuments` (50-200) | Request-time per-source controls; omitting an entry doesn't exclude the source |
| `maxRuntimeInSeconds` | 10-600 | Request timeout budget |
| `maxOutputSizeInTokens` | ≥ 5000 | Grounding output budget |
| `includeActivity` | `true` / `false` | Activity records such as `modelQueryPlanning` |

Source: [retrieve with 2026-10-01 REST](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve#retrieve-with-2026-10-01-rest).

---

## KB access from a hosted MAF agent — three routes

When a hosted MAF agent (`Agent + FoundryChatClient + ResponsesHostServer`)
needs to call a Knowledge Base, you have three transport choices. Route A
uses the GA `2026-10-01` retrieve API. The KB MCP endpoint returns what its
API version allows: `2026-04-01` is always minimal and extractive, while
`2026-11-01-preview` returns synthesized answers when the KB has a model and
a compatible effort
([source](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve#authenticate-to-the-mcp-endpoint)).
This KB-as-MCP endpoint is distinct from the preview-only `mcpServer`
knowledge-source kind. Foundry Agent Service integration uses `2026-11-01-preview`
(see [Foundry Agent Service: prompt agent with the KB MCP tool](#foundry-agent-service-prompt-agent-with-the-kb-mcp-tool)).

| Route | What it is | Auth flavor | When to pick |
|---|---|---|---|
| **A. Direct SDK `@tool` (GA default)** | `KnowledgeBaseRetrievalClient.retrieve()` wrapped in an `@tool` function on `2026-10-01` | `DefaultAzureCredential` native, transparent token refresh | Production default. Fewest moving parts and no preview MCP transport. |
| **B. Direct KB MCP via `httpx.Auth`** | `MCPStreamableHTTPTool` against `<search>/knowledgebases/<n>/mcp?api-version=<version>` | AAD bearer (`https://search.azure.com/.default`) injected by an `httpx.AsyncClient(auth=httpx.Auth-subclass)` passed via `http_client=` | Uniform MCP surface. `2026-04-01` = GA extractive only; `2026-11-01-preview` = preview synthesis. **Do NOT use `header_provider=`** — see Common Errors row on bootstrap 401. |
| **C. Toolbox MCP wrapping the KB (preview)** | Foundry Toolbox `mcp` tool with `project_connection_id` pointing at a `RemoteTool` connection to the `2026-11-01-preview` KB endpoint | Toolbox handles transport + token refresh centrally; with `agentic-identity` auth the agent identity is used and user tokens are rejected | Use only when the Foundry Agent Service preview integration is acceptable and per-user trimming isn't needed. |

### Route A — Direct SDK `@tool` (minimal)

Tested (Nov 2026) with `azure-search-documents==12.1.0` against a `low`-effort
KB: the response carried a `modelQueryPlanning` activity and the reference.

```python
import os
from agent_framework import tool
from azure.identity import DefaultAzureCredential
from azure.search.documents.knowledgebases import KnowledgeBaseRetrievalClient
from azure.search.documents.knowledgebases.models import (
    KnowledgeBaseMessage,
    KnowledgeBaseMessageTextContent,
    KnowledgeBaseRetrievalRequest,
    KnowledgeRetrievalLowReasoningEffort,
    SearchIndexKnowledgeSourceParams,
)

_credential = DefaultAzureCredential()
_kb_client = KnowledgeBaseRetrievalClient(
    endpoint=os.environ["AI_SEARCH_ENDPOINT"],
    knowledge_base_name=os.environ["KB_NAME"],
    credential=_credential,
    api_version="2026-10-01",
)

@tool(approval_mode="never_require")
def my_kb_tool(query: str) -> dict:
    """Retrieve grounding data with citations from the knowledge base."""
    request = KnowledgeBaseRetrievalRequest(
        messages=[
            KnowledgeBaseMessage(
                role="user",
                content=[KnowledgeBaseMessageTextContent(text=query)],
            )
        ],
        retrieval_reasoning_effort=KnowledgeRetrievalLowReasoningEffort(),
        knowledge_source_params=[
            SearchIndexKnowledgeSourceParams(
                knowledge_source_name=os.environ["KNOWLEDGE_SOURCE_NAME"],
                include_references=True,
                include_reference_source_data=True,
            )
        ],
    )
    result = _kb_client.retrieve(request)
    return {
        "response": result.response,
        "activity": result.activity,
        "references": result.references,
    }
```

`low` needs a model on the KB. For a model-free KB use
`KnowledgeRetrievalMinimalReasoningEffort()` with
`intents=[KnowledgeRetrievalSemanticIntent(search=query)]` instead of
`messages`; minimal rejects `messages`.

`include_reference_source_data=True` is the SDK spelling of the stable
`2026-04-01` retrieve-time `knowledgeSourceParams` control
`includeReferenceSourceData` (unchanged on `2026-10-01`). Set it per
retrieval request, not on the persisted knowledge-source definition.

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
         f"/knowledgebases/{os.environ['KB_NAME']}/mcp?api-version=2026-11-01-preview"),
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

## Foundry Agent Service: prompt agent with the KB MCP tool

A knowledge base is a standalone MCP server exposing `knowledge_base_retrieve`.
Foundry Agent Service reaches it through a project connection. Labels:
**Documented** = [connect a knowledge base to Agent Service](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect);
**Tested** = run end-to-end by this skill's CI fixture (Nov 2026, Sweden
Central, `gpt-5.4-mini`).

Prerequisites (Documented):

| Identity | Scope | Role |
|----------|-------|------|
| You / deploy identity | Foundry account | `Foundry Project Manager` to create the connection; `Foundry User` to create and use agents |
| Foundry project system-assigned MI | Search service | `Search Index Data Reader` (+ `Search Index Data Contributor` only if the agent writes) |
| Search service system-assigned MI | Parent account of the KB model | Model access role (see the RBAC table above) |

**1. Create a `RemoteTool` connection** (Azure Resource Manager):

```http
PUT https://management.azure.com/{project_resource_id}/connections/{connection_name}?api-version=2025-10-01-preview

{
  "name": "{connection_name}",
  "type": "Microsoft.MachineLearningServices/workspaces/connections",
  "properties": {
    "authType": "ProjectManagedIdentity",
    "category": "RemoteTool",
    "target": "https://{search}.search.windows.net/knowledgebases/{kb}/mcp?api-version=2026-11-01-preview",
    "isSharedToAll": true,
    "audience": "https://search.azure.com/",
    "metadata": { "ApiType": "Azure" }
  }
}
```

**2. Create a prompt agent** with an `mcp` tool limited to
`knowledge_base_retrieve`, the only tool Agent Service supports for a KB:

```http
POST {project_endpoint}/agents?api-version=v1

{
  "name": "{agent_name}",
  "definition": {
    "kind": "prompt",
    "model": "{deployment}",
    "instructions": "Use the knowledge base tool for every question. If it has no answer, reply \"I don't know\". Cite sources.",
    "tools": [{
      "type": "mcp",
      "server_label": "knowledge-base",
      "server_url": "https://{search}.search.windows.net/knowledgebases/{kb}/mcp?api-version=2026-11-01-preview",
      "require_approval": "never",
      "allowed_tools": ["knowledge_base_retrieve"],
      "project_connection_id": "{connection_name}"
    }]
  }
}
```

**3. Invoke** through the project Responses endpoint. On the `/openai/v1/`
path, **do not add `api-version`**. Tested: `POST {project}/openai/v1/responses?api-version=v1`
returns `400 api-version query parameter is not allowed when using /v1 path`;
the same call without the query parameter returns `200`.

```http
POST {project_endpoint}/openai/v1/responses

{ "input": "{question}", "agent_reference": { "type": "agent_reference", "name": "{agent_name}" } }
```

Check the `output` array for an item with `type: "mcp_call"` and
`name: "knowledge_base_retrieve"`. **4. Clean up**: `DELETE
{project_endpoint}/agents/{agent_name}?api-version=v1`, then `DELETE` the
connection. Deleting them doesn't delete the KB or its knowledge sources.

The canonical, tested sequence (including UUID-suffixed names and cleanup)
is [`test-fixture/live_smoke.py`](test-fixture/live_smoke.py).

---

## Billing: `knowledgeRetrieval` and HTTP 402

From Search Service REST `2026-04-01` onward, agentic retrieval billing is
controlled by the service property `knowledgeRetrieval` (`free` | `standard`),
independently of `semanticSearch`. New services default to `free`: after the
monthly allowance, requests that would incur paid usage return **HTTP 402**.
Set `standard` (Basic tier or higher) with Search Management API
`2026-03-01-preview` or later
([source](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-enable-disable)):

```http
PATCH https://management.azure.com/subscriptions/{sub}/resourcegroups/{rg}/providers/Microsoft.Search/searchServices/{name}?api-version=2026-03-01-preview

{ "properties": { "knowledgeRetrieval": "standard" } }
```

GET the service with the same API version and confirm
`properties.knowledgeRetrieval` is `standard`. In Bicep, set
`knowledgeRetrieval: 'standard'` on `Microsoft.Search/searchServices@2026-03-01-preview`
(as this skill's CI infrastructure does). If you relied on `semanticSearch`
for paid agentic retrieval, set `knowledgeRetrieval` explicitly before moving
to `2026-04-01` or later. Model tokens for planning and synthesis are billed
separately on the Azure OpenAI resource.

---

## Preview: `2026-11-01-preview` (Microsoft Retriever 1, `auto`)

- **Microsoft Retriever 1 (MSR1)** is a parameterless planning model,
  `{"kind": "microsoftRetriever1"}`. A KB with only MSR1 supports `minimal`
  and extractive output, not answer synthesis. Requires the `standard`
  knowledge retrieval plan
  ([source](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-use-microsoft-retriever)).
- **`auto` effort** needs exactly one MSR1 model plus one `azureOpenAI` or
  `openAICompatible` model, and a preview API. It is rejected on `2026-10-01`
  ([source](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)).
- **Region caveat (Tested, Nov 2026):** in Sweden Central, creating a KB with
  `auto` and `[microsoftRetriever1, azureOpenAI]` failed with
  `Agentic retrieval is not available in this region or environment`, while
  `low` and `medium` worked. The MSR1 page links to the region table for Auto
  support, but that table has no Auto or MSR1 column, so availability is not
  documented per region. Test `auto` in your region before designing for it.
- Entity and topic graphs, named KB tools, GPT-6 model profiles and async
  file ingestion are also `2026-11-01-preview` only; see the
  [feature availability](https://learn.microsoft.com/azure/search/agentic-retrieval-overview#feature-availability)
  list before using them.

---

## Permission trimming

"Permissions are enforced" depends on three things: whether a per-user token
reaches the retrieve call, the source type, and authorization propagation.

**Headers** (Documented, [enforce permissions at query time](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve#enforce-permissions-at-query-time-preview)):

| Header | Sources | Value |
|--------|---------|-------|
| `x-ms-query-source-authorization` | All except Work IQ | Delegated user token for `https://search.azure.com/.default`; needs no Search role |
| `x-ms-query-work-iq-source-authorization` | Work IQ | App-audience user assertion (Work IQ flow) |

`Authorization` separately authorizes the Search call and can be a managed
identity. Blob container RBAC (`ingestionPermissionOptions: ["rbacScope"]`)
and ADLS Gen2 ACL/RBAC ingestion and query filtering are GA on `2026-10-01`.

**Behaviour**:

| Case | Result | Label |
|------|--------|-------|
| Retrieve **without** the user header on a permission-filtered source | `200`, only public grants; protected documents are **not** returned (fail closed) | Tested (`2026-10-01` and `2026-11-01-preview`); Documented by the retrieve how-to |
| Retrieve with a user token, user holds a Blob data role covering the container | That container's documents returned | Tested in a member-user setup (#559). Not reproduced here: a B2B guest user with `Storage Blob Data Reader` on the container, then the account, got no documents after 16 h (undocumented; see note) |
| Role narrowed on Storage | Results follow only after a delay: ~7 min in one test (#559) | Tested; delay not documented |
| Prompt agent (KB MCP tool), no header configured, invoked by a user | Trimmed: Agent Service set the header from the calling user | Tested; Documented ("Set dynamically by Agent Service") |
| Prompt agent with `structured_inputs` + `headers: {"x-ms-query-source-authorization": "{{search_auth_token}}"}` | Trimmed identically | Tested; Documented |
| Hosted agent + Toolbox with `agentic-identity` connection | Agent identity only; user tokens are rejected on purpose, so no per-user trimming | Documented ([quickstart](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-foundry-iq-hosted-agent)) |
| Blob KS with graph extraction + `ingestionPermissionOptions` | `400 Attaching provenance index '...' with document-level permissions is not supported.` | Tested (preview); the OneLake page also says to omit graph extraction with permission ingestion |

**Documentation conflict.** The Agent Service connect page says "Without the
token, permission-enabled sources return results unfiltered", while the
retrieve how-to says omitting the header "retains only public `all` grants;
it doesn't return unfiltered results". Our tests match the retrieve how-to.
Design for fail-closed, but never rely on either behaviour as a security
boundary without your own probe.

**Propagation and identities.** The docs say Blob RBAC scope is evaluated
against the delegated user at query time, that "authorization resolution uses
caches; reindexing doesn't force those caches to refresh", and that
permission changes "can take time to appear"
([source](https://learn.microsoft.com/azure/search/search-query-access-control-rbac-enforcement#how-query-time-enforcement-works)).
No duration is documented: plan for minutes, re-test after changes, and
probe with the real user population. In our Nov 2026 run the querying user
was a B2B guest of the test tenant; with the role at container and then
account scope, `2026-10-01` and `2026-11-01-preview` still returned no
protected content after 16 hours (fail closed). Guest support for `rbacScope`
isn't documented either way, so test with member and guest users you expect.

**Probe recipe** before you claim per-user trimming:

1. Index one known-answer document per container with `rbacScope`.
2. Query without the header: expect no protected content.
3. Query as a user entitled to one container: expect only that answer.
4. Query as a differently entitled user: expect the denial.
5. After any role change, re-check the denial at least 15 minutes later, and
   longer if the user queried before the change (cached negative result).
6. Never retry a failed permission evaluation without the user token or with
   elevated read.

---

## API Reference

### Knowledge base retrieval (default)

Use `KnowledgeBaseRetriever` in
[`scripts/knowledge_base_manager.py`](scripts/knowledge_base_manager.py) or
the Route A SDK sample. Both target GA `2026-10-01`.

### Knowledge Agent Retrieval

> **Legacy appendix.** Everything from here to the end of "Direct REST API
> (Alternative)" applies only to first-generation `2025-05-01-preview`
> Knowledge Agents. Do not use it for new work.

`azure-search-documents~=12.1.0` has no first-party Python SDK client for
the `2025-05-01-preview` Knowledge Agent surface. Do not import
`azure.search.documents.agent` or reuse stable Knowledge Base
`knowledge_source_params` models here.

> **MUST:** Reuse the canonical bundled REST helper in
> [`scripts/knowledge_agent_manager.py`](scripts/knowledge_agent_manager.py).
> Its `KnowledgeAgentRetriever` keeps the API version, OData agent path,
> typed `messages`, and `targetIndexParams` request shape together. For a
> minimal standalone call, use the direct REST example below.

### Direct REST API (Alternative)

```python
# Used in KnowledgeAgentService — keyless with DefaultAzureCredential
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://search.azure.com/.default").token

url = f"{endpoint}/agents('{agent_name}')/retrieve?api-version=2025-05-01-preview"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

request_body = {
    "messages": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What is the PTO policy?"}],
        }
    ],
    "targetIndexParams": [{"indexName": "policy-documents"}],
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
    index_name=os.environ["APP_IQ_INDEX"],
    credential=DefaultAzureCredential(),
)
results = client.upload_documents(documents=docs)
ok = sum(1 for r in results if r.succeeded)
fail = [(r.key, r.status_code, r.error_message) for r in results if not r.succeeded]
if fail:
    raise RuntimeError(f"Search upload partial: ok={ok} failed={len(fail)} first_fail={fail[0]}")
print(f"Seeded {ok} docs into '{os.environ['APP_IQ_INDEX']}'")
```

### 2. Fail-fast on every shell-out

If you *must* shell out to `az rest` (e.g., for the `/agents('<name>')` PUT
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
        index_name=os.environ["APP_IQ_INDEX"],
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

### 3. API Generation Selection
- Use GA `2026-10-01` for knowledge bases, including `low`/`medium` planning and answer synthesis
- Use `2026-11-01-preview` only for the KB MCP endpoint in Agent Service, MSR1, `auto` and other preview features
- Use `2025-05-01-preview` only for compatibility with first-generation Knowledge Agents

### 4. Error Handling
- Knowledge bases may not exist on first run - handle gracefully
- Index creation is idempotent - "already exists" is OK
- API version mismatches are common - pin the version per surface, never only swap the string

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
2. **Keep API generations atomic**: version, paths, persisted definitions, and retrieve request shapes must move together
3. **Include clear agent instructions** for citation format
4. **Handle gracefully when KB lacks relevant content**
5. **Log all configuration at startup** for debugging
6. **Use health checks** to verify all services are operational

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| API Version mismatch | Mixing GA, preview, and first-generation wire contracts | Use `AI_SEARCH_KNOWLEDGE_SOURCE_API_VERSION=2026-10-01` for GA knowledge sources and knowledge bases, `2026-11-01-preview` only for preview-only capabilities (KB MCP for Agent Service, MSR1, `auto`), or `AI_SEARCH_API_VERSION=2025-05-01-preview` for the legacy `/agents('<name>')` script. Do not change only the version string; endpoint paths and payloads differ. |
| Missing index | Index not created | Run `/setup` endpoint first |
| Authentication failed | 401 / 403 from Search or AOAI | Threadlight pilots are **keyless-by-mandate** — verify the agent's UAMI has the required Entra roles (Search Index Data Reader, Cognitive Services OpenAI User, Foundry User on the Foundry account) AND that `AZURE_CLIENT_ID` is exported into the container so DefaultAzureCredential picks the UAMI (not the dev-loop user). Do NOT bypass by setting `AI_SEARCH_KEY` or `AZURE_OPENAI_API_KEY`. |
| 403 from `corpus_query` after RBAC grant on Foundry hosted agent | Granted only to project / account MI; hosted-agent runtime uses `blueprint.principal_id` + `instance_identity.principal_id` instead | Grant `Search Index Data Reader` to BOTH MIs (see Hosted-agent runtime identity callout in § Environment Variables). Wait 5-10 min for AI Search RBAC propagation. |
| `'search.in' invalid expression` from corpus filter | Wrong OData syntax — separate quoted args instead of single CSV string | Use `search.in(field, 'a,b,c', ',')` — single quoted CSV string + delimiter, NOT `search.in(field, 'a','b','c')`. Common copy-paste error. |
| `KnowledgeAgent` PUT returns 400/500 | The `2025-05-01-preview` tuple is incomplete or the preview surface is unavailable in the target region | Confirm the OData `/agents('<name>')` path, required `Prefer: return=representation` header, required `models` and object-valued `targetIndexes`, supported model name, Search system-MI access to the model, and the matching retrieve shape. Prefer `/knowledgebases('<name>')` on GA `2026-10-01` for new production code. |
| Index doc count = 0 after "successful" bootstrap | Bootstrap script silently swallowed an `az rest` error (rc != 0 then `[seeded N]` logged unconditionally) | See § Bootstrap script: hardening checklist. Replace `az rest` with direct `SearchClient.upload_documents(...)`, fail-fast on rc != 0, and inspect per-doc result.succeeded. |
| `InvalidDocumentKey` 400 on upload | Document key contains illegal chars (parens, brackets, dots, spaces) | Sanitize keys: `re.sub(r"[^A-Za-z0-9_\-=]", "_", name)` then collapse runs of `_` and trim to 128 chars. AI Search only accepts `[A-Za-z0-9_\-=]`. |
| `Field 'content' contains a term that is too large to process. The max length for UTF-8 encoded terms is 32766 bytes.` | Source doc has a long unbroken token (URL, base64 blob, no whitespace) > 32k bytes | Chunk content > ~25k chars at paragraph / sentence / whitespace boundaries with a hard-cap fallback. Don't rely on `[:60000]` truncation — that doesn't fix the term length, only the field length. |
| Hosted MAF agent returns `server_error` after wiring `MCPStreamableHTTPTool` against `/knowledgebases/<n>/mcp` | **Confirmed (May 2026):** MAF's `MCPStreamableHTTPTool._ensure_connected()` issues an MCP `ping` request during agent registration. KB MCP returns HTTP 500 on `ping`. The agent fails to register and every invoke returns `server_error` with no useful log signal. On MAF 1.6.0, overriding `_ensure_connected` with a `self._client` reference causes `AttributeError` (attribute renamed to `self.client`) — container starts, readiness passes, but every request returns empty `output: []` / `model: ""` | **Recommended (MAF 1.6.0+):** subclass with `_ping_available = False` in `__init__` — MAF's base respects this flag natively: `class _PingSkipMCPTool(MCPStreamableHTTPTool): def __init__(self, **kwargs): super().__init__(**kwargs); self._ping_available = False`. This is cleaner than overriding `_ensure_connected` and survives internal attribute renames. See `foundry-hosted-agents` SKILL § "MCP `ping` trap". |
| `401` from KB MCP endpoint on hosted MAF agent (despite agent identity having `Search Index Data Reader`) | `MCPStreamableHTTPTool(header_provider=...)` does NOT cover the MCP bootstrap exchange. The `_mcp_call_headers` ContextVar is only set inside `call_tool()` (`agent_framework/_mcp.py` ~line 1589); `_ensure_connected` runs `initialize` + `tools/list` BEFORE the first `call_tool`, with the ContextVar still empty → no `Authorization` header → 401 → agent boot fails. The `server_error` surfaced to the responses endpoint has no useful log signal. | **Use `httpx.AsyncClient(auth=httpx.Auth)` via `http_client=`** instead of `header_provider=`. The `auth.auth_flow()` method runs on EVERY outbound request including bootstrap. See `foundry-hosted-agents` SKILL § "MCP with per-call AAD bearer (`header_provider`)" → ⚠️ Bootstrap caveat for the worked `httpx.Auth` example, and § KB access from a hosted MAF agent → Route B above. |
| `references[].source_data` is `null` on KB MCP / SDK responses | The retrieve request omits `includeReferenceSourceData: true`; the KB returns reference IDs without structured source data | On `2026-04-01` and `2026-10-01`, set `"includeReferenceSourceData": true` on the matching entry in retrieve-time `knowledgeSourceParams`. In Python SDK 12.x, use `SearchIndexKnowledgeSourceParams(..., include_reference_source_data=True)`. Do not place this request control on the persisted knowledge-source definition. |
| `client.get_mcp_tool()` accepts only static `headers: dict[str, str]` — no `header_provider` | The hosted-MCP shape is designed for static API keys / unauthenticated MCPs; the static dict is pinned at agent build time | For MCP servers that need short-lived AAD tokens (e.g. KB MCP, Storage MCP behind PMI), do NOT use `client.get_mcp_tool()` — switch to `MCPStreamableHTTPTool + header_provider`. Static `Bearer` tokens in the dict will expire after ~1h and break the agent until container restart. Bug-009/014 itself is FIXED in `agent-framework-core` 1.3.0 ([PR #5581](https://github.com/microsoft/agent-framework/pull/5581)) — the static-headers limitation is a separate design constraint. |
| Foundry Toolbox `azure_ai_search` tool type wraps an INDEX, not a Knowledge Base | The built-in Toolbox tool only exposes `index_name` + `query_type=vector_semantic_hybrid` — no agentic query planning or answer synthesis | The Foundry Agent Service / Toolbox MCP integration is preview. Use `server_url=<search>/knowledgebases/<n>/mcp?api-version=2026-11-01-preview` with a `RemoteTool` project connection (see "Foundry Agent Service: prompt agent with the KB MCP tool") only when preview terms are acceptable; otherwise call stable Route A directly. |
| HTTP `402 Payment Required` from retrieve | Service on the default `knowledgeRetrieval: free` plan and the monthly allowance is used | PATCH `knowledgeRetrieval: standard` (Search Management `2026-03-01-preview`+); see § Billing |
| `400` on retrieve with `retrievalReasoningEffort: auto` | `auto` is preview-only; `2026-10-01` rejects it | Use `minimal`/`low`/`medium` on GA, or a preview API with MSR1 + an external model |
| `Agentic retrieval is not available in this region or environment` creating a KB with `auto` + MSR1 | Tested in Sweden Central (Nov 2026); per-region Auto/MSR1 support isn't documented | Use `low`/`medium`, or test another region |
| `400 api-version query parameter is not allowed when using /v1 path` | `?api-version=` added to `{project}/openai/v1/...` | Drop the query parameter on `/openai/v1/` paths |
| `Role 'Azure AI User' doesn't exist` | Foundry roles were renamed | Use `Foundry User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`) |
| Agent answers without calling the KB, or 403 from Search via the agent | Project MI lacks `Search Index Data Reader`, or `allowed_tools` misses `knowledge_base_retrieve` | Grant the role on the Search service to the **project** MI; keep `allowed_tools: ["knowledge_base_retrieve"]`; require tool use in instructions |
| `400 Attaching provenance index '...' with document-level permissions is not supported` | Graph extraction combined with `ingestionPermissionOptions` | Choose one: graph extraction or document-level permissions |
| User sees no protected documents right after a role change | Authorization propagation and Search authorization caches | Re-check later (see § Permission trimming); don't fall back to elevated read |
| No results | Empty index | Index sample documents first |
| Timeout | Large retrieval | Reduce requested output or chunk size; adjust reasoning only when the selected API version publishes that control |

### Debug Checklist

1. Check environment variables are loaded
2. Verify Azure services are accessible (health endpoint)
3. Confirm index exists and has documents
4. Test simple queries before complex ones
5. Check API response codes and error messages

---

## Extension Ideas

1. **Add SharePoint source**: Connect document libraries as knowledge sources
2. **Skill-based orchestration**: Wrap the knowledge base retrieval in a dedicated `src/agent/skills/<knowledge-skill>/SKILL.md` so the threadlight agent (single-agent, skill-based pattern) can call it as a tool — this is the orchestration model `threadlight-design` uses, NOT a separate retrieval agent
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
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | The hosted agent that calls this knowledge base as a tool |

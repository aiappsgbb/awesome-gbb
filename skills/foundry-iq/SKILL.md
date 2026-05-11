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
| [**threadlight-design**](../threadlight-design/) | Generates SPEC.md § 7 Knowledge Sources — the input contract for this skill |
| [**threadlight-deploy**](../threadlight-deploy/) | Phase 6 (Module Composer) wires `foundry-iq-index.bicep` when SPEC § 7 declares `Backing service: foundry-iq` |
| [**azd-patterns**](../azd-patterns/) | Owns the `foundry-iq-index.bicep` module shape |
| [**foundry-doc-vision-speech**](../foundry-doc-vision-speech/) | Pairs with this skill: extract structured text from raw docs (foundry-doc-vision-speech) → index it for retrieval (foundry-iq) |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Alternative knowledge backing (`mcp-search`) when foundry-iq is genuinely overkill — prefer foundry-iq by default |
| [**foundry-evals**](../foundry-evals/) | Evaluates retrieval precision, citation accuracy, multi-hop reasoning quality |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | The hosted agent that calls this Knowledge Agent as a tool |

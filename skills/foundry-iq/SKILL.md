---
name: foundry-iq
description: Build enterprise RAG solutions using Foundry IQ with Azure AI Search agentic retrieval. Use when implementing policy assistants, knowledge bases with citations, or multi-hop question answering systems.
---

# Foundry IQ Agent Framework Integration Skill

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

```bash
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
# AZURE_OPENAI_API_KEY=            # Optional — omit for keyless auth
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Azure AI Search Configuration
AI_SEARCH_ENDPOINT=https://<service>.search.windows.net
# AI_SEARCH_KEY=                    # Optional — omit for keyless auth
AI_SEARCH_API_VERSION=2025-01-01-preview

# PolicyBot Configuration
POLICY_INDEX_NAME=policy-documents
POLICY_AGENT_NAME=policy-agent
POLICY_CHAT_MODEL=gpt-5.4-mini

# Document Chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Agentic Retrieval
REASONING_EFFORT=medium       # minimal | low | medium
OUTPUT_MODE=extractive_data

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
| API Version mismatch | Using old version | Use `2025-01-01-preview` for Knowledge Agents |
| Missing index | Index not created | Run `/setup` endpoint first |
| Authentication failed | Bad credentials | Check API keys in `.env` |
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
2. **Multi-agent orchestration**: Specialized agents for different domains
3. **Streaming responses**: Real-time token streaming with Gradio UI
4. **Custom functions**: Email escalation, ticket creation, etc.
5. **Caching layer**: Redis for conversation history and frequent queries
6. **Observability**: OpenTelemetry tracing for request flow visibility

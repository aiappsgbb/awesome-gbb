# Product Requirements Document: Foundry IQ Skill

## Document Information
| Field | Value |
|-------|-------|
| Skill Name | Foundry IQ |
| Version | 1.1 |
| Last Updated | July 2026 |
| Status | Building Block |

---

## 1. Overview

### 1.1 Purpose
The Foundry IQ skill provides reusable building blocks for creating enterprise-grade RAG (Retrieval-Augmented Generation) solutions using Azure AI Search Knowledge Agents with agentic retrieval. This skill enables multi-hop reasoning, query planning, and citation-backed responses.

### 1.2 Scope
This skill covers:
- Azure AI Search index creation and management
- Document indexing with smart chunking
- Knowledge Agent configuration and retrieval
- Agentic retrieval with query decomposition
- Citation tracking and response synthesis
- GA-versus-preview knowledge-source selection

### 1.3 Building Block Nature
**This skill is a building block, not a complete product.** Integrators should:
- Define their own document corpus and domain
- Implement custom UI for their use case
- Add authentication and access control
- Configure retrieval parameters for their needs
- Integrate with their existing systems

---

## 2. Functional Requirements

### 2.1 Core Capabilities

| ID | Requirement | Priority | Description |
|----|-------------|----------|-------------|
| FR-1 | Index Management | P0 | Create and configure Azure AI Search indexes with vector search |
| FR-2 | Document Indexing | P0 | Index documents with smart chunking and sentence boundary detection |
| FR-3 | Knowledge Agent Creation | P0 | Create and configure Knowledge Agents for retrieval |
| FR-4 | Semantic Retrieval | P0 | Fast retrieval for simple queries (~100-300ms) |
| FR-5 | Agentic Retrieval | P0 | Multi-hop reasoning for complex queries (~1-3s) |
| FR-6 | Citation Tracking | P1 | Maintain source references in responses |
| FR-7 | Query Decomposition | P1 | Break complex questions into sub-queries |
| FR-8 | Multi-turn Conversations | P1 | Track conversation history for context |
| FR-9 | Configurable Reasoning | P2 | Adjust reasoning effort (minimal/low/medium) |
| FR-10 | Stable Knowledge Sources | P0 | Use only `searchIndex`, `azureBlob`, `indexedOneLake`, or `web` on stable REST `2026-04-01` |

### 2.2 Retrieval Modes

| Mode | Latency | Use Case | Reasoning |
|------|---------|----------|-----------|
| Semantic | ~100-300ms | Simple Q&A, factual queries | None |
| Agentic | ~1-3s | Complex questions, multi-hop reasoning | Query planning |

### 2.3 Integration Points

| Integration Point | Description | Required By Integrator |
|-------------------|-------------|----------------------|
| Document Pipeline | Ingest documents into the system | Yes - MUST implement |
| User Interface | Chat/search interface | Yes - MUST implement |
| Authentication | User identity and access control | Yes - MUST implement |
| Domain Configuration | Index schema, chunking parameters | Yes - MUST customize |
| Response Formatting | Citation display, answer presentation | Yes - MUST customize |

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Metric | Requirement |
|--------|-------------|
| Semantic Retrieval | < 500ms p95 |
| Agentic Retrieval | < 5s p95 |
| Document Indexing | 100+ documents/minute |
| Index Size | Scales to millions of documents |

### 3.2 Scalability

| Tier | Documents | Recommended SKU |
|------|-----------|-----------------|
| Small | < 10,000 | Basic |
| Medium | 10,000 - 1M | Standard S1 |
| Large | > 1M | Standard S2/S3 |

### 3.3 Security

- **API Keys**: Store in environment variables, never in code
- **Index Access**: Configure per-index permissions
- **Data Residency**: Choose appropriate Azure region

---

## 4. Technical Constraints

### 4.1 Azure Service Dependencies

| Service | Purpose | Required |
|---------|---------|----------|
| Azure AI Search | Document storage and retrieval | Yes |
| Azure OpenAI | Embeddings and chat completions | Yes |
| Azure Blob Storage | Document source (optional) | Optional |

### 4.2 API Version Requirements

| Surface | Version | Status |
|---------|---------|--------|
| Azure AI Search Knowledge Sources / Knowledge Bases | `2026-04-01` | GA programmatic slice |
| Azure AI Search expanded source kinds and options | `2026-05-01-preview` | Preview |
| Legacy Knowledge Agents used by bundled scripts | `2025-01-01-preview` | Preview compatibility path |
| Azure OpenAI | `2024-12-01-preview` | Existing sample dependency |

### 4.3 Chunking Constraints

| Parameter | Default | Range | Impact |
|-----------|---------|-------|--------|
| Chunk Size | 1000 chars | 500-2000 | Larger = more context, higher cost |
| Chunk Overlap | 200 chars | 50-500 | Larger = better continuity, more tokens |

---

## 5. User Stories (For Integrators)

### 5.1 Application Developer Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-1 | As a developer, I want to index my company's documents | Documents chunked and indexed with vectors |
| US-2 | As a developer, I want to enable semantic search | Users can search with natural language |
| US-3 | As a developer, I want multi-hop reasoning | Complex questions decomposed and answered |
| US-4 | As a developer, I want cited responses | Answers include source references |

### 5.2 End User Stories (When Integrated)

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| EU-1 | As a user, I want to ask questions about policies | Get accurate answers with citations |
| EU-2 | As a user, I want to ask complex multi-part questions | System handles query decomposition |
| EU-3 | As a user, I want to verify answer sources | Can click citations to see source |

---

## 6. Available Building Blocks

### 6.1 Python Scripts

| Script | Purpose | Key Classes |
|--------|---------|-------------|
| `search_index_manager.py` | Index lifecycle management | `SearchIndexManager` |
| `document_indexer.py` | Document chunking and upload | `DocumentIndexer` |
| `knowledge_agent_manager.py` | Agent creation and retrieval | `KnowledgeAgentManager`, `KnowledgeAgentRetriever` |
| `azure_openai_client.py` | Chat completions and embeddings | `AzureOpenAIClient`, `PolicyBot` |

### 6.2 Recommended Project Structure

```
your-app/
├── .env                    # Configuration
├── src/
│   └── foundry-iq/
│       ├── app/
│       │   ├── main.py     # FastAPI endpoints
│       │   ├── models.py   # Request/response models
│       │   └── services.py # Business logic
│       └── requirements.txt
└── documents/              # Your document corpus
```

---

## 7. Integration Checklist

### 7.1 Before Integration

- [ ] Azure AI Search service provisioned
- [ ] Azure OpenAI service with embedding model deployed
- [ ] Document corpus identified and prepared
- [ ] Index schema designed for your domain

### 7.2 During Integration

- [ ] Environment variables configured (see `.env.sample`)
- [ ] Index created with appropriate fields
- [ ] Documents chunked and indexed
- [ ] Knowledge Agent created with reasoning settings
- [ ] API endpoints implemented

### 7.3 Testing

- [ ] Simple queries return accurate results
- [ ] Complex multi-hop queries decompose correctly
- [ ] Citations map to source documents
- [ ] Conversation context maintained across turns
- [ ] Error handling for missing content

---

## 8. Limitations & Constraints

### 8.1 Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Agentic retrieval latency | 1-3s per query | Use semantic mode for simple queries |
| Reasoning effort cost | Higher effort = more tokens | Match effort to query complexity |
| API version requirements | Stable and preview capabilities differ | Use `2026-04-01` for the four GA kinds; opt into `2026-05-01-preview` only for explicitly preview features |
| Regional availability | Knowledge Agents limited regions | Deploy in supported regions |

### 8.2 Out of Scope

The following are NOT provided by this skill:
- Document OCR or extraction (use Azure Document Intelligence)
- User authentication/authorization
- Custom embedding models
- Real-time document sync
- Multi-language support configuration

---

## 9. Configuration Guidelines

### 9.1 Reasoning Effort Selection

| Query Type | Recommended Effort | Example |
|------------|-------------------|---------|
| Factual lookup | minimal | "What is the PTO policy?" |
| Comparison | low | "Compare expense limits for travel vs supplies" |
| Multi-hop | medium | "Can I work remotely while using PTO?" |

### 9.2 Chunking Strategy

| Document Type | Chunk Size | Overlap | Rationale |
|---------------|------------|---------|-----------|
| Policies | 1000 | 200 | Balance context and precision |
| Technical docs | 1500 | 300 | Preserve code blocks |
| FAQs | 500 | 100 | Keep Q&A pairs intact |

---

## 10. Success Metrics (For Integrators to Define)

Suggested metrics for integrated applications:

| Metric | Description | Target (Example) |
|--------|-------------|------------------|
| Answer Accuracy | % of correct answers (human eval) | > 85% |
| Citation Precision | % of citations that are relevant | > 90% |
| Query Latency | p95 response time | < 3s for agentic |
| User Satisfaction | Post-query rating | > 4.0/5.0 |
| Fallback Rate | % queries with "no relevant info" | < 10% |

---

## 11. References

- [SKILL.md](./SKILL.md) - Detailed technical documentation
- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [Foundry IQ overview](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [Knowledge-source availability](https://learn.microsoft.com/azure/search/agentic-knowledge-source-overview)
- [Agentic retrieval migration guide](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-migrate)
- [Stable `2026-04-01` knowledge-source REST operation](https://learn.microsoft.com/rest/api/searchservice/knowledge-sources/create-or-update?view=rest-searchservice-2026-04-01)

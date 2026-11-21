"""
Foundry IQ Building Block Scripts

This package provides reusable components for building Foundry IQ agents:

- search_index_manager: Create and manage Azure AI Search indexes
- document_indexer: Index documents with chunking and embeddings
- knowledge_base_manager: Knowledge sources, knowledge bases and retrieve on GA 2026-10-01 (default)
- knowledge_agent_manager: Legacy 2025-05-01-preview Knowledge Agents (existing deployments only)
- azure_openai_client: Azure OpenAI client for grounded chat completions
"""

from .search_index_manager import SearchIndexManager
from .document_indexer import DocumentIndexer, SAMPLE_POLICIES
from .knowledge_base_manager import (
    KnowledgeBaseManager,
    KnowledgeBaseRetriever,
    kb_mcp_endpoint,
)
from .knowledge_agent_manager import KnowledgeAgentManager, KnowledgeAgentRetriever
from .azure_openai_client import AzureOpenAIClient, PolicyBot

__all__ = [
    "SearchIndexManager",
    "DocumentIndexer",
    "SAMPLE_POLICIES",
    "KnowledgeBaseManager",
    "KnowledgeBaseRetriever",
    "kb_mcp_endpoint",
    "KnowledgeAgentManager",
    "KnowledgeAgentRetriever",
    "AzureOpenAIClient",
    "PolicyBot",
]

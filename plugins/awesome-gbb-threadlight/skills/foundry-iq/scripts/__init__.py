"""
Foundry IQ Building Block Scripts

This package provides reusable components for building Foundry IQ agents:

- search_index_manager: Create and manage Azure AI Search indexes
- document_indexer: Index documents with chunking and embeddings
- knowledge_agent_manager: Create and use Knowledge Agents for agentic retrieval
- azure_openai_client: Azure OpenAI client for grounded chat completions
"""

from .search_index_manager import SearchIndexManager
from .document_indexer import DocumentIndexer, SAMPLE_POLICIES
from .knowledge_agent_manager import KnowledgeAgentManager, KnowledgeAgentRetriever
from .azure_openai_client import AzureOpenAIClient, PolicyBot

__all__ = [
    "SearchIndexManager",
    "DocumentIndexer",
    "SAMPLE_POLICIES",
    "KnowledgeAgentManager",
    "KnowledgeAgentRetriever",
    "AzureOpenAIClient",
    "PolicyBot",
]

"""
Knowledge Agent Manager for Foundry IQ

Creates and manages Azure AI Search Knowledge Agents for agentic retrieval.
Knowledge Agents enable query planning, multi-hop reasoning, and intelligent
answer synthesis.

Auth: DefaultAzureCredential (keyless) by default. Falls back to API key
ONLY when AI_SEARCH_KEY is set, AND the deploy posture explicitly allows
keys (Threadlight pilots are keyless-by-mandate — see SKILL.md § Keyless
RBAC).
"""

import os
import json
from typing import Optional, Dict, Any, List

import requests
from azure.identity import DefaultAzureCredential


def _get_search_headers(api_key: str = None) -> Dict[str, str]:
    """Build headers: API key if provided, else bearer token from DefaultAzureCredential."""
    headers = {"Content-Type": "application/json"}
    key = api_key or os.environ.get("AI_SEARCH_KEY")
    if key:
        headers["api-key"] = key
    else:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://search.azure.com/.default").token
        headers["Authorization"] = f"Bearer {token}"
    return headers


class KnowledgeAgentManager:
    """
    Manages Azure AI Search Knowledge Agents for Foundry IQ agentic retrieval.

    Knowledge Agents provide:
    - Query planning and decomposition
    - Multi-hop reasoning across documents
    - Answer synthesis with citations
    """

    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        api_version: str = "2025-01-01-preview"
    ):
        self.endpoint = endpoint or os.environ.get("AI_SEARCH_ENDPOINT")
        self.api_version = api_version

        if not self.endpoint:
            raise ValueError("AI_SEARCH_ENDPOINT is required")

        self.endpoint = self.endpoint.rstrip("/")
        self.headers = _get_search_headers(api_key)

    def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an HTTP request to the Azure AI Search API."""
        url = f"{self.endpoint}{path}?api-version={self.api_version}"

        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            json=data
        )

        if response.status_code == 204:
            return {"status": "success"}

        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_detail = error_json["error"].get("message", error_detail)
            except:
                pass
            raise Exception(f"API error {response.status_code}: {error_detail}")

        return response.json()

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all Knowledge Agents in the search service."""
        result = self._make_request("GET", "/agents")
        return result.get("value", [])

    def get_agent(self, agent_name: str) -> Dict[str, Any]:
        """Get a Knowledge Agent by name."""
        return self._make_request("GET", f"/agents/{agent_name}")

    def create_agent(
        self,
        agent_name: str,
        index_name: str,
        description: str = None,
        target_indexes: List[str] = None,
        reasoning_effort: str = "medium",
        output_mode: str = "extractiveData"
    ) -> Dict[str, Any]:
        """
        Create a Knowledge Agent for agentic retrieval.

        Args:
            agent_name: Name of the Knowledge Agent
            index_name: Primary search index to use as knowledge source
            description: Optional description of the agent
            target_indexes: Additional indexes to include as knowledge sources
            reasoning_effort: Query planning effort level (minimal, low, medium)
            output_mode: How to return results — wire format is camelCase:
                "extractiveData" or "answerSynthesis" (NOT snake_case)

        Returns:
            Created agent configuration
        """
        # Build knowledge sources list
        knowledge_sources = [
            {
                "name": f"{index_name}-source",
                "kind": "searchIndex",
                "indexName": index_name
            }
        ]

        # Add additional indexes if specified
        if target_indexes:
            for idx_name in target_indexes:
                knowledge_sources.append({
                    "name": f"{idx_name}-source",
                    "kind": "searchIndex",
                    "indexName": idx_name
                })

        # NOTE on wire format (2025-11-01-preview): top-level
        # `retrievalReasoningEffort` and `outputConfiguration.modality` —
        # NOT nested under `configuration`. The legacy /agents/ endpoint
        # at api-version 2025-01-01-preview accepted the `configuration`
        # nesting; the new /knowledgebases/ endpoint at 2025-11-01-preview
        # rejects it. Switch this manager to /knowledgebases/ once your
        # tenant is migrated; until then, callers MUST pin the matching
        # api_version+endpoint pair.
        agent_config = {
            "name": agent_name,
            "description": description or f"Knowledge Agent for {index_name}",
            "knowledgeSources": knowledge_sources,
            "targetIndexes": [index_name] + (target_indexes or []),
            "retrievalReasoningEffort": reasoning_effort,
            "outputConfiguration": {"modality": output_mode},
        }

        return self._make_request("PUT", f"/agents/{agent_name}", agent_config)

    def delete_agent(self, agent_name: str) -> Dict[str, Any]:
        """Delete a Knowledge Agent by name."""
        return self._make_request("DELETE", f"/agents/{agent_name}")

    def create_policy_agent(
        self,
        agent_name: str = "policy-agent",
        index_name: str = "policy-documents"
    ) -> Dict[str, Any]:
        """
        Create a Knowledge Agent optimized for policy document retrieval.

        Args:
            agent_name: Name for the agent
            index_name: Index containing policy documents

        Returns:
            Created agent configuration
        """
        return self.create_agent(
            agent_name=agent_name,
            index_name=index_name,
            description="PolicyBot Knowledge Agent for HR and company policy Q&A",
            reasoning_effort="medium",  # Enable full query planning
            output_mode="extractiveData"  # Let calling agent synthesize
        )


class KnowledgeAgentRetriever:
    """
    Performs agentic retrieval using a Knowledge Agent.

    Uses the KnowledgeAgentRetrievalClient pattern from Azure AI Search SDK.
    """

    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        agent_name: str = "policy-agent",
        api_version: str = "2025-01-01-preview"
    ):
        self.endpoint = endpoint or os.environ.get("AI_SEARCH_ENDPOINT")
        self.agent_name = agent_name
        self.api_version = api_version

        if not self.endpoint:
            raise ValueError("AI_SEARCH_ENDPOINT is required")

        self.endpoint = self.endpoint.rstrip("/")
        self.headers = _get_search_headers(api_key)

        # Conversation history for multi-turn
        self.messages: List[Dict[str, str]] = []

    def clear_history(self):
        """Clear conversation history."""
        self.messages = []

    def retrieve(
        self,
        query: str,
        knowledge_source_name: str = None,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """
        Perform agentic retrieval using the Knowledge Agent.

        Args:
            query: User query
            knowledge_source_name: Optional specific knowledge source
            include_history: Whether to include conversation history

        Returns:
            Retrieval result with extracted content and citations
        """
        # Add user message to history
        self.messages.append({
            "role": "user",
            "content": query
        })

        # Build retrieval request
        messages_for_request = self.messages if include_history else [
            {"role": "user", "content": query}
        ]

        request_body = {
            "messages": [
                {
                    "role": msg["role"],
                    "content": [{"text": msg["content"]}]
                }
                for msg in messages_for_request
                if msg["role"] != "system"
            ]
        }

        # Add knowledge source params if specified
        if knowledge_source_name:
            request_body["knowledgeSourceParams"] = [
                {
                    "knowledgeSourceName": knowledge_source_name,
                    "kind": "searchIndex"
                }
            ]

        url = f"{self.endpoint}/agents/{self.agent_name}/retrieve?api-version={self.api_version}"

        response = requests.post(
            url=url,
            headers=self.headers,
            json=request_body
        )

        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_json = response.json()
                if "error" in error_json:
                    error_detail = error_json["error"].get("message", error_detail)
            except:
                pass
            raise Exception(f"Retrieval error {response.status_code}: {error_detail}")

        result = response.json()

        # Store assistant response in history for multi-turn
        if "content" in result:
            self.messages.append({
                "role": "assistant",
                "content": self._extract_text_content(result["content"])
            })

        return result

    def _extract_text_content(self, content: Any) -> str:
        """Extract text from content array."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, str):
                    texts.append(item)
            return " ".join(texts)
        return str(content)

    def format_citations(self, result: Dict[str, Any]) -> str:
        """
        Format retrieval result with citations.

        Args:
            result: Retrieval result from retrieve()

        Returns:
            Formatted text with citation annotations
        """
        content = result.get("content", [])
        citations = result.get("citations", [])

        # Build citation reference map
        citation_map = {}
        for i, citation in enumerate(citations):
            source = citation.get("sourceFile", citation.get("title", f"Source {i}"))
            citation_map[i] = source

        # Extract and format text with citations
        formatted_parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                citation_refs = item.get("citations", [])

                # Add citation markers
                for ref in citation_refs:
                    if ref in citation_map:
                        text += f" [{citation_map[ref]}]"

                formatted_parts.append(text)

        return " ".join(formatted_parts) if formatted_parts else str(content)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Create Knowledge Agent
    manager = KnowledgeAgentManager()

    # List existing agents
    agents = manager.list_agents()
    print(f"Existing agents: {[a['name'] for a in agents]}")

    # Create policy agent
    try:
        agent = manager.create_policy_agent(
            agent_name="policy-agent",
            index_name="policy-documents"
        )
        print(f"Created agent: {agent['name']}")
    except Exception as e:
        print(f"Error creating agent: {e}")
        # Try to get existing agent
        try:
            agent = manager.get_agent("policy-agent")
            print(f"Using existing agent: {agent['name']}")
        except:
            pass

    # Test retrieval
    retriever = KnowledgeAgentRetriever(agent_name="policy-agent")

    try:
        result = retriever.retrieve("How many PTO days do new employees get?")
        print("\nRetrieval Result:")
        print(retriever.format_citations(result))
    except Exception as e:
        print(f"Retrieval error: {e}")

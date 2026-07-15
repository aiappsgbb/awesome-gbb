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
from typing import Optional, Dict, Any, List

import requests
from azure.identity import DefaultAzureCredential


SUPPORTED_KNOWLEDGE_AGENT_MODELS = {
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
}


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


def _knowledge_agent_path(agent_name: str) -> str:
    """Return the 2025-05 OData path for one knowledge agent."""
    escaped_name = agent_name.replace("'", "''")
    return f"/agents('{escaped_name}')"


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
        api_version: str = "2025-05-01-preview"
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
        return self._make_request("GET", _knowledge_agent_path(agent_name))

    def create_agent(
        self,
        agent_name: str,
        index_name: str,
        model_resource_uri: str,
        model_deployment_id: str,
        model_name: str,
        description: str = None,
        target_indexes: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a Knowledge Agent for agentic retrieval.

        Args:
            agent_name: Name of the Knowledge Agent
            index_name: Primary search index targeted by the agent
            model_resource_uri: Azure OpenAI resource root URI
            model_deployment_id: Azure OpenAI deployment ID
            model_name: Supported model family deployed at the deployment ID
            description: Optional description of the agent
            target_indexes: Additional indexes targeted by the agent

        Returns:
            Created agent configuration
        """
        required_model_values = {
            "model_resource_uri": model_resource_uri,
            "model_deployment_id": model_deployment_id,
            "model_name": model_name,
        }
        missing = [name for name, value in required_model_values.items() if not value]
        if missing:
            raise ValueError(
                "Explicit knowledge agent model configuration is required: "
                + ", ".join(missing)
            )
        if model_name not in SUPPORTED_KNOWLEDGE_AGENT_MODELS:
            supported = ", ".join(sorted(SUPPORTED_KNOWLEDGE_AGENT_MODELS))
            raise ValueError(
                f"Unsupported knowledge agent model '{model_name}'. "
                f"Supported models: {supported}"
            )

        target_index_definitions = [
            {"indexName": name}
            for name in [index_name, *(target_indexes or [])]
        ]
        agent_config = {
            "name": agent_name,
            "description": description or f"Knowledge Agent for {index_name}",
            "models": [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": model_resource_uri,
                        "deploymentId": model_deployment_id,
                        "modelName": model_name,
                    },
                }
            ],
            "targetIndexes": target_index_definitions,
        }

        return self._make_request(
            "PUT",
            _knowledge_agent_path(agent_name),
            agent_config,
        )

    def delete_agent(self, agent_name: str) -> Dict[str, Any]:
        """Delete a Knowledge Agent by name."""
        return self._make_request("DELETE", _knowledge_agent_path(agent_name))

    def create_policy_agent(
        self,
        model_resource_uri: str,
        model_deployment_id: str,
        model_name: str,
        agent_name: str = "policy-agent",
        index_name: str = "policy-documents"
    ) -> Dict[str, Any]:
        """
        Create a Knowledge Agent optimized for policy document retrieval.

        Args:
            model_resource_uri: Azure OpenAI resource root URI
            model_deployment_id: Azure OpenAI deployment ID
            model_name: Supported deployed model family
            agent_name: Name for the agent
            index_name: Index containing policy documents

        Returns:
            Created agent configuration
        """
        return self.create_agent(
            agent_name=agent_name,
            index_name=index_name,
            model_resource_uri=model_resource_uri,
            model_deployment_id=model_deployment_id,
            model_name=model_name,
            description="PolicyBot Knowledge Agent for HR and company policy Q&A",
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
        api_version: str = "2025-05-01-preview"
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
        target_index_name: str = None,
        include_history: bool = True
    ) -> Dict[str, Any]:
        """
        Perform agentic retrieval using the Knowledge Agent.

        Args:
            query: User query
            target_index_name: Optional target index parameters to apply
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
                    "content": [{"type": "text", "text": msg["content"]}]
                }
                for msg in messages_for_request
                if msg["role"] != "system"
            ]
        }

        if target_index_name:
            request_body["targetIndexParams"] = [
                {"indexName": target_index_name}
            ]

        url = (
            f"{self.endpoint}{_knowledge_agent_path(self.agent_name)}"
            f"/retrieve?api-version={self.api_version}"
        )

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

        for message in reversed(result.get("response", [])):
            if message.get("role") == "assistant":
                self.messages.append({
                    "role": "assistant",
                    "content": self._extract_text_content(message.get("content", [])),
                })
                break

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
        formatted_parts = [
            self._extract_text_content(message.get("content", []))
            for message in result.get("response", [])
            if message.get("role") == "assistant"
        ]
        source_keys = [
            reference.get("docKey")
            for reference in result.get("references", [])
            if reference.get("docKey")
        ]
        if source_keys:
            formatted_parts.append(
                "Sources: " + ", ".join(f"[{source}]" for source in source_keys)
            )
        return "\n\n".join(formatted_parts)


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
            model_resource_uri=os.environ["KNOWLEDGE_AGENT_MODEL_RESOURCE_URI"],
            model_deployment_id=os.environ[
                "KNOWLEDGE_AGENT_MODEL_DEPLOYMENT_ID"
            ],
            model_name=os.environ["KNOWLEDGE_AGENT_MODEL_NAME"],
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

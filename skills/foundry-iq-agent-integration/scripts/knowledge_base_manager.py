"""
Knowledge Base Manager for Foundry IQ (default path)

Creates `searchIndex` knowledge sources and knowledge bases, and retrieves
through the GA Search REST API `2026-10-01` (`/knowledgesources`,
`/knowledgebases`). Model-backed planning (`low` / `medium`) needs an Azure
OpenAI model on the knowledge base; `minimal` does not.

The first-generation `2025-05-01-preview` Knowledge Agent helper is kept in
`knowledge_agent_manager.py` for existing deployments only.

Auth: DefaultAzureCredential (keyless) by default. An admin or query key is
used only when AI_SEARCH_KEY is set.
"""

import os
from typing import Any, Dict, List, Optional

import requests
from azure.identity import DefaultAzureCredential

GA_API_VERSION = "2026-10-01"
KB_MCP_API_VERSION = "2026-11-01-preview"
GA_REASONING_EFFORTS = {"minimal", "low", "medium"}


def _get_search_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    """Build headers: API key if provided, else bearer token from DefaultAzureCredential."""
    headers = {"Content-Type": "application/json"}
    key = api_key or os.environ.get("AI_SEARCH_KEY")
    if key:
        headers["api-key"] = key
    else:
        token = DefaultAzureCredential().get_token(
            "https://search.azure.com/.default"
        ).token
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _check(response: requests.Response) -> Dict[str, Any]:
    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("error", {}).get("message", detail)
        except ValueError:
            pass
        raise RuntimeError(f"Search error {response.status_code}: {detail}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def kb_mcp_endpoint(endpoint: str, knowledge_base_name: str) -> str:
    """Return the KB MCP URL that Foundry Agent Service connections target."""
    return (
        f"{endpoint.rstrip('/')}/knowledgebases/{knowledge_base_name}/mcp"
        f"?api-version={KB_MCP_API_VERSION}"
    )


class KnowledgeBaseManager:
    """Creates and deletes knowledge sources and knowledge bases on 2026-10-01."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_version: str = GA_API_VERSION,
    ):
        self.endpoint = (endpoint or os.environ.get("AI_SEARCH_ENDPOINT") or "").rstrip("/")
        if not self.endpoint:
            raise ValueError("AI_SEARCH_ENDPOINT is required")
        self.api_version = api_version
        self.headers = _get_search_headers(api_key)

    def _url(self, path: str) -> str:
        return f"{self.endpoint}/{path}?api-version={self.api_version}"

    def _put(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return _check(
            requests.put(
                self._url(path),
                headers={**self.headers, "Prefer": "return=representation"},
                json=body,
                timeout=90,
            )
        )

    def create_search_index_knowledge_source(
        self,
        name: str,
        index_name: str,
        semantic_configuration: str = "default",
        source_data_fields: Optional[List[str]] = None,
        search_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create or update a `searchIndex` knowledge source over an existing index."""
        parameters: Dict[str, Any] = {
            "searchIndexName": index_name,
            "semanticConfigurationName": semantic_configuration,
        }
        if source_data_fields:
            parameters["sourceDataFields"] = [{"name": f} for f in source_data_fields]
        if search_fields:
            parameters["searchFields"] = [{"name": f} for f in search_fields]
        return self._put(
            f"knowledgesources('{name}')",
            {"name": name, "kind": "searchIndex", "searchIndexParameters": parameters},
        )

    def create_knowledge_base(
        self,
        name: str,
        knowledge_source_names: List[str],
        reasoning_effort: str = "low",
        model_resource_uri: Optional[str] = None,
        model_deployment_id: Optional[str] = None,
        model_name: Optional[str] = None,
        output_mode: str = "extractiveData",
    ) -> Dict[str, Any]:
        """Create or update a knowledge base.

        `low` and `medium` require the model triple; the Search service's
        managed identity calls it. `auto` is preview-only and rejected here.
        """
        if reasoning_effort not in GA_REASONING_EFFORTS:
            raise ValueError(
                f"{reasoning_effort!r} is not a GA effort on {GA_API_VERSION}; "
                "use minimal, low, or medium"
            )
        model = (model_resource_uri, model_deployment_id, model_name)
        if reasoning_effort != "minimal" and not all(model):
            raise ValueError(f"{reasoning_effort} effort requires a model")
        body: Dict[str, Any] = {
            "name": name,
            "knowledgeSources": [{"name": n} for n in knowledge_source_names],
            "retrievalReasoningEffort": {"kind": reasoning_effort},
            "outputMode": output_mode,
        }
        if all(model):
            body["models"] = [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": model_resource_uri,
                        "deploymentId": model_deployment_id,
                        "modelName": model_name,
                    },
                }
            ]
        return self._put(f"knowledgebases('{name}')", body)

    def delete_knowledge_base(self, name: str) -> None:
        _check(requests.delete(self._url(f"knowledgebases('{name}')"), headers=self.headers, timeout=90))

    def delete_knowledge_source(self, name: str) -> None:
        _check(requests.delete(self._url(f"knowledgesources('{name}')"), headers=self.headers, timeout=90))


class KnowledgeBaseRetriever:
    """Retrieves from a knowledge base on 2026-10-01 with multi-turn history."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        knowledge_base_name: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        api_version: str = GA_API_VERSION,
    ):
        self.endpoint = (endpoint or os.environ.get("AI_SEARCH_ENDPOINT") or "").rstrip("/")
        if not self.endpoint:
            raise ValueError("AI_SEARCH_ENDPOINT is required")
        reasoning_effort = reasoning_effort or os.environ.get(
            "KNOWLEDGE_BASE_REASONING_EFFORT", "low"
        )
        self.knowledge_base_name = knowledge_base_name or os.environ.get(
            "KNOWLEDGE_BASE_NAME", "policy-kb"
        )
        if reasoning_effort not in GA_REASONING_EFFORTS:
            raise ValueError(f"{reasoning_effort!r} is not a GA reasoning effort")
        self.reasoning_effort = reasoning_effort
        self.api_version = api_version
        self.headers = _get_search_headers(api_key)
        self.messages: List[Dict[str, str]] = []

    def clear_history(self) -> None:
        self.messages = []

    def build_request(self, query: str, include_history: bool = True) -> Dict[str, Any]:
        """Build a retrieve body.

        `minimal` rejects `messages`, so it sends one semantic intent; `low`
        and `medium` send the conversation as messages.
        """
        body: Dict[str, Any] = {
            "retrievalReasoningEffort": {"kind": self.reasoning_effort},
            "outputMode": "extractiveData",
            "includeActivity": True,
        }
        if self.reasoning_effort == "minimal":
            body["intents"] = [{"type": "semantic", "search": query}]
            return body
        history = self.messages if include_history else []
        turns = [*history, {"role": "user", "content": query}]
        body["messages"] = [
            {"role": t["role"], "content": [{"type": "text", "text": t["content"]}]}
            for t in turns
        ]
        return body

    def retrieve(
        self,
        query: str,
        include_history: bool = True,
        query_source_authorization: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve grounding data.

        Pass the end user's Search token as `query_source_authorization` for
        permission-trimmed sources; without it only public content returns.
        """
        headers = dict(self.headers)
        if query_source_authorization:
            headers["x-ms-query-source-authorization"] = query_source_authorization
        result = _check(
            requests.post(
                f"{self.endpoint}/knowledgebases('{self.knowledge_base_name}')"
                f"/retrieve?api-version={self.api_version}",
                headers=headers,
                json=self.build_request(query, include_history),
                timeout=120,
            )
        )
        self.messages.append({"role": "user", "content": query})
        text = self._extract_text_content(
            [c for m in result.get("response", []) for c in m.get("content", [])]
        )
        if text:
            self.messages.append({"role": "assistant", "content": text})
        return result

    def _extract_text_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                item["text"] if isinstance(item, dict) else str(item)
                for item in content
                if isinstance(item, str) or (isinstance(item, dict) and "text" in item)
            )
        return str(content)

    def format_citations(self, result: Dict[str, Any]) -> str:
        parts = [
            self._extract_text_content(m.get("content", []))
            for m in result.get("response", [])
        ]
        keys = [r.get("docKey") for r in result.get("references", []) if r.get("docKey")]
        if keys:
            parts.append("Sources: " + ", ".join(f"[{k}]" for k in dict.fromkeys(keys)))
        return "\n\n".join(p for p in parts if p)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    retriever = KnowledgeBaseRetriever()
    print(retriever.format_citations(retriever.retrieve("What is the PTO policy?")))

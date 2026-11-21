"""Execute the Foundry IQ GA knowledge base + Agent Service CI smoke.

This fixture is invoked by `consumer_prompt.md`. It discovers the standing
Search service by tag and the configured Foundry project, then:

1. creates a UUID-scoped index, uploads known-answer documents, and creates a
   `searchIndex` knowledge source and a `low`-effort knowledge base through
   the GA `2026-10-01` Search REST API;
2. runs a `low` retrieve and checks model query planning plus the answer;
3. creates a `RemoteTool` project connection (`ProjectManagedIdentity`) to
   the KB MCP endpoint (`2026-11-01-preview`) and a prompt agent whose `mcp`
   tool allows only `knowledge_base_retrieve`;
4. invokes the agent and checks the MCP call and answer;
5. deletes every object it created. The Search service is never touched.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

import requests
from azure.identity import DefaultAzureCredential

SEARCH_API = "2026-10-01"
MCP_API = "2026-11-01-preview"
CONNECTION_API = "2025-10-01-preview"
EVIDENCE_PATH = "/tmp/foundry-iq-agent-integration-smoke-evidence"
ARM = "https://management.azure.com"
SEARCH_DELETE_OK = (204, 404)
CONTROL_DELETE_OK = (200, 202, 204, 404)
DELETE_OK = {
    "agent": CONTROL_DELETE_OK,
    "connection": CONTROL_DELETE_OK,
    "knowledge_base": SEARCH_DELETE_OK,
    "knowledge_source": SEARCH_DELETE_OK,
    "index": SEARCH_DELETE_OK,
}


def _graph(token: str, query: str) -> list[dict]:
    response = requests.post(
        f"{ARM}/providers/Microsoft.ResourceGraph/resources?api-version=2024-04-01",
        headers={"Authorization": f"Bearer {token}"},
        json={"subscriptions": [os.environ["AZURE_SUBSCRIPTION_ID"]], "query": query},
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["data"]


def _retry(call, accept, attempts: int, delay: int, label: str):
    response = None
    for _ in range(attempts):
        response = call()
        if accept(response):
            return response
        time.sleep(delay)
    raise RuntimeError(
        f"{label}: HTTP {response.status_code} {response.text[:400]}"
    )


def main() -> int:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    arm_token = credential.get_token(f"{ARM}/.default").token
    arm_headers = {"Authorization": f"Bearer {arm_token}"}

    services = _graph(
        arm_token,
        """
Resources
| where type =~ 'microsoft.search/searchservices'
| where tags.workload =~ 'foundry-iq'
| where tags.lifecycle =~ 'persistent-ci'
| project name
""",
    )
    assert len(services) == 1, f"expected one tagged Search service: {services}"
    endpoint = f"https://{services[0]['name']}.search.windows.net"

    project_endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/")
    match = re.fullmatch(
        r"https://([^.]+)\.services\.ai\.azure\.com/api/projects/([^/]+)",
        project_endpoint,
    )
    assert match, "FOUNDRY_PROJECT_ENDPOINT is not a Foundry project endpoint"
    account_name, project_name = match.groups()
    accounts = _graph(
        arm_token,
        "Resources | where type =~ 'microsoft.cognitiveservices/accounts'"
        f" | where name =~ '{account_name}' | project id",
    )
    assert len(accounts) == 1, f"expected one Foundry account: {accounts}"
    account_id = accounts[0]["id"]
    project_id = f"{account_id}/projects/{project_name}"
    deployment = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT", "gpt-5.4-mini")
    response = requests.get(
        f"{ARM}{account_id}/deployments/{deployment}?api-version=2025-06-01",
        headers=arm_headers,
        timeout=90,
    )
    response.raise_for_status()
    model_name = response.json()["properties"]["model"]["name"]

    suffix = uuid.uuid4().hex[:8]
    index_name = f"ci-iq-{suffix}"
    source_name = f"{index_name}-ks"
    kb_name = f"{index_name}-kb"
    connection_name = f"ci-iq-kb-mcp-{suffix}"
    agent_name = f"ci-iq-agent-{suffix}"
    answer_code = f"HERON-{suffix.upper()}"
    question = "What is the travel approval code in the Contoso travel policy?"

    search_token = credential.get_token("https://search.azure.com/.default").token
    search_headers = {
        "Authorization": f"Bearer {search_token}",
        "Content-Type": "application/json",
    }
    put_headers = {**search_headers, "Prefer": "return=representation"}
    ai_token = credential.get_token("https://ai.azure.com/.default").token
    ai_headers = {
        "Authorization": f"Bearer {ai_token}",
        "Content-Type": "application/json",
    }

    def surl(path: str, api: str = SEARCH_API) -> str:
        return f"{endpoint}/{path}?api-version={api}"

    mcp_url = surl(f"knowledgebases/{kb_name}/mcp", MCP_API)
    connection_url = (
        f"{ARM}{project_id}/connections/{connection_name}"
        f"?api-version={CONNECTION_API}"
    )
    agent_url = f"{project_endpoint}/agents/{agent_name}?api-version=v1"

    evidence: dict[str, object] = {
        "search_api_version": SEARCH_API,
        "mcp_api_version": MCP_API,
        "model_name": model_name,
    }
    created: list[tuple[str, str, dict]] = []
    hard_success = False
    try:
        _retry(
            lambda: requests.get(surl("indexes"), headers=search_headers, timeout=90),
            lambda r: r.status_code == 200,
            30,
            10,
            "Search data-plane roles did not propagate",
        )

        index_body = {
            "name": index_name,
            "fields": [
                {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
                {"name": "title", "type": "Edm.String", "searchable": True},
                {"name": "content", "type": "Edm.String", "searchable": True},
            ],
            "semantic": {
                "defaultConfiguration": "default",
                "configurations": [
                    {
                        "name": "default",
                        "prioritizedFields": {
                            "titleField": {"fieldName": "title"},
                            "prioritizedContentFields": [{"fieldName": "content"}],
                            "prioritizedKeywordsFields": [],
                        },
                    }
                ],
            },
        }
        response = requests.put(
            surl(f"indexes('{index_name}')"), headers=put_headers, json=index_body, timeout=90
        )
        assert response.status_code == 201, response.text
        created.append(("index", surl(f"indexes('{index_name}')"), search_headers))
        evidence["index_status"] = response.status_code

        documents = [
            {
                "@search.action": "upload",
                "id": "travel",
                "title": "Contoso travel policy",
                "content": (
                    "Every business trip must be approved before booking. "
                    f"The travel approval code is {answer_code}. "
                    "Economy class is required for flights under six hours."
                ),
            },
            {
                "@search.action": "upload",
                "id": "expenses",
                "title": "Contoso expense policy",
                "content": "Meals are reimbursed up to 50 EUR per day with receipts.",
            },
        ]
        response = requests.post(
            surl(f"indexes('{index_name}')/docs/index"),
            headers=search_headers,
            json={"value": documents},
            timeout=90,
        )
        assert response.status_code == 200, response.text
        _retry(
            lambda: requests.get(
                surl(f"indexes('{index_name}')/docs/$count"),
                headers=search_headers,
                timeout=90,
            ),
            lambda r: r.status_code == 200 and r.text.strip().lstrip("\ufeff") == "2",
            30,
            2,
            "uploaded documents not visible",
        )

        source_body = {
            "name": source_name,
            "kind": "searchIndex",
            "description": "Temporary CI knowledge source.",
            "searchIndexParameters": {
                "searchIndexName": index_name,
                "semanticConfigurationName": "default",
                "sourceDataFields": [{"name": "title"}, {"name": "content"}],
                "searchFields": [{"name": "content"}],
            },
        }
        response = requests.put(
            surl(f"knowledgesources('{source_name}')"),
            headers=put_headers,
            json=source_body,
            timeout=90,
        )
        assert response.status_code == 201, response.text
        created.insert(
            0, ("knowledge source", surl(f"knowledgesources('{source_name}')"), search_headers)
        )
        evidence["knowledge_source_status"] = response.status_code

        kb_body = {
            "name": kb_name,
            "description": "Temporary CI knowledge base with model query planning.",
            "knowledgeSources": [{"name": source_name}],
            "models": [
                {
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": f"https://{account_name}.openai.azure.com",
                        "deploymentId": deployment,
                        "modelName": model_name,
                    },
                }
            ],
            "retrievalReasoningEffort": {"kind": "low"},
            "outputMode": "extractiveData",
        }
        response = requests.put(
            surl(f"knowledgebases('{kb_name}')"), headers=put_headers, json=kb_body, timeout=90
        )
        assert response.status_code == 201, response.text
        created.insert(0, ("knowledge base", surl(f"knowledgebases('{kb_name}')"), search_headers))
        evidence["knowledge_base_status"] = response.status_code

        retrieve_body = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ],
            "retrievalReasoningEffort": {"kind": "low"},
            "outputMode": "extractiveData",
            "includeActivity": True,
            "knowledgeSourceParams": [
                {
                    "knowledgeSourceName": source_name,
                    "kind": "searchIndex",
                    "alwaysQuerySource": True,
                    "failOnError": True,
                    "includeReferences": True,
                    "includeReferenceSourceData": True,
                }
            ],
        }
        # The Search identity's model role can still be propagating: retry
        # 206/502 (model or source activity error) for up to five minutes.
        response = _retry(
            lambda: requests.post(
                surl(f"knowledgebases('{kb_name}')/retrieve"),
                headers=search_headers,
                json=retrieve_body,
                timeout=120,
            ),
            lambda r: r.status_code == 200,
            20,
            15,
            "low-effort retrieve failed",
        )
        retrieved = response.json()
        activity_types = sorted({a.get("type", "") for a in retrieved.get("activity", [])})
        assert "modelQueryPlanning" in activity_types, activity_types
        assert answer_code in json.dumps(retrieved), "answer code not retrieved"
        evidence["retrieve_status"] = response.status_code
        evidence["retrieve_activity_types"] = activity_types

        response = requests.put(
            connection_url,
            headers={**arm_headers, "Content-Type": "application/json"},
            json={
                "name": connection_name,
                "type": "Microsoft.MachineLearningServices/workspaces/connections",
                "properties": {
                    "authType": "ProjectManagedIdentity",
                    "category": "RemoteTool",
                    "target": mcp_url,
                    "isSharedToAll": True,
                    "audience": "https://search.azure.com/",
                    "metadata": {"ApiType": "Azure"},
                },
            },
            timeout=90,
        )
        assert response.status_code in (200, 201), response.text
        created.insert(0, ("connection", connection_url, arm_headers))
        evidence["connection_status"] = response.status_code

        response = requests.post(
            f"{project_endpoint}/agents?api-version=v1",
            headers=ai_headers,
            json={
                "name": agent_name,
                "definition": {
                    "kind": "prompt",
                    "model": deployment,
                    "instructions": (
                        "You must call the knowledge base tool for every question "
                        "and answer only from its results. If the knowledge base "
                        "does not contain the answer, reply \"I don't know\"."
                    ),
                    "tools": [
                        {
                            "type": "mcp",
                            "server_label": "knowledge-base",
                            "server_url": mcp_url,
                            "require_approval": "never",
                            "allowed_tools": ["knowledge_base_retrieve"],
                            "project_connection_id": connection_name,
                        }
                    ],
                },
            },
            timeout=90,
        )
        assert response.status_code in (200, 201), response.text
        created.insert(0, ("agent", agent_url, ai_headers))
        evidence["agent_status"] = response.status_code

        # No api-version query parameter on the /openai/v1/ path.
        response = _retry(
            lambda: requests.post(
                f"{project_endpoint}/openai/v1/responses",
                headers=ai_headers,
                json={
                    "input": question,
                    "agent_reference": {"type": "agent_reference", "name": agent_name},
                },
                timeout=180,
            ),
            lambda r: r.status_code == 200 and answer_code in r.text,
            6,
            20,
            "agent did not answer through the KB MCP tool",
        )
        output = response.json().get("output", [])
        mcp_calls = [
            item for item in output
            if item.get("type") == "mcp_call" and item.get("name") == "knowledge_base_retrieve"
        ]
        assert mcp_calls, [item.get("type") for item in output]
        assert not any(call.get("error") for call in mcp_calls), mcp_calls
        evidence["agent_mcp_tool"] = mcp_calls[0]["name"]
        evidence["agent_answer_has_code"] = answer_code in (
            response.json().get("output_text") or json.dumps(output)
        )
        hard_success = True
    finally:
        cleanup_notes: list[str] = []
        for label, url, headers in created:
            key = label.replace(" ", "_")
            try:
                response = requests.delete(url, headers=headers, timeout=90)
                evidence[f"{key}_delete_status"] = response.status_code
                if response.status_code not in DELETE_OK[key]:
                    cleanup_notes.append(f"{label} cleanup HTTP {response.status_code}")
            except Exception as exc:  # noqa: BLE001 - recorded, then graded
                evidence[f"{key}_delete_status"] = None
                cleanup_notes.append(f"{label} cleanup {type(exc).__name__}")
        credential.close()
        if cleanup_notes:
            print("NOTE: data-plane teardown: " + "; ".join(cleanup_notes))

    if not hard_success:
        return 1
    with open(EVIDENCE_PATH, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(evidence, sort_keys=True))
    if any(
        evidence.get(f"{key}_delete_status") not in allowed
        for key, allowed in DELETE_OK.items()
    ):
        return 1
    print("foundry-iq-ga-kb-agent-ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Execute the Foundry IQ stable knowledge-source CI smoke.

This fixture is invoked by `consumer_prompt.md`. It discovers the standing
Search service by tag, creates UUID-scoped data-plane objects through the
stable 2026-04-01 REST API, records evidence, and removes those objects.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid

import requests
from azure.identity import DefaultAzureCredential

API_VERSION = "2026-04-01"
EVIDENCE_PATH = "/tmp/foundry-iq-smoke-evidence"


def main() -> int:
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )
    management_token = credential.get_token(
        "https://management.azure.com/.default"
    ).token
    resource_graph = requests.post(
        "https://management.azure.com/providers/Microsoft.ResourceGraph/resources"
        "?api-version=2024-04-01",
        headers={
            "Authorization": f"Bearer {management_token}",
            "Content-Type": "application/json",
        },
        json={
            "subscriptions": [os.environ["AZURE_SUBSCRIPTION_ID"]],
            "query": """
Resources
| where type =~ 'microsoft.search/searchservices'
| where tags.workload =~ 'foundry-iq'
| where tags.lifecycle =~ 'persistent-ci'
| project name, resourceGroup, id
""",
        },
        timeout=90,
    )
    resource_graph.raise_for_status()
    matches = resource_graph.json()["data"]
    assert len(matches) == 1, (
        f"expected one tagged Foundry IQ Search service: {matches}"
    )
    endpoint = f"https://{matches[0]['name']}.search.windows.net"

    suffix = uuid.uuid4().hex[:8]
    index_name = f"ci-iq-{suffix}"
    source_name = f"{index_name}-ks"
    index_url = (
        f"{endpoint}/indexes('{index_name}')?api-version={API_VERSION}"
    )
    source_url = (
        f"{endpoint}/knowledgesources('{source_name}')"
        f"?api-version={API_VERSION}"
    )
    token = credential.get_token("https://search.azure.com/.default").token
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    put_headers = {**headers, "Prefer": "return=representation"}

    index_body = {
        "name": index_name,
        "description": "Temporary CI index for the stable Foundry IQ REST smoke.",
        "fields": [
            {
                "name": "id",
                "type": "Edm.String",
                "key": True,
                "filterable": True,
            },
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
    source_body = {
        "name": source_name,
        "kind": "searchIndex",
        "description": "Temporary CI knowledge source proving the stable GA kind.",
        "searchIndexParameters": {
            "searchIndexName": index_name,
            "semanticConfigurationName": "default",
            "sourceDataFields": [{"name": "title"}],
            "searchFields": [{"name": "content"}],
        },
    }

    hard_success = False
    cleanup_notes: list[str] = []
    cleanup_statuses: dict[str, object] = {
        "knowledge_source_delete_status": None,
        "index_delete_status": None,
    }
    evidence: dict[str, object] = {}
    try:
        for attempt in range(30):
            response = requests.get(
                f"{endpoint}/indexes?api-version={API_VERSION}",
                headers=headers,
                timeout=90,
            )
            if response.status_code == 200:
                break
            if response.status_code != 403:
                response.raise_for_status()
            if attempt == 29:
                raise RuntimeError(
                    "Search Service Contributor did not propagate within 5 minutes"
                )
            time.sleep(10)

        response = requests.put(
            index_url,
            headers=put_headers,
            json=index_body,
            timeout=90,
        )
        assert response.status_code == 201, response.text
        index_status = response.status_code

        response = requests.put(
            source_url,
            headers=put_headers,
            json=source_body,
            timeout=90,
        )
        assert response.status_code == 201, response.text
        create_status = response.status_code

        response = requests.get(source_url, headers=headers, timeout=90)
        assert response.status_code == 200, response.text
        returned = response.json()
        assert returned["kind"] == "searchIndex", returned
        assert (
            returned["searchIndexParameters"]["searchIndexName"] == index_name
        ), returned

        evidence = {
            "api_version": API_VERSION,
            "exercised_ga_kind": returned["kind"],
            "index_name": index_name,
            "knowledge_source_name": source_name,
            "index_status": index_status,
            "knowledge_source_status": create_status,
            "get_status": response.status_code,
        }
        hard_success = True
    finally:
        for label, status_key, url in (
            (
                "knowledge source",
                "knowledge_source_delete_status",
                source_url,
            ),
            ("index", "index_delete_status", index_url),
        ):
            try:
                response = requests.delete(url, headers=headers, timeout=90)
                cleanup_statuses[status_key] = response.status_code
                if response.status_code not in (204, 404):
                    cleanup_notes.append(
                        f"{label} cleanup HTTP {response.status_code}"
                    )
            except Exception as exc:
                cleanup_notes.append(
                    f"{label} cleanup {type(exc).__name__}"
                )
        credential.close()

    if cleanup_notes:
        print(
            "NOTE: best-effort data-plane teardown: "
            + "; ".join(cleanup_notes)
        )
    if not hard_success:
        return 1
    evidence.update(cleanup_statuses)
    with open(EVIDENCE_PATH, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(evidence, sort_keys=True))
    if any(status not in (204, 404) for status in cleanup_statuses.values()):
        return 1
    print("foundry-iq-ga-searchIndex-ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())

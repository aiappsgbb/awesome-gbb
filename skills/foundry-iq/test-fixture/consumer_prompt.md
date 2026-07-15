# Goal — `foundry-iq` stable GA knowledge-source smoke

Prove the narrow Foundry IQ GA programmatic slice against the standing CI
Azure AI Search service. Create a UUID-suffixed search index, create and
read a `searchIndex` knowledge source through REST API `2026-04-01`, verify
the returned kind, and clean up only the two data-plane objects you created.

The Search service was provisioned separately through the checked-in
`azure.yaml` + Bicep project. This execution fixture must not provision or
delete infrastructure. Never delete or recreate the Search service, its
resource group, locks, identities, policies, or role assignments.

This is an execution smoke, not a catalog inspection. Run every Bash block
in order. Do not inspect repo files, rebuild docs, run validators, or invoke
`copilot` recursively. You are already the running Copilot CLI process; a
nested invocation has no GitHub authentication and can clobber the workflow
transcript. The outer workflow already captures stdout.

---

## Step -1 — Acknowledge the skill contract

Run this first so the post-hoc audit records the skill path without loading
the 1,000-line document into model context:

```bash
echo "Loading skill contract: skills/foundry-iq/SKILL.md (version 1.4.x)"
echo "Fixture path: skills/foundry-iq/test-fixture/consumer_prompt.md"
```

---

## Step 0 — Show auth context and gate only on required variables

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
```

If any variable is empty, write the FAIL marker from Step 3 with reason
`auth context missing: <var-name>` and stop. This fixture doesn't use `az`
or `azd`; Resource Graph discovery and the real Search data-plane call are
the authentication gates.

The workflow already provides `python3` and `pip`. Do not hunt for or install
OS-level tooling.

---

## Step 1 — Install bounded Python dependencies

```bash
python3 -m pip install --quiet \
  "azure-identity~=1.25.0" \
  "requests~=2.32.0"
```

If installation fails, write the FAIL marker with reason
`dependency install failed` and stop.

---

## Step 2 — Execute the stable REST operation

Run this script verbatim. It uses Entra authentication, never reads an
admin key, and sends `api-version=2026-04-01`. The four GA wire kinds are
`searchIndex`, `azureBlob`, `indexedOneLake`, and `web`. Azure SQL, direct
file upload, indexed/remote SharePoint, Fabric Data Agent, Fabric Ontology,
MCP server, and Work IQ are preview-only; this smoke must not create or
label any of them as GA.

```bash
python3 <<'PY'
import json
import os
import sys
import time
import uuid

import requests
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
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
assert len(matches) == 1, f"expected one tagged Foundry IQ Search service: {matches}"
endpoint = f"https://{matches[0]['name']}.search.windows.net"
api_version = "2026-04-01"
suffix = uuid.uuid4().hex[:8]
index_name = f"ci-iq-{suffix}"
source_name = f"{index_name}-ks"
index_url = f"{endpoint}/indexes('{index_name}')?api-version={api_version}"
source_url = f"{endpoint}/knowledgesources('{source_name}')?api-version={api_version}"
token = credential.get_token("https://search.azure.com/.default").token
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}
put_headers = {
    **headers,
    "Prefer": "return=representation",
}

index_body = {
    "name": index_name,
    "description": "Temporary CI index for the stable Foundry IQ REST smoke.",
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
cleanup_notes = []
try:
    for attempt in range(30):
        response = requests.get(
            f"{endpoint}/indexes?api-version={api_version}",
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

    response = requests.put(index_url, headers=put_headers, json=index_body, timeout=90)
    assert response.status_code == 201, response.text
    index_status = response.status_code

    response = requests.put(source_url, headers=put_headers, json=source_body, timeout=90)
    assert response.status_code == 201, response.text
    create_status = response.status_code

    response = requests.get(source_url, headers=headers, timeout=90)
    assert response.status_code == 200, response.text
    returned = response.json()
    assert returned["kind"] == "searchIndex", returned
    assert returned["searchIndexParameters"]["searchIndexName"] == index_name, returned

    evidence = {
        "api_version": api_version,
        "ga_kind": returned["kind"],
        "index_name": index_name,
        "knowledge_source_name": source_name,
        "index_status": index_status,
        "knowledge_source_status": create_status,
        "get_status": response.status_code,
        "preview_kinds_treated_as_ga": [],
    }
    with open("/tmp/foundry-iq-smoke-evidence", "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(evidence, sort_keys=True))
    hard_success = True
finally:
    for label, url in (("knowledge source", source_url), ("index", index_url)):
        try:
            response = requests.delete(url, headers=headers, timeout=90)
            if response.status_code not in (204, 404):
                cleanup_notes.append(f"{label} cleanup HTTP {response.status_code}")
        except Exception as exc:
            cleanup_notes.append(f"{label} cleanup {type(exc).__name__}")
    credential.close()

if cleanup_notes:
    print("NOTE: best-effort data-plane teardown: " + "; ".join(cleanup_notes))
if not hard_success:
    sys.exit(1)
print("foundry-iq-ga-searchIndex-ok")
PY
```

Success requires exit code 0, output containing
`foundry-iq-ga-searchIndex-ok`, and evidence showing:

- `api_version` is exactly `2026-04-01`
- `ga_kind` is exactly `searchIndex`
- `preview_kinds_treated_as_ga` is an empty list
- the index PUT, knowledge-source PUT, and knowledge-source GET succeeded

If the script fails, write the FAIL marker with the exception class or HTTP
status and stop. A cleanup warning after all assertions is a transcript NOTE,
not a hard failure; both objects are UUID-suffixed and their names remain in
the uploaded evidence for maintenance cleanup.

---

## Step 3 — Write the deterministic result marker

After Step 2 succeeds, your final action is this Bash tool call:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-iq-smoke-result
```

On any earlier failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-iq-smoke-result
```

The marker file is authoritative. Do not emit the marker token anywhere
else in assistant prose.

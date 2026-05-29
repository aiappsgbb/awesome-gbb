---
name: foundry-memory
description: >
  Use Azure AI Foundry Memory Store for persistent agent memory across sessions:
  user profiles, chat summaries, semantic memory retrieval, hosted-agent memory
  tool wiring, scope isolation via x-memory-user-id / {{$userId}}, and
  azure-ai-projects patterns across Python, C#, and TypeScript. USE FOR:
  foundry memory, memory store, user profile, chat summary, cross-session
  memory, persistent memory, agent memory, remember user preferences,
  conversation history, semantic memory retrieval, azure-ai-projects memory,
  replace Mem0. DO NOT USE FOR: RAG/knowledge retrieval (use foundry-iq),
  document grounding, vector search over documents.
metadata:
  version: "1.0.1"
---

# Foundry Memory

Foundry Memory Store is the native Azure AI Foundry feature for **persistent
agent memory across sessions**. It gives a Foundry agent a managed long-term
memory layer instead of requiring an external sidecar such as Mem0.

It stores two memory types:

1. **User profiles** — durable facts and preferences about a user (for example,
   preferred units, UI settings, loyalty program, or role context).
2. **Chat summaries** — distilled cross-session summaries of prior threads so a
   later conversation can resume without replaying the full transcript.

Use it when the memory is **user-scoped, conversational, and agent-native**.
If the problem is document grounding or enterprise RAG over files, use
[`foundry-iq`](../foundry-iq/) instead.

---

## 1. Overview

Foundry Memory is a **managed long-term memory subsystem** inside Foundry Agent
Service. The service extracts salient facts from conversations, consolidates
duplicates, and makes the results searchable for later turns or later sessions.

Key platform facts:

- **SDK floor:** `azure-ai-projects>=2.0.0`
- **Python entry point:** `project_client.beta.memory_stores`
- **REST API version:** `2025-11-15-preview`
- **Native replacement for older Mem0 patterns:** prefer Foundry Memory when
  the workload already lives in Foundry Agent Service
- **Agent integration:** attach the `memory_search_preview` tool so the agent
  can read and write memory automatically during conversations

---

## 2. Prerequisites

Before you create a memory store, make sure the project has:

- A Foundry project endpoint such as
  `https://<project>.services.ai.azure.com/api/projects/<project-name>`
- A compatible **chat model deployment** for extraction / consolidation
- A compatible **embedding model deployment** for semantic retrieval
- `azure-ai-projects>=2.0.0` plus `azure-identity` for Python
- Preview API access for `2025-11-15-preview`

### Embedding model requirement

Deploy **`text-embedding-3-small`** or **`text-embedding-3-large`** in the same
project (or via a connected resource). Memory retrieval uses that embedding
model to index and recall relevant memories.

### Supported regions (May 2026 field audit)

`australiaeast`, `canadacentral`, `centralus`, `eastus`, `eastus2`,
`francecentral`, `germanywestcentral`, `japaneast`, `koreacentral`,
`northcentralus`, `norwayeast`, `polandcentral`, `southcentralus`,
`swedencentral`, `switzerlandnorth`, `uaenorth`, `westeurope`, `westus3`

If your project is outside those regions, treat memory as unavailable until the
preview footprint expands.

---

## 3. Creating a memory store

Create **one memory store per agent or per clear isolation boundary**. Keep the
store focused so profile extraction and summary retrieval stay relevant.

### Python

```python
import os
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    MemoryStoreDefaultDefinition,
    MemoryStoreDefaultOptions,
)
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

definition = MemoryStoreDefaultDefinition(
    chat_model=os.environ["MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME"],
    embedding_model=os.environ["MEMORY_STORE_EMBEDDING_MODEL_DEPLOYMENT_NAME"],
    options=MemoryStoreDefaultOptions(
        user_profile_enabled=True,
        chat_summary_enabled=True,
        user_profile_details=(
            "Remember stable user preferences and history; avoid secrets, "
            "credentials, and irrelevant personal data."
        ),
    ),
)

store = project_client.beta.memory_stores.create(
    name="<store-name>",
    definition=definition,
    description="Persistent memory store for a Foundry agent",
)

print(store.id)
```

### REST

```bash
API_VERSION="2025-11-15-preview"
ACCESS_TOKEN="$(az account get-access-token \
  --resource https://ai.azure.com/ \
  --query accessToken -o tsv)"

curl -X POST \
  "https://<project>.services.ai.azure.com/api/projects/<project-name>/memory_stores?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "<store-name>",
    "description": "Persistent memory store for a Foundry agent",
    "definition": {
      "kind": "default",
      "chat_model": "<chat-model-deployment>",
      "embedding_model": "text-embedding-3-small",
      "options": {
        "user_profile_enabled": true,
        "chat_summary_enabled": true,
        "user_profile_details": "Remember stable preferences; avoid secrets."
      }
    }
  }'
```

---

## 4. Adding memories

The low-level API adds memory by submitting conversation turns. Foundry then
extracts profile facts and summary memories from those turns.

### User profiles + chat summaries

```python
scope = "<entra-oid>"

items = [
    {
        "type": "message",
        "role": "user",
        "content": "I prefer dark mode, metric units, and vegetarian meals.",
    },
    {
        "type": "message",
        "role": "assistant",
        "content": "Understood. I will use those preferences in later sessions.",
    },
]

update_poller = project_client.beta.memory_stores.begin_update_memories(
    name="<store-name>",
    scope=scope,
    items=items,
    update_delay=0,
)

update_result = update_poller.result()
for operation in update_result.memory_operations:
    print(operation.kind, operation.memory_item.content)
```

REST shape:

```bash
curl -X POST \
  "https://<project>.services.ai.azure.com/api/projects/<project-name>/memory_stores/<store-name>:update_memories?api-version=2025-11-15-preview" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "<entra-oid>",
    "items": [
      {
        "type": "message",
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "I prefer dark mode, metric units, and vegetarian meals."
          }
        ]
      }
    ],
    "update_delay": 0
  }'
```

Notes:

- **User profile memory** is the stable fact layer extracted from those turns
- **Chat summary memory** is the summarized thread layer extracted after the
  conversation settles
- Writes are **asynchronous**; `update_delay` controls when long-term memory is
  committed after inactivity

---

## 5. Searching / retrieving memories

Search is semantic. Use it either to preload stable profile facts at session
start or to fetch relevant summary memories for the current turn.

```python
from azure.ai.projects.models import MemorySearchOptions

query_item = {
    "type": "message",
    "role": "user",
    "content": "What preferences has this user shared before?",
}

search_response = project_client.beta.memory_stores.search_memories(
    name="<store-name>",
    scope="<entra-oid>",
    items=[query_item],
    options=MemorySearchOptions(max_memories=5),
)

for memory in search_response.memories:
    print(memory.memory_item.content)
```

REST search:

```bash
curl -X POST \
  "https://<project>.services.ai.azure.com/api/projects/<project-name>/memory_stores/<store-name>:search_memories?api-version=2025-11-15-preview" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "<entra-oid>",
    "items": [
      {
        "type": "message",
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": "What preferences has this user shared before?"
          }
        ]
      }
    ],
    "options": {
      "max_memories": 5
    }
  }'
```

Retrieval pattern:

- **Static profile recall:** call search with a `scope` but no new items when
  you want baseline user facts at conversation start
- **Contextual recall:** include the latest turn in `items` to retrieve the most
  relevant summaries for the current question

---

## 6. Scope isolation

Scope is the boundary that prevents one user's memory from bleeding into
another's.

### Tool-based auto-resolution

When memory is attached as an agent tool, set:

- `scope: "{{$userId}}"` in the tool definition
- `x-memory-user-id: <entra-oid>` on response calls when your backend is acting
  on behalf of a user

If the header is absent, Foundry falls back to the caller's Microsoft Entra
identity and resolves scope from **tenant ID + object ID**.

### Low-level API behavior

For direct memory store API calls, **you must provide `scope` explicitly**.
The low-level API does not auto-resolve scope from Entra.

**Rule of thumb:**

- tool path = `{{$userId}}` + optional `x-memory-user-id`
- direct API path = explicit `scope="<stable-user-id>"`

---

## 7. Using with hosted agents

Attach the memory store as a tool so the hosted agent reads and writes memory
without manual update/search calls in your application logic.

```python
from azure.ai.projects.models import MemorySearchPreviewTool, PromptAgentDefinition

memory_tool = MemorySearchPreviewTool(
    memory_store_name="<store-name>",
    scope="{{$userId}}",
    update_delay=1,
)

agent = project_client.agents.create_version(
    agent_name="memory-enabled-agent",
    definition=PromptAgentDefinition(
        model=os.environ["MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME"],
        instructions="Use stored profile and chat summary memory to personalize responses.",
        tools=[memory_tool],
    ),
)

response = project_client.get_openai_client().responses.create(
    conversation="<conversation-id>",
    input="Please use my saved preferences.",
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    extra_headers={"x-memory-user-id": "<entra-oid>"},
)
```

Operationally:

- the agent injects **static profile memory** at conversation start
- it retrieves **contextual memories** per turn
- it schedules memory writes after inactivity using `update_delay`

This is the cleanest replacement for external memory middleware when the agent
already runs on Foundry.

---

## 8. Multi-language SDKs

| Language | Package | Primary surface |
|---|---|---|
| Python | `azure-ai-projects` | `project_client.beta.memory_stores` |
| C# | `Azure.AI.Projects` | `projectClient.MemoryStores` |
| TypeScript | `@azure/ai-projects` | `project.beta.memoryStores` |

### Python

```python
project_client.beta.memory_stores.create(...)
project_client.beta.memory_stores.begin_update_memories(...)
project_client.beta.memory_stores.search_memories(...)
```

### C#

```csharp
projectClient.MemoryStores.CreateMemoryStore(...);
projectClient.MemoryStores.WaitForMemoriesUpdate(...);
projectClient.MemoryStores.SearchMemories(...);
```

### TypeScript

```typescript
await project.beta.memoryStores.create(...);
const poller = project.beta.memoryStores.updateMemories(...);
await project.beta.memoryStores.searchMemories(...);
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Memory store creation fails or retrieval returns no results | No embedding deployment | Deploy `text-embedding-3-small` or `text-embedding-3-large` in the same project or connected resource |
| Memory APIs or tool are unavailable | Region not in preview footprint | Recreate the project in a supported region |
| Wrong user's preferences appear | Scope mismatch or missing `x-memory-user-id` | Use a stable per-user scope and always pass the header when acting on behalf of a user |
| Agent never seems to remember after one turn | `update_delay` not elapsed yet | Wait for inactivity, or set a smaller delay for demos/tests |
| Direct API call does not isolate users automatically | Expecting tool-style auto-resolution | Pass `scope` explicitly on every direct memory API call |

Security reminder: memory can be poisoned by bad prompts or bad imported
context. Filter inputs, avoid storing secrets, and keep `user_profile_details`
focused on business-relevant memory only.

---

## 10. Related skills

- [`foundry-hosted-agents`](../foundry-hosted-agents/) — deploys and operates
  the hosted agent runtime that can consume memory tools
- [`foundry-iq`](../foundry-iq/) — use for document grounding / enterprise RAG,
  not conversational long-term memory
- [`zava-workspace-deploy`](https://github.com/aiappsgbb/zava-constellation/tree/main/skills/zava-workspace-deploy) — older Zava notes refer
  to Mem0-style memory; prefer Foundry Memory as the native Foundry replacement

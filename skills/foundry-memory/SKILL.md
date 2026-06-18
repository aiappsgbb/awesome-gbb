---
name: foundry-memory
description: >
  Use Azure AI Foundry Memory Store for persistent agent memory across sessions:
  user profiles, chat summaries, procedural memory, semantic memory retrieval,
  hosted-agent memory tool wiring, scope isolation via x-memory-user-id /
  {{$userId}}, and azure-ai-projects patterns across Python, C#, and TypeScript.
  USE FOR: foundry memory, memory store, user profile, chat summary, procedural
  memory, cross-session memory, persistent memory, agent memory, remember user
  preferences, conversation history, semantic memory retrieval, memory CRUD,
  memory TTL, azd memory commands, azure-ai-projects memory, replace Mem0.
  DO NOT USE FOR: RAG/knowledge retrieval (use foundry-iq), document grounding,
  vector search over documents.
metadata:
  version: "1.1.1"
---

# Foundry Memory

Foundry Memory Store is the native Azure AI Foundry feature for **persistent
agent memory across sessions**. It gives a Foundry agent a managed long-term
memory layer instead of requiring an external sidecar such as Mem0.

It stores three memory types:

1. **User profiles** — durable facts and preferences about a user (for example,
   preferred units, UI settings, loyalty program, or role context).
2. **Chat summaries** — distilled cross-session summaries of prior threads so a
   later conversation can resume without replaying the full transcript.
3. **Procedural memory** — codified procedures the agent has learned through
   experience (for example, "when the user asks for a refund, always confirm
   the order ID first"). Procedural memory is opt-in per store via
   `procedural_memory_enabled=True`.

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

> **Sweden Central:** embedding deployments MUST use SKU `GlobalStandard`,
> not the default `Standard` — ARM rejects `Standard` with
> `InvalidResourceProperties: Sku is not supported in this region`. Other
> regions may impose similar constraints; verify the SKU-by-region
> availability table in the Foundry / Cognitive Services capacity docs
> before deploying elsewhere. (AGENTS.md § 9.7 Pattern 21.)

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

**RBAC requirement** (Pattern 23 — server-side worker identity): Memory
consolidation runs as the **project's system-assigned managed identity**
(NOT the caller's identity). That identity needs `Cognitive Services
OpenAI User` AND `Cognitive Services User` at the Foundry account scope to
call the chat deployment. The project SAMI is created with ACR roles only —
the two Cog roles must be granted explicitly. Symptom of omission: 401 from
the memory worker on its first consolidation pass, with the deploy/invoke
path superficially succeeding. See `AGENTS.md` § 9.7 Pattern 23 for the
canonical grant script.

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

## 9. Procedural memory

Procedural memory is the third memory type alongside user profiles and chat
summaries. It stores **codified procedures the agent has learned through
experience** — patterns like "always confirm the order ID before issuing a
refund", "for premium-tier users, skip the upsell prompt", or "when a customer
mentions an outage, check the status page before opening a ticket".

Procedural memory is **opt-in per store**. Enable it on
`MemoryStoreDefaultOptions` at create-time:

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
        procedural_memory_enabled=True,
        user_profile_details=(
            "Remember stable user preferences and history; avoid secrets, "
            "credentials, and irrelevant personal data."
        ),
    ),
)

store = project_client.beta.memory_stores.create(
    name="<store-name>",
    definition=definition,
    description="Persistent memory store with procedural memory enabled",
)
```

### Behavioral contract

- Procedural memory items have `kind="procedural"` when returned by
  `list_memories` or `search_memories`.
- Foundry extracts procedural memories from conversation turns the same way it
  extracts profile facts and summaries — submit turns via
  `begin_update_memories` (see § 4), then wait for the `update_delay` window.
- Procedural memory is scope-isolated like the other types — always pass a
  stable `scope` (typically `{"user_id": "<id>"}`) so an agent's learned
  procedures stay separated per user / per tenant.
- Enabling procedural memory **does not retroactively populate** the store from
  prior conversations. It applies only to turns submitted after the flag is on.

Keep `user_profile_details` (or the procedural-side hints) focused on the
domain the agent operates in. Procedural memory can be poisoned by adversarial
prompts the same way as user profiles — apply the input-filtering and
no-secrets rules from § 13.

---

## 10. CRUD on memories via direct API

In addition to `search_memories` (§ 5) for retrieval and `begin_update_memories`
(§ 4) for write, the direct API surfaces store-level CRUD and a `list_memories`
helper for browsing the current contents of a scope.

### Store-level CRUD

```python
# Get a store by name (raises ResourceNotFoundError if absent)
store = project_client.beta.memory_stores.get(name="<store-name>")

# List all stores in the project
for s in project_client.beta.memory_stores.list():
    print(s.name, s.description)

# Delete a store (idempotent — returns an object with .deleted boolean)
result = project_client.beta.memory_stores.delete(name="<store-name>")
assert result.deleted
```

### Listing memories inside a store

`list_memories` enumerates the memory items Foundry has extracted for a given
scope. Use it for audit, debugging, and admin UIs — for runtime retrieval,
prefer `search_memories` (§ 5) which returns semantically-ranked items.

```python
for item in project_client.beta.memory_stores.list_memories(
    name="<store-name>",
    scope={"user_id": "<user-id>"},
):
    print(item.memory_id, item.kind, item.content)
```

`kind` is one of `"user_profile"`, `"chat_summary"`, or `"procedural"` —
filter client-side when you only want one type.

### Per-item deletion

The current preview surface does **not** expose a per-item
`delete_memory(memory_id)` call. To prune individual memories, the supported
paths are:

- **Store-level delete + recreate** for full reset (acceptable for tests and
  rebuilds; destructive in production).
- **TTL-based expiry** (see § 11) — set a `default_ttl_seconds` so unused
  memories self-evict instead of accumulating.
- **Scope-bounded retention** — give each tenant / session / sandbox its own
  scope, then drop the scope when you're done with it; the store stays alive
  for other scopes.

Track the upstream preview surface — per-item delete is a likely addition.
Don't hand-roll a delete-by-ID workaround that touches storage primitives
underneath the API.

---

## 11. `default_ttl_seconds` on memory store config

`MemoryStoreDefaultOptions.default_ttl_seconds` sets a default expiry window
(in seconds) for every memory item Foundry stores in this store. After the
TTL elapses without re-touch, the memory item is evicted server-side.

- `default_ttl_seconds=0` (the default) means **no expiry** — memories live
  until the store is deleted or a future per-item delete API ships.
- A positive value (for example `30 * 24 * 60 * 60` for 30 days) caps every
  memory's lifetime. Use this to keep stores from accumulating stale
  preferences across long-lived deployments.
- TTL is a **store-wide default**; per-item TTL overrides are not currently
  surfaced. Choose a value that matches the slowest-changing memory in the
  store (e.g. user preferences may need months; transient session notes may
  need hours).

```python
from azure.ai.projects.models import (
    MemoryStoreDefaultDefinition,
    MemoryStoreDefaultOptions,
)

definition = MemoryStoreDefaultDefinition(
    chat_model=os.environ["MEMORY_STORE_CHAT_MODEL_DEPLOYMENT_NAME"],
    embedding_model=os.environ["MEMORY_STORE_EMBEDDING_MODEL_DEPLOYMENT_NAME"],
    options=MemoryStoreDefaultOptions(
        user_profile_enabled=True,
        chat_summary_enabled=True,
        procedural_memory_enabled=True,
        default_ttl_seconds=30 * 24 * 60 * 60,  # 30 days
    ),
)
```

When you set a short TTL for testing (for example `30` seconds), allow a small
grace window beyond the TTL before re-querying — server-side expiry is
eventually consistent, not synchronous.

---

## 12. `azd ai agent memory` direct commands

The `azd ai agent` extension exposes a `memory` subcommand group for
admin-style operations on memory stores from the CLI. Use this for one-off
inspection, smoke tests, and CI fixtures where you'd otherwise hand-roll a
Python script.

Discover the current surface — the flag set is preview-unstable (Pattern 16,
AGENTS.md § 9.7) and will drift across extension versions:

```bash
azd ai agent memory --help
```

The documented operations (subject to the extension version on your PATH)
cover store create / get / list / delete and memory list / search workflows.
**Do not hardcode flag names from this skill into production scripts** —
preview-CLI flag surfaces have already broken hosted-agent fixtures in this
catalog (see Pattern 16). For production, prefer the SDK paths in §§ 3-11.

If you need a stable scripted entry point, wrap the SDK call (§ 10) in a
small Python helper rather than depending on the CLI surface — the SDK is GA
ahead of the CLI extension.

When `azd ai agent memory --help` returns "unknown subcommand", the
extension on your PATH is older than the preview that added memory support.
Update with `azd extension upgrade ai`.

---

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Memory store creation fails or retrieval returns no results | No embedding deployment | Deploy `text-embedding-3-small` or `text-embedding-3-large` in the same project or connected resource |
| Memory APIs or tool are unavailable | Region not in preview footprint | Recreate the project in a supported region |
| Wrong user's preferences appear | Scope mismatch or missing `x-memory-user-id` | Use a stable per-user scope and always pass the header when acting on behalf of a user |
| Agent never seems to remember after one turn | `update_delay` not elapsed yet | Wait for inactivity, or set a smaller delay for demos/tests |
| 401 from memory worker (server-side, not your client) | Project SAMI lacks `Cognitive Services OpenAI User` AND `Cognitive Services User` at account scope | Grant **both** roles per Pattern 23 (AGENTS.md § 9.7), then wait ≥ 5 min for AAD propagation |
| Direct API call does not isolate users automatically | Expecting tool-style auto-resolution | Pass `scope` explicitly on every direct memory API call |

Security reminder: memory can be poisoned by bad prompts or bad imported
context. Filter inputs, avoid storing secrets, and keep `user_profile_details`
focused on business-relevant memory only.

---

## 14. Related skills

- [`foundry-hosted-agents`](../foundry-hosted-agents/) — deploys and operates
  the hosted agent runtime that can consume memory tools
- [`foundry-iq`](../foundry-iq/) — use for document grounding / enterprise RAG,
  not conversational long-term memory
- [`zava-workspace-deploy`](https://github.com/aiappsgbb/zava-constellation/tree/main/skills/zava-workspace-deploy) — older Zava notes refer
  to Mem0-style memory; prefer Foundry Memory as the native Foundry replacement

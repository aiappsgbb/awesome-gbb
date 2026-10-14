# Tool prerequisites and connection setup

Use an existing approved project and deployed model. Resolve the actual endpoint,
tool resource, connection name, execution identity and network route before
creating an agent version. Authenticate within `azure-tenant-isolation`; stop
on missing access rather than granting roles, opening networks or provisioning
replacements. Keep connection secrets out of agent definitions and logs.

| Tool | Prepare first | Check before invoking |
|---|---|---|
| File Search | Upload approved files and finish vector-store ingestion using the project's OpenAI client; retain returned file/store IDs | Ingestion completed with no failed files; an empty store is not grounding evidence |
| Code Interpreter | Upload files in the same project and select the documented container/file configuration | Files are authorized for this caller; container state is not per-user isolation |
| Azure AI Search | Existing populated index and a project Search connection | Correct index (not a Knowledge Base), searchable/retrievable fields, query mode and tool identity's index access |
| MCP | Reachable HTTPS MCP endpoint; a matching project connection for authenticated servers | Discover exact names, allowed tools, consent and approval behavior; successful connection CRUD is not a tool-call proof |
| OpenAPI | Reviewed spec with unique operation IDs, server URL and explicit auth configuration | Supported operations and parameter schemas; no credentials in the spec |
| Fabric IQ | Fabric workspace/data agent and its project connection | Fabric-specific permissions, endpoint and approval policy |
| Work IQ | Work IQ project connection with the documented delegated authorization | Tenant prerequisites and caller consent; do not substitute a project token for a user |
| Browser Automation | Playwright resource and project connection | Approved test URL, browser permissions, network reachability and run-owned session cleanup |

## Resolve, then wire

The SDK 2.4 connection reader is `project.connections.get(connection_name)`.
Use its returned `id`, not a display label or guessed ARM path. Do not request
credentials merely to discover the connection. Fabric IQ and Work IQ use
`project_connection_id`; Browser Automation nests it under
`browser_automation_preview.connection`. The tested construction examples are
in [SKILL.md](../SKILL.md#build-2026-additions-preview).

For Azure AI Search, this structural excerpt assumes an authenticated `project`,
an existing connection named `search-connection`, and an approved `documents`
index. It creates a definition only, not a connection or index:

```python
from azure.ai.projects.models import (
    AISearchIndexResource, AzureAISearchTool, AzureAISearchToolResource,
)

search_connection = project.connections.get("search-connection")
search_tool = AzureAISearchTool(
    azure_ai_search=AzureAISearchToolResource(
        indexes=[AISearchIndexResource(
            project_connection_id=search_connection.id,
            index_name="documents",
        )],
    ),
)
```

For OpenAPI, construct `OpenApiTool(openapi=OpenApiFunctionDefinition(...))`
with `name`, the complete `spec` dictionary and an explicit auth model. Use
`OpenApiAnonymousAuthDetails` only for an intentionally anonymous API; choose
the documented connection or managed-identity auth model otherwise.

For MCP connection lifecycle and supported auth families, follow
[Toolbox connections](../../foundry-toolbox/SKILL.md#mcp-auth-flavors-deeper).
Direct Prompt MCP and Toolbox MCP are different consumers: preserve the
caller identity and do not assume delegated passthrough. Keep approval enabled
unless the owner approves a bounded trusted-tool exception.

## Verify and retain custody

Invoke one synthetic query pinned to the candidate agent version. Inspect the
actual tool call/result and grounded answer; creation alone is not acceptance.
Keep approvals and auth failures visible. Record which files, stores, agent
versions and browser sessions this run created, and remove only those with
owner-authorized cleanup and readback. Never delete a shared connection/index.

## Official setup references

- [File Search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/file-search)
- [Azure AI Search](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search)
- [MCP](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/model-context-protocol)
- [OpenAPI](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/openapi)
- [Work IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)
- [Fabric IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Browser Automation](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/browser-automation)

These guides describe service prerequisites; newer samples do not override the
SDK cohort declared by this skill. Inspect the matching public model/schema
before adapting them.

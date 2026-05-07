---
name: foundry-mcp-aca
description: >
  Deploy custom MCP servers as Azure Container Apps or Azure Functions for use with
  Foundry hosted agents. Covers Cosmos DB MCPToolKit, Playwright MCP, custom MCP servers,
  protocol requirements, ACA configuration, and authentication patterns.
  USE FOR: deploy MCP server, MCP on ACA, Cosmos MCP, Playwright MCP in Foundry,
  custom MCP server, Azure Functions MCP, MCP ACA deployment, remote MCP endpoint,
  MCP for hosted agent, connect hosted agent to MCP.
  DO NOT USE FOR: deploying the hosted agent itself (use threadlight-deploy),
  local MCP development (use mcp-config.json directly), general Azure deploy.
---

# Foundry MCP ACA Deployment

Deploy custom MCP servers as **Azure Container Apps** or **Azure Functions** for
use with Foundry hosted agents. The hosted agent container connects to these MCP
servers via HTTP at runtime using `client.get_mcp_tool()`.

## When to Use

- Deploying a Cosmos DB MCP server for agent data access
- Running Playwright/browser automation as a remote MCP server
- Creating a custom MCP server for an API or data store not covered by Foundry built-ins
- Deploying an MCP server as an Azure Function (consumption billing)

## Architecture

```
┌────────────────────────┐     HTTPS      ┌─────────────────────┐
│  Hosted Agent Container │ ─────────────► │  MCP ACA            │
│  client.get_mcp_tool()  │               │  (e.g. Cosmos MCP)  │
│  Agent + ResponsesHost  │               │  Port 8080 /mcp     │
└────────────────────────┘                └─────────────────────┘
```

The hosted agent container:
1. Loads `mcp-config.json` at startup (or `MCP_SERVER_URL` env var)
2. Creates `client.get_mcp_tool(name=..., url=..., approval_mode="never_require")` per server
3. Passes tools to `Agent(tools=[...])` alongside skill-loaded instructions

---

## MCP Protocol Requirements

**ALL 6 JSON-RPC methods must return HTTP 200** — even if the response body is empty `{}`.
Failing to handle any of these causes `FoundryChatClient.get_mcp_tool()` to silently fail.

| Method | Purpose | Notes |
|--------|---------|-------|
| `initialize` | Protocol handshake | Must return server capabilities |
| `notifications/initialized` | Client notification | Can return `{}` |
| `tools/list` | Discover available tools | Must return tool definitions |
| `prompts/list` | List prompts | Required by agent-framework (return empty list) |
| `resources/list` | List resources | Required by agent-framework (return empty list) |
| `logging/setlevel` | Set log level | **Must be lowercase** — `logging/setlevel` not `logging/setLevel` |

**Transport requirements:**
- Foundry only accepts **remote HTTP** MCP endpoints (no stdio, no local)
- Use Streamable HTTP transport (HTTP POST with JSON-RPC at `/mcp`)
- Non-streaming tool call timeout: **100 seconds**
- Private MCP (VNet) requires Standard Agent Setup
- Port 8080 is convention for ACA MCP servers
- Health endpoint at `/health` (separate from MCP protocol)

---

## Option A: Cosmos DB MCPToolKit (.NET)

A pre-built .NET Cosmos DB MCPToolKit image provides 10 tools out of the box:

| Tool | Type | Purpose |
|------|------|---------|
| `list_databases` | Read | List all Cosmos databases |
| `list_collections` | Read | List containers in a database |
| `find_document_by_id` | Read | Get single document by id |
| `text_search` | Read | Text search across documents |
| `query_documents` | Read | SQL query against a container |
| `get_approximate_schema` | Read | Infer schema from sample docs |
| `get_recent_documents` | Read | Get N most recent documents |
| `vector_search` | Read | Semantic vector search |
| `upsert_document` | Write | Create or update a document |
| `delete_document` | Write | Delete a document by id |

### Deployment

Deploy as a per-project ACA with these environment variables:

| Variable | Required | Purpose |
|----------|----------|---------|
| `COSMOS_ENDPOINT` | ✅ | Cosmos DB account endpoint |
| `COSMOS_DATABASE` | ✅ | Default database name |
| `COSMOS_AUTH_KEY` | ✅ | Cosmos DB key (store in ACA secrets) |
| `DEV_BYPASS_AUTH` | No | Set `true` for dev (skip auth on MCP endpoint) |

### Agent Configuration

In the hosted agent's `mcp-config.json`:

```json
{
  "servers": {
    "cosmos-tools": {
      "type": "http",
      "url": "${MCP_SERVER_URL}/mcp"
    }
  }
}
```

Set `MCP_SERVER_URL` in `agent.yaml` environment variables to the ACA endpoint.

---

## Option B: Azure Functions (Consumption)

For lightweight, consumption-billed MCP servers:

```bash
# Scaffold from template
azd init --template remote-mcp-functions-python -e my-mcp-server

# Test locally
func start

# Deploy to Azure
azd up

# Endpoint: https://{app}.azurewebsites.net/runtime/webhooks/mcp
```

Azure Functions use HTTP Streamable transport by default.

---

## Option C: Custom ACA

Build a custom Docker image with your MCP tools and deploy as ACA.

### Example: Playwright MCP on ACA

For browser automation in Foundry (hosted agent containers cannot run browsers locally):

```dockerfile
FROM mcr.microsoft.com/playwright:v1.52.0-noble

RUN npm install -g @playwright/mcp

EXPOSE 8080
CMD ["npx", "@playwright/mcp", "--port", "8080"]
```

Deploy as ACA with external ingress on port 8080.

### Example: Custom Python MCP Server

```python
from fastmcp import FastMCP

mcp = FastMCP("my-tools")

@mcp.tool()
async def search_orders(query: str) -> str:
    """Search orders by keyword."""
    # Call your backend API here
    return results

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

---

## Bicep: ACA for MCP Server

```bicep
@description('Name of the MCP ACA')
param name string

@description('Location')
param location string = resourceGroup().location

@description('Container app environment ID')
param containerAppEnvironmentId string

@description('Container image')
param image string

@description('Environment variables')
param env array = []

resource mcpAca 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: image
          env: env
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = mcpAca.properties.configuration.ingress.fqdn
```

---

## Option D: Mock MCP Server (for PoC / Demo)

When backend systems are inaccessible (SAP, Oracle, corporate CRM, etc.), generate a
**FastMCP mock server** backed by sample data from `specs/sample-data/`. The customer
sees real MCP tool calls with realistic responses — and later swaps the endpoint URL
for their real system.

### How It Works

1. `threadlight-design` produces `specs/sample-data/{entity}.json` + tool contracts in spec § 6
2. This skill generates a FastMCP server with tools matching those contracts
3. Each tool reads from the sample data JSON files and returns matching records
4. Deploy to ACA (or run locally for dev) — agent connects via `mcp-config.json`
5. When real system available: customer deploys a real MCP server, changes the URL

### Generate `src/mcp/server.py`

For each tool contract in `specs/SPEC.md` § 6 that is backed by a system marked **mock**
in § 5, generate a tool function:

```python
"""Mock MCP server — auto-generated from SpecKit spec.
Replace with real system integration when available."""

import json
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("mock-tools")

DATA_DIR = Path(__file__).parent / "data"


def _load(entity: str) -> list:
    """Load sample data for an entity."""
    path = DATA_DIR / f"{entity}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [r for r in data if not r.get("_meta")]


# === Auto-generated tools from spec § 6 ===
# Each tool matches a tool contract. Replace with real API calls when available.

@mcp.tool()
async def get_customer_profile(customer_id: str) -> str:
    """Look up customer profile. (Mock: reads from sample data)"""
    records = _load("customers")
    match = [r for r in records if r.get("customer_id") == customer_id]
    if match:
        return json.dumps(match[0], indent=2)
    return json.dumps({"error": "not_found", "customer_id": customer_id})


# ... generate one @mcp.tool() per tool contract backed by a mocked system ...


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

### Generate `src/mcp/data/`

Copy sample data from `specs/sample-data/*.json` into `src/mcp/data/`.

### Generate `src/mcp/Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir fastmcp
COPY server.py .
COPY data/ data/
EXPOSE 8080
CMD ["python", "server.py"]
```

### Generate `src/mcp/requirements.txt`

```
fastmcp>=2.0.0
```

### Local Development

```bash
cd src/mcp
pip install -r requirements.txt
python server.py
# MCP endpoint: http://localhost:8080/mcp
```

### Deploy to ACA

```bash
az acr build --registry <acr> --image mock-mcp:latest ./src/mcp/
# Then create ACA pointing to the image (see Bicep above)
```

### Swap to Real System

When the real system becomes available:
1. Deploy a real MCP server (see Options A–C above)
2. Update `mcp-config.json` URL from mock endpoint to real endpoint
3. Redeploy the agent (`azd deploy <service>`)
4. The tool contracts stay the same — only the backing implementation changes

---

## Authentication

| Pattern | When to Use | How |
|---------|------------|-----|
| **No auth (dev)** | Local dev, internal ACA | `DEV_BYPASS_AUTH=true` or no auth middleware |
| **API key** | Simple production setups | Pass key in `Authorization: Bearer <key>` header via `mcp-config.json` |
| **Managed identity** | Production, same Azure tenant | ACA system-assigned MI → Cosmos RBAC / API auth |

For API key auth, store the key in ACA secrets and reference in `mcp-config.json`:

```json
{
  "servers": {
    "cosmos-tools": {
      "type": "http",
      "url": "${MCP_SERVER_URL}/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_API_KEY}"
      }
    }
  }
}
```

---

## Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| MCP tools not appearing in agent | Server returns 400/404 on protocol methods | All 6 JSON-RPC methods must return HTTP 200 |
| `logging/setLevel` error | Case-sensitive method name | Use lowercase: `logging/setlevel` |
| MCP connection timeout | ACA not started (cold start) | Runtime retries automatically; set `minReplicas: 1` for always-on |
| `invalid_payload` error | `${ENV_VAR}` in mcp-config.json not resolved → empty URL | Only include MCP servers with deployed endpoints. Remove entries with unresolved env vars. |
| Tools listed but calls fail | Tool call timeout (>100s) | Optimize tool implementation or increase ACA resources |
| `prompts/list` not implemented | Server doesn't handle this method | Return `{"prompts": []}` — agent-framework requires it |

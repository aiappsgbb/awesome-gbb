---
name: foundry-mcp-aca
description: >
  Deploy custom MCP servers as Azure Container Apps or Azure Functions for use with
  Foundry hosted agents. Covers Cosmos DB MCPToolKit, Playwright MCP, custom MCP servers,
  protocol requirements, ACA configuration, and authentication + hardening
  (ACA built-in auth / Easy Auth, OAuth, managed identity).
  USE FOR: deploy MCP server, MCP on ACA, Cosmos MCP, Playwright MCP in Foundry,
  custom MCP server, Azure Functions MCP, MCP ACA deployment, remote MCP endpoint,
  MCP for hosted agent, connect hosted agent to MCP, secure MCP server,
  harden MCP server, MCP authentication, MCP OAuth, ACA Easy Auth for MCP.
  DO NOT USE FOR: deploying the hosted agent itself (use threadlight-deploy),
  local MCP development (use mcp-config.json directly), general Azure deploy.
metadata:
  version: "1.2.3"
---
> **📦 This skill is for MCP server PRODUCERS (deploying servers to ACA).** If you want to CONSUME an existing MCP server from a Foundry hosted agent, see [foundry-hosted-agents](../foundry-hosted-agents/SKILL.md) § MCP Tools or [foundry-toolbox](../foundry-toolbox/SKILL.md) § Learn MCP.

# Foundry MCP ACA Deployment

> 🎯 **Scope: PRODUCER-side only.** This skill is for **hosting** MCP servers on
> Azure Container Apps or Azure Functions, NOT for **consuming** a remote MCP from
> a Foundry hosted agent (e.g. calling `https://learn.microsoft.com/api/mcp` or
> `https://api.github.com/mcp` from your agent's `container.py`).
>
> - **Producer (this skill):** you're WRITING + DEPLOYING an MCP server.
>   Cosmos MCP, Playwright MCP, custom MCP for an internal API, etc.
> - **Consumer (different skill):** you're WRITING a Foundry hosted agent that
>   CALLS a remote MCP server. Use [`foundry-hosted-agents`](../foundry-hosted-agents/SKILL.md)
>   § MCP Tools via FoundryChatClient + § MCP Tools — recommended pattern.
>
> Confusing the two costs hours. The consumer-side pattern is `MCPStreamableHTTPTool`
> wired into `Agent(tools=[…])`; the producer-side is everything below.

> ⚠️ **Azure Tenant Isolation (mandatory).** Before any `azd` or `az`
> operation, verify tenant isolation per
> [`azure-tenant-isolation`](../azure-tenant-isolation/): set config dirs,
> check token, assert subscription. See that skill's Agent preflight.

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
| `logging/setLevel` | Set log level | Per [MCP spec § Logging](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging) — camelCase `setLevel` (capital L). Lowercase `setlevel` returns `-32601 Method not found` from spec-compliant clients. |

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

Deploy as a per-project ACA. **Threadlight pilots are keyless-by-mandate** —
prefer managed identity over Cosmos keys.

| Variable | Required | Purpose |
|----------|----------|---------|
| `COSMOS_ENDPOINT` | ✅ | Cosmos DB account endpoint |
| `COSMOS_DATABASE` | ✅ | Default database name |
| `AZURE_CLIENT_ID` | ✅ (keyless) | UAMI client ID — the MCPToolKit's Cosmos SDK uses `DefaultAzureCredential` which reads this |
| `COSMOS_AUTH_KEY` | ❌ avoid | Cosmos master key. Only for local dev; for ACA, **disable account keys** at the Cosmos resource (`disableLocalAuth: true`) and grant the UAMI `Cosmos DB Built-in Data Contributor` (data-plane RBAC, NOT control-plane Contributor) on the database scope |
| `DEV_BYPASS_AUTH` | No | Set `true` only for local dev; never in prod |

> **RBAC pin (verified May 2026).** Cosmos DB SQL API data-plane access is
> NOT granted by control-plane roles like `Contributor` or
> `DocumentDB Account Contributor`. You MUST assign the data-plane role
> `Cosmos DB Built-in Data Contributor`
> (`00000000-0000-0000-0000-000000000002`) via `az cosmosdb sql role
> assignment create`. This is the same gotcha called out in
> `threadlight-hitl-patterns` — keep both wirings consistent.

> **⚠️ aiohttp dep is mandatory for the Python Cosmos MCP server.** The Python Cosmos MCPToolKit uses `azure-cosmos` async client which
> silently requires `aiohttp` as the HTTP transport. Without it the container starts
> fine, `tools/list` returns the 11 tools, but every `upsert_item` / `query_items`
> call fails server-side with what looks like a Cosmos error but is actually an
> ImportError swallowed by FastMCP. Pin in `src/mcp/requirements.txt`:
>
> ```
> fastmcp>=2.0.0,<3.0.0  # MUST upper-bound — see callout below
> azure-cosmos>=4.15.0   # see kwarg callout below
> azure-identity>=1.19.0
> mcp>=1.10.0
> aiohttp>=3.9.0         # REQUIRED — async HTTP transport for azure-cosmos
> ```

> **⚠️ Pin `fastmcp<3.0.0` — the unbounded `>=2.0.0` pin is a re-deploy time bomb.**
> FastMCP 3.x changed the streamable-http mount path. If `requirements.txt` says
> `fastmcp>=2.0.0` (no upper bound), the next container rebuild will pull
> **fastmcp 3.x silently** the moment it ships on PyPI. Symptoms — agent says
> *"case read failed"* / *"audit-log screening read failed"* on every tool call,
> bot/MCP logs show every single request as `POST /mcp HTTP/1.1" 404 Not Found`,
> the MCP container itself is `Healthy` and `Running`. **FastMCP itself prints
> the warning at boot:**
>
> ```
> FastMCP 3.0 is coming!
> Pin `fastmcp < 3` in production, then upgrade when you're ready.
> ```
>
> If you skim past that and ship, every Cosmos tool call will 404. The KYC PoC
> burned an hour on this when an unrelated `azd deploy cosmos-mcp` rebuild
> jumped fastmcp 2.14.7 → 3.2.4 and broke point reads + queries simultaneously.
> Always upper-bound: `fastmcp>=2.0.0,<3.0.0`. Same rule applies to **any
> client** that imports `fastmcp` (e.g. an ACA Job that drives the MCP) — pin
> client + server to the same major.
>
> **🛑 DO NOT bump `fastmcp` major version without re-running the demo scenarios** — the streamable-http mount path changed between 2.x and 3.x. Every Cosmos tool call will fail silently if the path moves. **DO test locally first:** `pip install 'fastmcp>=3' && python -m pytest tests/ -k cosmos_mcp`.

> **⚠️ `enable_cross_partition_query` was DROPPED in `azure-cosmos>=4.15` async.**
> If your `query_items` tool implementation passes `enable_cross_partition_query=True`,
> the kwarg leaks down to `aiohttp.ClientSession._request()` and raises
> `TypeError: ClientSession._request() got an unexpected keyword argument
> 'enable_cross_partition_query'`. FastMCP swallows the traceback and surfaces
> only `Error calling tool 'query_items'` — the agent then says "case lookup
> failed" on every related read while point reads (`get_item`) keep working.
>
> The new async signature is partition-key-aware by inference:
>
> ```python
> # ❌ Old (works on azure-cosmos<4.15, breaks on >=4.15):
> async for item in container.query_items(
>     query=q, parameters=p, enable_cross_partition_query=True,
> ):
>     ...
>
> # ✅ New: omit partition_key for cross-partition; pass it for single-partition:
> kwargs = {"query": q, "parameters": p}
> if partition_key is not None:
>     kwargs["partition_key"] = partition_key
> async for item in container.query_items(**kwargs):
>     ...
> ```
>
> This is a **silent migration trap** — the SDK dependency floats forward, the
> kwarg used to be valid, and the runtime error message blames the tool name
> not the SDK call. Catches every Cosmos MCP that pinned `azure-cosmos>=4.7`
> instead of `>=4.15`.
>
> **🛑 DO NOT rely on cross-partition queries for MCP tool calls without explicit user consent** — partition-scoped queries are cheaper and more predictable. **DO scope per-partition or accept the cost & latency impact.** If you must cross-partition, document it as a tool contract in SPEC § 6 so the agent knows to prefer partition-scoped alternatives when available.

> **⚠️ `azd deploy <mcp-service>` poisons every running agent's MCP session — must redeploy the agent too.**
> FastMCP's streamable-http maintains per-client session state in-memory on the MCP
> container. When you redeploy the MCP server (`azd deploy cosmos-mcp` /
> `azd deploy <mock-mcp-service>` / any new container revision), every session is wiped.
> The Foundry hosted agent's MCP client **caches the `mcp-session-id` from the previous
> initialize handshake and keeps sending it with every `tools/call`** — and **does NOT
> auto-detect "Session not found" + re-handshake**. Result: every tool call returns
> 404 silently, agent self-reports `case read failed` / `audit-log query failed`
> on EVERY tool, MCP container is `Healthy` and `Running`, MCP logs show
> `POST /mcp HTTP/1.1" 404 Not Found` **without** the preceding `new transport
> with session ID: ...` log line that a fresh handshake would produce. External
> probes to `/mcp` with proper Accept headers return `200 OK` — the path is fine,
> the SESSION is gone.
>
> **Distinguishing this from the FastMCP 3.x mount-path 404:**
>
> | Symptom | FastMCP 3.x mount-path | Stale session-id |
> |---|---|---|
> | MCP log line | `POST /mcp HTTP/1.1" 404` (no transport log either way) | `POST /mcp HTTP/1.1" 404` (no `new transport with session ID` log preceding) |
> | External probe with `Accept: application/json, text/event-stream` | `404 Not Found` (path moved) | `200 OK` (path fine) |
> | External probe with stale `mcp-session-id` header | `404 Not Found` (path moved) | `404 {"error":{"code":-32600,"message":"Session not found"}}` |
> | Fix | Pin `fastmcp<3.0.0`, rebuild MCP | Redeploy the AGENT after redeploying MCP |
>
> **Mandatory recovery sequence after redeploying any MCP server:**
>
> ```bash
> # After: azd deploy cosmos-mcp   (or any MCP service)
> # ALSO redeploy the agent so its in-memory MCP client cache is dropped:
> azd deploy <agent-service-name>      # creates a new agent version, fresh compute
>
> # And restart the bot ACA replica so its connection pool is dropped:
> az containerapp revision restart \
>   -g <rg> -n <bot-aca-name> \
>   --revision $(az containerapp revision list -g <rg> -n <bot-aca-name> \
>                  --query "[?properties.active] | [0].name" -o tsv)
> ```
>
> **Alternatively** — wait ~15 min idle and the refreshed-preview hosted agent
> auto-deprovisions; the next user message will spin up fresh compute with a
> fresh MCP session. But "wait 15 min" isn't a fix you can put in a runbook.
>
> **Where this should ideally be solved**: the agent runtime's MCP client should
> catch JSON-RPC error code `-32600 Session not found` and re-initialize. Until
> the platform handles this, treat MCP and agent as a **coupled deploy pair** —
> you cannot redeploy one without the other on a running pilot.
>
> **🛑 DO NOT redeploy MCP server without re-importing the consuming agent version** — the cached session ID will become stale and every tool call will 404. **DO bump the agent version pin** (or call `azd ai agent show` to refresh) **immediately after each MCP redeploy.** This is the most common production outage pattern on Foundry hosted agents.

### Cosmos firewall + ACA egress (the trap that wastes 45 min on every fresh PoC)

The single biggest "first-deploy doesn't work" gotcha for ACA→Cosmos:

| Default | What happens | Fix |
|---|---|---|
| Cosmos `publicNetworkAccess: Disabled` (the Azure default) | All ACA→Cosmos traffic returns `Forbidden — public access disabled` | Set `publicNetworkAccess: Enabled` for pilots (production: use private endpoint) |
| Cosmos `networkAclBypass: None` (default) AND `ipRules: []` | All ACA→Cosmos traffic returns `Forbidden — Request originated from IP <egress-ip> through public internet. This is blocked` | Either: (a) set `networkAclBypass: AzureServices` ⚠️ (see caveat) OR (b) add the ACA environment's egress IP to `ipRules` (proven path for pilots) |
| `networkAclBypass: AzureServices` is set, ACA still blocked | Even with `AzureServices` bypass, ACA managed-environment egress can still be treated as "public internet" by Cosmos. The bypass DOES NOT cover ACA the way it covers Functions/Logic Apps. | **Add the ACA egress IP to `ipRules` explicitly.** Get it from the Cosmos Forbidden error message ("Request originated from IP X.X.X.X"), then `az cosmosdb update -g <rg> -n <acct> --ip-range-filter "X.X.X.X"`. For prod, use a private endpoint instead. |

**Bicep snippet** (pilot-grade default — put this in `infra/modules/cosmos-db.bicep`):

```bicep
@description('Pilot posture: enables public network with AzureServices bypass + room for explicit ACA egress IP. Set false for prod-grade (private endpoint).')
param pilotPosture bool = true

@description('Optional explicit IP allowlist (for ACA egress IPs). Pilots: leave empty initially, then re-deploy with the IP from the Cosmos Forbidden error.')
param ipAllowlist array = []

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  // ...
  properties: {
    publicNetworkAccess: pilotPosture ? 'Enabled' : 'Disabled'
    networkAclBypass: pilotPosture ? 'AzureServices' : 'None'
    ipRules: [for ip in ipAllowlist: { ipAddressOrRange: ip }]
    disableLocalAuth: true   // keyless-by-mandate
    // ...
  }
}
```

**Operator runbook for the "ACA→Cosmos Forbidden" failure** (post-deploy):

```bash
# 1. Pull the egress IP from the cosmos-mcp ACA logs
az containerapp logs show -g <rg> -n ca-<process>-cosmos-mcp-<token> --tail 200 \
  | grep -i "Request originated from IP"
# Example output: "Request originated from IP 135.116.230.235 through public internet"

# 2. Add it to Cosmos firewall (REST PATCH; CLI does not expose --enable-public-network)
az rest --method PATCH \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.DocumentDB/databaseAccounts/<acct>?api-version=2024-12-01-preview" \
  --body '{"properties":{"publicNetworkAccess":"Enabled","ipRules":[{"ipAddressOrRange":"135.116.230.235"}]}}'

# 3. Wait 60-180s for Cosmos provisioningState to flip Updating -> Succeeded
az cosmosdb show -g <rg> -n <acct> --query "provisioningState" -o tsv
```

**Or automate it as a postdeploy hook (recommended for fully unattended `azd up`).**
Reference implementation: [`references/postdeploy_cosmos_firewall_egress.py`](references/postdeploy_cosmos_firewall_egress.py)
in this skill. The script:

1. Reads `AZURE_RESOURCE_GROUP` / `AZURE_COSMOS_ACCOUNT_NAME` from azd env
2. Auto-discovers the cosmos-mcp ACA name (first ACA matching `*cosmos-mcp*`)
3. Polls the ACA's recent console logs (up to 5 min) for the Cosmos Forbidden error pattern
4. Extracts the egress IP, idempotently patches Cosmos `ipRules`
5. Polls Cosmos `provisioningState` until `Succeeded`

Wire it into `azure.yaml`:

```yaml
hooks:
  postdeploy:
    shell: pwsh
    run: |
      cd infra/scripts && uv sync --frozen
      uv run postdeploy.py
      uv run postdeploy_cosmos_firewall_egress.py
```

This closes the last manual step in the "1-shot `azd up` for Cosmos-using
processes" flow. Verified design against recent pilot forensics.

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

> **MUST:** Copy verbatim from [`references/python/server.py`](references/python/server.py). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical FastMCP server with the `transport="streamable-http"` + `host="0.0.0.0"` + `port=os.environ["PORT"]` trio (closes M2 + M3) plus the `_helper()` pattern for sharing logic between two `@mcp.tool()` decorated functions.

The three lines this template prevents from going wrong: `transport="streamable-http"` (not bare `"http"`), `host="0.0.0.0"` (not stdio default), and `port=int(os.environ.get("PORT","8080"))` (ACA injects PORT). Plus: never call one `@mcp.tool()`-decorated function from inside another — extract shared logic into a plain `_helper()`.

---

## Bicep: ACA for MCP Server

> **MUST:** Copy verbatim from [`references/bicep/mcp-aca.bicep`](references/bicep/mcp-aca.bicep). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical ACA module with external ingress on `:8080`, UAMI for ACR pull (A2), `transport: 'http'` (not deprecated `'auto'`), and liveness + startup probes on `/health` (without them, cold-start tool calls 502 until the first scrape). `minReplicas: 1` avoids the cold-start hit on every demo.

VNet injection is intentionally out of scope here — see `foundry-vnet-deploy` SKILL for private topology. External ingress is required when the Foundry hosted agent (which runs in Foundry's infra, not your VNet) calls the MCP.

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
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
COPY data/ data/
EXPOSE 8080
CMD ["python", "server.py"]
```

> **Pin `fastmcp`.** `fastmcp` had a
> 1.x → 2.x API break (Client interface changed). Both server (`src/mcp/`) and any
> client that imports `fastmcp` (e.g. an ACA Job that drives the MCP server) MUST
> pin to the **same major** to avoid silent failures: container starts, `tools/list`
> works, but `tools/call` returns the wrong shape and the agent self-reports `failed`.

### Generate `src/mcp/requirements.txt`

```
fastmcp>=2.0.0,<3.0.0
azure-cosmos>=4.7.0          # only if Cosmos MCP — see Option A
azure-identity>=1.19.0       # only if keyless to Azure
aiohttp>=3.9.0               # MANDATORY for Cosmos MCP — async transport for azure-cosmos
```

### MCP ACA also needs the `fetch-container-image` pattern (just like bot)

> **Verified in recent ACA port-mismatch retrospectives.** When `infra/main.bicep`
> defaults the MCP image to `mcr.microsoft.com/azuredocs/containerapps-helloworld:latest`
> (the standard "first-deploy" placeholder), the ACA gets stuck `InProgress` forever
> because the placeholder serves port 80 but the MCP module pins `targetPort: 8080`.
> The `fetch-container-image` pattern is documented for bot ACAs in `foundry-teams-bot`
> SKILL.md but **MUST be applied to MCP ACAs too.** Same trap, same fix:

```bicep
// infra/main.bicep — MCP ACA wiring
@description('Set true after the first azd deploy mcp; lets re-provision preserve the deployed image')
param mcpResourceExists bool = false

module fetchMcpImage 'mcp/fetch-container-image.bicep' = if (mcpResourceExists) {
  name: 'fetch-mcp-image'
  params: {
    name: 'ca-${prefix}-mcp-${token}'
  }
}

module mcp 'mcp/aca.bicep' = {
  params: {
    image: mcpResourceExists && !empty(fetchMcpImage.outputs.image)
      ? fetchMcpImage.outputs.image
      : 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
    targetPortOverride: mcpResourceExists ? 8080 : 80   // KEY: 80 on first deploy (helloworld), 8080 thereafter
    // ... rest of params
  }
}
```

The `fetch-container-image.bicep` shape is identical to the bot version
in `foundry-teams-bot/templates/infra/bot/fetch-container-image.bicep` —
copy it into `infra/mcp/` and adjust the resource type.

`threadlight-safe-check` will catch the helloworld placeholder if you
forget; see its `--phase post-deploy` image-probe step.

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

## Securing your MCP server

> **The perimeter is yours to build.** A public survey found only **8.5% of
> reachable MCP servers require OAuth** — the rest are unauthenticated remote
> tool-execution endpoints, i.e. open RCE. A remote MCP server with no identity
> check is not "internal-only by obscurity"; it is exploitable. This section
> hardens the ACA deployment above with Entra-validated auth **in front of** the
> container, managed identity for the hops behind it, and audit + input
> defenses on the tools themselves.
>
> **This skill uses ACA built-in authentication ("Easy Auth for Container
> Apps") — not Azure App Service.** The platform validates the caller's token
> before a request reaches your code. Reference:
> [Authentication and authorization in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication).

### Threat model → defense mapping

| Threat | Mitigating layer | Where it lives |
|--------|------------------|----------------|
| Unauthenticated tool invocation (open RCE) | **L1** ACA built-in auth + `Return401` | `references/bicep/mcp-aca-auth.bicep` / `az containerapp auth` |
| Confused deputy — server replays the caller's token downstream | **L2** managed identity; never forward the inbound token | `references/python/secure_server.py` |
| Over-broad RBAC → lateral movement | **L2** one least-privilege role assignment | `references/bicep/mcp-aca-auth.bicep` |
| Secret exfiltration through a tool result | **L3** return secret *metadata*, never values; Key Vault refs | `references/python/secure_server.py` |
| Path traversal / command injection in tool args | **L3** allow-list inputs; reject `..` `/` `\` `;` `\|` `` ` `` `$(` | `references/python/secure_server.py` |
| Undetected abuse (invocation floods, probing) | **L5** one audit event per call → scheduled-query alert | `references/python/secure_server.py` + `foundry-observability` |

Defense-in-depth: skipping **L1** makes everything else moot; **L2–L5** keep a
breach from spreading.

### Layer 1 — Identity perimeter: ACA built-in auth

Put Entra in front of the container. ACA validates the JWT **before** it reaches
your app and injects a trusted `X-MS-CLIENT-PRINCIPAL` header (base64 JSON the
client cannot forge). Anonymous calls get `401` — they never touch your tools.
Read that header **server-side** (FastMCP's `get_http_headers()` — see
[`secure_server.py`](references/python/secure_server.py)); never accept the
principal as a tool argument, which the client controls and can forge.

**One-time app registration** (defines the audience clients request a token for):

```bash
TENANT_ID=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name "mcp-server-auth" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)
az ad sp create --id "$APP_ID"
# Expose api://<appId> as the resource callers request a token for:
az ad app update --id "$APP_ID" --identifier-uris "api://$APP_ID"
```

**Enable built-in auth + reject anonymous callers:**

```bash
az containerapp auth microsoft update -n <app> -g <rg> \
  --client-id "$APP_ID" \
  --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
  --allowed-token-audiences "api://$APP_ID" --yes
az containerapp auth update -n <app> -g <rg> \
  --unauthenticated-client-action Return401
```

> **⚠️ Audience-scoped only.** These two commands validate audience + issuer —
> enough for delegated / interactive callers. The **app-only server-to-server**
> model (this skill's primary consumer) needs two more adjustments: see the
> callout below, or use the Bicep reference, which encodes both.

`Return401` is the API-server posture (reject), versus `RedirectToLoginPage`
(browser apps) or `AllowAnonymous` (pass everything through — never for a remote
MCP). The IaC-native equivalent — a `Microsoft.App/containerApps/authConfigs`
child resource, validation-only so it needs **no client secret** — is
[`references/bicep/mcp-aca-auth.bicep`](references/bicep/mcp-aca-auth.bicep).

> **App-only callers need explicit allow-listing — a mismatch is `403`, not
> `401`.** A server-to-server / MI bearer token (this skill's primary consumer
> model) clears the anonymous check but is still **denied `403`** unless its
> client id is in `defaultAuthorizationPolicy.allowedApplications`. Two more
> app-only quirks the reference Bicep encodes (all three verified against a live
> ACA Easy Auth deployment):
> - a **v2 app-only token's `aud` is the bare client GUID**, not `api://<appId>`
>   — list **both** forms in `allowedAudiences` so delegated *and* app-only
>   callers pass audience validation;
> - **auth-config edits need an auth-sidecar reload** — run `az containerapp
>   revision restart` after changing `authConfig`, or the old policy silently
>   sticks and every authed call keeps returning the stale result.

**Caveat — no Dynamic Client Registration.** Entra does not implement DCR, so
interactive MCP clients must be **pre-registered**; ship a known client id
rather than expecting the client to self-register.

These options replace the old dev-only table:

| Option | When | Posture |
|--------|------|---------|
| Built-in auth + `Return401` (**recommended**) | Any reachable deployment | Entra-validated bearer |
| `AllowAnonymous` + a dev bypass flag | Local inner-loop only | No perimeter — never expose |

### Layer 2 — Managed identity and the confused-deputy rule

The server authenticates to Azure with its **own** managed identity, never the
caller's token. `DefaultAzureCredential` resolves `az login` locally and the
user-assigned MI in ACA — no secrets in code:

> **MUST:** downstream Azure access uses the server's MI. Copy the credential +
> secret-metadata pattern verbatim from
> [`references/python/secure_server.py`](references/python/secure_server.py).

**The confused-deputy rule:** the inbound token authorizes the caller to *your
server only*. Do **not** replay it to Cosmos, Key Vault, or another API. Use the
server's MI, or the On-Behalf-Of flow if you genuinely must act as the user.
Grant that MI exactly one role (e.g. `Key Vault Secrets User`) — the role
assignment is in
[`references/bicep/mcp-aca-auth.bicep`](references/bicep/mcp-aca-auth.bicep).

### Layer 3 — Secret hygiene and tool-input defense

**Never return a secret value from a tool.** Return metadata (name, version,
enabled) so the model can reason about a secret without exfiltrating it; the
value reaches the runtime via a Key Vault reference
(`@Microsoft.KeyVault(SecretUri=...)`), not through the model. The
`secret_status` tool in `secure_server.py` shows the pattern.

**Reject unsafe tool inputs.** Any argument that becomes a path, key, or shell
fragment is a traversal/injection vector. The `safe_lookup` tool in
`secure_server.py` rejects `..`, `/`, `\`, `;`, `|`, `` ` ``, and `$(` before
use — reject-by-default beats sanitizing.

### Layer 4 — Network hardening

Easy Auth is an **identity** perimeter, not a **network** one. For regulated
workloads add, in order: private endpoints + VNET injection, then an APIM front
door running `validate-jwt` + `rate-limit-by-key`. That topology (and why
Foundry hosted agents still require external ingress) is
[`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) — out of scope here.

**External ingress is not "unauthenticated."** Foundry hosted agents run in
Foundry's infrastructure, so the MCP needs `--ingress external` (see Gotchas).
With Layer 1 in front, every external call still needs a valid token — external
ingress + Easy Auth is the standard safe posture. Reach for VNET isolation only
when a compliance boundary demands it.

### Layer 5 — Audit and monitoring

Emit one structured audit line per tool call (caller, tool, decision). ACA ships
stdout to Log Analytics automatically, so a
[`foundry-observability`](../foundry-observability/SKILL.md) scheduled-query
alert can fire on invocation spikes or repeated `denied` events. The
`audit_event` helper in `secure_server.py` is the emitter; upgrade to Azure
Monitor OpenTelemetry spans via `foundry-observability` when you want
distributed tracing.

### Connecting clients

| Client | How it authenticates | Notes |
|--------|----------------------|-------|
| **Server-to-server** (Foundry agent, any service) | Its MI requests a token for `api://<appId>`, sends `Authorization: Bearer <token>` | Platform-native; the CI fixture proves this 401→200 contract when the standing `MCP_AUTH_APP_CLIENT_ID` secret is configured (else that step is skipped) |
| **Interactive — manual bearer** (VS Code / Claude / Copilot) | Paste a token into the client's MCP config | Simplest interactive path |
| **Interactive — OAuth discovery** (advanced) | Server publishes PRM (RFC 9728); client follows `WWW-Authenticate` → user sign-in | Server's job on ACA — see below |

**Manual bearer** — a VS Code `.vscode/mcp.json` fragment:

```json
{
  "servers": {
    "my-mcp": {
      "type": "http",
      "url": "https://<aca-fqdn>/mcp/",
      "headers": { "Authorization": "Bearer ${input:mcpToken}" }
    }
  }
}
```

Get the token with
`az account get-access-token --resource api://<appId> --query accessToken -o tsv`.

**OAuth discovery (advanced).** Unlike Azure App Service (whose preview platform
feature can auto-serve Protected Resource Metadata), **on ACA the MCP server
itself must publish PRM** at `/.well-known/oauth-protected-resource` (RFC 9728)
and emit a `WWW-Authenticate` challenge so a spec-compliant client can discover
the authorization server and run the flow. FastMCP's auth provider implements
this; see the
[MCP authorization spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization).
This path requires an interactive browser sign-in, so it is documented but not
CI-tested.

---

## Gotchas

> **🔴 DO NOT** use bare `MCP.run()` (defaults to stdio transport). On ACA, you MUST use `transport="streamable-http"` and bind to `0.0.0.0:8080`.

| Issue | Cause | Fix |
|-------|-------|-----|
| MCP tools not appearing in agent | Server returns 400/404 on protocol methods | All 6 JSON-RPC methods must return HTTP 200 |
| `logging/setLevel` returns -32601 Method not found | Server didn't implement the optional logging capability OR used wrong casing | Either implement the method per [MCP spec § Logging](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging) (camelCase `setLevel`) and declare `capabilities.logging`, or simply omit the capability — Foundry's MCP client tolerates servers that don't expose logging. |
| MCP connection timeout | ACA not started (cold start) | Runtime retries automatically; set `minReplicas: 1` for always-on |
| `invalid_payload` error | `${ENV_VAR}` in mcp-config.json not resolved → empty URL | Only include MCP servers with deployed endpoints. Remove entries with unresolved env vars. |
| Tools listed but calls fail | Tool call timeout (>100s) | Optimize tool implementation or increase ACA resources |
| **`FastMCP` server starts but returns 000/timeout on port** | `MCP.run()` with no args defaults to `stdio` transport (reads stdin, never binds HTTP port). ACA health probe fails, container marked unhealthy. | **🛑 DO NOT use bare `MCP.run()` on ACA — it defaults to stdio.** **DO use** `MCP.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))`. Note: `transport="streamable-http"` (with the dash) matches the canonical examples elsewhere in this SKILL; the legacy bare `http` transport name is stale. |
| **`TypeError: 'FunctionTool' object is not callable` inside a tool** | `@MCP.tool` wraps the function in a `FunctionTool` object. Calling it from Python (e.g., tool A calls tool B internally) raises `TypeError`. | **Extract shared logic into a plain `_helper()` function. Both `@MCP.tool` functions call the helper. Never call one `@MCP.tool`-decorated function from inside another.** |
| **MCP ACA deployed but Foundry agent can't reach it (connection timeout)** | `az containerapp create --ingress internal` — only resources in the same VNET can reach it. Foundry hosted agents run in **Foundry's own infrastructure**, not your VNET. | **Use `--ingress external` for MCP ACA containers that Foundry agents call. Internal ingress only works for VNET-injected agents (private topology) where the agent subnet is peered/injected into the same VNET. See `foundry-vnet-deploy`.** External ingress is safe when fronted by ACA built-in auth (see § Securing your MCP server → Layer 1); it is not the same as "unauthenticated." |
| `prompts/list` not implemented | Server doesn't handle this method | Return `{"prompts": []}` — agent-framework requires it |
| MCP container `404` log noise after demo | MAF client occasionally fires 1-3 stray POSTs to `/mcp` after `DELETE` of the session — the server is gone, so they 404. Cosmos calls succeeded; this is post-mortem chatter, not a runtime problem. | Either accept the noise (no functional impact) or suppress in the FastMCP server with a no-op handler that returns 204 for any POST hitting an unknown session id. Document for whoever reads `az containerapp logs show` so they don't chase it as a real bug. |

---

## Failure Modes & Recovery (Consumer Config / Deployment Coupling)

| Symptom | Root cause | DO NOT do | DO instead |
|---------|-----------|-----------|-----------|
| Consumer config points to wrong URL (env var not resolved at deploy time) | `${MCP_SERVER_URL}` expands to empty at agent-startup time, not deployment time | **DO NOT use unguarded `${VAR}` substitution in mcp-config.json** — if the var is undefined, the agent skips the server silently | **DO guard with validation:** `if not url or not url.startswith("http"): raise ValueError(f"Invalid MCP URL: {url}")` in agent startup. Fail fast + audit-log. |
| Session ID stale after MCP redeploy | Foundry hosted agent caches the `mcp-session-id` token from the MCP server's `initialize` response. When MCP redeploys (new container), the session is wiped. Agent keeps sending stale session ID and gets 404. | **DO NOT redeploy MCP server without re-importing + pinning the agent version** — the in-memory client cache persists across requests even after MCP dies | **DO bump the agent version pin** (e.g., `version: "1.2.3"` → `"1.2.4"` in `agent-config.json`) or run `azd ai agent show <agent-id>` to force version refresh. See § Mandatory recovery sequence. |
| Wrong mount path (404 on MCP calls) | FastMCP 3.x serves on `/mcp/` with trailing slash; consumer config or curl tests use `/` without slash | **DO NOT assume FastMCP mount path** — it changed between 2.x and 3.x; don't infer from version. Test explicitly. | **DO test with `curl https://<aca-fqdn>/mcp/ -H "Accept: application/json, text/event-stream"` (note trailing slash).** Returns `200 OK` if path is correct. For local: `curl http://localhost:8080/mcp/`. |
| MCP call returns `401` after enabling built-in auth | Caller sent no token, or a token for the wrong resource | DO NOT switch to `AllowAnonymous` to "make it work" — that deletes the perimeter | Send `Authorization: Bearer $(az account get-access-token --resource api://<appId> --query accessToken -o tsv)`; confirm the token `aud` equals `api://<appId>` |
| `401` even with a token attached | `allowedAudiences` / issuer mismatch, or a Graph token | DO NOT paste a Microsoft Graph token (`--resource https://graph.microsoft.com`) | Request the token for `api://<appId>`; verify `--allowed-token-audiences` includes exactly that value and issuer is `https://login.microsoftonline.com/<tenant>/v2.0` |

---

## Mock Data Generation — Delegate to `threadlight-demo-data-factory`

**Important**: The Mock MCP Server (Option D above) describes the **MCP shell**
— how to wrap mocked systems behind the protocol. **It does NOT generate the
realistic sample data itself.** Data generation is the responsibility of the
`threadlight-demo-data-factory` skill.

### Division of labor

| Layer | Skill | Output |
|-------|-------|--------|
| **What data should look like** (industry rules, golden cases, distributions) | `threadlight-design` (`references/data-realism/<industry>.md`) | Markdown rules per industry |
| **How data is generated** (Faker generators, seeding, reset, scripts) | `threadlight-demo-data-factory` | `src/agent/data/seed.py` + scripts |
| **How tools wrap the data** (MCP protocol, JSON-RPC, tool contracts) | `foundry-mcp-aca` (this skill) | `src/mcp/server.py` + Dockerfile + ACA Bicep |

### Workflow when the spec marks a system as `mock`

```
SPEC § 5 says system X is "mock"
    │
    ├── threadlight-design § 11d defines the data shape (volumes, golden cases, industry rules)
    │
    ├── threadlight-demo-data-factory generates src/agent/data/*.json
    │       (Faker + per-industry generator + seeded RNG + Cosmos seed/reset scripts)
    │
    └── foundry-mcp-aca (this skill) generates src/mcp/server.py
            that READS src/agent/data/*.json AND/OR queries Cosmos (seeded by the factory)
            and exposes the spec § 6 tool contracts via MCP
```

The `src/mcp/data/` directory described in Option D §
"Generate `src/mcp/data/`" is **populated by `threadlight-demo-data-factory`,
not by this skill**. The script copying step in Option D should be replaced
with a call to the factory:

```bash
# Old (manual): cp specs/sample-data/*.json src/mcp/data/
# New (skill-driven):
uv run scripts/seed_data.py --to src/mcp/data/   # threadlight-demo-data-factory
```

---

## Validate-or-reject (the canonical pattern for stateful tools)

> **Highest-leverage pattern in the toolchain.** Observed in recent pilots:
> lifted recommendation quality from "junk packet
> with `confidence: 0`" to "well-cited `confidence: 0.93` packet" with
> a single server-side change. Apply this to **every** MCP tool that
> commits a decision, persists state, or returns a high-stakes
> artifact (recommendation, approval, payment, allocation, contract).

### The failure mode this fixes

When a hosted agent runs a long instruction chain (10+ steps), even
strong models occasionally call a "build the answer" tool **before**
calling the evidence-gathering tools. With a permissive server, this
returns a hollow object — no transactions, no merchant lookup, no rule
citations — and the agent confidently emits it as the final answer.

The most reliable fix is **NOT** to add more text to the agent's
instructions ("ALWAYS call X before Y"). It's to make the server
**physically incapable** of producing a hollow answer.

### The pattern

Every commit-style tool validates that its `evidence_bundle` (or
equivalent input) contains the required fields. If anything is missing,
return a structured error with a `next_steps` array that names exactly
which tools to call. The agent reads this and self-corrects on the
next iteration.

```python
# src/mcp/server.py — applies to ANY commit-style tool
@mcp.tool()
async def build_recommendation(
    case_id: str,
    evidence_bundle: dict,   # the agent assembles this from prior tool calls
) -> str:
    """Build the final recommendation packet. REQUIRES complete evidence."""

    REQUIRED = {
        "transactions": "get_transaction_history",
        "merchant_profile": "get_merchant_profile",
        "prior_cases": "search_prior_cases",
        "rule_citations": "lookup_reg_rule + lookup_network_rule",
    }

    missing = []
    for field, source_tool in REQUIRED.items():
        v = evidence_bundle.get(field)
        if not v or (isinstance(v, list) and len(v) == 0):
            missing.append({"field": field, "call_tool": source_tool})

    if missing:
        return json.dumps({
            "error": "INSUFFICIENT_EVIDENCE",
            "case_id": case_id,
            "missing": missing,
            "next_steps": [
                f"Call `{m['call_tool']}` to populate evidence_bundle.{m['field']}"
                for m in missing
            ],
            "guidance": (
                "Do not retry build_recommendation until every "
                "missing field is populated."
            ),
        }, indent=2)

    # ... real recommendation construction here ...
    return json.dumps(packet, indent=2)
```

### What good looks like (acceptance criteria)

| Test | Expected |
|------|----------|
| Call commit-tool with empty `evidence_bundle` | Returns `INSUFFICIENT_EVIDENCE` with full `missing` + `next_steps` (HTTP 200, error in payload — never raise) |
| Call commit-tool with partial evidence | Returns `INSUFFICIENT_EVIDENCE` listing only the missing fields |
| Call commit-tool with complete evidence | Returns the real packet |
| Smoke test on the agent end-to-end | Agent never emits a hollow packet — when it tries, it self-corrects within 1-2 extra tool calls |

### Why structured (`error` + `missing` + `next_steps`), not free-form

A free-form `"please call get_transaction_history first"` works *some*
of the time. The structured shape is the difference between "works
high and low reproducibility in recent strict-smoke runs. Models
parse structured payloads more reliably than English instructions in
tool outputs.

### Severity & error semantics

- Always return HTTP 200 with the error in the JSON body. **Never raise**
  — Foundry's MCP client will treat HTTP errors as a tool failure and
  retry with the same arguments, which doesn't help.
- Use a stable `error` enum (`INSUFFICIENT_EVIDENCE`, `NOT_FOUND`,
  `STATE_CONFLICT`, etc.) so the agent can pattern-match.
- `next_steps` MUST name the exact tool name the agent has access to —
  do not write "go look it up", write `"Call \`get_transaction_history\`
  with customer_id=…"`.

### When NOT to apply this pattern

- Pure-read tools (`get_transaction_history`, `lookup_*`) — no state,
  no commit, no need to gate.
- Trivial tools that take only the inputs they validate (e.g.,
  `compute_business_days(start, end)`) — there's nothing to gate
  against.
- Tools whose entire purpose IS to fail-fast on missing args (the
  validation IS the answer).

### Cross-reference

This pattern combines with `threadlight-design` SPEC § 6 tool contracts:
each commit-style tool's contract should explicitly enumerate its
required `evidence_bundle` fields and the `error` enums it can return.
The MCP server then mirrors those contracts as the validate-or-reject
guard above.

---

## Streaming & Webhook Primitives (for live-event MCP servers)

Some processes (Order Fallout, Network Fault, Supplier Risk news ingestion)
need MCP tools that return **streaming live data** rather than read-once
records. Two patterns:

### Pattern 1 — `tools/call` with progressive notifications

For long-running tools that should stream partial results (e.g., "scanning
1247 orders for fallout matches"):

```python
@mcp.tool()
async def scan_fallout_orders(ctx: Context) -> dict:
    total = 1247
    for i, order in enumerate(orders):
        await ctx.report_progress(i, total, f"Scanning {order['order_id']}")
        if matches_fallout_pattern(order):
            yield order  # streaming chunk
    return {"scanned": total, "matched": match_count}
```

The agent receives `progress` notifications via JSON-RPC and can render
them in the workspace UI.

### Pattern 2 — webhook-fed MCP server

For event-driven sources (Service Bus, Event Grid), pair this skill with
**`threadlight-event-triggers`**:

```
External event source                  MCP server (this skill)
     │                                       ▲
     ▼                                       │
[event-triggers receiver]  ─writes to─►  Cosmos / Storage
     │
     └── normalizes payload, dedups, writes to backing store
```

The receiver scaffold (from `threadlight-event-triggers`) ingests and
normalizes; this skill's MCP server reads from the backing store and exposes
it through tool contracts. **Do not poll external APIs from inside the MCP
server** — it makes the agent slow and breaks the 100-second tool timeout.

---

## Reset & Replay Scripts

Every MCP server backed by a mocked system MUST ship two scripts so demos
recover from failed runs in <30s:

### `scripts/seed_mcp.py`

Idempotent. Loads `src/agent/data/*.json` (generated by
`threadlight-demo-data-factory`) into the MCP backing store (in-memory cache
or Cosmos seeding). Safe to call repeatedly.

### `scripts/reset_mcp.py`

Wipes any state the agent has mutated (case statuses moved, decisions
recorded) and re-seeds. The agent does NOT need to be restarted — the MCP
server re-reads on next tool call.

```python
# scripts/reset_mcp.py — typical shape
async def reset():
    await wipe_mutable_state()        # agent-driven changes
    await seed_baseline()             # factory-generated data
    await mark_reset(timestamp=now()) # surface in workspace UI

if __name__ == "__main__":
    asyncio.run(reset())
    print("MCP reset complete.")
```

The reset endpoint MAY also be exposed as an HTTP route on the MCP server
(`POST /admin/reset`) for one-click reset from the workspace UI — but
ONLY in dev/demo environments. Gate behind `DEV_BYPASS_AUTH=true`.

---

## Input contract / Output artifacts

| Reads | From |
|-------|------|
| **SPEC.md § 5 Integrations** | `threadlight-design` — flags each system as `real | mock | hybrid` |
| **SPEC.md § 5b External Systems & Mocks** | `threadlight-design` — per-system MCP shape and tool list |
| **SPEC.md § 6 Tool Contracts** | `threadlight-design` — exact tool signatures the MCP server must expose |
| `src/agent/data/*.json` | `threadlight-demo-data-factory` — pre-generated sample data |
| **SPEC.md § 10b Triggers** | `threadlight-design` — tells you whether to also wire an event receiver (delegated to `threadlight-event-triggers`) |

| Produces | At |
|----------|-----|
| `src/mcp/server.py` | One MCP server per mocked system |
| `src/mcp/Dockerfile` | Build artifact for ACA |
| `src/mcp/requirements.txt` or `pyproject.toml` | Python deps |
| `infra/modules/aca-mcp.bicep` | ACA module — composed by `threadlight-deploy` (delegates to `azd-patterns` Bicep library) |
| `scripts/seed_mcp.py` | Idempotent reseed |
| `scripts/reset_mcp.py` | Demo recovery (<30s) |
| `mcp-config.json` entry | Wired into `src/agent/mcp-config.json` so the hosted agent can discover the MCP server |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Generates SPEC.md § 5 / § 5b / § 6 — the input contract |
| [**threadlight-demo-data-factory**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-demo-data-factory/) | Generates the JSON files this MCP server reads |
| [**threadlight-event-triggers**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-event-triggers/) | Pairs with this skill for webhook-fed MCP servers (event source → receiver → backing store → MCP read) |
| [**threadlight-deploy**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy/) | Composes the MCP ACA into the overall agent project (Phase 6 module composer) |
| [**azd-patterns**](../azd-patterns/) | Bicep module library — `aca-mcp.bicep` is one of the composable modules |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | The hosted agent that consumes the MCP server's tools |

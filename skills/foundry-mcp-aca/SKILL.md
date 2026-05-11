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

@description('Container image (in the ACR; pulled with the UAMI below)')
param image string

@description('Environment variables')
param env array = []

@description('User-assigned managed identity resource ID (for ACR pull + downstream RBAC)')
param userAssignedIdentityId string

@description('Container Registry name (no FQDN — just the resource name)')
param acrName string

resource mcpAca 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${userAssignedIdentityId}': {} }
  }
  properties: {
    managedEnvironmentId: containerAppEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8080
        // Use 'http' (HTTP/1.1 + Streamable HTTP) explicitly. 'auto' was
        // deprecated for new container apps in early 2026 — leaving it
        // here makes new revisions fail at deploy time with
        // `InvalidParameterValueInContainerTemplate`.
        transport: 'http'
      }
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: userAssignedIdentityId
        }
      ]
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
          // Liveness + startup probes — Foundry's MCP client only flips
          // the server "healthy" if /health returns 200; missing probes
          // mean cold-start tool calls 502 until the first scrape.
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 2
              periodSeconds: 3
              failureThreshold: 30
            }
          ]
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
| `logging/setLevel` returns -32601 Method not found | Server didn't implement the optional logging capability OR used wrong casing | Either implement the method per [MCP spec § Logging](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/logging) (camelCase `setLevel`) and declare `capabilities.logging`, or simply omit the capability — Foundry's MCP client tolerates servers that don't expose logging. |
| MCP connection timeout | ACA not started (cold start) | Runtime retries automatically; set `minReplicas: 1` for always-on |
| `invalid_payload` error | `${ENV_VAR}` in mcp-config.json not resolved → empty URL | Only include MCP servers with deployed endpoints. Remove entries with unresolved env vars. |
| Tools listed but calls fail | Tool call timeout (>100s) | Optimize tool implementation or increase ACA resources |
| `prompts/list` not implemented | Server doesn't handle this method | Return `{"prompts": []}` — agent-framework requires it |
| MCP container `404` log noise after demo | MAF client occasionally fires 1-3 stray POSTs to `/mcp` after `DELETE` of the session — the server is gone, so they 404. Cosmos calls succeeded; this is post-mortem chatter, not a runtime problem. | Either accept the noise (no functional impact) or suppress in the FastMCP server with a no-op handler that returns 204 for any POST hitting an unknown session id. Document for whoever reads `az containerapp logs show` so they don't chase it as a real bug. |

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

> **Highest-leverage pattern in the toolchain.** Discovered during the
> card-dispute v3 PoC: lifted recommendation quality from "junk packet
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
3/3" and "works 1/3" in the v3 PoC reproducibility runs. Models
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
| [**threadlight-design**](../threadlight-design/) | Generates SPEC.md § 5 / § 5b / § 6 — the input contract |
| [**threadlight-demo-data-factory**](../threadlight-demo-data-factory/) | Generates the JSON files this MCP server reads |
| [**threadlight-event-triggers**](../threadlight-event-triggers/) | Pairs with this skill for webhook-fed MCP servers (event source → receiver → backing store → MCP read) |
| [**threadlight-deploy**](../threadlight-deploy/) | Composes the MCP ACA into the overall agent project (Phase 6 module composer) |
| [**azd-patterns**](../azd-patterns/) | Bicep module library — `aca-mcp.bicep` is one of the composable modules |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | The hosted agent that consumes the MCP server's tools |

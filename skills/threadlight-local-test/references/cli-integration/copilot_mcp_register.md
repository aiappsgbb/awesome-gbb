# Pattern 1 — Register the PoC's MCP server with Copilot CLI / GHCP

Copilot CLI (and Cowork / Clawpilot when running atop it) supports
calling **arbitrary MCP servers** from natural-language prompts.
This makes the CLI itself the fastest tool-development loop for a
Threadlight PoC: write a tool, save the file, ask the CLI to call
it, read the JSON, fix the tool. No agent prompt to disentangle.

## One-time setup

```powershell
# 1. Run the PoC's MCP server in a dedicated terminal
cd <poc-root>/src/mcp_server
uv run python main.py
# Server binds to http://localhost:8000/mcp by default
```

In a separate terminal:

```powershell
# 2. Register the server with Copilot CLI (per-user, persists)
copilot mcp add <poc-name>-local --url http://localhost:8000/mcp

# 3. Verify the registration
copilot mcp list
# expected: <poc-name>-local  http://localhost:8000/mcp  enabled
```

## Use the tools from a CLI session

```powershell
copilot
# Inside the CLI prompt:
> /mcp <poc-name>-local list_tools
> Call list_open_disputes and show me the first 3 cases
> Now call get_case_evidence for the first case
> Find me a case where the timer is at risk of breaching Reg E §1005.11
```

The CLI invokes the local MCP tool directly. You see the raw JSON
response (or a CLI summary, depending on the prompt). Edit the
tool, save the file, re-ask — FastMCP picks up the new code on
the next call (no server restart needed if you launched with
`uv run python main.py --reload`).

## Authenticating to cloud Cosmos / Search from the local MCP

The most common Pattern-1 deployment: MCP runs on `localhost`, but
its tools read from cloud Cosmos / AI Search (not the emulator).
Because the local MCP process uses `DefaultAzureCredential`, it
inherits your `az` token.

```powershell
# Make sure you're in the right tenant (per azure-tenant-isolation)
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-tenants\dev"
az account show --query "{tenantId:tenantId, sub:name}" -o table

# Now start the MCP — it'll auth as you
cd <poc-root>/src/mcp_server
uv run python main.py
```

If the MCP fails with `403 Forbidden` against Cosmos, your user is
missing the **Cosmos DB Built-in Data Contributor** role
(`00000000-0000-0000-0000-000000000002`). Grant it:

```powershell
$cosmosId = az cosmosdb show -g <rg> -n <cosmos> --query id -o tsv
az cosmosdb sql role assignment create `
  --account-name <cosmos> -g <rg> `
  --role-definition-id 00000000-0000-0000-0000-000000000002 `
  --principal-id (az ad signed-in-user show --query id -o tsv) `
  --scope $cosmosId
```

(For non-prod tenants only — production data plane RBAC should be
managed via Bicep + UAMI per `foundry-hosted-agents`.)

## Removing / disabling

```powershell
copilot mcp remove <poc-name>-local
# Or to disable temporarily:
copilot mcp disable <poc-name>-local
```

## Anti-pattern: full-agent MCP

Don't expose the PoC's hosted agent itself as an MCP tool to
Copilot CLI. The CLI's own LLM is ALSO an agent, and stacking two
LLMs (CLI calls hosted agent, hosted agent calls MCP, ...) is slow,
expensive, and produces tangled traces. Use Pattern 1 for tool
development; Pattern 2 (`local_smoke.py`) for full-agent testing.

## Differences from `agent_framework.MCPStreamableHTTPTool`

The Copilot CLI's MCP client does NOT need the
`parse_tool_results=_mcp_text_extractor` workaround that
`agent_framework` requires (per `foundry-hosted-agents` § "MCP
Tools — recommended pattern"). The CLI's MCP renderer handles
`TextContent` correctly. So if the JSON looks fine in the CLI but
broken when called from the actual agent in Pattern 2 / 3, the
fix is in the agent's MCP tool config, not in the MCP server.

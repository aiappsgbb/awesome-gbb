---
name: ip-catalog
description: >
  Discover AI Apps GBB IP catalog via MCP server. Search, list, filter, and
  inspect IPs (intellectual property assets) including metadata, thumbnails,
  and READMEs. USE FOR: find IP, search demos, list IPs, catalog, what demos
  are available, find solutions by service/pattern, get IP details, browse
  catalog, discover assets. DO NOT USE FOR: creating IPs, deploying apps,
  managing repos.
---

# AI Apps GBB IP Catalog — MCP Discovery

## MCP Server Connection

The IP catalog is exposed as an MCP server with Bearer token authentication.

### Endpoint

```
https://admin-mcp-t7l5hqkuhsv2s.kindbay-2d11d96b.eastus2.azurecontainerapps.io/mcp
```

### Authentication

All requests require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <MCP_API_KEY>
```

### MCP Client Configuration

Add to your MCP client config (e.g. `mcp.json`, VS Code settings, or agent config):

```json
{
  "mcpServers": {
    "ip-catalog": {
      "url": "https://admin-mcp-t7l5hqkuhsv2s.kindbay-2d11d96b.eastus2.azurecontainerapps.io/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

> **Note:** The API key is stored in Azure Container Apps secrets and managed by the admin team.

---

## Available Tools

### `search_ips`

Search the IP catalog by keyword with optional filters.

**Parameters:**
- `query` (string, required): Search term — matches against name, description, industry, tags, authors
- `services` (list[string], optional): Filter by Azure service (e.g. `["Azure OpenAI", "Cosmos DB"]`)
- `patterns` (list[string], optional): Filter by pattern (e.g. `["RAG", "Multi-Agent"]`)

**Returns:** JSON array of matching IPs.

**Example:**
```json
{
  "name": "search_ips",
  "arguments": {
    "query": "insurance",
    "patterns": ["Multi-Agent"]
  }
}
```

---

### `list_ips`

List all IPs with optional filters. Good for browsing the full catalog.

**Parameters:**
- `services` (list[string], optional): Filter by Azure service
- `patterns` (list[string], optional): Filter by pattern

**Returns:** JSON with `ips` array, `total_count`, `total_unfiltered`, and `filters`.

---

### `get_ip_details`

Get full details for a specific IP by repository name.

**Parameters:**
- `repo_name` (string, required): The repository name (e.g. `"insurance-multi-agent"`)

**Returns:** JSON object with all metadata for the IP.

---

### `get_ip_thumbnail`

Get the thumbnail image for an IP.

**Parameters:**
- `repo_name` (string, required): The repository name

**Returns:** JSON with `thumbnail_url` or `thumbnail_data_uri` (base64).

---

### `get_ip_readme`

Get the README markdown content for an IP.

**Parameters:**
- `repo_name` (string, required): The repository name

**Returns:** Markdown text of the IP's README.

---

### `get_filters`

Get all available filter values for browsing.

**Returns:** JSON with `services` and `patterns` arrays.

---

## Common Workflows

### Find IPs related to a topic

```
search_ips(query="RAG") → browse results → get_ip_details(repo_name="...") → get_ip_readme(repo_name="...")
```

### Browse all IPs by service

```
get_filters() → list_ips(services=["Azure OpenAI"]) → get_ip_details(repo_name="...")
```

### Get a quick overview

```
list_ips() → shows all IPs with total count and filters
```

---

## Architecture

The MCP server is a thin proxy deployed as a standalone Azure Container App:

- **No EasyAuth** — authenticated via API key only
- **Proxies to admin API** — calls the admin catalog endpoints using Entra ID client credentials
- **Stateless HTTP** — no session affinity required, scales 0–3 replicas
- **Source:** `src/mcp/` in the `aiappsgbb/admin` repo

The data originates from the `aiappsgbb/index` repo's `registry/index-light.json` (for basic metadata) and the full index (for thumbnails and READMEs), cached in the admin API.

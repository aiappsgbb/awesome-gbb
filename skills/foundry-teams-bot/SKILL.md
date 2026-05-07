---
name: foundry-teams-bot
description: >
  Connect a Microsoft Foundry Hosted Agent to Microsoft Teams — generate the bot code,
  Bicep infrastructure, Teams manifest, and ACA deployment. Uses Azure Bot Service with
  UAMI auth and the microsoft-agents-* SDK.
  USE FOR: connect agent to Teams, Teams bot, Teams integration, expose agent in Teams,
  Teams channel, sideload Teams app, add Teams to Foundry agent, chat with agent in Teams.
  DO NOT USE FOR: designing the agent (use threadlight-design), deploying the hosted agent
  itself (use threadlight-deploy), general Bot Framework development.
---

# Foundry Teams Bot

Connect a **Microsoft Foundry Hosted Agent** to **Microsoft Teams** — generate all the
code, infrastructure, and manifest needed to chat with your agent directly in Teams.

## When to Use

Invoke this skill when the user wants to:
- Expose an existing Foundry hosted agent in Teams
- Add a Teams bot frontend to their deployed agent
- Generate bot.py, app.py, Dockerfile, Bicep, and Teams manifest
- Sideload a Foundry agent as a Teams app

## Prerequisites

- A **deployed Foundry Hosted Agent** (see `threadlight-deploy` or `foundry-hosted-agents` skills)
- An Azure subscription with Contributor access
- The agent's **Foundry project endpoint**

---

## Architecture

```
┌──────────────────────────┐
│  Microsoft Teams          │
│  (user sends message)     │
└────────┬─────────────────┘
         │ Bot Framework Protocol
         ▼
┌──────────────────────────┐
│  Azure Bot Service        │  ← F0 (free) SKU
│  (routing + auth)         │  ← UAMI as msaAppId
│  MsTeamsChannel enabled   │  ← msaAppType: UserAssignedMSI
└────────┬─────────────────┘
         │ POST /api/messages
         ▼
┌──────────────────────────┐
│  Copilot ACA              │  ← aiohttp web server (port 80)
│  copilot/bot.py           │  ← microsoft-agents-* SDK
│  - Receives Bot messages  │
│  - Calls Foundry API      │  ← AIProjectClient → oai.responses.create(stream=True)
│  - Streams response       │     with agent_name-bound client
│  - Sends to Teams         │
└────────┬─────────────────┘
         │ Responses API (streaming)
         ▼
┌──────────────────────────┐
│  Foundry Hosted Agent     │  ← Already deployed
│  (your agent container)   │
└──────────────────────────┘
```

---

## Directory Structure

Template files are in `templates/` — copy them into your project root:

```bash
cp -r templates/* <your-project>/
```

This adds:

```
copilot/
├── bot.py                      # Bot logic — receives messages, calls Foundry
├── app.py                      # aiohttp web server (SDK-managed Bot Framework auth)
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container for ACA deployment
└── teams_package/
    ├── manifest.json           # Teams app manifest (devPreview)
    ├── color.png               # 192×192 color icon (provide your own)
    └── outline.png             # 32×32 outline icon (provide your own)

infra/bot/
├── uami.bicep                  # User-Assigned Managed Identity
├── bot-service.bicep           # Azure Bot Service + MsTeamsChannel
└── aca.bicep                   # ACA environment + bot container app

scripts/
└── build_teams_manifest.py     # postprovision: builds copilot_package.zip
```

---

## Step 1: Gather Context

Ask the user for:
1. **Agent name** — the Foundry hosted agent name (e.g., `orchestrator`)
2. **Project endpoint** — Foundry project endpoint URL
3. **Display name** — how the bot appears in Teams (e.g., `Tech News Digest`)
4. **Developer/org name** — for the Teams manifest

---

## Step 2: Generate Bot Code

### `copilot/bot.py`

> **Template:** [`templates/copilot/bot.py`](templates/copilot/bot.py)

The bot MUST use the **refreshed preview invocation pattern** — agent-bound client.
Replace `__PROJECT_NAME__` with the Foundry agent name.

**Critical implementation notes:**
- Uses `get_openai_client(agent_name=...)` — the **refreshed preview** pattern
- Do NOT use `extra_body={"agent_reference": ...}` — that's the old pattern and silently fails
- `allow_preview=True` on `AIProjectClient` is REQUIRED for `agent_name` to work
- Collect all streaming chunks before sending — Teams garbles individual chunks
- `!reset` command clears stale conversations (break after agent version updates)
- Auto-retry on `server_error` by resetting thread_id

### `copilot/app.py`

> **Template:** [`templates/copilot/app.py`](templates/copilot/app.py)

aiohttp server with SDK-managed Bot Framework auth via `MsalConnectionManager`.

### `copilot/requirements.txt`

> **Template:** [`templates/copilot/requirements.txt`](templates/copilot/requirements.txt)

### `copilot/Dockerfile`

> **Template:** [`templates/copilot/Dockerfile`](templates/copilot/Dockerfile)

---

## Step 3: Generate Bicep Infrastructure

### `infra/bot/uami.bicep`

> **Template:** [`templates/infra/bot/uami.bicep`](templates/infra/bot/uami.bicep)

Creates a User-Assigned Managed Identity. Outputs: `id`, `clientId`, `principalId`.

### `infra/bot/bot-service.bicep`

> **Template:** [`templates/infra/bot/bot-service.bicep`](templates/infra/bot/bot-service.bicep)

Azure Bot Service (F0 SKU) with UAMI auth (`msaAppType: UserAssignedMSI`) and MsTeamsChannel.

### `infra/bot/aca.bicep`

> **Template:** [`templates/infra/bot/aca.bicep`](templates/infra/bot/aca.bicep)

Azure Container App with external ingress, UAMI identity, and env var injection.

### Bicep integration in `main.bicep`:

```bicep
// === UAMI ===
module uami 'bot/uami.bicep' = {
  name: 'uami'
  params: {
    name: 'id-${environmentName}'
    location: location
    tags: tags
  }
}

// === Azure Bot Service ===
module bot 'bot/bot-service.bicep' = {
  name: 'bot'
  params: {
    name: 'bot-${environmentName}'
    displayName: '__AGENT_NAME__'
    msaAppId: uami.outputs.clientId
    msaAppTenantId: tenant().tenantId
    msaAppMSIResourceId: uami.outputs.id
    messagesEndpoint: 'https://${copilotAca.outputs.fqdn}/api/messages'
    tags: tags
  }
}

// === Copilot ACA ===
module copilotAca 'bot/aca.bicep' = {
  name: 'copilot'
  params: {
    name: 'copilot-${environmentName}'
    image: '${acrEndpoint}/copilot:latest'
    targetPort: 80
    userAssignedIdentityId: uami.outputs.id
    env: [
      { name: 'AZURE_CLIENT_ID', value: uami.outputs.clientId }
      { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
      {
        name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID'
        value: uami.outputs.clientId
      }
      {
        name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID'
        value: tenant().tenantId
      }
      {
        name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE'
        value: 'UserManagedIdentity'
      }
    ]
    tags: tags
  }
}
```

---

## Step 4: Generate Teams Manifest

### `copilot/teams_package/manifest.json`

> **Template:** [`templates/copilot/teams_package/manifest.json`](templates/copilot/teams_package/manifest.json)

Uses `devPreview` schema with `copilotAgents.customEngineAgents` for custom engine agent bots.
Also provide **color.png** (192×192) and **outline.png** (32×32) icons in the same directory.

**Token replacement:**

| Token | Value | Source |
|-------|-------|--------|
| `__BOT_APP_ID__` | UAMI client ID (filled at postprovision) | Bicep output |
| `__AGENT_NAME__` | Display name | User input |
| `__AGENT_DESCRIPTION__` | One-line description | User input |
| `__DEVELOPER_NAME__` | Developer/org name | User input |

---

## Step 5: Build Teams Package Script

### `scripts/build_teams_manifest.py`

> **Template:** [`templates/scripts/build_teams_manifest.py`](templates/scripts/build_teams_manifest.py)

Replaces all placeholder tokens in manifest.json and packages into `copilot_package.zip` for sideloading.

### Wiring as azd postprovision hook

Add to `azure.yaml`:

```yaml
hooks:
  postprovision:
    shell: pwsh
    run: >
      python scripts/build_teams_manifest.py
    env:
      BOT_APP_ID: ${AZURE_BOT_APP_ID}
      AGENT_DISPLAY_NAME: "My Agent"
      AGENT_DESCRIPTION: "My agent description"
      DEVELOPER_NAME: "My Org"
```

`AZURE_BOT_APP_ID` is set by Bicep output → azd env during provisioning.

---

## Step 6: azure.yaml Integration

Add the copilot service to the project's `azure.yaml`:

```yaml
services:
  # ... existing hosted agent service ...

  copilot:
    project: ./copilot
    language: py
    host: containerapp
    docker:
      path: ./copilot/Dockerfile
      context: ./copilot
```

Or deploy manually:

```bash
# Build and push copilot image
az acr build --registry <your-acr> --image copilot:latest ./copilot/

# Create copilot ACA
az containerapp create \
    --name copilot-<env> \
    --resource-group <rg> \
    --environment <cae-id> \
    --image <acr>.azurecr.io/copilot:latest \
    --target-port 80 \
    --ingress external \
    --user-assigned <uami-resource-id> \
    --env-vars \
        AZURE_CLIENT_ID=<uami-client-id> \
        PROJECT_ENDPOINT=<foundry-endpoint> \
        CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID=<uami-client-id> \
        CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID=<tenant-id> \
        CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity
```

---

## Step 7: Sideload into Teams

1. Run `python scripts/build_teams_manifest.py` (or let postprovision hook run it)
2. Open **Microsoft Teams** → **Apps** → **Manage your apps**
3. Click **Upload an app** → **Upload a custom app**
4. Select `copilot_package.zip`
5. The bot appears in your personal chat list
6. Send a message to test

> **Note**: Sideloading must be enabled by your Teams admin. For production,
> publish via the Teams App Catalog or Microsoft AppSource.

---

## Environment Variables (Copilot ACA)

| Variable | Required | Purpose |
|----------|----------|---------|
| `AZURE_CLIENT_ID` | ✅ | UAMI client ID — used by `DefaultAzureCredential` |
| `PROJECT_ENDPOINT` | ✅ | Foundry project endpoint |
| `AGENT_NAME` | No | Hosted agent name (default from `__PROJECT_NAME__`) |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` | ✅ | UAMI client ID for Bot Framework MSAL auth |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID` | ✅ | Azure AD tenant ID |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE` | ✅ | Must be `UserManagedIdentity` |

---

## RBAC Requirements

The bot's UAMI needs these role assignments to call the Foundry Hosted Agent:

| Role | Scope | Purpose |
|------|-------|---------|
| `Azure AI Developer` | Foundry project | Create conversations, call Responses API |
| `Cognitive Services OpenAI User` | AI Services account | Use model deployments |
| `Cognitive Services User` | AI Services account | Access AI services |

---

## Gotchas & Hard-Won Lessons

| Issue | Cause | Fix |
|-------|-------|-----|
| Bot returns "Response could not be saved" | Old-style `agent_reference` invocation | Use `get_openai_client(agent_name=...)` with `allow_preview=True` |
| Bot auth 401 on /api/messages | UAMI not in CONNECTIONS__ env vars | Set all 3 `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` vars |
| Teams can't find bot | manifest botId mismatch | `botId` must equal UAMI client ID used as `msaAppId` |
| Streaming garbled in Teams | Sending each chunk separately | Collect all chunks, send as single message |
| Sideload fails | manifest schema wrong | Use `manifestVersion: "devPreview"` with `copilotAgents.customEngineAgents` |
| Bot crashes on first message | `PROJECT_ENDPOINT` not set | Must include full path: `https://acct.services.ai.azure.com/api/projects/proj` |
| Thread state lost between restarts | Using MemoryStorage | Switch to BlobStorage for production (`microsoft-agents-storage-blob`) |
| Bot SDK auth fails | Wrong `msaAppType` in bot.bicep | Must be `UserAssignedMSI` (not `SingleTenant` or `MultiTenant`) |
| Bot image overwritten on reprovision | Bicep resets container image | Use `fetch-container-image.bicep` + `SERVICE_BOT_RESOURCE_EXISTS` param |
| `server_error` in Teams | Stale conversation from previous agent version | Type `!reset` in Teams chat — bot auto-retries with fresh conversation |

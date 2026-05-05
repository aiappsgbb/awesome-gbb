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

Generate these files in the project:

```
copilot/
├── bot.py                      # Bot logic — receives messages, calls Foundry
├── app.py                      # aiohttp web server (JWT auth middleware)
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container for ACA deployment
└── teams_package/
    ├── manifest.json           # Teams app manifest (devPreview)
    ├── color.png               # 192×192 color icon
    └── outline.png             # 32×32 outline icon

infra/bot/
├── uami.bicep                  # User-Assigned Managed Identity
├── bot-service.bicep           # Azure Bot Service + MsTeamsChannel
├── aca.bicep                   # ACA environment + bot container app
└── fetch-container-image.bicep # Prevents image overwrite on reprovision

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

The bot MUST use the **refreshed preview invocation pattern** — agent-bound client:

```python
"""Teams bot that streams from a Foundry Hosted Agent."""

import json
import logging
import os
import traceback

from azure.ai.projects.aio import AIProjectClient
from azure.identity.aio import DefaultAzureCredential
from microsoft_agents.activity import Activity, ActivityTypes
from microsoft_agents.hosting.core import (
    AgentApplication,
    ConversationState,
    MemoryStorage,
    TurnContext,
    TurnState,
)

logger = logging.getLogger(__name__)

AGENT_NAME = os.getenv("AGENT_NAME", "__PROJECT_NAME__")
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")


class AgentBot(AgentApplication):
    """Teams bot that forwards messages to a Foundry Hosted Agent."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._storage = MemoryStorage()
        self._conversation_state = ConversationState(self._storage)
        self.on_activity(ActivityTypes.message, self._on_message)

    async def _on_message(self, context: TurnContext, state: TurnState) -> bool:
        """Handle incoming Teams message."""
        user_message = context.activity.text or ""
        if not user_message.strip():
            return True

        # Handle reset command
        if user_message.strip().lower() == "!reset":
            state["thread_id"] = None
            await context.send_activity(
                "🔄 Conversation reset. Send a new message to start fresh."
            )
            return True

        try:
            async with DefaultAzureCredential() as credential:
                async with AIProjectClient(
                    endpoint=PROJECT_ENDPOINT,
                    credential=credential,
                    allow_preview=True,  # REQUIRED for agent_name
                ) as project_client:
                    # Agent-bound client — routes to dedicated endpoint
                    oai = project_client.get_openai_client(
                        agent_name=AGENT_NAME
                    )

                    # Stream response from Foundry Hosted Agent
                    collected_text = []
                    stream = oai.responses.create(
                        input=user_message,
                        stream=True,
                    )

                    async for event in await stream:
                        if hasattr(event, "type"):
                            if event.type == "response.output_text.delta":
                                collected_text.append(event.delta)
                            elif event.type == "response.failed":
                                error = getattr(event.response, "error", None)
                                msg = _friendly_error(error)
                                await context.send_activity(msg)
                                return True

                    # Send collected response as single message
                    full_response = "".join(collected_text).strip()
                    if full_response:
                        await context.send_activity(full_response)
                    else:
                        await context.send_activity(
                            "🤔 I processed your request but didn't "
                            "generate a text response."
                        )

        except Exception as e:
            error_code = getattr(e, "code", "") or ""
            if "server_error" in str(error_code).lower():
                # Stale conversation — reset and retry
                state["thread_id"] = None
                logger.warning("server_error — resetting conversation")
                return await self._on_message(context, state)

            logger.error(
                "Error processing message: %s\n%s", e, traceback.format_exc()
            )
            await context.send_activity(
                f"⚠️ Something went wrong. Please try again.\n\n"
                f"Error: {type(e).__name__}: {e}"
            )

        return True


def _friendly_error(error) -> str:
    """Convert Foundry error to user-friendly message."""
    if not error:
        return "⚠️ An unexpected error occurred. Please try again."

    code = getattr(error, "code", "")
    msg = getattr(error, "message", str(error))

    if "content_filter" in code.lower() or "content_filter" in msg.lower():
        return "🚫 Your message was filtered by content safety policies. Please rephrase."
    if "rate_limit" in code.lower() or "429" in msg:
        return "⏳ The service is currently busy. Please wait a moment and try again."
    if "timeout" in code.lower():
        return "⏰ The request timed out. Please try a shorter question."

    return f"⚠️ Error: {msg}"
```

**Critical implementation notes:**
- Uses `get_openai_client(agent_name=...)` — the **refreshed preview** pattern
- Do NOT use `extra_body={"agent_reference": ...}` — that's the old pattern and silently fails
- `allow_preview=True` on `AIProjectClient` is REQUIRED for `agent_name` to work
- Collect all streaming chunks before sending — Teams garbles individual chunks
- `!reset` command clears stale conversations (break after agent version updates)
- Auto-retry on `server_error` by resetting thread_id

### `copilot/app.py`

```python
"""aiohttp web server for the Teams bot."""

import logging
import os

from aiohttp import web
from microsoft_agents.authentication.msal import MsalConnectionManager
from microsoft_agents.hosting.aiohttp import CloudAdapter, start_agent_process

from bot import AgentBot

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "80"))


def create_app() -> web.Application:
    """Create the aiohttp application with bot routes."""
    agent_configuration = MsalConnectionManager()
    adapter = CloudAdapter(agent_configuration)
    bot = AgentBot(adapter=adapter)
    app = start_agent_process(bot, adapter, agent_configuration)
    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)
```

### `copilot/requirements.txt`

```
# Microsoft Agents SDK (Bot Framework successor)
microsoft-agents-activity>=0.8.0
microsoft-agents-authentication-msal>=0.8.0
microsoft-agents-hosting-aiohttp>=0.8.0
microsoft-agents-hosting-core>=0.8.0
microsoft-agents-hosting-teams>=0.8.0
microsoft-agents-storage-blob>=0.8.0

# Azure AI
azure-ai-projects>=2.0.0
azure-identity>=1.19.0

# Web server
aiohttp>=3.9.0

# Logging
python-dotenv>=1.0.0
```

### `copilot/Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot.py app.py ./
COPY teams_package/ ./teams_package/

EXPOSE 80
CMD ["python", "app.py"]
```

---

## Step 3: Generate Bicep Infrastructure

### `infra/bot/uami.bicep`

```bicep
@description('Name of the User-Assigned Managed Identity')
param name string

@description('Location for the identity')
param location string = resourceGroup().location

@description('Tags for the resource')
param tags object = {}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: name
  location: location
  tags: tags
}

output id string = identity.id
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
output name string = identity.name
```

### `infra/bot/bot-service.bicep`

```bicep
@description('Name of the Azure Bot resource')
param name string

@description('Location for the Bot Service (use "global" for most scenarios)')
param location string = 'global'

@description('Bot display name in Teams')
param displayName string

@description('UAMI Client ID — used as msaAppId')
param msaAppId string

@description('UAMI Tenant ID')
param msaAppTenantId string

@description('UAMI Resource ID')
param msaAppMSIResourceId string

@description('Bot messages endpoint (e.g., https://<aca-fqdn>/api/messages)')
param messagesEndpoint string

@description('Tags for the resource')
param tags object = {}

resource bot 'Microsoft.BotService/botServices@2022-09-15' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'F0'
  }
  kind: 'azurebot'
  properties: {
    displayName: displayName
    endpoint: messagesEndpoint
    msaAppId: msaAppId
    msaAppType: 'UserAssignedMSI'
    msaAppTenantId: msaAppTenantId
    msaAppMSIResourceId: msaAppMSIResourceId
    schemaTransformationVersion: '1.3'
  }
}

resource teamsChannel 'Microsoft.BotService/botServices/channels@2022-09-15' = {
  parent: bot
  name: 'MsTeamsChannel'
  location: location
  properties: {
    channelName: 'MsTeamsChannel'
    properties: {
      isEnabled: true
    }
  }
}

output botId string = bot.properties.msaAppId
output botName string = bot.name
```

### `infra/bot/aca.bicep`

The ACA module should create a container app with external ingress on port 80,
the UAMI identity attached, and the required environment variables injected.

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

```json
{
    "$schema": "https://developer.microsoft.com/json-schemas/teams/vDevPreview/MicrosoftTeams.schema.json",
    "manifestVersion": "devPreview",
    "version": "1.0.0",
    "id": "__BOT_APP_ID__",
    "developer": {
        "name": "__DEVELOPER_NAME__",
        "websiteUrl": "https://example.com",
        "privacyUrl": "https://example.com/privacy",
        "termsOfUseUrl": "https://example.com/terms"
    },
    "name": {
        "short": "__AGENT_NAME__",
        "full": "__AGENT_DESCRIPTION__"
    },
    "description": {
        "short": "__AGENT_DESCRIPTION__",
        "full": "__AGENT_DESCRIPTION__"
    },
    "icons": {
        "color": "color.png",
        "outline": "outline.png"
    },
    "accentColor": "#0078D4",
    "copilotAgents": {
        "customEngineAgents": [
            {
                "type": "bot",
                "id": "__BOT_APP_ID__"
            }
        ]
    },
    "bots": [
        {
            "botId": "__BOT_APP_ID__",
            "scopes": ["personal"],
            "commandLists": [
                {
                    "scopes": ["personal"],
                    "commands": [
                        {
                            "title": "!reset",
                            "description": "Reset conversation and start fresh"
                        }
                    ]
                }
            ],
            "isNotificationOnly": false,
            "supportsCalling": false,
            "supportsVideo": false
        }
    ],
    "permissions": ["identity", "messageTeamMembers"],
    "validDomains": []
}
```

**Token replacement:**

| Token | Value | Source |
|-------|-------|--------|
| `__BOT_APP_ID__` | UAMI client ID (filled at postprovision) | Bicep output |
| `__AGENT_NAME__` | Display name | User input |
| `__AGENT_DESCRIPTION__` | One-line description | User input |
| `__DEVELOPER_NAME__` | Developer/org name | User input |

Also provide **color.png** (192×192) and **outline.png** (32×32) icons — use placeholder
images if the user doesn't provide custom ones.

---

## Step 5: Build Teams Package Script

### `scripts/build_teams_manifest.py`

```python
"""Build Teams manifest zip for sideloading (postprovision hook)."""

import json
import os
import zipfile
from pathlib import Path


def build_manifest(bot_client_id: str, agent_name: str, output_dir: str = "copilot"):
    """Build the Teams app package zip."""
    src = Path("copilot/teams_package")
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    manifest = json.loads((src / "manifest.json").read_text())
    manifest["id"] = bot_client_id
    manifest["copilotAgents"]["customEngineAgents"][0]["id"] = bot_client_id
    manifest["bots"][0]["botId"] = bot_client_id
    manifest["name"]["short"] = agent_name

    zip_path = out / "copilot_package.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for icon in ("color.png", "outline.png"):
            icon_path = src / icon
            if icon_path.exists():
                zf.write(icon_path, icon)

    print(f"Teams package: {zip_path}")
    return zip_path


if __name__ == "__main__":
    build_manifest(
        bot_client_id=os.environ.get("BOT_APP_ID", "<uami-client-id>"),
        agent_name=os.environ.get("AGENT_NAME", "My Agent"),
    )
```

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

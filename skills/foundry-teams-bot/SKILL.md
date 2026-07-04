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
metadata:
  version: "1.1.4"
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
    ├── manifest.json           # Teams app manifest (v1.21 — required for M365 Copilot CEA GA)
    ├── color.png               # 192×192 color icon (provide your own)
    └── outline.png             # 32×32 outline icon (provide your own)

infra/bot/
├── uami.bicep                  # User-Assigned Managed Identity
├── bot-service.bicep           # Azure Bot Service + MsTeamsChannel
├── aca.bicep                   # ACA environment + bot container app
├── bot-rbac.bicep              # Cross-resource RBAC: AcrPull + Foundry User on account+project
└── fetch-container-image.bicep # Re-provision safety — preserve existing image

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

### Invocations Protocol Agents (GHCP SDK)

> **If the hosted agent uses GHCP SDK (`InvocationAgentServerHost`)**, the bot
> CANNOT use `oai.responses.create()` — the Responses API returns 400/404.
> This only affects GHCP agents. MAF agents (ResponsesHostServer) work fine
> with the Responses API.

For GHCP agents, the bot must POST directly to the Invocations SSE endpoint
and parse the event stream:

```python
import aiohttp
import json

async def _invoke_invocations(endpoint: str, credential, agent_name: str, query: str) -> str:
    """Call a GHCP (Invocations protocol) hosted agent via SSE."""
    token = await credential.get_token("https://ai.azure.com/.default")
    url = f"{endpoint}/agents/{agent_name}/endpoint/protocols/invocations?api-version=v1"

    message_text = ""
    delta_text = ""

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"input": query},
            headers={
                "Authorization": f"Bearer {token.token}",
                "Foundry-Features": "HostedAgents=V1Preview",
            },
            timeout=aiohttp.ClientTimeout(total=600),
        ) as resp:
            async for line_bytes in resp.content:
                line = line_bytes.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])
                etype = event.get("type", "")
                content = event.get("data", {}).get("content", "")
                if etype == "assistant.message" and content:
                    message_text += content
                elif etype == "assistant.message_delta" and content:
                    delta_text += content

    return message_text if message_text else delta_text
```

**In `on_message`**, replace `oai_client.responses.create(...)` with:
```python
response_text = await _invoke_invocations(
    PROJECT_ENDPOINT, credential, AGENT_NAME, user_message
)
if response_text:
    await context.send_activity(response_text)
```

**Which pattern to use:**

| Agent Runtime | Bot Pattern | Template |
|--------------|-------------|----------|
| **Either** (recommended) | Streaming to Teams + dual protocol | [`templates/copilot/bot-streaming.py`](templates/copilot/bot-streaming.py) |
| **MAF** (ResponsesHostServer) | Non-streaming, collect-then-send | [`templates/copilot/bot.py`](templates/copilot/bot.py) |
| **GHCP SDK** (InvocationAgentServerHost) | Non-streaming, collect-then-send | [`templates/copilot/bot-invocations.py`](templates/copilot/bot-invocations.py) |

### Teams Streaming (`bot-streaming.py`) — Recommended

> **Template:** [`templates/copilot/bot-streaming.py`](templates/copilot/bot-streaming.py)

The streaming template uses `context.streaming_response` (Agents SDK ≥0.9.0) to
progressively update the Teams message as chunks arrive from the agent. This gives
users real-time feedback during long queries (2-5 min for CI scans).

**Requires:** `microsoft-agents-hosting-core>=0.9.0` (see `requirements.txt`)

**Supports both protocols** via `AGENT_PROTOCOL` env var (`responses` | `invocations`):
- **Responses API** — `oai.responses.create(stream=True)` → yields `response.output_text.delta`
- **Invocations SSE** — HTTP POST to `/protocols/invocations` → yields `assistant.message_delta`

**How Teams streaming works:**

```python
@AGENT_APP.activity("message")
async def on_message(context, state):
    sr = context.streaming_response
    sr.queue_informative_update("⏳ Working on your request...")
    sr.set_generated_by_ai_label(True)

    async for chunk in agent_stream_generator(query):
        sr.queue_text_chunk(chunk)

    await sr.end_stream()
```

**Wire protocol:**
1. `typing` + `stream_type="informative"` → "Working..." placeholder
2. `typing` + `stream_type="streaming"` + incrementing `stream_sequence` → progressive chunks
3. `message` + `stream_type="final"` → permanent message

**Constraints:**
- Teams enforces **~1s interval** between streaming updates (SDK handles this automatically)
- **Agentic/Copilot requests** don't support streaming yet (`_is_streaming_channel=False`) — chunks are buffered and sent as one final message
- **Bot Framework Emulator** is non-streaming — same buffering behavior
- WebChat/DirectLine channels stream at 0.5s interval

**`StreamingResponse` API reference** (Agents SDK ≥0.9.0):

| Method | Description |
|--------|-------------|
| `queue_informative_update(text)` | Status text before content starts ("Thinking...") |
| `queue_text_chunk(text, citations?)` | Partial text chunk — auto-accumulated |
| `await end_stream()` | Sends final message — **must be awaited** |
| `set_generated_by_ai_label(True)` | Adds "Generated by AI" label |
| `set_feedback_loop(True)` | Enables thumbs-up/down in Teams |
| `set_citations([Citation(...)])` | Adds AI citations to final message |
| `set_attachments([Attachment(...)])` | Adds attachments to final message |
| `get_message()` | Returns accumulated text so far |

### Stream Cancellation Fallback (CRITICAL for long queries)

Teams cancels streams after **~2 minutes** by sending `403 ContentStreamNotAllowed`.
The SDK catches this and sets `sr._cancelled = True`. After cancellation, no more
streaming chunks can reach the user.

**What gets cancelled:** Only the **Teams streaming display** — the Foundry agent
stream between bot→agent continues uninterrupted. The bot keeps receiving chunks
from the agent, it just can't stream them to Teams anymore.

**The `bot-streaming.py` template handles this automatically:**

```python
async for event in gen:
    # Check on EVERY event, not just TextChunk
    # (tool calls have 10-30s gaps with no text — must check during those too)
    if not stream_cancelled and sr._cancelled:
        stream_cancelled = True
        await context.send_activity("⏳ Still working — full answer coming shortly...")

    if isinstance(event, TextChunk):
        accumulated_text += event.text
        if not stream_cancelled:
            sr.queue_text_chunk(event.text)
    # ... StatusUpdate, SessionComplete ...

# After generator completes:
if stream_cancelled:
    await context.send_activity(accumulated_text)  # Full response as regular message
else:
    await sr.end_stream()

# Then deliver files
if session_id:
    await _send_session_files(context, session_id)
```

**Common mistake:** Only checking `sr._cancelled` after `queue_text_chunk()`. During
tool calls (web search, Playwright), no text chunks flow for 10-30s. If the 403
arrives during a tool call, you won't detect it until text resumes — by then the
user has been staring at a dead screen for minutes. **Check on every event type.**

### `copilot/app.py`

> **Template:** [`templates/copilot/app.py`](templates/copilot/app.py)

aiohttp server with SDK-managed Bot Framework auth via `MsalConnectionManager`.

**⚠️ Critical pattern:** Use `Application(middlewares=[jwt_authorization_middleware])` with
a manual `entry_point()` handler that calls `start_agent_process(req, agent, adapter)`.
Do NOT use `start_agent_process()` at the application level — it must be called per-request.
Older samples may show a different pattern — the template has the working approach.

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

> **Private-ACR pull is required.** The template's `properties.configuration.registries`
> block binds the bot's UAMI to the ACR login server so ACA can pull the bot image. You
> MUST pass `acrLoginServer` (e.g. `myacr.azurecr.io`) as a module param. Without it, the
> first revision will fail with `UNAUTHORIZED` against the private registry, ACA falls
> back to the placeholder image, and the bot looks "running" but never serves real traffic.

### `infra/bot/bot-rbac.bicep`

> **Template:** [`templates/infra/bot/bot-rbac.bicep`](templates/infra/bot/bot-rbac.bicep)

Cross-resource role grants for the bot UAMI. Three assignments wired in one module:

| # | Role | Scope | GUID | Why |
|---|------|-------|------|-----|
| 1 | AcrPull | ACR | `7f951dda-…` | Pull the bot container image |
| 2 | Foundry User | Foundry account | `53ca6127-…` | Model inference data-plane (post-May-2026 rename of `Azure AI User`) |
| 3 | Foundry User | Foundry project | `53ca6127-…` | Storage, history, Responses API project endpoint |

Role IDs are pinned by GUID so the May 2026 display-name rename (`Azure AI User` →
`Foundry User`) doesn't break the deploy. **Both account AND project scopes are
required** — `Foundry Account Owner` no longer implies data-plane access.

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
    acrLoginServer: acrEndpoint
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

> [!CAUTION]
> **🚨 `AUTHTYPE=UserManagedIdentity` is NOT optional.**
>
> If you forget this single env var, the bot looks healthy from outside
> (ACA Running, JWT middleware returns 401 on synthetic probes,
> `safe-check` channel probe returns `OK_jwt_alive`) but **every real
> Teams message returns HTTP 500** with `AADSTS7000216: 'client_assertion',
> 'client_secret' or 'request' is required for the 'client_credentials'
> grant type` in the bot logs. This happens because the
> `microsoft-agents-*` SDK defaults to **ConfidentialClient** (which
> wants a client secret you don't have, since the deploy is keyless),
> instead of switching to **UserAssignedManagedIdentity** flow.
>
> **All FOUR** `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` env vars
> must be present. Missing any one is a deploy bug:
> - `CLIENTID` — UAMI client ID
> - `TENANTID` — tenant
> - `AUTHORITYENDPOINT` — Entra login endpoint
> - **`AUTHTYPE` — must be literal string `UserManagedIdentity`** (not
>   `UserAssignedManagedIdentity`, not `ManagedIdentity`)
>
> The post-deploy gate (`threadlight-safe-check --phase post-deploy`)
> includes a behavioural check (`bot_auth_health`) that verifies this
> when `Bot Service.appType == UserAssignedMSI`. Run it before declaring
> the bot ready. (Observed in recent pilots after hours of "why
> won't Teams reach my bot" debugging.)

---

## Step 4: Generate Teams Manifest

### `copilot/teams_package/manifest.json`

> **Template:** [`templates/copilot/teams_package/manifest.json`](templates/copilot/teams_package/manifest.json)

Uses `1.21` schema with `copilotAgents.customEngineAgents` for custom engine agent bots
(M365 Copilot CEA went GA in May 2025 and **requires manifest version 1.21 or later** —
`devPreview` is no longer accepted by the Teams admin center for new uploads).

**Bot scopes are `["personal", "copilot"]`.** Per the Microsoft Learn validation
guidelines for agents, "Custom engine agents must include `copilot` in `bot.scopes`
and `bot.commandList.scopes` to ensure proper surfacing and full platform support."
`personal` is required for 1:1 chat in Teams; `copilot` is required for the Microsoft
365 Copilot Chat surface. Both nodes (`bot.scopes` AND `bot.commandLists[].scopes`)
must match. Add `"team"` only if your bot needs channel-mention support; do NOT add
`"groupChat"` because prompt starters are documented as "only supported for one-on-one
chat bots".

**Prompt starters live in `bots[0].commandLists[0].commands[]`**, NOT in a
`conversationStarters` array. The Teams v1.21 schema declares `additionalProperties:
false` on each `customEngineAgents` item with only `id` + `type` allowed — adding
`conversationStarters` there causes schema-invalid manifests that Teams admin center
rejects at sideload. The correct field per Microsoft Learn ("Create prompt suggestions"
— bots/how-to/conversations/prompt-suggestions) is a `{title, description}` entry in
`commandLists[].commands[]`. The template ships with 3 placeholder slots
`__STARTER_<N>_TITLE__` / `__STARTER_<N>_PROMPT__` (alongside the built-in `!reset`
command). `build_teams_manifest.py` reads `STARTER_<N>_TITLE` / `STARTER_<N>_PROMPT`
env vars (N=1..3): present → replaces the placeholder; absent → strips the placeholder
slot entirely so the bot ships only with `!reset`.

Also provide **color.png** (192×192) and **outline.png** (32×32) icons in the same directory.

**Token replacement:**

| Token | Value | Max Length | Source |
|-------|-------|-----------|--------|
| `__BOT_APP_ID__` | UAMI client ID (filled at postprovision) | — | Bicep output |
| `__AGENT_NAME__` | Short display name | **30 chars** | User input |
| `__AGENT_NAME_FULL__` | Full display name | **100 chars** | User input |
| `__AGENT_DESCRIPTION_SHORT__` | Short description | **80 chars** | User input |
| `__AGENT_DESCRIPTION__` | Full description | 4000 chars | User input |
| `__DEVELOPER_NAME__` | Developer/org name | — | User input |

> **Teams manifest has strict length limits.** The build script auto-truncates,
> but keep descriptions concise to avoid cut-off text.

> **File delivery:** If the agent generates downloadable files (reports, exports),
> add `"supportsFiles": true` to the `bots[0]` object in the manifest. This enables
> the FileConsentCard flow (see [Sending Files to Teams](#sending-files-to-teams)).

---

## Step 5: Build Teams Package Script

### `scripts/build_teams_manifest.py`

> **Template:** [`templates/scripts/build_teams_manifest.py`](templates/scripts/build_teams_manifest.py)

Replaces all placeholder tokens in manifest.json and packages into `copilot_package.zip` for sideloading.

> **⚠️ Silent-placeholder trap.** The script MUST fail loudly if `BOT_APP_ID` is
> empty or still a placeholder (e.g., `<uami-client-id>`). A silent fallback produces
> a zip that passes `azd deploy` without error but fails Teams schema validation at
> sideload time: `String "<uami-client-id>" does not match regex pattern
> "^[0-9a-fA-F]{8}-..."` on `id`, `copilotAgents[0].id`, and `bots[0].botId`.
> The template now includes a guard: `if not bot_id or bot_id.startswith("<"):
> raise SystemExit(...)`. For manual runs outside `azd up`:
> `$env:BOT_APP_ID = azd env get-value BOT_APP_ID`.

### Wiring as azd postprovision hook (REQUIRED)

> **This is NOT optional.** Without the postprovision hook, the Teams manifest
> won't be built and sideloading will fail.

Add to `azure.yaml` hooks section:

```yaml
hooks:
  postprovision:
    shell: pwsh
    run: >
      python src/bot/build_manifest.py
    env:
      BOT_APP_ID: ${AZURE_BOT_APP_ID}
      AGENT_DISPLAY_NAME: "My Agent"
      AGENT_DESCRIPTION: "My agent description"
      DEVELOPER_NAME: "My Org"
```

`AZURE_BOT_APP_ID` comes from Bicep output — `bot-service.bicep` must output:
```bicep
output botId string = bot.properties.msaAppId
```
azd automatically maps Bicep outputs to env vars in hooks.

---

## Step 6: azure.yaml Integration

Add the bot service to the project's `azure.yaml`:

```yaml
services:
  # ... existing hosted agent service ...

  bot:
    project: ./src/bot
    language: py
    host: containerapp
    docker:
      path: ./src/bot/Dockerfile
      context: ./src/bot
      remoteBuild: true
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

## Re-Provision Safety

> **Template:** [`templates/infra/bot/fetch-container-image.bicep`](templates/infra/bot/fetch-container-image.bicep)

On re-provision, Bicep will overwrite the bot ACA's image with a blank default.
To prevent this, use `fetch-container-image.bicep` with a `botAppExists` parameter:

```bicep
// In main.bicep:
param botAppExists bool  // azd manages this automatically

module fetchBotImage 'bot/fetch-container-image.bicep' = {
  name: 'fetch-bot-image'
  params: {
    exists: botAppExists
    name: 'bot-${environmentName}'
  }
}

// Pass the preserved image to aca.bicep:
module botAca 'bot/aca.bicep' = {
  params: {
    image: botAppExists ? fetchBotImage.outputs.image : '${acrEndpoint}/bot:latest'
    // ... other params
  }
}
```

## Main Bicep Wiring

The bot modules must be called from `main.bicep` and wired together:

```bicep
// 1. UAMI
module uami 'bot/uami.bicep' = { params: { name: 'id-${environmentName}' } }

// 2. Bot Service
module bot 'bot/bot-service.bicep' = {
  params: {
    name: 'bot-${environmentName}'
    displayName: '__AGENT_NAME__'
    msaAppId: uami.outputs.clientId
    msaAppTenantId: tenant().tenantId
    msaAppMSIResourceId: uami.outputs.id
    messagesEndpoint: 'https://${botAca.outputs.fqdn}/api/messages'
  }
}

// 3. RBAC — AcrPull on ACR + Foundry User on account AND project
// (see infra/bot/bot-rbac.bicep for the role-GUID + dual-scope rationale)
module botRbac 'bot/bot-rbac.bicep' = {
  name: 'bot-rbac'
  params: {
    botPrincipalId: uami.outputs.principalId
    acrName: acrName
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
  }
}

// 5. Bot ACA
module botAca 'bot/aca.bicep' = {
  params: {
    name: 'bot-${environmentName}'
    image: botAppExists ? fetchBotImage.outputs.image : '${acrEndpoint}/bot:latest'
    userAssignedIdentityId: uami.outputs.id
    acrLoginServer: acrEndpoint
    env: [
      { name: 'AZURE_CLIENT_ID', value: uami.outputs.clientId }
      { name: 'PROJECT_ENDPOINT', value: projectEndpoint }
      { name: 'FOUNDRY_AGENT_NAME', value: '__PROJECT_NAME__' }
      { name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID', value: uami.outputs.clientId }
      { name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID', value: tenant().tenantId }
      { name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE', value: 'UserManagedIdentity' }
    ]
  }
}

// 6. Output bot app ID for postprovision hook
output AZURE_BOT_APP_ID string = uami.outputs.clientId
```

---

## Step 7: Sideload into Teams

1. Run `python src/bot/build_manifest.py` (or let postprovision hook run it)
2. Open **Microsoft Teams** → **Apps** → **Manage your apps**
3. Click **Upload an app** → **Upload a custom app**
4. Select `copilot_package.zip`
5. The bot appears in your personal chat list
6. Send a message to test

> **Note**: Sideloading must be enabled by your Teams admin. For production,
> publish via the Teams App Catalog or Microsoft AppSource.

---

## Testing via DirectLine (Smoke Test)

Before sideloading into Teams, test the bot directly via the Azure Bot Service's
**DirectLine** channel. This works from any HTTP client — no Teams needed.

### 1. Get the DirectLine secret

In the Azure Portal → Bot Service → **Channels** → **Direct Line** → copy the **Secret key**.

Or via CLI:
```bash
az bot directline show --name <bot-name> --resource-group <rg> --with-secrets true \
  --query "properties.properties.sites[0].key" -o tsv
```

### 2. Start a conversation

```bash
# Start conversation
CONVERSATION=$(curl -s -X POST \
  https://directline.botframework.com/v3/directline/conversations \
  -H "Authorization: Bearer <DIRECTLINE_SECRET>" \
  -H "Content-Type: application/json" | jq -r '.conversationId')

echo "Conversation: $CONVERSATION"
```

### 3. Send a message

```bash
curl -s -X POST \
  "https://directline.botframework.com/v3/directline/conversations/${CONVERSATION}/activities" \
  -H "Authorization: Bearer <DIRECTLINE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"type": "message", "from": {"id": "smoke-test"}, "text": "Hello, what can you do?"}'
```

### 4. Read response

```bash
curl -s \
  "https://directline.botframework.com/v3/directline/conversations/${CONVERSATION}/activities" \
  -H "Authorization: Bearer <DIRECTLINE_SECRET>" | jq '.activities[-1].text'
```

### 5. Check bot logs

If the bot doesn't respond, check the ACA container logs:

```bash
# Stream logs from bot ACA
az containerapp logs show --name <bot-aca-name> --resource-group <rg> --follow

# Or via portal: Container Apps → bot ACA → Log stream
```

Common issues visible in logs:
- `MsalConnectionManager` errors → CONNECTIONS__ env vars missing or wrong
- `Agent not reachable` → hosted agent not deployed or RBAC not propagated
- `401 Unauthorized` → UAMI missing roles on Foundry project
- `ConnectionError` → PROJECT_ENDPOINT wrong or ACA can't reach Foundry

---

## Environment Variables (Copilot ACA)

| Variable | Required | Purpose |
|----------|----------|---------|
| `AZURE_CLIENT_ID` | ✅ | UAMI client ID — used by `DefaultAzureCredential` |
| `PROJECT_ENDPOINT` | ✅ | Foundry project endpoint |
| `AGENT_NAME` | No | Hosted agent name (default from `__PROJECT_NAME__`) |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID` | ✅ | UAMI client ID for Bot Framework MSAL auth |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID` | ✅ | Azure AD tenant ID |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHORITYENDPOINT` | ✅ | Entra login endpoint (`environment().authentication.loginEndpoint` in Bicep) |
| `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE` | ✅✅ | **MANDATORY** — must be literal `UserManagedIdentity`. Without it, MSAL falls back to ConfidentialClient → AADSTS7000216 on every real Teams message. The synthetic JWT probe in `safe-check` does NOT catch this (JWT middleware fires before outbound token acquisition). |

---

## RBAC Requirements

The bot's UAMI needs these role assignments to call the Foundry Hosted Agent:

| Role | GUID (pin this — names rotate) | Scope | Purpose |
|------|------------------------------|-------|---------|
| `Foundry User` (was `Azure AI User` pre-May 2026) | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | Foundry **account** | Data-plane: model inference. **Required since rename — `Foundry Account Owner` no longer implies this.** |
| `Foundry User` | `53ca6127-db72-4b80-b1b0-d745d6d5456d` | Foundry **project** | Conversations, sessions, history, Responses API project endpoint |
| `AcrPull` | `7f951dda-4ed3-4680-a7ca-43fe172d538d` | Azure Container Registry | Pull the bot container image (paired with `registries` block in `aca.bicep`) |

> Both account AND project scopes are required. `bot-rbac.bicep` wires all three
> in one module — call it from `main.bicep` (see "Main Bicep Wiring" above).

---

## User Identity

The Teams user's identity is available from the incoming activity. This is **NOT OBO**
(On-Behalf-Of) — just metadata from the Bot Framework activity.

Useful when the agent needs to filter data by user (e.g., "show MY orders") or for
audit logging.

**Available fields on `context.activity.from_property`:**

| Field | Value | Example |
|-------|-------|---------|
| `id` | Teams user ID | `29:U1a2b3c...` |
| `name` | Display name | `John Smith` |
| `aad_object_id` | Azure AD UUID | `12345678-abcd-...` |

**Example — reading identity:**

```python
user = context.activity.from_property
if user:
    user_name = user.name              # "John Smith"
    aad_id = user.aad_object_id        # Azure AD UUID
    logger.info(f"Message from {user_name} (AAD: {aad_id})")
```

**If the agent needs user context** (e.g., for data filtering), the bot can inject
the identity into the prompt. This is optional — only do it when the business process
requires user-scoped data:

```python
agent_input = f"[User: {user_name}] {user_message}"
```

> To resolve UPN (email) from `aad_object_id`, you'd need a Graph API call —
> that's a separate concern, not covered here.

---

## Sending Files to Teams

### Pattern 1: FileConsentCard (recommended, personal chat)

The proper way to send files from bot to Teams. The bot asks user for permission
to upload, then writes the file to the user's OneDrive. The user sees a clickable
file card they can preview or download.

> **Limitation:** Only works in `personal` context (1:1 chat), NOT channels or group chats.
> Requires `supportsFiles: true` in the Teams manifest.

**Flow:** Agent generates file → bot downloads from session files API → bot sends
FileConsentCard → user accepts → bot uploads to OneDrive URL → bot sends FileCard.

#### Step 1: Add `supportsFiles` to manifest

In the `bots` array of `manifest.json`:

```json
{
  "botId": "__BOT_APP_ID__",
  "scopes": ["personal"],
  "supportsFiles": true,
  ...
}
```

#### Step 2: Pending-file cache and consent card sender

The bot must hold file bytes in memory between sending the consent card and receiving
the invoke callback. Use a simple dict keyed by UUID:

```python
import uuid
from microsoft_agents.activity import Activity, ActivityTypes, Attachment, InvokeResponse

REPORT_EXTENSIONS = {".xlsx", ".csv", ".html", ".json", ".md", ".txt", ".pdf"}

# Pending files awaiting user consent (file_id → (filename, bytes))
_pending_files: dict[str, tuple[str, bytes]] = {}


async def _send_session_files(context, session_id: str):
    """Download generated files from the agent session and offer via FileConsentCard."""
    cred = DefaultAzureCredential()
    token = await cred.get_token("https://ai.azure.com/.default")
    await cred.close()

    headers = {
        "Authorization": f"Bearer {token.token}",
        "Foundry-Features": "HostedAgents=V1Preview",
    }

    async with aiohttp.ClientSession() as http:
        list_url = (
            f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions"
            f"/{session_id}/files?api-version=v1&path=."
        )
        async with http.get(list_url, headers=headers) as resp:
            if resp.status != 200:
                return
            files_data = await resp.json()

        for entry in files_data.get("entries", []):
            name = entry.get("name", "")
            ext = ("." + name.rsplit(".", 1)[-1]).lower() if "." in name else ""
            if ext not in REPORT_EXTENSIONS:
                continue

            dl_url = (
                f"{PROJECT_ENDPOINT}/agents/{AGENT_NAME}/endpoint/sessions"
                f"/{session_id}/files/content?api-version=v1&path={name}"
            )
            async with http.get(dl_url, headers=headers) as resp:
                if resp.status != 200:
                    continue
                content = await resp.read()

            # Store file and send FileConsentCard
            file_id = str(uuid.uuid4())
            _pending_files[file_id] = (name, content)

            consent_card = Attachment(
                content_type="application/vnd.microsoft.teams.card.file.consent",
                name=name,
                content={
                    "description": f"Agent-generated report ({len(content):,} bytes)",
                    "sizeInBytes": len(content),
                    "acceptContext": {"file_id": file_id, "filename": name},
                    "declineContext": {"file_id": file_id},
                },
            )
            await context.send_activity(
                Activity(type=ActivityTypes.message, attachments=[consent_card])
            )
```

#### Step 3: Invoke handler for file consent

Register an invoke handler in the `setup()` function alongside the message handler:

```python
@AGENT_APP.activity("invoke")
async def on_invoke(context: TurnContext, state: TurnState):
    if context.activity.name == "fileConsent/invoke":
        await _handle_file_consent(context)
    else:
        # Acknowledge unknown invokes to avoid Teams errors
        await context.send_activity(
            Activity(type=ActivityTypes.invoke_response, value=InvokeResponse(status=200))
        )


async def _handle_file_consent(context):
    """Handle fileConsent/invoke — upload on accept, clean up on decline."""
    value = context.activity.value or {}
    action = value.get("action", "")
    accept_ctx = value.get("context") or value.get("acceptContext") or {}
    file_id = accept_ctx.get("file_id", "")
    upload_info = value.get("uploadInfo") or value.get("upload_info") or {}

    if action == "accept":
        if file_id not in _pending_files:
            await context.send_activity("⚠️ File expired — please regenerate the report.")
            return

        filename, content = _pending_files.pop(file_id)
        upload_url = upload_info.get("uploadUrl") or upload_info.get("upload_url", "")

        if not upload_url:
            await context.send_activity("⚠️ No upload URL received from Teams.")
            return

        # Upload to OneDrive (simple PUT for files < 4 MB)
        async with aiohttp.ClientSession() as http:
            put_headers = {
                "Content-Type": "application/octet-stream",
                "Content-Range": f"bytes 0-{len(content) - 1}/{len(content)}",
            }
            async with http.put(upload_url, data=content, headers=put_headers) as resp:
                if resp.status not in (200, 201):
                    await context.send_activity(f"⚠️ Upload failed ({resp.status}).")
                    return

        # Send FileInfoCard — Teams renders this as a clickable file
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "file"
        file_card = Attachment(
            content_type="application/vnd.microsoft.teams.card.file.info",
            name=filename,
            content_url=upload_info.get("contentUrl") or upload_info.get("content_url", ""),
            content={
                "uniqueId": upload_info.get("uniqueId") or upload_info.get("unique_id", ""),
                "fileType": ext,
            },
        )
        await context.send_activity(
            Activity(type=ActivityTypes.message, attachments=[file_card])
        )

    elif action == "decline":
        _pending_files.pop(file_id, None)
        await context.send_activity("File upload cancelled.")

    # Always send invoke response to acknowledge
    await context.send_activity(
        Activity(type=ActivityTypes.invoke_response, value=InvokeResponse(status=200))
    )
```

#### Step 4: Wire into the message handler

After the streaming response completes, check for session files:

```python
# In on_message, after sr.end_stream():
if agent_session_id:
    await _send_session_files(context, agent_session_id)
```

The `agent_session_id` comes from the `response.completed` event (Responses protocol):

```python
elif event_type == "response.completed":
    resp = getattr(event, "response", None)
    if resp:
        sid = getattr(resp, "agent_session_id", None)
        if sid:
            yield SessionInfo(session_id=sid)
```

> **Validated pattern** — tested with XLSX (openpyxl) and PDF (fpdf2) file delivery
> in recent file-delivery pilots. Files appear as clickable OneDrive cards in
> Teams with preview support.

### Downloading files from Foundry session

Both patterns need to get files from the agent session first:

```python
async def _download_session_file(session_id: str, filename: str) -> bytes:
    """Download a file from the Foundry agent session."""
    cred = DefaultAzureCredential()
    token = await cred.get_token("https://ai.azure.com/.default")
    await cred.close()

    endpoint = os.environ["PROJECT_ENDPOINT"]
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Foundry-Features": "HostedAgents=V1Preview",
    }
    url = f"{endpoint}/agents/{AGENT_NAME}/endpoint/sessions/{session_id}/files/content?api-version=v1&path={filename}"
    async with aiohttp.ClientSession() as http:
        async with http.get(url, headers=headers) as resp:
            return await resp.read()
```

### Listing session files

```python
list_url = f"{endpoint}/agents/{AGENT_NAME}/endpoint/sessions/{session_id}/files?api-version=v1&path=."
# Returns: {"entries": [{"name": "report.csv", "size": 1234}, ...]}
```

### Fallback: Inline code blocks (text-only, primitive)

For small text files (<28KB) where FileConsentCard isn't available (e.g., group chats),
fall back to inline code blocks. Only useful for plain text or code snippets:

```python
if len(content) < 28000:
    text = content.decode("utf-8", errors="replace")
    await context.send_activity(f"📎 **{name}**\n\n```\n{text[:20000]}\n```")
```

> This is a last-resort fallback — not suitable for binary files, images, or reports.

---

## Receiving Files from Teams (investigation notes)

When a user sends a file in Teams personal chat, the bot receives an activity with
attachments. The file is uploaded to the user's OneDrive automatically by Teams.

```python
if context.activity.attachments:
    for att in context.activity.attachments:
        if att.content_type == "application/vnd.microsoft.teams.file.download.info":
            filename = att.name
            download_url = att.content.get("downloadUrl")  # Pre-signed URL

            # Download the file (no extra auth needed — URL is pre-signed)
            async with aiohttp.ClientSession() as http:
                async with http.get(download_url) as resp:
                    file_bytes = await resp.read()

            # Forward to agent as context
            agent_input = f"User uploaded file '{filename}' ({len(file_bytes)} bytes). Content: {file_bytes.decode('utf-8', errors='replace')[:5000]}"
```

> **Status: Investigation only.** This pattern documents how file attachments arrive.
> Forwarding binary files to the Foundry agent's Responses API (which expects text input)
> needs further design — likely upload to blob storage and pass URL, or base64-encode
> for small files.

---

## Future: OBO Authentication (investigation — NOT TESTED)

> [!WARNING]
> **This section is speculative.** OBO for Teams → Foundry hosted agents has NOT been
> tested or validated. It is documented here as an investigation reference for when
> user-delegated access becomes a requirement. **Do NOT implement this without first
> confirming with Microsoft that the Foundry hosted agent API accepts user-delegated
> bearer tokens.**

### Why OBO?

Current model: bot authenticates as UAMI (app identity). The Foundry agent doesn't
know which Teams user is talking. For production scenarios you may need:
- User-scoped data filtering (agent sees who's calling)
- Per-user RBAC on the Foundry project
- Audit trail with real user identity

### How it would work (theoretical)

```
Teams User → SSO token from Teams Bot Framework
  → Bot exchanges via Entra OBO flow
  → Gets user-delegated token (scope: https://ai.azure.com/.default)
  → Wraps in custom BearerTokenCredential
  → AIProjectClient(credential=user_credential)
  → Foundry validates user's Entra identity + RBAC
```

### What would change

| Component | Current (UAMI) | OBO (user-delegated) |
|-----------|----------------|---------------------|
| Bot Service auth | `msaAppType: UserAssignedMSI` | `msaAppType: MultiTenant` + client secret |
| Entra app | UAMI only | App registration with delegated `ai.azure.com` permissions |
| Bot code | `DefaultAzureCredential()` | SSO token extraction → OBO exchange → custom credential |
| Foundry RBAC | UAMI has `Azure AI User` | Each user needs `Azure AI User` on account + project |
| Credential | `DefaultAzureCredential` | Custom `BearerTokenCredential` wrapping user token |

### Custom credential wrapper (concept)

```python
from azure.core.credentials import AccessToken, TokenCredential

class BearerTokenCredential(TokenCredential):
    """Wrap a user-delegated OBO token as a TokenCredential."""
    def __init__(self, token: str, expires_on: int):
        self._token = token
        self._expires_on = expires_on

    def get_token(self, *scopes, **kwargs) -> AccessToken:
        return AccessToken(self._token, self._expires_on)
```

### OBO token exchange (concept)

```python
import msal

app = msal.ConfidentialClientApplication(
    client_id=BOT_APP_ID,
    client_credential=BOT_APP_SECRET,
    authority=f"https://login.microsoftonline.com/{TENANT_ID}",
)

# Exchange Teams SSO token for Foundry-scoped user token
result = app.acquire_token_on_behalf_of(
    user_assertion=teams_sso_token,  # From Teams Bot Framework token exchange
    scopes=["https://ai.azure.com/.default"],
)
user_token = result["access_token"]
```

### Open questions

1. **Does Foundry accept user-delegated tokens?** All current docs/samples use app identity only. Needs Microsoft confirmation.
2. **What RBAC roles does the user need?** Likely `Azure AI User` on account + project, but untested.
3. **Does `get_openai_client(agent_name=...)` work with user tokens?** The SDK uses `TokenCredential` abstractly, so it should — but not validated.
4. **Consent flow:** Users would need to consent to `ai.azure.com` permissions. How does this interact with Teams SSO?
5. **Token refresh:** OBO tokens expire (~1h). Long conversations need refresh logic.

---

## Gotchas & Hard-Won Lessons

| Issue | Cause | Fix |
|-------|-------|-----|
| Bot returns "Response could not be saved" | Old-style `agent_reference` invocation | Use `get_openai_client(agent_name=...)` with `allow_preview=True` |
| Bot auth 401 on /api/messages | UAMI not in CONNECTIONS__ env vars | Set all 4 `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*` vars: CLIENTID, TENANTID, AUTHORITYENDPOINT, **AUTHTYPE=UserManagedIdentity** |
| **Bot returns HTTP 500 with `AADSTS7000216` on every real Teams message** | **Missing `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE` → MSAL falls back to ConfidentialClient (needs a client secret the keyless deploy never provisioned)** | **Set `AUTHTYPE=UserManagedIdentity`. Synthetic JWT probe in safe-check returns OK_jwt_alive because JWT middleware fires before outbound token acquisition; only `safe-check --phase post-deploy` Step 5.7 catches it. Quick patch: `az containerapp update --set-env-vars CONNECTIONS__SERVICE_CONNECTION__SETTINGS__AUTHTYPE=UserManagedIdentity`** |
| Teams can't find bot | manifest botId mismatch | `botId` must equal UAMI client ID used as `msaAppId` |
| Streaming garbled in Teams | Sending each chunk separately as `send_activity()` | Use `StreamingResponse` from `microsoft_agents.hosting.core.app.streaming.streaming_response`: `sr.queue_text_chunk(delta)` per chunk + `await sr.end_stream()` once. SDK handles batching + sequence numbers. See `templates/copilot/bot-streaming.py`. |
| Bot delivers ONE big message after 60s of typing-dots silence (no progressive UX) | Bot uses the legacy collect-then-send pattern: SSE chunks accumulated into a list, joined, sent via single `send_activity()` at end | Refactor to streaming. Replace `chunks.append(delta)` + final `send_activity(answer)` with `StreamingResponse(context).queue_text_chunk(delta)` per chunk + `await streaming.end_stream()`. ~30 LOC change. **Origin:** recent pilot retrospective. |
| Teams shows the bot's reply twice (full message appended after streaming completes) | Yielding `TextChunk` on both `response.output_text.delta` and `response.output_text.done` | ✅ **Fixed in `templates/copilot/bot-streaming.py` (May 2026).** Only deltas yield `TextChunk`; the `.done` branch is now a deliberate `pass` because `.done` carries the full accumulated text as metadata, not a new content payload. If you fork an older copy of the template, drop the `.done` yield. |
| Teams shows Invocations replies twice after streaming | Yielding `TextChunk` on both `assistant.message_delta` and final `assistant.message` | Track whether deltas were streamed; if yes, ignore final `assistant.message`, otherwise use it for non-delta backends |
| Sideload fails | manifest schema wrong | Use `manifestVersion: "1.21"` (not `devPreview` — `devPreview` is rejected for new CEA uploads since GA May 2025) with `copilotAgents.customEngineAgents` |
| Sideload fails with "Schema validation error" on `customEngineAgents` | Manifest had a `conversationStarters` field on the customEngineAgent | Remove it. Schema requires `additionalProperties: false` on customEngineAgents items (only `id` + `type` allowed). Prompt starters belong in `bots[0].commandLists[0].commands[]` with `{title, description}` |
| Sideload fails with "Schema validation error" on `bots[].scopes` | Used lowercase `groupchat` instead of camelCase `groupChat` | The schema enum is `["team","personal","groupChat","copilot"]` — case-sensitive. For CEAs, use `["personal","copilot"]` per validation guidelines |
| Bot doesn't show up in M365 Copilot Chat | bot `scopes` missing `copilot` (or `commandLists.scopes` doesn't match) | Per validation guidelines, CEAs MUST include `copilot` in BOTH `bots[0].scopes` AND `bots[0].commandLists[0].scopes`. The two scope arrays must match |
| Prompt starters don't appear | Manifest has placeholder text `__STARTER_*__` left behind, OR env vars not set, OR placed in a `conversationStarters[]` (which is not in v1.21 schema) | Set `STARTER_1_TITLE` / `STARTER_1_PROMPT` (and 2/3) before `build_teams_manifest.py` runs. Starters become `{title, description}` entries in `bots[0].commandLists[0].commands[]`. Without env vars, `build_teams_manifest.py` strips the placeholder slots so only `!reset` ships |
| Bot crashes on first message | `PROJECT_ENDPOINT` not set | Must include full path: `https://acct.services.ai.azure.com/api/projects/proj` |
| Thread state lost between restarts | Using MemoryStorage | Switch to BlobStorage for production (`microsoft-agents-storage-blob`) |
| Bot SDK auth fails | Wrong `msaAppType` in bot.bicep | Must be `UserAssignedMSI` (not `SingleTenant` or `MultiTenant`) |
| Bot image overwritten on reprovision | Bicep resets container image | Use `fetch-container-image.bicep` + `SERVICE_BOT_RESOURCE_EXISTS` param |
| `server_error` in Teams | Stale conversation from previous agent version | Type `!reset` in Teams chat — bot auto-retries with fresh conversation |
| Manifest validation fails on length | `name.full` > 100 chars or `description.short` > 80 chars | Use separate short/full tokens. Build script auto-truncates but keep inputs concise. |
| Bot crashes after pip install | microsoft-agents-* 0.9.x has breaking changes | Pin to `>=0.8.0,<0.9.0` in requirements.txt (tested with 0.8.0) |
| Bot crashes: MsalConnectionManager can't find CONNECTIONS__ vars | `MsalConnectionManager()` called without config | Must use `load_configuration_from_env(os.environ)` and pass `**config` to `MsalConnectionManager()`. See app.py template. |
| Bot gets 400 "responses protocol not declared" | Agent uses GHCP SDK (Invocations) but bot calls `oai.responses.create()` | **CONFIRMED:** `InvocationAgentServerHost` only serves `/invocations`. Bot must use direct HTTP POST to `/protocols/invocations` endpoint with SSE parsing. See "Invocations Protocol Agents" section. |
| Courtesy message appears only at end, not when stream cancelled | `sr._cancelled` only checked after `queue_text_chunk()` — no text flows during tool calls | **Check `sr._cancelled` on EVERY event** in the generator loop (TextChunk, StatusUpdate, SessionComplete). Tool calls have 10-30s gaps. See "Stream Cancellation Fallback" section. |
| FileConsentCard not working | Manifest has `supportsFiles: false` | Set `"supportsFiles": true` in `bots[0]` in manifest.json. Re-sideload the updated zip. |
| "Questa risposta è stata arrestata" (stream killed) | Teams 2-min streaming timeout (403 ContentStreamNotAllowed) | Expected for long queries. `bot-streaming.py` catches this, sends courtesy message, then delivers full response as regular message. |
| Stream cancelled but Foundry still running | Normal — Teams cancels the **display**, not the agent | Bot keeps consuming the Foundry stream. After agent finishes, sends full response via `context.send_activity()`. |
| SDK 0.9.x pin warning in troubleshooting | Outdated — 0.9.x MsalConnectionManager is backward-compatible | `>=0.9.0` is safe. `streaming_response` requires it. |
| `aca.bicep` first revision fails `UNAUTHORIZED` on image pull → falls back to placeholder image, bot looks "Running" but never receives traffic | `aca.bicep` missing `properties.configuration.registries` block, so ACA tries anonymous pull from the private ACR | ✅ **Fixed in `templates/infra/bot/aca.bicep` (May 2026).** Template now takes an `acrLoginServer` param and binds the UAMI as the registry credential. Make sure `main.bicep` passes `acrLoginServer: acrEndpoint` AND that the AcrPull role grant (via `bot-rbac.bicep`) has propagated. |
| **Scary RED `404 NotFound` error block at the end of `azd deploy <any-service>` ("agents/agent/versions/<n> not found"); deploy itself succeeded** | `azure.yaml` declares a service with `host: azure.ai.agent` whose **service key** ≠ the actual agent name. The `azure.ai.agents` azd extension's postdeploy hook fires after **every** `azd deploy` (including unrelated services like `bot` / `workspace` / `mcp`) and looks up `agents/<service-key>/versions/<n>` — using the service key verbatim, not the real agent name. Benign-but-loud false alarm. See **`foundry-hosted-agents` SKILL § Troubleshooting** for the cross-reference. | Rename the agent service key in `azure.yaml` to match the actual agent name (e.g. service key `journey-advisor` ↔ agent name `journey-advisor`). If you can't rename (downstream scripts reference the key), the error is cosmetic — your deploy succeeded; check `azd ai agent show` to confirm. |

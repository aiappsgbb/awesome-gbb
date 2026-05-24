---
name: zava-workspace-deploy
description: >
  Deploy the Zava agentic-org control plane to Azure Container Apps.
  Full-stack: FastAPI backend (462 files, 38 domains, 48 routes, 46 MCP
  tools, 62 agent graphs, 19 ambient agents, KuzuDB entity graph, Mem0
  memory, AGT governance) + 3 React/Vite SPAs (operator, portal,
  blueprint) + 18 Node MCP mock servers. Multi-stage Docker, nginx
  reverse-proxy, Citadel APIM integration, OTel, managed identity.
  USE FOR: deploy Zava, Zava workspace, Zava control plane, Zava ACA,
  Zava Docker, Zava container, Zava to Azure, Zava Citadel, agentic org
  deploy, zava-control-plane, deploy control plane, Zava fruocco, Zava
  demo deploy, Zava cloud, Zava APIM.
  DO NOT USE FOR: Threadlight agent deploy (use threadlight-deploy),
  Threadlight workspace UI (use threadlight-workspace-ui), Citadel hub
  setup (use citadel-hub-deploy), Foundry agent deploy (use
  foundry-hosted-agents).
metadata:
  version: "2.0.0"
---

# Zava Workspace Deploy — Agentic-Org Control Plane → ACA

Deploy the complete Zava control plane — a 462-file Python/TypeScript
agentic-org platform — to Azure Container Apps as a single multi-process
container behind nginx, wired to the Citadel APIM gateway and Foundry
backends.

> **Zava is the full-enterprise demo.** While Threadlight deploys one
> process (one domain, one agent, one MCP), Zava runs the entire org:
> 38 workflow domains, 62 agent graphs, 19 ambient agents, a KuzuDB
> entity graph, Mem0 memory, AGT governance, 3 SPAs, and a fleet
> manager — all in one container. It shows what "agentic org at scale"
> looks like when every Threadlight process is composed together.

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Azure Container App (1 container, nginx PID 1 + uvicorn bg)   │
│                                                                 │
│  nginx :80                                                      │
│  ├── /              → /var/www/client     (operator UI)         │
│  ├── /portal/       → /var/www/portal     (candidate portal)    │
│  ├── /blueprint/    → /var/www/blueprint  (constellation essay) │
│  ├── /api/*         → uvicorn :3101       (FastAPI backend)     │
│  └── /api/stream/*  → uvicorn :3101       (SSE, no buffering)  │
│                                                                 │
│  uvicorn :3101 — FastAPI control plane                          │
│  ├── 48 route modules (fleet, workflows, entities, portal, …)  │
│  ├── 46 MCP tool functions (in-process, no sidecar)            │
│  ├── 62 agent graph executors (LanGraph-style DAGs)            │
│  ├── 19 ambient agents (CEO, Finance, HR, Legal, Ops, …)       │
│  ├── Fleet Manager + simulator orchestrator                     │
│  ├── KuzuDB entity graph (Person, Org, Workflow, edges)        │
│  ├── Mem0 memory layer (working + distilled lessons)           │
│  ├── AGT governance kernel (policy, authority, kill-switch)     │
│  ├── SSE hub (real-time UI push)                               │
│  ├── Event bus (in-process pub/sub)                            │
│  └── OTel → Azure Monitor (Foundry App Insights)               │
│                                                                 │
│  In-process MCP tool server (NOT sidecars)                      │
│  └── 46 tools (policy, entity, fleet, OCR, speech, image, …)  │
│                                                                 │
│  Optional Node MCP mock sidecar(s) (separate ACA apps or off)  │
│  └── 18 mock servers (Workday, Concur, ServiceNow, …)          │
└─────────────────────────────────────────────────────────────────┘
         │                        │                    │
         ▼                        ▼                    ▼
   Citadel APIM              Cosmos DB           Foundry backends
   (LLM gateway)        (optional telemetry)    (model deployments)
```

### Key numbers

| Metric | Count |
|--------|-------|
| Python source files | 462 |
| Workflow domains | 38 (15 primary + 23 composite/cadenced) |
| FastAPI route modules | 48 |
| Agent graph executors | 62 |
| In-process MCP tools | 46 |
| Ambient agents | 19 |
| Node MCP mock servers | 18 (3 packs: POC1, POC2, Agency) |
| React/Vite SPAs | 3 + 1 shared lib |
| Data fabric generators | 12 |
| Services | 47 |

---

## Source repos

| Repo | What |
|------|------|
| [`arturcrmbot/zava-control-plane`](https://github.com/arturcrmbot/zava-control-plane) | Backend + 3 SPAs + mocks + data |
| [`arturcrmbot/zava-design-skills`](https://github.com/arturcrmbot/zava-design-skills) | `compose-org` + `research-company` skills (already in awesome-gbb) |

---

## Prerequisites

| Need | Why |
|------|-----|
| `zava-control-plane` repo cloned | Source code |
| An ACA environment (swedencentral recommended) | Where the container runs |
| ACR (Azure Container Registry) in same region | Image storage |
| Citadel APIM gateway URL | LLM routing (or direct Foundry endpoint) |
| Foundry AI Services account | Model deployments (gpt-4.1, gpt-5.4-mini, text-embedding-3-large) |
| App Insights connection string | OTel telemetry (optional but recommended) |
| Managed Identity with RBAC | Auth to Foundry + Storage + Cosmos |
| `azure-tenant-isolation` | **MANDATORY** before any `az` command |

---

## Step 1: Multi-stage Dockerfile

The container runs two processes: nginx (PID 1) serves static bundles
and reverse-proxies `/api/*` to uvicorn (background). No Durable
Functions — all orchestration is in-process via the event bus + fleet
manager + agent graphs.

```dockerfile
# Dockerfile.zava
# ── Stage 1: Build 3 SPAs ────────────────────────────────────────
FROM node:20-alpine AS spa-build
WORKDIR /app

# Root package.json (workspace + shared deps)
COPY package.json package-lock.json ./
COPY web/shared/ web/shared/
COPY web/client/ web/client/
COPY web/portal/ web/portal/
COPY web/blueprint/ web/blueprint/
COPY vite.config.ts tsconfig.json tailwind.config.ts postcss.config.js ./
COPY index.html ./

# Install all deps (includes vite, react, tailwind)
RUN npm ci --production=false

# Build: operator UI (root vite → dist/), portal, blueprint
ARG VITE_API_BASE_URL=""
RUN npm run build \
 && npm run build:portal \
 && npm run build:blueprint

# ── Stage 2: Python backend ──────────────────────────────────────
FROM python:3.13-slim AS api-build
WORKDIR /app

# System deps for kuzu, weasyprint, pillow, sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpango1.0-dev libcairo2 libgdk-pixbuf2.0-0 \
    libffi-dev libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
# Use uv for fast deterministic installs (already has lockfile)
RUN pip install uv && uv sync --frozen --no-dev

# Copy the application
COPY api/ api/
COPY data/ data/

# ── Stage 3: Runtime ─────────────────────────────────────────────
FROM python:3.13-slim
WORKDIR /app

# Runtime deps for weasyprint + kuzu + nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx libpango1.0-0 libcairo2 libgdk-pixbuf2.0-0 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python venv from build stage
COPY --from=api-build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Application code
COPY --from=api-build /app/api /app/api
COPY --from=api-build /app/data /app/data
COPY --from=api-build /app/pyproject.toml /app/

# SPA bundles
COPY --from=spa-build /app/dist /var/www/client
COPY --from=spa-build /app/web/portal/dist /var/www/portal
COPY --from=spa-build /app/web/blueprint/dist /var/www/blueprint

# nginx config + entrypoint
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/app/entrypoint.sh"]
```

---

## Step 2: nginx.conf

```nginx
# deploy/nginx.conf
worker_processes  auto;
events { worker_connections 1024; }

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout 65;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml text/javascript image/svg+xml;

    upstream api {
        server 127.0.0.1:3101;
    }

    server {
        listen 80;
        server_name _;

        # ── Operator UI (root) ──────────────────────────────
        location / {
            root /var/www/client;
            index index.html;
            try_files $uri $uri/ /index.html;
        }

        # ── Candidate Portal ────────────────────────────────
        location /portal/ {
            alias /var/www/portal/;
            index index.html;
            try_files $uri $uri/ /portal/index.html;
        }

        # ── Blueprint / Constellation Essay ─────────────────
        location /blueprint/ {
            alias /var/www/blueprint/;
            index index.html;
            try_files $uri $uri/ /blueprint/index.html;
        }

        # ── SSE streams (no buffering) ─────────────────────
        location /api/stream/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Connection "";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 3600s;
            chunked_transfer_encoding off;
        }

        # ── API proxy ──────────────────────────────────────
        location /api/ {
            proxy_pass http://api;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 300s;
        }

        # ── Internal webhook bridge ────────────────────────
        location /internal/ {
            proxy_pass http://api;
            proxy_set_header Host $host;
        }

        # ── Static asset caching ───────────────────────────
        location ~* \.(js|css|png|jpg|ico|svg|woff2?)$ {
            root /var/www/client;
            expires 30d;
            add_header Cache-Control "public, immutable";
            try_files $uri =404;
        }
    }
}
```

---

## Step 3: Entrypoint

```bash
#!/bin/bash
# deploy/entrypoint.sh — start uvicorn then nginx (PID 1)
set -e

# Start FastAPI backend in background
cd /app
uvicorn api.server.main:app \
  --host 127.0.0.1 \
  --port 3101 \
  --workers 1 \
  --log-level info &

# Wait for API to be ready
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:3101/api/health >/dev/null 2>&1; then
    echo "[entrypoint] API ready"
    break
  fi
  sleep 1
done

# Start nginx in foreground (PID 1 for ACA health probes)
exec nginx -g 'daemon off;'
```

---

## Step 4: Environment variables

The control plane reads ~80 env vars. The table below groups them by
integration layer. Set via ACA `--env-vars` or `--yaml` revision template.

### Required (backend won't start without these)

| Var | Example | Purpose |
|-----|---------|---------|
| `PORT` | `3101` | FastAPI listen port (internal, nginx proxies) |

### Citadel APIM integration (recommended)

| Var | Example | Purpose |
|-----|---------|---------|
| `AZURE_OPENAI_ENDPOINT` | `https://apim-<id>.azure-api.net/azure-openai` | LLM calls via Citadel gateway |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4.1` | Default model deployment |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | API version |
| `FLEET_MANAGER_MODEL` | `gpt-4.1` | Fleet Manager model |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | `text-embedding-3-large` | Mem0 lesson embeddings |

### Foundry & evaluation

| Var | Example | Purpose |
|-----|---------|---------|
| `AZURE_FOUNDRY_PROJECT_ENDPOINT` | `https://aif-<id>.services.ai.azure.com/api/projects/<name>` | Foundry eval project |
| `AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT` | `gpt-4.1` | Eval judge model |
| `EVAL_SAMPLE_RATE` | `1.0` | Score every agent invocation (demo) |

### Telemetry (OTel → App Insights)

| Var | Example | Purpose |
|-----|---------|---------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=...` | Azure Monitor export |
| `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` | `true` | Capture prompts (synthetic data only!) |

### Simulator

| Var | Default | Purpose |
|-----|---------|---------|
| `SIMULATOR_RAMP_ENABLED` | `1` | Auto-spawn workflows |
| `SIMULATOR_RAMP_AVG_INTERVAL_SECONDS` | `60` | Seconds between spawns |
| `SIMULATOR_RAMP_DOMAINS` | `expense-claim` | CSV of active domains |
| `DEMO_TIME_WARP_FACTOR` | `60` | 1 day = 24 min of demo |
| `PERSONA_AUTO_CLOSE` | (empty) | CSV of personas to auto-decide |

### Entity plane & memory

| Var | Default | Purpose |
|-----|---------|---------|
| `ENTITY_PLANE_ENABLED` | `1` | KuzuDB entity graph |
| `MEMORY_DOMAINS` | `hiring` | Domains with Mem0 partitions |
| `DREAM_PASS_DEMO_CADENCE_SECONDS` | `120` | Memory consolidation interval |

### Portal integrations (optional)

| Var | Purpose |
|-----|---------|
| `AZURE_STORAGE_CONNECTION_STRING` | Blob storage for CV uploads, avatar cache |
| `ACS_EMAIL_CONNECTION_STRING` | Azure Communication Services magic-link emails |
| `AZURE_SPEECH_REGION` | Azure Speech avatar batch synthesis |
| `AZURE_GPT_REALTIME_URL` | GPT Realtime voice screen (WebRTC) |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | OCR extract MCP tool |

### MCP mock URLs (when running sidecars)

| Var | Default | Purpose |
|-----|---------|---------|
| `WORKDAY_MCP_URL` | `http://localhost:4101` | Workday expense mock |
| `CONCUR_MCP_URL` / `MACONOMY_MCP_URL` | `:4102` / `:4103` | Travel mocks |
| `GREENHOUSE_MCP_URL` … `HEYGEN_MCP_URL` | `:4201`…`:4207` | POC2 hiring mocks |
| `SALESFORCE_MCP_URL` … `DOCUSIGN_MCP_URL` | `:4200`…`:4226` | Agency mocks |

### Governance

| Var | Default | Purpose |
|-----|---------|---------|
| `AGT_ENFORCE` | `0` | `1` = deny policy violations (not just log) |
| `READ_ROUTE_AUTH` | (empty) | `enforce` = require X-Actor-Id on reads |

---

## Step 5: Managed Identity & RBAC

Create a user-assigned managed identity for the ACA app:

```bash
# Per azure-tenant-isolation — AZURE_CONFIG_DIR already set
az identity create -g $RG -n id-zava --location $LOCATION

IDENTITY_ID=$(az identity show -g $RG -n id-zava --query id -o tsv)
PRINCIPAL_ID=$(az identity show -g $RG -n id-zava --query principalId -o tsv)
CLIENT_ID=$(az identity show -g $RG -n id-zava --query clientId -o tsv)
```

Required role assignments:

| Resource | Role | Why |
|----------|------|-----|
| Foundry AI Services account | Cognitive Services OpenAI User | LLM calls |
| Foundry project | Foundry User (`53ca6127-...`) | Agent + eval API |
| Storage account | Storage Blob Data Contributor | CV uploads, avatar cache |
| App Insights | Monitoring Metrics Publisher (`3913510d-...`) | OTel export |
| Document Intelligence | Cognitive Services User | OCR tool |
| Speech Services | Cognitive Services Speech User | Avatar synthesis |

```bash
# Foundry — assign at ACCOUNT scope (not just project)
FOUNDRY_ID=$(az cognitiveservices account show -g $RG -n $FOUNDRY_NAME --query id -o tsv)
az role assignment create --assignee-object-id $PRINCIPAL_ID \
  --role "Cognitive Services OpenAI User" --scope $FOUNDRY_ID
az role assignment create --assignee-object-id $PRINCIPAL_ID \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" --scope $FOUNDRY_ID
```

---

## Step 6: Build & push to ACR

```bash
# Verify tenant isolation
EXPECTED_TENANT="<your-tenant-id>"
ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
[ "$ACTUAL_TENANT" = "$EXPECTED_TENANT" ] || { echo "❌ Tenant mismatch"; exit 1; }

# Build in ACR (no local Docker needed)
TAG=$(date -u +%Y%m%d-%H%M%S)
az acr build \
  --registry $ACR_NAME \
  --resource-group $RG \
  --image "zava-control-plane:$TAG" \
  --image "zava-control-plane:latest" \
  --file deploy/Dockerfile \
  . \
  --timeout 1200
```

> Build takes ~5-8 min (npm ci + uv sync + kuzu/weasyprint wheels).
> The `--timeout 1200` prevents ACR from killing slow builds.

---

## Step 7: Deploy to ACA

### Option A: New ACA app (first deploy)

```bash
az containerapp create \
  --name zava-control-plane \
  --resource-group $RG \
  --environment $ACA_ENV_NAME \
  --image "$ACR_LOGIN_SERVER/zava-control-plane:$TAG" \
  --registry-server $ACR_LOGIN_SERVER \
  --registry-identity $IDENTITY_ID \
  --user-assigned $IDENTITY_ID \
  --target-port 80 \
  --ingress external \
  --cpu 2 --memory 4Gi \
  --min-replicas 1 --max-replicas 1 \
  --env-vars \
    PORT=3101 \
    AZURE_CLIENT_ID=$CLIENT_ID \
    AZURE_OPENAI_ENDPOINT="https://$APIM_NAME.azure-api.net/azure-openai" \
    AZURE_OPENAI_DEPLOYMENT=gpt-4.1 \
    FLEET_MANAGER_MODEL=gpt-4.1 \
    AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-large \
    AZURE_OPENAI_API_VERSION=2024-10-21 \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$APPINSIGHTS_CONN" \
    AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED=true \
    SIMULATOR_RAMP_ENABLED=1 \
    SIMULATOR_RAMP_AVG_INTERVAL_SECONDS=60 \
    SIMULATOR_RAMP_DOMAINS=expense-claim \
    DEMO_TIME_WARP_FACTOR=60 \
    ENTITY_PLANE_ENABLED=1 \
    CORS_ALLOWED_ORIGINS="*"
```

> **CPU/memory**: 2 vCPU / 4 GiB minimum. KuzuDB + sentence-transformers
> + 62 graph executors need headroom. For demos with all 38 domains,
> consider 4 vCPU / 8 GiB.

### Option B: Update existing ACA app

```bash
az containerapp update \
  --name zava-control-plane \
  --resource-group $RG \
  --image "$ACR_LOGIN_SERVER/zava-control-plane:$TAG"
```

---

## Step 8: Verify

```bash
FQDN=$(az containerapp show --name zava-control-plane -g $RG \
  --query properties.configuration.ingress.fqdn -o tsv)

# Health check
curl -sf "https://$FQDN/api/health" | python3 -m json.tool

# Workflow count (should grow as simulator runs)
curl -sf "https://$FQDN/api/workflows" | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print(f'{len(d)} workflows')"

# Entity graph
curl -sf "https://$FQDN/api/entities/stats" | python3 -m json.tool

# Fleet manager status
curl -sf "https://$FQDN/api/fleet" | python3 -m json.tool

# SSE stream (Ctrl-C after a few events)
curl -N "https://$FQDN/api/stream/fleet"

# Open in browser
echo "Operator UI: https://$FQDN"
echo "Portal:      https://$FQDN/portal/"
echo "Blueprint:   https://$FQDN/blueprint/"
```

---

## Deployment profiles

The control plane supports three demo profiles, controlled by env vars:

### Profile 1: Single-domain walkthrough (default)

Best for live demos where you walk through one domain end-to-end.

```
SIMULATOR_RAMP_ENABLED=1
SIMULATOR_RAMP_DOMAINS=expense-claim
PERSONA_AUTO_CLOSE=             (empty — human drives every gate)
DEMO_TIME_WARP_FACTOR=60
```

### Profile 2: Full constellation

All 38 domains active, ambient agents auto-resolving. The "Constellation"
view in the blueprint SPA shows the full org in motion.

```
SIMULATOR_RAMP_ENABLED=1
SIMULATOR_RAMP_DOMAINS=expense-claim,hiring,travel-preapproval,vendor-kyc,...
PERSONA_AUTO_CLOSE=cfo,gc,vp-hr,director-procurement,...
DEMO_TIME_WARP_FACTOR=60
SIMULATOR_CADENCE_BURST=1       (fire all cadenced rituals on first tick)
```

### Profile 3: Replay mode

Pre-recorded tape loops for unattended kiosk display. No LLM calls.

```
ZAVA_MODE=replay
ZAVA_TAPE_PATH=/app/tape/tape.tar.gz
```

Record a tape locally: `scripts/record_tape.sh` captures events for
N minutes, then bake into the Docker image at build time.

---

## Node MCP mock sidecars (optional)

For demos that need external-system simulation (Workday responses,
ServiceNow tickets, etc.), deploy the mock servers as separate ACA apps.
Each mock is a ~50-line Express server reading a JSON fixture.

### POC1 pack (expense-claim domain)

| Mock | Port | Fixture |
|------|------|---------|
| `workday-mcp` | 4101 | `mocks/workday-mcp/data.json` |
| `concur-mcp` | 4102 | `mocks/concur-mcp/data.json` |
| `maconomy-mcp` | 4103 | `mocks/maconomy-mcp/data.json` |

### POC2 pack (hiring domain)

| Mock | Port | Fixture |
|------|------|---------|
| `greenhouse-mcp` | 4201 | Greenhouse ATS mock |
| `linkedin-mcp` | 4202 | LinkedIn profile mock |
| `workday-hr-mcp` | 4203 | Workday HR mock |
| `graph-mcp` | 4204 | MS Graph calendar mock |
| `servicenow-mcp` | 4205 | ServiceNow ticket mock |
| `acs-mcp` | 4206 | ACS communication mock |
| `heygen-mcp` | 4207 | HeyGen avatar mock |

### Agency pack (enterprise pitch)

7 mocks: Salesforce, Mediaocean, Prisma, Kinesso, SAP S/4, Workday HCM,
DocuSign (ports 4200-4226).

### Deploy a mock sidecar

```dockerfile
# Dockerfile.mock
FROM node:20-alpine
WORKDIR /app
COPY mocks/<mock-name>/ .
RUN npm install --production
EXPOSE <port>
CMD ["npx", "tsx", "server.ts"]
```

Wire the main container's env var (e.g. `WORKDAY_MCP_URL`) to the
sidecar's internal ACA URL.

> **For most demos, mocks aren't needed.** The 46 in-process MCP tools
> handle the core demo. Mocks add realism for specific domain walkthroughs
> where you want to show "Workday returned this data."

---

## Citadel APIM integration

When deploying alongside a Citadel hub (recommended), set
`AZURE_OPENAI_ENDPOINT` to the APIM gateway URL:

```
AZURE_OPENAI_ENDPOINT=https://apim-<id>.azure-api.net/azure-openai
```

The control plane uses `DefaultAzureCredential` (via the managed identity)
for all Azure SDK calls. The Citadel APIM validates the JWT from the
managed identity against the product's access contract.

To create a Zava access contract in the Citadel hub:

```bash
# Create an APIM product for Zava
az apim product create \
  --resource-group $CITADEL_RG \
  --service-name $APIM_NAME \
  --product-id zava-control-plane \
  --title "Zava Control Plane" \
  --description "Full agentic-org platform — all 38 domains" \
  --state published \
  --subscription-required false
```

---

## Connecting to Threadlight PoCs

Zava is the **composition layer** that runs 38 domains; each domain
is a Threadlight process. On the Citadel hub, each Threadlight PoC
has its own APIM product access contract. Zava's fleet manager routes
LLM calls through the appropriate backend pool based on domain config.

The `api/shared/domains.py` registry maps each domain to its orchestrator,
graphs, HITL gates, and persona config. Adding a new domain (a new
Threadlight PoC) is one entry in this registry + the corresponding
graph executors.

---

## Data persistence

| Data | Storage | Persistence |
|------|---------|-------------|
| KuzuDB entity graph | `/app/data/portal/entity_graph.kuzu` | Ephemeral (in-container) — resets on restart |
| Mem0 lessons | In-memory or ChromaDB | Ephemeral unless `AZURE_OPENAI_EMBED_DEPLOYMENT` configured |
| Magic links (SQLite) | `/app/data/portal/magic_links.sqlite` | Ephemeral |
| KPI snapshots (SQLite) | `/app/data/portal/kpis.sqlite` | Ephemeral |
| Audit ledger | In-memory or Azure Blob (`AZURE_STORAGE_AUDIT_ACCOUNT`) | Persistent if blob configured |
| Workflow state | In-memory `StateStore` | Ephemeral — reseeded by simulator on restart |

> **For demos, ephemeral is fine.** The simulator reseeds workflows on
> boot. For persistent deployments, mount an Azure Files volume at
> `/app/data/portal/` and configure blob audit.

### Snapshot save/restore

```bash
# Save current state (locally, before baking into image)
uv run python scripts/zava-snapshot.py save "demo-baseline"

# Restore on boot (via BOOT_DEMO_SNAPSHOT env var)
BOOT_DEMO_SNAPSHOT=demo-baseline
```

---

## Local development

```bash
# Prerequisites
uv sync && npm install && npm run build

# Boot everything (azurite + mocks + fastapi + 3 SPAs)
make up

# Ports:
#   Operator UI:    http://localhost:5273
#   Portal:         http://localhost:5274
#   Blueprint:      http://localhost:5275
#   FastAPI:        http://localhost:3101

# Inject a test workflow
curl -X POST http://localhost:3101/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"demo-fail"}'
```

---

## See also

| Skill | Relationship |
|-------|-------------|
| [`threadlight-deploy`](../threadlight-deploy/) | Deploys individual Threadlight processes; Zava composes them all |
| [`threadlight-workspace-ui`](../threadlight-workspace-ui/) | Generates reference UIs from SPEC; Zava has its own custom UIs |
| [`citadel-hub-deploy`](../citadel-hub-deploy/) | Deploys the APIM gateway Zava routes LLM calls through |
| [`citadel-spoke-onboarding`](../citadel-spoke-onboarding/) | Creates access contracts for Zava in the Citadel hub |
| [`foundry-observability`](../foundry-observability/) | OTel pattern the control plane's `init_otel()` follows |
| [`foundry-hosted-agents`](../foundry-hosted-agents/) | MAF agents that replace the Durable Functions orchestrators |
| [`azd-patterns`](../azd-patterns/) | Bicep module library for ACA, ACR, managed identity |
| [`azure-tenant-isolation`](../azure-tenant-isolation/) | **MANDATORY** before any `az` command |
| [`compose-org`](../compose-org/) | Forks Zava into a customer-flavoured digital clone |
| [`research-company`](../research-company/) | Produces the org-brief YAML that `compose-org` consumes |

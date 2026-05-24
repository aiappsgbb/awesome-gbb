---
name: zava-workspace-deploy
description: >
  Deploy the Zava agentic-org control plane to Azure Container Apps via
  azd (Azure Developer CLI). Single uvicorn process: FastAPI backend
  (462 files, 38 domains, 48 routes, 46 MCP tools, 62 agent graphs,
  19 ambient agents, KuzuDB entity graph, Mem0 memory, AGT governance)
  + 3 React/Vite SPAs served via Starlette StaticFiles. Bicep infra
  plugs into existing shared resources (ACR, App Insights, Citadel APIM).
  UAMI + RBAC — keyless everywhere.
  USE FOR: deploy Zava, Zava workspace, Zava control plane, Zava ACA,
  Zava azd, Zava container, Zava to Azure, Zava Citadel, agentic org
  deploy, zava-control-plane, deploy control plane, Zava demo deploy,
  Zava cloud, Zava APIM, azd up zava.
  DO NOT USE FOR: Threadlight agent deploy (use threadlight-deploy),
  Threadlight workspace UI (use threadlight-workspace-ui), Citadel hub
  setup (use citadel-hub-deploy), Foundry agent deploy (use
  foundry-hosted-agents).
metadata:
  version: "3.0.1"
---

# Zava Workspace Deploy — Agentic-Org Control Plane → ACA via azd

Deploy the complete Zava control plane — a 462-file Python/TypeScript
agentic-org platform — to Azure Container Apps with a single `azd up`,
plugging into existing shared infrastructure (ACR, App Insights, Citadel
APIM gateway).


> **Zava is the full-enterprise demo.** While Threadlight deploys one
> process (one domain, one agent, one MCP), Zava runs the entire org:
> 38 concurrent workflow domains, 79 persona roles, ambient agents,
> entity graph, memory consolidation, fleet manager, simulator — all in
> one container.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 ACA Container — Zava Control Plane                   │
│                                                                     │
│  uvicorn :80 — FastAPI + Starlette StaticFiles (single process)    │
│  ├── /                → StaticFiles(/app/static/client, html=True) │
│  ├── /portal/         → StaticFiles(/app/static/portal, html=True) │
│  ├── /blueprint/      → StaticFiles(/app/static/blueprint, html=T) │
│  ├── /api/*           → FastAPI route handlers                      │
│  └── /api/stream/*    → SSE endpoints (StreamingResponse)          │
│                                                                     │
│  FastAPI control plane                                              │
│  ├── 48 route modules (fleet, workflows, entities, portal, …)      │
│  ├── 46 MCP tool functions (in-process, no sidecar)                │
│  ├── 62 agent graph executors (LanGraph-style DAGs)                │
│  ├── 19 ambient agents (CEO, Finance, HR, Legal, Ops, …)          │
│  ├── Fleet Manager + simulator orchestrator                         │
│  ├── KuzuDB entity graph (Person, Org, Workflow, edges)            │
│  ├── Mem0 memory layer (working + distilled lessons)               │
│  ├── AGT governance kernel (policy, authority, kill-switch)        │
│  ├── SSE hub (real-time UI push)                                   │
│  ├── Event bus (in-process pub/sub)                                │
│  └── OTel → Azure Monitor (Foundry App Insights)                   │
│                                                                     │
│  Optional Node MCP mock sidecar(s) (separate ACA apps or off)      │
│  └── 18 mock servers (Workday, Concur, ServiceNow, …)              │
└─────────────────────────────────────────────────────────────────────┘
         │                        │                    │
         ▼                        ▼                    ▼
   Citadel APIM           Azure Files volume      Foundry backends
   (LLM gateway)       (KuzuDB persistence)      (model deployments)
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
| `azd` (Azure Developer CLI) installed | Deployment orchestrator |
| `azure-tenant-isolation` configured | **MANDATORY** — per-tenant `AZURE_CONFIG_DIR` before any `az`/`azd` command |
| Existing ACR in same region | Shared image registry (NOT provisioned by this skill) |
| Existing App Insights | Shared telemetry sink (NOT provisioned by this skill) |
| Citadel APIM gateway URL | LLM routing (or direct Foundry endpoint) |
| Foundry AI Services account | Model deployments (gpt-4.1, text-embedding-3-large) |

> **Shared infra convention.** This skill's Bicep does NOT provision ACR
> or App Insights — it references existing shared instances via parameters.
> This follows the azd-patterns convention: one ACR + one App Insights per
> subscription, shared by all workloads.

---

## Deploy model: `azd up`

Zava deploys with a single `azd up`. The command:
1. **Provisions infrastructure** via Bicep (UAMI, Storage, ACA env, ACA app, RBAC)
2. **Builds the container image** in the existing ACR (multi-stage Docker)
3. **Deploys the image** to the ACA app (swaps the placeholder image)

### azd template structure

```
zava-control-plane/
├── azure.yaml                    # azd project definition
├── deploy/
│   └── Dockerfile                # Multi-stage: SPA build → Python build → runtime
├── infra/
│   ├── main.bicep                # Subscription-scoped orchestrator
│   ├── main.parameters.json      # azd env var references
│   └── modules/
│       ├── uami.bicep            # User-Assigned Managed Identity
│       ├── storage.bicep         # Storage account + Azure Files share
│       ├── aca-env.bicep         # ACA managed environment + volume
│       ├── aca-app.bicep         # ACA container app (placeholder image)
│       └── rbac-acr-pull.bicep   # AcrPull on existing ACR
└── .env.azd.example              # Env var reference template
```

### azure.yaml

```yaml
name: zava-control-plane
metadata:
  template: zava-control-plane
services:
  zava:
    host: containerapp
    project: .
    docker:
      path: deploy/Dockerfile
      context: .
```

One service, one container. azd builds via ACR, tags with
`SERVICE_ZAVA_IMAGE_NAME`, and updates the ACA app.

---

## Step 1: Tenant isolation + azd init

```bash
# ── azure-tenant-isolation (MANDATORY) ────────────────────────────
ALIAS=fruocco
INDEX="${AZURE_TENANT_INDEX:-$HOME/.azure-tenants/index.json}"
TENANT_ID=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['tenant_id'])")
DEFAULT_SUB=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); print(d['tenants']['$ALIAS']['default_subscription'])")
AZ_CFG=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('config_dir'); print(os.path.expanduser(v) if v else os.path.expanduser('~/.azure-tenants/$ALIAS'))")
AZD_CFG=$(python3 -c "import json,os; d=json.load(open(os.path.expanduser('$INDEX'))); v=d['tenants']['$ALIAS'].get('azd_config_dir'); print(os.path.expanduser(v) if v else os.path.expanduser('~/.azd-tenants/$ALIAS'))")

export AZURE_CONFIG_DIR="$AZ_CFG"
export AZD_CONFIG_DIR="$AZD_CFG"

# Verify (MUST pass before any destructive op)
ACTUAL_TENANT=$(az account show --query tenantId -o tsv)
ACTUAL_SUB=$(az account show --query name -o tsv)
[ "$ACTUAL_TENANT" = "$TENANT_ID" ] || { echo "❌ Tenant mismatch"; exit 1; }
[ "$ACTUAL_SUB" = "$DEFAULT_SUB" ] || { echo "❌ Sub mismatch"; exit 1; }
echo "✅ Verified: $ACTUAL_SUB on tenant $ACTUAL_TENANT"
```

### Initialize azd environment

```bash
cd zava-control-plane
azd init               # first time only — creates .azure/ folder
azd env new zava       # creates .azure/zava/.env
```

### Set environment variables

```bash
# Existing shared infra
azd env set AZURE_ACR_LOGIN_SERVER <your-acr>.azurecr.io
azd env set AZURE_ACR_NAME <your-acr>
azd env set AZURE_ACR_RESOURCE_GROUP <acr-rg>
azd env set APPLICATIONINSIGHTS_CONNECTION_STRING "<conn-string>"

# LLM via Citadel APIM
azd env set AZURE_OPENAI_ENDPOINT "https://apim-<id>.azure-api.net/azure-openai"
azd env set AZURE_OPENAI_DEPLOYMENT gpt-4.1
azd env set AZURE_OPENAI_EMBED_DEPLOYMENT text-embedding-3-large
azd env set AZURE_OPENAI_API_VERSION 2024-10-21
azd env set FLEET_MANAGER_MODEL gpt-4.1

# Simulator (single-domain demo by default)
azd env set SIMULATOR_RAMP_ENABLED 1
azd env set SIMULATOR_RAMP_DOMAINS expense-claim
azd env set DEMO_TIME_WARP_FACTOR 60
```

> See `.env.azd.example` for the full ~80 env vars reference.

---

## Step 2: Deploy with `azd up`

```bash
# Verify tenant isolation again (immediately before destructive op)
[ "$(az account show --query tenantId -o tsv)" = "$TENANT_ID" ] || exit 1

azd up
```

This runs:
1. `azd provision` — creates RG, UAMI, Storage, ACA env + app, RBAC
2. `azd deploy` — builds image in ACR (~5-8 min), deploys to ACA

> **Build timeout.** ACR builds take ~5-8 min (npm ci + uv sync + heavy
> wheels: kuzu, weasyprint, sentence-transformers). If ACR times out,
> increase `--timeout` in the Dockerfile build args or retry.

---

## Step 3: Verify

```bash
FQDN=$(az containerapp show --name zava -g rg-zava \
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

## Bicep infrastructure

### What the Bicep creates (Zava-specific only)

| Module | Resource | Purpose |
|--------|----------|---------|
| `uami.bicep` | User-Assigned Managed Identity | Keyless auth to Foundry, Storage, ACR |
| `storage.bicep` | Storage Account + Azure Files share | KuzuDB persistence across ACA restarts |
| `aca-env.bicep` | ACA Managed Environment + volume mount | Container runtime with Azure Files volume |
| `aca-app.bicep` | ACA Container App | Runs uvicorn; placeholder image swapped by `azd deploy` |
| `rbac-acr-pull.bicep` | AcrPull role assignment | UAMI → existing ACR |

### What the Bicep does NOT create

| Resource | Why | How to provide |
|----------|-----|----------------|
| ACR | Shared per subscription | `AZURE_ACR_LOGIN_SERVER` param |
| App Insights | Shared per subscription | `APPLICATIONINSIGHTS_CONNECTION_STRING` param |
| Log Analytics Workspace | Owned by App Insights | Already exists |
| Citadel APIM | Hub-level resource | `AZURE_OPENAI_ENDPOINT` env var |
| Foundry AI Services | Per-project resource | RBAC assigned manually |

### RBAC added by Bicep

| Principal | Resource | Role | GUID |
|-----------|----------|------|------|
| UAMI | Existing ACR | AcrPull | `7f951dda-...` |

Additional RBAC (not in Bicep — assign manually or via postdeploy hook):

| Principal | Resource | Role | GUID |
|-----------|----------|------|------|
| UAMI | Foundry AI Services account | Foundry User | `53ca6127-...` |
| UAMI | Foundry AI Services account | Cognitive Services OpenAI User | `a97b65f3-...` |
| UAMI | App Insights | Monitoring Metrics Publisher | `3913510d-...` |

---

## Dockerfile — single process, no nginx

Three-stage multi-stage build. uvicorn serves everything on port 80:
FastAPI API routes + 3 SPA bundles via Starlette `StaticFiles(html=True)`.

```
Stage 1 (node:20-slim)    → npm ci + vite build for 3 SPAs
Stage 2 (python:3.13-slim) → uv sync (CPU-only torch via UV_EXTRA_INDEX_URL)
Stage 3 (python:3.13-slim) → copy venv + SPA bundles → uvicorn :80
```

Key design decisions:
- **No nginx, no entrypoint.sh** — uvicorn IS the process, PID 1
- **CPU-only torch** — `UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu`
  (ACA has no GPU; saves ~1.5 GiB image size)
- **uv from ghcr.io/astral-sh/uv** — multi-stage COPY for fast deterministic installs
- **SPA bundles at `/app/static/`** — `static_production.py` mounts them:

```python
# api/server/static_production.py (added to the repo)
app.mount("/portal", StaticFiles(directory="/app/static/portal", html=True))
app.mount("/blueprint", StaticFiles(directory="/app/static/blueprint", html=True))
app.mount("/", StaticFiles(directory="/app/static/client", html=True))
```

---

## Environment variables

The control plane reads ~80 env vars. The table below groups them by
integration layer. Set via `azd env set` before `azd up`.

### Citadel APIM integration (recommended)

| Var | Example | Purpose |
|-----|---------|---------|
| `AZURE_OPENAI_ENDPOINT` | `https://apim-<id>.azure-api.net/azure-openai` | LLM calls via Citadel gateway |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4.1` | Default model deployment |
| `AZURE_OPENAI_API_VERSION` | `2024-10-21` | API version |
| `FLEET_MANAGER_MODEL` | `gpt-4.1` | Fleet Manager model |
| `AZURE_OPENAI_EMBED_DEPLOYMENT` | `text-embedding-3-large` | Mem0 lesson embeddings |

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

### Governance

| Var | Default | Purpose |
|-----|---------|---------|
| `AGT_ENFORCE` | `0` | `1` = deny policy violations (not just log) |

> See `.env.azd.example` in the repo for the full list including portal
> integrations (Speech, Document Intelligence, ACS) and MCP mock URLs.

---

## Deployment profiles

### Profile 1: Single-domain walkthrough (default)

```
SIMULATOR_RAMP_DOMAINS=expense-claim
PERSONA_AUTO_CLOSE=             (empty — human drives every gate)
```

### Profile 2: Full constellation

```
SIMULATOR_RAMP_DOMAINS=expense-claim,hiring,travel-preapproval,vendor-kyc,...
PERSONA_AUTO_CLOSE=cfo,gc,vp-hr,director-procurement,...
SIMULATOR_CADENCE_BURST=1
```

### Profile 3: Replay mode (no LLM calls)

```
ZAVA_MODE=replay
ZAVA_TAPE_PATH=/app/tape/tape.tar.gz
```

---

## Data persistence

| Data | Storage | Persistence |
|------|---------|-------------|
| KuzuDB entity graph | Azure Files volume at `/data` | **Persistent** — survives ACA restarts |
| Mem0 lessons | In-memory | Ephemeral |
| Workflow state | In-memory `StateStore` | Ephemeral — reseeded by simulator on restart |
| Audit ledger | In-memory or Azure Blob | Persistent if blob configured |

The Bicep provisions an Azure Files share (`zava-data`) mounted at `/data`
on the ACA container. KuzuDB writes to `/data/entity_graph.kuzu` — the
entity graph persists across restarts without Cosmos DB.

---

## Citadel APIM integration

Set `AZURE_OPENAI_ENDPOINT` to the Citadel gateway URL. The control plane
uses `DefaultAzureCredential` (via UAMI) for all Azure SDK calls. The
APIM validates the JWT against the product's access contract.

To create a Zava access contract, use `citadel-spoke-onboarding`.

---

## Node MCP mock sidecars (optional)

For demos that need external-system simulation, deploy mock servers as
separate ACA apps. Each mock is a ~50-line Express server reading a JSON
fixture. Use `foundry-mcp-aca` to deploy them.

| Pack | Mocks | Ports |
|------|-------|-------|
| POC1 (expense-claim) | workday, concur, maconomy | 4101-4103 |
| POC2 (hiring) | greenhouse, linkedin, workday-hr, graph, servicenow, acs, heygen | 4201-4207 |
| Agency (enterprise) | salesforce, mediaocean, prisma, kinesso, sap, workday-hcm, docusign | 4200-4226 |

> **For most demos, mocks aren't needed.** The 46 in-process MCP tools
> handle the core demo.

---

## Connecting to Threadlight PoCs

Zava is the **composition layer** that runs 38 domains; each domain
is a Threadlight process. On the Citadel hub, each Threadlight PoC
has its own APIM product access contract. Zava's fleet manager routes
LLM calls through the appropriate backend pool based on domain config.

---

## Verified deployment (fruocco-2)

Tested on ACA with `LLM_RUNTIME=fake` (no real LLM calls). The in-process
workflow runner replaces Azure Durable Functions with a generator-based
orchestrator running inside the same uvicorn process.

**Fleet test results (v9, 2026-05-24):** 34/34 workflows completed, 0 failed.

| Domain type | IDs tested | Status |
|-------------|-----------|--------|
| expense-claim | EXP-0001..0004 | ✅ completed |
| hiring (10-phase pipeline) | HIRE-0001..0002 | ✅ completed |
| employee-transfer | EXF-0001 | ✅ completed |
| training-request | TRQ-0001 | ✅ completed |
| ap-invoice, contract-renewal, contract-review, employee-onboarding, it-access-request, perf-review, privacy-dpia, purchase-order, treasury-fx, vendor-kyc, travel | 1 each + constellation | ✅ completed |
| creative-campaign | CMP-0001..0002 | ✅ completed |

---

## Local development

```bash
uv sync && npm install && npm run build
make up    # azurite + mocks + fastapi + 3 SPAs

# Ports: Operator :5273, Portal :5274, Blueprint :5275, API :3101
curl -X POST http://localhost:3101/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"scenario":"demo-fail"}'
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| ACR build timeout | Increase `--timeout` to 1200s; `github-copilot-sdk` may fail — pin to `0.2.0` |
| ACR build `--mount=type=cache` fails | ACR doesn't support BuildKit; use plain `RUN` in Dockerfile |
| `ModuleNotFoundError: kuzu` | Native deps missing in runtime stage — check `libpango`, `libcairo` |
| SPAs show blank page | Check `/app/static/client/index.html` exists in container; verify StaticFiles mount order |
| SSE streams drop | ACA ingress timeout is 240s default — set `--session-affinity sticky` for long-lived SSE |
| KuzuDB `PermissionDenied` | Azure Files volume not mounted — check ACA env volume config |
| `torch` import crashes | CPU-only wheel not installed — verify `UV_EXTRA_INDEX_URL` in build stage |
| Hiring workflows show `status=failed` at Voice | HITL auto-resolve returns `"approved"` but orchestrator expects `"approve"`. Fix `_auto_resolve_hitl()` decision vocabulary |
| Validators return `{"ok": true}` but next phase crashes | Fake-mode validators must return domain-specific Pydantic stubs, not raw passthrough. Each segment's `SegmentXOutput` has required fields (`verdict`, `jd_draft_id`, etc.) |
| State wiped after ACA revision update | In-memory `StateStore` is ephemeral; re-inject via `/api/simulator/inject` after new revisions |
| mem0 `401 missing subscription key` | Non-blocking — caught in try/except. mem0 calls embeddings via APIM without the subscription key header. Ignore in `LLM_RUNTIME=fake` mode |
| Event bus `dropped N events (cap=20/sec)` | Burst injection exceeds the 20/sec EventBus cap. Use `/api/simulator/inject` (single) instead of `/api/simulator/inject-burst` for testing |

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
| [`foundry-mcp-aca`](../foundry-mcp-aca/) | Deploy MCP mock sidecars as ACA containers |
| [`azure-tenant-isolation`](../azure-tenant-isolation/) | **MANDATORY** before any `az`/`azd` command |
| [`compose-org`](../compose-org/) | Forks Zava into a customer-flavoured digital clone |
| [`research-company`](../research-company/) | Produces the org-brief YAML that `compose-org` consumes |

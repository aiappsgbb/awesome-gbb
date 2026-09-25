# Customer goal — `foundry-mcp-aca` skill smoke

You are running an end-to-end smoke for the `foundry-mcp-aca` skill on the
GitHub Actions runner. The goal is to **prove the documented deployment +
wire-protocol contract works**: deploy a minimal FastMCP server to Azure
Container Apps via `azd up`, then perform an MCP-over-HTTP roundtrip
(`initialize` + `tools/list` + `tools/call`) against the deployed FQDN
and verify the MCP 2025-06-18 wire protocol (`initialize` → 200,
`notifications/initialized` → 202, `tools/list` → 200, `tools/call` → 200
with exact payload). The MCP HTTP roundtrip is the value contract this skill exists
to enable — everything else is plumbing.

You are NOT testing a tutorial, README, or design doc. You are testing
whether a customer following the skill verbatim ends up with a working
MCP server reachable from Foundry hosted agents over the network. Pretend
you are that customer.

**CRITICAL — this is an EXECUTION smoke, not a catalog inspection.**
Do NOT read, view, grep, glob, or open ANY repository file other than
what you create in the scratch project. Specifically forbidden:
- `skills/foundry-mcp-aca/SKILL.md` (the bootstrap echo is audit
  evidence only — do NOT `cat`/`view` the file)
- `scripts/tests/*.py` (test files)
- `.github/workflows/*.yml` (workflow definitions)
- `skills/foundry-mcp-aca/references/*` (audit trail, pin files), except
  executing the prescribed `fixture_ownership.py` and sourcing
  `fixture_cleanup_guard.sh`; do not inspect or rewrite either helper
- `.github/skill-deps.yml`, `.github/ci-shared-preamble.md`
- Any file under `skills/`, `docs/`, or `scripts/`

**CRITICAL — Bash-only execution and deterministic authoring (MANDATORY).**
NEVER use Edit, Create, Write, or any other file-editing tool anywhere in this smoke, for any purpose.
This includes `~/.copilot/session-state/*/plan.md`.
Do not create a plan file.
Every action in this smoke must be one of the prescribed Bash tool actions.
Your FIRST action must be one Bash tool invocation executing the complete
Step 0 bootstrap block exactly as written. Do not prepend, append, split,
merge, or reorder that block. Only after it returns zero may you invoke
the prescribed Step 2 scaffold block.

**CRITICAL — deterministic scaffold authoring (MANDATORY).**
Invoke only the prescribed Bash block in Step 2 to author the six scaffold files.
NEVER use Edit, Create, or Write file tools.
Never inspect or patch the generated files after the scaffold block runs.
If the scaffold block fails, write SMOKE_RESULT=FAIL and stop.
There is no second file-write path.

This prompt contains EVERYTHING you need. Execute Steps 0–7 exactly as
written. If a step's command fails, write SMOKE_RESULT=FAIL with the
error and stop. Do NOT search the repository for fixes, alternative
approaches, or "the smallest safe fix". Do NOT run the test suite.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You
ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Doing so spawns
a nested CLI process WITHOUT GitHub auth (the workflow only sets
`COPILOT_PROVIDER_BEARER_TOKEN` for our Foundry routing, NOT
`COPILOT_GITHUB_TOKEN`), which will (a) crash with "No authentication
information found" and (b) overwrite this run's transcript at
`/tmp/foundry-mcp-aca-transcript.log`, defeating the workflow's retry
classifier (AGENTS.md § 9.7 Pattern 19 addendum). The workflow ALREADY
captures your output via the outer `tee` — your job is to EXECUTE Steps
0–7 directly in Bash tool calls, not to "run the smoke".

---

## Environment available (pre-provisioned in CI)

The workflow has already authenticated you via OIDC. These env vars are
exported into your shell:

- `AZURE_CLIENT_ID` — the CI UAMI `uami-awesome-gbb-ci`
- `AZURE_TENANT_ID` — the `fruocco` tenant
- `AZURE_SUBSCRIPTION_ID` — the CI subscription
- `ACR_LOGIN_SERVER` — `acrawesomegbbci.azurecr.io`

Pre-granted RBAC on the CI UAMI (do NOT re-grant — propagation takes
5-15 min and races the workflow timeout, per AGENTS.md § 9.7 Pattern 7):

- `Contributor` on resource group `rg-awesome-gbb-ci`
- `AcrPush` on registry `acrawesomegbbci`
- `Cognitive Services OpenAI User` on `aif-awesome-gbb-ci` (not used by
  this fixture; documented for completeness)

Pre-provisioned shared infrastructure you MUST reference via Bicep
`existing` (NOT create new):

- Resource group: `rg-awesome-gbb-ci` (Sweden Central)
- Container Apps Environment: `cae-awesome-gbb-ci`
- Container Registry: `acrawesomegbbci`
- User-Assigned Managed Identity (for ACR pull): the same CI UAMI,
  referenced by `AZURE_CLIENT_ID`. Its resource ID is
  `/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.ManagedIdentity/userAssignedIdentities/uami-awesome-gbb-ci`.

---

## Tooling pre-installed (Pattern 15 — do NOT re-install)

- `az` (Azure CLI, pre-installed on ubuntu-latest)
- `azd` (Azure Developer CLI, installed by the workflow's
  `azure/setup-azd@v2` step at `/usr/local/bin/azd`)
- `docker` (pre-installed on ubuntu-latest, used by `azd` for local image
  inspection if needed)
- `curl`, `jq`, `python3`, `uuidgen`

DO NOT run any of these forbidden patterns (Pattern 15 — agent-side
remediation wastes 3-5 min of budget per run and masks real workflow
bugs):

- `command -v azd` / `which azd` / `find / -name azd` — `azd` is
  pre-installed; verify by reading the version: `azd version`
- `curl -fsSL https://aka.ms/install-azd-script-linux | bash` — tarball
  install detour; if `azd` is missing, that is a workflow bug, not a
  fixture bug
- `apt-get install` of any of the listed tools

---

## Step 0 — deterministic audit + auth + state bootstrap (FIRST ACTION)

Before Step 2 prepares the image, complete the skill's capability/identity
preflight using the approved standing CI target. Record environment support,
registry authorization mode, effective pull boundary and exact identities for
invoke/source/result readback. An unreadable or incompatible capability is a
blocker, never permission to change shared registry mode, networking or grants.
Authentication is required before deploying the real MCP image. The fixture
never publishes a tool server first and adds its perimeter afterward.

The block below is the sole audit, authentication, naming, and initial-state
path. Its state file is deliberately removed before validation and published
with `mv` only after `azd auth login` succeeds. Therefore Step 2 cannot run
from state created by an unauthenticated invocation.

`MCP_AUTH_APP_CLIENT_ID` is the client ID of the standing API audience;
`AZURE_CLIENT_ID` is the distinct authorized caller. The provisioning block
requires both and validates the complete policy before its first Azure write.
Only the explicitly named `auth_config.py`, `fixture_ownership.py` and
`fixture_cleanup_guard.sh` helpers may be executed from the repository;
the catalog-inspection prohibition is unchanged.

Do NOT invent additional credential checks (no `az ad sp show`, no
`az role assignment list`, no `az login --service-principal`). Do NOT
strict-equality-compare the subscription ID against env (Pattern 16/17).
The `az account show` command is show-don't-assert; explicit
`azd auth login` is the authentication gate.

### Deterministic bootstrap Bash block (MANDATORY)

```bash
set -Eeuo pipefail
echo "skills/foundry-mcp-aca/SKILL.md"
STATE_FILE="/tmp/foundry-mcp-aca-state.env"
STATE_TMP="${STATE_FILE}.tmp.$$"
FAIL() {
  trap - ERR
  rm -f "$STATE_TMP" "$STATE_FILE"
  printf 'SMOKE_RESULT=FAIL %s\n' "$1" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
}
trap 'FAIL "bootstrap block failed"' ERR
rm -f "$STATE_TMP" "$STATE_FILE"

for REQUIRED_VAR in GITHUB_WORKSPACE AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_SUBSCRIPTION_ID ACR_LOGIN_SERVER; do
  if [[ -z "${!REQUIRED_VAR:-}" ]]; then
    FAIL "auth context missing: ${REQUIRED_VAR}"
  fi
  echo "${REQUIRED_VAR}=set"
done
echo "MCP_AUTH_APP_CLIENT_ID=${MCP_AUTH_APP_CLIENT_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
azd auth login \
  --federated-credential-provider github \
  --client-id "$AZURE_CLIENT_ID" \
  --tenant-id "$AZURE_TENANT_ID" || FAIL "azd auth login failed"

SMOKE_RUN_ID=$(uuidgen | tr 'A-Z' 'a-z')
SUFFIX="${SMOKE_RUN_ID:0:8}"
APP_NAME="ci-smoke-mcp-${SUFFIX}"
PROJECT_DIR="${GITHUB_WORKSPACE}/.scratch/${APP_NAME}"
UAMI_RESOURCE_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.ManagedIdentity/userAssignedIdentities/uami-awesome-gbb-ci"
ACR_SERVER="$ACR_LOGIN_SERVER"
{
  printf 'APP_NAME=%s\n' "$APP_NAME"
  printf 'PROJECT_DIR=%s\n' "$PROJECT_DIR"
  printf 'UAMI_RESOURCE_ID=%s\n' "$UAMI_RESOURCE_ID"
  printf 'ACR_SERVER=%s\n' "$ACR_SERVER"
  printf 'SMOKE_RUN_ID=%s\n' "$SMOKE_RUN_ID"
} > "$STATE_TMP"
mv "$STATE_TMP" "$STATE_FILE"
trap - ERR
echo "APP_NAME=$APP_NAME"
```

---

## Step 1 — goal + scaffolding constraints

You will deploy a **tiny, self-contained FastMCP server** to Azure
Container Apps using `azd up`. The server exposes one `echo` tool and a
`/health` route. After `azd up` returns 0, you will resolve the
deployed FQDN and call the MCP HTTP endpoint with three JSON-RPC requests
(`initialize` + `tools/list` + `tools/call`) to prove the wire protocol works.

### State persistence between Bash tool calls

Copilot CLI runs each Bash tool invocation in a **fresh process** — env
vars set in one call are NOT available in the next. Step 0 atomically
publishes `APP_NAME`, `PROJECT_DIR`, `UAMI_RESOURCE_ID`, `ACR_SERVER` and `SMOKE_RUN_ID`
only after authentication succeeds. The next Bash tool invocation is the
single deterministic scaffold block in Step 2. It restores that state,
creates the scaffold directories, and enters `$PROJECT_DIR` in the
prescribed `source; mkdir; cd` order. All later Bash blocks retain their
explicit state restoration as written. Do NOT assume variables survive
between tool calls and do not create or replace initial state anywhere else.

### Scaffolding location

The Copilot CLI's shell-tool gate rejects `cd` outside `$GITHUB_WORKSPACE`
even with `--allow-all-tools`. The persisted `PROJECT_DIR` already selects
the workspace-backed, gitignored `.scratch/` location; use it exactly as
prescribed in Step 2 and do not choose another location.

### Pattern 25 framing — read this BEFORE you start

This fixture follows the **Pattern 25 marker-first / cleanup-second**
shape (AGENTS.md § 9.7 Pattern 25). The hard gates of this smoke are:

1. **`azd up` returns 0** (Bicep deploy + ACR remote build + revision
   reaches Running state)
2. **MCP HTTP roundtrip succeeds** (`initialize` returns 200 with
   `result.serverInfo.name` and `result.protocolVersion`; server assigns
   a non-empty `Mcp-Session-Id`; `notifications/initialized` returns
   HTTP 202; `tools/list` returns 200 with at least one tool in
   `result.tools[]`; `tools/call` on `echo` returns 200 with exact
   payload `"echoed: ci-probe"` and `isError` is not `true`)

Once BOTH hard gates pass, you write the PASS marker file **IMMEDIATELY
via the Bash tool** (see Step 5 below). Cleanup is hygiene — it happens
AFTER the marker is written. Teardown failure (timeout, OIDC TTL expiry,
preview-CLI flag drift) does NOT downgrade the smoke verdict. The
`rg-awesome-gbb-ci` janitor sweeps `ci-smoke-mcp-*` resources older than
7 days.

Do NOT chain marker emission after cleanup. The smoke is the contract;
cleanup is best-effort. It never authorizes deleting the shared resource group,
CAE, registry, identity or unproven image/deployment artifacts.

---

## Step 2 — create the deterministic scaffold

### Deterministic scaffold-authoring Bash block (MANDATORY)

```bash
source /tmp/foundry-mcp-aca-state.env || { printf 'SMOKE_RESULT=FAIL scaffold block failed\n' > /tmp/foundry-mcp-aca-smoke-result; exit 1; }
set -Eeuo pipefail
trap 'printf "SMOKE_RESULT=FAIL scaffold block failed\n" > /tmp/foundry-mcp-aca-smoke-result' ERR
if [[ -z "${APP_NAME:-}" || -z "${PROJECT_DIR:-}" || -z "${UAMI_RESOURCE_ID:-}" || -z "${ACR_SERVER:-}" || -z "${SMOKE_RUN_ID:-}" ]]; then printf 'SMOKE_RESULT=FAIL scaffold state incomplete\n' > /tmp/foundry-mcp-aca-smoke-result; exit 1; fi
mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"
cd "$PROJECT_DIR"
cat > src/server.py <<'PY'
"""Tiny MCP server for the CI smoke — single `echo` tool + /health route."""
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("ci-smoke-mcp")


@mcp.custom_route("/health", methods=["GET"])
async def health(_req: Request) -> PlainTextResponse:
    return PlainTextResponse("ok", status_code=200)


@mcp.tool()
async def echo(message: str) -> str:
    """Echo back the message prefixed with `echoed: `."""
    return f"echoed: {message}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
PY
cat > src/requirements.txt <<'REQ'
fastmcp~=2.14.7
REQ
cat > src/Dockerfile <<'DOCKER'
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8080
CMD ["python", "server.py"]
DOCKER
cat > infra/main.bicep <<'BICEP'
@description('Deployment region — must match the CAE.')
param location string = 'swedencentral'

@description('Container App name (also used as ACR repo tag).')
param appName string

@description('Unique fixture run identity, bound to the pre-create inventory.')
param smokeRunId string

@description('Container image reference. Defaults to placeholder; azd deploy patches with the real image.')
param image string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Resource ID of the user-assigned managed identity used for ACR pull.')
param uamiResourceId string

@description('ACR login server (e.g. myacr.azurecr.io). Must be explicit — do NOT derive from image param.')
param acrServer string

@description('Name of the pre-provisioned Container Apps Environment.')
param caeName string = 'cae-awesome-gbb-ci'

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: caeName
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: {
    'azd-service-name': appName
    'gbb-smoke-run': smokeRunId
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiResourceId}': {}
    }
  }
  properties: {
    environmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrServer
          identity: uamiResourceId
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: image
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          // Note: probes are omitted for the placeholder→deploy lifecycle.
          // The placeholder image (containerapps-helloworld) serves on port 80
          // while the real server serves on 8080. Probes targeting 8080 would
          // prevent the placeholder revision from becoming healthy, potentially
          // blocking azd provision. azd deploy immediately swaps the image to
          // the real server which does serve on 8080. Production deployments
          // should add liveness/startup probes after the first successful deploy.
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output appName string = app.name

resource authConfig 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: app
  name: 'current'
  properties: loadJsonContent('mcp-authconfig.json').properties
}
BICEP
cat > infra/main.parameters.json <<PARAMS
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "appName": { "value": "${APP_NAME}" },
    "uamiResourceId": { "value": "${UAMI_RESOURCE_ID}" },
    "acrServer": { "value": "${ACR_SERVER}" },
    "smokeRunId": { "value": "${SMOKE_RUN_ID}" }
  }
}
PARAMS
cat > azure.yaml <<AZDYAML
name: ${APP_NAME}
metadata:
  template: ci-smoke-mcp@0.0.1
services:
  ${APP_NAME}:
    project: ./src
    language: python
    host: containerapp
    docker:
      path: Dockerfile
      context: .
AZDYAML
```

---

## Step 4 — `azd up` (HARD GATE)

The Bicep template uses a placeholder image (`containerapps-helloworld:latest`)
for the initial provision. The `registries` block explicitly references the ACR
server (not derived from the image) so ACA only uses managed-identity auth for
ACR pulls — the MCR placeholder is pulled anonymously since its server doesn't
match any configured registry. `azd up` runs provision (creates the Container App
with placeholder), then immediately builds the real image via the `azure.yaml`
service binding and patches the Container App. The `azd-service-name: $APP_NAME`
tag in Bicep (matching the azure.yaml service key) enables `azd deploy` to locate
and update the resource. No probes are configured — the placeholder revision
starts regardless of port mismatch (port 80 vs targetPort 8080) and `azd deploy`
immediately swaps to the real image.

The exact provision block below creates the `azd` environment structure
directly and then runs `azd up`. Do NOT use `azd env new` or `azd env set`;
they require interactive prompts that fail in headless CI. The block sources
the state that Step 0 publishes only after successful `azd auth login`, so
provision cannot begin on an unauthenticated path.

Before the first create, the ownership helper verifies the exact approved
subscription/tenant and existing resource group, proves the exact app ID is
absent, and persists a private inventory. The Bicep run tag binds a later
readback to that intent; a name prefix/suffix alone is not ownership proof.
The inventory survives a failed step and must never be reset to permit a retry.
An existing app or inventory blocks deployment rather than being adopted.

The EXIT guard is appended to the existing state file so every later Bash
step restores it. Any intermediate failure reconciles the exact app ID,
attempts only owned-app cleanup, and preserves the original failure status.
An uncertain `azd up` is not automatically replayed, including on a resolver
race: inspect the saved inventory and receipts first.

### Deterministic provision Bash block (MANDATORY)

```bash
source /tmp/foundry-mcp-aca-state.env || { printf 'SMOKE_RESULT=FAIL provision state missing\n' > /tmp/foundry-mcp-aca-smoke-result; exit 1; }
set -Eeuo pipefail
trap 'printf "SMOKE_RESULT=FAIL provision block failed\n" > /tmp/foundry-mcp-aca-smoke-result' ERR
cd "$PROJECT_DIR"

AZD_ENV_DIR="${PROJECT_DIR}/.azure/${APP_NAME}"
mkdir -p "$AZD_ENV_DIR"
cat > "${PROJECT_DIR}/.azure/config.json" <<EOF
{ "version": 1, "defaultEnvironment": "${APP_NAME}" }
EOF
cat > "${AZD_ENV_DIR}/.env" <<EOF
AZURE_ENV_NAME=${APP_NAME}
AZURE_LOCATION=swedencentral
AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID}
AZURE_RESOURCE_GROUP=rg-awesome-gbb-ci
AZURE_TENANT_ID=${AZURE_TENANT_ID}
APP_NAME=${APP_NAME}
UAMI_RESOURCE_ID=${UAMI_RESOURCE_ID}
ACR_SERVER=${ACR_SERVER}
AZURE_CONTAINER_REGISTRY_ENDPOINT=${ACR_SERVER}
EOF
echo "azd env created at $AZD_ENV_DIR"

python3 "$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/python/auth_config.py" \
  --tenant "$AZURE_TENANT_ID" --audience "${MCP_AUTH_APP_CLIENT_ID:?API audience required}" \
  --caller "$AZURE_CLIENT_ID" > infra/mcp-authconfig.json

OWNERSHIP_HELPER="$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/python/fixture_ownership.py"
OWNERSHIP_ARGS=(
  --state /tmp/foundry-mcp-aca-ownership.json
  --evidence /tmp/foundry-mcp-aca-smoke-evidence
  --run-id "$SMOKE_RUN_ID"
  --subscription "$AZURE_SUBSCRIPTION_ID" --tenant "$AZURE_TENANT_ID"
  --resource-group rg-awesome-gbb-ci --app-name "$APP_NAME" --registry "$ACR_SERVER"
)
python3 "$OWNERSHIP_HELPER" prepare "${OWNERSHIP_ARGS[@]}"
printf '\nsource "$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/bash/fixture_cleanup_guard.sh"\n' \
  >> /tmp/foundry-mcp-aca-state.env
source "$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/bash/fixture_cleanup_guard.sh"
python3 "$OWNERSHIP_HELPER" start "${OWNERSHIP_ARGS[@]}"
if azd up --no-prompt; then
  python3 "$OWNERSHIP_HELPER" capture "${OWNERSHIP_ARGS[@]}"
else
  DEPLOY_STATUS=$?
  printf 'SMOKE_RESULT=FAIL azd up exited %s; reconcile owned inventory\n' "$DEPLOY_STATUS" \
    > /tmp/foundry-mcp-aca-smoke-result
  exit "$DEPLOY_STATUS"
fi
```

Total budget for this step: ~8-12 min (ACR remote build ~3-5 min + Bicep
provision ~3-5 min + image swap ~1-2 min).

---

## Step 5 — MCP HTTP roundtrip (HARD GATE)

Resolve the FQDN of the deployed Container App. Prefer the `azd env get-values`
output, but fall back to `az containerapp show`:

```bash
source /tmp/foundry-mcp-aca-state.env
cd "$PROJECT_DIR"
FQDN=$(azd env get-values | awk -F= '/^FQDN=/ {gsub(/"/, "", $2); print $2}')
if [ -z "$FQDN" ]; then
  FQDN=$(az containerapp show -g rg-awesome-gbb-ci -n "$APP_NAME" \
    --query 'properties.configuration.ingress.fqdn' -o tsv)
fi
echo "FQDN=$FQDN"
[ -n "$FQDN" ] || {
  printf 'SMOKE_RESULT=FAIL could not resolve FQDN for %s\n' "$APP_NAME" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
}
echo "FQDN=$FQDN" >> /tmp/foundry-mcp-aca-state.env
```

Call `initialize`. The MCP streamable-HTTP spec requires a dual
`Accept: application/json, text/event-stream` header so the server can
choose single-response vs streaming. The endpoint is `/mcp` (FastMCP
2.x mount path; see SKILL.md L580-593 + L603 critical gotchas).
Capture response headers to extract `mcp-session-id` for subsequent
requests:

```bash
source /tmp/foundry-mcp-aca-state.env
TOKEN=$(az account get-access-token --resource "api://$MCP_AUTH_APP_CLIENT_ID" --query accessToken -o tsv)
INIT_RESPONSE=$(curl -sS --connect-timeout 10 --max-time 30 -D /tmp/mcp-init-headers.txt \
  -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "id": 1,
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": { "name": "ci-smoke", "version": "1.0" }
    }
  }')

INIT_CODE=$(echo "$INIT_RESPONSE" | grep '__HTTP_CODE__' | cut -d: -f2)
INIT_BODY=$(echo "$INIT_RESPONSE" | sed '/__HTTP_CODE__/d')

echo "initialize HTTP=$INIT_CODE"
echo "initialize body: $INIT_BODY"

if [ "$INIT_CODE" != "200" ]; then
  printf 'SMOKE_RESULT=FAIL initialize returned HTTP %s\n' "$INIT_CODE" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

# Extract mcp-session-id from response headers (case-insensitive grep)
SESSION_ID=$(grep -i '^mcp-session-id:' /tmp/mcp-init-headers.txt | tr -d '\r' | cut -d' ' -f2)
echo "mcp-session-id=$SESSION_ID"

# Streamable-HTTP servers may return either JSON or SSE. Extract the
# JSON object: if the body starts with `data: `, strip the SSE prefix.
INIT_JSON=$(echo "$INIT_BODY" | sed -n 's/^data: //p' | head -1)
[ -z "$INIT_JSON" ] && INIT_JSON="$INIT_BODY"

SERVER_NAME=$(echo "$INIT_JSON" | jq -r '.result.serverInfo.name // empty')
if [ -z "$SERVER_NAME" ]; then
  printf 'SMOKE_RESULT=FAIL initialize missing result.serverInfo.name\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
echo "serverInfo.name=$SERVER_NAME"

# Capture negotiated protocol version (MCP 2025-06-18 lifecycle spec)
PROTOCOL_VERSION=$(echo "$INIT_JSON" | jq -r '.result.protocolVersion // empty')
echo "protocolVersion=$PROTOCOL_VERSION"

# Protocol version is mandatory per MCP 2025-06-18
if [ -z "$PROTOCOL_VERSION" ]; then
  printf 'SMOKE_RESULT=FAIL initialize did not return result.protocolVersion\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

# Session ID is required for this fixture — FastMCP always assigns one
if [ -z "$SESSION_ID" ]; then
  printf 'SMOKE_RESULT=FAIL initialize did not return Mcp-Session-Id header\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

# Persist MCP exchange state for subsequent Bash fences
echo "SESSION_ID=$SESSION_ID" >> /tmp/foundry-mcp-aca-state.env
echo "PROTOCOL_VERSION=$PROTOCOL_VERSION" >> /tmp/foundry-mcp-aca-state.env
```

Send `notifications/initialized` (required by MCP protocol before
tools/list). Per MCP 2025-06-18, notifications MUST return HTTP 202
Accepted. Capture and assert the exact status code:

```bash
source /tmp/foundry-mcp-aca-state.env
TOKEN=$(az account get-access-token --resource "api://$MCP_AUTH_APP_CLIENT_ID" --query accessToken -o tsv)
SESSION_ARGS=(-H "Mcp-Session-Id: $SESSION_ID" -H "MCP-Protocol-Version: $PROTOCOL_VERSION")

INIT_NOTIFY_BODY=$(curl -sS --connect-timeout 10 --max-time 30 -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  "${SESSION_ARGS[@]}" \
  -d '{ "jsonrpc": "2.0", "method": "notifications/initialized", "params": {} }')

INIT_NOTIFY_CODE=$(echo "$INIT_NOTIFY_BODY" | grep '__HTTP_CODE__' | cut -d: -f2)
INIT_NOTIFY_CONTENT=$(echo "$INIT_NOTIFY_BODY" | sed '/__HTTP_CODE__/d' | tr -d '[:space:]')

echo "notifications/initialized HTTP=$INIT_NOTIFY_CODE body='$INIT_NOTIFY_CONTENT'"
if [ "$INIT_NOTIFY_CODE" != "202" ]; then
  printf 'SMOKE_RESULT=FAIL notifications/initialized returned HTTP %s (expected 202)\n' "$INIT_NOTIFY_CODE" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
if [ -n "$INIT_NOTIFY_CONTENT" ]; then
  printf 'SMOKE_RESULT=FAIL notifications/initialized returned non-empty body (expected empty per MCP spec)\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
```

Then call `tools/list` (with session and protocol version headers):

```bash
source /tmp/foundry-mcp-aca-state.env
TOKEN=$(az account get-access-token --resource "api://$MCP_AUTH_APP_CLIENT_ID" --query accessToken -o tsv)
SESSION_ARGS=(-H "Mcp-Session-Id: $SESSION_ID" -H "MCP-Protocol-Version: $PROTOCOL_VERSION")
TOOLS_RESPONSE=$(curl -sS --connect-timeout 10 --max-time 30 -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  "${SESSION_ARGS[@]}" \
  -d '{ "jsonrpc": "2.0", "method": "tools/list", "id": 2 }')

TOOLS_CODE=$(echo "$TOOLS_RESPONSE" | grep '__HTTP_CODE__' | cut -d: -f2)
TOOLS_BODY=$(echo "$TOOLS_RESPONSE" | sed '/__HTTP_CODE__/d')

echo "tools/list HTTP=$TOOLS_CODE"
echo "tools/list body: $TOOLS_BODY"

if [ "$TOOLS_CODE" != "200" ]; then
  printf 'SMOKE_RESULT=FAIL tools/list returned HTTP %s\n' "$TOOLS_CODE" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

TOOLS_JSON=$(echo "$TOOLS_BODY" | sed -n 's/^data: //p' | head -1)
[ -z "$TOOLS_JSON" ] && TOOLS_JSON="$TOOLS_BODY"

TOOL_COUNT=$(echo "$TOOLS_JSON" | jq -e -r 'select(.jsonrpc == "2.0" and (.error == null) and (.result.tools | type == "array") and (.result.tools | length >= 1)) | .result.tools | length') || {
  printf 'SMOKE_RESULT=FAIL tools/list response failed JSON-RPC schema or non-empty tools array validation\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
}
if [ -z "$TOOL_COUNT" ] || [ "$TOOL_COUNT" -lt 1 ]; then
  printf 'SMOKE_RESULT=FAIL tools/list returned 0 tools\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
echo "tools/list returned $TOOL_COUNT tool(s)"
```

Then call `tools/call` on the `echo` tool with a known probe message.
The scaffolded server's `echo` tool returns `"echoed: <message>"`. Assert
the exact payload and verify `isError` is not `true`:

```bash
source /tmp/foundry-mcp-aca-state.env
TOKEN=$(az account get-access-token --resource "api://$MCP_AUTH_APP_CLIENT_ID" --query accessToken -o tsv)
SESSION_ARGS=(-H "Mcp-Session-Id: $SESSION_ID" -H "MCP-Protocol-Version: $PROTOCOL_VERSION")
CALL_RESPONSE=$(curl -sS --connect-timeout 10 --max-time 30 -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json, text/event-stream" \
  "${SESSION_ARGS[@]}" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 3,
    "params": {
      "name": "echo",
      "arguments": { "message": "ci-probe" }
    }
  }')

CALL_CODE=$(echo "$CALL_RESPONSE" | grep '__HTTP_CODE__' | cut -d: -f2)
CALL_BODY=$(echo "$CALL_RESPONSE" | sed '/__HTTP_CODE__/d')

echo "tools/call HTTP=$CALL_CODE"
echo "tools/call body: $CALL_BODY"

if [ "$CALL_CODE" != "200" ]; then
  printf 'SMOKE_RESULT=FAIL tools/call returned HTTP %s\n' "$CALL_CODE" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

CALL_JSON=$(echo "$CALL_BODY" | sed -n 's/^data: //p' | head -1)
[ -z "$CALL_JSON" ] && CALL_JSON="$CALL_BODY"

# Verify isError is not true
IS_ERROR=$(echo "$CALL_JSON" | jq -r '.result.isError // false')
if [ "$IS_ERROR" = "true" ]; then
  printf 'SMOKE_RESULT=FAIL tools/call returned isError=true\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi

# Verify exact echo payload: "echoed: ci-probe"
ECHO_TEXT=$(echo "$CALL_JSON" | jq -r '.result.content[0].text // empty')
if [ "$ECHO_TEXT" != "echoed: ci-probe" ]; then
  printf 'SMOKE_RESULT=FAIL tools/call echo expected "echoed: ci-probe" got "%s"\n' "$ECHO_TEXT" > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
echo "tools/call echo payload verified: $ECHO_TEXT"
```

If all three calls (initialize, tools/list, tools/call) return 200 with
conformant bodies, the protocol gate has passed. Proceed to Step 5b; do not
write a PASS marker before the required authorization checks.

DO NOT use `azd ai mcp` preview-CLI subcommands or any other preview
CLI that hides the HTTP wire protocol (Pattern 16). The HTTP endpoint
is the GA surface.

---

## Step 5b — Easy Auth and loaded caller policy (HARD GATE)

Layer 1 of the skill's security model is ACA built-in auth: the platform
must return **401** to an unauthenticated caller and let a caller presenting
a valid Entra bearer token for `api://$MCP_AUTH_APP_CLIENT_ID` through (not
401). Steps 1–5 already proved the server works over the wire; this step
proves the documented `## Securing your MCP server` § "Layer 1 — Identity
perimeter" contract on the live app.

The API audience is mandatory and was validated before provisioning. Do not
skip this gate or accept an unauthenticated base smoke as its replacement.

```bash
if [ -z "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
  printf 'SMOKE_RESULT=FAIL API audience missing\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
```

When `MCP_AUTH_APP_CLIENT_ID` IS set, run all of the following. Any failure
here is a HARD FAIL — write `SMOKE_RESULT=FAIL <reason>` to
`/tmp/foundry-mcp-aca-smoke-result` inline and stop.

1. **Retain the original policy for the bounded negative test.** It was
   provisioned before the MCP image, not added to a public tool server:

   ```bash
   source /tmp/foundry-mcp-aca-state.env
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     cp "$PROJECT_DIR/infra/mcp-authconfig.json" /tmp/mcp-authconfig.json
   fi
   ```

2. **Wait for the auth config to take effect and assert 401** (Easy Auth is a
   control-plane change; poll up to 6× with a 10 s back-off, per the
   ACA-control-plane race guidance in AGENTS.md § 9.7 Pattern 9):

   ```bash
   source /tmp/foundry-mcp-aca-state.env
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     CODE=""
     for i in $(seq 1 6); do
       CODE=$(curl -sS --connect-timeout 10 --max-time 30 -o /dev/null -w '%{http_code}' \
         -H 'Accept: application/json, text/event-stream' \
         "https://${FQDN}/mcp")
       [ "$CODE" = "401" ] && break
       sleep 10
     done
     echo "unauth status: $CODE"
     if [ "$CODE" != "401" ]; then
       printf 'SMOKE_RESULT=FAIL auth proof: expected 401 unauth, got %s\n' "$CODE" \
         > /tmp/foundry-mcp-aca-smoke-result
       exit 1
     fi
   fi
   ```

3. **Acquire a token and assert the authed call is 200.** The CI managed
   identity requests a token for the app's audience, then repeats the MCP
   `initialize` round-trip WITH the bearer header:

   ```bash
   source /tmp/foundry-mcp-aca-state.env
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     TOKEN=$(az account get-access-token \
       --resource "api://$MCP_AUTH_APP_CLIENT_ID" \
       --query accessToken -o tsv)
     AUTHED_CODE=$(curl -sS --connect-timeout 10 --max-time 30 -o /tmp/mcp-authed.json -w '%{http_code}' \
       -X POST "https://${FQDN}/mcp" \
       -H 'Content-Type: application/json' \
       -H 'Accept: application/json, text/event-stream' \
       -H "Authorization: Bearer $TOKEN" \
       -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ci","version":"1"}}}')
     echo "authed status: $AUTHED_CODE"
     case "$AUTHED_CODE" in
       200) echo "auth proof: 401 unauth / authed $AUTHED_CODE OK" ;;
       *)
         printf 'SMOKE_RESULT=FAIL auth proof: valid token expected 2xx, got %s (401=aud/authz mismatch for api://%s or bare %s; 403=caller not in allowedApplications)\n' \
           "$AUTHED_CODE" "$MCP_AUTH_APP_CLIENT_ID" "$MCP_AUTH_APP_CLIENT_ID" \
           > /tmp/foundry-mcp-aca-smoke-result
         exit 1 ;;
     esac
   fi
   ```

Both assertions must hold before the caller-exclusion test; do not skip it.

4. **Valid token, excluded caller must be denied (mandatory when auth enabled).**
   Use the standing worker UAMI client ID only as the alternative ACL entry on
   this run-owned echo app. Keep the SAME CI token/audience for the negative
   request; this tests caller authorization, not an invalid audience. Restore
   the exact approved CI-caller policy even on failure. Never change the worker
   identity or any other app, and never mint a worker token.

   ```bash
   source /tmp/foundry-mcp-aca-state.env
   set -euo pipefail
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     TOKEN=$(timeout 40 az account get-access-token --resource "api://$MCP_AUTH_APP_CLIENT_ID" --query accessToken -o tsv)
     test -n "${MCP_ACA_JOBS_WORKER_IDENTITY_ID:-}" || exit 1
     NEGATIVE_CALLER=$(timeout 40 az identity show --ids "$MCP_ACA_JOBS_WORKER_IDENTITY_ID" \
       --query clientId -o tsv --only-show-errors)
     test -n "$NEGATIVE_CALLER" && test "$NEGATIVE_CALLER" != "$AZURE_CLIENT_ID" || exit 1
     AUTH_URL="https://management.azure.com/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.App/containerApps/$APP_NAME/authConfigs/current?api-version=2025-01-01"
     POLICY_RESTORE_ATTEMPTED=0
     restore_ci_policy() {
       [ "$POLICY_RESTORE_ATTEMPTED" -eq 0 ] || return 1
       POLICY_RESTORE_ATTEMPTED=1
       timeout 60 az rest --method put --url "$AUTH_URL" --body @/tmp/mcp-authconfig.json --only-show-errors >/dev/null
     }
     restore_policy_and_preserve_failure() {
       local original_status=$?
       trap - EXIT
       if ! restore_ci_policy; then
         echo "NOTE: auth policy restoration remains unverified" >&2
       fi
       if [ "$original_status" -ne 0 ]; then
         if ! fixture_owned_cleanup; then
           echo "NOTE: teardown incomplete; preserve original failure and ownership evidence" >&2
         fi
       fi
       exit "$original_status"
     }
     trap restore_policy_and_preserve_failure EXIT
     python3 "$GITHUB_WORKSPACE/skills/foundry-mcp-aca/references/python/auth_config.py" \
       --tenant "$AZURE_TENANT_ID" --audience "$MCP_AUTH_APP_CLIENT_ID" \
       --caller "$NEGATIVE_CALLER" > /tmp/mcp-authconfig-negative.json
     timeout 60 az rest --method put --url "$AUTH_URL" --body @/tmp/mcp-authconfig-negative.json --only-show-errors >/dev/null
     DENIED_CODE=""
     for attempt in $(seq 1 6); do
       DENIED_CODE=$(curl -sS --connect-timeout 10 --max-time 30 -o /dev/null -w '%{http_code}' \
         -H "Authorization: Bearer $TOKEN" -H 'Accept: application/json, text/event-stream' \
         "https://${FQDN}/mcp")
       [ "$DENIED_CODE" = 403 ] && break
       sleep 10
     done
     restore_ci_policy || exit 1
     trap fixture_owned_exit EXIT
     [ "$DENIED_CODE" = 403 ] || {
       printf 'SMOKE_RESULT=FAIL valid token excluded caller was not denied\n' > /tmp/foundry-mcp-aca-smoke-result
       exit 1
     }
     echo "CALLER_ACL_NEGATIVE_403"
     RESTORED_CODE=""
     for attempt in $(seq 1 6); do
       RESTORED_CODE=$(curl -sS --connect-timeout 10 --max-time 30 -o /tmp/mcp-restored.json -w '%{http_code}' \
         -X POST "https://${FQDN}/mcp" \
         -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
         -H 'Accept: application/json, text/event-stream' \
         -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ci-restored","version":"1"}}}')
       [ "$RESTORED_CODE" = 200 ] && break
       sleep 10
     done
     [ "$RESTORED_CODE" = 200 ] || {
       printf 'SMOKE_RESULT=FAIL original caller policy restored in ARM but not proven loaded\n' > /tmp/foundry-mcp-aca-smoke-result
       exit 1
     }
     echo "CALLER_ACL_RESTORED_200"
   fi
   ```

---

## Step 6 — Write the PASS marker IMMEDIATELY (Pattern 12)

The MOMENT the Step 4 provision gate, the Step 5 MCP round-trip gate, AND
the Step 5b auth gate, including the restored positive policy, have all
succeeded, write the deterministic PASS
marker file via the Bash tool. The file's literal byte content is what
CI grades — NOT your assistant text reply. The workflow evaluator
(`.github/workflows/skill-test.yml`) reads `/tmp/foundry-mcp-aca-smoke-result`
and `cmp -s` against `printf 'SMOKE_RESULT=PASS\n'` for byte-exact
match (FAIL beats PASS):

```bash
source /tmp/foundry-mcp-aca-state.env
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-smoke-result
```

If at ANY point in Steps 0-5 a hard gate failed (auth missing, `azd up`
failed, MCP call returned non-200, JSON parse
failed, missing `serverInfo.name`, missing tools), you MUST already have
written `SMOKE_RESULT=FAIL <one-line reason>` to the same marker file
inline at the failure site.

DO NOT mention the marker token in your assistant prose reply. The
marker is the file contents on disk, not any text you type to the
console. Do NOT decorate the marker line with backticks anywhere.

---

## Step 7 — Best-effort teardown (Pattern 25 — AFTER the marker)

ONLY AFTER the PASS marker is written, attempt the same exact-owned cleanup
used on failure. CLI/HTTP calls and deletion polling are finite. Pattern 25
keeps a proven functional PASS separate from cleanup status, never from its
safety boundaries. Unknown/auth/network results are not absence.

```bash
source /tmp/foundry-mcp-aca-state.env || {
  echo "NOTE: teardown blocked: state unavailable; no deletion authorized"
  exit 0
}
if ! fixture_owned_cleanup; then
  echo "NOTE: teardown incomplete; inspect the exported ownership inventory and exact residuals"
fi
```

Never invoke group-scoped teardown against the shared CI resource group.
The canonical helper requires pre-write absence and exact run ownership,
deletes only the run's app, and verifies absence. Image and deployment artifacts
remain explicit residuals unless their immutable ownership is separately proven.
Shared identities, registry, environment, resource group and standing audience
are retained.

The marker stays `SMOKE_RESULT=PASS`. Cleanup failure does NOT downgrade
the smoke verdict. Do NOT re-write the marker file in this step under
any circumstance.

The helper deletes only the app whose pre-create absence, exact ID and run tag
match the inventory. It never deletes a resource group, CAE, registry, UAMI,
repository, image or deployment record. `azd` does not supply an immutable
per-image custody receipt here, so observed app image references and possible
build/deployment artifacts are exported as explicit residuals for the owner;
do not claim those artifacts were deleted or delete an entire shared repository.
The authoritative `/tmp/foundry-mcp-aca-ownership.json` is not reset on retries.
The raw inventory is owner-readable on the runner. A scope-redacted snapshot
with a scope hash is written to the existing smoke-evidence artifact path;
it is not an executable replacement for the private inventory.

---

## Summary of FAIL conditions (all must already have written
## `SMOKE_RESULT=FAIL <reason>` to the marker file inline)

- Missing CI env var (Pattern 11 — workflow bug)
- `azd auth login` non-zero (workflow OIDC bug)
- `azd up` failed (reconcile the exact owned inventory before another attempt —
  infra or skill bug)
- MCP `initialize` returned non-200 or missing `result.serverInfo.name`
- MCP `initialize` did not return a `Mcp-Session-Id` header (empty session ID)
- MCP `initialize` did not return a negotiated `protocolVersion` or
  `MCP-Protocol-Version` header replay failed on subsequent requests
- MCP `notifications/initialized` returned non-202 or non-empty body
  (expected HTTP 202 with no body per MCP 2025-06-18 spec)
- MCP `tools/list` returned non-200 or returned 0 tools
- MCP `tools/call` on `echo` returned non-200, `isError=true`, or
  payload did not match `"echoed: ci-probe"`
- JSON parse failed on any MCP response body
- FQDN could not be resolved post-deploy
- Missing API audience; anonymous request not 401, excluded caller not 403,
  or restored permitted caller not 200

Teardown failure is NOT a FAIL condition (Pattern 25 — soft-PASS).

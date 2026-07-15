# Customer goal — `foundry-mcp-aca` skill smoke

You are running an end-to-end smoke for the `foundry-mcp-aca` skill on the
GitHub Actions runner. The goal is to **prove the documented deployment +
wire-protocol contract works**: deploy a minimal FastMCP server to Azure
Container Apps via `azd up`, then perform an MCP-over-HTTP roundtrip
(`initialize` + `tools/list`) against the deployed FQDN and verify both
JSON-RPC calls return HTTP 200 with conformant bodies. The MCP HTTP
roundtrip is the value contract this skill exists to enable — everything
else is plumbing.

You are NOT testing a tutorial, README, or design doc. You are testing
whether a customer following the skill verbatim ends up with a working
MCP server reachable from Foundry hosted agents over the network. Pretend
you are that customer.

## Step -1 — acknowledge the skill contract

Your first Bash action must be:

```bash
echo "skills/foundry-mcp-aca/SKILL.md"
```

This lightweight line is the workflow's skill-usage audit evidence. Do not
open the whole file.

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
-1-7 directly in Bash tool calls, not to "run the smoke".

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

## Step 0 — verify CI auth contract (Pattern 11 + Pattern 17)

Run these checks FIRST. They must all succeed before you proceed to any
other step. If any of the env-var inventory checks fails, the workflow's
env contract is broken (AGENTS.md § 9.7 Pattern 11) — that is a workflow
bug, not a skill bug. Emit `SMOKE_RESULT=FAIL auth context missing:
<var-name>` and stop.

1. **Non-secret env-var inventory** (Pattern 11). Each line MUST print
   `…=set`:

   ```bash
   echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
   echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
   echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
   echo "ACR_LOGIN_SERVER=${ACR_LOGIN_SERVER:+set}"
   ```

   Then show the OPTIONAL auth-proof var (Pattern 17 — show-don't-assert;
   an empty value here is EXPECTED and MUST NOT fail the run):

   ```bash
   echo "MCP_AUTH_APP_CLIENT_ID=${MCP_AUTH_APP_CLIENT_ID:+set}"
   ```

   `MCP_AUTH_APP_CLIENT_ID` is OPTIONAL. When set, it is the client id of a
   standing pre-registered Entra app whose `api://<id>` audience this smoke
   uses to prove the 401→200 Easy Auth contract (Step 5b). When unset, the
   auth sub-test (Step 5b) is SKIPPED with a NOTE — that is expected and
   MUST NOT fail the run; the base smoke (Steps 1–5) already proves the
   server works.

2. **Show-don't-assert on `az` cache** (Pattern 17). The copilot CLI
   subprocess MAY or MAY NOT inherit `~/.azure/` from the runner. Print
   for the audit log; do NOT gate flow on this:

   ```bash
   az account show --output table || echo "(az cache not inherited — relying on azd auth login below)"
   ```

3. **Explicit `azd auth login`** (Pattern 6). This is the deterministic
   OIDC exchange that produces a fresh `azd` token from the inherited
   `AZURE_*` env vars. It is the auth gate — if it fails, the OIDC
   federation is broken (workflow bug):

   ```bash
   azd auth login \
     --federated-credential-provider github \
     --client-id "$AZURE_CLIENT_ID" \
     --tenant-id "$AZURE_TENANT_ID"
   ```

Do NOT invent additional credential checks (no `az ad sp show`, no
`az role assignment list`, no `az login --service-principal`). Do NOT
strict-equality-compare the subscription ID against env (Pattern 16/17 —
shell quoting flap risk). Existence checks via `${VAR:+set}` only, and
trust `azd auth login` as the gate.

---

## Step 1 — goal + scaffolding constraints

You will deploy a **tiny, self-contained FastMCP server** to Azure
Container Apps using `azd up`. The server exposes one `echo` tool and a
`/health` route. After `azd up` returns 0, you will resolve the
deployed FQDN and call the MCP HTTP endpoint with two JSON-RPC requests
(`initialize` + `tools/list`) to prove the wire protocol works.

### Naming

Generate a short UUID suffix for this run so parallel matrix legs and
retries don't collide on resource names (Pattern 3):

```bash
SUFFIX=$(uuidgen | tr 'A-Z' 'a-z' | cut -c1-8)
APP_NAME="ci-smoke-mcp-${SUFFIX}"
echo "APP_NAME=$APP_NAME"
```

Use `$APP_NAME` for the Container App name, the ACR repository tag, and
the `azd` environment name throughout.

### Scaffolding location

The Copilot CLI's shell-tool gate rejects `cd` outside `$GITHUB_WORKSPACE`
even with `--allow-all-tools`. Scaffold everything under
`${GITHUB_WORKSPACE}/.scratch/<APP_NAME>/`:

```bash
PROJECT_DIR="${GITHUB_WORKSPACE}/.scratch/${APP_NAME}"
mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/infra"
cd "$PROJECT_DIR"
```

`.scratch/` is gitignored — no risk of polluting the repo. You will NOT
commit any of the scaffolded files.

### Pattern 25 framing — read this BEFORE you start

This fixture follows the **Pattern 25 marker-first / cleanup-second**
shape (AGENTS.md § 9.7 Pattern 25). The hard gates of this smoke are:

1. **`azd up` returns 0** (Bicep deploy + ACR remote build + revision
   reaches Running state)
2. **MCP HTTP roundtrip succeeds** (`initialize` returns 200 with
   `result.serverInfo.name`; `tools/list` returns 200 with at least one
   tool in `result.tools[]`)

Once BOTH hard gates pass, you write the PASS marker file **IMMEDIATELY
via the Bash tool** (see Step 5 below). Cleanup is hygiene — it happens
AFTER the marker is written. Teardown failure (timeout, OIDC TTL expiry,
preview-CLI flag drift) does NOT downgrade the smoke verdict. The
`rg-awesome-gbb-ci` janitor sweeps `ci-smoke-mcp-*` resources older than
7 days.

Do NOT chain marker emission after cleanup. The smoke is the contract;
cleanup is best-effort.

---

## Step 2 — write the FastMCP server (`src/server.py`)

Write this exact server body to `${PROJECT_DIR}/src/server.py`. The
canonical `references/python/server.py` in the skill does NOT register
a `/health` route, but the canonical `references/bicep/mcp-aca.bicep`
configures both liveness AND startup probes against `/health:8080` —
which means a server without that route crash-loops on startup. The
explicit `mcp.custom_route("/health", …)` decorator below is the
documented FastMCP 2.x workaround (see the foundry-mcp-aca audit trail's
HIT-1 entry):

```python
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
```

Then write `${PROJECT_DIR}/src/requirements.txt`. **Pin `fastmcp` per
the SKILL.md mandate** — SKILL.md and the pin file's KI-001 both require
FastMCP `<3.0.0` (the 3.x release rewrote the streamable-HTTP mount path
and tool registration). The pin README table specifies `2.14.7`:

```
fastmcp~=2.14.7
```

Then write `${PROJECT_DIR}/src/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8080
CMD ["python", "server.py"]
```

---

## Step 3 — write the Bicep (`infra/main.bicep`)

Write `${PROJECT_DIR}/infra/main.bicep` that references the
pre-provisioned CAE and ACR via `existing`, deploys a single Container
App, and outputs the FQDN. Do NOT create a new CAE, ACR, or UAMI — they
are pre-provisioned and pre-RBAC'd:

```bicep
@description('Deployment region — must match the CAE.')
param location string = 'swedencentral'

@description('Container App name (also used as ACR repo tag).')
param appName string

@description('Full container image reference (ACR login server + repo + tag).')
param image string

@description('Resource ID of the user-assigned managed identity used for ACR pull.')
param uamiResourceId string

@description('Name of the pre-provisioned Container Apps Environment.')
param caeName string = 'cae-awesome-gbb-ci'

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: caeName
}

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  tags: {
    'azd-service-name': 'mcp'
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
          server: split(image, '/')[0]
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
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
            {
              type: 'Startup'
              httpGet: { path: '/health', port: 8080 }
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

output fqdn string = app.properties.configuration.ingress.fqdn
output appName string = app.name
```

Then write `${PROJECT_DIR}/azure.yaml` so `azd` knows how to build + push
the container image and bind it to the Bicep service:

```yaml
name: ci-smoke-mcp
metadata:
  template: ci-smoke-mcp@0.0.1
services:
  mcp:
    project: ./src
    language: python
    host: containerapp
    docker:
      path: Dockerfile
      context: .
```

---

## Step 4 — pre-build image, then `azd provision` (HARD GATE)

The MCP server listens on port 8080 and the Bicep `targetPort` is pinned
to 8080 (see SKILL.md L489-494 — the ACA helloworld placeholder serves
port 80, which would trap the MCP revision in `InProgress` forever).
SKILL.md's `image` Bicep param is required and **undefaulted on purpose**
— there is no safe placeholder for an MCP-on-ACA deploy. So build the
real image FIRST via `az acr build` (ACR remote build — no docker
engine needed on the runner), then run `azd provision` (NOT `azd up`)
to deploy the Bicep referencing the real image.

```bash
# 1) Build the MCP container image via ACR remote build. The runner
#    needs no docker daemon — ACR's build agent compiles + pushes in
#    one round trip. Takes ~3-5 min cold.
IMAGE_REF="${ACR_LOGIN_SERVER}/${APP_NAME}:${SUFFIX}"
echo "Building image: $IMAGE_REF"
az acr build \
  --registry "$ACR_LOGIN_SERVER" \
  --image "${APP_NAME}:${SUFFIX}" \
  --file src/Dockerfile \
  src/
echo "Image built: $IMAGE_REF"
```

Initialize the `azd` env and set the Bicep params. `azd` auto-maps
`UPPER_SNAKE_CASE` env-var keys to `camelCase` Bicep params (so
`APP_NAME` → `appName`, `IMAGE` → `image`, `UAMI_RESOURCE_ID` →
`uamiResourceId`). The Container App lands in `rg-awesome-gbb-ci`
(pre-existing):

```bash
azd env new "$APP_NAME" --location swedencentral --subscription "$AZURE_SUBSCRIPTION_ID"
azd env set AZURE_RESOURCE_GROUP rg-awesome-gbb-ci
azd env set APP_NAME "$APP_NAME"
azd env set IMAGE "$IMAGE_REF"
azd env set UAMI_RESOURCE_ID "/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.ManagedIdentity/userAssignedIdentities/uami-awesome-gbb-ci"
```

Then run `azd provision` (NOT `azd up`). The image is already built and
in ACR — we don't need the `azd deploy` swap step, just the Bicep
deploy referencing `$IMAGE_REF`. ACA's ARM resolver has a documented
cross-resource index-rebuild race (`ManagedEnvironmentNotFound`,
AGENTS.md § 9.7 Pattern 18) — wrap with a bounded retry loop:

```bash
attempts=0
max_attempts=6
until azd provision --no-prompt; do
  attempts=$((attempts + 1))
  if [ $attempts -ge $max_attempts ]; then
    echo "azd provision failed after $max_attempts attempts"
    printf 'SMOKE_RESULT=FAIL azd provision failed after retry exhaustion\n' > /tmp/foundry-mcp-aca-smoke-result
    # Best-effort cleanup of any partial deploy:
    azd down --purge --force --no-prompt || true
    exit 1
  fi
  echo "azd provision attempt $attempts failed, sleeping 5s before retry (Pattern 18 — ARM cross-resource race)"
  sleep 5
done
```

Total budget for this step: ~8-12 min under typical conditions
(ACR build ~3-5 min + Bicep provision ~5-7 min until revision reaches
Running state). This is materially faster than `azd up` because we
skip the `azd deploy` revision-swap loop entirely.

---

## Step 5 — MCP HTTP roundtrip (HARD GATE)

Resolve the FQDN of the deployed Container App. Prefer the `azd env get-values`
output, but fall back to `az containerapp show`:

```bash
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
```

Call `initialize`. The MCP streamable-HTTP spec requires a dual
`Accept: application/json, text/event-stream` header so the server can
choose single-response vs streaming. The endpoint is `/mcp/` (trailing
slash — FastMCP 2.x mount path; see SKILL.md L580-593 + L603 critical
gotchas). Use `curl -L` so any 307 redirect to/from `/mcp` is followed:

```bash
INIT_RESPONSE=$(curl -sS -L -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp/" \
  -H "Content-Type: application/json" \
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
```

Then call `tools/list`:

```bash
TOOLS_RESPONSE=$(curl -sS -L -w "\n__HTTP_CODE__:%{http_code}" \
  -X POST "https://${FQDN}/mcp/" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
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

TOOL_COUNT=$(echo "$TOOLS_JSON" | jq -r '.result.tools | length // 0')
if [ "$TOOL_COUNT" -lt 1 ]; then
  printf 'SMOKE_RESULT=FAIL tools/list returned 0 tools\n' > /tmp/foundry-mcp-aca-smoke-result
  exit 1
fi
echo "tools/list returned $TOOL_COUNT tool(s)"
```

If both calls return 200 with conformant bodies, the hard gates have
passed. Proceed IMMEDIATELY to Step 6.

DO NOT use `azd ai mcp` preview-CLI subcommands or any other preview
CLI that hides the HTTP wire protocol (Pattern 16). The HTTP endpoint
is the GA surface.

---

## Step 5b — Easy Auth 401→200 proof (HARD GATE only when `MCP_AUTH_APP_CLIENT_ID` is set)

Layer 1 of the skill's security model is ACA built-in auth: the platform
must return **401** to an unauthenticated caller and let a caller presenting
a valid Entra bearer token for `api://$MCP_AUTH_APP_CLIENT_ID` through (not
401). Steps 1–5 already proved the server works over the wire; this step
proves the documented `## Securing your MCP server` § "Layer 1 — Identity
perimeter" contract on the live app.

**Gate:** if `MCP_AUTH_APP_CLIENT_ID` is empty, SKIP this entire step — echo
exactly `NOTE: MCP_AUTH_APP_CLIENT_ID unset — skipping Easy Auth 401/200 proof`
and proceed to Step 6. Do NOT write a FAIL marker for an unset client id.

```bash
if [ -z "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
  echo "NOTE: MCP_AUTH_APP_CLIENT_ID unset — skipping Easy Auth 401/200 proof"
fi
```

When `MCP_AUTH_APP_CLIENT_ID` IS set, run all of the following. Any failure
here is a HARD FAIL — write `SMOKE_RESULT=FAIL <reason>` to
`/tmp/foundry-mcp-aca-smoke-result` inline and stop.

1. **Enable built-in auth on the app you deployed** (`$APP_NAME` from Step 1,
   resource group `rg-awesome-gbb-ci`, tenant `$AZURE_TENANT_ID`):

   ```bash
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     # `--allowed-token-audiences` is a SINGLE-value flag (argparse nargs=None):
     # two space-separated values fail at PARSE time ("unrecognized arguments").
     # The only CLI-native way to list BOTH api://<id> (delegated / v1 aud) AND
     # the bare <id> (app-only v2 aud) is a full authConfig PUT that mirrors
     # references/bicep/mcp-aca-auth.bicep. That PUT also encodes Return401, so
     # it REPLACES the separate `az containerapp auth update` call. Build the
     # body with jq (no heredoc → robust to copy indentation), then az rest PUT.
     SUB=$(az account show --query id -o tsv)
     jq -n --arg cid "$MCP_AUTH_APP_CLIENT_ID" \
       --arg iss "https://login.microsoftonline.com/$AZURE_TENANT_ID/v2.0" \
       '{properties:{platform:{enabled:true},globalValidation:{unauthenticatedClientAction:"Return401"},identityProviders:{azureActiveDirectory:{enabled:true,registration:{clientId:$cid,openIdIssuer:$iss},validation:{allowedAudiences:["api://\($cid)",$cid]}}}}}' \
       > /tmp/mcp-authconfig.json
     az rest --method put \
       --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/rg-awesome-gbb-ci/providers/Microsoft.App/containerApps/$APP_NAME/authConfigs/current?api-version=2025-01-01" \
       --body @/tmp/mcp-authconfig.json
   fi
   ```

2. **Wait for the auth config to take effect and assert 401** (Easy Auth is a
   control-plane change; poll up to 6× with a 10 s back-off, per the
   ACA-control-plane race guidance in AGENTS.md § 9.7 Pattern 9):

   ```bash
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     CODE=""
     for i in $(seq 1 6); do
       CODE=$(curl -s -o /dev/null -w '%{http_code}' \
         -H 'Accept: application/json, text/event-stream' \
         "https://${FQDN}/mcp/")
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

3. **Acquire a token and assert the authed call is NOT 401.** The CI managed
   identity requests a token for the app's audience, then repeats the MCP
   `initialize` round-trip WITH the bearer header:

   ```bash
   if [ -n "${MCP_AUTH_APP_CLIENT_ID:-}" ]; then
     TOKEN=$(az account get-access-token \
       --resource "api://$MCP_AUTH_APP_CLIENT_ID" \
       --query accessToken -o tsv)
     AUTHED_CODE=$(curl -s -o /tmp/mcp-authed.json -w '%{http_code}' \
       -X POST "https://${FQDN}/mcp/" \
       -H 'Content-Type: application/json' \
       -H 'Accept: application/json, text/event-stream' \
       -H "Authorization: Bearer $TOKEN" \
       -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ci","version":"1"}}}')
     echo "authed status: $AUTHED_CODE"
     case "$AUTHED_CODE" in
       2*) echo "auth proof: 401 unauth / authed $AUTHED_CODE OK" ;;
       *)
         printf 'SMOKE_RESULT=FAIL auth proof: valid token expected 2xx, got %s (401=aud/authz mismatch for api://%s or bare %s; 403=caller not in allowedApplications)\n' \
           "$AUTHED_CODE" "$MCP_AUTH_APP_CLIENT_ID" "$MCP_AUTH_APP_CLIENT_ID" \
           > /tmp/foundry-mcp-aca-smoke-result
         exit 1 ;;
     esac
   fi
   ```

When both assertions hold (or the step was SKIPPED), proceed to Step 6.

---

## Step 6 — Write the PASS marker IMMEDIATELY (Pattern 12)

The MOMENT the Step 4 provision gate, the Step 5 MCP round-trip gate, AND
the Step 5b auth gate (or its documented SKIP when `MCP_AUTH_APP_CLIENT_ID`
is unset) have all succeeded, write the deterministic PASS
marker file via the Bash tool. The file's literal byte content is what
CI grades — NOT your assistant text reply. The workflow evaluator
(`.github/workflows/skill-test.yml`) reads `/tmp/foundry-mcp-aca-smoke-result`
and `cmp -s` against `printf 'SMOKE_RESULT=PASS\n'` for byte-exact
match (FAIL beats PASS):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-smoke-result
```

If at ANY point in Steps 0-5 a hard gate failed (auth missing, `azd up`
failed after retry exhaustion, MCP call returned non-200, JSON parse
failed, missing `serverInfo.name`, missing tools), you MUST already have
written `SMOKE_RESULT=FAIL <one-line reason>` to the same marker file
inline at the failure site.

DO NOT mention the marker token in your assistant prose reply. The
marker is the file contents on disk, not any text you type to the
console. Do NOT decorate the marker line with backticks anywhere.

---

## Step 7 — Best-effort teardown (Pattern 25 — AFTER the marker)

ONLY AFTER the PASS marker is written, attempt cleanup. The hard cap
is **5 minutes** (Pattern 25). If teardown stalls past that, emit a
single NOTE line to stdout and return — the smoke verdict stays PASS:

```bash
cd "$PROJECT_DIR"
timeout 300 azd down --purge --force --no-prompt 2>&1 | tail -20 || {
  echo "NOTE: teardown stalled or errored within 5-minute Pattern-25 budget — leaving orphans for the rg-awesome-gbb-ci janitor (will sweep ci-smoke-mcp-* older than 7 days)"
}
```

The marker stays `SMOKE_RESULT=PASS`. Cleanup failure does NOT downgrade
the smoke verdict. Do NOT re-write the marker file in this step under
any circumstance.

---

## Summary of FAIL conditions (all must already have written
## `SMOKE_RESULT=FAIL <reason>` to the marker file inline)

- Missing CI env var (Pattern 11 — workflow bug)
- `azd auth login` non-zero (workflow OIDC bug)
- `azd up` failed after 6 retry attempts (Pattern 18 budget exhausted —
  infra or skill bug)
- MCP `initialize` returned non-200 or missing `result.serverInfo.name`
- MCP `tools/list` returned non-200 or returned 0 tools
- JSON parse failed on either MCP response body
- FQDN could not be resolved post-deploy
- Step 5b auth proof: unauth call not 401, or valid-token call still 401
  (only when `MCP_AUTH_APP_CLIENT_ID` is set; SKIPPED and never a FAIL when
  unset)

Teardown failure is NOT a FAIL condition (Pattern 25 — soft-PASS).

---
name: azd-patterns
description: >
  Tips and patterns for Azure Developer CLI (azd) workflows, ACA job deployment,
  and infrastructure scripting conventions.
  USE FOR: azd hooks, postdeploy, postprovision, ACA job deployment, container app
  job image update, publish_aca, deploy_job, azure.yaml hooks, cross-platform
  deployment scripts, uv run, azd env, azd conventions, infra scripts.
  DO NOT USE FOR: az login, tenant switching, subscription isolation (use
  azure-tenant-isolation), Foundry agents (use microsoft-foundry).
metadata:
  version: "1.0.0"
---

# AZD Tips & Patterns

Conventions and best practices for `azd` workflows, hooks, and ACA job deployments gathered from real repos.

---

## ACA Job Deployment

`azd` does not natively deploy Container Apps **Jobs** — only Container Apps. Jobs need a separate deployment step.

### Recommended: Python + `postdeploy` hook (cross-platform)

Used in newer repos. The pattern:

1. **`azure.yaml`** — wire a `postdeploy` hook that runs after `azd deploy`:

   ```yaml
   hooks:
     postdeploy:
       shell: pwsh
       run: 'cd infra/scripts && uv sync --frozen && uv run deploy_job.py'
       interactive: false
       continueOnError: false
   ```

2. **`infra/scripts/deploy_job.py`** — update the job image via Azure SDK:

   ```python
   import asyncio, os, sys, logging
   from utils import load_azd_env
   from azure.identity.aio import AzureCliCredential
   from azure.mgmt.appcontainers.aio import ContainerAppsAPIClient

   async def main():
       load_azd_env()
       image_name = os.getenv("SERVICE_AGENTS_IMAGE_NAME")
       job_name = os.getenv("JOB_NAME")
       resource_group = os.getenv("RESOURCE_GROUP")
       subscription_id = os.getenv("SUBSCRIPTION_ID")
       tenant_id = os.getenv("AZURE_TENANT_ID")

       async with AzureCliCredential(tenant_id=tenant_id) as credential:
           async with ContainerAppsAPIClient(credential, subscription_id) as client:
               job = await client.jobs.get(resource_group, job_name)
               job.template.containers[0].image = image_name
               # Remove stale sidecars — they cause "Failed" status if they exit non-zero
               job.template.containers = [job.template.containers[0]]
               poller = await client.jobs.begin_create_or_update(resource_group, job_name, job)
               await poller.result()

   if __name__ == "__main__":
       try:
           asyncio.run(main())
       except Exception as e:
           logging.critical("Error deploying job: %s", e)
           sys.exit(1)
   ```

3. **`infra/scripts/utils.py`** — load azd environment variables:

   ```python
   import json, os, subprocess
   from pathlib import Path
   from dotenv import load_dotenv

   def _ensure_azd_config_dir():
       """Walk up from script dir to find repo-root .azure directory.
       Needed when azd hooks run from a temp directory."""
       if os.environ.get("AZD_CONFIG_DIR"):
           return
       search = Path(__file__).resolve().parent
       for _ in range(10):
           candidate = search / ".azure"
           if candidate.is_dir() and any(
               (candidate / d / ".env").exists()
               for d in os.listdir(candidate)
               if (candidate / d).is_dir()
           ):
               os.environ["AZD_CONFIG_DIR"] = str(candidate)
               return
           if search.parent == search:
               break
           search = search.parent

   def load_azd_env():
       """Load the default azd environment's .env file."""
       _ensure_azd_config_dir()
       result = subprocess.run("azd env list -o json", shell=True, capture_output=True, text=True)
       if result.returncode != 0:
           raise Exception("Error loading azd env")
       env_json = json.loads(result.stdout)
       for entry in env_json:
           if entry["IsDefault"]:
               load_dotenv(entry["DotEnvPath"], override=True)
               return
       raise Exception("No default azd env file found")
   ```

4. **`infra/scripts/pyproject.toml`** — managed by `uv`:

   ```toml
   [project]
   name = "infra-scripts"
   requires-python = ">=3.11"
   dependencies = [
       "azure-identity",
       "azure-mgmt-appcontainers",
       "python-dotenv",
   ]
   ```

### Benefits over the old PowerShell approach

| Old (`publish_aca.ps1`) | New (`deploy_job.py`) |
|---|---|
| Shells out to `az acr build` + `az containerapp job update` | Uses Azure SDK directly |
| Windows-only (or requires PS Core) | Cross-platform (Python) |
| Depends on `az` CLI subscription state | Uses `AzureCliCredential` (respects `AZURE_CONFIG_DIR`) |
| No sidecar cleanup | Removes stale sidecars that cause false "Failed" status |
| Manual image tagging | Reads image name from azd env vars (`SERVICE_*_IMAGE_NAME`) |

### Legacy: PowerShell script (`publish_aca.ps1`)

Older repos (e.g. `acme-demo-form`) use a `postprovision` hook with a PowerShell script:

```yaml
# azure.yaml
hooks:
  postprovision:
    shell: pwsh
    run: |
      $RG = azd env get-value AZURE_RESOURCE_GROUP
      $APP_NAME = azd env get-value AZURE_CAJOB_NAME
      .\infra\scripts\publish_aca.ps1 -RG $RG -APP_SOURCE_FOLDER .\src\ca-job -APP_NAME $APP_NAME -TYPE job
    interactive: true
    continueOnError: false
```

The script does `az acr build` + `az containerapp job update`. This works but is not cross-platform and depends on `az` CLI subscription state.

> **⚠️ Gotcha:** `postprovision` runs only on `azd provision`/`azd up`, NOT on `azd deploy`. If the job needs updating on every deploy, use `postdeploy` instead.

---

## ACA Job: silent-failure debug playbook

**Symptom we keep hitting.** ACA Job execution flips to `Failed`
within 60s of the deploy completing, but **zero console + system
logs reach Log Analytics Workspace** even though sibling ACA apps
(MCP server, agent) in the same env route logs cleanly. `az
containerapp job logs show` hangs indefinitely. This has bitten deadline-watcher cron jobs after in-process
refactors and is often the biggest end-of-session blocker.

The diagnostic ladder below goes **cheap → expensive**. Stop at the
first rung that surfaces actionable signal.

### Rung 1 — Verify the basics aren't lying

```powershell
$RG  = 'rg-<your-process>-poc'
$JOB = 'aca-job-deadline-watcher'

# Confirm the job exists and what image it's actually running
az containerapp job show --resource-group $RG --name $JOB `
  --query "{state:properties.runningState, image:properties.template.containers[0].image, env:properties.environmentId}" -o table

# Confirm last execution(s)
az containerapp job execution list --resource-group $RG --name $JOB `
  --query "[].{name:name, status:properties.status, start:properties.startTime, end:properties.endTime}" `
  --output table | Select-Object -First 10
```

Common findings:
- Image is `mcr.microsoft.com/azuredocs/containerapps-helloworld` — `azd
  provision` ran but `azd deploy` / publish_aca didn't (placeholder
  leak — `threadlight-safe-check` Step 3.5 (image-probe) catches this;
  check separately).
- Image hash matches latest ACR push but jobs still Failed → real
  runtime crash, advance to Rung 2.

### Rung 2 — Probe LAW for ANY signal at all (including system events)

```powershell
$WS = az monitor log-analytics workspace list --resource-group $RG `
        --query "[0].customerId" -o tsv
$JOB = 'aca-job-deadline-watcher'

# Console logs — what stdout/stderr emitted (this is the "no logs" thing if empty)
az monitor log-analytics query --workspace $WS --analytics-query @"
ContainerAppConsoleLogs_CL
| where ContainerJobName_s == '$JOB'
| order by TimeGenerated desc
| project TimeGenerated, RevisionName_s, Log_s
| take 50
"@ -o table

# System logs — ACA control plane events (start/stop/pull/probe failures)
az monitor log-analytics query --workspace $WS --analytics-query @"
ContainerAppSystemLogs_CL
| where ContainerAppName_s == '$JOB'
| order by TimeGenerated desc
| project TimeGenerated, Type_s, Reason_s, Log_s
| take 50
"@ -o table
```

What each empty/non-empty combo means:

| ConsoleLogs | SystemLogs | Likely cause |
|---|---|---|
| Empty | Empty | LAW routing not wired to this job (env-level diag setting missing or job created before diag setting), OR ACA Job log-pipeline lag (try again 2-3 min after execution) |
| Empty | Non-empty | Image pulls / starts but exits before any `print()` / `logging.info()` reaches LAW. Usually an **import-time crash** — the process exits before `logging.basicConfig()` fires. Move to Rung 3. |
| Non-empty | Non-empty | You have signal — read it. |

### Rung 3 — Force first-line logging in the entrypoint

When the ConsoleLogs pipe is empty but SystemLogs show the container
started + exited, the crash is import-side. Tactic: emit a synchronous
write to stderr **before any other import** so even an
`ImportError` produces a visible breadcrumb.

```python
# main.py — top of file, BEFORE any project imports
import sys
sys.stderr.write("BOOT: entrypoint reached\n"); sys.stderr.flush()
try:
    import azure.identity     # the usual suspects first
    sys.stderr.write("BOOT: azure.identity OK\n"); sys.stderr.flush()
    import azure.cosmos
    sys.stderr.write("BOOT: azure.cosmos OK\n"); sys.stderr.flush()
    # ... your imports ...
except Exception as e:
    sys.stderr.write(f"BOOT: import failed: {type(e).__name__}: {e}\n")
    sys.stderr.flush()
    raise
```

Push, redeploy, kick off a manual execution (`az containerapp job
start --resource-group $RG --name $JOB`), wait ~90s, re-run the
ConsoleLogs query at Rung 2. The breadcrumbs reveal which import
exploded.

### Rung 4 — Activity log probe (orthogonal channel — bypasses LAW entirely)

```powershell
$RG = 'rg-<your-process>-poc'
$JOB = 'aca-job-deadline-watcher'
$JOB_ID = az containerapp job show --resource-group $RG --name $JOB --query id -o tsv

# Last 4 hours of activity log entries for the job resource
az monitor activity-log list `
  --resource-id $JOB_ID `
  --start-time (Get-Date).AddHours(-4).ToString('o') `
  --query "[].{time:eventTimestamp, level:level, op:operationName.value, status:status.value, msg:properties.statusMessage}" `
  -o table | Select-Object -First 20
```

Catches: image pull failures (ACR auth / RBAC missing on the env's
UAMI), execution-create failures (quota), control-plane denials.

### Rung 5 — Portal Container Apps blade (job execution detail)

The most painful diagnostic to automate, but it has signal that **is
NOT exposed via CLI**. Path:

1. Azure Portal → Resource group → the ACA Job resource
2. Left nav → **Execution history**
3. Click the failed execution name
4. The right pane shows **per-replica logs** including init-container
   output and any pre-`logging.basicConfig` stderr — the same data
   that LAW would show *if* the routing were healthy.

Use this rung when Rungs 1–4 give you nothing actionable. Do not
skip the earlier rungs — they're 1-line probes; the portal click is
several minutes of navigation.

### Rung 6 — Detectors API (preview — sometimes 404s)

```powershell
$RG = 'rg-<your-process>-poc'
$JOB = 'aca-job-deadline-watcher'
$exec = (az containerapp job execution list --resource-group $RG --name $JOB `
          --query "[0].name" -o tsv)
az rest --method get `
  --uri "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RG/providers/Microsoft.App/jobs/$JOB/executions/$exec/detectors?api-version=2024-03-01"
```

Returns `404` on many regions / SKU combos as of May 2026 — try
`api-version=2024-08-02-preview` or `2025-01-01` if 404. When it
works, surfaces structured root-cause diagnostics (e.g.
"OutOfMemoryException", "ImagePullBackOff", "MaxReplicasExceeded").

### Common root causes — the "if I ran out of time, what's it most likely?" table

| Symptom in logs | Likely cause | Fix |
|---|---|---|
| ConsoleLogs empty + SystemLogs `Type=Pull`, `Reason=ImagePullError` | ACR pull RBAC missing on env's UAMI, or image tag doesn't exist in ACR | Verify `az acr repository show-tags`; grant `AcrPull` to env UAMI |
| ConsoleLogs empty + SystemLogs `Reason=ContainerStartedExited` ExitCode 1 within 5s | Import-time crash before logger setup | Apply Rung 3 first-line stderr breadcrumbs |
| ConsoleLogs empty + activity log `Forbidden` | Cosmos / Search data-plane RBAC not granted to job's UAMI (note: a Foundry hosted-agent's runtime UAMI is `ServiceIdentity` and **cannot** receive Cosmos data-plane RBAC — see `foundry-hosted-agents` § "Agent Identities · ServiceIdentity Cosmos limitation") | Use a separate User-Assigned MI for the job; grant role `00000000-0000-0000-0000-000000000002` (Cosmos DB Built-in Data Contributor) at the account scope |
| ConsoleLogs empty + everything looks healthy + execution Failed | LAW diagnostic settings missing for the ACA env (apps emit logs because they were created with diag wiring; jobs created later inherit the env but not always the diag setting on the job resource itself) | Add diagnostic setting on the job resource: `az monitor diagnostic-settings create --resource $JOB_ID --name to-law --workspace $WS --logs '[{"category":"ContainerAppConsoleLogs","enabled":true},{"category":"ContainerAppSystemLogs","enabled":true}]'` |
| Image confirmed real + console fine + early Failed | Cron `args:` running unintended path (e.g. `python -m main` when entrypoint is `python main.py`) | `az containerapp job show ... --query template.containers[0].command` |

### Anti-pattern (DO NOT do)

- ❌ Don't add `time.sleep(120)` "just to keep the container alive" — it
  hides the crash. Fix the import.
- ❌ Don't switch to a long-lived `containerapp app` to "get logs" — ACA
  Jobs are the right primitive for cron; the routing IS fixable.
- ❌ Don't blindly bump `replicaTimeout` — if the entrypoint crashes
  in 5s, more time won't help.

> Captured from recent cron-debug retrospectives. Future cron debugs
> should rerun this ladder top-to-bottom.

---

## Hooks: `postprovision` vs `postdeploy`

| Hook | Runs after | Use for |
|------|-----------|---------|
| `postprovision` | `azd provision` or `azd up` | One-time setup: storage seeding, RBAC, federated identity |
| `postdeploy` | `azd deploy` or `azd up` | Recurring: ACA job image update, config sync |

**Tip:** `azd up` runs both hooks in sequence (provision → deploy). `azd deploy` only runs `postdeploy`.

---

## Bicep: ACA Job Pattern

Jobs are provisioned with an empty placeholder image and updated by the hook script after deploy:

```bicep
// Resolve existing image if the job already exists, otherwise use placeholder
module fetchLatestImage './fetch-container-image.bicep' = {
  name: 'job-image'
  params: {
    exists: jobExists
    name: '${prefix}-job-${uniqueId}'
  }
}

resource processingJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-job-${uniqueId}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uamiResourceId}': {} }
  }
  properties: {
    environmentId: containerAppEnv.id
    configuration: {
      replicaTimeout: 300
      triggerType: 'Schedule'  // or 'Manual'
      scheduleTriggerConfig: { cronExpression: '0 6 * * *' }
      registries: [{
        server: '${acr}.azurecr.io'
        identity: uamiResourceId
      }]
    }
    template: {
      containers: [{
        name: 'job'
        image: jobExists ? fetchLatestImage.outputs.containers[0].image : emptyContainerImage
        resources: { cpu: 1, memory: '2Gi' }
        env: [ /* ... */ ]
      }]
    }
  }
}
```

The `fetch-container-image.bicep` module is used to read the current image from an existing resource so that `azd provision` doesn't reset it to the placeholder.

> **API version note:** `Microsoft.App/jobs@2024-03-01` is the current GA API version (verified May 2026). Older preview versions (`2023-11-02-preview`) still work but lack newer fields like `replicaRetryLimit`.

---

## Shared UAMI Pattern

All deployed resources (ACA services, ACA jobs, Azure Functions) should share
**one User-Assigned Managed Identity** rather than using system-assigned MIs.

### Why

- **One identity, one set of RBAC assignments** — no need to grant roles to N different principals
- **Predictable** — `AZURE_CLIENT_ID` is the same across all resources
- **Debuggable** — one principal to check in RBAC, one token to trace
- **Portable** — UAMI survives resource recreation (system MI doesn't)

### Bicep

```bicep
// infra/identity/uami.bicep
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id'
  location: location
}

output id string = identity.id
output clientId string = identity.properties.clientId
output principalId string = identity.properties.principalId
```

### Wire to all ACAs

```bicep
// Every ACA gets the same UAMI
identity: {
  type: 'UserAssigned'
  userAssignedIdentities: { '${uami.outputs.id}': {} }
}

// Every ACA gets AZURE_CLIENT_ID pointing to the shared UAMI
env: [
  { name: 'AZURE_CLIENT_ID', value: uami.outputs.clientId }
  // ... other env vars
]
```

### RBAC — assign once, applies to all resources

```bicep
// Role definition GUIDs are stable across tenants — the one below is
// `Azure AI User` (`53ca6127-db72-4b80-b1b0-d745d6d5456d`). Substitute
// other built-in role GUIDs as needed (e.g. `Search Index Data Reader`
// = `1407120a-92aa-4202-b7e9-c0e197c71c8f`). NEVER ship `'...'` as a
// placeholder — Bicep will compile but the deploy will fail with
// `RoleDefinitionDoesNotExist` at apply-time, after every other
// resource has provisioned.
resource aiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().subscriptionId, uami.outputs.principalId, 'ai-user')
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '53ca6127-db72-4b80-b1b0-d745d6d5456d'   // Azure AI User
    )
    principalId: uami.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Exception: Hosted agent containers

Hosted agent containers get a **platform-managed dedicated identity** (instance + blueprint)
at deploy time — you don't assign a UAMI to them. The shared UAMI is for everything
else: bot ACA, MCP ACA, jobs, hooks, etc.

---

## `uv` for Hook Scripts

Use [`uv`](https://docs.astral.sh/uv/) for Python dependency management in hook scripts:

```yaml
hooks:
  postdeploy:
    shell: pwsh
    run: 'cd infra/scripts && uv sync --frozen && uv run deploy_job.py'
```

- `uv sync --frozen` — install deps from lockfile (deterministic, fast)
- `uv run deploy_job.py` — run script in the managed venv
- No need to manually create/activate venvs
- Cross-platform (Windows/Linux/Mac)

---

## Composable Bicep Module Library

`threadlight-deploy` Phase 6 (Module Composer) reads SPEC § 11c and includes
exactly the right Bicep modules. This section catalogs the modules and what
SPEC inputs select them.

### Module catalog

Every module lives at `infra/modules/<name>.bicep` in the generated repo.
Ship them as **a single self-contained Bicep file per module** (no nested
modules) so they can be vendored independently.

| Module | File | Selector (SPEC § 11c kebab-case key) | Outputs (always) | When to include |
|--------|------|---------------------------------------|------------------|-----------------|
| **cosmos-db** | `infra/modules/cosmos-db.bicep` | `cosmos-db: yes` (params: `sku: 'serverless' \| 'autoscale'`, `pilotPosture: bool = true`, `ipAllowlist: array = []`) | `endpoint`, `accountName`, `databaseName`, `containerNames[]` | Any process that needs case state, audit, or agent memory (default for case-based / regulated processes). **`pilotPosture=true` (default) sets `publicNetworkAccess: Enabled` + `networkAclBypass: AzureServices` — see Cosmos firewall callout below** |
| **ai-search** | `infra/modules/ai-search.bicep` | `ai-search: yes` (params: `sku: 'basic' \| 'standard'`) | `endpoint`, `serviceName`, `indexNames[]`, `apiVersion` | Knowledge retrieval (paired with `foundry-iq-index` below) |
| **doc-intel** | `infra/modules/doc-intel.bicep` | `doc-intel: yes` (params: `tier: 'S0'`) | `endpoint`, `accountName` | Structured-doc ingestion (KYC IDs, invoices, claims forms) |
| **azure-vision** | `infra/modules/azure-vision.bicep` | `azure-vision: yes` (params: `model: 'gpt-5.4-pro' \| 'gpt-5.4' \| 'gpt-5.4-mini'`) | `endpoint`, `deploymentName` | Image / damage-photo / blueprint analysis |
| **azure-speech** | `infra/modules/azure-speech.bicep` | `azure-speech: yes` (params: `tier: 'S0'`, `customSubdomain: ...`) | `endpoint`, `accountName`, `region` | STT for FNOL / call recordings, TTS for IVR responses. **Custom subdomain is IRREVERSIBLE** — surface a `--confirm-irreversible` flag |
| **event-grid** | `infra/modules/event-grid.bicep` | `event-grid: yes` (params: `topics: [...]`) | `topicEndpoints{}`, `topicResourceIds{}` | Event-driven triggers (Supplier Risk news, Order Fallout) |
| **service-bus** | `infra/modules/service-bus.bicep` | `service-bus: yes` (params: `tier: 'standard' \| 'premium'`, `queues: [...]`, `topics: [...]`) | `namespace`, `queueNames[]`, `topicNames[]` | Async work queues (PIM enrichment batch, Card Dispute case routing) |
| **storage-blob** | `infra/modules/storage-blob.bicep` | `storage-blob: yes` (params: `containers: [...]`) | `accountName`, `containerNames[]`, `endpoint` | Document/image/audio storage for vision / doc-intel / speech |
| **key-vault** | `infra/modules/key-vault.bicep` | `key-vault: yes` (params: `enabled: bool`) | `vaultName`, `vaultUri` | Required ONLY when external API keys must be secured (e.g., third-party data sources). NOT in always-include — threadlight pilots are keyless-by-mandate. |
| **app-insights** | `infra/modules/app-insights.bicep` | (always — non-optional) | `connectionString`, `instrumentationKey`, `appId` | Always — required for `foundry-evals` continuous loop |
| **aca-job** | `infra/modules/aca-job.bicep` | `aca-job: yes` (params: `[{ name, trigger: 'cron' \| 'manual', ... }]`) | `jobName`, `jobResourceId` per entry | Wired by `threadlight-event-triggers` for receivers |
| **aca-mcp** | `infra/modules/aca-mcp.bicep` | `aca-mcp: yes` (params: `[{ name, image, ... }]`) | `mcpEndpoints{}`, `mcpFqdns{}` | Wired by `foundry-mcp-aca` for each mocked or custom MCP server |
| **aca-bot** | `infra/modules/aca-bot.bicep` | `aca-bot: yes` (params: `manifest: ...`) | `botFqdn`, `botResourceId`, `botAppId` | Wired by `foundry-teams-bot` when SPEC § 8 includes Teams |
| **foundry-iq-index** | `infra/modules/foundry-iq-index.bicep` | `foundry-iq-index: yes` (params: `knowledgeBases: [...]`) | `indexNames[]`, `agentNames[]` | Provisions the AI Search index + Knowledge Agent. Implies `ai-search` and `storage-blob` |
| **uami** | `infra/modules/uami.bicep` | (always included) | `uamiResourceId`, `uamiPrincipalId`, `uamiClientId` | Always — single shared identity per app (see Shared UAMI Pattern above) |
| **acr** | `infra/modules/acr.bicep` | (always included for poly-repo agents) (params: `sku: 'Standard' \| 'Premium'`) | `acrEndpoint`, `acrName`, `acrResourceId` | Always — required for the agent container itself; reused for MCP / bot / job containers |
| **foundry-account** | `infra/modules/foundry-account.bicep` | (always included for the hosted agent) | `accountName`, `projectName`, `endpoint` | Always — hosts the agent itself |

### Selector grammar (SPEC § 11c)

The SPEC § 11c table is read as a **selector table** — kebab-case rows
mapping module name → `yes`/`no` + optional params. The composer iterates
rows where `selected: yes` and includes only those modules. The vocabulary
is the source of truth for both this catalog and `threadlight-deploy`
Phase 6.

```markdown
# specs/SPEC.md § 11c (excerpted, canonical kebab-case shape)

| Module             | Selected? | Purpose / params                                            |
| `cosmos-db`        | yes       | sku: serverless                                              |
| `ai-search`        | yes       | sku: basic                                                   |
| `foundry-iq-index` | yes       | knowledgeBases: [{ name: kyc-policies, sources: [...] }]    |
| `azure-vision`     | yes       | model: gpt-5.4-mini                                          |
| `aca-job`          | yes       | [{ name: sla-watcher, trigger: cron, schedule: "*/15 * * * *" }] |
| `aca-mcp`          | yes       | [{ name: customer-data-mcp, image: customer-mcp:latest }]   |
| `aca-bot`          | yes       | manifest: ...                                                |
| `key-vault`        | no        | (threadlight: keyless-by-mandate)                            |
```

Resulting `infra/main.bicep` includes (in canonical inclusion order):
`uami → acr → app-insights → cosmos-db → ai-search → foundry-iq-index → azure-vision → doc-intel → azure-speech → storage-blob → event-grid → service-bus → aca-mcp → aca-job → foundry-account → aca-bot`.

> **`key-vault` is NOT in the always-include set.** Threadlight pilots
> are keyless end-to-end. Include `key-vault` ONLY when SPEC § 11c
> explicitly selects `key-vault: yes` for an external integration that
> demands a literal API key.

### Cosmos firewall — pilot-grade defaults (the trap that costs ~45 min on every fresh PoC)

**Observed in recent pilots.** Azure's Cosmos default is
`publicNetworkAccess: Disabled` — every ACA→Cosmos write returns
`Forbidden` until manually patched, even with managed identity + correct
data-plane RBAC. `cosmos-db.bicep` MUST default to pilot-friendly
posture:

```bicep
@description('Pilot posture: enables public network + AzureServices bypass. Set false for prod-grade (private endpoint).')
param pilotPosture bool = true

@description('Explicit IP allowlist for ACA egress (pilots: leave empty initially, then re-deploy with the IP from the Cosmos Forbidden error). Required because AzureServices bypass does NOT cover ACA traffic — see foundry-mcp-aca.')
param ipAllowlist array = []

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  // ...
  properties: {
    publicNetworkAccess: pilotPosture ? 'Enabled' : 'Disabled'
    networkAclBypass:    pilotPosture ? 'AzureServices' : 'None'
    ipRules: [for ip in ipAllowlist: { ipAddressOrRange: ip }]
    disableLocalAuth: true
    // ...
  }
}
```

**Pilot-only — gotcha:** `AzureServices` bypass alone is NOT sufficient
for ACA → Cosmos traffic in `swedencentral` (and likely other regions).
The full operator runbook + post-deploy IP discovery commands live in
`foundry-mcp-aca` SKILL.md § "Cosmos firewall + ACA egress (the trap
that wastes 45 min on every fresh PoC)".

### Why composable modules (not one big main.bicep)

- **Per-process repos vary widely** — KYC needs `doc-intel + speech + foundry-iq`;
  Order Fallout needs `service-bus + aca-job + aca-mcp`. A single template would
  bury 70% of the file in `if` blocks per module.
- **Customer can adopt modules incrementally** — they may already have a Cosmos
  account they want to reuse; replacing one module file is cleaner than editing
  a monolith.
- **Each module is independently versionable** — when AI Search v2025-09 ships
  a new index schema, only `ai-search.bicep` changes.

### How a new module gets added to the library

1. Author the module Bicep at `infra/modules/<name>.bicep` (single self-contained file)
2. Document its outputs (must be stable — they're the wire format between modules)
3. Add a row to the catalog table above
4. Update `threadlight-deploy` Phase 6's selector parser to recognize the new key
5. If the module wires a runtime service (cosmos, search, vision, etc.), add a
   line to `agent.yaml`'s `environment_variables:` so the agent receives endpoints

---

## Input contract / Output artifacts

| Reads | From |
|-------|------|
| **SPEC.md § 11c Tech Stack module selectors** | `threadlight-design` |
| **SPEC.md § 5 Integrations** (which systems are real vs mock) | `threadlight-design` |
| **SPEC.md § 7b AI Services & Model Selection** (which Foundry models, which deployment names) | `threadlight-design` |
| **SPEC.md § 11b Governance Posture** (drives whether `keyVault` and `app-insights` get their secrets pre-loaded) | `threadlight-design` |

| Produces | At |
|----------|-----|
| `infra/main.bicep` | Includes only the modules SPEC § 11c selected |
| `infra/modules/*.bicep` | One file per included module |
| `infra/main.parameters.json` | Wires SPEC selectors → Bicep parameters |
| `azure.yaml` `hooks:` | postprovision/postdeploy entries for ACA Jobs and Bot wiring |
| `infra/scripts/*.py` | Hook script implementations (uv-managed) |

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-deploy**](../threadlight-deploy/) | Phase 6 (Module Composer) is the consumer of this Bicep library |
| [**threadlight-design**](../threadlight-design/) | Defines SPEC § 11c selectors that drive module inclusion |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Owns the `aca-mcp.bicep` shape |
| [**foundry-teams-bot**](../foundry-teams-bot/) | Owns the `aca-bot.bicep` shape |
| [**foundry-iq**](../foundry-iq/) | Owns the `foundry-iq-index.bicep` shape |
| [**threadlight-event-triggers**](../threadlight-event-triggers/) | Owns the `aca-job.bicep` shape (cron + manual triggers) |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | Owns the `foundry-account.bicep` shape |
| [**citadel-spoke-onboarding**](../citadel-spoke-onboarding/) | Adds Citadel hub wiring AFTER the base Bicep is provisioned (opt-in via SPEC § 11b `citadel.required: yes`) |
| [**azure-tenant-isolation**](../azure-tenant-isolation/) | Per-tenant `AZURE_CONFIG_DIR` so `azd up` lands in the right tenant |

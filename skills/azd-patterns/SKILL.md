---
name: azd-patterns
description: >
  Tips and patterns for Azure Developer CLI (azd) workflows, ACA job deployment,
  and infrastructure scripting conventions.
  USE FOR: azd hooks, postdeploy, postprovision, ACA job deployment, container app
  job image update, publish_aca, deploy_job, azure.yaml hooks, cross-platform
  deployment scripts, uv run, azd env, azd conventions, infra scripts,
  MCAPS subscription, SecurityControl Ignore tag, resource group tagging,
  Defender for Cloud noise, Azure Policy auto-remediation, AZURE_TAGS,
  pilot posture, demo subscription tagging, AcrPull, ImagePullError, JSON array param,
  BCP186, FetchingKeyVaultSecretFailed, dependsOn rbac, image-pull credential,
  ACA placeholder image, azd env set triple-escape.
  DO NOT USE FOR: az login, tenant switching, subscription isolation (use
  azure-tenant-isolation), Foundry agents (use microsoft-foundry).
metadata:
  version: "1.4.9"
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

## Fetch-Latest-Image Pattern (Bicep + ACR)

When Bicep provisions a Container App (or Job), it needs an image reference.
On **first deploy** the real image hasn't been built yet, so Bicep uses a
placeholder. On **subsequent deploys**, `azd deploy` builds the real image into
ACR and patches the running container. This is the expected lifecycle — the
placeholder in Bicep is intentional, not a bug.

### Why the placeholder exists

```bicep
// infra/main.bicep — first-deploy bootstrap
resource mcpApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
  ...
  tags: {
    'azd-service-name': 'mcp'  // REQUIRED — azd deploy uses this tag to find the resource
  }
  properties: {
    template: {
      containers: [
        {
          name: 'mcp'
          // Placeholder: azd deploy will swap this to the real ACR image
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        }
      ]
    }
  }
}
```

> ⚠️ **The `azd-service-name` tag is MANDATORY.** `azd deploy` locates the
> Container App to patch by searching for a resource tagged with
> `azd-service-name: <service>` matching the service name in `azure.yaml`.
> Without this tag, `azd deploy` fails with "resource not found: unable to
> find a resource tagged with 'azd-service-name: mcp'". This is not
> documented prominently in the azd docs — add it to every ACA Bicep.

On `azd up`:
1. `azd provision` runs Bicep → Container App created with placeholder image
2. `azd deploy` builds `src/mcp/` → pushes to ACR → patches the Container App with the real image
3. Subsequent `azd deploy` calls repeat step 2 only

### Pattern A — `azure.yaml` service binding (recommended)

Let `azd` manage the image lifecycle. Declare each container as a service:

```yaml
# azure.yaml
services:
  mcp:
    host: containerapp
    project: src/mcp
    docker:
      path: src/mcp/Dockerfile
      context: src/mcp
```

`azd deploy` will:
- Build the Dockerfile into ACR (tag = `azd-deploy-{timestamp}`)
- Set env var `SERVICE_MCP_IMAGE_NAME` = full ACR image ref
- Patch the Container App to use the new image

### `azure.yaml` field traps

> ⚠️ **`language: html` and `language: static` are NOT valid `azure.yaml`
> values.** They look plausible for static or front-end services but silently
> break `azd` build detection. For custom-Dockerfile services, omit
> `language` entirely and declare only `project` + `docker`.

When the Dockerfile is not in the service root, set `docker.context` to the
actual build-context directory:

```yaml
services:
  web:
    host: containerapp
    project: .
    docker:
      path: ./src/Dockerfile
      context: ./src
```

Without `docker.context`, `azd deploy` builds from the service root and the
Dockerfile's `COPY` lines fail because the expected files are outside the
build context.

### Pattern B — `postdeploy` hook with `SERVICE_*_IMAGE_NAME`

For Container Apps **Jobs** (not managed by `azd deploy`), use a postdeploy
hook that reads the azd-generated image name:

```yaml
hooks:
  postdeploy:
    shell: pwsh
    run: 'cd infra/scripts && uv sync --frozen && uv run deploy_job.py'
```

```python
# infra/scripts/deploy_job.py
image_name = os.getenv("SERVICE_MCP_IMAGE_NAME")  # set by azd deploy
# ... patch the Container App Job with this image
```

### Pattern C — Bicep `containerImage` parameter with default

For repos where the image is pre-built (e.g., shared ACR across teams):

```bicep
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource app 'Microsoft.App/containerApps@2024-10-02-preview' = {
  ...
  properties: {
    template: {
      containers: [{ name: 'app', image: containerImage }]
    }
  }
}
```

Override at deploy time: `azd provision --parameter containerImage=myacr.azurecr.io/app:v2`

### The `SERVICE_*_IMAGE_NAME` convention

`azd` auto-generates env vars for each service declared in `azure.yaml`:

| azure.yaml service name | Env var | Example value |
|---|---|---|
| `mcp` | `SERVICE_MCP_IMAGE_NAME` | `acrfoo.azurecr.io/mcp:azd-deploy-1716300000` |
| `agent` | `SERVICE_AGENT_IMAGE_NAME` | `acrfoo.azurecr.io/agent:azd-deploy-1716300000` |

These are available in `postdeploy` hooks and in `.azure/{env}/.env`.

> **⚠️ Don't treat the Bicep placeholder as a bug.** When reviewing Bicep
> that uses `containerapps-helloworld:latest`, check whether `azure.yaml`
> declares the corresponding service. If it does, `azd deploy` handles the
> image swap automatically. The placeholder is a bootstrap artifact, not a
> deployment gap.

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
| ConsoleLogs empty + SystemLogs `Type=Pull`, `Reason=ImagePullError` | ACR pull RBAC missing on the UAMI **bound to that specific ACA app** (`identity.userAssignedIdentities`), or image tag doesn't exist in ACR. **Common trap:** in a multi-service pilot every ACA app has its own UAMI (frontend UAMI, backend UAMI, …) and **each one independently needs AcrPull** — granting it only to a "shared env UAMI" or to the Foundry project MI (which covers the agent container) leaves frontend / backend revisions stuck. **2nd common trap:** `FetchingKeyVaultSecretFailed: 401` in SystemLogs is also this — the ACA system component mis-categorises image-pull credential failure as a Key Vault error | Verify `az acr repository show-tags`; grant `AcrPull` (`7f951dda-…`) on the ACR to every ACA-app UAMI in `rbac.bicep` |
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

### Escalation rule: 3-fix limit

If you have attempted **3 or more fixes** and each one reveals a new
problem in a different place (auth → RBAC → identity → timing → retry),
**STOP**. This is not a configuration problem — it is an architecture
problem. Each fix exposing a new failure in a different subsystem means
the design assumptions are wrong.

| Excuse | Reality |
|--------|---------|
| "I'm almost there, one more fix" | You said that 2 fixes ago. The pattern is divergent. |
| "Each fix is small and targeted" | Small fixes to the wrong architecture produce infinite small fixes. |
| "I just need to try a different parameter" | If 3 different parameters in 3 different subsystems all fail, the subsystems don't compose the way you assumed. |

**Action:** Report the 3+ failed attempts to the user with a 1-sentence
diagnosis of why the fixes diverge, and ask whether to continue with the
current architecture or redesign.

---

## Verification before completion

**DO NOT report deployment success until evidence is collected.** `azd up`
returning exit code 0 means Bicep succeeded — it does NOT mean the
application works.

After every `azd up` / `azd deploy`, run this 5-step gate:

1. **Identify** the verification command (e.g., `curl`, `az containerapp show`,
   App Insights KQL query).
2. **Run it fresh** — do not rely on cached output or prior runs.
3. **Read the full output** — do not truncate or skip error sections.
4. **Verify** the output matches expected behavior (HTTP 200 with correct
   body, container in `Running` state, traces present).
5. **Only then claim success** — include the verification evidence in your
   response.

Minimum verification checklist after `azd up`:

| Check | Command | Expected |
|-------|---------|----------|
| ACA running | `az containerapp show -g <rg> -n <app> --query "properties.runningStatus"` | `Running` |
| No placeholder image | `az containerapp show -g <rg> -n <app> --query "properties.template.containers[0].image"` | Not `containerapps-helloworld` |
| Health endpoint | `curl -fsS <app-url>/health` | HTTP 200 |
| App Insights traces | KQL: `traces \| where timestamp > ago(5m) \| count` | Count > 0 (warn-only if 0) |

### Rationalisation prevention

| Excuse | Reality |
|--------|---------|
| "`azd up` returned 0, so it worked" | Exit code 0 means Bicep succeeded. It says nothing about whether the application started, responds to requests, or emits telemetry. |
| "I'll verify later" | You won't. The next task will consume your attention. Verify now while the deployment context is fresh. |
| "The logs looked fine" | Deployment logs show Bicep resource creation. They don't show runtime health. A container can deploy successfully and crash-loop immediately. |
| "It worked in my last deployment" | Azure state is mutable. Image tags, RBAC propagation, network rules, and secret expiry all change between deployments. |

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

> **MUST:** Copy verbatim from [`references/bicep/rbac.bicep`](references/bicep/rbac.bicep). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the full role-assignment module (Foundry project MI + workload UAMIs + ACR + Foundry account, all pinned by GUID).

**Why each line matters:**

- **Role GUIDs are stable across tenants** — never ship `'...'` as a placeholder. Bicep compiles but `RoleDefinitionDoesNotExist` blows up at apply-time, after every other resource has provisioned. Built-ins referenced in the module: `Foundry User` (renamed from `Azure AI User` in May 2026; GUID unchanged) = `53ca6127-db72-4b80-b1b0-d745d6d5456d`, `Search Index Data Reader` = `1407120a-92aa-4202-b7e9-c0e197c71c8f`, `AcrPull` = `7f951dda-4ed3-4680-a7ca-43fe172d538d`.
- **`principalType: 'ServicePrincipal'`** is mandatory for MI-based deploys; see § CI/CD trap below for why `'User'` breaks GHA / ADO pipelines.
- **One module, one `dependsOn:[rbac]` from every consumer** — see § Prefer Bicep `dependsOn: [rbac]` below for the wiring pattern that pre-empts the AcrPull propagation race.

### CI/CD trap — `PrincipalTypeNotSupported`

When the deploy runs from GitHub Actions or Azure DevOps, Bicep role
assignments that emit `principalType: 'User'` often fail with
`PrincipalTypeNotSupported`. For MI-based deploys, set
`allowUserIdentityPrincipal: false` in the shared `roleAssignment` Bicep
module or force `principalType: 'ServicePrincipal'`. Use `User` only when
binding a real human principal.

### Exception: Hosted agent containers

Hosted agent containers get a **platform-managed dedicated identity** (instance + blueprint)
at deploy time — you don't assign a UAMI to them. The shared UAMI is for everything
else: bot ACA, MCP ACA, jobs, hooks, etc.

### Cross-skill ownership: UAMI & AcrPull

**Ownership split:** UAMI and AcrPull guidance is split across two SKILLs:
- **Foundry project system MI** (the identity used by Foundry to pull agent container images) → owned by [`foundry-hosted-agents`](../foundry-hosted-agents/) § Identity & RBAC
- **ACA workload UAMIs** (backend, frontend, job containers, hooks) → owned by this SKILL

When in doubt: project MI RBAC → `foundry-hosted-agents`; workload UAMI RBAC → `azd-patterns`.

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

## `azd env set` + JSON arrays/objects: use `.bicepparam`, not JSON parameters

> **🔴 DO NOT** pass JSON arrays via `azd env set`. The value gets triple-escaped through shell → azd → Bicep → ARM. Use `.bicepparam` files or `--parameters` instead.

> 🛑 **DO NOT** push array- or object-typed values through `azd env set`. The CLI re-escapes
> the value on every `.env` read/write, producing triple-escaped JSON that fails to round-trip.
> **DO** hard-code the literal in `infra/main.bicepparam` instead — that is the only safe
> place for array/object Bicep parameters.
>
> Even worse: the `azd ai agent` extension auto-runs `azd env set AI_PROJECT_DEPLOYMENTS '[...]'`
> on EVERY `azd provision` (silently). So even if you set `AI_PROJECT_DEPLOYMENTS` cleanly
> by hand once, the next provision will re-mangle it. Using `readEnvironmentVariable(...) + json(...)`
> for this specific param is therefore guaranteed to fail eventually — **hardcode the literal**.

**Don't put JSON arrays or objects through `azd env set`.** The CLI
re-escapes the value on every read/write of `.azure/<env>/.env`, so a
clean PUT like:

```bash
azd env set AI_PROJECT_DEPLOYMENTS '[{"name":"gpt-5.4-mini","model":{"name":"gpt-5.4-mini","format":"OpenAI","version":"2026-03-17"},"sku":{"name":"GlobalStandard","capacity":100}}]'
```

lands in `.env` as triple-escaped JSON (`[{\\\"name\\\":\\\"gpt-5.4-mini\\\",…}]`)
and fails to round-trip through `azd env get-value`, through
`main.parameters.json` `${VAR}` substitution, and through Bicep's
`json()` function. Provisioning fails with
`invalid character '\\' looking for beginning of object key string`
or `invalid character '$' looking for beginning of value`. Verified on
`azd 1.25.0` (May 2026 fruocco pilot).

**Workaround: use a `.bicepparam` file** (`infra/main.bicepparam`) and
either (a) hard-code the array literal in Bicep syntax when the value is
a spec-level decision, or (b) read structured env vars via
`readEnvironmentVariable(…)` paired with `json(…)` for things that must
be runtime-configurable.

> **MUST:** Copy verbatim from [`references/bicep/main.bicepparam`](references/bicep/main.bicepparam). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical `using './main.bicep'` parameter file with the literal-array `aiProjectDeployments` (closes A1) at `capacity: 30` (closes MID-9). It is intentionally skipped by `az bicep build` in CI because `using` can't resolve in isolation.

> **🔴 DO NOT** default model `capacity` to 100 K TPM in a shared subscription.
> Shared subs often run at 900+/1000 K TPM aggregate quota; a fresh
> `azd provision` with `capacity: 100` fails with `InsufficientQuota`
> mid-deploy and the only fix is to lower the capacity and re-provision (~4 min wasted).
> Default to `capacity: 30` for pilot deployments; preflight with
> `az cognitiveservices usage list --location <region>` and raise only
> after confirming free quota. The 30 K TPM ceiling also forces realistic
> demo pacing (~80 s between scenario calls) — useful for catching
> retry-handling bugs early.

```bicep
// Option B (NOT in the reference file): structured env for genuinely runtime-configurable values.
// Set as a single-quoted JSON string in `.azure/<env>/.env` by HAND-EDITING
// the file once (not via `azd env set`) — azd will preserve it on subsequent
// reads, but every `azd env set` of any value re-mangles it.
// param secondaryDeployments = json(readEnvironmentVariable('SECONDARY_DEPLOYMENTS', '[]'))
```

In `azure.yaml`'s `infra:` section, point to the `.bicepparam` file
**instead** of the `.json` parameters file (azd accepts either when
present at the standard location).

**Plain string/bool/number env vars are fine to use with `azd env set`** —
the bug is array/object-typed values only.

---

## Composable Bicep Module Library

`threadlight-deploy` Phase 6 (Module Composer) reads SPEC § 11c and includes
exactly the right Bicep modules. This section catalogs the modules and what
SPEC inputs select them.

> **MUST:** Use the canonical reference Bicep modules vendored from the 2026-05-29 smb-credit-memo pilot (live-deployed in `swedencentral`, agentic-loop SKILL Validation history row 8). Do NOT redefine them inline in this SKILL — each file is single-source-of-truth and is cross-linked from the section that explains it:
>
> - [`references/bicep/foundry-account.bicep`](references/bicep/foundry-account.bicep) — Foundry account + project + capabilityHost (account-level FIRST per MID-10) + model deployment + AppIn connection with explicit `metadata.ConnectionString` (per MID-8) + `endpoints['AI Foundry API']` output (per MID-2).
> - [`references/bicep/aca-app.bicep`](references/bicep/aca-app.bicep) — canonical 3-service-shape ACA container app (consumed by § ACR + ACA Registry Binding and § Prefer Bicep `dependsOn: [rbac]`).
> - [`references/bicep/rbac.bicep`](references/bicep/rbac.bicep) — all role assignments pinned by GUID (consumed by § RBAC — assign once).
> - [`references/bicep/main.bicepparam`](references/bicep/main.bicepparam) — literal-array `aiProjectDeployments` parameter file (consumed by § `azd env set` + JSON arrays/objects).

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
| **app-insights** | `infra/modules/app-insights.bicep` | (always — non-optional) | `connectionString`, `instrumentationKey`, `appId` | Always — required for `foundry-evals` continuous loop. **Telemetry wiring** (AppInsights connection string env injection, client-side instrumentation, retry on transient drops) is owned by [`foundry-observability`](../foundry-observability/) § Layer 2. This SKILL focuses on deploy mechanics; for telemetry configuration, see foundry-observability. |
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

## RG Tagging — MCAPS Subscriptions (`SecurityControl: Ignore`)

**MCAPS** (Microsoft Customer & Partner Solutions — the internal subscription
class GBBs and the field use for customer demos / PoCs / tenant-specific
work) ships with org-wide Defender for Cloud + Azure Policy assignments
that aggressively flag and (in some MCAPS rings) auto-remediate resources
the security team considers risky. For pilot work this manifests as:

- Cosmos / Storage / KV firewalls flipped back to `Disabled` minutes after
  `azd up` finishes — every demo breaks the next morning.
- Container Apps with `ingress.external = true` flagged as critical
  findings on the team's compliance dashboard.
- `Microsoft.Security` policy emails landing in the deal lead's inbox the
  day before the customer call.

The supported escape hatch is the **`SecurityControl: Ignore`** tag.
Applied at the **resource-group level**, every Defender / Policy
assignment that reads it skips the RG and everything inside it. This is
explicitly sanctioned for **non-production** subscriptions (PoC, demo,
pre-sales sandbox) — never apply it in a customer's own production
landing zone.

> **Scope**: this section applies ONLY to Microsoft-internal MCAPS
> subscriptions. In a customer tenant, leave the RG untagged and let
> the customer's own governance posture apply.

### Three ways to set it (pick one — they compose)

#### 1 — Bicep, subscription-scope RG creation (preferred for `azd` repos)

When `azd up` creates the RG via a subscription-scope deployment, set the
tag on the RG resource itself:

```bicep
// infra/main.bicep — targetScope = 'subscription'
@description('When true (default for MCAPS pilot subs), tags the RG so Defender for Cloud / Azure Policy skip it. Set false in customer-owned subscriptions.')
param mcapsPilotPosture bool = true

@description('Free-form tags to merge onto the RG and propagate to every resource.')
param tags object = {}

var baseTags = union(tags, mcapsPilotPosture ? { SecurityControl: 'Ignore' } : {})

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
  tags: baseTags
}
```

Then thread `tags: baseTags` into every resource-group-scope module call so
**resources inherit the tag too** (some Defender controls evaluate at
resource scope, not RG scope):

```bicep
module workload './modules/main.bicep' = {
  scope: rg
  name: 'workload'
  params: {
    tags: baseTags
    // ...
  }
}
```

Every leaf module's resource declarations should accept `tags` and pass it
through:

```bicep
// infra/modules/<any>.bicep
param tags object = {}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-12-01-preview' = {
  // ...
  tags: tags
  // ...
}
```

#### 2 — `AZURE_TAGS` (honored by `azd` for resource-group-scope deploys)

If `infra/main.bicep` is **resource-group-scope** (i.e., `azd` creates the
RG itself rather than a subscription-scope template), set the tag via the
azd environment so `azd provision` applies it:

```powershell
azd env set AZURE_TAGS '{"SecurityControl":"Ignore","Workload":"<pilot-name>"}'
azd provision
```

`azd` reads `AZURE_TAGS` and applies it to the RG it creates. This does
**not** propagate to child resources automatically — pair with the Bicep
`tags` param-threading shown above for full coverage.

#### 3 — `az group update` postprovision hook (fallback for pre-existing RG)

When the RG was created out-of-band (Cowork sandbox, manual `az group
create`, BYO landing zone) and you can't reshape the deploy:

```yaml
# azure.yaml
hooks:
  postprovision:
    shell: pwsh
    run: |
      az group update --name $env:AZURE_RESOURCE_GROUP `
        --set tags.SecurityControl=Ignore `
        --output none
```

This is the least invasive option but only tags the RG, not the resources
inside. Defender controls that evaluate at resource scope (Cosmos
firewall, Storage public access, KV soft-delete) may still fire.

### Verifying it landed

```powershell
# RG tag present?
az group show --name $env:AZURE_RESOURCE_GROUP `
  --query "tags.SecurityControl" -o tsv      # → "Ignore"

# Resource-level tag present? (spot-check the chattiest resource type)
az resource list --resource-group $env:AZURE_RESOURCE_GROUP `
  --query "[?type=='Microsoft.DocumentDB/databaseAccounts'].tags.SecurityControl" -o tsv
```

Defender / Policy honor the tag on the **next evaluation cycle** (typically
≤ 1 hour). If a finding was already open before the tag was applied,
manually dismiss it once — it won't re-open.

### Cross-skill applicability

Every `azd`-based deploy in this catalog should expose `mcapsPilotPosture`
+ `tags` the same way:

- **`threadlight-deploy`** — Phase 6 module composer threads `tags` into
  every selected module from the catalog above (when present in SPEC § 11c
  or via `AZURE_TAGS`).
- **`foundry-vnet-deploy`** — `templates/main.bicep` accepts `tags` (manual
  apply via Step 8 interview); when the deploy lands in an MCAPS sub, the
  operator should answer `yes` to the implicit MCAPS prompt.
- **`foundry-mcp-aca`**, **`foundry-teams-bot`**, **`citadel-spoke-onboarding`** —
  all consume the same module library; the tag rides along automatically
  when `tags` is passed at the parent scope.

> **Don't hard-code the tag value.** Apply `SecurityControl: Ignore` only
> when `mcapsPilotPosture` is `true`. Letting it leak into a customer
> tenant's deployment files is a finding in its own right.

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

## ACA Persistent Volume (Azure Files)

When an ACA container needs persistent storage across restarts (e.g.,
embedded databases like KuzuDB, file caches, local state), use an Azure
Files volume mount. This is the simplest persistent storage pattern for
ACA — no Cosmos DB, no Blob SDK, just a filesystem path.

### Bicep module: `aca-volume.bicep`

```bicep
// infra/modules/aca-volume.bicep
@description('Storage account for ACA volumes')
param storageAccountName string
param location string = resourceGroup().location
param shareName string = 'aca-data'
param shareQuotaGb int = 5

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
}

resource fileServices 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: fileServices
  name: shareName
  properties: {
    shareQuota: shareQuotaGb
  }
}

output storageAccountName string = storage.name
output shareName string = share.name
output storageAccountKey string = storage.listKeys().keys[0].value
```

### ACA environment volume binding

In the ACA environment Bicep, register the storage as a volume:

```bicep
// In the ACA app resource
resource app 'Microsoft.App/containerApps@2024-03-01' = {
  // ...
  properties: {
    template: {
      volumes: [
        {
          name: 'persistent-data'
          storageType: 'AzureFile'
          storageName: acaEnvStorage.name  // registered on the ACA env
        }
      ]
      containers: [
        {
          // ...
          volumeMounts: [
            {
              volumeName: 'persistent-data'
              mountPath: '/data'           // KuzuDB writes here
            }
          ]
        }
      ]
    }
  }
}
```

### Register storage on ACA environment

```bicep
resource acaEnvStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: acaEnvironment
  name: 'persistent-data'
  properties: {
    azureFile: {
      accountName: storageAccount.name
      accountKey: storageAccount.listKeys().keys[0].value
      shareName: fileShare.name
      accessMode: 'ReadWrite'
    }
  }
}
```

### When to use

- Embedded databases (KuzuDB, SQLite) that must survive container restarts
- File caches that are expensive to rebuild
- Demo data snapshots that persist between `azd deploy` cycles

### When NOT to use

- High-throughput data → use Cosmos DB
- Large datasets (>5 GB) → use Blob Storage via SDK
- Multi-replica writes → Azure Files is ReadWriteMany but NOT designed
  for concurrent high-frequency writes from multiple containers

---

## `azd up` is THE deployment path

> ⚠️ **`azd up` (= `azd provision` + `azd deploy`) is the default and
> preferred way to deploy ACA workloads.** It handles Bicep provisioning,
> Docker image build, ACR push, and ACA image swap in one command.
>
> Raw `az deployment sub create` + `az acr build` + `az containerapp update`
> is an **escape hatch only** — use it when `azd` is unavailable (e.g., CI
> without `azd` installed, or debugging a specific Bicep module). Never use
> raw `az` as the primary deploy path when `azd` is available.

---

## ACR + ACA Registry Binding (complete example)

> **MUST:** Every UAMI assigned to an ACA container app needs `AcrPull` on the container registry. This applies to EVERY service — not just the first one. Missing `AcrPull` causes `ImagePullError` with a misleading "Key Vault 401" message.

> 🛑 **MUST rule.** In a multi-service pilot, **every ACA app's UAMI** independently
> needs `AcrPull` on the ACR — not just a "shared env UAMI" or the Foundry **project** MI
> (which only covers the agent container). Granting `AcrPull` to ONE identity and assuming
> it covers the others leaves frontend / backend revisions stuck on the placeholder
> `mcr.microsoft.com/k8se/quickstart:latest` image, with `FetchingKeyVaultSecretFailed: 401`
> in `ContainerAppSystemLogs_CL` (yes, that's the wrong category — the ACA system component
> mis-categorises image-pull credential failure as a Key Vault error). Verified live in
> the 2026-05-28 learn-assistant pilot.

When `azd deploy` pushes an image to ACR, the ACA must be configured to
pull from that ACR. This requires three things in Bicep: (1) the ACR
resource, (2) the ACA with `registries[]` + `secrets[]` + `azd-service-name`
tag, and (3) the `AZURE_CONTAINER_REGISTRY_ENDPOINT` output for azd.

> **MUST:** Copy verbatim from [`references/bicep/aca-app.bicep`](references/bicep/aca-app.bicep). Do NOT redefine inline — the validator enforces single-source-of-truth. That file is the canonical 3-service-shape ACA module (UAMI + registry binding + placeholder image), live-deployed across the 2026-05 pilots (weather-agent, learn-assistant, smb-credit-memo, hybrid-mcp-agent).

**Without all three pieces, `azd deploy` pushes to ACR successfully but the ACA fails to pull the image (401 unauthorized).** The placeholder `image:` lets the first revision land before the real image is built; `azd deploy` then patches it. The `tags: { 'azd-service-name': 'agent' }` is what binds this Bicep resource to the `services:` entry in `azure.yaml` — missing or mistyped, `azd deploy` skips this app silently.

### AcrPull propagation retry loops (post-`azd provision`, pre-`azd deploy`)

> 💡 **Preferred fix first.** If your `main.bicep` invokes a separate `rbac` module +
> ACA-app modules in the same deployment, use Bicep `dependsOn: [rbac]` on every
> ACA-app module to **pre-empt** the race at provision time. See § Prefer Bicep
> `dependsOn: [rbac]` below for the canonical pattern. The retry loop here is the
> fallback for cross-deployment scenarios (e.g. role granted between provision and
> deploy, or RBAC propagation lags ARM completion).

If `azd provision` grants `AcrPull` to the ACA environment or shared UAMI,
do **not** immediately run `azd deploy`. RBAC propagation can lag by a few
minutes, so the first deploy fails with `ImagePullError` even though the
assignment exists. Poll the role assignment before proceeding:

```bash
# Wait for AcrPull RBAC propagation before deploying
MAX_RETRIES=5; SLEEP=60
for i in $(seq 1 $MAX_RETRIES); do
  ROLE=$(az role assignment list --assignee "$IDENTITY_PRINCIPAL_ID" --role "AcrPull" --scope "$ACR_ID" --query "[0].roleDefinitionName" -o tsv 2>/dev/null)
  [ "$ROLE" = "AcrPull" ] && echo "✅ AcrPull propagated" && break
  echo "⏳ AcrPull not yet visible (attempt $i/$MAX_RETRIES), waiting ${SLEEP}s..."
  sleep $SLEEP
done
[ "$ROLE" != "AcrPull" ] && echo "❌ AcrPull not propagated after $((MAX_RETRIES * SLEEP))s" && exit 1
```

```powershell
# Wait for AcrPull RBAC propagation before deploying
$maxRetries = 5; $sleep = 60
for ($i = 1; $i -le $maxRetries; $i++) {
    $role = az role assignment list --assignee $identityPrincipalId --role "AcrPull" --scope $acrId --query "[0].roleDefinitionName" -o tsv 2>$null
    if ($role -eq 'AcrPull') { Write-Host "✅ AcrPull propagated"; break }
    Write-Host "⏳ AcrPull not yet visible (attempt $i/$maxRetries), waiting ${sleep}s..."
    Start-Sleep -Seconds $sleep
}
if ($role -ne 'AcrPull') { Write-Error "❌ AcrPull not propagated after $($maxRetries * $sleep)s"; exit 1 }
```

### Prefer Bicep `dependsOn: [rbac]` over the retry loop when both modules live in the same deployment

> **MUST:** Add `dependsOn: [rbac]` to every ACA module that references a UAMI. Without it, `azd up` races RBAC propagation and the first deploy fails with 401.

The retry loop above patches the **symptom** at deploy time. The cleaner fix
is to **pre-empt** the race at provision time: when `main.bicep` invokes a
separate `rbac` module (the canonical pattern when role assignments are
batched) and ACA-app modules in parallel, Bicep does **not** infer a
dependency between them unless one references the other's outputs.

Add an explicit `dependsOn: [rbac]` to every ACA-app module invocation so the
ARM engine waits for role assignment PUTs to return before starting the
container app provision:

```bicep
// infra/main.bicep
module rbac './modules/rbac.bicep' = {
  name: 'rbac'
  scope: rg
  params: {
    foundryProjectPrincipalId: foundry.outputs.projectMiPrincipalId
    backendUamiPrincipalId:    backendUami.outputs.principalId
    frontendUamiPrincipalId:   frontendUami.outputs.principalId
    acrName:                   acr.outputs.name
    foundryAccountName:        foundry.outputs.accountName
  }
}

module backendApp './modules/aca-app.bicep' = {
  name: 'backend'
  scope: rg
  dependsOn: [ rbac ]   // ← waits for AcrPull to be assigned before first revision
  params: { /* ... */ }
}

module frontendApp './modules/aca-app.bicep' = {
  name: 'frontend'
  scope: rg
  dependsOn: [ rbac ]   // ← same
  params: { /* ... */ }
}
```

The retry loop is still the right fallback for **deploy-time** scenarios
(e.g. the user grants a new role between `azd provision` and `azd deploy`,
or RBAC propagation lags ARM completion as it occasionally does in
`swedencentral` / `eastus2`). Use `dependsOn` first; keep the retry loop as
belt-and-braces.

**Two failure surfaces this prevents (both verified on real pilots, May 2026):**

- Frontend / backend ACA app stuck at `mcr.microsoft.com/k8se/quickstart:latest`
  placeholder after `azd deploy`: the first revision tried to pull the real
  image before AcrPull existed, fell back to the placeholder, and `azd` reported
  Success.
- Cryptic `FetchingKeyVaultSecretFailed: 401` in `ContainerAppSystemLogs_CL`
  after the first revision (it's actually the image-pull credential failing —
  the error is mis-categorised by the ACA system component).

---

## `az deployment sub validate` with `.bicepparam` — pass the `.bicep` directly, NOT the compiled `.json`

> 🛑 **DO NOT** pre-compile your Bicep to ARM JSON and then validate with
> `--template-file infra/main.json --parameters infra/main.bicepparam`. Recent
> `az` (verified on 2.86 / azd 1.25, May 2026) **rejects this combination**
> with: *"Only a .bicep template is allowed with a .bicepparam file"*.
>
> **DO** pass `infra/main.bicep` directly:
>
> ```bash
> az deployment sub validate \
>   --location <region> \
>   --template-file infra/main.bicep \
>   --parameters infra/main.bicepparam
> ```
>
> `az` compiles the Bicep itself as part of the validation pipeline; one fewer
> step and the only shape `.bicepparam` validates cleanly against.

This shows up as a noisy red error during automated Verify pipelines (any CI
workflow that does plan-coherence checks before provisioning). The fix is one
CLI argument; no Bicep / parameter rewrites needed.

---

## `azd` reformats `azure.yaml` to 4-space indent after first deploy

azd 1.25 silently rewrites `azure.yaml` from your authored indent (typically
2-space) to 4-space after the first successful `azd deploy <service>`.
The file content is semantically identical but any tool that parses
`azure.yaml` with a hand-rolled 2-space-only YAML regex (e.g. ad-hoc
shell/Python scripts that grep for `^  <name>:` or `^    host:`) will break
on the second invocation.

**Fix in any tool that parses `azure.yaml`:** make the indent detection
dynamic. Read the first non-blank indented line under `services:`, take its
indent as the service-name indent, then anything deeper is a property.

Verified live on 2026-05-28 (azd 1.25, hosted-agent pilot):
first `azd deploy` left azure.yaml at the authored 2-space indent; the
second `azd deploy` (same project, same env) rewrote it to 4-space. azd
reports no diff in `azd env get-values`.

> 💡 If your tool MUST stay 2-space-strict, lock azure.yaml after first
> deploy with `chattr +i` (Linux) / file system attributes (macOS/Win),
> but that's a workaround for poor parsers; fix the parser instead.

---

## ACA Container Debugging — check logs FIRST

> ⚠️ **When an ACA container fails, ALWAYS check system logs before
> retrying.** Port mismatches, startup probe failures, image pull errors,
> and OOM kills are all visible in system logs. Retrying without reading
> logs wastes time.

**Canonical owner of container-debugging diagnostics:** This section (§ ACA Container Debugging) is the authoritative reference for container-failure diagnosis. Sibling SKILLs (`foundry-hosted-agents`, `foundry-observability`, etc.) should link here rather than duplicate.

```bash
# System logs — infrastructure events (port mismatch, probe fail, OOM)
az containerapp logs show -g <rg> -n <app> --type system --tail 20

# Console logs — application stdout/stderr
az containerapp logs show -g <rg> -n <app> --type console --tail 20
```

### Common failures and what they look like in logs

| System log message | Cause | Fix |
|---|---|---|
| `TargetPort 8080 does not match the listening port 80` | Bicep `targetPort` ≠ container's actual listen port | Fix `targetPort` in Bicep to match the app |
| `Container failed startup probe, will be restarted` | App crashes or takes too long to start | Check console logs for the crash reason |
| `Failed to pull image ... 401 Unauthorized` | ACA can't auth to ACR | Add registry binding + secret (see ACR section above) |
| `Persistent Failure to start container` / `ContainerBackOff` | Container exits immediately | Check console logs — likely a Python crash or missing entrypoint |
| `azd postdeploy` / `azd postprovision` hook exits with non-zero code | Missing or incorrect `AZURE_AI_PROJECT_ENDPOINT` or other azd env value in hook script | DO NOT: hardcode env var lookups. DO: use `azd env get-value VAR_NAME` with explicit error handling. Fix: re-run hook manually via `cd infra/scripts && uv run <hook>.py` after checking all required env vars are set. |
| `FetchingKeyVaultSecretFailed: 401` in `ContainerAppSystemLogs_CL` | ACA UAMI lacks `AcrPull` on the private ACR (NOT a Key Vault issue — ACA mis-categorises image-pull credential failure) | DO NOT: trust the "Key Vault" label literally. DO: first check `az role assignment list --assignee <aca-uami-principal-id> --scope <acr-resource-id>` to confirm `AcrPull` exists. Ensure all ACA UAMIs (backend, frontend, job) have independent `AcrPull` assignments (see § ACR + ACA Registry Binding). |
| ACA revision status shows `secret-resolution` error | Revision references a Key Vault secret that the ACA UAMI cannot read (actual Key Vault permission issue) | Grant `Key Vault Secrets User` role on the vault to the ACA UAMI, then redeploy or trigger a new revision. |
| First revision after `azd provision` fails image pull; retry within minutes succeeds | RBAC propagation lag (30–60 seconds) — the role assignment was created but hasn't propagated to the image-pull auth path | DO NOT: rely on retry loops alone. DO: add Bicep `dependsOn: [rbac]` on every ACA-app module to pre-empt the race (see § Prefer Bicep `dependsOn: [rbac]` below). The retry loop is fallback for cross-deployment scenarios. |

---

## ACA Scale-to-Zero Gotcha

`minReplicas: 0` means the container **doesn't start until the first
request arrives**. This is efficient for production but confusing during
deploy testing — you deploy, curl the endpoint, get a timeout, and think
the deploy failed when it's actually just cold-starting.

**For pilots and deploy testing:** use `minReplicas: 1` so the container
starts immediately after deploy. Switch to `0` for production when you
want cost savings.

```bicep
scale: {
  minReplicas: 1   // 1 for pilots/testing, 0 for production cost savings
  maxReplicas: 3
}
```

---

## Azure Tenant Isolation (mandatory preflight)

> ⚠️ **Before ANY `az` or `azd` command in this skill, verify tenant
> isolation per the [`azure-tenant-isolation`](../azure-tenant-isolation/)
> skill.** Set `AZURE_CONFIG_DIR` + `AZD_CONFIG_DIR`, assert the tenant +
> subscription with `az account show`, then proceed. This is the #1 cause
> of "deployed to the wrong subscription" incidents.

---

## See Also

| Skill | Use When |
|-------|----------|
| [**threadlight-deploy**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-deploy/) | Phase 6 (Module Composer) is the consumer of this Bicep library |
| [**threadlight-design**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-design/) | Defines SPEC § 11c selectors that drive module inclusion |
| [**foundry-mcp-aca**](../foundry-mcp-aca/) | Owns the `aca-mcp.bicep` shape |
| [**foundry-teams-bot**](../foundry-teams-bot/) | Owns the `aca-bot.bicep` shape |
| [**foundry-iq**](../foundry-iq/) | Owns the `foundry-iq-index.bicep` shape |
| [**threadlight-event-triggers**](https://github.com/aiappsgbb/threadlight-skills/tree/main/skills/threadlight-event-triggers/) | Owns the `aca-job.bicep` shape (cron + manual triggers) |
| [**foundry-hosted-agents**](../foundry-hosted-agents/) | Owns the `foundry-account.bicep` shape |
| [**citadel-spoke-onboarding**](../citadel-spoke-onboarding/) | Adds Citadel hub wiring AFTER the base Bicep is provisioned (opt-in via SPEC § 11b `citadel.required: yes`) |
| [**azure-tenant-isolation**](../azure-tenant-isolation/) | Per-tenant `AZURE_CONFIG_DIR` so `azd up` lands in the right tenant |

**Note:** External threadlight-skills links (threadlight-deploy, threadlight-design, threadlight-event-triggers) point to a separate repository. For offline or agent-context use, abbreviated summaries of those skills are often included in local `threadlight-skills/SKILL.md` installations.

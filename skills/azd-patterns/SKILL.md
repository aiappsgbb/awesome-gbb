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
---

# AZD Tips & Patterns

Conventions and best practices for `azd` workflows, hooks, and ACA job deployments gathered from real repos.

---

## ACA Job Deployment

`azd` does not natively deploy Container Apps **Jobs** — only Container Apps. Jobs need a separate deployment step.

### Recommended: Python + `postdeploy` hook (cross-platform)

Used in newer repos (e.g. `threadlight-v2`). The pattern:

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

Older repos (e.g. `aigbb-demo-form`) use a `postprovision` hook with a PowerShell script:

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

resource processingJob 'Microsoft.App/jobs@2023-11-02-preview' = {
  name: '${prefix}-job-${uniqueId}'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${uamiResourceId}': {} }
  }

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
resource aiUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().subscriptionId, uami.outputs.principalId, 'ai-user')
  scope: foundryAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '...')
    principalId: uami.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}
```

### Exception: Hosted agent containers

Hosted agent containers get a **platform-managed dedicated identity** (instance + blueprint)
at deploy time — you don't assign a UAMI to them. The shared UAMI is for everything
else: bot ACA, MCP ACA, jobs, hooks, etc.
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
